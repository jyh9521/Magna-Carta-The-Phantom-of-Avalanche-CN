from pathlib import Path
import struct
import unittest
from unittest.mock import patch
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import replay_native_gui_parent as t
SOURCE=ROOT/'runtime/data/MCAlpha.dll'

@unittest.skipUnless(SOURCE.exists(),'User-supplied source image required; no target is executed')
class GuiParentReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.image=SOURCE.read_bytes()
    def test_recorded_bounds_fault_and_replay_only_proposal_and_exact_rollback(self):
        r=t.replay(self.image)
        self.assertEqual(r['baseline']['fault']['address'],'0xbaf024')
        self.assertTrue(r['modified']['completed']);self.assertTrue(r['modified']['stack_balanced'])
        self.assertEqual(r['modified']['parent_unchanged'],hex(t.ROOT))
        self.assertEqual(r['baseline']['fault'],r['rollback']['fault'])
        self.assertFalse(r['os_game_started']);self.assertFalse(r['scene_transition_verified']);self.assertFalse(r['proposal_deployed'])
    def test_spatial_parent_translation_and_scale_still_inherit(self):
        n=t.NativeGuiParent(self.image,'spatial');n.patch();r=n.run()
        self.assertEqual(r['translation'],[110,220,330]);self.assertEqual(r['scale'],[6,12,20]);self.assertEqual(r['notifications'],2)
    def compare(self,setup):
        n=t.NativeGuiParent(self.image,'spatial');setup(n);before=n.run();n.patch();after=n.run();self.assertEqual(before,after)
    def test_same_class_not_global_root_is_not_bypassed(self):
        self.compare(lambda n:(n.write(t.OTHER,t.BASE+t.ROOT_VTABLE),n.write(t.OTHER+4,2)))
    def test_root_slot_match_with_other_vtable_is_not_bypassed(self):
        self.compare(lambda n:n.write(t.BASE+t.ROOT_SLOT,t.OTHER))
    def test_wrong_root_type_is_not_bypassed(self):
        self.compare(lambda n:(n.write(t.BASE+t.ROOT_SLOT,t.OTHER),n.write(t.OTHER,t.BASE+t.ROOT_VTABLE),n.write(t.OTHER+4,3)))
    def test_parented_root_is_not_bypassed(self):
        self.compare(lambda n:(n.write(t.BASE+t.ROOT_SLOT,t.OTHER),n.write(t.OTHER,t.BASE+t.ROOT_VTABLE),n.write(t.OTHER+4,2),n.write(t.OTHER+8,t.OTHER+0x200)))
    def test_idempotent_patch_and_guarded_exact_rollback(self):
        n=t.NativeGuiParent(self.image);n.patch();n.patch();n.rollback()
        self.assertEqual(bytes(n.cpu.mem_read(t.BASE+t.SITE,6)),t.EXPECTED)
        with self.assertRaises(ValueError):n.rollback()
    def test_unknown_site_is_not_overwritten(self):
        n=t.NativeGuiParent(self.image);n.cpu.mem_write(t.BASE+t.SITE,b'owned!')
        with self.assertRaises(ValueError):n.patch()
        self.assertEqual(bytes(n.cpu.mem_read(t.BASE+t.SITE,6)),b'owned!')
    def test_rollback_rejects_foreign_change(self):
        n=t.NativeGuiParent(self.image);n.patch();n.cpu.mem_write(t.BASE+t.SITE,b'owned!')
        with self.assertRaises(ValueError):n.rollback()
        self.assertEqual(bytes(n.cpu.mem_read(t.BASE+t.SITE,6)),b'owned!')

class SourceGuardTests(unittest.TestCase):
    def test_unknown_source_rejected_before_emulator_setup(self):
        with patch.object(t.NativeTitle,'__init__') as init:
            with self.assertRaises(ValueError):t.NativeGuiParent(b'owned unsupported sample')
            init.assert_not_called()

if __name__=='__main__':unittest.main()
