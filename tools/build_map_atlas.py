"""Generate local first-frame terrain previews from version-locked WRD geometry.
No original game resources are modified. Geometry is not a walkability model.
"""
import argparse
import hashlib
import json
import math
import struct
from pathlib import Path
from resource_wrd import parse

def project_scene(result):
    meshes=[]
    for instance in result['instances']:
        group=[m for m in result['meshes'] if m['group']==instance['group']]
        if len(group)!=1 or len(instance['tracks'])!=1:
            raise ValueError('Unknown instance-to-mesh association')
        matrix=instance['tracks'][0]['first_matrix']
        if len(matrix)!=16 or any(not math.isfinite(v) for v in matrix):
            raise ValueError('Invalid instance matrix')
        if abs(matrix[3])+abs(matrix[7])+abs(matrix[11])+abs(matrix[15]-1)>.001:
            raise ValueError('Non-affine instance matrix')
        mesh=group[0];points=[]
        for point in mesh['points']:
            value=tuple(sum(matrix[c*4+r]*point[c] for c in range(3))+matrix[12+r] for r in range(3))
            if any(not math.isfinite(v) or abs(v)>1e9 for v in value):raise ValueError('Invalid projected position')
            points.append(value)
        meshes.append(dict(points=points,triangles=mesh['triangles']))
    points=[p for m in meshes for p in m['points']]
    if not points:raise ValueError('Empty map geometry')
    bounds=[min(p[k] for p in points) for k in range(2)]+[max(p[k] for p in points) for k in range(2)]
    if bounds[2]<=bounds[0] or bounds[3]<=bounds[1]:raise ValueError('Degenerate map bounds')
    return meshes,bounds

def raster(meshes,bounds,size):
    from PIL import Image,ImageDraw
    if size<128 or size>2048:raise ValueError('Atlas size outside supported range')
    image=Image.new('RGB',(size,size),(19,32,39));draw=ImageDraw.Draw(image)
    scale=min((size-24)/(bounds[2]-bounds[0]),(size-24)/(bounds[3]-bounds[1]))
    origin=((size-(bounds[2]-bounds[0])*scale)/2,(size-(bounds[3]-bounds[1])*scale)/2)
    def xy(p):return (origin[0]+(p[0]-bounds[0])*scale,size-origin[1]-(p[1]-bounds[1])*scale)
    triangles=[tuple(mesh['points'][i] for i in triangle) for mesh in meshes for triangle in mesh['triangles']]
    triangles.sort(key=lambda t:sum(p[2] for p in t))
    for triangle in triangles:
        points=[xy(p) for p in triangle]
        draw.polygon(points,fill=(65,86,84));draw.line(points+[points[0]],fill=(99,119,110),width=max(1,size//512))
    return image,(origin[0],origin[1],scale)

def build(source,output,size=512):
    source=source.resolve(strict=True);output=output.resolve()
    if output.exists() or output.is_relative_to(source) or source.is_relative_to(output):raise ValueError('New independent map asset directory required')
    output.mkdir(parents=True);accepted=[];rejected=[]
    for path in sorted(source.glob('*.wrd')):
        before=path.read_bytes();source_hash=hashlib.sha256(before).hexdigest()
        try:
            result=parse(before);meshes,bounds=project_scene(result);image,viewport=raster(meshes,bounds,size)
        except ValueError as error:
            rejected.append(dict(file=path.name,reason=str(error)));continue
        identifier=int(path.stem);png=output/f'{identifier:04d}.png';image.save(png)
        metadata=output/f'{identifier:04d}.map'
        metadata.write_bytes(struct.pack('<4sII7f',b'MCM1',size,size,*bounds,*viewport))
        if hashlib.sha256(path.read_bytes()).hexdigest()!=source_hash:raise ValueError('Source changed while generating map')
        accepted.append(dict(id=identifier,source_sha256=source_hash,png_sha256=hashlib.sha256(png.read_bytes()).hexdigest(),metadata_sha256=hashlib.sha256(metadata.read_bytes()).hexdigest(),bounds=bounds,vertices=result['vertices'],triangles=result['triangles']))
    manifest=dict(schema=1,size=size,projection='first_instance_frame_column_major_XY',navigation_verified=False,accepted=accepted,rejected=rejected,source_unchanged=True)
    (output/'manifest.json').write_bytes((json.dumps(manifest,indent=2)+'\n').encode('utf8'))
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--size',type=int,default=512);a=p.parse_args()
    result=build(a.source,a.output,a.size)
    print(f"MAP_ATLAS PASS accepted={len(result['accepted'])} rejected={len(result['rejected'])} source_unchanged=true navigation_verified=false")
