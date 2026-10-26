"""Compiled desktop integration with owned data and a verifier that never launches a game."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_compiled_desktop as compiler
import build_compiled_release as release
import verify_compiled_release as audit


def sha(b): return hashlib.sha256(b).hexdigest()
def blob(value): return (json.dumps(value,ensure_ascii=False)+'\n').encode()
DEFAULT=dict(schema=2,resolution='1080p',window_mode='borderless',window_resolution='1280x720',frame_rate=60,native_gamepad=False,free_view=False)


def make_owned_fixture(base):
    base=Path(base);entries=base/'template';resources=base/'resources';resources.mkdir(parents=True)
    icon=base/'owned.ico';Image.new('RGBA',(32,32),(120,60,20,255)).save(icon)
    payload=compiler.entries(entries,icon)
    native=base/'OwnedNative.cs'
    native.write_text('''using System;using System.IO;using System.Collections.Generic;using System.Web.Script.Serialization;
class Owned {static int Main(string[] args){Console.OutputEncoding=new System.Text.UTF8Encoding(false);if(Array.IndexOf(args,"--verify-only")<0)return 73;
var e=new Dictionary<string,string>();foreach(System.Collections.DictionaryEntry x in Environment.GetEnvironmentVariables())if(x.Key.ToString().StartsWith("MC_"))e[x.Key.ToString()]=x.Value.ToString();
Console.WriteLine(new JavaScriptSerializer().Serialize(new {args=args,env=e,ini=File.ReadAllText("DDrawCompat-MagnaCarta.ini")}));
if(Environment.GetEnvironmentVariable("OWNED_EXTERNAL_EDIT")=="1")File.WriteAllText("DDrawCompat-MagnaCarta.ini","external edit");
return Environment.GetEnvironmentVariable("OWNED_FAIL")=="1"?17:0;}}''',encoding='utf8')
    subprocess.run([str(compiler.compiler()),'/nologo','/target:exe','/r:System.Web.Extensions.dll','/out:'+str(base/'owned.exe'),str(native)],check=True,capture_output=True)
    payload['modules/workspace_launcher.exe']=(base/'owned.exe').read_bytes()
    for name in ('display','configuration','field-return-height','gui-parent-guard','native-loading','scaled-font','minimap'):
        payload['modules/'+name+'.dll']=('owned '+name).encode()
    payload['scene.bin']=b'modified owned scene';payload['DDrawCompat-MagnaCarta.ini']=b'base display'
    payload['maps/0009.png']=b'owned map';payload['maps/0009.map']=b'owned metadata';payload['maps/label.txt']=b'owned label'
    payload['maps/manifest.json']=blob(dict(schema=1,navigation_verified=False,accepted=[dict(id=9,png_sha256=sha(payload['maps/0009.png']),metadata_sha256=sha(payload['maps/0009.map']))]))
    profiles={'baseline':sha(b'base display')}
    assets={'config/Configure.xaml':(ROOT/'src/configuration/Configure.xaml').read_bytes(),
            'config/configuration-ui.json':(ROOT/'locales/zh-CN/configuration-ui.json').read_bytes(),
            'config/enhancements.json':blob(DEFAULT),'config/encounter-ui.json':blob(dict(on='ON',off='OFF')),
            'config/profile-base.bin':bytes([0,1]+[0]*50),'MC.ico':icon.read_bytes(),
            'config/profiles/baseline.ini':b'base display'}
    logo=base/'logo.png';Image.new('RGBA',(1750,532),(30,80,110,255)).save(logo);assets['config/configuration-logo.png']=logo.read_bytes()
    for quality in ('1080p','2k','4k','auto'):
        for mode in ('fullscreen','windowed','borderless'):
            for fps in (30,60):
                name=f'md3-{quality}-{mode}-{fps}';data=('owned '+name).encode();profiles[name]=sha(data);assets['config/profiles/'+name+'.ini']=data
    files={n:sha(b) for n,b in payload.items() if n!='DDrawCompat-MagnaCarta.ini'}
    runtime=dict(schema=1,data_root='.',files=files,data={'scene.bin':sha(payload['scene.bin'])},profiles=profiles,
                 recipes=dict(configured=dict(module='configured',settings=None),baseline=dict(module='display',settings=dict(schema=1,display_profile='baseline',motion60=False,native_gamepad=False)),maps=dict(module='minimap',settings=None,maps=True)))
    for key,module in [('field_return_height','field-return-height'),('gui_parent_guard','gui-parent-guard'),('native_scene_loading','native-loading'),('scaled_font','scaled-font'),('map_overlay','minimap')]:
        runtime[key]=dict(schema=1,enabled=True,module=module)
    runtime['scaled_font']['scale']=4;runtime['test_candidates']=dict(schema=1,collision_guard=True,audio_provider_policy=True,contact_audio_trace=True)
    overlay=dict(schema=1,kind='clean_game_overlay',layout='flat',files={n:sha(b) for n,b in payload.items()},source_files={'scene.bin':sha(b'original owned scene')},changes=[dict(resource='scene.bin',source_sha256=sha(b'original owned scene'),target_sha256=sha(payload['scene.bin']))])
    assets['runtime.json']=blob(runtime);assets['Overlay-Manifest.json']=blob(overlay)
    for n,b in assets.items():
        p=resources/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
    for n,b in payload.items():
        p=entries/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
    compiler.core(entries/'modules/DesktopRuntime.dll',resources)
    return entries,resources,icon,payload


@unittest.skipUnless(os.name=='nt','Windows .NET/WPF integration')
class CompiledDesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace=tempfile.TemporaryDirectory(prefix='compiled desktop ')
        cls.base=Path(cls.workspace.name)
        cls.template,cls.resources,cls.icon,cls.payload=make_owned_fixture(cls.base)
    @classmethod
    def tearDownClass(cls): cls.workspace.cleanup()
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='compiled case ');self.addCleanup(self.temp.cleanup)
        self.case=Path(self.temp.name);self.root=self.case/'installation 空间';shutil.copytree(self.template,self.root)
        self.env=os.environ.copy();self.env['LOCALAPPDATA']=str(self.case/'user data');self.env.pop('OWNED_FAIL',None);self.env.pop('OWNED_EXTERNAL_EDIT',None)
        key=sha(str(self.root.resolve()).rstrip('\\/').upper().encode())[:16]
        self.user=self.case/'user data/MagnaCarta/Installations'/key;self.cache=self.user/'cache'
    def run_entry(self,name,*args,code=0):
        result=subprocess.run([str(self.root/(name+'.exe')),*map(str,args)],env=self.env,cwd=ROOT,timeout=30,capture_output=True)
        log=self.cache/(name+'.log');text=log.read_text(encoding='utf-8-sig') if log.exists() else result.stderr.decode(errors='replace')
        self.assertEqual(result.returncode,code,text);return text
    def settings(self,**updates):
        d=dict(DEFAULT,**updates);self.user.mkdir(parents=True,exist_ok=True);(self.user/'enhancements.json').write_bytes(blob(d));return d
    def launch_record(self): return json.loads((self.cache/'launcher.stdout.txt').read_text(encoding='utf-8-sig'))
    def test_compiled_launch_preserves_routes_flags_and_display_restore(self):
        self.assertIn('module=minimap',self.run_entry('Game','--verify-only'))
        data=self.launch_record();self.assertIn('--input-passthrough',data['args']);self.assertIn('--in-place-overlay',data['args'])
        for key in ('MC_FIELD_RETURN_HEIGHT','MC_GUI_PARENT_GUARD','MC_NATIVE_SCENE_LOADING','MC_SCALED_FONT','MC_MAP_OVERLAY','MC_COLLISION_GUARD','MC_AUDIO_PROVIDER_POLICY','MC_CONTACT_AUDIO_TRACE','MC_MOTION60_COMPLETE'):
            self.assertEqual(data['env'][key],'1',key)
        self.assertEqual(data['env']['MC_FREE_VIEW'],'0');self.assertEqual(data['ini'],'owned md3-1080p-borderless-60')
        self.assertEqual((self.root/'DDrawCompat-MagnaCarta.ini').read_bytes(),b'base display')
        self.assertEqual((self.cache/'profile.bin').read_bytes(),bytes(52))
        self.assertEqual(json.loads((self.user/'enhancements.json').read_text()),DEFAULT)
        self.assertFalse((self.root/'config').exists())
    def test_all_24_display_profiles_and_window_size(self):
        for quality in ('1080p','2k','4k','auto'):
            for mode in ('fullscreen','windowed','borderless'):
                for fps in (30,60):
                    self.settings(resolution=quality,window_mode=mode,frame_rate=fps,window_resolution='1600x900')
                    self.run_entry('Game','--verify-only');data=self.launch_record()
                    self.assertEqual(data['ini'],f'owned md3-{quality}-{mode}-{fps}')
                    self.assertEqual(data['env']['MC_MOTION60_COMPLETE'],str(int(fps==60)))
                    self.assertEqual(data['env'].get('MC_WINDOW_RESOLUTION',''),'1600x900' if mode=='windowed' else '')
    def test_existing_user_settings_win_over_legacy(self):
        value=self.settings(resolution='2k',frame_rate=30);(self.root/'config').mkdir();(self.root/'config/enhancements.json').write_bytes(blob(DEFAULT))
        self.run_entry('Game','--verify-only');self.assertEqual(json.loads((self.user/'enhancements.json').read_text()),value)
        self.assertEqual(json.loads((self.root/'config/enhancements.json').read_text()),DEFAULT)
    def test_legacy_migration_and_preservation(self):
        legacy=dict(DEFAULT,resolution='auto',frame_rate=30);(self.root/'config').mkdir();p=self.root/'config/enhancements.json';p.write_bytes(blob(legacy));before=p.read_bytes()
        self.run_entry('Game','--verify-only');self.assertEqual((self.user/'enhancements.json').read_text(),json.dumps(legacy,separators=(',',':')));self.assertEqual(p.read_bytes(),before)
    def test_baseline_and_stable_preserve_isolated_toggle_semantics(self):
        self.run_entry('Game','--verify-only','--recipe','baseline');data=self.launch_record();self.assertIn(str(self.root/'modules/display.dll'),data['args']);self.assertEqual(data['env']['MC_MAP_OVERLAY'],'0');self.assertEqual(data['env']['MC_SCALED_FONT'],'0')
        self.run_entry('Game','--verify-only','--without-test-candidates');data=self.launch_record();self.assertEqual(data['env']['MC_COLLISION_GUARD'],'0');self.assertEqual(data['env']['MC_MAP_OVERLAY'],'1')
    def test_invalid_settings_do_not_touch_installation(self):
        for changes in ({'frame_rate':'60'},{'schema':True},{'window_mode':'bad'},{'extra':1},{'native_gamepad':1}):
            self.settings(**changes);self.run_entry('Game','--verify-only',code=1);self.assertEqual((self.root/'DDrawCompat-MagnaCarta.ini').read_bytes(),b'base display')
    def test_hash_drift_rejects_before_native_launch(self):
        (self.root/'scene.bin').write_bytes(b'drift');self.run_entry('Game','--verify-only',code=1);self.assertFalse((self.cache/'launcher.stdout.txt').exists())
    def test_installed_check_includes_unbundled_baseline_dependency(self):
        resources=self.case/'changed resources';shutil.copytree(self.resources,resources)
        runtime=json.loads((resources/'runtime.json').read_bytes())
        runtime['data']['Asura.dll']=sha(b'owned supported library')
        (resources/'runtime.json').write_bytes(blob(runtime))
        compiler.core(self.root/'modules/DesktopRuntime.dll',resources)
        (self.root/'Asura.dll').write_bytes(b'owned other library version')
        self.assertIn('Hash mismatch: Asura.dll',self.run_entry('Game','--check-installed',code=1))
        self.assertFalse((self.cache/'launcher.stdout.txt').exists())
        (self.root/'Asura.dll').write_bytes(b'owned supported library')
        self.assertIn('OVERLAY_MODIFIED PASS',self.run_entry('Game','--check-installed'))

    def test_hash_error_records_expected_and_actual_digests(self):
        (self.root/'scene.bin').write_bytes(b'drift')
        log=self.run_entry('Game','--verify-only',code=1)
        self.assertIn('expected='+sha(b'modified owned scene'),log)
        self.assertIn('actual='+sha(b'drift'),log)

    def diagnostic_status(self,started):
        script="$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[Text.UTF8Encoding]::new($false); [Reflection.Assembly]::LoadFrom($args[0]) | Out-Null; [DesktopRuntime.LaunchDiagnostics]::Failure($args[1],1,[DateTime]::Parse($args[2]).ToUniversalTime())"
        path=self.case/'diagnostic.ps1';path.write_text(script,encoding='utf-8-sig')
        r=subprocess.run(['powershell.exe','-NoProfile','-File',str(path),str(self.root/'modules/DesktopRuntime.dll'),str(self.cache),started],capture_output=True,timeout=30)
        self.assertEqual(r.returncode,0,r.stderr.decode(errors='replace'))
        return r.stdout.decode('utf8').strip()

    def test_failed_status_names_mismatched_file_and_retains_log_path(self):
        (self.root/'scene.bin').write_bytes(b'drift');self.run_entry('Game','--verify-only',code=1)
        text=self.diagnostic_status('2000-01-01T00:00:00Z')
        self.assertIn('scene.bin',text);self.assertIn('文件版本不匹配',text);self.assertIn(str(self.cache),text)
        self.assertNotIn('System.IO',text);self.assertNotIn('expected=',text)

    def test_failed_status_ignores_stale_or_missing_diagnostics(self):
        self.cache.mkdir(parents=True)
        (self.cache/'Game.log').write_text('COMPILED_DESKTOP FAIL System.IO.InvalidDataException: Hash mismatch: old.dll',encoding='utf-8-sig')
        text=self.diagnostic_status('2100-01-01T00:00:00Z');self.assertNotIn('old.dll',text)
        (self.cache/'Game.log').unlink();self.assertEqual(text,self.diagnostic_status('2000-01-01T00:00:00Z'))

    def test_failure_restores_ini_and_preserves_prior_profile_log(self):
        self.settings();self.cache.mkdir();(self.cache/'profile.log').write_bytes(b'prior diagnostic');self.env['OWNED_FAIL']='1'
        self.assertIn('exit=17',self.run_entry('Game','--verify-only',code=1));self.assertEqual((self.root/'DDrawCompat-MagnaCarta.ini').read_bytes(),b'base display');self.assertEqual((self.cache/'profile.log').read_bytes(),b'prior diagnostic')
    def test_external_display_edit_preserved(self):
        self.env['OWNED_EXTERNAL_EDIT']='1';self.assertIn('External display edit preserved',self.run_entry('Game','--verify-only',code=1));self.assertEqual((self.root/'DDrawCompat-MagnaCarta.ini').read_text(),'external edit')
    def test_loose_scripts_and_external_manifests_are_not_loaded(self):
        (self.root/'Start.ps1').write_text('exit 99');(self.root/'runtime.json').write_text('not json');(self.root/'Overlay-Manifest.json').write_text('not json')
        self.run_entry('Game','--verify-only');self.run_entry('Game','--check-installed')
    def test_headless_configuration_uses_embedded_ui_and_icon(self):
        preview=self.case/'preview.png';log=self.run_entry('Configure','--self-test','--preview',preview)
        self.assertIn('choices=14 icon=embedded resources=embedded visible=false',log)
        self.assertFalse((self.user/'enhancements.json').exists())
        with Image.open(preview) as im:self.assertEqual(im.size,(720,600));self.assertGreater(len(im.getcolors(1000000)),20)
    def test_complete_baseline_modified_rollback_on_owned_files(self):
        original=self.case/'original';original.mkdir();(original/'scene.bin').write_bytes(b'original owned scene')
        self.run_entry('Game','--check-baseline',original);self.run_entry('Game','--check-installed')
        (self.root/'MC00.SAV').write_bytes(b'personal save');value=self.settings(resolution='4k')
        self.assertIn('OVERLAY_ROLLBACK PASS',self.run_entry('Game','--rollback',original))
        self.assertEqual((self.root/'scene.bin').read_bytes(),b'original owned scene');self.assertEqual((self.root/'MC00.SAV').read_bytes(),b'personal save');self.assertEqual(json.loads((self.user/'enhancements.json').read_text()),value)
        self.assertTrue((self.root/'Game.exe').exists());self.assertTrue((self.root/'modules/DesktopRuntime.dll').exists());self.run_entry('Game','--check-baseline',self.root)
    def test_bad_rollback_original_preflight_has_no_partial_writes(self):
        original=self.case/'original';original.mkdir();(original/'scene.bin').write_bytes(b'wrong original');before={p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        self.run_entry('Game','--rollback',original,code=1);self.assertEqual(before,{p.relative_to(self.root).as_posix():p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
    def test_invalid_arguments(self):
        self.run_entry('Game','--unknown',code=2);self.run_entry('Game','--rollback',code=2);self.run_entry('Game','--self-test',code=2);self.run_entry('Game','--rollback',self.case,'--verify-only',code=2)
    def test_requested_hotkey_copy_and_compact_hint_spacing(self):
        catalog=json.loads((ROOT/'locales/zh-CN/configuration-ui.json').read_text(encoding='utf8'))
        self.assertEqual(catalog['pending'].split('  '), ['F5切换随机遇敌','F9切换小地图','F10普通自动连招','F11暴走模式自动连招'])
        self.assertNotIn('\n',catalog['pending'])
        self.assertEqual(catalog['pending'],catalog['controls'])
        markup=(ROOT/'src/configuration/Configure.xaml').read_text(encoding='utf-8-sig')
        self.assertIn('Width="720" Height="600"',markup)
        self.assertIn('Name="Pending" Style="{StaticResource Hint}" Margin="12,0,12,0" LineHeight="17"',markup)

    def test_header_has_no_quality_note_and_symmetric_logo_columns(self):
        import xml.etree.ElementTree as ET
        ns={'w':'http://schemas.microsoft.com/winfx/2006/xaml/presentation'}
        name='{http://schemas.microsoft.com/winfx/2006/xaml}Name'
        tree=ET.parse(ROOT/'src/configuration/Configure.xaml')
        self.assertFalse(any(n.get('Name')=='Quality' for n in tree.iter()))
        header=next(n for n in tree.iter() if n.get(name)=='HeaderGrid')
        widths=[n.get('Width') for n in header.find('w:Grid.ColumnDefinitions',ns)]
        self.assertEqual(widths,['*','220','*'])
        self.assertIn('COMPILED_HEADER PASS centered=true quality_note=absent',self.run_entry('Configure','--self-test'))

    def test_no_interpreter_code_in_compiled_sources(self):
        source='\n'.join((ROOT/'src/desktop'/n).read_text() for n in ('RuntimeCore.cs','Configuration.cs','CompiledEntry.cs'))
        for forbidden in ('powershell.exe','System.Management.Automation','-ExecutionPolicy','Start.ps1'):
            self.assertNotIn(forbidden,source)

    def test_package_embeds_resources_and_verifies_without_any_scripts(self):
        payload=dict(self.payload)
        for p in self.resources.rglob('*'):
            if p.is_file() and p.relative_to(self.resources).as_posix().startswith('config/'):
                payload[p.relative_to(self.resources).as_posix()]=p.read_bytes()
        old_ui=json.loads(payload['config/configuration-ui.json']);old_ui.pop('failed_detail',None);old_ui.pop('file_mismatch',None)
        payload['config/configuration-ui.json']=blob(old_ui)
        payload['Start.ps1']=b'owned previous startup';payload['Verify-Overlay.ps1']=b'owned previous verifier'
        runtime=json.loads((self.resources/'runtime.json').read_bytes())
        runtime['files'].update({n:sha(b) for n,b in payload.items() if n.startswith('config/') or n.endswith('.ps1')})
        payload['runtime.json']=blob(runtime)
        manifest=json.loads((self.resources/'Overlay-Manifest.json').read_bytes());manifest['files']={n:sha(b) for n,b in payload.items()}
        payload['Overlay-Manifest.json']=blob(manifest);source=self.case/'source.zip'
        with zipfile.ZipFile(source,'w') as z:
            for n,b in payload.items():z.writestr(n,b)
        out=self.case/'compiled.zip';work=self.case/'work'
        release.build(source,sha(source.read_bytes()),self.icon,work,out)
        audit.verify(out,self.icon)
        with zipfile.ZipFile(out) as z:
            self.assertIsNone(z.testzip());self.assertEqual(z.read('scene.bin'),b'modified owned scene')
            self.assertFalse(any(n.startswith('config/') or n.endswith(('.ps1','.psm1','.xaml')) or n in release.REMOVED for n in z.namelist()))
            core=z.read('modules/DesktopRuntime.dll');self.assertIn(self.icon.read_bytes(),core)
            self.assertIn((work/'resources/runtime.json').read_bytes(),core)
            self.assertIn((work/'resources/Overlay-Manifest.json').read_bytes(),core)
            installed=self.case/'packaged installation';z.extractall(installed)
        self.root=installed
        key=sha(str(installed.resolve()).rstrip('\\/').upper().encode())[:16]
        self.user=self.case/'user data/MagnaCarta/Installations'/key;self.cache=self.user/'cache'
        self.run_entry('Game','--check-installed');self.run_entry('Game','--verify-only');self.run_entry('Configure','--self-test')
        self.assertFalse(json.loads((work/'resources/Overlay-Manifest.json').read_bytes())['in_game_verified'])
        (self.root/'scene.bin').write_bytes(b'drift');self.run_entry('Game','--verify-only',code=1)
        self.assertIn('文件版本不匹配',self.diagnostic_status('2000-01-01T00:00:00Z'))

    def test_bad_source_hash_and_icon_rejected(self):
        source=self.case/'wrong.zip';source.write_bytes(b'owned invalid source')
        with self.assertRaisesRegex(ValueError,'hash mismatch'):
            release.build(source,'0'*64,self.icon,self.case/'work',self.case/'new.zip')
        self.assertFalse((self.case/'new.zip').exists())
        bad=self.case/'bad.ico';bad.write_bytes(b'not an icon')
        with self.assertRaises(ValueError):compiler.icon_bytes(bad)


if __name__=='__main__':unittest.main()
