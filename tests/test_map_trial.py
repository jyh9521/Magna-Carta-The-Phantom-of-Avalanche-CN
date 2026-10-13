import sys,tempfile,unittest,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import prepare_map_trial as trial
class MapTrial(unittest.TestCase):
 def test_wrapper_is_explicit_and_preserves_settings(self):
  with tempfile.TemporaryDirectory() as directory:
   r=Path(directory);game=r/'game';prior=game/'.advanced-runtime';prior.mkdir(parents=True);native=r/'native';native.mkdir();atlas=r/'atlas';atlas.mkdir();locale=r/'locale';locale.mkdir()
   for name in ['StartEnhanced.ps1','EnhancementSettings.psm1','manifest.json','title-background.json','workspace_profile.dll','workspace_launcher.exe']:(prior/name).write_bytes(b'baseline')
   for name in ['workspace_profile.dll','workspace_launcher.exe']:(native/name).write_bytes(b'candidate')
   (atlas/'manifest.json').write_text(json.dumps(dict(schema=1,projection='first_instance_frame_column_major_XY',navigation_verified=False,accepted=[],rejected=[])))
   (locale/'map-ui.json').write_text(json.dumps(dict(map_title='Terrain map')))
   output=r/'candidate';lock=trial.prepare(game,native,atlas,locale,output)
   s=(output/'StartMap.ps1').read_text(encoding='utf-8-sig');self.assertIn('$WithoutTextureGuard=$true',s);self.assertIn("$env:MC_FREE_VIEW='0'",s);self.assertIn('$env:MC_MAP_OVERLAY=$oldMap',s)
   self.assertEqual((prior/'workspace_profile.dll').read_bytes(),b'baseline');self.assertIn('-WithoutMap',(output/'Play-without-maps.cmd').read_text())
 def test_read_only_source_bindings(self):
  root=Path(__file__).resolve().parents[1];s=(root/'src/runtime/map_overlay.cpp').read_text(encoding='utf8')
  self.assertIn('scene+0x10d0',s);self.assertIn('actor+0x154',s);self.assertIn('sameMap&&controlled',s);self.assertIn('WS_EX_NOACTIVATE',s);self.assertIn('SWP_NOACTIVATE',s);self.assertNotIn('SetForegroundWindow(',s);self.assertNotIn('SetCursorPos(',s)
