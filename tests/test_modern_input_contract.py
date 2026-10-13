"""Modern-input integration defaults; behavior lives in the native fixtures."""
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]


class ModernInputContractTests(unittest.TestCase):
    def test_explicit_launcher_switch_and_environment_reset(self):
        source=(ROOT/'src/runtime/workspace_launcher.cpp').read_text('utf8')
        self.assertIn('modernInput = false',source)
        self.assertIn('arg == L"--modern-input"',source)
        self.assertIn('MC_MODERN_INPUT",modernInput?L"1":L"0"',source)
        self.assertIn('!modernInput || !fixture',source)

    def test_no_global_keyboard_injection(self):
        source=(ROOT/'src/runtime/modern_gamepad.cpp').read_text('utf8')
        for forbidden in ('SendInput(', 'keybd_event(', 'PostMessage(', 'SetForegroundWindow('):
            self.assertNotIn(forbidden,source)
        self.assertIn('front==*gameWindow',source)
        self.assertIn('returnAddress!=caller',source)
        self.assertIn('LOAD_LIBRARY_SEARCH_SYSTEM32',source)

    def test_build_remains_optional_and_separate_from_locale_data(self):
        source=(ROOT/'src/runtime/workspace_profile.cpp').read_text('utf8')
        self.assertIn('bool modernInput = false',source)
        self.assertIn('MODERN_INPUT_REJECTED',source)
        cmake=(ROOT/'src/runtime/CMakeLists.txt').read_text('utf8')
        self.assertIn('modern_gamepad_fixture',cmake)
        self.assertIn('MODERN_INPUT_TEST',cmake)


if __name__=='__main__':unittest.main()
