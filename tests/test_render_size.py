import sys
from pathlib import Path
import re
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import predict_render_size as size
import graphics_compat as graphics

class RenderSizeTests(unittest.TestCase):
    def test_1080_preserves_original_ratio(self):
        self.assertEqual(size.predict([640,480],[1920,1080],-1),[1440,1080])

    def test_positive_multiplier_rounds_up(self):
        self.assertEqual(size.predict([640,480],[1920,1080],1),[1920,1440])

    def test_integer_and_disabled_scaling(self):
        self.assertEqual(size.predict([640,480],[640,480],2),[1280,960])
        self.assertEqual(size.predict([640,480],[1920,1080],0),[640,480])

    def test_invalid_dimensions(self):
        with self.assertRaises(ValueError):size.predict([0,480],[1920,1080],-1)
        with self.assertRaises(ValueError):size.predict([640,480],[1920,1080],17)

    def test_native_focus_config_hashes_match_profiles(self):
        source=(Path(__file__).resolve().parents[1]/'src/runtime/workspace_launcher.cpp').read_text()
        branch=source.split('auto focusConfig =',1)[1].split('Unsupported focus graphics configuration',1)[0]
        actual=set(re.findall(r'"([0-9a-f]{64})"',branch))
        expected={graphics.sha(graphics.PROFILES[p]) for p in ['standard','activation','render2x','render1080']}
        self.assertEqual(actual,expected)
