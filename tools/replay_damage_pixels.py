"""Actual native submission -> Asura queue/driver -> owned offscreen HAL.

World point and digit first-vertex markers use separate native matrices. No
software projection is used for the pixel oracle. Texture conversion preserves
the BGR stored bottom-up rows consumed by the native graph's v=1 first vertex.
"""
import sys,json,subprocess,re,struct,hashlib,argparse,math
from pathlib import Path
from replay_damage_driver import NativeFlush,ROOT,require
sys.path.insert(0,str(ROOT/'tools'))
from resource_image import parse
HERE=ROOT/'build/damage-render-chain/driver'
GPU=None
SOURCE=None
I=[1.,0,0,0,0,1.,0,0,0,0,1.,0,0,0,0,1.]
def output_path(name):
 file=HERE/name
 require(SOURCE is None or file.resolve()!=SOURCE,'Input source overwrite rejected')
 require(file.resolve().is_relative_to((ROOT/'build').resolve()),'Output must remain inside build/')
 require(not file.is_symlink() and (not file.exists() or file.stat().st_nlink==1),'Output symlink/hardlink rejected')
 return file
def write_input(name,size,viewport,draw,texture=None):
 tw=th=0;pixels=b''
 if texture:
  image=parse(texture.read_bytes());tw,th=image.width,image.height;require(image.format=='TGA' and image.stride==tw*4,'Expected native 32-bit TGA texture')
  pixels=image.bitmap
 renderstates=draw.get('renderstates',{});stagestates=draw.get('stagestates',[])
 header=struct.pack('<7I48f6I',0x33504744,*size,*viewport,*draw['transforms']['1'],*draw['transforms']['2'],*draw['transforms']['3'],draw['kind'],len(draw['vertices']),tw,th,len(renderstates),len(stagestates))
 vertices=b''.join(struct.pack('<3f3I2f',*v) for v in draw['vertices'])
 states=b''.join(struct.pack('<2I',int(k),v) for k,v in renderstates.items())+b''.join(struct.pack('<3I',*state) for state in stagestates)
 file=output_path(name+'.bin');file.write_bytes(header+vertices+pixels+states)
 return file
def gpu(name,size,viewport,draw,texture=None):
 file=write_input(name,size,viewport,draw,texture);bmp=output_path(name+'.bmp')
 r=subprocess.run([str(GPU),str(file),str(bmp)],capture_output=True,text=True,timeout=60)
 output_path(name+'.stdout.txt').write_text(r.stdout+r.stderr,newline='\n');require(r.returncode==0,r.stdout+r.stderr)
 m=re.search(r'bbox=(-?\d+),(-?\d+),(-?\d+),(-?\d+) pixels=(\d+)',r.stdout);require(m is not None,'Missing GPU bbox')
 bbox=list(map(int,m.groups()[:4]));require(bbox[2]>=bbox[0],r.stdout)
 return {'bbox':bbox,'pixels':int(m[5]),'stdout':r.stdout.strip(),'exit':r.returncode,'input':str(file),'image':str(bmp),'sha256':hashlib.sha256(file.read_bytes()).hexdigest()}
