"""Read-only native ANI layout audit. Emit aggregate metrics, never pose arrays.

Layout binding: supported MCAlpha RVA 2c88a. Header word 0 is opaque, not a
version. Matrix classifications mirror current motion::rigid admission using
Python double arithmetic; this is coverage evidence, not live render acceptance.
"""
import argparse,hashlib,json,math,struct
from pathlib import Path

def metrics():
 return dict(matrices=0,accepted=0,mirrored_accepted=0,reflected=0,singular=0,nonaffine=0,stretch_shear=0)

def classify(m):
 if not all(math.isfinite(v) for v in m):raise ValueError('Nonfinite ANI matrix')
 a,b,c,d,e,f,g,h,i=m[0],m[1],m[2],m[4],m[5],m[6],m[8],m[9],m[10]
 determinant=a*(e*i-f*h)-b*(d*i-f*g)+c*(d*h-e*g)
 norms=(a*a+b*b+c*c,d*d+e*e+f*f,g*g+h*h+i*i)
 dots=(a*d+b*e+c*f,a*g+b*h+c*i,d*g+e*h+f*i)
 stretch=any(abs(n-1)>.03 for n in norms) or any(abs(v)>.03 for v in dots)
 affine=abs(m[3])+abs(m[7])+abs(m[11])<.001 and abs(m[15]-1)<.001
 return dict(matrices=1,accepted=int(not stretch and affine and .97<determinant<1.03),
             mirrored_accepted=int(not stretch and affine and -1.03<determinant<-.97),
             reflected=int(determinant<0),singular=int(abs(determinant)<=1e-8),
             nonaffine=int(not affine),stretch_shear=int(stretch))

def parse(data):
 if len(data)<20 or len(data)>512*1024*1024:raise ValueError('ANI size outside bounds')
 tag,frames,stride,samples,bones=struct.unpack_from('<5I',data)
 if frames>100000 or samples>100000 or bones>512:raise ValueError('ANI count outside bounds')
 if not stride or stride>100000 or samples!=(frames+stride-1)//stride:raise ValueError('Unsupported ANI frame/sample relation')
 matrix_bytes=bones*(samples+1)*64
 if matrix_bytes>len(data)-20:raise ValueError('Truncated ANI matrices')
 bind=metrics();dynamic=metrics();pos=20
 for bone in range(bones):
  for sample in range(samples+1):
   m=struct.unpack_from('<16f',data,pos);pos+=64
   target=bind if sample==0 else dynamic
   for key,value in classify(m).items():target[key]+=value
 references=0
 for bone in range(bones):
  if pos+8>len(data):raise ValueError('Truncated ANI bone metadata')
  opaque_parent,count=struct.unpack_from('<2I',data,pos);pos+=8
  # Root parent fields may retain 0xcccccccc. Do not reinterpret/normalize them.
  if count>bones or pos+count*4>len(data):raise ValueError('Invalid ANI reference range')
  children=struct.unpack_from('<'+'I'*count,data,pos);pos+=count*4
  if any(child>=bones for child in children):raise ValueError('ANI child index outside bone array')
  references+=count
 if pos!=len(data):raise ValueError('Unexpected ANI trailing bytes')
 return dict(schema=1,sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),consumed=pos,
             header=dict(opaque_tag=tag,frames=frames,stride=stride,samples=samples,bones=bones),
             references=references,bind=bind,dynamic=dynamic,read_only=True,
             hierarchy_semantics_verified=False,live_pose_verified=False)

def audit(paths):
 rows=[];errors=[];bind=metrics();dynamic=metrics()
 for path in sorted(paths):
  try:
   result=parse(path.read_bytes());result['file']=path.name;rows.append(result)
   for label,total in [('bind',bind),('dynamic',dynamic)]:
    for key in total:total[key]+=result[label][key]
  except (ValueError,OSError,struct.error) as error:errors.append(dict(file=path.name,error=str(error)))
 return dict(schema=1,files=len(rows),errors=errors,bind=bind,dynamic=dynamic,items=rows,
             source_modified=False,pose_arrays_exported=False,live_pose_verified=False)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 source=a.source.resolve(strict=True);output=a.output.resolve()
 if not source.is_dir() or output==source or output.is_relative_to(source):raise ValueError('Report must be outside source data')
 paths=list(source.glob('*.ani'))
 if not paths:raise ValueError('No ANI inputs')
 result=audit(paths);output.parent.mkdir(parents=True,exist_ok=True);output.write_bytes((json.dumps(result,indent=2)+'\n').encode('utf8'))
 print(f"ANI_AUDIT files={result['files']} errors={len(result['errors'])} dynamic={result['dynamic']['matrices']} accepted={result['dynamic']['accepted']} mirrored_accepted={result['dynamic']['mirrored_accepted']} reflected={result['dynamic']['reflected']} stretch_shear={result['dynamic']['stretch_shear']} source_modified=false pose_arrays_exported=false")
 raise SystemExit(1 if result['errors'] else 0)
