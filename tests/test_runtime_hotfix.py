"""Exercise the actual PowerShell hotfix transaction using owned tiny files."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import build_runtime_hotfix as hotfix

@unittest.skipUnless(os.name=='nt','PowerShell transaction requires Windows')
class RuntimeHotfixTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name);self.runtime=self.root/'runtime';self.record=self.root/'record';self.target=self.root/'installed';self.output=self.root/'package'
  self.states={}
  for name in ['runtime.json']+['modules/'+n+'.dll' for n in ['display','modern','texture','camera','maps','input-diagnostics','motion-space','configuration']]:
   old=('owned old '+name).encode();new=('owned new '+name).encode()
   for base,data in [(self.record/'original',old),(self.target,old),(self.runtime,new)]:
    p=base/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
   self.states[name]={'before':hashlib.sha256(old).hexdigest(),'after':hashlib.sha256(new).hexdigest()}
  (self.record/'changes.json').write_text(json.dumps(self.states),encoding='utf8')
  data=b'owned opening fixture';self.data_name='FrameData/0001.fdi'
  for base in [self.runtime,self.target]:
   p=base/'data'/self.data_name;p.parent.mkdir(parents=True);p.write_bytes(data)
  self.metadata=self.root/'locale.json';self.metadata.write_text(json.dumps({'layouts':[{'sha256':{self.data_name:hashlib.sha256(data).hexdigest()}}]}),encoding='utf8')
  self.archive=hotfix.build(self.runtime,self.record,self.metadata,self.output)
  (self.target/'save.sav').write_bytes(b'keep save');(self.target/'settings.json').write_bytes(b'keep settings')
 def run_update(self,action):
  return subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(self.output/'Update.ps1'),'-Action',action,'-Target',str(self.target)],capture_output=True,text=True,timeout=30)
 def test_install_check_rollback_exact_and_preserves_saves(self):
  for action,token in [('Verify','HOTFIX_VERIFY PASS'),('Install','HOTFIX_INSTALL PASS'),('CheckInstalled','HOTFIX_CHECK PASS'),('Rollback','HOTFIX_ROLLBACK PASS')]:
   result=self.run_update(action);self.assertEqual(result.returncode,0,result.stdout+result.stderr);self.assertIn(token,result.stdout)
  for name,state in self.states.items():self.assertEqual(hotfix.sha(self.target/name),state['before'])
  self.assertEqual((self.target/'save.sav').read_bytes(),b'keep save');self.assertEqual((self.target/'settings.json').read_bytes(),b'keep settings')
 def test_unknown_input_rejected_before_any_write(self):
  (self.target/'modules/display.dll').write_bytes(b'unknown')
  before={n:(self.target/n).read_bytes() for n in self.states}
  result=self.run_update('Install');self.assertNotEqual(result.returncode,0)
  self.assertEqual(before,{n:(self.target/n).read_bytes() for n in self.states})
 def test_resource_drift_rejected_before_any_write(self):
  (self.target/'data'/self.data_name).write_bytes(b'drift')
  self.assertNotEqual(self.run_update('Install').returncode,0)
  for n,s in self.states.items():self.assertEqual(hotfix.sha(self.target/n),s['before'])
 def test_changed_after_install_blocks_rollback(self):
  self.assertEqual(self.run_update('Install').returncode,0)
  (self.target/'modules/maps.dll').write_bytes(b'newer work')
  before={n:(self.target/n).read_bytes() for n in self.states}
  self.assertNotEqual(self.run_update('Rollback').returncode,0)
  self.assertEqual(before,{n:(self.target/n).read_bytes() for n in self.states})
