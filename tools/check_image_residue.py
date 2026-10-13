"""Read-only pixel checks for reviewed source-outline remnants outside targets."""
import argparse,json,sys
from pathlib import Path
from resource_image import parse
from build_image_text import rectangle

def check(workspace,plans):
    results=[]
    for row in plans['checks']:
        i=parse((Path(workspace)/row['resource']).read_bytes());rgba=i.rgba();n=0
        for box in row['regions_xyxy']:
            x1,y1,x2,y2=rectangle(box,i.width,i.height)
            for y in range(y1,y2):
                for x in range(x1,x2):
                    at=(y*i.width+x)*4
                    n+=list(rgba[at:at+4])!=row['expected_rgba']
        results.append(dict(resource=row['resource'],residual_pixels=n))
    return results

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True)
    p.add_argument('--plans',type=Path,required=True);a=p.parse_args()
    rows=check(a.workspace,json.loads(a.plans.read_text(encoding='utf8')));n=sum(r['residual_pixels'] for r in rows)
    print(f'IMAGE_RESIDUE {"PASS" if not n else "FAIL"} checks={len(rows)} residual_pixels={n} game_started=false')
    for r in rows:print(r['resource']+' residual_pixels='+str(r['residual_pixels']))
    sys.exit(0 if not n else 1)
