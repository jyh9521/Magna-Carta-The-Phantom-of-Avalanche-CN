import hashlib
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import replay_scene_resource as r


class SourceGuardTests(unittest.TestCase):
    def test_unknown_source_is_rejected_before_emulation(self):
        with self.assertRaisesRegex(ValueError, 'full engine SHA256'):
            r.ResourceReplay(b'unknown')


@unittest.skipUnless((ROOT / 'runtime/data/MCAlpha.dll').is_file(), 'Local source-locked sample required')
class NativeResourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.image = (ROOT / 'runtime/data/MCAlpha.dll').read_bytes()
        cls.before = hashlib.sha256(cls.image).hexdigest()
        cls.report = r.verify(cls.image)

    def test_twelve_cases_and_no_game_acceptance(self):
        self.assertEqual(len(self.report['cases']), 12)
        for field in ('game_started', 'game_dll_loaded', 'production_modified',
                      'scene_transition_verified', 'scene_root_cause_confirmed'):
            self.assertIs(self.report[field], False)

    def test_type8_worker_does_not_produce_map(self):
        for state in range(5):
            c = self.report['cases']['worker_type8_state' + str(state)]
            self.assertEqual(c['result'], '0x0')
            self.assertNotIn('type3_load_boundary', c['boundaries'])

    def test_type3_control_produces_result(self):
        c = self.report['cases']['worker_type3_control']
        self.assertEqual(c['result'], hex(r.RESULT))
        self.assertEqual(c['state'], 3)

    def test_state2_does_not_schedule_delete(self):
        c = self.report['cases']['state2']
        self.assertEqual((c['sync_loads'], c['state']), (1, 2))

    def test_completed_cases_mark_retirement(self):
        for name, loads in [('complete_cached', 0), ('complete_empty', 1)]:
            c = self.report['cases'][name]
            self.assertEqual((c['sync_loads'], c['state']), (loads, 4))

    def test_noncompletion_is_wait_not_crash(self):
        c = self.report['cases']['pending_never_completed']
        self.assertEqual(c['outcome'], 'bounded_wait_not_crash')
        self.assertGreater(c['sleeps'], 1)
        self.assertFalse(c['returned'])

    def test_original_bytes_remain_and_drift_rejected(self):
        changed = bytearray(self.image); changed[-1] ^= 1
        with self.assertRaisesRegex(ValueError, 'full engine SHA256'):
            r.ResourceReplay(bytes(changed))
        self.assertEqual(hashlib.sha256(self.image).hexdigest(), self.before)


if __name__ == '__main__':
    unittest.main()
