import struct,subprocess,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EXE=ROOT/'build/native/Release/bone_pose_audit.exe'
@unittest.skipUnless(EXE.is_file(),'Build bone_pose_audit first')
class NativePoseAuditTests(unittest.TestCase):
 def data(self):
  m=[0.]*16
  m[0]=2.;m[5]=.5;m[10]=1.5;m[4]=.25;m[15]=1.
  return struct.pack('<5I',0,2,1,2,1)+struct.pack('<16f',*m)*3+struct.pack('<2I',0xcccccccc,0)
 def run_audit(self,data=None):
  with tempfile.TemporaryDirectory() as d:
   if data is not None:(Path(d)/'0001.ani').write_bytes(data)
   return subprocess.run([str(EXE),d],capture_output=True,text=True)
 def test_scaled_native_pose_accepted_without_export(self):
  p=self.run_audit(self.data());self.assertEqual(p.returncode,0,p.stderr)
  self.assertIn('files=1 matrices=2 old_accepted=0 new_accepted=2 pairs=1',p.stdout)
 def test_truncated_matrix_rejected(self):
  self.assertNotEqual(self.run_audit(self.data()[:50]).returncode,0)
 def test_metadata_truncation_and_bad_children_rejected(self):
  for data in [self.data()[:-1],self.data()[:-8]+struct.pack('<3I',0,1,1),self.data()+b'x']:
   self.assertNotEqual(self.run_audit(data).returncode,0)
 def test_nonfinite_pose_rejected(self):
  data=bytearray(self.data());struct.pack_into('<f',data,20,float('nan'))
  self.assertNotEqual(self.run_audit(data).returncode,0)
 def test_no_inputs_rejected(self):
  self.assertNotEqual(self.run_audit().returncode,0)
