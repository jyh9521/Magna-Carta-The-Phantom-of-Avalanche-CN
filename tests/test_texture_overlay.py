import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import prepare_texture_overlay as tool
class OverlayTests(unittest.TestCase):
 def test_isolated_runtime(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);game=root/'game';prior=game/'.advanced-runtime';prior.mkdir(parents=True);native=root/'native';native.mkdir()
   for n in ['StartEnhanced.ps1','EnhancementSettings.psm1','manifest.json','title-background.json','workspace_profile.dll','workspace_launcher.exe']:(prior/n).write_bytes(b'original')
   for n in ['workspace_profile.dll','workspace_launcher.exe']:(native/n).write_bytes(b'modified')
   out=root/'overlay';lock=tool.prepare(game,native,out)
   self.assertEqual((prior/'workspace_profile.dll').read_bytes(),b'original');self.assertEqual((out/'workspace_profile.dll').read_bytes(),b'modified')
   self.assertIn('-WithoutTextureGuard',(out/'Play-without-texture-guard.cmd').read_text());self.assertEqual(len(lock['inputs']),8)
   s=(out/'Start.ps1').read_text(encoding='utf-8-sig');self.assertIn('-SettingsFile $SettingsFile',s);self.assertIn('MC_TITLE_BACKGROUND4K',s)
   self.assertRaises(ValueError,tool.prepare,game,native,out)
 def test_missing_trial(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);self.assertRaises(ValueError,tool.prepare,r,r,r/'out')
