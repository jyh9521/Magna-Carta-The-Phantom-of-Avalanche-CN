"""Source-bound native combo-handler and cue update/draw differentials; no game/DLL load."""
from pathlib import Path
import argparse,hashlib,json,struct
from replay_native_title import NativeTitle,BASE,STOP
ENGINE_SHA='7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e'
VALUE_SHA='1433183acb6763aae110e6b1da7362704c9be30978eef7b6dbe46fd44edff58c'
SCENE=0x20003000;ACTOR=0x20006000

def value_data(data):
 if hashlib.sha256(data).hexdigest()!=VALUE_SHA:raise ValueError('Unsupported complete ValueData SHA256')
 count,version=struct.unpack_from('<II',data)
 if (count,version)!=(60,1) or len(data)!=8+count*8:raise ValueError('ValueData header mismatch')
 return dict(struct.unpack_from('<ii',data,8+i*8) for i in range(count))

class ComboHooks:
 """Reusable hooks for resource-boundaries only; native A3681/flags run unchanged.
 The caller invokes handle(address) from its Unicorn instruction hook and owns
 scene/actor setup and scheduler. Arena must not overlap another fixture map.
 """
 def __init__(self,cpu,values,scene=SCENE,actor=ACTOR,arena=0x22000000):
  self.cpu=cpu;self.values=values;self.scene=scene;self.actor=actor;self.next=arena;self.time=0;self.sounds=[];self.popups=[];self.counts={}
  cpu.mem_map(arena,0x100000)
  self.noop=STOP+0x400;cpu.mem_write(self.noop,b'\x31\xc0\xc3');cpu.mem_write(STOP+0x420,bytes.fromhex('dd442404d9fac3'))
  self.leaf_table=self.allocate(0x100)
  for o in range(0,0x100,4):self.write(self.leaf_table+o,self.noop)
 def allocate(self,n):
  a=self.next;self.next+=(n+15)&~15;self.cpu.mem_write(a,bytes(n));return a
 def write(self,a,v):self.cpu.mem_write(a,struct.pack('<I',v&0xffffffff))
 def read(self,a):return struct.unpack('<I',self.cpu.mem_read(a,4))[0]
 def vec(self,a,*v):self.cpu.mem_write(a,struct.pack('<3f',*v))
 def ret(self,value=0,pop=0):
  from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_EAX,UC_X86_REG_EIP
  sp=self.cpu.reg_read(UC_X86_REG_ESP);target=self.read(sp)
  self.cpu.reg_write(UC_X86_REG_EAX,value);self.cpu.reg_write(UC_X86_REG_ESP,sp+4+pop);self.cpu.reg_write(UC_X86_REG_EIP,target)
 def leaf(self):
  a=self.allocate(0x180);self.write(a,self.leaf_table);return a
 def popup(self,a,kind):
  self.write(a,BASE+0xc1b00);self.write(a+0xf0,self.actor);self.write(a+0xec,self.leaf())
  graph=self.allocate(0x194);self.write(graph,BASE+0xbec88);self.write(graph+0xec,self.leaf());self.write(a+0xf4,graph)
  mover=self.allocate(0x150);self.write(mover,BASE+0xbe9d8);self.write(mover+0xec,self.leaf());self.write(mover+0xf0,1)
  self.cpu.mem_write(mover+0x134,struct.pack('<f',8 if kind==3 else 4));self.vec(mover+0x138,0,-100,0);self.write(a+0xf8,mover)
  self.popups.append(dict(address=a,kind=kind,time=self.time,mover=mover,graph=graph))
 def handle(self,address):
  from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_ECX
  r=address-BASE;sp=self.cpu.reg_read(UC_X86_REG_ESP);this=self.cpu.reg_read(UC_X86_REG_ECX)
  self.counts[r]=self.counts.get(r,0)+1
  if r==0xb8cf4:
   from unicorn.x86_const import UC_X86_REG_EIP
   self.cpu.reg_write(UC_X86_REG_EIP,STOP+0x420);return True
  if r==0xb8b5a:self.ret(self.allocate(self.read(sp+4)));return True
  if r==0xa412d:self.ret(0);return True  # Normal timed attack, not charge mode.
  if r==0xa40df:self.ret(1);return True  # Selected actor's current action key matches.
  if r==0xb5b0e:
   key=self.read(sp+4)
   if key not in self.values:raise ValueError(f'Unknown native config key {key:x}')
   self.ret(self.values[key],4);return True
  if r==0xaaf58:
   self.popup(this,self.read(sp+4));self.ret(this,20);return True
  if r==0x493e0:
   self.sounds.append(dict(time=self.time,id=self.read(sp+4)));self.ret(this,20);return True
  if r in (0x4c600,0x4d340,0x4d370):self.ret();return True  # GPU/modelview leaves.
  if r==0x4d480:self.ret(pop=12);return True  # Leaf graph transform submission.
  return False

