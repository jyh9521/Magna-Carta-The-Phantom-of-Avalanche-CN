import sys,unittest,struct,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from build_map_atlas import project_scene,raster,build

def sample():
 return dict(meshes=[dict(group=0,points=[(0,0,0),(1,0,0),(0,1,0)],triangles=[(0,1,2)])],instances=[dict(group=0,tracks=[dict(first_matrix=[2,0,0,0,0,3,0,0,0,0,1,0,10,20,0,1])])])
class MapAtlasTests(unittest.TestCase):
 def test_scaled_translated_instance(self):
  data=sample();meshes,bounds=project_scene(data)
  self.assertEqual(meshes[0]['points'],[(10,20,0),(12,20,0),(10,23,0)]);self.assertEqual(bounds,[10,20,12,23])
  self.assertEqual(data['meshes'][0]['points'][0],(0,0,0))
 def test_missing_association(self):
  d=sample();d['instances'][0]['tracks']=[];self.assertRaisesRegex(ValueError,'association',project_scene,d)
 def test_non_affine(self):
  d=sample();d['instances'][0]['tracks'][0]['first_matrix'][3]=1;self.assertRaisesRegex(ValueError,'affine',project_scene,d)
 def test_nonfinite(self):
  d=sample();d['instances'][0]['tracks'][0]['first_matrix'][0]=float('inf');self.assertRaisesRegex(ValueError,'matrix',project_scene,d)
 def test_raster_size_and_viewport(self):
  m,b=project_scene(sample());image,viewport=raster(m,b,128);self.assertEqual(image.size,(128,128));self.assertGreater(viewport[2],0);self.assertRaises(ValueError,raster,m,b,1)
 def test_incremental_legacy_atlas_preserves_version(self):
  from test_resource_wrd import sample as wrd_sample
  identity=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]
  b=wrd_sample()[:-40]+struct.pack('<4I',0,0,0,1)+struct.pack('<II16f',0,0,*identity)+struct.pack('<II',0,0)+bytes(16)
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);source=root/'source';source.mkdir();legacy=b.replace(b'1.400000',b'1.300000')
   (source/'0022.wrd').write_bytes(legacy);(source/'0031.wrd').write_bytes(b)
   result=build(source,root/'out',128,[22])
   self.assertEqual(result['selected_ids'],[22]);self.assertEqual(len(result['accepted']),1)
   self.assertEqual(result['accepted'][0]['source_version'],'1.300000');self.assertFalse((root/'out/0031.png').exists())
   self.assertEqual((source/'0022.wrd').read_bytes(),legacy)
 def test_incremental_missing_identifier_rejected_before_output(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);source=root/'source';source.mkdir()
   self.assertRaisesRegex(ValueError,'missing',build,source,root/'out',128,[9999]);self.assertFalse((root/'out').exists())
 def test_incremental_invalid_identifier_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);source=root/'source';source.mkdir()
   for value in [[],[-1],[10000],[True]]:self.assertRaisesRegex(ValueError,'identifiers',build,source,root/'out',128,value)
