"""Optional source-locked native instruction checks, never game execution."""
from pathlib import Path
import hashlib
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
sys.path.insert(0, str(ROOT/'runtime/dependencies'))
import replay_native_map_points as tool
from replay_native_title import SUPPORTED_SHAS


class NativeMapPointsTests(unittest.TestCase):
    def test_unknown_engine_rejected_before_emulation(self):
        with self.assertRaisesRegex(ValueError, 'SHA256'):
            tool.run(b'owned unsupported engine')

    def test_native_condition_and_transition_routes_when_source_present(self):
        engine = ROOT/'runtime/data/MCAlpha.dll'
        if not engine.exists() or hashlib.sha256(engine.read_bytes()).hexdigest() not in SUPPORTED_SHAS:
            self.skipTest('Optional supported engine source absent')
        try:
            import unicorn
        except ImportError:
            self.skipTest('Optional Unicorn dependency absent')
        result = tool.run(engine.read_bytes())
        self.assertEqual([row['result'] for row in result['conditions']], [1, 0, 1, 0, 0, 0])
        self.assertEqual([row['transition']['target_field'] for row in result['transitions']], [663, 751])
        self.assertEqual(result['transitions'][1]['entry_state'], [1, 7, 8])
        self.assertFalse(result['game_started'])
        self.assertFalse(result['scene_loader_executed'])


if __name__ == '__main__':
    unittest.main()
