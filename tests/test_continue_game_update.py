import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import build_continue_game_update as repair
from test_runtime_module_update import dll


class ContinueGameUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.old = {name: dll(b'old owned') for name in repair.MODULES}
        self.old['runtime.json'] = json.dumps(dict(schema=1, files={n:repair.sha(b) for n,b in self.old.items()}, custom='preserved')).encode()
        rows, payload = [], {}
        for n,b in self.old.items():
            key = f'payload/{len(rows)}.bin'
            payload[key] = b
            rows.append(dict(path=n, after=repair.sha(b), payload=key, payload_sha256=repair.sha(b), delta=False, size=len(b)))
        payload['package.json'] = json.dumps(dict(schema=1, kind='text_runtime_update', files=rows)).encode()
        self.previous = self.base/'old.zip'
        with zipfile.ZipFile(self.previous,'x') as z:
            for n,b in payload.items(): z.writestr(n,b)
        self.native = self.base/'new.dll'
        self.native.write_bytes(dll(b'fixed owned'))

    def build(self):
        return repair.assemble(self.previous,self.native,self.base/'fix.zip',self.base/'work',repair.sha(self.previous.read_bytes()),repair.sha(self.native.read_bytes()))

    def test_input_hash_mismatch_does_not_publish(self):
        with self.assertRaisesRegex(ValueError,'Source hash'):
            repair.assemble(self.previous,self.native,self.base/'fix.zip',self.base/'work','0'*64,repair.sha(self.native.read_bytes()))
        self.assertFalse((self.base/'fix.zip').exists())
        self.assertFalse((self.base/'work').exists())

    def test_package_is_owned_only_and_uses_distinct_journal(self):
        with zipfile.ZipFile(self.build()) as z:
            self.assertIsNone(z.testzip())
            m=json.loads(z.read(repair.FOLDER+'/package.json'))
            self.assertEqual(len(m['files']),13)
            self.assertTrue(all(not r['path'].startswith('data/') for r in m['files']))
            script=z.read(repair.FOLDER+'/Update.ps1')
            self.assertIn(repair.BACKUP.encode(),script)
            self.assertNotIn(b"Located $Runtime '.text-runtime-update'",script)
            row=next(r for r in m['files'] if r['path']=='runtime.json')
            manifest=json.loads(z.read(repair.FOLDER+'/'+row['payload']))
            self.assertEqual(manifest['custom'],'preserved')
            self.assertTrue(all(manifest['files'][n]==repair.sha(self.native.read_bytes()) for n in repair.MODULES))

    @unittest.skipUnless(os.name=='nt' and shutil.which('powershell.exe'),'Windows updater required')
    def test_real_wrapper_with_prior_installed_backup_and_exact_rollback(self):
        target=self.base/'runtime with spaces'
        target.mkdir()
        for n,b in self.old.items():
            p=target/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
        protected={'.text-runtime-update/state.json':b'earlier installed marker',
                   '.text-runtime-update/original/runtime.json':b'earlier exact backup',
                   'config/enhancements.json':b'user settings','data/MC00.sav':b'user save'}
        for n,b in protected.items():
            p=target/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
        with zipfile.ZipFile(self.build()) as z:z.extractall(target)
        cmd=target/'Repair-ContinueGame.cmd'
        for _ in range(2):
            r=subprocess.run(['cmd.exe','/d','/c',str(cmd)],input='\n',capture_output=True,text=True,errors='replace',timeout=60)
            self.assertEqual(r.returncode,0,r.stdout+r.stderr)
            self.assertIn('REPAIR PASS',r.stdout)
        for n in repair.MODULES:self.assertEqual((target/n).read_bytes(),self.native.read_bytes())
        r=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(target/repair.FOLDER/'Update.ps1'),'-Action','Rollback','-Runtime',str(target)],capture_output=True,text=True,errors='replace',timeout=60)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        for n,b in {**self.old,**protected}.items():self.assertEqual((target/n).read_bytes(),b)
