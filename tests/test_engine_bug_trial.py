import sys,tempfile,unittest,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import prepare_engine_bug_trial as trial
ROOT=Path(__file__).resolve().parents[1]
class EngineBugTrial(unittest.TestCase):
 def test_guard_is_opt_in(self):
  with tempfile.TemporaryDirectory() as d:
   r=Path(d);runtime=r/'.advanced-runtime';runtime.mkdir()
   for n in ['StartTitle.ps1','StartAdvanced.ps1','manifest.json','title-background.json','workspace_profile.dll','workspace_launcher.exe']:(runtime/n).write_bytes(b'fixture')
   trial.write_entrypoints(r,ROOT/'locales/zh-CN')
   s=(runtime/'StartEngineBug.ps1').read_text(encoding='utf-8-sig')
   self.assertIn('[switch]$TextureLifetime',s);self.assertIn("if($TextureLifetime){$arguments+='--texture-lifetime'}",s)
   self.assertIn('-TextureLifetime',(r/'Play-texture-guard.cmd').read_text())
   self.assertNotIn('-TextureLifetime',(r/'Play-without-texture-guard.cmd').read_text())
 def test_driver_hook_composes_before_display(self):
  s=(ROOT/'src/runtime/workspace_profile.cpp').read_text(encoding='utf8')
  self.assertLess(s.index('installCurrentTextureLifetime(module'),s.index('if((wideDisplay||render60)&&!_wcsicmp(base,L"AsrD3DDrv.dll"))'))
  self.assertIn('TEXTURE_LIFETIME_REJECTED\");ExitProcess(125)',s)
 def test_current_guard_has_no_bind_cache(self):
  s=(ROOT/'src/runtime/current_texture_lifetime.cpp').read_text()
  self.assertIn('GetTexture(stage,&bound)',s);self.assertIn('bound->Release()',s)
  self.assertNotIn('states[32]',s);self.assertIn('0x104ea0',s);self.assertIn('InterlockedCompareExchange',s)
