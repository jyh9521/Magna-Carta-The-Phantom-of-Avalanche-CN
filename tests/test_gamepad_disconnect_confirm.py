from pathlib import Path
import subprocess
import unittest
ROOT=Path(__file__).resolve().parents[1]
class GamepadDisconnectConfirmTests(unittest.TestCase):
    def test_actual_input_ui_and_title_release_contract(self):
        exe=ROOT/'build/native/Release/world_gamepad_fixture.exe'
        if not exe.exists():
            self.skipTest('Build the owned world_gamepad_fixture first')
        result=subprocess.run([str(exe),'--menu-dispatch-only'],capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)
        self.assertIn('GAMEPAD_DISCONNECT_REPLAY PASS synthetic_release=cancelled device_switch=cancelled visual_press=cleared physical_release=preserved neutral_rearm=true focus_path=unchanged game_started=false',result.stdout)
        self.assertIn('TITLE_LISTENER_REPLAY PASS requests=4',result.stdout)
if __name__=='__main__':
    unittest.main()
