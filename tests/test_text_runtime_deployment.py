import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import deploy_text_runtime as deploy


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.runtime, self.candidate, self.native, self.record = [root/n for n in ['runtime','candidate','native','record']]
        self.old = {'modules/display.dll': b'old profile', 'modules/workspace_launcher.exe': b'old launcher',
                    'data/MCAlpha.dll': b'owned old text', 'config/enhancements.json': b'keep settings', 'data/a.sav': b'keep save'}
        for name, raw in self.old.items():
            path = self.runtime/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        digest = lambda b: hashlib.sha256(b).hexdigest()
        manifest = dict(schema=1, files={n: digest(b) for n,b in self.old.items() if n.startswith('modules/')},
                        data={'MCAlpha.dll': digest(self.old['data/MCAlpha.dll'])})
        self.old['runtime.json'] = (json.dumps(manifest)+'\n').encode()
        (self.runtime/'runtime.json').write_bytes(self.old['runtime.json'])
        self.candidate.mkdir()
        (self.candidate/'MCAlpha.dll').write_bytes(b'owned new text')
        (self.candidate/'build.json').write_text(json.dumps({'files':[dict(resource='MCAlpha.dll', before_sha256=digest(b'owned old text'), after_sha256=digest(b'owned new text'))]}))
        self.native.mkdir()
        (self.native/'workspace_profile.dll').write_bytes(b'new profile')
        (self.native/'workspace_launcher.exe').write_bytes(b'new launcher')

    def apply(self):
        with patch.object(deploy, 'idle'):
            return deploy.apply(self.runtime, self.candidate, self.native, self.record)

    def test_apply_and_isolated_rollback(self):
        states = self.apply()
        self.assertEqual(len(states), 4)
        self.assertEqual((self.runtime/'data/MCAlpha.dll').read_bytes(), b'owned new text')
        deploy.rollback(self.runtime, self.record)
        self.assertEqual(self.old, {n:(self.runtime/n).read_bytes() for n in self.old})

    def test_unknown_candidate_before_no_write(self):
        (self.candidate/'MCAlpha.dll').write_bytes(b'drift')
        with self.assertRaisesRegex(ValueError, 'output mismatch'):
            self.apply()
        self.assertFalse(self.record.exists())
        self.assertEqual(self.old, {n:(self.runtime/n).read_bytes() for n in self.old})

    def test_runtime_drift_no_write(self):
        (self.runtime/'modules/display.dll').write_bytes(b'drift')
        with self.assertRaisesRegex(ValueError, 'Runtime drift'):
            self.apply()
        self.assertFalse(self.record.exists())

    def test_partial_write_failure_restores_exact(self):
        real_write = deploy.write
        count = 0
        def fail_once(path, data):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError('injected write failure')
            real_write(path, data)
        with patch.object(deploy, 'write', side_effect=fail_once):
            with self.assertRaisesRegex(OSError, 'injected'):
                self.apply()
        self.assertEqual(self.old, {n:(self.runtime/n).read_bytes() for n in self.old})
