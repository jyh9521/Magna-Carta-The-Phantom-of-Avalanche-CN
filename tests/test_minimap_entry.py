"""Exercise the actual shared entry with an owned verifier, never a game."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import prepare_shared_runtime as package
import test_shared_runtime as shared_fixtures


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atlas_fixture(atlas):
    atlas.mkdir(exist_ok=True)
    (atlas/'0009.png').write_bytes(b'owned image; not loaded by the entry verifier')
    (atlas/'0009.map').write_bytes(b'owned metadata; not loaded by the entry verifier')
    (atlas/'label.txt').write_bytes('Terrain'.encode('utf-16le'))
    row=dict(id=9,png_sha256=digest(atlas/'0009.png'),metadata_sha256=digest(atlas/'0009.map'))
    manifest=dict(schema=1,navigation_verified=False,accepted=[row])
    (atlas/'manifest.json').write_text(json.dumps(manifest),encoding='utf8')
    return manifest


class MinimapPackageTests(unittest.TestCase):
    def inputs(self, root):
        return shared_fixtures.SharedRuntimeTests().inputs(root)

    def test_optional_module_copies_hash_locked_maps_without_game_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);game,modules,atlas=self.inputs(root)
            atlas_fixture(atlas);modules['minimap']=modules['configuration']
            (atlas/'hint.txt').write_bytes('F9: mini / full / off'.encode('utf-16le'))
            out=root/'runtime';manifest=package.prepare(game,modules,atlas,out)
            self.assertEqual(manifest['map_overlay'],dict(schema=1,enabled=True,module='minimap'))
            self.assertEqual(manifest['recipes']['baseline']['module'],'display')
            self.assertFalse((out/'data').exists())
            for name in ('modules/minimap.dll','maps/manifest.json','maps/label.txt','maps/hint.txt','maps/0009.png','maps/0009.map'):
                self.assertEqual(digest(out/name),manifest['files'][name])

    def test_minimap_rejects_empty_or_drifted_atlas_before_output(self):
        for failure in ('empty','drift','duplicate','identifier'):
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);game,modules,atlas=self.inputs(root)
                modules['minimap']=modules['configuration'];out=root/'runtime'
                if failure!='empty':
                    manifest=atlas_fixture(atlas)
                    if failure=='drift':(atlas/'0009.png').write_bytes(b'changed')
                    elif failure=='duplicate':manifest['accepted']*=2
                    else:manifest['accepted'][0]['id']=True
                    (atlas/'manifest.json').write_text(json.dumps(manifest),encoding='utf8')
                with self.assertRaises(ValueError):package.prepare(game,modules,atlas,out)
                self.assertFalse(out.exists())

    def test_legacy_package_does_not_enable_new_default_route(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);game,modules,atlas=self.inputs(root)
            manifest=package.prepare(game,modules,atlas,root/'runtime')
            self.assertNotIn('map_overlay',manifest)
            self.assertNotIn('modules/minimap.dll',manifest['files'])

    def bound_labels(self, root, atlas):
        from build_map_atlas import map_labels
        source=root/'map-ui.json'
        source.write_text(json.dumps(dict(map_title='Terrain',map_hint='F9: mini / full / off')),encoding='utf8')
        payload,record=map_labels(source)
        for name,data in payload.items():(atlas/name).write_bytes(data)
        return record

    def test_generated_label_provenance_matches_package_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);game,modules,atlas=self.inputs(root)
            manifest=atlas_fixture(atlas);manifest['labels']=self.bound_labels(root,atlas)
            (atlas/'manifest.json').write_text(json.dumps(manifest),encoding='utf8')
            assets=package.map_assets(atlas,require_nonempty=True)
            for name,expected in manifest['labels']['files'].items():
                self.assertEqual(assets['maps/'+name],expected)
            self.assertNotIn('maps/legend.txt',assets)

    def test_label_tampering_and_malformed_provenance_reject_before_output(self):
        cases=('text','encoding','field','source_sha','file_sha','missing_label',
               'unknown_file','extra_file','missing_file','unicode','too_long','newline')
        for failure in cases:
            with self.subTest(failure=failure),tempfile.TemporaryDirectory() as directory:
                root=Path(directory);game,modules,atlas=self.inputs(root)
                modules['minimap']=modules['configuration'];out=root/'runtime'
                manifest=atlas_fixture(atlas);labels=self.bound_labels(root,atlas);manifest['labels']=labels
                if failure=='text':(atlas/'hint.txt').write_bytes('Changed'.encode('utf-16le'))
                elif failure=='encoding':labels['encoding']='utf-8'
                elif failure=='field':labels['unexpected']=True
                elif failure=='source_sha':labels['source_sha256']='not-a-sha'
                elif failure=='file_sha':labels['files']['hint.txt']='0'*64
                elif failure=='missing_label':del labels['files']['label.txt']
                elif failure=='unknown_file':labels['files']['outside.txt']='0'*64
                elif failure=='extra_file':(atlas/'legend.txt').write_bytes('Extra'.encode('utf-16le'))
                elif failure=='missing_file':(atlas/'hint.txt').unlink()
                else:
                    data={'unicode':b'\x00','too_long':('x'*256).encode('utf-16le'),
                          'newline':'two\nlines'.encode('utf-16le')}[failure]
                    (atlas/'hint.txt').write_bytes(data);labels['files']['hint.txt']=digest(atlas/'hint.txt')
                (atlas/'manifest.json').write_text(json.dumps(manifest),encoding='utf8')
                with self.assertRaisesRegex(ValueError,'map label|Map label|UTF-16LE'):
                    package.prepare(game,modules,atlas,out)
                self.assertFalse(out.exists())


@unittest.skipUnless(os.name=='nt','Owned Win32 entry verifier')
class MinimapEntryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory(dir=ROOT/'build',prefix='minimap-verifier-')
        cls.exe=Path(cls.temporary.name)/'owned-verifier.exe'
        source=('public class OwnedMapVerifier { public static int Main(string[] args) {'
                'if(System.Array.IndexOf(args,"--verify-only")<0)return 88;'
                'string text=System.String.Join("|",args);'
                'foreach(string key in new string[]{"MC_MAP_OVERLAY","MC_MAP_ASSETS","MC_FREE_VIEW","MC_FIELD_RETURN_HEIGHT","MC_GUI_PARENT_GUARD","MC_NATIVE_SCENE_LOADING","MC_SCALED_FONT"})'
                'text+="|"+key+"="+System.Environment.GetEnvironmentVariable(key);'
                'System.IO.File.WriteAllText(System.Environment.GetEnvironmentVariable("OWNED_MAP_CAPTURE"),text);'
                'return 0; }}')
        command="Add-Type -TypeDefinition '"+source+"' -OutputAssembly '"+str(cls.exe)+"' -OutputType ConsoleApplication"
        result=subprocess.run(['powershell.exe','-NoProfile','-Command',command],capture_output=True,text=True,timeout=30)
        if result.returncode:raise RuntimeError(result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def fixture(self, root, integration=True):
        for name in ('data','config/profiles','modules','maps'):(root/name).mkdir(parents=True)
        start=Path(os.environ.get('MINIMAP_START_SOURCE',ROOT/'src/configuration/StartShared.ps1'))
        shutil.copyfile(start,root/'Start.ps1')
        shutil.copyfile(ROOT/'src/configuration/EnhancementSettings.psm1',root/'config/EnhancementSettings.psm1')
        shutil.copyfile(self.exe,root/'modules/workspace_launcher.exe')
        for name in ('display','scaled-font','minimap'):(root/'modules'/f'{name}.dll').write_bytes(b'owned module; never loaded')
        (root/'data/DDrawCompat-MagnaCarta.ini').write_bytes(b'owned display\r\n')
        (root/'config/profiles/wide4k.ini').write_bytes(b'owned display\r\n')
        (root/'config/profile-base.bin').write_bytes(bytes(52))
        (root/'config/PrepareProfile.ps1').write_text('function Convert-CompatibilityProfile([byte[]]$Value){return ,$Value}')
        settings=dict(schema=1,display_profile='wide4k',motion60=False,native_gamepad=False)
        (root/'config/enhancements.json').write_text(json.dumps(settings))
        atlas_fixture(root/'maps')
        files={name:digest(root/name) for name in ('modules/minimap.dll','maps/manifest.json','maps/label.txt','maps/0009.png','maps/0009.map')}
        # Production mutex identity is the manifest hash. Independent owned
        # fixtures must not collide when another test process runs in parallel.
        manifest=dict(schema=1,owned_fixture=str(root),data={},files=files,profiles={'wide4k':digest(root/'config/profiles/wide4k.ini')},
                      recipes={'configured':dict(module='configured'),'baseline':dict(module='display'),'maps':dict(module='maps',maps=True)},
                      configured_modules={'display':'display'},
                      field_return_height=dict(schema=1,enabled=True,module='field-return-height'),
                      gui_parent_guard=dict(schema=1,enabled=True,module='gui-parent-guard'),
                      native_scene_loading=dict(schema=1,enabled=True,module='native-loading'),
                      scaled_font=dict(schema=1,enabled=True,module='scaled-font',scale=4))
        if integration:manifest['map_overlay']=dict(schema=1,enabled=True,module='minimap')
        self.save_manifest(root,manifest)
        return manifest

    def save_manifest(self, root, manifest):
        (root/'runtime.json').write_text(json.dumps(manifest),encoding='utf8')

    def invoke(self, root, recipe='configured'):
        env=os.environ.copy();env['LOCALAPPDATA']=str(root/'user data')
        env['OWNED_MAP_CAPTURE']=str(root/'capture.txt')
        env['MC_MAP_OVERLAY']='parent';env['MC_MAP_ASSETS']='parent assets'
        code=("$ErrorActionPreference='Stop';& '"+str(root/'Start.ps1')+"' -Recipe "+recipe+" -VerifyOnly;"
              "if($env:MC_MAP_OVERLAY -ne 'parent' -or $env:MC_MAP_ASSETS -ne 'parent assets'){throw 'Map environment leaked'};"
              "'MAP_ENVIRONMENT_RESTORED'")
        return subprocess.run(['powershell.exe','-NoProfile','-Command',code],capture_output=True,text=True,env=env,timeout=30)

    def test_configured_and_maps_use_current_module_and_preserve_fixes(self):
        for recipe in ('configured','maps'):
            with self.subTest(recipe=recipe),tempfile.TemporaryDirectory(dir=ROOT/'build',prefix='minimap-entry-') as directory:
                root=Path(directory);self.fixture(root);result=self.invoke(root,recipe)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertIn('module=minimap',result.stdout)
                self.assertIn('map_overlay=True',result.stdout)
                self.assertIn('MAP_ENVIRONMENT_RESTORED',result.stdout)
                actual=(root/'capture.txt').read_text()
                self.assertIn('minimap.dll',actual);self.assertIn('--input-passthrough',actual)
                self.assertNotIn('--native-gamepad',actual)
                self.assertIn('MC_MAP_OVERLAY=1',actual);self.assertIn('MC_MAP_ASSETS='+str(root/'maps'),actual)
                for name in ('MC_FIELD_RETURN_HEIGHT','MC_GUI_PARENT_GUARD','MC_NATIVE_SCENE_LOADING','MC_SCALED_FONT'):
                    self.assertIn(name+'=1',actual)
                self.assertIn('MC_FREE_VIEW=0',actual)
                self.assertEqual((root/'data/DDrawCompat-MagnaCarta.ini').read_bytes(),b'owned display\r\n')

    def test_baseline_disabled_and_legacy_configured_keep_maps_off(self):
        for kind in ('baseline','disabled','legacy'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory(dir=ROOT/'build',prefix='minimap-entry-') as directory:
                root=Path(directory);manifest=self.fixture(root,integration=kind!='legacy')
                if kind=='disabled':manifest['map_overlay']['enabled']=False
                self.save_manifest(root,manifest)
                result=self.invoke(root,'baseline' if kind=='baseline' else 'configured')
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertIn('map_overlay=False',result.stdout)
                actual=(root/'capture.txt').read_text()
                self.assertIn('MC_MAP_OVERLAY=0',actual);self.assertNotIn('--input-passthrough',actual)
                self.assertNotIn('minimap.dll',actual)

    def test_legacy_explicit_maps_recipe_remains_available(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build',prefix='minimap-entry-') as directory:
            root=Path(directory);self.fixture(root,integration=False);result=self.invoke(root,'maps')
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            actual=(root/'capture.txt').read_text()
            self.assertIn('MC_MAP_OVERLAY=1',actual);self.assertIn('--input-passthrough',actual)
            self.assertNotIn('minimap.dll',actual)

    def test_invalid_integration_or_assets_reject_before_verifier(self):
        for kind in ('schema','boolean','module','missing','empty','digest','identifier'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory(dir=ROOT/'build',prefix='minimap-entry-') as directory:
                root=Path(directory);manifest=self.fixture(root)
                if kind=='schema':manifest['map_overlay']['schema']='1'
                elif kind=='boolean':manifest['map_overlay']['enabled']='true'
                elif kind=='module':manifest['map_overlay']['module']='maps'
                elif kind=='missing':del manifest['files']['modules/minimap.dll']
                else:
                    atlas=json.loads((root/'maps/manifest.json').read_text())
                    if kind=='empty':atlas['accepted']=[]
                    elif kind=='digest':atlas['accepted'][0]['png_sha256']='0'*64
                    else:atlas['accepted'][0]['id']=True
                    (root/'maps/manifest.json').write_text(json.dumps(atlas))
                    manifest['files']['maps/manifest.json']=digest(root/'maps/manifest.json')
                self.save_manifest(root,manifest);result=self.invoke(root)
                self.assertNotEqual(result.returncode,0)
                self.assertFalse((root/'capture.txt').exists())


if __name__=='__main__':unittest.main()
