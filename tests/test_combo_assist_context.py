"""Production compiled combo-assist manual ownership and lifecycle guards."""
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]

class ComboAssistContextTests(unittest.TestCase):
    def test_fixture_compiles_production_router_exactly_once(self):
        source = (ROOT / 'src/runtime/combo_assist_context_fixture.cpp').read_text('utf8')
        self.assertIn('#include "modern_gamepad.cpp"', source)
        self.assertNotIn('LoadLibrary(', source)
        cmake = (ROOT / 'src/runtime/CMakeLists.txt').read_text('utf8')
        declaration = next(line for line in cmake.splitlines()
                           if line.startswith('add_executable(combo_assist_context_fixture '))
        self.assertNotIn(' modern_gamepad.cpp', declaration)
        self.assertIn('MODERN_INPUT_TEST', cmake)

    def test_manual_takeover_mode_device_and_attack_lifecycle(self):
        executable = ROOT / 'build/native/Release/combo_assist_context_fixture.exe'
        if not executable.exists():
            self.skipTest('Build the owned combo_assist_context_fixture target first')
        result = subprocess.run([str(executable)], capture_output=True, text=True,
                                encoding='utf8', errors='replace', timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for check in ['held_A_blocks_R3', 'held_X_blocks_R3',
                      'A_manual_takeover_cancels', 'X_manual_takeover_cancels',
                      'pad_mode_menu_cancel', 'pad_mode_result_cancel',
                      'pad_mode_blocked_cancel', 'F10_mode_menu_cancel',
                      'F10_mode_result_cancel', 'F10_mode_blocked_cancel',
                      'pad_device_switch_cancel', 'same_scene_attack_regression_cancel']:
            self.assertIn('PASS ' + check, result.stdout)
        self.assertIn('COMBO_ASSIST_CONTEXT checks=14 failures=0', result.stdout)
        self.assertIn('game_started=false commercial_dll_loaded=false', result.stdout)

if __name__ == '__main__':
    unittest.main()
