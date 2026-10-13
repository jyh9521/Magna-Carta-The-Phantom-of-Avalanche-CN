import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from build_map_atlas import project_scene,raster

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
