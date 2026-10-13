import copy, hashlib, json, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import patch_binary_plan as m
import install_disc_gate as install

class BinaryPlanTests(unittest.TestCase):
    def setUp(self):
        self.raw = b'0123456789'
        self.target = b'012AB56789'
        self.plan = dict(schema=1,source_size=10,source_sha256=m.digest(self.raw),target_sha256=m.digest(self.target),
                         changes=[dict(offset=3,expected_hex=b'34'.hex(),replacement_hex=b'AB'.hex())])
    def test_forward_reverse_exact(self):
        self.assertEqual(m.transform(self.raw,self.plan),self.target)
        self.assertEqual(m.transform(self.target,self.plan,True),self.raw)
    def test_unknown_versions_and_bad_ranges_fail(self):
        with self.assertRaises(ValueError):m.transform(b'X'+self.raw[1:],self.plan)
        for offset in [True,-1,9]:
            p=copy.deepcopy(self.plan);p['changes'][0]['offset']=offset
            with self.assertRaises(ValueError):m.transform(self.raw,p)
        p=copy.deepcopy(self.plan);p['changes']*=2
        with self.assertRaises(ValueError):m.transform(self.raw,p)
    def test_mismatch_and_wrong_target_fail(self):
        for field,value in [('expected_hex','0000'),('replacement_hex','00')]:
            p=copy.deepcopy(self.plan);p['changes'][0][field]=value
            with self.assertRaises(ValueError):m.transform(self.raw,p)
        p=copy.deepcopy(self.plan);p['target_sha256']='0'*64
        with self.assertRaises(ValueError):m.transform(self.raw,p)
    def test_independent_copy_and_rollback(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);s=p/'source';t=p/'target';s.write_bytes(self.raw)
            m.apply(s,t,self.plan);self.assertEqual(s.read_bytes(),self.raw)
            with self.assertRaises(ValueError):m.apply(s,t,self.plan)
            m.rollback(t,self.plan);self.assertEqual(t.read_bytes(),self.raw)
            with self.assertRaises(ValueError):m.rollback(t,self.plan)
    def test_declared_disc_branch_destination(self):
        p=json.loads((Path(__file__).resolve().parents[1]/'patches/disc-gate.json').read_text())
        r=p['changes'][0];b=bytes.fromhex(r['replacement_hex'])
        self.assertEqual(b[0],0xe9)
        self.assertEqual(int(r['branch_va'],16)+5+int.from_bytes(b[1:],'little',signed=True),int(r['destination_va'],16))
        self.assertEqual(int(r['destination_va'],16),0x4010d1)

    def test_new_game_copy_preserves_saves_and_restores_launcher(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'source';package=root/'package';target=root/'candidate'
            source.mkdir();package.mkdir();(source/'MagnaCarta.exe').write_bytes(self.raw)
            (source/'MCAlpha.dll').write_bytes(b'owned module');(source/'MC00.sav').write_bytes(b'owned save')
            (source/'.locale-runtime').mkdir();(source/'.locale-runtime/workspace_launcher.exe').write_bytes(b'old launcher')
            (package/'workspace_launcher.exe').write_bytes(b'new launcher')
            (source/'.locale-runtime/Start.ps1').write_bytes(b'old start')
            (package/'Start.ps1').write_bytes(b'new start')
            (package/'PrepareProfile.ps1').write_bytes(b'profile helper')
            (package/'disc-gate.json').write_text(json.dumps(self.plan))
            bundle=dict(files={n:m.digest((package/n).read_bytes()) for n in ['workspace_launcher.exe','disc-gate.json','Start.ps1','PrepareProfile.ps1']},
                        engine_sha256=[m.digest(b'owned module')])
            (package/'bundle.json').write_text(json.dumps(bundle))
            install.install(source,package,target)
            self.assertEqual((source/'MagnaCarta.exe').read_bytes(),self.raw)
            self.assertEqual((target/'MagnaCarta.exe').read_bytes(),self.target)
            self.assertEqual((target/'MC00.sav').read_bytes(),b'owned save')
            launcher=target/'.locale-runtime/workspace_launcher.exe';launcher.write_bytes(b'drift')
            with self.assertRaises(ValueError):install.restore(target)
            self.assertEqual((target/'MagnaCarta.exe').read_bytes(),self.target)
            launcher.write_bytes(b'new launcher');install.restore(target)
            self.assertEqual((target/'MagnaCarta.exe').read_bytes(),self.raw)
            self.assertEqual(launcher.read_bytes(),b'old launcher')
            self.assertEqual((target/'.locale-runtime/Start.ps1').read_bytes(),b'old start')
            self.assertFalse((target/'.locale-runtime/PrepareProfile.ps1').exists())
            self.assertEqual((target/'MC00.sav').read_bytes(),b'owned save')
