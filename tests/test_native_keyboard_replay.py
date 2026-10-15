from pathlib import Path
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import replay_native_keyboard as replay


class NativeKeyboardReplayTests(unittest.TestCase):
    def test_unknown_image_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported MCAlpha image'):
            replay.run_replay(b'owned unsupported sample')

    def test_report_cannot_overwrite_sample_or_hardlink(self):
        (ROOT/'build').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'build', prefix='keyboard-replay-guard-') as directory:
            folder = Path(directory).resolve()
            self.assertTrue(folder.is_relative_to((ROOT/'build').resolve()))
            sample = folder/'sample.bin'
            sample.write_bytes(b'owned invalid sample')
            alias = folder/'alias.json'
            os.link(sample, alias)
            for output in [sample, alias]:
                r = subprocess.run([sys.executable, '-O', str(ROOT/'tools/replay_native_keyboard.py'),
                                    '--sample', str(sample), '--report', str(output)], capture_output=True, text=True)
                self.assertEqual(r.returncode, 2, r.stderr)
                self.assertIn('Report must differ from the sample path', r.stderr)
                self.assertEqual(sample.read_bytes(), b'owned invalid sample')

    @unittest.skipUnless(importlib.util.find_spec('unicorn') and (ROOT/'runtime/data/MCAlpha.dll').is_file(),
                         'Requires optional Unicorn and supported user-supplied image')
    def test_original_keyboard_admission_and_direction_phases(self):
        report = replay.run_replay((ROOT/'runtime/data/MCAlpha.dll').read_bytes())
        self.assertEqual(len(report['cases']), 25)
        self.assertFalse(report['game_started'])
        self.assertEqual(report['listener'], 'boundary_recorder')
        cases = {c['name']: c for c in report['cases']}
        self.assertEqual(cases['nonmodal_mode_0']['return'], 1)
        self.assertEqual(cases['nonmodal_mode_1']['events'], [])
        self.assertEqual(cases['exclusive_exact_mode_2']['return'], 1)
        self.assertEqual(cases['exclusive_sibling_mode_0']['return'], 0)
        self.assertEqual(cases['masked_down_zero']['active_events'], [])
        self.assertEqual(cases['original_down_idle_route']['up_idle_event_10_count'], 2)
