from pathlib import Path
import sys,re,unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
import render_candidate as render

class AdvancedDisplayContract(unittest.TestCase):
    def test_all_mode_hashes_are_exact_and_separate(self):
        native=(ROOT/'src/runtime/advanced_display.cpp').read_text('utf8')
        found=dict(re.findall(r'if\(mode==L"(\w+)"\)return hash=="([0-9a-f]{64})"',native))
        self.assertEqual(found,{k:render.graphics.sha(v) for k,v in render.PROFILES.items()})

    def test_modes_explicitly_clear_legacy_experiments(self):
        s=(ROOT/'src/runtime/workspace_launcher.cpp').read_text('utf8')
        self.assertIn('!textureLifetime&&(!modernInput||nativeGamepad)',s)
        self.assertIn('MC_GAMEPAD_NATIVE',s)
        for flag in ('MC_WIDE_DISPLAY','MC_RENDER60'):
            self.assertIn(flag,s)
        self.assertIn('Advanced mode/config mismatch',s)

    def test_logic_update_interval_not_rewritten(self):
        s=(ROOT/'src/runtime/advanced_display.cpp').read_text('utf8')
        self.assertIn('image+0xce5c,&desired,1',s)
        self.assertIn('memcmp(image+0xcf01,updateGuard',s)
        for interval in ('0x608cb','0x60fa3','0x61ba0','0x63040','0x8ab10','0x8ad0c','0xb140b','0xb62cb'):
            self.assertNotIn(interval,s)
        self.assertNotIn('timeBeginPeriod',s)

    def test_projection_preserves_other_matrices(self):
        s=(ROOT/'src/runtime/advanced_display.cpp').read_text('utf8')
        self.assertIn('mode==0x1701',s)
        self.assertIn('std::abs(original-4.0/3.0)<0.002',s)
        self.assertIn('originalPerspective(object,fov,changed,nearZ,farZ)',s)

if __name__=='__main__':unittest.main()
