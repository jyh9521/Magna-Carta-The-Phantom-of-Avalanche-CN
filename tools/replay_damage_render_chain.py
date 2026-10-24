"""Actual native head-anchor/damage digits/render replay. Never launches the game."""
import argparse,hashlib,json,struct,subprocess
from pathlib import Path
from replay_native_title import NativeTitle,BASE,STOP
from replay_battle_message_queue import require
from replay_battle_gamepad import BattleGamepadReplay
from replay_combo_cue import ComboHooks,ENGINE_SHA
from unicorn.x86_const import UC_X86_REG_ECX,UC_X86_REG_ESP,UC_X86_REG_EIP,UC_X86_REG_EAX,UC_X86_REG_EBP

DRIVER_SHA='00d443327abf56c94f9f088515ab29be63bab9650771a5cacdcef20ab85eff29'
ASURA_SHA='f81e7c458d43b77210311499b39b9be2c4895e3a3b356d2e848b6e84210d2557'
class DamageReplay(NativeTitle):
 def __init__(self,data,width=800,height=600):
  self.data=Path(data);image=(self.data/'MCAlpha.dll').read_bytes();require(hashlib.sha256(image).hexdigest()==ENGINE_SHA,'Complete engine identity');super().__init__(image)
  self.hooks=ComboHooks(self.cpu,{});self.stubs={};self.last=0;self.steps=0;self.history=[];self.fdihandles={};self.fdihandle=100;self.resource_hashes={};self.skipped_decorations=0;self.calls=[]
  import pefile
  source=(self.data/'ASURA.dll').read_bytes();require(hashlib.sha256(source).hexdigest()==ASURA_SHA,'Complete ASURA identity');p=pefile.PE(data=source);a=p.OPTIONAL_HEADER.ImageBase;self.cpu.mem_map(a,p.OPTIONAL_HEADER.SizeOfImage);self.cpu.mem_write(a,p.get_memory_mapped_image());self.executable.extend((a+s.VirtualAddress,a+s.VirtualAddress+max(s.Misc_VirtualSize,s.SizeOfRawData)) for s in p.sections if s.Characteristics&0x20000000)
  exports={s.name:s.address+a for s in p.DIRECTORY_ENTRY_EXPORT.symbols if s.name}
  for d in pefile.PE(data=image).DIRECTORY_ENTRY_IMPORT:
   for i in d.imports:
    if i.name and b'ASRMatrix' in i.name and i.name in exports:self.write(i.address,exports[i.name])
  self.import_stub(0x10066174-BASE,'ASURA memset',0,self.memset)
  self.import_stub(0x1006617c-BASE,'ASURA memcpy',0,self.memcpy)
  self.write(0x10066178,STOP+0x1000)
  for i,(slot,code) in enumerate([(0x100661f0,'dd442404d9fec3'),(0x100661f4,'dd442404d9ffc3'),(0x100661c8,'dd442404d9fac3'),(BASE+0xbd314,'dd442404d9f2ddd8c3'),(BASE+0xbd37c,'dd442404d9e8d9f3c3')]):
   sh=STOP+0x500+i*16;self.cpu.mem_write(sh,bytes.fromhex(code));self.write(slot,sh)
  self.import_stub(0xbd320,'strlen',0,lambda:len(self.cstring(self.arg(0))))
  self.import_stub(0xbd330,'atoi',0,lambda:int(self.cstring(self.arg(0))))
  self.stub(0xb8b54,'memcpy',0,self.memcpy)
  self.stub(0xb8cf4,'sqrt x87 shim',0,None)
  self.stub(0xb8b5a,'owned allocation',0,lambda:self.hooks.allocate(self.arg(0)))
  self.stub(0xb8a86,'owned free',0);self.stub(0xb8b4e,'memset',0,self.memset)
  for r,n,fn in [(0xbd358,'sprintf',self.fmt),(0xbd028,'Cfopen',self.fopen),(0xbd020,'Cfread',self.fread),(0xbd030,'Cfclose',None),(0xbd344,'list free',None)]:self.import_stub(r,n,0,fn)
  self.import_stub(0xbd114,'ASRRegEnable state boundary',0)
  self.import_stub(0xbd1d8,'ASRRegDisable state boundary',0)
  self.import_stub(0xbd01c,'ASRRegRender queue boundary',0,self.render)
  self.import_stub(0xbd24c,'malloc',0,lambda:self.hooks.allocate(self.arg(0)))
  self.stub(0x323a1,'BGR decoded texture upload boundary',4,self.bgr)
  self.write(BASE+0xf1b48,width);self.write(BASE+0xf1b4c,height)
 def projection_bridge(self,path):
  exe=Path(path).resolve();self.bridge_path=exe;dll=exe.parent/'AsrD3DDrv.dll';require(exe.is_file() and dll.is_file(),'Owned compiled projection bridge required');self.bridge_dll=dll;self.raster_result=None;self.raster_cases=[]
 def raster(self):
  point=list(struct.unpack('<3f',self.cpu.mem_read(self.arg(0),12)));mv=list(struct.unpack('<16f',self.cpu.mem_read(self.driver+0x5c,64)));pr=list(struct.unpack('<16f',self.cpu.mem_read(self.driver+0x9c,64)));w,h=self.read(BASE+0xf1b48),self.read(BASE+0xf1b4c);line=[len(self.raster_cases),w,h,0x1897c,0x80a4,0x9b8c,*mv,*pr,*point,0,0,0,0,0]
  process=subprocess.run([str(self.bridge_path),str(self.bridge_dll)],input=' '.join(map(str,line))+'\n',text=True,capture_output=True,timeout=10);require(process.returncode==0,'Compiled hook bridge failed/rollback: '+process.stderr);out=process.stdout;require(bool(out),'Owned compiled bridge output missing');self.raster_result=json.loads(out);require(self.raster_result['abi_error_bits']==0,'Projection native ABI');self.raster_cases.append(dict(point=point,modelview=mv,projection=pr,result=self.raster_result));return 0
 def fresh_anchor(self):
  model=self.cpu.reg_read(UC_X86_REG_ECX);camera=self.read(BASE+0xf2290);lens=self.read(camera+4)
  sites=[0xaa0ba,0xaa398,0xaa629,0xaa916,0xaab88,0xab128,0xab453,0xab6e1,0xaba34]
  caller=self.read(self.cpu.reg_read(UC_X86_REG_ESP))-BASE-5;require(caller in sites,'Native popup getter callsite')
  def floats(address,count):return list(struct.unpack('<'+'f'*count,self.cpu.mem_read(address,count*4)))
  matrices=[];node=model
  while node:
   require(len(matrices)<64,'Bounded native parent hierarchy');matrices.append(floats(node+0x4c,16));node=self.read(node+8)
  fov,aspect,near,far=struct.unpack('<4d',self.cpu.mem_read(lens+0x10,32))
  flags=[];node=model
  while node:
   flags.extend([self.read(node+0x10c),self.read(node+0x110)]);node=self.read(node+8)
  line=['anchor-flags',self.read(BASE+0xf1b48),self.read(BASE+0xf1b4c),sites.index(caller),1,fov,near,far,*floats(camera+0x80,16),len(matrices),*[v for m in matrices for v in m],*flags,*floats(model+0xb4,16),*floats(model+0x12c,3),*struct.unpack('<2i',self.cpu.mem_read(model+0x138,8))]
  process=subprocess.run([str(self.bridge_path),str(self.bridge_dll),*getattr(self,'anchor_options',[])],input=' '.join(map(str,line))+'\n',text=True,capture_output=True,timeout=10)
  require(process.returncode==0,'Compiled fresh anchor bridge: '+process.stderr);result=json.loads(process.stdout);require(result['abi_error_bits']==0,'Fresh anchor ABI')
  raw=struct.pack('<2i',*result['screen']);self.cpu.mem_write(model+0x138,raw);self.cpu.mem_write(self.arg(0),raw);return self.arg(0)
 def render(self):
  args=[self.arg(i) for i in range(14)];self.calls.append(dict(args=args,vertices=list(struct.unpack('<20f',self.cpu.mem_read(args[2],80))),matrix=list(struct.unpack('<16f',self.cpu.mem_read(args[12],64)))));return 0
 def setup_driver(self):
  import pefile
  source=(self.data/'Drv/AsrD3DDrv.dll').read_bytes();require(hashlib.sha256(source).hexdigest()==DRIVER_SHA,'Complete driver identity');p=pefile.PE(data=source);b=p.OPTIONAL_HEADER.ImageBase;self.cpu.mem_map(b+0x20000,p.OPTIONAL_HEADER.SizeOfImage-0x20000);self.cpu.mem_write(b,p.get_memory_mapped_image());self.executable.extend((b+x.VirtualAddress,b+x.VirtualAddress+max(x.Misc_VirtualSize,x.SizeOfRawData)) for x in p.sections if x.Characteristics&0x20000000)
  self.import_stub(0x3001a504-BASE,'driver memcpy',0,self.memcpy);self.import_stub(0x3001a514-BASE,'driver memset',0,self.memset)
  self.driver=0x23000000;self.cpu.mem_map(self.driver,0x110000);self.write(self.driver,b+0x1a5a8);self.write(BASE+0xf1b70,self.driver);self.write(self.driver+0x58,0x1700);self.cpu.mem_map(0x24000000,0x20000)
  self.identity=struct.pack('<16f',*[float(i%5==0) for i in range(16)]);self.cpu.mem_write(self.driver+0x5c,self.identity);self.cpu.mem_write(self.driver+0x9c,self.identity)
  self.matrix_stacks={};self.matrix_current={};self.transforms=[]
  for field,offset in [(0x108ea0,0x5c),(0x108ea4,0x9c),(0x108ea8,0xdc)]:
   obj=self.hooks.allocate(8);vt=self.hooks.allocate(0x50);buf=self.hooks.allocate(64);self.write(obj,vt);self.write(self.driver+field,obj);self.matrix_stacks[obj]=[];self.matrix_current[obj]=buf;self.cpu.mem_write(buf,self.identity)
   for slot,name,pop,fn in [(0x18,'matrix stack LoadMatrix',8,self.stack_load),(0x10,'matrix stack Push',4,self.stack_push),(0xc,'matrix stack Pop',4,self.stack_pop),(0x44,'matrix stack GetTop',4,self.stack_top)]:
    a=STOP+0x800+len(self.stubs)*16;self.write(vt+slot,a);self.stubs[a]=(name,pop,fn)
  dev=self.hooks.allocate(8);vt=self.hooks.allocate(0x200);self.write(dev,vt);self.write(self.driver+0x2c,dev)
  for slot,pop in [(0x2c,12),(0x28,28),(0x34,8),(0x50,12),(0x58,16)]:
   a=STOP+0x800+len(self.stubs)*16;self.write(vt+slot,a);self.stubs[a]=('Device SetTransform/state',pop,self.set_transform if slot==0x2c else None)
 def stack_load(self):self.cpu.mem_write(self.matrix_current[self.arg(0)],bytes(self.cpu.mem_read(self.arg(1),64)));return 0
 def stack_push(self):self.matrix_stacks[self.arg(0)].append(bytes(self.cpu.mem_read(self.matrix_current[self.arg(0)],64)));return 0
 def stack_pop(self):
  stack=self.matrix_stacks[self.arg(0)];require(bool(stack),'Native matrix stack underflow');self.cpu.mem_write(self.matrix_current[self.arg(0)],stack.pop());return 0
 def stack_top(self):return self.matrix_current[self.arg(0)]
 def set_transform(self):self.transforms.append(dict(kind=self.arg(1),matrix=list(struct.unpack('<16f',self.cpu.mem_read(self.arg(2),64)))));return 0
 def stub(self,rva,name,pop,fn=None):self.stubs[BASE+rva]=(name,pop,fn)
 def import_stub(self,rva,name,pop,fn=None):
  p=STOP+0x800+len(self.stubs)*16;self.write(BASE+rva,p);self.stubs[p]=(name,pop,fn)
 def arg(self,n):return self.read(self.cpu.reg_read(UC_X86_REG_ESP)+4+4*n)
 def ret(self,pop,value=0):
  sp=self.cpu.reg_read(UC_X86_REG_ESP);self.cpu.reg_write(UC_X86_REG_EAX,value or 0);self.cpu.reg_write(UC_X86_REG_ESP,sp+4+pop);self.cpu.reg_write(UC_X86_REG_EIP,self.read(sp))
 cstring=BattleGamepadReplay.cstring
 fread=BattleGamepadReplay.fread
 def bgr(self):
  obj=BattleGamepadReplay.bgr(self);self.write(obj+4,self.arg(0)+1);return obj
 def fmt(self):
  fmt=self.cstring(self.arg(1));v=self.arg(2);raw=(fmt.replace('\\','/')%v).encode()+b'\0';self.cpu.mem_write(self.arg(0),raw);return len(raw)-1
 def fopen(self):
  p=(self.data/self.cstring(self.arg(0)).replace('\\','/')).resolve();require(self.data.resolve() in p.parents,'Resource escape');b=p.read_bytes();self.resource_hashes[str(p)]=hashlib.sha256(b).hexdigest();self.fdihandle+=1;self.fdihandles[self.fdihandle]=[b,0];return self.fdihandle
 def memcpy(self):
  d,src,n=self.arg(0),self.arg(1),self.arg(2);require(n<=0x100000,'memcpy bound');self.cpu.mem_write(d,bytes(self.cpu.mem_read(src,n)));return d
 def memset(self):
  d,v,n=self.arg(0),self.arg(1),self.arg(2);require(n<=0x100000,'memset bound');self.cpu.mem_write(d,bytes([v&255])*n);return d
 def _instruction(self,cpu,address,size,data):
  self.last=address;self.steps+=1;self.history.append(hex(address));self.history=self.history[-16:]
  if not hasattr(self,'stubs'):return super()._instruction(cpu,address,size,data)
  if getattr(self,'popup_producer_stop',0)==address:
   self.ret(0,cpu.reg_read(UC_X86_REG_EAX));return
  if address==BASE+0x8cd1:self.ui_root=list(struct.unpack('<16f',self.cpu.mem_read(self.driver+0x5c,64)))
  if hasattr(self,'bridge_path'):
   if address==BASE+0xac590 and getattr(self,'use_fresh_anchor',False):self.ret(4,self.fresh_anchor());return
   if address==0x3001897c:
    require(self.read(cpu.reg_read(UC_X86_REG_ESP))==BASE+0x474d5,'Actual native raster callsite');self.ret(4,self.raster());return
   if address==0x300080a4 and self.arg(0)==0xb07:
    self.cpu.mem_write(self.arg(1),struct.pack('<4I',*self.raster_result['float_bits']));self.ret(8);return
   if address==0x30009b8c and self.arg(0)==0xb08:
    self.cpu.mem_write(self.arg(1),bytes([self.raster_result['valid']]));self.ret(8);return
  if address==BASE+0xb8cf4:cpu.reg_write(UC_X86_REG_EIP,STOP+0x520);return
  if address in self.stubs:
   _,pop,fn=self.stubs[address];self.ret(pop,fn() if fn else 0);return
  if address==BASE+0x4d984:
   dec=self.read(cpu.reg_read(UC_X86_REG_EBP)-0x20)
   if self.read(dec+0x18) in (0,1,4):
    require(self.cpu.mem_read(dec+1,1)==b'\0','Non-BGR interactive decoration');self.skipped_decorations+=1;cpu.reg_write(UC_X86_REG_EIP,BASE+0x4debc);return
  if STOP+0x500<=address<STOP+0x560:return
  super()._instruction(cpu,address,size,data)
 def call(self,rva,this,*args,budget=2000000):
  sp=0x2401f000 if hasattr(self,'driver') else 0x3001f000;self.cpu.mem_write(sp,struct.pack('<'+'I'*(1+len(args)),STOP,*args));self.cpu.reg_write(UC_X86_REG_ESP,sp);self.cpu.reg_write(UC_X86_REG_ECX,this)
  try:self.cpu.emu_start(BASE+rva,STOP,count=budget)
  except Exception as e:raise RuntimeError(f'Native fault {rva:x} last={self.last:x} history={self.history}') from e
  require(self.cpu.reg_read(UC_X86_REG_EIP)==STOP,'Native instruction budget/stop')
  require(self.cpu.reg_read(UC_X86_REG_ESP) in (sp+4,sp+4+4*len(args)),'Native stack balance')
  return self.cpu.reg_read(UC_X86_REG_EAX)


