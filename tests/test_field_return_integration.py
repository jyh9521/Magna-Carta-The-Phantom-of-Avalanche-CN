"""Default-route integration, owned runtime and verifier only; no game execution."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import integrate_field_return as tool
import test_field_return_trial as trial_tests
START=trial_tests.START
import test_configuration_verify_transaction as route_tests
import build_player_test_bundle as bundle

class IntegrationTransactionTests(unittest.TestCase):
    def setUp(self):
        self.fixture=trial_tests.FieldReturnTrialTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.f=self.fixture
        self.guard=patch.object(tool,'BASE_START_SHA',tool.digest(START));self.guard.start();self.addCleanup(self.guard.stop)
    def install(self):return tool.integrate(self.f.runtime,self.f.module,self.f.record)
    def test_apply_and_rollback_exact_all_files(self):
        j=self.install();self.assertEqual(len(j['changes']),3)
        m=json.loads((self.f.runtime/'runtime.json').read_bytes())
        self.assertEqual(m['field_return_height'],dict(schema=1,enabled=True,module='field-return-height'))
        self.assertFalse((self.f.runtime/'Play-stairwell-fix.cmd').exists())
        for n,b in self.f.before.items():
            if n not in ('Start.ps1','runtime.json'):self.assertEqual((self.f.runtime/n).read_bytes(),b)
        tool.rollback(self.f.record);self.assertEqual(self.f.snapshot(),self.f.before)
    def test_unknown_baseline_rejected(self):
        with patch.object(tool,'BASE_START_SHA','0'*64):
            with self.assertRaises(ValueError):self.install()
        self.assertFalse(self.f.record.exists());self.assertEqual(self.f.snapshot(),self.f.before)
    def test_reentry_rejected(self):
        self.install();after=self.f.snapshot()
        with self.assertRaises(ValueError):tool.integrate(self.f.runtime,self.f.module,self.f.root/'second')
        self.assertEqual(self.f.snapshot(),after)
    def test_backup_drift_prevents_any_rollback(self):
        self.install();after=self.f.snapshot();(self.f.record/'original/Start.ps1').write_bytes(b'drift')
        with self.assertRaises(ValueError):tool.rollback(self.f.record)
        self.assertEqual(self.f.snapshot(),after)
    def test_installed_drift_prevents_any_rollback(self):
        self.install();(self.f.runtime/'Start.ps1').write_bytes(b'foreign');after=self.f.snapshot()
        with self.assertRaises(ValueError):tool.rollback(self.f.record)
        self.assertEqual(self.f.snapshot(),after)
    def test_partial_write_compensates(self):
        real=tool.write_file
        def write(p,b):
            if p==self.f.runtime/'Start.ps1':raise OSError('owned failure')
            real(p,b)
        with patch.object(tool,'write_file',side_effect=write):
            with self.assertRaises(OSError):self.install()
        self.assertEqual(self.f.snapshot(),self.f.before)
    def test_package_requires_default_route_and_rejects_old_entry(self):
        with self.assertRaises(ValueError):bundle.validate_engine_fixes(self.f.runtime,self.f.manifest)
        self.install();m=json.loads((self.f.runtime/'runtime.json').read_bytes())
        with self.assertRaisesRegex(ValueError,'GUI parent-guard'):bundle.validate_engine_fixes(self.f.runtime,m)
        m['gui_parent_guard']=dict(schema=1,enabled=True,module='gui-parent-guard')
        m['files']['modules/gui-parent-guard.dll']='owned'
        self.assertTrue(bundle.validate_engine_fixes(self.f.runtime,m)['field_return_height']['default_enabled'])
        (self.f.runtime/'Play-stairwell-fix.cmd').write_bytes(b'old')
        with self.assertRaises(ValueError):bundle.validate_engine_fixes(self.f.runtime,m)

class DefaultRouteTests(unittest.TestCase):
    setUpClass=classmethod(route_tests.SharedVerifyIntegrationTests.setUpClass.__func__)
    tearDownClass=classmethod(route_tests.SharedVerifyIntegrationTests.tearDownClass.__func__)
    fixture=route_tests.SharedVerifyIntegrationTests.fixture
    def test_normal_baseline_maintenance_routes_and_parent_environment(self):
        for recipe,without,expected,fail in [('configured',False,True,False),('baseline',False,False,False),('configured',True,False,False),('configured',False,True,True)]:
            with self.subTest(recipe=recipe,without=without,fail=fail), tempfile.TemporaryDirectory(dir=ROOT/'build') as d:
                r=Path(d);self.fixture(r);m=json.loads((r/'runtime.json').read_bytes())
                m['recipes']['baseline']=dict(module='display',settings=dict(schema=1,display_profile='baseline',motion60=False,native_gamepad=False))
                m['field_return_height']=dict(schema=1,enabled=True,module='field-return-height')
                (r/'runtime.json').write_text(json.dumps(m));capture=r/'capture.txt'
                env=os.environ.copy();env['OWNED_CAPTURE_FILE']=str(capture);env['OWNED_VERIFY_EXIT']='7' if fail else '0'
                cmd="$env:MC_FIELD_RETURN_HEIGHT='parent';try{& '"+str(r/'Start.ps1')+"' -VerifyOnly -Recipe "+recipe+(' -WithoutFieldReturnHeight' if without else '')+";if("+('$true' if fail else '$false')+"){throw 'expected failure'}}catch{if("+('$false' if fail else '$true')+"){throw};if($_ -notmatch 'Shared launcher exit=7'){throw}};if($env:MC_FIELD_RETURN_HEIGHT -ne 'parent'){throw 'parent env changed'};exit 0"
                result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-Command',cmd],env=env,capture_output=True,text=True,timeout=30)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                actual=capture.read_text();self.assertIn('MC_FIELD_RETURN_HEIGHT='+str(int(expected)),actual)
                self.assertIn(('field-return-height' if expected else 'display')+'.dll',actual)
                self.assertEqual((r/'data/DDrawCompat-MagnaCarta.ini').read_bytes(),b'owned baseline\r\n')
    def test_string_enable_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as d:
            r=Path(d);self.fixture(r);m=json.loads((r/'runtime.json').read_bytes());m['field_return_height']=dict(schema=1,enabled='true',module='field-return-height');(r/'runtime.json').write_text(json.dumps(m))
            result=subprocess.run(['powershell.exe','-NoProfile','-File',str(r/'Start.ps1'),'-VerifyOnly'],capture_output=True,text=True,timeout=30)
            self.assertNotEqual(result.returncode,0);self.assertIn('Invalid field return-height integration',result.stderr)

if __name__=='__main__':unittest.main()
