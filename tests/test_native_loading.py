"""Owned fixtures and VerifyOnly; no game process or commercial DLL loading."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import integrate_native_loading as tool
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
        self.assertEqual(m['native_scene_loading'],dict(schema=1,enabled=True,module='native-loading'))
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
        self.assertTrue(result['native_scene_loading']['default_enabled'])
        self.assertFalse(result['native_scene_loading']['in_game_verified'])
        self.assertFalse(result['scene_transition_crash_fixed'])
        m['native_scene_loading']['enabled']='true'
        with self.assertRaises(ValueError):bundle.validate_engine_fixes(self.f.runtime,m)

class NativeTests(unittest.TestCase):
    def test_prepare_rejects_conflicting_or_missing_guards_before_output(self):
        from prepare_shared_runtime import prepare
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as d:
            root=Path(d);out=root/'output'
            for modules in [dict.fromkeys(['native-loading','scene-loading']),{'native-loading':None}]:
                with self.assertRaises(ValueError):prepare(root/'missing',modules,root/'atlas',out)
                self.assertFalse(out.exists())

    def test_native_baseline_modified_rollback(self):
        fixture=ROOT/'build/native/Release/native_scene_loading_fixture.exe'
        if not fixture.exists():self.skipTest('Build scene_loading_fixture first')
        for mode,code,text in [('baseline',1,'flag=0 draws=1 cleanup=1'),('modified',0,'flag_before_native_draw=1 normal_draws=1 standalone_presents=0'),('rollback',1,'original_gate=restored')]:
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
        self.assertEqual(p.get_data(0x631da,5),bytes.fromhex('e843010000'))
        self.assertEqual(p.get_data(0x631a0,8),bytes.fromhex('558bec83ec08894d'))

class RouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):routes.SharedVerifyIntegrationTests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls):routes.SharedVerifyIntegrationTests.tearDownClass.__func__(cls)
    fixture=routes.SharedVerifyIntegrationTests.fixture

    def test_independent_switch_and_parent_environment(self):
        for recipe,flags,enabled,module in [('configured',[],1,'native-loading'),('configured',['-WithoutNativeLoading'],0,'gui-parent-guard'),('baseline',[],0,'display')]:
            for fail in (False,True):
                with self.subTest(recipe=recipe,flags=flags,fail=fail),tempfile.TemporaryDirectory(dir=ROOT/'build') as d:
                    r=Path(d);self.fixture(r);m=json.loads((r/'runtime.json').read_bytes())
                    m['recipes']['baseline']=dict(module='display',settings=dict(schema=1,display_profile='baseline',motion60=False,native_gamepad=False))
                    for key,name in [('field_return_height','field-return-height'),('gui_parent_guard','gui-parent-guard'),('native_scene_loading','native-loading')]:m[key]=dict(schema=1,enabled=True,module=name)
                    (r/'runtime.json').write_text(json.dumps(m));capture=r/'capture.txt'
                    env=os.environ.copy();env['OWNED_CAPTURE_FILE']=str(capture);env['OWNED_VERIFY_EXIT']='7' if fail else '0'
                    cmd="$env:MC_NATIVE_SCENE_LOADING='parent';try{& '"+str(r/'Start.ps1')+"' -VerifyOnly -Recipe "+recipe+' '+' '.join(flags)+";if("+('$true' if fail else '$false')+"){throw 'expected failure'}}catch{if("+('$false' if fail else '$true')+"){throw};if($_ -notmatch 'Shared launcher exit=7'){throw}};if($env:MC_NATIVE_SCENE_LOADING -ne 'parent'){throw 'env drift'};exit 0"
                    p=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-Command',cmd],env=env,capture_output=True,text=True,timeout=30)
                    self.assertEqual(p.returncode,0,p.stdout+p.stderr)
                    text=capture.read_text();self.assertIn('MC_NATIVE_SCENE_LOADING='+str(enabled),text);self.assertIn(module+'.dll',text)
                    self.assertEqual((r/'data/DDrawCompat-MagnaCarta.ini').read_bytes(),b'owned baseline\r\n')
                    if recipe!='baseline':self.assertIn('MC_GUI_PARENT_GUARD=1',text);self.assertIn('MC_FIELD_RETURN_HEIGHT=1',text)

    def test_string_boolean_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'build') as d:
            r=Path(d);self.fixture(r);m=json.loads((r/'runtime.json').read_bytes());m['native_scene_loading']=dict(schema=1,enabled='true',module='native-loading');(r/'runtime.json').write_text(json.dumps(m))
            p=subprocess.run(['powershell.exe','-NoProfile','-File',str(r/'Start.ps1'),'-VerifyOnly'],capture_output=True,text=True,timeout=30)
            self.assertNotEqual(p.returncode,0);self.assertIn('Invalid native scene-loading integration',p.stderr)

class OriginalGateTests(unittest.TestCase):
    def test_original_frame_keeps_one_present_and_one_update(self):
        from replay_native_loading_frame import verify
        path=ROOT/'runtime/data/MCAlpha.dll'
        if not path.exists():self.skipTest('Local source required')
        r=verify(path.read_bytes())
        for name in ['baseline','modified','rollback']:
            x=r[name]
            self.assertEqual(x['normal_presents'],1)
            self.assertEqual(x['fixed_clock_calls'],1)
            self.assertEqual(x['standalone_presents'],0)
            self.assertEqual(x['loading_before_normal_present'],name=='modified')
            self.assertTrue(x['original_loop_executed'])
            self.assertFalse(x['rendered_pixels_verified'])

    def test_actual_gate_and_exit_instructions(self):
        from replay_native_loading_gate import verify
        path=ROOT/'runtime/data/MCAlpha.dll'
        if not path.exists():self.skipTest('Local source required')
        r=verify(path.read_bytes());self.assertEqual(len(r['cases']),7)
        self.assertNotIn('original_loading_71085_boundary',r['cases']['ordinary_exit_flag0']['events'])
        self.assertIn('original_loading_71085_boundary',r['cases']['native_loading_flag1']['events'])
        self.assertFalse(r['native_loading_body_executed']);self.assertFalse(r['actual_scene_delay_reproduced'])

    def test_actual_artwork_resources(self):
        import struct
        import json
        from resource_image import parse
        data=ROOT/'runtime/data'
        if not (data/'FrameData/0204.fdi').exists():self.skipTest('Local assets required')
        b=(data/'FrameData/0204.fdi').read_bytes();self.assertEqual(len(b),787)
        rows=[struct.unpack_from('<iiiii',b,157+i*42+2) for i in range(15) if b[157+i*42]]
        self.assertEqual(rows,[(1,0,0,3,354),(1,128,0,3,355),(1,256,0,3,356)])
        for row in rows:
            p=data/'BGR'/f'{row[4]:04d}.BGR';im=parse(p.read_bytes());self.assertEqual((im.width,im.height),(128,128))
        plans=json.loads((ROOT/'locales/zh-CN/image-group-plans.json').read_text('utf8'))
        loading=next(g for g in plans['groups'] if g['id']=='loading-progress')
        self.assertEqual(loading['plans'][0]['target'],'卡尔塔系统载入中……')
