import os
from pathlib import Path
import shutil
import sys
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_rage_combo_update as package
import verify_continue_game_update as verifier
import test_continue_game_update as fixtures
from test_runtime_module_update import dll


class RageUpdateTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.ContinueGameUpdateTests('test_input_hash_mismatch_does_not_publish')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.previous=self.fixture.build()
        self.module=self.fixture.base/'rage.dll';self.module.write_bytes(dll(b'owned rage build'))
        self.output=self.fixture.base/'rage.zip';self.work=self.fixture.base/'rage-work'

    def build(self):
        return package.build(self.previous,self.module,self.output,self.work,package.sha(self.previous.read_bytes()),package.sha(self.module.read_bytes()))

    def test_bad_identity_rejects_before_work(self):
        with self.assertRaisesRegex(ValueError,'Source hash'):
            package.build(self.previous,self.module,self.output,self.work,'0'*64,package.sha(self.module.read_bytes()))
        self.assertFalse(self.work.exists());self.assertFalse(self.output.exists())

    def test_zip_has_independent_scripts_and_backup_namespace(self):
        with zipfile.ZipFile(self.build()) as z:
            self.assertIsNone(z.testzip())
            self.assertIn(package.WRAPPER,z.namelist())
            script=z.read(package.FOLDER+'/Update.ps1')
            self.assertIn(package.BACKUP.encode(),script)
            self.assertNotIn(b"Located $Runtime '.continue-game-fix-20261023'",script)
            self.assertIn('F11',z.read('README-F11.txt').decode())

    @unittest.skipUnless(os.name=='nt' and shutil.which('powershell.exe'),'Windows updater required')
    def test_real_install_over_continue_fix_preserves_both_prior_journals(self):
        self.build()
        report=verifier.verify(self.work/'previous.zip',self.output,self.fixture.base/'verified',
            package.sha(self.output.read_bytes()),package.FOLDER,package.WRAPPER,'.continue-game-fix-20261023')
        self.assertEqual(report['rollback'],'exact')
        self.assertTrue(report['prior_backup_preserved'])
        self.assertEqual(report['final_state'],'modified')