def run(source,j,physical=None,case_index=0,native_only=False):
 w,h=j['logical_canvas'];pw,ph=physical or (w,h);viewport=(0,0,pw,ph)
 require('flush_entry_driver_modelview' in j['frames'][0],'Capture actual frame state, do not invent UI view')
 require(j['frames'][0]['tick']==0 and j['frames'][0]['number_position'][:2]==j['native_screen'],'This oracle requires native initial frame with zero float displacement')
 for asset,digest in j['resources'].items():
  path=Path(asset);path=path if path.is_absolute() else ROOT/path
  require(hashlib.sha256(path.read_bytes()).hexdigest()==digest,'Native resource identity changed: '+asset)
 raster=j['raster'][0];prefix=f'case{case_index}-{w}x{h}-{pw}x{ph}'
 point={'kind':1,'vertices':[[*raster['point'],0,0xffffffff,0,0,0]],'transforms':{'1':raster['modelview'],'2':I,'3':raster['projection']}}
 n=NativeFlush();n.put(n.obj+0x14,ph);n.slot(0x554,viewport)
 for mode,m in [(0x1701,raster['projection']),(0x1700,j['frames'][0]['flush_entry_driver_modelview'])]:
  n.slot(0x2cc,(mode,));n.u.mem_write(0x23002000,struct.pack('<16f',*m));n.slot(0x290,(0x23002000,))
 captures=n.registered_batch(j['frames'][0]['draws']);pixels=[]
 native_file=output_path(prefix+'-native-draws.json');native_file.write_text(json.dumps({'draws':captures,'queue_order':n.queue_order,'texture_upload_boundary':'Owned opaque texture pointers; native binding metadata explicitly initialized LINEAR mag/min, no mipmaps, WRAP u/v. Native emitted states are captured and applied on the owned GPU. Commercial driver init/resource COM calls are not executed.','controlled_render_boundary':'Isolated offscreen surface, no depth buffer; owned Z-off boundary and D3D default initial states, followed by actual captured native states.'},indent=2),newline='\n')
 if native_only:
  head_input=write_input(prefix+'-head',(pw,ph),viewport,point)
  report={'source':str(Path(source).resolve()),'case_index':case_index,'logical':[w,h],'physical':[pw,ph],'native_queue_order':n.queue_order,'native_draw_report':str(native_file),'native_final_draws':captures,'head_gpu_input':str(head_input),'result':'NATIVE_ONLY_GPU_NOT_RUN','game_started':False,'dll_loaded':False,'display_mode_changed':False}
  print(f'DAMAGE_NATIVE_ONLY PASS logical={w}x{h} physical={pw}x{ph} draws={len(captures)} native_queue_sort_flush=true gpu_pixels=not_run')
  return report
 head=gpu(prefix+'-head',(pw,ph),viewport,point)
 for index,draw in enumerate(captures):
  require(draw['texture_handle'] is not None,'Native driver texture bind missing')
  asset=ROOT/'runtime/data/BGR'/f"{draw['texture_handle']-1:04d}.BGR"
  pixels.append(gpu(prefix+f'-digit{index}',(pw,ph),viewport,draw,asset))
 first=next(draw for draw in captures if draw['texture_handle']==j['frames'][0]['draws'][0]['args'][6])
 anchor=dict(first);anchor['kind']=1;anchor['vertices']=anchor['vertices'][:1];anchor['renderstates']={};anchor['stagestates']=[]
 actual=gpu(prefix+'-digit-anchor',(pw,ph),viewport,anchor)
 tolerance=[math.ceil(pw/w)+1,math.ceil(ph/h)+1]
 delta=[actual['bbox'][axis]-head['bbox'][axis] for axis in (0,1)]
 require(all(abs(delta[axis])<=tolerance[axis] for axis in (0,1)),'Independent world/UI GPU anchor mismatch: '+str(delta))
 require(head['bbox'][0]>pw*.1 and head['bbox'][1]>ph*.05,'Fixture must exercise a non-top-left head')
 for digit in pixels:
  x,y,right,bottom=digit['bbox'];ax,ay=actual['bbox'][:2]
  require(0<=x<=right<pw and 0<=y<=bottom<ph,'Glyph outside viewport')
  require(ax-2*pw/w<=x<=right<=ax+(len(pixels)*16+16)*pw/w and ay-2*ph/h<=y<=bottom<=ay+24*ph/h,'Actual textured glyph is not beside native head')
 report={'source':str(Path(source).resolve()),'case_index':case_index,'logical':[w,h],'physical':[pw,ph],'head':head,'digit_anchor':actual,'digits':pixels,'anchor_delta':delta,'tolerance':tolerance,'tolerance_reason':'Native float-to-integer anchor truncation is <1 logical pixel plus <=1 physical rasterization pixel; initial native frame has zero floating displacement.','native_queue_order':n.queue_order,'native_draw_report':str(native_file),'native_final_draws':captures,'game_started':False,'dll_loaded':False,'display_mode_changed':False,'result':'PASS'}
 file=output_path(prefix+'-pixels.json');require(file.resolve()!=Path(source).resolve(),'Source overwrite rejected');file.write_text(json.dumps(report,indent=2),newline='\n')
 print('DAMAGE_NATIVE_GPU logical='+str([w,h])+' physical='+str([pw,ph])+' head='+str(head['bbox'])+' digit_anchor='+str(actual['bbox'])+' digits='+str([p['bbox'] for p in pixels]))
 return report
