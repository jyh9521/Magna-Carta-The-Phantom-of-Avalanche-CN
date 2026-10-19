"""Owned fixtures and VerifyOnly; no game process or commercial DLL loading."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import integrate_scene_loading as tool
import test_field_return_trial as trials
import test_configuration_verify_transaction as routes

ROOT=Path(__file__).resolve().parents[1]

class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.f=trials.FieldReturnTrialTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.f.manifest['field_return_height']=dict(schema=1,enabled=True,module='field-return-height')
        self.f.manifest['gui_parent_guard']=dict(schema=1,enabled=True,module='gui-parent-guard')
        self.f.update_manifest();self.f.before=self.f.snapshot()
        g=patch.object(tool,'BASE_START_SHA',tool.digest(trials.START));g.start();self.addCleanup(g.stop)
    def install(self):return tool.integrate(self.f.runtime,self.f.module,self.f.record)
    def test_apply_rollback_byte_exact(self):
        self.install();m=json.loads((self.f.runtime/'runtime.json').read_bytes())
        self.assertEqual(m['scene_loading'],dict(schema=1,enabled=True,module='scene-loading'))
        self.assertEqual(m['field_return_height'],self.f.manifest['field_return_height'])
        for n,b in self.f.before.items():
            if n not in ('Start.ps1','runtime.json'):self.assertEqual((self.f.runtime/n).read_bytes(),b)
        tool.rollback(self.f.record);self.assertEqual(self.f.snapshot(),self.f.before)
    def test_unknown_baseline(self):
        with patch.object(tool,'BASE_START_SHA','0'*64),self.assertRaises(ValueError):self.install()
        self.assertEqual(self.f.snapshot(),self.f.before)
    def test_missing_stair_baseline(self):
        del self.f.manifest['field_return_height'];self.f.update_manifest()
        with self.assertRaises(ValueError):self.install()
    def test_reentry_rejected(self):
        self.install();before=self.f.snapshot()
        with self.assertRaises(ValueError):tool.integrate(self.f.runtime,self.f.module,self.f.root/'second')
        self.assertEqual(self.f.snapshot(),before)
    def test_backup_drift_rejected(self):
        self.install();(self.f.record/'original/Start.ps1').write_bytes(b'drift');before=self.f.snapshot()
        with self.assertRaises(ValueError):tool.rollback(self.f.record)
        self.assertEqual(self.f.snapshot(),before)
    def test_installed_drift_rejected(self):
        self.install();(self.f.runtime/'Start.ps1').write_bytes(b'foreign');before=self.f.snapshot()
        with self.assertRaises(ValueError):tool.rollback(self.f.record)
        self.assertEqual(self.f.snapshot(),before)
    def test_partial_write_compensates(self):
        real=tool.write_file
        def write(p,b):
            if p==self.f.runtime/'Start.ps1':raise OSError('owned failure')
            real(p,b)
        with patch.object(tool,'write_file',side_effect=write),self.assertRaises(OSError):self.install()
        self.assertEqual(self.f.snapshot(),self.f.before)

    def test_package_metadata_distinguishes_presentation_from_crash_fix(self):
        import build_player_test_bundle as bundle
        self.install();m=json.loads((self.f.runtime/'runtime.json').read_bytes())
        for name in ['field-return-height','gui-parent-guard']:m['files']['modules/'+name+'.dll']='owned'
        result=bundle.validate_engine_fixes(self.f.runtime,m)
        self.assertTrue(result['scene_loading']['default_enabled'])
        self.assertFalse(result['scene_loading']['in_game_verified'])
        self.assertFalse(result['scene_transition_crash_fixed'])
        m['scene_loading']['enabled']='true'
        with self.assertRaises(ValueError):bundle.validate_engine_fixes(self.f.runtime,m)

class NativeTests(unittest.TestCase):
    def test_native_baseline_modified_rollback(self):
        fixture=ROOT/'build/native/Release/scene_loading_fixture.exe'
        if not fixture.exists():self.skipTest('Build scene_loading_fixture first')
        for mode,code,text in [('baseline',1,'retained_old_frame=true'),('modified',0,'order=draw_release_present_cleanup'),('rollback',1,'restored_old_frame=true')]:
            p=subprocess.run([str(fixture),mode],capture_output=True,text=True,timeout=15)
            self.assertEqual(p.returncode,code,p.stdout+p.stderr)
            self.assertIn(text,p.stdout)
            self.assertIn('game_started=false',p.stdout)

    def test_exact_local_source_sites(self):
        import pefile
        from replay_native_gui_parent import SOURCE_SHA
        import hashlib
        path=ROOT/'runtime/data/MCAlpha.dll'
        if not path.exists():self.skipTest('Local source sample required')
        data=path.read_bytes();self.assertEqual(hashlib.sha256(data).hexdigest(),SOURCE_SHA)
        p=pefile.PE(data=data)
        self.assertEqual(p.get_data(0x63075,5),bytes.fromhex('e8e1000000'))
        self.assertEqual(p.get_data(0x631a0,8),bytes.fromhex('558bec83ec08894d'))

class RouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):routes.SharedVerifyIntegrationTests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls):routes.SharedVerifyIntegrationTests.tearDownClass.__func__(cls)
    fixture=routes.SharedVerifyIntegrationTests.fixture

    def test_independent_switch_and_parent_environment(self):
        for recipe,flags,enabled,module in [('configured',[],1,'scene-loading'),('configured',['-WithoutSceneLoading'],0,'gui-parent-guard'),('baseline',[],0,'display')]:
            for fail in (False,True):
                with self.subTest(recipe=recipe,flags=flags,fail=fail),tempfile.TemporaryDirectory(dir=ROOT/'build') as d:
                    r=Path(d);self.fixture(r);m=json.loads((r/'runtime.json').read_bytes())
                    m['recipes']['baseline']=dict(module='display',settings=dict(schema=1,display_profile='baseline',motion60=False,native_gamepad=False))
                    for key,name in [('field_return_height','field-return-height'),('gui_parent_guard','gui-parent-guard'),('scene_loading','scene-loading')]:m[key]=dict(schema=1,enabled=True,module=name)
                    (r/'runtime.json').write_text(json.dumps(m));capture=r/'capture.txt'
                    env=os.environ.copy();env['OWNED_CAPTURE_FILE']=str(capture);env['OWNED_VERIFY_EXIT']='7' if fail else '0'
                    cmd="$env:MC_SCENE_LOADING='parent';try{& '"+str(r/'Start.ps1')+"' -VerifyOnly -Recipe "+recipe+' '+' '.join(flags)+";if("+('$true' if fail else '$false')+"){throw 'expected failure'}}catch{if("+('$false' if fail else '$true')+"){throw};if($_ -notmatch 'Shared launcher exit=7'){throw}};if($env:MC_SCENE_LOADING -ne 'parent'){throw 'env drift'};exit 0"
                    p=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-Command',cmd],env=env,capture_output=True,text=True,timeout=30)
                    self.assertEqual(p.returncode,0,p.stdout+p.stderr)
                    text=capture.read_text();self.assertIn('MC_SCENE_LOADING='+str(enabled),text);self.assertIn(module+'.dll',text)
                    self.assertEqual((r/'data/DDrawCompat-MagnaCarta.ini').read_bytes(),b'owned baseline\r\n')
                    if recipe!='baseline':self.assertIn('MC_GUI_PARENT_GUARD=1',text);self.assertIn('MC_FIELD_RETURN_HEIGHT=1',text)

    def test_string_boolean_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as d:
            r=Path(d);self.fixture(r);m=json.loads((r/'runtime.json').read_bytes());m['scene_loading']=dict(schema=1,enabled='true',module='scene-loading');(r/'runtime.json').write_text(json.dumps(m))
            p=subprocess.run(['powershell.exe','-NoProfile','-File',str(r/'Start.ps1'),'-VerifyOnly'],capture_output=True,text=True,timeout=30)
            self.assertNotEqual(p.returncode,0);self.assertIn('Invalid scene-loading integration',p.stderr)