class ComboCueReplay(NativeTitle):
 def __init__(self,image,values):
  if hashlib.sha256(image).hexdigest()!=ENGINE_SHA:raise ValueError('Unsupported complete engine SHA256')
  super().__init__(image);self.hooks=ComboHooks(self.cpu,values);self.native_steps=0
  self.write(SCENE,BASE+0xc1960);self.write(SCENE+0x40,ACTOR);self.write(SCENE+0x15d4,ACTOR);self.write(SCENE+0x1dc4,1)
  graph=self.hooks.allocate(0x144);self.write(ACTOR+0x2dc,graph);self.write(graph+0x138,400);self.write(graph+0x13c,300)
 def _instruction(self,cpu,address,size,data):
  self.last=address
  if hasattr(self,'hooks') and self.hooks.handle(address):return
  if STOP+0x400<=address<STOP+0x430:return
  self.native_steps+=1;super()._instruction(cpu,address,size,data)
 def call(self,rva,this,args=()):
  from unicorn.x86_const import UC_X86_REG_ESP,UC_X86_REG_ECX
  sp=0x3001f000;self.cpu.mem_write(sp,struct.pack('<'+'I'*(1+len(args)),STOP,*args));self.cpu.reg_write(UC_X86_REG_ESP,sp);self.cpu.reg_write(UC_X86_REG_ECX,this)
  try:self.cpu.emu_start(BASE+rva,STOP,count=100000)
  except Exception as e:raise RuntimeError(f'native fault last={getattr(self,"last",0):x} eip={self.cpu.reg_read(self.regs[2]):x} entry={rva:x}') from e
  if self.cpu.reg_read(self.regs[2])!=STOP:raise ValueError(f'Instruction budget exhausted in {rva:x}')
 def press(self,time):
  self.hooks.time=time;before=self.read(SCENE+0x1ddc);self.call(0xa3681,SCENE)
  return dict(time=time,before_count=before,count=self.read(SCENE+0x1ddc),tick=self.read(SCENE+0x1de0),recorded=[self.read(SCENE+0x1dd0+i*4) for i in range(3)])
 def step_popup(self,popup,draw=False):
  p=popup['address'];self.call(self.read(self.read(p)+(0x10 if draw else 8))-BASE,p)
 def cues(self):
  return [dict(kind=p['kind'],age=self.read(p['address']+0xe4),y=struct.unpack('<f',self.cpu.mem_read(p['mover']+0x12c,4))[0],active=self.read(p['mover']+0xf0)) for p in self.hooks.popups]

def compare(image,values):
 runs=[]
 for hz in (30,60):
  q=ComboCueReplay(image,values);inputs=[];snapshots=[]
  # Exact shared logic/input ticks; presentation rate is the only variable.
  for tick in range(31):
   q.hooks.time=tick*33
   if tick in (0,12,24):inputs.append(q.press(tick*33))
   for p in list(q.hooks.popups):q.step_popup(p)
   for draw in range(hz//30):
    before=q.cues()
    for p in list(q.hooks.popups):q.step_popup(p,draw=True)
    if q.cues()!=before:raise ValueError('Draw unexpectedly mutated combo cue age/position')
   if tick in (0,12,24,30):snapshots.append(dict(tick=tick,cues=q.cues()))
   if q.read(SCENE+0x1dcc):q.write(SCENE+0x1de0,q.read(SCENE+0x1de0)+1)
  runs.append(dict(hz=hz,inputs=inputs,sounds=q.hooks.sounds,snapshots=snapshots,popup_update_calls=q.hooks.counts.get(0xab371,0),popup_draw_calls=q.hooks.counts.get(0x4c6ff,0)))
 if runs[0]['inputs']!=runs[1]['inputs'] or runs[0]['sounds']!=runs[1]['sounds'] or runs[0]['snapshots']!=runs[1]['snapshots']:raise ValueError('Native cue/handler differential found')
 return dict(engine_sha256=ENGINE_SHA,value_sha256=VALUE_SHA,interval=values[0x23],window=values[0x24],runs=runs,conclusion='No combo acceptance, sound event, popup age or mover-position differential in this bounded native handler/update/draw loop.',game_started=False,dll_loaded=False,
 limits=['Normal timed-attack key-match predicates are fixture inputs; actor/action-script execution is not included.','Allocation, graphics-resource construction and GPU transform leaves are shimmed; no sound device or rendered pixels.','Logic tick increment is supplied by the fixed-tick caller; complete scheduler timing is tested separately.','Does not establish the reported 60 FPS difficulty root cause.'])
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--sample',type=Path,required=True);p.add_argument('--values',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
 if a.report.resolve() in (a.sample.resolve(),a.values.resolve()) or a.report.exists():p.error('A new report path distinct from inputs is required')
 r=compare(a.sample.read_bytes(),value_data(a.values.read_bytes()));a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8')
 print('COMBO_CUE_REPLAY PASS native_A3681=true interval=10 window=6 update_cues=equal extra_draw_mutation=false sounds=equal game_started=false dll_loaded=false')
