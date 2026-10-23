"""Mapped x86 native Asura UI flush + D3D driver. No DLL entrypoint/load."""
from pathlib import Path
import struct,json,hashlib
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
ROOT=Path(__file__).resolve().parents[1]
def require(condition,message):
 if not condition:raise ValueError(message)
class NativeFlush:
 def __init__(self):
  self.u=Uc(UC_ARCH_X86,UC_MODE_32);self.obj=0x20000000;self.device=0x22000000;self.stop=0x60000000;self.sp=0x400f0000
  self.callbacks={};self.transforms={};self.draws=[];self.events=[];self.matrix_stack=[];self.renderstates={};self.stagestates={};self.textures={};self.stacktop=bytes(struct.pack('<16f',1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1))
  for p,sha in [('runtime/data/Drv/AsrD3DDrv.dll','00d443327abf56c94f9f088515ab29be63bab9650771a5cacdcef20ab85eff29'),('runtime/data/Asura.dll','f81e7c458d43b77210311499b39b9be2c4895e3a3b356d2e848b6e84210d2557')]:
   data=(ROOT/p).read_bytes();require(hashlib.sha256(data).hexdigest()==sha,'Unsupported native binary hash: '+p)
   pe=pefile.PE(data=data);base=pe.OPTIONAL_HEADER.ImageBase;self.u.mem_map(base,(pe.OPTIONAL_HEADER.SizeOfImage+4095)&~4095);self.u.mem_write(base,pe.get_memory_mapped_image())
   for module in pe.DIRECTORY_ENTRY_IMPORT:
    for imp in module.imports:
     if imp.name==b'_ftol':self.u.mem_write(imp.address,struct.pack('<I',0x6000f000))
     if imp.name and imp.name in (b'memcpy',b'memmove',b'memset'):
      ptr=self.callback(('crt',imp.name.decode()));self.u.mem_write(imp.address,struct.pack('<I',ptr))
  for p,n in [(self.obj,0x140000),(self.device,0x3000),(0x23000000,0x100000),(0x40000000,0x100000),(self.stop,0x10000)]:self.u.mem_map(p,n)
  self.u.mem_write(0x6000f000,bytes.fromhex('83ec10d97c2408668b442408660d000c668944240ad96c240adf3c24d96c24088b04248b54240483c410c3'))
  self.u.mem_write(self.obj,struct.pack('<I',0x3001a5a8));self.u.mem_write(self.obj+0x2c,struct.pack('<I',self.device));self.u.mem_write(self.device,struct.pack('<I',self.device+0x1000))
  for slot in range(0,0xd0,4):self.u.mem_write(self.device+0x1000+slot,struct.pack('<I',self.callback(('device',slot))))
  ms=self.device+0x2000;self.u.mem_write(ms,struct.pack('<I',ms+0x100));self.u.mem_write(self.obj+0x108ea0,struct.pack('<III',ms,ms,ms))
  for slot in [0xc,0x10,0x18,0x44]:self.u.mem_write(ms+0x100+slot,struct.pack('<I',self.callback(('stack',slot))))
  self.u.mem_write(self.obj+0x58,struct.pack('<I',0x1700));self.u.mem_write(self.obj+0x5c,self.stacktop);self.u.mem_write(self.obj+0x9c,self.stacktop)
  self.transforms={1:self.stacktop,2:self.stacktop,3:self.stacktop};self.u.hook_add(UC_HOOK_CODE,self.hook)
 def callback(self,which):
  p=0x60000100+len(self.callbacks)*0x10;self.callbacks[p]=which;return p
 def word(self,p):return struct.unpack('<I',self.u.mem_read(p,4))[0]
 def put(self,p,value):self.u.mem_write(p,struct.pack('<I',value))
 def hook(self,u,address,size,unused):
  if address==0x30007a67:
   self.bound_texture=self.word(u.reg_read(UC_X86_REG_ESP)+8)
  if address not in self.callbacks:return
  which,slot=self.callbacks[address];sp=u.reg_read(UC_X86_REG_ESP);a=[self.word(sp+i*4) for i in range(1,8)];ret=0;pop=0
  if which=='crt':
   if slot=='memset':u.mem_write(a[0],bytes([a[1]&255])*a[2])
   else:u.mem_write(a[0],bytes(u.mem_read(a[1],a[2])))
   ret=a[0]
  elif which=='stack':
   if slot==0x18:self.stacktop=bytes(u.mem_read(a[1],64));pop=8
   elif slot==0x10:self.matrix_stack.append(self.stacktop);pop=4
   elif slot==0xc:self.stacktop=self.matrix_stack.pop();pop=4
   elif slot==0x44:u.mem_write(0x230ff000,self.stacktop);ret=0x230ff000;pop=4
  elif which=='device':
   if slot==0x2c:self.transforms[a[1]]=bytes(u.mem_read(a[2],64));pop=12;self.events.append(('transform',a[1],list(struct.unpack('<16f',self.transforms[a[1]]))))
   elif slot==0x34:self.viewport=list(struct.unpack('<4I2f',u.mem_read(a[1],24)));pop=8
   elif slot==0x64:
    count=a[4];fvf=a[2];require(fvf==0x1e2 and 0<count<65536,'Native DrawPrimitive layout/count')
    self.draws.append({'kind':a[1],'fvf':fvf,'texture_handle':getattr(self,'bound_texture',None),'vertices':[list(struct.unpack('<3f3I2f',u.mem_read(a[3]+i*32,32))) for i in range(count)],'transforms':{str(k):list(struct.unpack('<16f',v)) for k,v in self.transforms.items()},'viewport':self.viewport,'renderstates':dict(self.renderstates),'stagestates':[list(k)+[v] for k,v in self.stagestates.items()],'texturebindings':dict(self.textures)});pop=24
   elif slot==0x50:self.renderstates[a[1]]=a[2];pop=12
   elif slot==0x8c:self.textures[a[1]]=a[2];pop=12
   elif slot==0x94:self.stagestates[(a[1],a[2])]=a[3];pop=16
   elif slot in [0x14,0x18]:pop=4
   else:raise AssertionError(('unhandled D3D COM',hex(slot),a))
  u.reg_write(UC_X86_REG_EAX,ret);u.reg_write(UC_X86_REG_EIP,self.word(sp));u.reg_write(UC_X86_REG_ESP,sp+4+pop)
 def call(self,address,args=(),this=None):
  self.u.mem_write(self.sp,struct.pack('<'+('I'*(1+len(args))),self.stop,*args));self.u.reg_write(UC_X86_REG_ESP,self.sp)
  if this is not None:self.u.reg_write(UC_X86_REG_ECX,this)
  self.u.emu_start(address,self.stop,count=2000000);require(self.u.reg_read(UC_X86_REG_EIP)==self.stop,'Native replay exceeded instruction limit')
 def slot(self,slot,args=()):self.call(self.word(0x3001a5a8+slot),args,self.obj)
 def registered_flush(self,draw):
  """Actual captured ASRRegRender args, pointer relocated; execute native queue writer."""
  ptr=0x23000000;matrix=0x23001000
  self.u.mem_write(ptr,struct.pack('<20f',*draw['vertices']));self.u.mem_write(matrix,struct.pack('<16f',*draw['matrix']))
  args=list(draw['args']);args[2]=ptr;args[12]=matrix
  self.put(0x10742c30,0);self.u.mem_write(0x103e2800,struct.pack('<4f',1,1,1,1))
  self.call(0x10051a01,args);require(self.word(0x10742c30)==1,'Native UI queue registration failed')
  self.call(0x100516fd,(self.obj,));return self.draws[-1]
 def registered_batch(self,draws):
  """Execute actual queue writer, native sorting and the complete ASRRender loop."""
  require(0<len(draws)<=100,'Supported queue fixture size is 1..100')
  self.put(0x103e27bc,0);self.put(0x10742c30,0)
  self.u.mem_write(0x103e2800,struct.pack('<4f',1,1,1,1))
  before=len(self.draws)
  for index,draw in enumerate(draws):
   ptr=0x23000000+index*0x100;matrix=0x23010000+index*0x100
   self.u.mem_write(ptr,struct.pack('<20f',*draw['vertices']));self.u.mem_write(matrix,struct.pack('<16f',*draw['matrix']))
   args=list(draw['args']);args[2]=ptr;args[12]=matrix;self.call(0x10051a01,args)
   self.put(self.obj+0x100ea0+args[6]*4,0x23030000+index*4)
   # Owned texture-upload boundary, not a claim of executing the driver ctor.
   for offset,value in [(0x112f14,2),(0x10ef14,2),(0x116f14,1),(0x11af14,1),(0x11ef14,1)]:
    self.put(self.obj+offset+args[6]*4,value)
  require(self.word(0x10742c30)==len(draws),'Native UI queue size mismatch')
  self.call(0x100516fd,(self.obj,))
  require(len(self.draws)-before==len(draws),'Native ASRRender lost a queued draw')
  self.queue_order=[self.word(0x103df4d8+i*4) for i in range(len(draws))]
  return self.draws[before:]