if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('source',type=Path)
 parser.add_argument('--gpu',type=Path,required=True,help='Built owned damage_projection_gpu_fixture.exe')
 parser.add_argument('--output',type=Path,required=True,help='Evidence directory inside build/')
 parser.add_argument('--physical',type=int,nargs=2,metavar=('WIDTH','HEIGHT'))
 parser.add_argument('--include-4k',action='store_true',help='Also render every selected logical case on a 3840x2160 offscreen target')
 parser.add_argument('--case-index',type=int,action='append',help='Aggregate case index; default is first case of each distinct logical canvas')
 parser.add_argument('--native-only',action='store_true',help='Capture native queue/driver at the selected physical viewport without claiming GPU pixels')
 args=parser.parse_args();HERE=args.output.resolve();GPU=args.gpu.resolve();SOURCE=args.source.resolve()
 require(HERE.is_relative_to((ROOT/'build').resolve()),'Output must remain inside build/')
 require(GPU.is_file() and not GPU.is_symlink(),'Owned GPU fixture missing/symlink')
 require(GPU.name in ('damage_gpu.exe','damage_projection_gpu_fixture.exe'),'Expected owned GPU fixture executable')
 HERE.mkdir(parents=True,exist_ok=True)
 identity_paths=[Path(__file__),ROOT/'tools/replay_damage_driver.py',ROOT/'tools/resource_image.py',ROOT/'src/runtime/damage_projection_gpu_fixture.cpp',GPU,args.source]
 initial_identities={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in identity_paths}
 document=json.loads(args.source.read_text());cases=document.get('cases',[document]);selected=args.case_index
 if selected is None:
  seen=set();selected=[]
  for index,case in enumerate(cases):
   canvas=tuple(case['logical_canvas'])
   if canvas not in seen:selected.append(index);seen.add(canvas)
 reports=[]
 for index in selected:
  require(0<=index<len(cases),'Invalid aggregate case index')
  reports.append(run(args.source,cases[index],args.physical,index,args.native_only))
  if args.include_4k and args.physical!=[3840,2160]:reports.append(run(args.source,cases[index],(3840,2160),index,args.native_only))
 identities={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in identity_paths}
 require(identities==initial_identities,'Tool/GPU/source identity changed while replay was running')
 result={'schema':1,'cases':reports,'identities_sha256':identities,'command':subprocess.list2cmdline([sys.executable,*sys.argv]),'working_directory':str(Path.cwd()),'result':'NATIVE_ONLY_GPU_NOT_RUN' if args.native_only else 'PASS'}
 destination=output_path('NATIVE_VERIFICATION.json' if args.native_only else 'GPU_VERIFICATION.json');destination.write_text(json.dumps(result,indent=2),newline='\n')
 require(json.loads(destination.read_text())==json.loads(json.dumps(result)),'Evidence reopen verification failed')
 print(f'DAMAGE_NATIVE_{"DRIVER" if args.native_only else "GPU"} PASS cases={len(reports)} independent_world_ui_pixels={not args.native_only} native_queue_sort_flush=true actual_bgr_textures={not args.native_only} evidence_reopened=true game_started=false display_mode_changed=false')
