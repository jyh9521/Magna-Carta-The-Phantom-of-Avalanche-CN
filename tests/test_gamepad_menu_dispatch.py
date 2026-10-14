from pathlib import Path
import subprocess,unittest
ROOT=Path(__file__).resolve().parents[1]
EXE=ROOT/'build/native/Release/world_gamepad_fixture.exe'
@unittest.skipUnless(EXE.is_file(),'Build world_gamepad_fixture first')
class MenuDispatchTests(unittest.TestCase):
 def test_native_counter_and_button_callbacks(self):
  p=subprocess.run([str(EXE),'--menu-dispatch-only'],capture_output=True,text=True,timeout=20)
  self.assertEqual(p.returncode,0,p.stdout+p.stderr)
  self.assertIn('MENU_DISPATCH_REPLAY PASS press=3 release=3 held=4 idle_distinct=true physical_poll=true disabled_guard=true',p.stdout)
  self.assertIn('TITLE_LISTENER_REPLAY PASS requests=4 commands=6,7,9,11 event=3c release_only=true phase_guard=true native_widget_ids=true listener_vtable=true transition_executor=not_run commercial_code_executed=false',p.stdout)
  self.assertIn('commercial_code_executed=false',p.stdout)
