"""Exercise cleanup in isolated, synchronized Git repositories, never the game tree."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(os.environ.get('CLEANUP_TEST_SCRIPT', ROOT/'tools/CleanupGenerated.ps1'))
BASELINE = os.environ.get('CLEANUP_TEST_BASELINE') == '1'

@unittest.skipUnless(shutil.which('powershell.exe') and shutil.which('git'), 'Windows tools required')
class CleanupTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)/'repo'
        self.root.mkdir()
        for name in ['tools','build','out','dist/old-unpacked','runtime/data','runtime/saves-import','runtime/maintenance']:
            (self.root/name).mkdir(parents=True, exist_ok=True)
        shutil.copy2(SCRIPT, self.root/'tools/CleanupGenerated.ps1')
        (self.root/'runtime/runtime.json').write_text(json.dumps(dict(data={},files={})))
        raw=b'preserved-save'
        h=hashlib.sha256(raw).hexdigest()
        (self.root/'runtime/saves-import/index.json').write_text(json.dumps([dict(Hash=h)]))
        (self.root/f'runtime/saves-import/{h}.sav').write_bytes(raw)
        (self.root/'runtime/data/player.sav').write_bytes(raw)
        (self.root/'build/junk.tmp').write_bytes(b'old')
        (self.root/'out/junk.tmp').write_bytes(b'old')
        (self.root/'dist/old-unpacked/junk.tmp').write_bytes(b'old')
        self.old=self.root/'dist/MagnaCarta-unified-test-old.zip'
        self.keep=self.root/'dist/MagnaCarta-unified-test-new.zip'
        self.old.write_bytes(b'old-zip')
        self.keep.write_bytes(b'latest-zip')
        os.utime(self.old,(1000000000,1000000000))
        os.utime(self.keep,(1100000000,1100000000))
        (self.root/'.gitignore').write_text('build/\ndist/\nout/\nruntime/\n')
        self.git('init','-b','main')
        self.git('config','user.email','fixture@example.invalid')
        self.git('config','user.name','Fixture')
        self.git('add','.')
        self.git('commit','-qm','fixture')
        remote=Path(tmp.name)/'remote.git'
        subprocess.run(['git','init','--bare',str(remote)],check=True,capture_output=True)
        self.git('remote','add','origin',str(remote))
        self.git('push','-q','origin','main')

    def git(self,*args):
        return subprocess.run(['git','-C',str(self.root),*args],check=True,capture_output=True)

    def run_cleanup(self,*args):
        return subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
                               str(self.root/'tools/CleanupGenerated.ps1'),*args],capture_output=True,text=True)

    def test_retention_and_saves(self):
        p=self.run_cleanup()
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)
        self.assertFalse((self.root/'build').exists())
        self.assertEqual(self.keep.exists(),not BASELINE)
        if not BASELINE:
            self.assertEqual(list((self.root/'dist').iterdir()),[self.keep])
            self.assertEqual(self.keep.read_bytes(),b'latest-zip')
            self.assertFalse((self.root/'out').exists())
        self.assertEqual((self.root/'runtime/data/player.sav').read_bytes(),b'preserved-save')
        self.assertEqual(len(list((self.root/'runtime/saves-import').glob('*.sav'))),1)

    @unittest.skipIf(BASELINE,'old script has no preview')
    def test_plan_does_not_delete(self):
        p=self.run_cleanup('-PlanOnly')
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn('PLAN PASS',p.stdout)
        self.assertTrue((self.root/'build/junk.tmp').exists())
        self.assertTrue(self.old.exists())

    @unittest.skipIf(BASELINE,'old script does not retain a package')
    def test_missing_package_stops_before_deletion(self):
        self.old.unlink();self.keep.unlink()
        p=self.run_cleanup()
        self.assertNotEqual(p.returncode,0)
        self.assertTrue((self.root/'build/junk.tmp').exists())

    def test_tracked_content_stops_before_deletion(self):
        self.git('add','-f','build/junk.tmp')
        self.git('commit','-qm','tracked fixture')
        self.git('push','-q','origin','main')
        p=self.run_cleanup()
        self.assertNotEqual(p.returncode,0)
        self.assertTrue((self.root/'build/junk.tmp').exists())
        self.assertTrue(self.keep.exists())

if __name__=='__main__':
    unittest.main()
