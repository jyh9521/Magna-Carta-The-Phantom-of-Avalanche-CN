import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import replay_battle_input as tool
class BattleInputTests(unittest.TestCase):
 def test_unknown_image_rejected(self):
  with self.assertRaises(ValueError):tool.verify(b'unknown engine')
 def test_source_native_windows_and_space_route(self):
  sample=ROOT/'runtime/data/MCAlpha.dll'
  if not sample.exists():self.skipTest('user-supplied supported engine absent')
  result=tool.verify(sample.read_bytes())
  self.assertEqual(len(result['cases']),12)
  self.assertEqual(result['space_routes'],{'0':None,'1':19,'2':None,'-1':None})
  self.assertFalse(result['game_started']);self.assertFalse(result['game_dll_loaded'])
 def test_render_rate_not_used_as_combo_time(self):
  source=(ROOT/'src/runtime/battle_input.h').read_text(encoding='utf8')
  self.assertIn('uint64_t(s.interval)*s.count',source)
  self.assertNotIn('GetTickCount',source);self.assertNotIn('QueryPerformanceCounter',source)
 def test_battle_only_input_still_runs_assist(self):
  source=(ROOT/'src/runtime/modern_gamepad.cpp').read_text(encoding='utf8')
  self.assertIn('passthroughOnly=passthroughOnly||battleOnly',source)
  self.assertIn('battleAssist(ok?keys:nullptr,battle,focused,false,false);if(ok)orbitKeyboard',source)
if __name__=='__main__':unittest.main()
