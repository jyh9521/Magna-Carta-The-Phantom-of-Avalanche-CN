"""Actual native queue/scheduler/GUI-handler red regression and compiled-latch green."""
import hashlib
from pathlib import Path
import unittest
import sys
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"tools"))
import replay_battle_message_queue as tool
ENGINE=ROOT/'runtime/data/MCAlpha.dll'
VALUES=ROOT/'runtime/data/ValueData/0001.val'

class BattleMessageQueue(unittest.TestCase):
 def inputs(self):
  if not ENGINE.exists() or not VALUES.exists():self.skipTest('Supported local PE and ValueData inputs not supplied')
  return ENGINE.read_bytes(),tool.value_data(VALUES.read_bytes())
 def bridge(self):
  p=ROOT/'build/battle-edge-bridge/Release/battle_edge_bridge.dll'
  if p.exists():return p
  self.skipTest('Build the owned x64 battle_edge_bridge target first')
 def test_unknown_source_rejected(self):
  with self.assertRaisesRegex(ValueError,'Unsupported complete engine SHA256'):
   tool.QueueReplay(b'owned unknown sample',{},60,[])
 def test_native_instruction_guard_rejects_mutation(self):
  import pefile,replay_native_title
  image,_=self.inputs();data=bytearray(image);p=pefile.PE(data=data);data[p.get_offset_from_rva(0xbde7)]^=1;digest=hashlib.sha256(data).hexdigest()
  with patch.object(tool,'ENGINE_SHA',digest),patch.object(replay_native_title,'SUPPORTED_SHAS',{digest}):
   with self.assertRaisesRegex(ValueError,'Native source guard drift'):
    tool.QueueReplay(bytes(data),{},60,[])
 def test_minimal_native_extra_pump_drops_same_wall_clock_press(self):
  image,values=self.inputs();events=[(20,True,False),(40,False,False)]
  old30=tool.run_case(image,values,30,events,duration=100)
  old60=tool.run_case(image,values,60,events,duration=100)
  self.assertEqual(old30['native_handler_calls'],1);self.assertEqual(old60['native_handler_calls'],0)
  self.assertEqual(old30['interval'],33);self.assertEqual(old60['interval'],33)
  self.assertEqual([m['time'] for m in old60['messages']],[33,50])
  self.assertFalse(old60['commercial_dll_loaded']);self.assertFalse(old60['game_started'])
 def test_compiled_production_latch_restores_native_three_hit_records(self):
  image,values=self.inputs();bridge=self.bridge()
  report=tool.verify(image,values,bridge)
  triple=report['triple']
  self.assertEqual([r['native_handler_calls'] for r in triple],[3,1,3])
  self.assertEqual(triple[0]['recorded'],[0,11,22]);self.assertEqual(triple[2]['recorded'],[0,11,22])
  self.assertEqual([s['id'] for s in triple[2]['sounds']],[0x237]*3)
  self.assertTrue(report['owned_latch_bridge_loaded']);self.assertFalse(report['commercial_dll_loaded'])
 def test_instruction_budget_is_enforced(self):
  image,values=self.inputs();q=tool.QueueReplay(image,values,60,[])
  with self.assertRaisesRegex(ValueError,'instruction budget/stop failure'):
   q.run(tool.BASE+0x8aeac,tool.BASE+0x8aec1,budget=1)
 def test_duration_and_rate_bounds(self):
  for rate,duration in [(0,100),(30,99),(60,5000)]:
   with self.assertRaises(ValueError):tool.run_case(b'',{},rate,[],duration=duration)

if __name__=='__main__':unittest.main()
