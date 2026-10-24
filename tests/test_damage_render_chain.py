"""Actual-PE damage chain tests; no commercial module is loaded or launched."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
DEPENDENCIES=all(importlib.util.find_spec(n) is not None for n in ('unicorn','pefile'))
if DEPENDENCIES:
 from replay_damage_render_chain import DamageReplay,run_chain,report_destination

DATA=ROOT/'runtime/data'
BRIDGE=ROOT/'build/native/Release/damage-render-fixture/damage_projection_bridge.exe'
READY=DEPENDENCIES and (DATA/'MCAlpha.dll').is_file() and (DATA/'ASURA.dll').is_file()

@unittest.skipUnless(DEPENDENCIES,'Install documented Unicorn/pefile offline replay dependencies')
class GuardTests(unittest.TestCase):
 def test_complete_engine_hash_rejects_unknown(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'MCAlpha.dll').write_bytes(b'unsupported')
   with self.assertRaisesRegex(ValueError,'engine identity'):DamageReplay(p)
 def test_report_rejects_existing_and_resource_alias(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);source=p/'source';source.mkdir();original=source/'file.bin';original.write_bytes(b'unchanged')
   with self.assertRaisesRegex(ValueError,'outside resource'):report_destination(source,source/'new.json')
   with self.assertRaisesRegex(ValueError,'outside resource'):report_destination(source,original)
   alias=p/'alias.json'
   try:alias.hardlink_to(original)
   except OSError:pass
   else:
    with self.assertRaisesRegex(ValueError,'outside resource'):report_destination(source,alias)
   self.assertEqual(original.read_bytes(),b'unchanged')

@unittest.skipUnless(READY,'Supply supported original runtime and offline replay dependencies')
class NativeResourceTests(unittest.TestCase):
 def test_driver_complete_hash_rejects_unknown(self):
  q=DamageReplay(DATA)
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'Drv').mkdir();(p/'Drv/AsrD3DDrv.dll').write_bytes(b'unknown');q.data=p
   with self.assertRaisesRegex(ValueError,'driver identity'):q.setup_driver()
 def test_actual_resource_reader_enemy_head(self):
  q=DamageReplay(DATA);manager=q.hooks.allocate(0x40);q.call(0x1aa0,manager+4);q.call(0xb216c,manager,0)
  row=q.call(0xb3854,manager,7)
  self.assertNotEqual(row,0)
  self.assertEqual(q.read(row+4),7)
  self.assertGreater(q.steps,100000)
  self.assertTrue(all(offset==len(data) for data,offset in q.fdihandles.values()))

@unittest.skipUnless(READY and BRIDGE.is_file(),'Build documented damage-render-fixture CMake target before full native chain replay')
class NativeDamageDrawTests(unittest.TestCase):
 def test_native_parent_skip_and_heal_at_widescreen(self):
  for flags in [(1,0),(0,1)]:
   case=run_chain(DATA,BRIDGE,1067,600,318,72,'heal',hidden=True,parented=True,parent_flags=flags)
   self.assertEqual(case['frames'][0]['number_position'][:2],case['native_screen'])
 def test_both_original_numeric_damage_producer_blocks(self):
  for route in (0,1):
   for flags in [(0,0),(1,0),(0,1)]:
    with self.subTest(route=route,flags=flags):
     case=run_chain(DATA,BRIDGE,damage=318,hidden=True,spatial_flags=flags,producer_route=route)
     self.assertEqual(case['frames'][0]['number_position'][:2],case['native_screen'])
 def test_native_spatial_skip_matches_visible_draw_for_hidden_damage(self):
  for flags in [(1,0),(0,1),(1,1),(2,0)]:
   with self.subTest(flags=flags):
    case=run_chain(DATA,BRIDGE,damage=318,hidden=True,spatial_flags=flags)
    self.assertEqual(case['frames'][0]['number_position'][:2],case['native_screen'])
 def test_hidden_skill_damage_origin_and_parent_transform(self):
  for width,height,parented,stale in [(800,600,False,False),(1067,600,True,False),(853,480,True,True),(640,480,False,True)]:
   with self.subTest(width=width,parented=parented,stale=stale):
    case=run_chain(DATA,BRIDGE,width,height,1706,hidden=True,parented=parented,stale=stale)
    self.assertEqual(case['frames'][0]['number_position'][:2],case['native_screen'])
    self.assertEqual(len(case['frames'][0]['draws']),4)
 def test_hidden_heal_uses_fresh_anchor_too(self):
  case=run_chain(DATA,BRIDGE,800,600,12345,72,'heal',hidden=True)
  self.assertEqual(case['frames'][0]['number_position'][:2],case['native_screen'])
 def test_hidden_rotated_scaled_parent_and_secondary_transform(self):
  case=run_chain(DATA,BRIDGE,damage=1706,hidden=True,parented=True,transformed=True)
  self.assertEqual(case['frames'][0]['number_position'][:2],case['native_screen'])
 def test_hidden_negative_control_reproduces_top_left(self):
  with self.assertRaisesRegex(ValueError,r'Hidden popup origin actual=\[0.0, 0.0\]'):
   run_chain(DATA,BRIDGE,damage=1706,hidden=True,fresh_anchor=False)
 def test_hidden_explicit_rollback_restores_top_left(self):
  with self.assertRaisesRegex(ValueError,r'Hidden popup origin actual=\[0.0, 0.0\]'):
   run_chain(DATA,BRIDGE,damage=1706,hidden=True,anchor_options=('--rollback',))
 def test_four_logical_canvases(self):
  for width,height in [(640,480),(800,600),(853,480),(1067,600)]:
   with self.subTest(width=width):
    case=run_chain(DATA,BRIDGE,width,height)
    self.assertEqual(case['head_anchor'],[0,0,40])
    self.assertTrue(case['raster'][0]['result']['hook_enabled'])
    self.assertTrue(case['raster'][0]['result']['installer_ready'])
    self.assertEqual(len(case['frames'][0]['draws']),3)
    self.assertNotEqual(case['native_screen'],[0,0])
    self.assertEqual(case['frames'][0]['number_position'][:2],case['native_screen'])
    self.assertEqual(case['frames'][0]['flush_entry_driver_modelview'],[float(i%5==0) for i in range(16)])
 def test_native_heal_resources_and_different_enemy_height(self):
  case=run_chain(DATA,BRIDGE,800,600,12345,72,'heal')
  self.assertEqual(case['head_anchor'],[0,0,70])
  self.assertEqual([d['args'][6]-1 for d in case['frames'][0]['draws']],[205,206,207,208,209])
 def test_third_enemy_height_and_digits(self):
  case=run_chain(DATA,BRIDGE,1067,600,98,82,'damage')
  self.assertEqual(case['head_anchor'],[0,0,60])
  self.assertEqual([d['args'][6]-1 for d in case['frames'][0]['draws']],[203,202])

if __name__=='__main__':unittest.main()