def fbits(value):return struct.unpack('<I',struct.pack('<f',value))[0]
def run_chain(data,bridge,width=800,height=600,damage=760,char_id=7,kind='damage',hidden=False,fresh_anchor=True,anchor_options=(),parented=False,stale=False,transformed=False,spatial_flags=(0,0),producer_route=None,parent_flags=(0,0)):
 import math
 require((width,height) in [(640,480),(800,600),(853,480),(1067,600)],'Supported logical canvas')
 require(char_id in (7,72,82) and kind in ('damage','heal'),'Source-derived actor/popup cases')
 require(isinstance(damage,int) and 0<=damage<=999999,'Bounded native numeric resource case')
 q=DamageReplay(data,width,height);q.setup_driver();q.projection_bridge(bridge);q.use_fresh_anchor=fresh_anchor;q.anchor_options=anchor_options
 try:
  # These leaves are outside the anchor/number coordinate pipeline. Mesh geometry
  # and lighting are not claimed as rendered by this replay.
  q.stub(0x3ddf8,'mesh allocation/lifecycle after native model ctor',8,lambda:q.cpu.reg_read(UC_X86_REG_ECX))
  q.stub(0x3f00d,'mesh draw after native anchor consumer completes',0)
  q.stub(0x27162,'scene light registration',0)
  manager=q.hooks.allocate(0x40);q.call(0x1aa0,manager+4);q.call(0xb216c,manager,0)
  row=q.call(0xb3854,manager,char_id);require(row,'Actual enemy CharData row')
  mon=q.data/'Mon'/({7:'0000.Mon',72:'0054.Mon',82:'0033.Mon'}[char_id]);mon_bytes=mon.read_bytes();require(len(mon_bytes)==44 and struct.unpack_from('<2I',mon_bytes)==(8,1) and char_id in struct.unpack('<11i',mon_bytes)[3:],'Actual monster group references character');q.resource_hashes[str(mon.resolve())]=hashlib.sha256(mon_bytes).hexdigest()
  actor=q.hooks.allocate(0x500)
  # Same 300-byte native runtime row consumed by 646C5. The unrelated full
  # actor/shadow/icon lifecycle is not needed to call its real head getter.
  q.cpu.mem_write(actor+0x1b0,bytes(q.cpu.mem_read(row,300)))
  vec=q.hooks.allocate(12);q.call(0x65ca6,actor,vec)
  anchor=list(struct.unpack('<3f',q.cpu.mem_read(vec,12)))
  model_id=q.call(0xb1cb1,actor+0x1b0,0)
  require(anchor==[0.,0.,{7:40.,72:70.,82:60.}[char_id]] and model_id>0,'Real enemy model/height resource drift')
  parent=0
  if parented:
   parent=q.hooks.allocate(0x120);q.call(0x385af,parent,0,152)
   q.write(parent+0x10c,parent_flags[0]);q.write(parent+0x110,parent_flags[1])
   q.cpu.mem_write(parent+0x24,struct.pack('<3f',-15,10,5));q.call(0x38c61,parent)
  model=q.hooks.allocate(0x144);q.call(0x471f0,model,model_id,0xffffffff,parent,152)
  require(q.read(model)==BASE+0xbe200,'Native model constructor vtable')
  q.write(model+0x10c,spatial_flags[0]);q.write(model+0x110,spatial_flags[1])
  q.write(actor+0x2dc,model);q.call(0x65e80,model,*struct.unpack('<3I',q.cpu.mem_read(vec,12)))
  # Explicit world/camera fixture inputs. Native ASURA and driver multiplication
  # propagate these, and no screen coordinate is written by the test.
  q.cpu.mem_write(model+0x24,struct.pack('<3f',50,-20,0));q.call(0x38c61,model)
  if transformed:
   for node in (model,parent) if parent else (model,):
    q.cpu.mem_write(node+0x30,struct.pack('<3f',.1,.2,.3))
    q.cpu.mem_write(node+0x40,struct.pack('<3f',1.2,.9,1.1));q.call(0x38c61,node)
   q.cpu.mem_write(model+0x8c,struct.pack('<3f',3,2,1))
   q.cpu.mem_write(model+0x98,struct.pack('<3f',.2,.1,0));q.call(0x38f6a,model)
  camera=q.hooks.allocate(0x100)
  camera_matrix=[1.,0.,0.,0.,0.,0.,-1.,0.,0.,1.,0.,0.,0.,0.,-300.,1.]
  q.cpu.mem_write(camera+0x80,struct.pack('<16f',*camera_matrix));q.write(BASE+0xf2290,camera)
  projection_object=q.hooks.allocate(0xb0);q.call(0x1d050,projection_object)
  q.write(camera+4,projection_object)
  q.write(q.driver+0x14,height);q.call(0x1d440,projection_object)
  projection_parameters=list(struct.unpack('<4d',q.cpu.mem_read(projection_object+0x10,32)))
  q.call(0x300032c6-BASE,q.driver,0x1700)
  q.call(q.read(0x3001a5a8+0x288)-BASE,q.driver)
  if parented:q.call(0x392fd,parent)
  q.call(0x47416,model)
  if parented:q.call(0x3935f,parent)
  screen=list(struct.unpack('<2i',q.cpu.mem_read(model+0x138,8)))
  require(q.raster_result['valid']==1 and 0<screen[0]<width and 0<screen[1]<height,'Native visible enemy head')
  if hidden:
   # Constructor-zero cache plus native visibility early return. The prior
   # visible pass supplies an independent expected position, not popup input.
   q.write(model+0x114,0xffffffff)
   cached=[123,45] if stale else [0,0]
   q.write(model+0x138,cached[0]);q.write(model+0x13c,cached[1])
   count=len(q.raster_cases);q.call(0x47416,model)
   require(len(q.raster_cases)==count and q.read(model+0x138)==cached[0] and q.read(model+0x13c)==cached[1],'Native hidden model skips anchor projection')
  ui=q.hooks.allocate(0x60);q.call(0x8990,ui)
  gui=q.hooks.allocate(0x200);q.call(0x54fce,gui,99,0,0,0,ui,1)
  scene=q.hooks.allocate(0x2000);q.write(scene+0x10fc,gui)
  if producer_route is None:
   popup=q.hooks.allocate(0x100);q.call(0xa9ef0 if kind=='damage' else 0xaa459,popup,damage,actor,scene,0,0x144)
  else:
   require(kind=='damage' and producer_route in (0,1),'Two original numeric damage producer blocks')
   # Settlement result is the seam: execute original receive-handler argument
   # construction, allocation and constructor, not a Python constructor surrogate.
   fp=q.hooks.allocate(0x500)+0x300
   q.write(fp-0x1f8,actor);q.write(fp-0x10,scene);q.write(fp-0x14,damage)
   q.cpu.reg_write(UC_X86_REG_EBP,fp)
   q.popup_producer_stop=BASE+(0x8c3cb if producer_route==0 else 0x8c883)
   popup=q.call(0x8c38e if producer_route==0 else 0x8c83d,actor)
  number=q.read(popup+0xf4);require(q.read(number)==BASE+0xc0914,'Real numeric GUI constructor')
  if hidden:
   initial=list(struct.unpack('<2f',q.cpu.mem_read(number+0x24,8)))
   require(initial==screen,f'Hidden popup origin actual={initial} expected={screen}')
  frames=[]
  for tick in range(3):
   q.call(q.read(q.read(popup)+4)-BASE,popup);q.calls=[];q.call(0x8b34,ui)
   require(len(q.calls)==len(str(damage)),'Actual Draw digit count')
   ys={r['matrix'][13] for r in q.calls};require(len(ys)==1,'Digits share native screen row')
   require(struct.unpack('<f',q.cpu.mem_read(number+0x24,4))[0]==screen[0],'Native projected X reaches number graph')
   frames.append(dict(tick=tick,draws=q.calls.copy(),flush_entry_driver_modelview=list(struct.unpack('<16f',q.cpu.mem_read(q.driver+0x5c,64))),number_position=list(struct.unpack('<3f',q.cpu.mem_read(number+0x24,12)))))
  require(frames[0]['number_position'][1]==screen[1],'Native projected Y reaches number graph')
  require(frames[1]['number_position'][1]<frames[0]['number_position'][1],'Actual native mover advances popup upwards')
  texture_ids=[r['args'][6]-1 for r in frames[0]['draws']]
  require(texture_ids==[(194 if kind=='damage' else 204)+int(d) for d in str(damage)],'Actual FDI digit-to-BGR resource selection')
  result=dict(logical_canvas=[width,height],damage=damage,popup_kind=kind,enemy_char_id=char_id,model_id=model_id,head_anchor=anchor,actor_position_input=[50,-20,0],camera_input=camera_matrix,projection_parameters=projection_parameters,
    raster=q.raster_cases,native_screen=screen,ui_root_matrix=q.ui_root,frames=frames,resources=q.resource_hashes,native_steps=q.steps,
    boundaries=sorted({x[0] for x in q.stubs.values()}),skipped_non_bgr_decorations=q.skipped_decorations,
    hidden_model=hidden,parented_model=parented,stale_cache=stale,spatial_flags=list(spatial_flags),producer_route=producer_route,result='fresh_popup_anchor_through_native_ASRRegRender_submission',
    limits=['Mesh lifecycle/render is excluded after anchor propagation; character head uses native resource height category, not a guessed mesh bounding box.',
    'Actor placement and camera matrix are explicit fixture inputs, not a captured running-game scene.',
    'Texture upload is a boundary; actual BGR metadata, vertex UVs and image pixels remain source-derived.',
    'Final ASURA queue/driver/GPU results are separate downstream evidence, not proved by this engine report.'])
  return result
 finally:
  # subprocess.run bounds and reaps each owned bridge, including timeout failures.
  pass

