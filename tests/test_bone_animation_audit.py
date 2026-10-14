import math,struct,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import audit_bone_animation as tool

def matrix(scale=1):
 m=[0.]*16;m[0]=m[5]=m[10]=scale;m[15]=1;return m
def fixture():
 bind=matrix();reflected=matrix();reflected[0]=-1
 return struct.pack('<5I',0,2,1,2,1)+b''.join(struct.pack('<16f',*m) for m in [bind,reflected,matrix(2)])+struct.pack('<2I',0xcccccccc,0)
class BoneAuditTests(unittest.TestCase):
 def test_separate_bind_and_real_samples_no_pose_export(self):
  data=fixture();r=tool.parse(data)
  self.assertEqual(r['consumed'],len(data));self.assertEqual(r['bind']['accepted'],1)
  self.assertEqual(r['dynamic']['matrices'],2);self.assertEqual(r['dynamic']['accepted'],0)
  self.assertEqual(r['dynamic']['reflected'],1);self.assertEqual(r['dynamic']['stretch_shear'],1)
  self.assertEqual(r['dynamic']['mirrored_accepted'],1)
  self.assertNotIn('poses',r);self.assertEqual(data,fixture())
 def test_all_truncations_rejected(self):
  b=fixture()
  for n in range(len(b)):
   with self.assertRaises(ValueError):tool.parse(b[:n])
 def test_trailing_rejected(self):
  with self.assertRaises(ValueError):tool.parse(fixture()+b'x')
 def test_nonfinite_rejected(self):
  b=bytearray(fixture());struct.pack_into('<f',b,20,float('nan'))
  with self.assertRaises(ValueError):tool.parse(b)
 def test_bad_counts_and_frame_relation(self):
  for offset,value in [(8,0),(12,20),(16,513)]:
   b=bytearray(fixture());struct.pack_into('<I',b,offset,value)
   with self.assertRaises(ValueError):tool.parse(b)
 def test_child_reference_and_opaque_parent(self):
  b=fixture()[:-8]+struct.pack('<3I',0xcccccccc,1,1)
  with self.assertRaises(ValueError):tool.parse(b)
  b=bytearray(fixture());struct.pack_into('<I',b,0,1)
  self.assertEqual(tool.parse(b)['header']['opaque_tag'],1)
