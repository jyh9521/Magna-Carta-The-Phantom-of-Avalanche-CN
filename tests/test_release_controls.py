import hashlib,json,shutil,struct,subprocess,sys,tempfile,unittest,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import update_release_controls as deploy
import build_release_controls_update as package

class ReleaseControlsTests(unittest.TestCase):
 def fixture(self,d):
  root=d/'runtime';root.mkdir();files={}
  for n in (*deploy.MODULES,*[n for n in deploy.SOURCE if n!='config/encounter-ui.json']):
   p=root/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(('old-owned:'+n).encode());files[n]=hashlib.sha256(p.read_bytes()).hexdigest()
  (root/'runtime.json').write_text(json.dumps(dict(schema=1,files=files,data={})))
  (root/'config/enhancements.json').write_bytes(b'{"schema":2,"native_gamepad":true,"free_view":true}')
  (root/'data').mkdir();(root/'data/MC00.sav').write_bytes(b'user save')
  module=d/'module.dll';raw=bytearray(512);raw[:2]=b'MZ';struct.pack_into('<I',raw,0x3c,0x80);raw[0x80:0x84]=b'PE\0\0';struct.pack_into('<H',raw,0x84,0x14c);struct.pack_into('<H',raw,0x96,0x2000);struct.pack_into('<H',raw,0x98,0x10b);module.write_bytes(raw)
  return root,module
 def test_deployment_rollback_exact_and_protected_bytes(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);root,module=self.fixture(d);before={p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}
   deploy.apply(root,module,d/'record');self.assertEqual((root/'config/enhancements.json').read_bytes(),before['config/enhancements.json'])
   self.assertEqual(json.loads((root/'runtime.json').read_text())['archived_features'],['native_gamepad','free_view'])
   deploy.rollback(root,d/'record');self.assertEqual(before,{p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()})
 def test_foreign_rollback_and_preflight_are_atomic(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);root,module=self.fixture(d);deploy.apply(root,module,d/'record');(root/deploy.MODULES[0]).write_bytes(b'foreign')
   before={p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}
   with self.assertRaises(ValueError):deploy.rollback(root,d/'record')
   with self.assertRaises(ValueError):deploy.apply(root,module,d/'record2')
   self.assertEqual(before,{p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()})
 def test_delivered_updater_baseline_modified_repeat_rollback(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);root,module=self.fixture(d);deploy.apply(root,module,d/'record');package.build(root,d/'record',d/'update.zip')
   deploy.rollback(root,d/'record');before={p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}
   with zipfile.ZipFile(d/'update.zip') as z:z.extractall(d/'package')
   script=d/'package'/package.FOLDER/'Update.ps1'
   def run(action,expected=0):
    r=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(script),'-Action',action,'-Runtime',str(root)],capture_output=True,text=True,timeout=30)
    self.assertEqual(r.returncode,expected,r.stdout+r.stderr);return r
   self.assertIn('BASELINE PASS files=19',run('Verify').stdout)
   self.assertIn('MODIFIED PASS files=19',run('Install').stdout);run('Install');run('CheckInstalled')
   (root/deploy.MODULES[0]).write_bytes(b'foreign');snapshot=(root/'runtime.json').read_bytes();run('Rollback',1);self.assertEqual(snapshot,(root/'runtime.json').read_bytes());(root/deploy.MODULES[0]).write_bytes(module.read_bytes())
   self.assertIn('ROLLBACK PASS files=19',run('Rollback').stdout)
   for n,b in before.items():self.assertEqual((root/n).read_bytes(),b,n)
   self.assertFalse((root/'config/encounter-ui.json').exists())
 def test_release_ui_has_no_archived_choices(self):
  x=(ROOT/'src/configuration/Configure.xaml').read_text(encoding='utf-8-sig')
  self.assertNotIn('GamepadChoices',x);self.assertNotIn('CameraChoices',x)
  ui=(ROOT/'src/configuration/Configure.ps1').read_text(encoding='utf-8-sig')
  self.assertIn('$settings=Convert-EnhancementSettings (Read-EnhancementSettings $SettingsFile)',ui)
  s=(ROOT/'src/configuration/StartShared.ps1').read_text(encoding='utf-8-sig')
  self.assertIn('$settings.native_gamepad=$false;$settings.free_view=$false',s)
  cpp=(ROOT/'src/runtime/workspace_profile.cpp').read_text()
  self.assertGreater(cpp.index('modernInput=false;cameraInput=false'),cpp.index('modernInput = GetEnvironmentVariableW'))
 def test_locale_labels_are_separate(self):
  self.assertEqual(set(json.loads((ROOT/'locales/zh-CN/encounter-ui.json').read_text(encoding='utf8'))),{'on','off'})
  self.assertNotIn('随机遇敌',(ROOT/'src/runtime/encounter_control.cpp').read_text())
 def test_full_refresh_filters_archived_entries_and_rejects_data_drift(self):
  from unittest.mock import patch
  import refresh_player_package as refresh
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);root=d/'runtime';(root/'data').mkdir(parents=True);(root/'config').mkdir()
   raw=b'owned changed resource';(root/'data/sample.bin').write_bytes(raw)
   (root/'runtime.json').write_text(json.dumps(dict(schema=1,files={'Play-camera.cmd':hashlib.sha256(b'archived entry').hexdigest()},data={},recipes={'camera':{},'gamepad':{},'configured':{}})))
   (root/'Configure.cmd').write_bytes(b'owned config');(root/'Play.cmd').write_bytes(b'owned play');(root/'Play-camera.cmd').write_bytes(b'archived entry')
   (root/'config/enhancements.json').write_text('{}')
   delta=b'MCD1'+struct.pack('<Q',len(raw))+struct.pack('<QI',0,len(raw))+raw
   manifest=dict(schema=1,source_files={'sample.bin':'source fixture'},changes=[dict(resource='sample.bin',target_sha256=hashlib.sha256(raw).hexdigest(),patch='sample.mcd',patch_sha256=hashlib.sha256(delta).hexdigest())])
   previous=d/'old.zip'
   with zipfile.ZipFile(previous,'w') as z:
    for n,b in {'package.json':json.dumps(manifest).encode(),'sample.mcd':delta,'payload/data/ddraw.dll':b'owned compatibility fixture','payload/data/DDrawCompat-MagnaCarta.ini':b'owned profile fixture','payload/Play-camera.cmd':b'archived entry','README.txt':b'old readme'}.items():z.writestr(n,b)
   old=previous.read_bytes();digest=hashlib.sha256(old).hexdigest()
   with patch.object(refresh,'validate_engine_fixes',return_value={}):refresh.refresh(previous,digest,root,d/'new.zip')
   with zipfile.ZipFile(d/'new.zip') as z:
    self.assertNotIn('payload/Play-camera.cmd',z.namelist());self.assertEqual(z.read('sample.mcd'),delta)
    m=json.loads(z.read('payload/runtime.json'));self.assertEqual(m['recipes'],{'configured':{}});self.assertNotIn('Play-camera.cmd',m['files'])
    self.assertFalse(json.loads(z.read('payload/config/enhancements.json'))['native_gamepad'])
   (root/'data/sample.bin').write_bytes(b'drift')
   with patch.object(refresh,'validate_engine_fixes',return_value={}):
    with self.assertRaises(ValueError):refresh.refresh(previous,digest,root,d/'rejected.zip')
   self.assertEqual(previous.read_bytes(),old);self.assertFalse((d/'rejected.zip').exists())
 @unittest.skipUnless((ROOT/'build/native/Release/encounter_control_fixture.exe').exists(),'Build native fixtures')
 def test_production_encounter_hook_and_HUD(self):
  r=subprocess.run([str(ROOT/'build/native/Release/encounter_control_fixture.exe')],capture_output=True,text=True,timeout=15);self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertIn('rollback=exact',r.stdout)
 @unittest.skipUnless((ROOT/'build/native/Release/native_actor_motion_fixture.exe').exists(),'Build native fixtures')
 def test_native_actor_midpoints(self):
  r=subprocess.run([str(ROOT/'build/native/Release/native_actor_motion_fixture.exe')],capture_output=True,text=True,timeout=15);self.assertEqual(r.returncode,0,r.stdout+r.stderr);self.assertIn('base_skin=interpolated base_rigid=interpolated',r.stdout)
if __name__=='__main__':unittest.main()
