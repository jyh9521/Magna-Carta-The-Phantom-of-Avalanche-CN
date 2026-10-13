"""Read version-1.4 WRD geometry from the verified native loader layout.
Read-only; unknown versions and malformed ranges are rejected. Raw model XY
is a research preview, not a verified walkable/navigation map.
"""
import argparse,hashlib,json,math,struct
from pathlib import Path
VERSION=b'MC File Version 1.400000\0'
class Reader:
 def __init__(self,data):self.data=data;self.pos=0
 def take(self,n):
  if n<0 or self.pos+n>len(self.data):raise ValueError(f'Truncated WRD at {self.pos}: {n} bytes')
  v=memoryview(self.data)[self.pos:self.pos+n];self.pos+=n;return v
 def u(self):return struct.unpack('<I',self.take(4))[0]
 def count(self,limit=1000000):
  n=self.u()
  if n>limit:raise ValueError(f'WRD count exceeds limit at {self.pos-4}')
  return n

def parse(data):
 r=Reader(data);header=bytes(r.take(0x108))
 if not header.startswith(VERSION):raise ValueError('Unsupported WRD version; expected 1.400000')
 texture_count=struct.unpack_from('<I',header,0x104)[0]
 if texture_count>4096:raise ValueError('Too many WRD textures')
 texture_ids=[]
 for _ in range(texture_count):
  texture_ids.append(r.u());dimension=r.count(4096);materials=r.count(100000)
  r.take(materials*28);r.take(dimension*dimension*3)
 r.take(256);groups=r.count(65536);meshes=[];instances=[];triangle_total=0
 for group in range(groups):
  part_count=r.count(65536);part_metadata=bytes(r.take(part_count*12))
  for part in range(part_count):
   vertices=r.count();kind=r.u();stride=r.count(4096);native_buffer=r.u();material_base=r.u();polygons=r.count(100000)
   if stride!=28:raise ValueError(f'Unsupported vertex stride: {stride}')
   raw=r.take(vertices*stride);points=[struct.unpack_from('<3f',raw,i*stride) for i in range(vertices)]
   if any(not all(math.isfinite(v) and abs(v)<1e8 for v in point) for point in points):raise ValueError('Invalid vertex coordinate')
   triangles=[]
   for polygon in range(polygons):
    r.take(76);faces=r.count()
    if faces:
     r.u();r.take(texture_ids.count(material_base+polygon)*4)
     indices=r.take(faces*6)
     for i in range(faces):
      tri=struct.unpack_from('<3H',indices,i*6)
      if any(v>=vertices for v in tri):raise ValueError('Triangle index outside vertex array')
      triangles.append(tri)
   triangle_total+=len(triangles)
   meshes.append(dict(group=group,part=part,kind=kind,material_base=material_base,points=points,triangles=triangles))
  animation_flags=r.u();animation_type=r.u();frames=r.count(100000);bones=r.count(65536);tracks=[]
  for _ in range(bones):
   index=r.u();refs=r.count(65536);references=list(struct.unpack('<'+'I'*refs,r.take(refs*4)))
   first=list(struct.unpack('<16f',r.take(64)));r.take(frames*64)
   if any(not math.isfinite(x) for x in first):raise ValueError('Nonfinite instance matrix')
   tracks.append(dict(index=index,references=references,first_matrix=first))
  instances.append(dict(group=group,metadata_hex=part_metadata.hex(),animation_flags=animation_flags,animation_type=animation_type,frames=frames,tracks=tracks))
 pairs=r.count();r.take(pairs*8);matrices=r.count();r.take(matrices*64);r.take(16)
 if r.pos!=len(data):raise ValueError(f'Unexpected WRD trailing data: {len(data)-r.pos}')
 points=[p for m in meshes for p in m['points']]
 bounds=[min(p[k] for p in points) for k in range(3)]+[max(p[k] for p in points) for k in range(3)] if points else None
 return dict(schema=1,version='1.400000',sha256=hashlib.sha256(data).hexdigest(),size=len(data),consumed=r.pos,groups=groups,texture_count=texture_count,vertices=len(points),triangles=triangle_total,raw_bounds=bounds,meshes=meshes,instances=instances,navigation_verified=False)

def preview_svg(result,width=1200,height=900):
 b=result['raw_bounds']
 if not b:raise ValueError('No geometry for preview')
 scale=min((width-48)/max(b[3]-b[0],1),(height-96)/max(b[4]-b[1],1))
 def xy(p):return (24+(p[0]-b[0])*scale,height-24-(p[1]-b[1])*scale)
 rows=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',f'<rect width="{width}" height="{height}" fill="#111b22"/>','<text x="24" y="30" fill="#e5dcba" font-size="18">WRD raw geometry / XY / not a navigation map</text>']
 for m in result['meshes']:
  for tri in m['triangles']:
   pts=' '.join(f'{x:.2f},{y:.2f}' for x,y in (xy(m['points'][i]) for i in tri))
   rows.append(f'<polygon points="{pts}" fill="#375660" fill-opacity=".08" stroke="#94aaa5" stroke-opacity=".25" stroke-width=".5"/>')
 rows.append('</svg>');return '\n'.join(rows)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--preview',type=Path);a=p.parse_args()
 result=parse(a.input.read_bytes());a.output.parent.mkdir(parents=True,exist_ok=True)
 a.output.write_text(json.dumps({k:v for k,v in result.items() if k!='meshes'},indent=2),encoding='utf8')
 if a.preview:a.preview.write_text(preview_svg(result),encoding='utf8')
 print(f"WRD_GEOMETRY PASS vertices={result['vertices']} triangles={result['triangles']} consumed={result['consumed']} read_only=true navigation_verified=false")
