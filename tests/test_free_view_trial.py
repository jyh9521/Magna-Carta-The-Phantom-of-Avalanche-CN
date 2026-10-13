import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import prepare_free_view_trial as trial

class FreeViewTrial(unittest.TestCase):
 def test_explicit_candidate_keeps_original_settings(self):
  with tempfile.TemporaryDirectory() as directory:
   r=Path(directory);game=r/'game';prior=game/'.advanced-runtime';prior.mkdir(parents=True);native=r/'native';native.mkdir()
   for name in ['StartEnhanced.ps1','EnhancementSettings.psm1','manifest.json','title-background.json','workspace_profile.dll','workspace_launcher.exe']:(prior/name).write_bytes(b'baseline')
   (prior/'enhancements.json').write_bytes(b'original settings')
   for name in ['workspace_profile.dll','workspace_launcher.exe']:(native/name).write_bytes(b'new runtime')
   output=r/'candidate';trial.prepare(game,native,output)
   s=(output/'StartFreeView.ps1').read_text(encoding='utf-8-sig')
   self.assertIn("$settings.display_profile='combined';$settings.motion60=$true",s)
   self.assertIn('$WithoutTextureGuard=$true',s);self.assertIn('$env:MC_FREE_VIEW=$oldFree',s)
   self.assertEqual((prior/'enhancements.json').read_bytes(),b'original settings')
   self.assertIn('-WithoutFreeView',(output/'Play-without-free-view.cmd').read_text())
 def test_foreground_and_identity_guards(self):
  root=Path(__file__).resolve().parents[1]
  s=(root/'src/runtime/motion60.cpp').read_text(encoding='utf8')
  self.assertIn('foregroundPid!=GetCurrentProcessId()',s);self.assertIn('freeGeneration!=phase.generation',s)
  self.assertIn('VK_CONTROL',s);self.assertIn('VK_MENU',s)
