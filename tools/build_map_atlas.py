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

def clip_at_height(triangle,height):
    if isinstance(height,bool) or not isinstance(height,(int,float)) or not math.isfinite(height) or abs(height)>1e9:
        raise ValueError('Invalid cutaway height')
    if len(triangle)!=3 or any(len(point)!=3 or not all(math.isfinite(v) for v in point) for point in triangle):
        raise ValueError('Invalid cutaway triangle')
    output=[]
    def append(point):
        if not output or output[-1]!=point:output.append(point)
    previous=tuple(triangle[-1]);previous_inside=previous[2]<=height
    for value in triangle:
        current=tuple(value);inside=current[2]<=height
        if inside!=previous_inside:
            if current[2]==height:intersection=current
            elif previous[2]==height:intersection=previous
            else:
                t=(height-previous[2])/(current[2]-previous[2])
                intersection=(previous[0]+t*(current[0]-previous[0]),previous[1]+t*(current[1]-previous[1]),float(height))
            append(intersection)
        if inside:append(current)
        previous,previous_inside=current,inside
    if len(output)>1 and output[0]==output[-1]:output.pop()
    return output if len(output)>=3 else []

def raster(meshes,bounds,size,clip_z_max=None):
    from PIL import Image,ImageDraw
    if size<128 or size>2048:raise ValueError('Atlas size outside supported range')
    image=Image.new('RGB',(size,size),(19,32,39));draw=ImageDraw.Draw(image)
    scale=min((size-24)/(bounds[2]-bounds[0]),(size-24)/(bounds[3]-bounds[1]))
    origin=((size-(bounds[2]-bounds[0])*scale)/2,(size-(bounds[3]-bounds[1])*scale)/2)
    def xy(p):return (origin[0]+(p[0]-bounds[0])*scale,size-origin[1]-(p[1]-bounds[1])*scale)
    triangles=[tuple(mesh['points'][i] for i in triangle) for mesh in meshes for triangle in mesh['triangles']]
    if clip_z_max is not None:
        # Clip only the rendering polygons. Full-scene bounds/viewport stay fixed.
        if not triangles:clip_at_height([(0,0,0)]*3,clip_z_max)
        triangles=[polygon for triangle in triangles if (polygon:=clip_at_height(triangle,clip_z_max))]
        if not triangles:raise ValueError('Cutaway removed all geometry; choose a higher plane')
    if clip_z_max is None:triangles.sort(key=lambda t:sum(p[2] for p in t))
    else:triangles.sort(key=lambda t:sum(p[2] for p in t)/len(t))
    for triangle in triangles:
        points=[xy(p) for p in triangle]
        draw.polygon(points,fill=(65,86,84));draw.line(points+[points[0]],fill=(99,119,110),width=max(1,size//512))
    return image,(origin[0],origin[1],scale)

def build(source,output,size=512,identifiers=None,clip_z_max=None):
    source=source.resolve(strict=True);output=output.resolve()
    if output.exists() or output.is_relative_to(source) or source.is_relative_to(output):raise ValueError('New independent map asset directory required')
    if clip_z_max is not None:clip_at_height([(0,0,0)]*3,clip_z_max)
    paths=sorted(source.glob('*.wrd'))
    selected=None
    if identifiers is not None:
        selected=set(identifiers)
        if not selected or any(isinstance(i,bool) or not isinstance(i,int) or not 0<=i<=9999 for i in selected):
            raise ValueError('Map identifiers must be nonempty integers from 0 to 9999')
        paths=[p for p in paths if p.stem.isdigit() and int(p.stem) in selected]
        if {int(p.stem) for p in paths} != selected:raise ValueError('Requested map identifiers are missing')
    output.mkdir(parents=True);accepted=[];rejected=[]
    for path in paths:
        before=path.read_bytes();source_hash=hashlib.sha256(before).hexdigest()
        try:
            result=parse(before);meshes,bounds=project_scene(result);image,viewport=raster(meshes,bounds,size,clip_z_max)
        except ValueError as error:
            rejected.append(dict(file=path.name,reason=str(error)));continue
        identifier=int(path.stem);png=output/f'{identifier:04d}.png';image.save(png)
        metadata=output/f'{identifier:04d}.map'
        metadata.write_bytes(struct.pack('<4sII7f',b'MCM1',size,size,*bounds,*viewport))
        if hashlib.sha256(path.read_bytes()).hexdigest()!=source_hash:raise ValueError('Source changed while generating map')
        accepted.append(dict(id=identifier,source_version=result['version'],source_sha256=source_hash,png_sha256=hashlib.sha256(png.read_bytes()).hexdigest(),metadata_sha256=hashlib.sha256(metadata.read_bytes()).hexdigest(),bounds=bounds,vertices=result['vertices'],triangles=result['triangles']))
    manifest=dict(schema=1,size=size,projection='first_instance_frame_column_major_XY',navigation_verified=False,accepted=accepted,rejected=rejected,source_unchanged=True)
    if selected is not None:manifest['selected_ids']=sorted(selected)
    if clip_z_max is not None:manifest['render_filter']={'clip_z_max':float(clip_z_max),'geometry_only':True}
    (output/'manifest.json').write_bytes((json.dumps(manifest,indent=2)+'\n').encode('utf8'))
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--size',type=int,default=512);p.add_argument('--ids',type=int,nargs='+',help='Generate only these map identifiers; omit for a full build');p.add_argument('--clip-z-max',type=float,help='Optional geometry-only cutaway plane; not automatic floor detection');a=p.parse_args()
    result=build(a.source,a.output,a.size,a.ids,a.clip_z_max)
    print(f"MAP_ATLAS PASS accepted={len(result['accepted'])} rejected={len(result['rejected'])} source_unchanged=true navigation_verified=false")
