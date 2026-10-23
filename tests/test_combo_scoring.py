"""Actual engine bytecode consumes source-locked ABI/ATT rows and recorded hits."""
import sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import replay_native_combo_scoring as scoring

class NativeComboScoringTests(unittest.TestCase):
    def test_unknown_resource_rejected(self):
        with self.assertRaisesRegex(ValueError,'SHA256'):
            scoring.resource_rows(b'unknown',scoring.ABI_SHA,205,7,0x158)

    def test_actual_resource_predicates_and_settlement(self):
        data=ROOT/'runtime/data'
        if not (data/'MCAlpha.dll').exists():self.skipTest('User-supplied game input absent')
        result=scoring.compare(data)
        old,fixed,edge,miss=result['runs']
        self.assertEqual(old['settlement']['success_count'],3)
        self.assertEqual(old['settlement']['perfect'],0)
        self.assertEqual(old['settlement']['selected_action'],10)
        self.assertEqual(fixed['settlement']['perfect'],1)
        self.assertEqual(fixed['settlement']['success_count'],3)
        self.assertEqual(fixed['settlement']['selected_action'],7)
        self.assertIn(3,fixed['settlement']['popup_kinds'])
        self.assertEqual(edge['settlement']['perfect'],1)
        self.assertEqual(miss['settlement']['perfect'],0)
        self.assertLess(miss['settlement']['success_count'],3)
        self.assertFalse(result['predicate_stubs'])
        self.assertFalse(result['game_started'])
        self.assertFalse(result['dll_loaded'])

    def test_queue_replay_variadic_call_compatibility(self):
        from replay_battle_message_queue import QueueReplay, SCENE
        from replay_combo_cue import value_data
        data=ROOT/'runtime/data'
        if not (data/'MCAlpha.dll').exists():self.skipTest('User-supplied game input absent')
        q=QueueReplay((data/'MCAlpha.dll').read_bytes(),value_data((data/'ValueData/0001.val').read_bytes()),30,[])
        scoring.setupCombatResources(q,data)
        q.call(0xa3681,SCENE)
        for tick in (10,20):
            q.write(SCENE+0x1de0,tick)
            q.call(0xa3681,SCENE)
        result=scoring.settle(q,choose_action=True)
        self.assertEqual((result['perfect'],result['success_count'],result['selected_action']),(1,3,7))

if __name__=='__main__':unittest.main()
