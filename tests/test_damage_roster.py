"""Roster inventory is not whole-skill execution coverage."""
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
READY = all(importlib.util.find_spec(n) is not None for n in ('unicorn', 'pefile'))


@unittest.skipUnless(READY and (ROOT/'runtime/data/MCAlpha.dll').is_file(), 'Supported offline inputs required')
class DamageRosterTests(unittest.TestCase):
    def test_all_eight_native_save_roster_rows_and_both_numeric_sinks(self):
        from audit_damage_roster import audit
        report = audit(ROOT/'runtime/data')
        self.assertEqual([r['char_id'] for r in report['roster']], [0, 3, 2, 1, 4, 6, 5, 20])
        self.assertTrue(all(r['model_id'] > 0 and r['abilities'] for r in report['roster']))
        self.assertEqual(report['numeric_producer_calls'], ['8c3c6', '8c87e'])
        self.assertEqual(report['anchor_subject'], 'victim_model')
        self.assertFalse(report['game_started'])


if __name__ == '__main__':
    unittest.main()
