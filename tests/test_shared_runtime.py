import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import prepare_shared_runtime as tool


class SharedRuntimeTests(unittest.TestCase):
    def test_ignore_generated_runtime_not_runtime_source(self):
        rules=(Path(__file__).resolve().parents[1]/'.gitignore').read_text(encoding='utf8').splitlines()
        self.assertIn('/runtime/',rules)
        self.assertNotIn('runtime/',rules)

    def inputs(self,root):
        game=root/'game'; prior=game/'.advanced-runtime'; prior.mkdir(parents=True)
        locale=game/'.locale-runtime'; (locale/'session-owned').mkdir(parents=True)
        (locale/'PrepareProfile.ps1').write_bytes(b'owned profile preparer')
        (locale/'session-owned/profile.bin').write_bytes(bytes(52))
        (game/'engine.dll').write_bytes(b'owned engine'); (game/'title.bgr').write_bytes(b'owned title')
        profiles={}
        for name in ['baseline','render4k','wide4k','fps60','combined']:
            (prior/(name+'.ini')).write_bytes(name.encode()); profiles[name]=tool.sha(prior/(name+'.ini'))
        (prior/'manifest.json').write_text(json.dumps(dict(schema=1,workspace=str(game),source_hashes={'engine.dll':tool.sha(game/'engine.dll')},config='config.ini',profiles=profiles)))
        (prior/'title-background.json').write_text(json.dumps(dict(active=True,tiles={'title.bgr':dict(after=tool.sha(game/'title.bgr'))})))
        (prior/'enhancements.json').write_text(json.dumps(tool.settings()))
        (prior/'configuration-ui.json').write_bytes(b'owned locale UI')
        native=root/'native.dll'; native.write_bytes(b'owned module')
        modules={name:native for name in ['display','modern','texture','camera','maps','launcher','configuration']}
        atlas=root/'atlas'; atlas.mkdir()
        (atlas/'manifest.json').write_text(json.dumps(dict(schema=1,navigation_verified=False,accepted=[])))
        (atlas/'label.txt').write_bytes(b'owned label')
        return game,modules,atlas

    def test_never_copies_game_and_all_recipes_share_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); game,modules,atlas=self.inputs(root); out=root/'runtime'
            before=tool.sha(game/'engine.dll'); m=tool.prepare(game,modules,atlas,out)
            self.assertEqual(before,tool.sha(game/'engine.dll'))
            self.assertFalse((out/'data').exists())
            self.assertEqual(m['data_root'],'data')
            self.assertEqual(m['configured_modules']['motion'],'modern')
            self.assertEqual(len(m['recipes']),14)
            self.assertTrue(m['recipes']['camera']['camera'])
            self.assertTrue(m['recipes']['camera-gamepad']['camera'])
            self.assertTrue(m['recipes']['camera-gamepad']['settings']['native_gamepad'])
            self.assertTrue(m['recipes']['maps']['maps'])
            self.assertTrue(m['recipes']['maps-gamepad']['maps'])
            self.assertTrue(m['recipes']['maps-gamepad']['settings']['native_gamepad'])
            self.assertTrue((out/'Configure.cmd').is_file())
            self.assertIn(b'set MC_TITLE_STYLE=0', (out/'Play-title-original.cmd').read_bytes())
            self.assertEqual(tool.sha(out/'Play-title-original.cmd'),m['files']['Play-title-original.cmd'])
            self.assertRaises(ValueError,tool.prepare,game,modules,atlas,out)

    def test_optional_height_module_sets_default_route_preserving_original_roles(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);game,modules,atlas=self.inputs(root)
            modules['field-return-height']=modules['display']
            out=root/'runtime';m=tool.prepare(game,modules,atlas,out)
            self.assertEqual(m['field_return_height'],dict(schema=1,enabled=True,module='field-return-height'))
            self.assertEqual(m['recipes']['baseline']['module'],'display')
            self.assertIn('modules/display.dll',m['files'])
            self.assertIn('modules/field-return-height.dll',m['files'])
            self.assertFalse((out/'Play-stairwell-fix.cmd').exists())

    def test_source_hash_drift_rejected_before_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); game,modules,atlas=self.inputs(root)
            (game/'engine.dll').write_bytes(b'drift')
            self.assertRaises(ValueError,tool.prepare,game,modules,atlas,root/'runtime')
            self.assertFalse((root/'runtime').exists())

    def test_current_candidates_are_preserved_when_repackaging(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); game,modules,atlas=self.inputs(root)
            motion=root/'motion.dll'; motion.write_bytes(b'current owned motion candidate')
            pad=root/'pad.dll'; pad.write_bytes(b'current owned input candidate')
            modules.update({'motion-space':motion,'input-diagnostics':pad})
            m=tool.prepare(game,modules,atlas,root/'runtime')
            self.assertEqual(m['recipes']['motion']['module'],'motion-space')
            self.assertEqual(m['recipes']['gamepad']['module'],'input-diagnostics')
            self.assertEqual(m['configured_modules']['combined'],'input-diagnostics')
            self.assertEqual(m['files']['modules/motion-space.dll'],tool.sha(motion))
            self.assertEqual(m['files']['modules/input-diagnostics.dll'],tool.sha(pad))
            for recipe in ['gamepad','motion-gamepad','camera-gamepad','maps-gamepad']:
                self.assertEqual(m['recipes'][recipe]['module'],'input-diagnostics',recipe)
            self.assertEqual(m['recipes']['camera']['module'],'camera')
            self.assertEqual(m['recipes']['maps']['module'],'maps')

    def test_motion_gamepad_recipe_has_both_controls_without_camera(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); game,modules,atlas=self.inputs(root)
            m=tool.prepare(game,modules,atlas,root/'runtime')
            recipe=m['recipes']['motion-gamepad']
            self.assertTrue(recipe['settings']['motion60'])
            self.assertTrue(recipe['settings']['native_gamepad'])
            self.assertEqual(recipe['settings']['display_profile'],'combined')
            self.assertNotIn('camera',recipe)
