import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import refresh_advanced_trial as module


@unittest.skipUnless(sys.platform == 'win32', 'Windows runtime rollback')
class RefreshTests(unittest.TestCase):
    def setUp(self):
        (ROOT / 'build').mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=ROOT / 'build')
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name).resolve()
        self.w = root / 'candidate'
        self.r = self.w / '.advanced-runtime'
        self.n = root / 'native'
        self.r.mkdir(parents=True)
        self.n.mkdir()
        sha = module.trial.render.graphics.sha
        self.old = {}
        runtime_hashes = {}
        for name in ['workspace_profile.dll', 'workspace_launcher.exe']:
            data = ('owned old ' + name).encode()
            (self.r / name).write_bytes(data)
            self.old[name] = data
            runtime_hashes[name] = sha(data)
            (self.n / name).write_bytes(('owned new ' + name).encode())
        (self.w / 'Asura.dll').write_bytes(b'owned artifact')
        profiles = module.trial.render.PROFILES
        for name, data in profiles.items():
            (self.r / (name + '.ini')).write_bytes(data)
        (self.w / module.trial.render.CONFIG_NAME).write_bytes(profiles['baseline'])
        lock = dict(schema=1, workspace=str(self.w), source=str(root), config=module.trial.render.CONFIG_NAME,
                    runtime_hashes=runtime_hashes, profiles={n: sha(d) for n, d in profiles.items()})
        self.old['manifest.json'] = json.dumps(lock).encode()
        mutex = 'Local\\MagnaCartaAdvanced_' + sha(str(self.w).encode())[:24]
        self.old['StartAdvanced.ps1'] = module.trial.SCRIPT.replace('__LOCK__', json.dumps(lock, ensure_ascii=True)).replace(
            '__MANIFEST_HASH__', sha(self.old['manifest.json'])).replace('__MUTEX__', mutex).encode('utf-8-sig')
        for name in ['manifest.json', 'StartAdvanced.ps1']:
            (self.r / name).write_bytes(self.old[name])
        for target, value in [('SOURCE_INPUTS', {'Asura.dll': sha(b'owned artifact')}),
                              ('SOURCE_HASHES', {'Asura.dll': sha(b'owned artifact')})]:
            p = patch.object(module.trial.render, target, value)
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(module.trial.render, 'checked_source', side_effect=lambda p: Path(p).resolve())
        p.start()
        self.addCleanup(p.stop)

    def test_refresh_and_real_powershell_rollback(self):
        lock = module.refresh(self.w, self.n)
        for name in ['workspace_profile.dll', 'workspace_launcher.exe']:
            self.assertEqual((self.r / name).read_bytes(), (self.n / name).read_bytes())
        result = subprocess.run(['powershell.exe', '-NoProfile', '-File', str(self.r / 'RestorePrevious.ps1')],
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('PREVIOUS_RUNTIME_RESTORED PASS', result.stdout)
        for name, data in self.old.items():
            self.assertEqual((self.r / name).read_bytes(), data)
        for name, sha in lock['previous'].items():
            self.assertEqual(module.trial.prepare_workspace.digest(self.r / name), sha)

    def test_unknown_runtime_rejected_before_backup(self):
        (self.r / 'workspace_profile.dll').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            module.refresh(self.w, self.n)
        self.assertFalse(list(self.r.glob('previous-runtime-*')))

    def test_restore_rejects_drift_without_partial_write(self):
        module.refresh(self.w, self.n)
        (self.r / 'workspace_launcher.exe').write_bytes(b'unknown runtime')
        before = (self.r / 'workspace_profile.dll').read_bytes()
        result = subprocess.run(['powershell.exe', '-NoProfile', '-File', str(self.r / 'RestorePrevious.ps1')],
                                capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((self.r / 'workspace_profile.dll').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
