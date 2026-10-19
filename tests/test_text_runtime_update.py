import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('text_update', ROOT/'tools/build_text_runtime_update.py')
update = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update)


@unittest.skipUnless(shutil.which('powershell.exe'), 'Windows PowerShell required')
class TextRuntimeUpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.runtime = self.root/'runtime'
        self.record = self.root/'record'
        self.package = self.root/'package'
        self.old = {'runtime.json': b'{"fixture":1}', 'modules/text.dll': b'owned old',
                    'data/Fpb/0000.fpb': b'A'*50+b'old sentence.'+b'B'*50}
        self.new = {'runtime.json': b'{"fixture":2}', 'modules/text.dll': b'owned new',
                    'data/Fpb/0000.fpb': b'A'*50+b'new sentence'+b'B'*50,
                    'modules/new.dll': b'new owned module'}
        states = {}
        for name, raw in self.new.items():
            p=self.runtime/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
            if name in self.old:
                p=self.record/'original'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(self.old[name])
            states[name] = dict(before=update.sha(self.old[name]) if name in self.old else None,after=update.sha(raw))
        (self.record/'changes.json').write_text(json.dumps(states))
        archive=update.build(self.runtime,self.record,self.root/'update.zip')
        with zipfile.ZipFile(archive) as z:
            self.assertFalse(any(n.lower().endswith(('.fpb','.dll')) for n in z.namelist()))
            self.assertEqual(z.read('licenses/NotoSansSC-OFL.txt'), (ROOT/'assets/licenses/NotoSansSC-OFL.txt').read_bytes())
            z.extractall(self.package)
        for name in self.new:
            (self.runtime/name).unlink()
        for name, raw in self.old.items():
            (self.runtime/name).write_bytes(raw)
        (self.runtime/'config').mkdir()
        (self.runtime/'config/enhancements.json').write_bytes(b'user settings')
        (self.runtime/'data/save.sav').write_bytes(b'user progress')

    def action(self, action):
        return subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
            str(self.package/'Update.ps1'),'-Action',action,'-Runtime',str(self.runtime)],capture_output=True,text=True)

    def success(self, action):
        p=self.action(action)
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        return p.stdout.strip()

    def test_baseline_install_check_rollback(self):
        self.assertEqual(self.success('Verify'),'BASELINE PASS files=4 writes=0')
        self.assertFalse((self.runtime/'.text-runtime-update').exists())
        self.assertIn('MODIFIED PASS files=4',self.success('Install'))
        for n,b in self.new.items():self.assertEqual((self.runtime/n).read_bytes(),b)
        self.assertIn('MODIFIED PASS files=4',self.success('CheckInstalled'))
        (self.runtime/'config/enhancements.json').write_bytes(b'changed user settings')
        (self.runtime/'data/save.sav').write_bytes(b'new user progress')
        self.assertIn('ROLLBACK PASS files=4',self.success('Rollback'))
        for n,b in self.old.items():self.assertEqual((self.runtime/n).read_bytes(),b)
        self.assertFalse((self.runtime/'modules/new.dll').exists())
        self.assertEqual((self.runtime/'config/enhancements.json').read_bytes(),b'changed user settings')
        self.assertEqual((self.runtime/'data/save.sav').read_bytes(),b'new user progress')

    def test_corrupt_payload_no_writes(self):
        manifest=json.loads((self.package/'package.json').read_text())
        (self.package/manifest['files'][-1]['payload']).write_bytes(b'corrupt')
        self.assertNotEqual(self.action('Install').returncode,0)
        self.assertFalse((self.runtime/'.text-runtime-update').exists())
        for n,b in self.old.items():self.assertEqual((self.runtime/n).read_bytes(),b)

    def test_reinstall_after_exact_rollback(self):
        self.success('Install')
        self.success('Rollback')
        self.success('Install')
        self.success('CheckInstalled')
        self.success('Rollback')
        for n,b in self.old.items():self.assertEqual((self.runtime/n).read_bytes(),b)

    def test_reinstall_with_corrupt_backup_no_writes(self):
        self.success('Install')
        self.success('Rollback')
        (self.runtime/'.text-runtime-update/original/runtime.json').write_bytes(b'corrupt')
        self.assertNotEqual(self.action('Install').returncode,0)
        for n,b in self.old.items():self.assertEqual((self.runtime/n).read_bytes(),b)

    def test_baseline_drift_no_writes(self):
        (self.runtime/'runtime.json').write_bytes(b'drift')
        self.assertNotEqual(self.action('Install').returncode,0)
        self.assertEqual((self.runtime/'modules/text.dll').read_bytes(),self.old['modules/text.dll'])

    def test_rollback_drift_preflight(self):
        self.success('Install')
        (self.runtime/'runtime.json').write_bytes(b'drift')
        self.assertNotEqual(self.action('Rollback').returncode,0)
        self.assertEqual((self.runtime/'modules/text.dll').read_bytes(),self.new['modules/text.dll'])

    def test_corrupt_backup_preflight(self):
        self.success('Install')
        (self.runtime/'.text-runtime-update/original/runtime.json').write_bytes(b'corrupt')
        self.assertNotEqual(self.action('Rollback').returncode,0)
        self.assertEqual((self.runtime/'modules/text.dll').read_bytes(),self.new['modules/text.dll'])

    def test_invalid_path_rejected(self):
        manifest=json.loads((self.package/'package.json').read_text())
        manifest['files'][-1]['path']='../escape.dll'
        (self.package/'package.json').write_text(json.dumps(manifest))
        self.assertNotEqual(self.action('Install').returncode,0)
        self.assertFalse((self.runtime/'.text-runtime-update').exists())

    def test_malformed_delta_hash_consistent_rejected(self):
        manifest=json.loads((self.package/'package.json').read_text())
        row=next(r for r in manifest['files'] if r['delta'])
        raw=b'MCD1'+b'\0'*8
        (self.package/row['payload']).write_bytes(raw);row['payload_sha256']=update.sha(raw)
        (self.package/'package.json').write_text(json.dumps(manifest))
        self.assertNotEqual(self.action('Install').returncode,0)
        for n,b in self.old.items():self.assertEqual((self.runtime/n).read_bytes(),b)


if __name__ == '__main__':
    unittest.main()
