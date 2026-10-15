import sys,struct,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from resource_wrd import parse,preview_svg,VERSION

def sample():
 h=bytearray(0x108);h[:len(VERSION)]=VERSION
 b=bytes(h)+bytes(256)+struct.pack('<I',1)+struct.pack('<I',1)+bytes(12)
 b+=struct.pack('<6I',3,1,28,0,0,1)
 for v in [(0,0,0),(1,0,0),(0,1,0)]:b+=struct.pack('<3f',*v)+bytes(16)
 b+=bytes(76)+struct.pack('<II3H',1,0,0,1,2)
 b+=struct.pack('<4I',0,0,0,0)+struct.pack('<II',0,0)+bytes(16)
 return b
class WrdTests(unittest.TestCase):
 def test_layout(self):
  b=sample();r=parse(b);self.assertEqual(r['consumed'],len(b));self.assertEqual((r['vertices'],r['triangles']),(3,1));self.assertFalse(r['navigation_verified'])
 def test_unknown_version(self):
  b=sample().replace(b'1.400000',b'1.500000');self.assertRaisesRegex(ValueError,'Unsupported WRD',parse,b)
 def test_legacy_same_native_layout_preserves_actual_version_and_hash(self):
  import hashlib
  b=sample().replace(b'1.400000',b'1.300000');r=parse(b)
  self.assertEqual(r['version'],'1.300000');self.assertEqual(r['sha256'],hashlib.sha256(b).hexdigest())
  self.assertEqual(r['consumed'],len(b));self.assertEqual((r['vertices'],r['triangles']),(3,1))
 def test_legacy_still_rejects_malformed_indices(self):
  b=bytearray(sample().replace(b'1.400000',b'1.300000'));off=0x108+256+8+12+24+84+76+8;struct.pack_into('<H',b,off,3)
  self.assertRaisesRegex(ValueError,'index',parse,bytes(b))
 def test_truncated(self):
  for n in [0,263,len(sample())-1]:self.assertRaises(ValueError,parse,sample()[:n])
 def test_extra_data(self):self.assertRaisesRegex(ValueError,'trailing',parse,sample()+b'x')
 def test_stride(self):
  b=bytearray(sample());struct.pack_into('<I',b,0x108+256+8+12+8,32);self.assertRaisesRegex(ValueError,'stride',parse,bytes(b))
 def test_bad_index(self):
  b=bytearray(sample());off=0x108+256+8+12+24+84+76+8;struct.pack_into('<H',b,off,3);self.assertRaisesRegex(ValueError,'index',parse,bytes(b))
 def test_nonfinite(self):
  b=bytearray(sample());struct.pack_into('<f',b,0x108+256+8+12+24,float('nan'));self.assertRaisesRegex(ValueError,'coordinate',parse,bytes(b))
 def test_preview(self):self.assertIn('not a navigation map',preview_svg(parse(sample())));self.assertIn('<polygon',preview_svg(parse(sample())))
