from pathlib import Path
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
import replay_native_cursor as replay


class NativeCursorReplayTests(unittest.TestCase):
    def test_unknown_image_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported MCAlpha image'):
            replay.run_replay(b'owned unsupported input')

    def test_report_cannot_overwrite_sample_or_alias(self):
        (ROOT/'build').mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT/'build', prefix='cursor-replay-guard-') as directory:
            folder = Path(directory).resolve()
            self.assertTrue(folder.is_relative_to((ROOT/'build').resolve()))
            sample = folder/'sample.bin'
            sample.write_bytes(b'owned invalid sample')
            alias = folder/'alias.json'
            os.link(sample, alias)
            for output in [sample, alias]:
                r = subprocess.run([sys.executable, '-O', str(ROOT/'tools/replay_native_cursor.py'),
                                    '--sample', str(sample), '--report', str(output)], capture_output=True, text=True)
                self.assertEqual(r.returncode, 2, r.stderr)
                self.assertIn('Report must differ from the sample path', r.stderr)
                self.assertEqual(sample.read_bytes(), b'owned invalid sample')

    @unittest.skipUnless(importlib.util.find_spec('unicorn') and (ROOT/'runtime/data/MCAlpha.dll').is_file(),
                         'Requires optional Unicorn and user-supplied supported image')
    def test_original_cursor_preparation_and_visibility(self):
        report = replay.run_replay((ROOT/'runtime/data/MCAlpha.dll').read_bytes())
        self.assertEqual(len(report['cases']), 9)
        self.assertGreater(report['native_instructions'], 100)
        self.assertFalse(report['graphics_APIs_executed'])
        self.assertFalse(report['game_started'])
        for case in report['cases'][:5]:
            self.assertEqual(case['local_position'][:2], tuple(case['click']))
            self.assertEqual(case['prepared_position'], case['local_position'])
        self.assertEqual(report['cases'][-1]['old_render_order'], -1)
        self.assertEqual(report['cases'][-1]['current_render_order'], 0)
