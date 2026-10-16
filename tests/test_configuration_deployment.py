import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import update_configuration_runtime as tool


class ConfigurationDeploymentTests(unittest.TestCase):
    def fixture(self, root):
        runtime = root/'runtime'
        (runtime/'config').mkdir(parents=True)
        (runtime/'modules').mkdir()
        (runtime/'config/enhancements.json').write_bytes(b'{"schema":1,"display_profile":"wide4k","motion60":false,"native_gamepad":false}')
        (runtime/'config/Configure.ps1').write_bytes(b'owned original UI')
        (runtime/'modules/workspace_launcher.exe').write_bytes(b'owned original launcher')
        manifest = {'schema':1, 'profiles':{}, 'files':{
            'config/Configure.ps1':hashlib.sha256(b'owned original UI').hexdigest(),
            'modules/workspace_launcher.exe':hashlib.sha256(b'owned original launcher').hexdigest()}}
        (runtime/'runtime.json').write_text(json.dumps(manifest))
        native = root/'native'; native.mkdir()
        for name in ['workspace_profile.dll', 'workspace_launcher.exe']:
            (native/name).write_bytes(b'owned new '+name.encode())
        return runtime, native

    def test_actual_update_and_isolated_rollback_restore_exact_files(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(tool, 'idle'):
            root=Path(directory);runtime,native=self.fixture(root);record=root/'record'
            before={str(p.relative_to(runtime)):p.read_bytes() for p in runtime.rglob('*') if p.is_file()}
            tool.apply(runtime,native,record)
            self.assertTrue((runtime/'config/Configure.xaml').is_file())
            self.assertEqual((runtime/'modules/configuration.dll').read_bytes(),b'owned new workspace_profile.dll')
            tool.rollback(runtime,record)
            after={str(p.relative_to(runtime)):p.read_bytes() for p in runtime.rglob('*') if p.is_file()}
            self.assertEqual(before,after)

    def test_existing_input_drift_rejected_before_record_or_writes(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(tool, 'idle'):
            root=Path(directory);runtime,native=self.fixture(root);record=root/'record'
            (runtime/'config/Configure.ps1').write_bytes(b'edited')
            with self.assertRaisesRegex(ValueError,'Runtime input changed'):
                tool.apply(runtime,native,record)
            self.assertFalse(record.exists())
            self.assertFalse((runtime/'modules/configuration.dll').exists())

    def test_post_update_edits_block_whole_rollback(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(tool, 'idle'):
            root=Path(directory);runtime,native=self.fixture(root);record=root/'record'
            tool.apply(runtime,native,record)
            (runtime/'config/Configure.ps1').write_bytes(b'keep later edit')
            before=(runtime/'runtime.json').read_bytes()
            with self.assertRaisesRegex(ValueError,'Rollback target changed'):
                tool.rollback(runtime,record)
            self.assertEqual((runtime/'config/Configure.ps1').read_bytes(),b'keep later edit')
            self.assertEqual((runtime/'runtime.json').read_bytes(),before)

    def test_new_user_settings_block_incompatible_old_ui_restore(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(tool, 'idle'):
            root=Path(directory);runtime,native=self.fixture(root);record=root/'record'
            tool.apply(runtime,native,record)
            settings=b'{"schema":2,"resolution":"2k"}'
            (runtime/'config/enhancements.json').write_bytes(settings)
            with self.assertRaisesRegex(ValueError,'Settings changed since deployment'):
                tool.rollback(runtime,record)
            self.assertEqual((runtime/'config/enhancements.json').read_bytes(),settings)
            self.assertTrue((runtime/'config/Configure.xaml').is_file())


if __name__=='__main__':
    unittest.main()
