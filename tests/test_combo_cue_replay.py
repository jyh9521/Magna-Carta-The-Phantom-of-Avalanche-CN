"""Guard actual value-file provenance and the bounded native cue counterexample."""
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import replay_combo_cue as replay

class ComboCueReplayTests(unittest.TestCase):
    def test_unknown_value_file_rejected(self):
        with self.assertRaisesRegex(ValueError, 'ValueData SHA256'):
            replay.value_data(b'unsupported')

    def test_actual_value_file_and_native_cues(self):
        sample = ROOT / 'runtime/data/MCAlpha.dll'
        values = ROOT / 'runtime/data/ValueData/0001.val'
        if not sample.exists() or not values.exists():
            self.skipTest('Supported user-supplied game inputs absent')
        config = replay.value_data(values.read_bytes())
        self.assertEqual((config[0x23], config[0x24]), (10, 6))
        result = replay.compare(sample.read_bytes(), config)
        first, second = result['runs']
        self.assertEqual(first['inputs'], second['inputs'])
        self.assertEqual(first['snapshots'], second['snapshots'])
        self.assertEqual(first['sounds'], second['sounds'])
        self.assertGreater(second['popup_draw_calls'], first['popup_draw_calls'])
        self.assertFalse(result['game_started'])

    def test_unknown_engine_rejected_before_mapping(self):
        with self.assertRaisesRegex(ValueError, 'engine SHA256'):
            replay.ComboCueReplay(b'unsupported', {})

if __name__ == '__main__':
    unittest.main()