def report_destination(data,report):
 require(not report.exists() and not report.resolve().is_relative_to(data.resolve()),'Report must be new and outside resource source')
 return report

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--data',type=Path,required=True);p.add_argument('--bridge',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
 report_destination(a.data,a.report)
 bridge_hash=hashlib.sha256(a.bridge.read_bytes()).hexdigest()
 cases=[run_chain(a.data,a.bridge,w,h) for w,h in [(640,480),(800,600),(853,480),(1067,600)]]
 cases.extend([run_chain(a.data,a.bridge,800,600,12345,72,'heal'),run_chain(a.data,a.bridge,1067,600,98,82,'damage')])
 require(hashlib.sha256(a.bridge.read_bytes()).hexdigest()==bridge_hash,'Owned bridge changed during replay')
 cases.extend(run_chain(a.data,a.bridge,w,h,1706,hidden=True,parented=(w>800),stale=(w==853)) for w,h in [(640,480),(800,600),(853,480),(1067,600)])
 cases.append(run_chain(a.data,a.bridge,800,600,12345,72,'heal',hidden=True))
 result=dict(schema=1,engine_sha256=ENGINE_SHA,asura_sha256=ASURA_SHA,tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),bridge_sha256=bridge_hash,cases=cases,
    current_baseline='72631ba draw-time projection enabled but popup reads cached anchor',independent_new_defect_observed=True,game_started=False,commercial_dll_loaded=False,owned_projection_bridge_loaded=True)
 a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,indent=2),encoding='utf8');require(json.loads(a.report.read_text())==result,'Reopen report verification')
 print('DAMAGE_RENDER_CHAIN PASS cases=11 native_head_to_digit_draw=true hidden_popup_anchor=fresh new_defect_observed=true game_started=false')
if __name__=='__main__':main()
