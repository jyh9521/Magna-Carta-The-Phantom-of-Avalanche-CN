"""Compiled production input closes the loop through original combo scoring."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from replay_combo_assist_chain import run_case
from replay_combo_cue import value_data


class ComboAssistChainTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = ROOT/'runtime/data'
        cls.bridge = ROOT/'build/native/Release/combo_assist_chain_fixture.exe'
        if not cls.bridge.exists() or not (cls.data/'MCAlpha.dll').exists():
            raise unittest.SkipTest('Build the owned adapter and supply original combat resources')
        cls.image = (cls.data/'MCAlpha.dll').read_bytes()
        cls.values = value_data((cls.data/'ValueData/0001.val').read_bytes())
        cls.abi = (cls.data/'Abi/0000.abi').read_bytes()

    def replay(self, hz, scenario, perfect=False):
        return run_case(self.image, self.values, self.abi, self.bridge,
                        hz, scenario, perfect, self.data)

    def test_f10_and_r3_reach_original_perfect_scoring_and_action_selection(self):
        for hz in (30, 60):
            for scenario in ('f10', 'r3'):
                with self.subTest(hz=hz, scenario=scenario):
                    result = self.replay(hz, scenario, True)
                    self.assertEqual(result['recorded'], [0, 10, 20])
                    self.assertTrue(result['producer_ready']['nativeIdentityFields'])
                    self.assertTrue(all(row['input'][19:21] == [0x20006000, 3]
                                        for row in result['production_rows']))
                    self.assertEqual(result['settlement']['selected_action'], 7)
                    self.assertEqual(result['native_timer_completion']['transition_calls'], 1)
                    self.assertEqual(result['native_timer_completion']['active_after'], 0)
                    self.assertEqual(result['producer_rollback']['rollback'], 'both_IATs_byte_exact')
                    self.assertFalse(result['game_started'])

    def test_real_handler_does_not_receive_assist_after_manual_hold_or_loss(self):
        for hz, scenario in ((30, 'held_a'), (60, 'held_x'),
                             (30, 'f10_focus'), (60, 'r3_disconnect')):
            with self.subTest(hz=hz, scenario=scenario):
                result = self.replay(hz, scenario)
                self.assertEqual(result['native_handler_calls'], 1)
                self.assertEqual(result['settlement']['selected_action'], 3)
                self.assertEqual(result['settlement']['perfect'], 0)


if __name__ == '__main__':
    unittest.main()
