"""F11 production input must reach actual native rage grading and selection."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from replay_rage_combo_assist import run
from replay_combo_assist_chain import Producer


class RageComboAssistTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=ROOT/'runtime/data'
        cls.bridge=ROOT/'build/native/Release/combo_assist_chain_fixture.exe'
        if not cls.bridge.exists() or not (cls.data/'MCAlpha.dll').exists():
            raise unittest.SkipTest('Build owned bridge and supply supported native resources')

    def test_f11_reaches_best_native_grade_at_both_rates(self):
        for hz in (30,60):
            r=run(self.data,self.bridge,hz,'f11',True)
            self.assertEqual(r['rage_recorded'],[0,3,6])
            self.assertEqual(r['native_handler_calls'],3)
            self.assertEqual(r['settlement'],dict(success=1,grade=3,selected_action=199))
            self.assertEqual(r['producer_rollback']['rollback'],'both_IATs_byte_exact')
            self.assertTrue(all(x['output']['pollsDelta']==0 for x in r['production_rows']))
            self.assertTrue(all(not x['output']['clearSpaceCounter'] for x in r['production_rows']))
            self.assertFalse(r['game_started'])

    def test_held_f11_and_manual_first_space_complete_once(self):
        for scenario in ('held_f11','manual_takeover'):
            r=run(self.data,self.bridge,60,scenario,True)
            self.assertEqual(r['native_handler_calls'],3)
            self.assertEqual(r['transition_calls'],1)

    def test_all_source_apocalypse_ability_records_select_their_own_actions(self):
        for ability,target in ((13,199),(14,200),(22,213),(30,205),(38,201),(46,202),(54,204),(62,203)):
            r=run(self.data,self.bridge,60,'f11',True,ability)
            self.assertEqual(r['settlement']['selected_action'],target)
            self.assertEqual(r['resources']['ability_id'],ability)

    def test_wrong_mode_focus_manual_hold_and_late_takeover_do_not_force_grade(self):
        for scenario in ('f10','focus_loss','manual_hold','late_takeover'):
            r=run(self.data,self.bridge,60,scenario)
            self.assertEqual(r['rage_count'],1,scenario)
            self.assertEqual(r['settlement']['success'],0,scenario)
            self.assertEqual(r['settlement']['selected_action'],13,scenario)

    def test_opposite_timed_mode_and_ambiguous_keys_do_not_emit(self):
        for hotkeys,normal,rage in ((2,1,0),(1,0,1),(3,0,0)):
            p=Producer(self.bridge,True)
            try:
                # Actual production adapter, not a Python scheduling substitute.
                fields=[0,1,1,1,normal,1,1,10,6,1,1,0,hotkeys,0,0,1,0,0,2,0x20006000,13,rage,1,1,10,3,4]
                row=p.sample(fields)
                self.assertFalse(bytes.fromhex(row['keysHex'])[32]&128)
                self.assertFalse(row['trace'])
                p.close()
            finally:
                if p.process.poll() is None:p.process.kill();p.process.wait(timeout=10)
