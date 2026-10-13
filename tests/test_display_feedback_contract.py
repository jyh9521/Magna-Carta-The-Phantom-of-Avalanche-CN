"""Integration contracts; native fixtures supply behavioral proof, not these scans."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import render_candidate


class FeedbackContracts(unittest.TestCase):
    def test_title_layout_is_only_enabled_with_wide_canvas(self):
        text = (ROOT / 'src/runtime/workspace_profile.cpp').read_text('utf8')
        self.assertIn('localizedModule && wideDisplay && !installTitleLayout', text)
        source = (ROOT / 'src/runtime/title_layout.cpp').read_text('utf8')
        self.assertIn('wideUiPhysicalWidth()', source)
        self.assertIn('wideUiCanvasWidth()', source)
        self.assertNotIn('originalPerspective', source)
        self.assertNotIn('setRenderWait', source)
    def test_animation_library_version_lock(self):
        sha = render_candidate.SOURCE_INPUTS['Asura.dll']
        self.assertEqual(sha, 'f81e7c458d43b77210311499b39b9be2c4895e3a3b356d2e848b6e84210d2557')
        self.assertIn(sha, (ROOT / 'src/runtime/workspace_launcher.cpp').read_text('utf8'))

    def test_mode_scoped_runtime_modules(self):
        text = (ROOT / 'src/runtime/workspace_profile.cpp').read_text('utf8')
        self.assertIn('localizedModule && wideDisplay && !installWideUi', text)
        self.assertIn('localizedModule && render60 && !installMotion60', text)
        self.assertIn('localizedModule && !installMenuVisibility', text)

    def test_fixtures_are_built_independently(self):
        text = (ROOT / 'src/runtime/CMakeLists.txt').read_text('utf8')
        for name, flag in [('wide_ui', 'WIDE_UI_TEST'), ('menu_visibility', 'MENU_VISIBILITY_TEST'), ('motion60', 'MOTION60_TEST')]:
            self.assertIn(f'add_executable({name}_fixture ', text)
            self.assertIn(f'target_compile_definitions({name}_fixture PRIVATE {flag})', text)

    def test_motion_does_not_replace_logic_clock_or_tick(self):
        text = (ROOT / 'src/runtime/motion60.cpp').read_text('utf8')
        self.assertNotIn('timeBeginPeriod', text)
        self.assertNotIn('timeGetTime', text)
        self.assertNotIn('0x3ea50', text)
        self.assertIn('__finally', text)
        self.assertIn('engineBase+0x3b801', text)


if __name__ == '__main__':
    unittest.main()
