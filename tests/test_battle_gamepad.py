"""Actual PE GUI state and complete native rectangle snapshots; no game launch."""
import sys
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import replay_battle_gamepad as tool
ENGINE=ROOT/'runtime/data/MCAlpha.dll'
VALUES=ROOT/'runtime/data/ValueData/0001.val'
class BattleGamepad(unittest.TestCase):
 def replay(self,mode=4):
  if not ENGINE.is_file() or not VALUES.is_file():self.skipTest('Supported local resources not supplied')
  return tool.BattleGamepadReplay(ENGINE.read_bytes(),tool.value_data(VALUES.read_bytes()),ROOT/'runtime/data',mode=mode)
 def test_unknown_engine_rejected(self):
  with self.assertRaisesRegex(ValueError,'Unsupported complete engine SHA256'):tool.BattleGamepadReplay(b'owned fixture',{},ROOT)
 def test_canvas_bound(self):
  with self.assertRaisesRegex(ValueError,'logical canvas'):tool.BattleGamepadReplay(b'',{},ROOT,width=0,height=0)
 def test_real_constructor_and_all_native_rect_nodes(self):
  q=self.replay();nodes=q.snapshot()['nodes'];cmd=next(n for n in nodes if n['id']==0x104)
  self.assertEqual(cmd['vt'],0xc02d4);self.assertEqual(cmd['rects'],[[10,132,168,270],[0,0,800,600]])
  buttons={n['id']:n for n in nodes if n['vt']==0xc00dc}
  self.assertEqual([(buttons[i]['x'],buttons[i]['y']) for i in [0x105,0x106,0x10b]],[(10.,132.),(10.,177.),(10.,222.)])
  for x,y in [(400,300),(50,152)]:
   q.call(0x4e686,cmd['address'],x,y);self.assertEqual(q.cpu.reg_read(tool.UC_X86_REG_EAX),1)
 def test_native_cancel_esc_red_mouse_green(self):
  for key,expected in [(27,0),(2,5)]:
   q=self.replay();keys=bytearray(256);keys[key]=128;q.feed(bytes(keys));result=q.feed(bytes(256));self.assertEqual(result['command'],expected)
 def test_actual_field_actor_virtual_turn(self):
  q=self.replay(1);keys=bytearray(256);keys[37]=128;result=q.feed(bytes(keys));self.assertAlmostEqual(result['actor_angle'],0.15,places=5)
  self.assertEqual(q.read(tool.ACTOR),tool.BASE+0xc1644)
 def test_native_populated_ability_label_constructor_and_selection(self):
  q=self.replay(4);q.populate_ability();q.call(0xaff96,tool.MENU,5)
  button=next(n for n in q.snapshot()['nodes'] if n['id']==0x10f and n['vt']==0xc00dc)
  self.assertEqual(button['rects'],[[0,0,168,45]])
  point=[94,154];keys=bytearray(256);keys[1]=128;result=q.feed(bytes(keys),point)
  self.assertEqual((result['command'],result['target_mode'],result['ability']),(5,5,0))
  self.assertEqual(result['pressed_buttons']['271'],1)
  q.call(0x5718f,button['address']);self.assertEqual(q.read(button['address']+0x19c),0)
  after=q.feed(bytes(256),point);self.assertEqual(after['events'],[])
 def test_budget_checked_even_without_assertions(self):
  q=self.replay()
  with self.assertRaisesRegex(ValueError,'instruction budget/stop failure'):q.run(tool.BASE+0x55134,tool.STOP,budget=1)
if __name__=='__main__':unittest.main()
