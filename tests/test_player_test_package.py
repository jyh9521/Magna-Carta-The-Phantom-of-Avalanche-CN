import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

@unittest.skipUnless(shutil.which('powershell.exe'), 'Windows PowerShell required')
class PlayerPackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root/'original'
        self.source.mkdir()
        self.target = self.root/'trial'
        self.package = self.root/'package'
        self.package.mkdir()
        shutil.copy2(ROOT/'assets/player-test-package/Install.ps1',self.package/'Install.ps1')
        self.before = b'original-owned-fixture'
        self.after = b'modified-owned-fixture-longer'
        (self.source/'sample.bin').write_bytes(self.before)
        (self.source/'sample.sav').write_bytes(b'user-save')
        (self.package/'payload').mkdir()
        (self.package/'payload/owned.txt').write_bytes(b'owned')
        self.patch = b'MCD1'+struct.pack('<Q',len(self.after))+struct.pack('<QI',0,len(self.after))+self.after
        (self.package/'patch.mcd').write_bytes(self.patch)
        self.manifest = dict(schema=1,source_files={'sample.bin':digest(self.before)},
            payload={'owned.txt':digest(b'owned')},changes=[dict(resource='sample.bin',
                source_sha256=digest(self.before),target_sha256=digest(self.after),target_size=len(self.after),
                patch='patch.mcd',patch_sha256=digest(self.patch))])
        self.write_manifest()

    def write_manifest(self):
        (self.package/'package.json').write_text(json.dumps(self.manifest))

    def run_action(self,action):
        return subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass',
            '-File',str(self.package/'Install.ps1'),'-Action',action,'-Source',str(self.source),
            '-Target',str(self.target)],capture_output=True,text=True)

    def install(self):
        p=self.run_action('Install')
        self.assertEqual(p.returncode,0,p.stdout+p.stderr)

    def test_verify_is_read_only(self):
        p=self.run_action('Verify')
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn('BASELINE PASS originals=1 deltas=1',p.stdout)
        self.assertFalse(self.target.exists())

    def test_install_and_check(self):
        self.install()
        self.assertEqual((self.target/'data/sample.bin').read_bytes(),self.after)
        self.assertEqual((self.source/'sample.bin').read_bytes(),self.before)
        self.assertEqual(self.run_action('CheckInstalled').returncode,0)

    def test_rollback_preserves_save(self):
        self.install()
        (self.target/'data/sample.sav').write_bytes(b'new-progress')
        p=self.run_action('Rollback')
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual((self.target/'data/sample.bin').read_bytes(),self.before)
        self.assertEqual((self.target/'data/sample.sav').read_bytes(),b'new-progress')

    def test_drift_refuses_rollback(self):
        self.install()
        (self.target/'data/sample.bin').write_bytes(b'edited')
        self.assertNotEqual(self.run_action('Rollback').returncode,0)
        self.assertEqual((self.target/'data/sample.bin').read_bytes(),b'edited')

    def test_unknown_source_rejected(self):
        (self.source/'sample.bin').write_bytes(b'unknown')
        self.assertNotEqual(self.run_action('Install').returncode,0)
        self.assertFalse(self.target.exists())

    def test_existing_target_preserved(self):
        self.target.mkdir()
        (self.target/'sentinel').write_bytes(b'keep')
        self.assertNotEqual(self.run_action('Install').returncode,0)
        self.assertEqual((self.target/'sentinel').read_bytes(),b'keep')

    def test_path_escape_rejected(self):
        self.manifest['changes'][0]['resource']='../escape'
        self.write_manifest()
        self.assertNotEqual(self.run_action('Install').returncode,0)
        self.assertFalse(self.target.exists())
