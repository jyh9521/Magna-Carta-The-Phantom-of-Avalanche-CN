"""Owned fixtures and VerifyOnly; no game process or commercial DLL loading."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import integrate_gui_parent as tool
import test_field_return_trial as trials
import test_configuration_verify_transaction as routes
import build_player_test_bundle as bundle
from replay_native_gui_parent import NativeGuiParent, replay, trampoline

ROOT=Path(__file__).resolve().parents[1]

class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.f=trials.FieldReturnTrialTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.f.manifest['field_return_height']=dict(schema=1,enabled=True,module='field-return-height')
        self.f.update_manifest();self.f.before=self.f.snapshot()
        g=patch.object(tool,'BASE_START_SHA',tool.digest(trials.START));g.start();self.addCleanup(g.stop)
    def install(self):return tool.integrate(self.f.runtime,self.f.module,self.f.record)
    def test_apply_rollback_byte_exact(self):
        self.install();m=json.loads((self.f.runtime/'runtime.json').read_bytes())
        self.assertEqual(m['gui_parent_guard'],dict(schema=1,enabled=True,module='gui-parent-guard'))
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
    def test_package_metadata_separate_from_scene(self):
        self.install();m=json.loads((self.f.runtime/'runtime.json').read_bytes())
        m['files']['modules/field-return-height.dll']='owned'
        r=bundle.validate_engine_fixes(self.f.runtime,m)
        self.assertFalse(r['scene_transition_crash_fixed']);self.assertFalse(r['gui_parent_guard']['in_game_verified'])
        del m['gui_parent_guard']
        with self.assertRaises(ValueError):bundle.validate_engine_fixes(self.f.runtime,m)

class RouteTests(unittest.TestCase):
    setUpClass=classmethod(routes.SharedVerifyIntegrationTests.setUpClass.__func__)
    tearDownClass=classmethod(routes.SharedVerifyIntegrationTests.tearDownClass.__func__)
    fixture=routes.SharedVerifyIntegrationTests.fixture
    def test_default_baseline_independent_rollbacks_and_environment(self):
        cases=[('configured',[],True,True,'gui-parent-guard'),
               ('baseline',[],False,False,'display'),
               ('configured',['-WithoutGuiParentGuard'],False,True,'field-return-height'),
               ('configured',['-WithoutFieldReturnHeight'],True,False,'gui-parent-guard'),
               ('configured',['-WithoutGuiParentGuard','-WithoutFieldReturnHeight'],False,False,'display')]
        for recipe,flags,gui,stair,module in cases:
            for fail in (False,True):
                with self.subTest(recipe=recipe,flags=flags,fail=fail),tempfile.TemporaryDirectory(dir=ROOT/'build') as d:
                    r=Path(d);self.fixture(r);m=json.loads((r/'runtime.json').read_bytes())
                    m['recipes']['baseline']=dict(module='display',settings=dict(schema=1,display_profile='baseline',motion60=False,native_gamepad=False))
                    m['field_return_height']=dict(schema=1,enabled=True,module='field-return-height')
                    m['gui_parent_guard']=dict(schema=1,enabled=True,module='gui-parent-guard')
                    (r/'runtime.json').write_text(json.dumps(m));capture=r/'capture.txt'
                    env=os.environ.copy();env['OWNED_CAPTURE_FILE']=str(capture);env['OWNED_VERIFY_EXIT']='7' if fail else '0'
                    cmd="$env:MC_GUI_PARENT_GUARD='parent';$env:MC_FIELD_RETURN_HEIGHT='parent';try{& '"+str(r/'Start.ps1')+"' -VerifyOnly -Recipe "+recipe+' '+' '.join(flags)+";if("+('$true' if fail else '$false')+"){throw 'expected failure'}}catch{if("+('$false' if fail else '$true')+"){throw};if($_ -notmatch 'Shared launcher exit=7'){throw}};if($env:MC_GUI_PARENT_GUARD -ne 'parent' -or $env:MC_FIELD_RETURN_HEIGHT -ne 'parent'){throw 'env drift'};exit 0"
                    p=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-Command',cmd],env=env,capture_output=True,text=True,timeout=30)
                    self.assertEqual(p.returncode,0,p.stdout+p.stderr)
                    s=capture.read_text();self.assertIn('MC_GUI_PARENT_GUARD='+str(int(gui)),s);self.assertIn('MC_FIELD_RETURN_HEIGHT='+str(int(stair)),s);self.assertIn(module+'.dll',s)
                    self.assertEqual((r/'data/DDrawCompat-MagnaCarta.ini').read_bytes(),b'owned baseline\r\n')
    def test_string_boolean_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as d:
            r=Path(d);self.fixture(r);m=json.loads((r/'runtime.json').read_bytes());m['gui_parent_guard']=dict(schema=1,enabled='true',module='gui-parent-guard');(r/'runtime.json').write_text(json.dumps(m))
            p=subprocess.run(['powershell.exe','-NoProfile','-File',str(r/'Start.ps1'),'-VerifyOnly'],capture_output=True,text=True,timeout=30)
            self.assertNotEqual(p.returncode,0);self.assertIn('Invalid GUI parent-guard integration',p.stderr)

class CompiledGuardTests(unittest.TestCase):
    def test_current_engine_matches_production_identity_sites(self):
        if not (ROOT/'runtime/data/MCAlpha.dll').is_file():
            self.skipTest('Local supported engine not supplied')
        import pefile
        import struct
        pe=pefile.PE(str(ROOT/'runtime/data/MCAlpha.dll'))
        self.assertEqual(pe.FILE_HEADER.TimeDateStamp,0x3ed73966)
        self.assertEqual(pe.OPTIONAL_HEADER.SizeOfImage,0x10b000)
        self.assertEqual(pe.get_data(0xba4c,2),b'\x6a\x54')
        self.assertEqual(pe.get_data(0xbd604,4),struct.pack('<I',pe.OPTIONAL_HEADER.ImageBase+0x9440))
        self.assertEqual(pe.get_data(0x1e940,17),bytes.fromhex('558bec51894dfc8b45fc8b4d08d900d801'))
    def test_compiled_encoder_and_actual_instructions(self):
        exe=ROOT/'build/native/Release/gui_parent_guard_fixture.exe'
        if not exe.exists():self.skipTest('Build owned gui_parent_guard_fixture first')
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)/'bridge.bin';p=subprocess.run([str(exe),str(dest)],capture_output=True,text=True,timeout=20)
            self.assertEqual(p.returncode,0,p.stdout+p.stderr);b=dest.read_bytes();self.assertEqual(b,trampoline())
            r=replay((ROOT/'runtime/data/MCAlpha.dll').read_bytes(),b)
            self.assertTrue(r['modified']['completed']);self.assertEqual(r['baseline']['fault'],r['rollback']['fault'])

if __name__=='__main__':unittest.main()
