import hashlib
import json
from pathlib import Path
import sys
import tempfile
import struct
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
            self.assertFalse((out/'Play-diagnostic.cmd').exists())
            self.assertNotIn('modules/capture_helper.exe',m['files'])
            self.assertIn(b'set MC_TITLE_STYLE=0', (out/'Play-title-original.cmd').read_bytes())
            self.assertEqual(tool.sha(out/'Play-title-original.cmd'),m['files']['Play-title-original.cmd'])
            self.assertRaises(ValueError,tool.prepare,game,modules,atlas,out)

    def capture_helper(self, root, machine=0x14c, magic=0x10b, flags=0x0102):
        # Owned PE header fixture, never executed or loaded.
        data=bytearray(512);data[:2]=b'MZ';struct.pack_into('<I',data,0x3c,0x80)
        data[0x80:0x84]=b'PE\0\0';struct.pack_into('<HH',data,0x84,machine,1)
        struct.pack_into('<HHH',data,0x94,224,flags,magic)
        path=root/'capture_helper.exe';path.write_bytes(data);return path

    def test_optional_capture_helper_generates_hash_locked_manual_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);game,modules,atlas=self.inputs(root)
            helper=self.capture_helper(root);out=root/'runtime'
            m=tool.prepare(game,modules,atlas,out,capture_helper=helper)
            self.assertIn(b'-Recipe configured -CaptureException',(out/'Play-diagnostic.cmd').read_bytes())
            for name in ('Play-diagnostic.cmd','modules/capture_helper.exe'):
                self.assertEqual(tool.sha(out/name),m['files'][name])
            self.assertEqual((out/'modules/capture_helper.exe').read_bytes(),helper.read_bytes())
            self.assertFalse((out/'data').exists())

    def test_capture_helper_wrong_type_rejected_before_output(self):
        for machine,magic,flags in ((0x8664,0x20b,0x0102),(0x14c,0x10b,0x2102),
                                    (0x14c,0x10b,0x0100)):
            with self.subTest(machine=machine,magic=magic,flags=flags):
                with tempfile.TemporaryDirectory() as directory:
                    root=Path(directory);game,modules,atlas=self.inputs(root)
                    helper=self.capture_helper(root,machine,magic,flags);out=root/'runtime'
                    with self.assertRaisesRegex(ValueError,'capture helper'):
                        tool.prepare(game,modules,atlas,out,capture_helper=helper)
                    self.assertFalse(out.exists())
        with self.assertRaisesRegex(ValueError,'capture helper'):
            tool.check_capture_helper(b'not an executable')

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

    def test_gui_guard_preserves_prior_module_and_has_no_new_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);game,modules,atlas=self.inputs(root)
            modules['gui-parent-guard']=modules['display'];out=root/'runtime'
            with self.assertRaisesRegex(ValueError,'retained field return'):tool.prepare(game,modules,atlas,out)
            self.assertFalse(out.exists())
            modules['field-return-height']=modules['display'];m=tool.prepare(game,modules,atlas,out)
            self.assertEqual(m['gui_parent_guard'],dict(schema=1,enabled=True,module='gui-parent-guard'))
            self.assertIn('modules/field-return-height.dll',m['files']);self.assertIn('modules/gui-parent-guard.dll',m['files'])
            self.assertEqual(m['recipes']['baseline']['module'],'display')
            self.assertFalse((out/'Play-gui-parent-guard.cmd').exists())

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
