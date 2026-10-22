"""Actual-PE battle queue/poll/GUI/combo replay; Windows queue APIs are contract shims."""
from pathlib import Path
import argparse,ctypes,hashlib,json,struct
from replay_native_title import NativeTitle,BASE,STOP
from replay_combo_cue import ComboHooks,value_data,ENGINE_SHA,VALUE_SHA
from unicorn.x86_const import UC_X86_REG_EAX,UC_X86_REG_ECX,UC_X86_REG_EIP,UC_X86_REG_ESP,UC_X86_REG_EBP
SCENE=0x20003000;ACTOR=0x20006000;MENU=0x20008000;OWNER=0x20009000;GUI=0x20002000;MANAGER=BASE+0xf2250
GUARDS={0x8ad08:'8b4de0516a21b950220f52e8371ef8ff',0x8aeac:'e84113f8ffff1558d00b52b950220f52e8031ff8ff',0x8afda:'e8df0df8ff',0xbdbe:'558bec83ec24',0xbde7:'ff1528d40b52',0xbdfb:'ff152cd40b52',0xbe2d:'ebac',0x2fcf:'ff15dcd30b52',0x55258:'6a20e855defaff',0x5610e:'e8b8050000',0x9d424:'c70060190c52'}

def require(ok,message):
 if not ok:raise ValueError(message)

def bridge_identity(path):
 root=Path(__file__).resolve().parents[1]
 return dict(dll_sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest(),
             header_sha256=hashlib.sha256((root/'src/runtime/battle_edge.h').read_bytes()).hexdigest(),
             source_sha256=hashlib.sha256((root/'src/runtime/battle_edge_bridge.cpp').read_bytes()).hexdigest(),
             implementation='Compiled repository SpaceEdgeLatch, not a Python replacement.')

class Latch:
 """Runs the repository's actual C++ SpaceEdgeLatch through an owned bridge DLL."""
 def __init__(self,path):
  self.lib=ctypes.CDLL(str(Path(path).resolve()));p=ctypes.c_void_p;u=ctypes.c_uint32;o=ctypes.c_size_t;i=ctypes.c_int
  self.lib.edge_create.restype=p;self.lib.edge_destroy.argtypes=[p]
  self.lib.edge_sample.argtypes=[p,o,u,i];self.lib.edge_message.argtypes=[p,o,u,u,i,i,i];self.lib.edge_consume.argtypes=[p,o,u,i];self.lib.edge_consume.restype=i
  self.obj=self.lib.edge_create();require(self.obj,'Owned latch allocation failed')
 def sample(self,owner,now,valid):self.lib.edge_sample(self.obj,owner,now,int(valid))
 def message(self,owner,now,stamp,down,repeat,valid):self.lib.edge_message(self.obj,owner,now,stamp,int(down),int(repeat),int(valid))
 def consume(self,owner,now,valid):return bool(self.lib.edge_consume(self.obj,owner,now,int(valid)))
 def close(self):
  if self.obj:self.lib.edge_destroy(self.obj);self.obj=None

class QueueReplay(NativeTitle):
 def __init__(self,image,values,hz,events,bridge=None):
  require(hashlib.sha256(image).hexdigest()==ENGINE_SHA,'Unsupported complete engine SHA256')
  super().__init__(image)
  for rva,raw in GUARDS.items():require(bytes(self.cpu.mem_read(BASE+rva,len(bytes.fromhex(raw)))).hex()==raw,f'Native source guard drift {rva:x}')
  self.hooks=ComboHooks(self.cpu,values,SCENE,ACTOR);self.stubs={};self.now=0;self.hz=hz;self.steps=0;self.key=False;self.events=sorted(events);self.event_index=0;self.queue=[];self.records=[];self.polls=[];self.messages=[];self.latch=Latch(bridge) if bridge else None;self.phase='setup';self.clock_reads=0;self.last=None;self.history=[]
  self.stub(0xb8b4e,'memset',0,self.memset)
  self.import_stub(0xbd24c,'malloc',0,lambda:self.hooks.allocate(self.arg(0)))
  self.import_stub(0xbd43c,'timeGetTime',0,self.clock)
  self.import_stub(0xbd3dc,'GetKeyboardState',4,self.keyboard)
  self.import_stub(0xbd058,'ASRBegin',0)
  self.import_stub(0xbd428,'PeekMessageA',20,self.peek)
  self.import_stub(0xbd42c,'GetMessageA',16,self.get_message)
  self.import_stub(0xbd430,'TranslateMessage',4)
  self.import_stub(0xbd434,'DispatchMessageA',4)
  self.stub(0xc1f2,'ASR_clear',0)
  self.stub(0x2dad,'OS_cursor',0)
  self.stub(0x52637,'card_pool',0)
  self.stub(0x565d2,'GUI_eligible',0,lambda:1)
  self.stub(0x557ee,'GUI_mouse_navigation',0)
  self.stub(0xa44b7,'actor_animation_interrupt',0)
  self.stub(0xa42e2,'actor_action_prepare',0)
  self.stub(0x8e0ef,'selected_actor_ready',0,lambda:1)
  self.stub(0xa4ecd,'actor_completion',0)
  self.stub(0xa9082,'actor_command_pending',0)
  self.stub(0xa9025,'actor_command_transition',4)
  # Real registered battle wrapper and scene virtual tables, not handwritten dispatch tables.
  self.call(0x8b050,OWNER);self.write(OWNER+0xc,SCENE)
  self.write(SCENE,BASE+0xc1960);self.write(SCENE+0x40,ACTOR);self.write(SCENE+0x15d4,ACTOR);self.write(SCENE+0x1dc4,1);self.write(SCENE+0x1718,1)
  self.write(ACTOR+0xec,0x2000a000)
  self.write(MENU,BASE+0xbec88);self.write(MENU+4,0xf6);self.write(MENU+0x17c,SCENE);self.write(MENU+0x190,1);self.write(SCENE+0x10fc,MENU)
  self.call(0x2590,GUI,0,9);self.call(0x2590,0x2000b000,0,9);self.write(SCENE+0x1708,0x2000b000);self.write(BASE+0xf220c,GUI)
  self.write(MANAGER+0x2c,0x3f800000)
  self.write(0x3001e000-0x20,OWNER);self.cpu.reg_write(UC_X86_REG_EBP,0x3001e000);self.cpu.reg_write(UC_X86_REG_ESP,0x3001df00);self.run(BASE+0x8ad08,BASE+0x8ad18)
  self.task=self.read(self.read(MANAGER+0xc));require(self.read(self.task+8)==33,'Native battle registration interval mismatch')
  if hz==60:self.cpu.mem_write(BASE+0xce5c,b'\xeb')
  if self.latch:self.latch.sample(SCENE,0,True)
  self.phase='frame'
 def stub(self,rva,name,pop,fn=None):self.stubs[BASE+rva]=(name,pop,fn)
 def import_stub(self,rva,name,pop,fn=None):
  p=STOP+0x800+len(self.stubs)*16;self.write(BASE+rva,p);self.stubs[p]=(name,pop,fn)
 def arg(self,n):return self.read(self.cpu.reg_read(UC_X86_REG_ESP)+4+n*4)
 def ret(self,pop,value=0):
  sp=self.cpu.reg_read(UC_X86_REG_ESP);self.cpu.reg_write(UC_X86_REG_EAX,value);self.cpu.reg_write(UC_X86_REG_ESP,sp+4+pop);self.cpu.reg_write(UC_X86_REG_EIP,self.read(sp))
 def memset(self):
  dest,value,n=self.arg(0),self.arg(1),self.arg(2);require(n<=0x10000,'Owned memset limit');self.cpu.mem_write(dest,bytes([value&255])*n);return dest
 def clock(self):
  if self.phase=='frame' and self.clock_reads:self.now+=1
  self.clock_reads+=1;return self.now
 def keyboard(self):
  keys=bytearray(256);keys[32]=0x80 if self.key else 0
  valid=self.read(SCENE+0x1dc4)==1
  edge=self.latch.consume(SCENE,self.now,valid) if self.latch else False
  if edge:keys[32]|=0x80;self.write(BASE+0xf1c9c+32*4,0)
  self.cpu.mem_write(self.arg(0),bytes(keys));self.polls.append(dict(time=self.now,thread_key=self.key,latched=edge));return 1
 def enqueue(self):
  while self.event_index<len(self.events) and self.events[self.event_index][0]<=self.now:
   self.queue.append(self.events[self.event_index]);self.event_index+=1
 def peek(self):self.enqueue();return int(bool(self.queue))
 def get_message(self):
  require(bool(self.queue),'GetMessage called without queued event')
  stamp,down,repeat=self.queue.pop(0);self.key=bool(down)
  self.cpu.mem_write(self.arg(0),struct.pack('<7I',0,0x100 if down else 0x101,32,(1<<30) if repeat else 0,stamp,0,0))
  self.messages.append(dict(time=self.now,stamp=stamp,down=bool(down),repeat=bool(repeat)))
  if self.latch:self.latch.message(SCENE,self.now,stamp,down,repeat,self.read(SCENE+0x1dc4)==1)
  return 1
 def _instruction(self,cpu,address,size,data):
  self.last=address
  if hasattr(self,"history"):
   self.history.append(hex(address));self.history=self.history[-20:]
  if not hasattr(self,'hooks'):return super()._instruction(cpu,address,size,data)
  self.steps+=1
  if address in self.stubs:
   _,pop,fn=self.stubs[address];self.ret(pop,fn() if fn else 0);return
  if address==BASE+0xa0dc9:
   # Enter the actual timed-attack state function, not a Python tick increment.
   self.hooks.time=self.now;cpu.reg_write(UC_X86_REG_EIP,BASE+0xa14b2);return
  if address==BASE+0xa3681:
   self.records.append(dict(time=self.now,before_count=self.read(SCENE+0x1ddc),before_tick=self.read(SCENE+0x1de0)))
   self.hooks.time=self.now
  if address==BASE+0xa3270:
   if self.records:self.records[-1].update(count=self.read(SCENE+0x1ddc),recorded=[self.read(SCENE+0x1dd0+i*4) for i in range(3)])
  if self.hooks.handle(address):return
  if STOP+0x400<=address<STOP+0x430:return
  super()._instruction(cpu,address,size,data)
 def run(self,start,end,budget=100000):
  try:self.cpu.emu_start(start,end,count=budget)
  except Exception as e:raise ValueError(f'Native replay failure entry={start:x} last={self.last:x} history={self.history} eip={self.cpu.reg_read(UC_X86_REG_EIP):x}') from e
  require(self.cpu.reg_read(UC_X86_REG_EIP)==end,'Native instruction budget/stop failure')
 def call(self,rva,this,*args):
  sp=0x3001f000;self.cpu.mem_write(sp,struct.pack('<'+'I'*(1+len(args)),STOP,*args));self.cpu.reg_write(UC_X86_REG_ESP,sp);self.cpu.reg_write(UC_X86_REG_ECX,this);self.run(BASE+rva,STOP)
 def frame(self,now):
  self.now=max(self.now,now);self.clock_reads=0;bp=0x3001e000;self.write(bp-8,OWNER);self.cpu.reg_write(UC_X86_REG_EBP,bp);self.cpu.reg_write(UC_X86_REG_ESP,bp-0x100)
  # Actual callsites: clear/begin, CDC4 and its scene/GUI update tree; rendering excluded.
  self.run(BASE+0x8aeac,BASE+0x8aec1)
  self.cpu.reg_write(UC_X86_REG_ESP,bp-0x100);self.run(BASE+0xbdbe,BASE+0xbe2f)
 def finish(self):
  result=dict(hz=self.hz,latched=self.latch is not None,now=self.now,interval=self.read(self.task+8),native_handler_calls=len(self.records),records=self.records,polls=self.polls,messages=self.messages,recorded=[self.read(SCENE+0x1dd0+i*4) for i in range(3)],count=self.read(SCENE+0x1ddc),sounds=self.hooks.sounds,steps=self.steps,api_and_environment_boundaries=sorted(s[0] for s in self.stubs.values()),game_started=False,commercial_dll_loaded=False,owned_latch_bridge_loaded=self.latch is not None)
  if self.latch:self.latch.close()
  return result

def run_case(image,values,hz,events,bridge=None,duration=1000):
 require(hz in (30,60),'Only 30/60 Hz comparison cases are supported')
 require(isinstance(duration,int) and 100<=duration<=2000 and duration%100==0,'Duration must be 100..2000 ms in 100 ms steps')
 require(len(events)<=100 and all(len(e)==3 and isinstance(e[0],int) and 0<=e[0]<=duration for e in events),'Bounded message events required')
 q=QueueReplay(image,values,hz,events,bridge)
 for frame in range(1,duration*hz//1000+1):q.frame(frame*1000//hz)
 return q.finish()

def phase_sweep(image,values,bridge):
 points=[]
 for phase in range(33):
  events=[(20+phase,True,False),(40+phase,False,False)]
  runs=[run_case(image,values,hz,events,b,duration=100) for hz,b in [(30,None),(60,None),(60,bridge)]]
  points.append(dict(phase_ms=phase,baseline30=runs[0]['native_handler_calls'],baseline60=runs[1]['native_handler_calls'],
                     modified60=runs[2]['native_handler_calls'],records=[r['recorded'] for r in runs]))
 require(all(p['modified60']==1 for p in points),'Compiled latch dropped a phase-swept physical press')
 return dict(pulse_ms=20,phases_ms=list(range(33)),points=points,
             totals={k:sum(p[k] for p in points) for k in ['baseline30','baseline60','modified60']},
             old60_losses_against30=sum(p['baseline30']>p['baseline60'] for p in points))

def verify(image,values,bridge=None,sweep=False):
 events=[(20,True,False),(40,False,False)]
 cases=[run_case(image,values,hz,events) for hz in (30,60)]
 require(cases[0]['native_handler_calls']==1 and cases[1]['native_handler_calls']==0,'Shortest native queue red case not reproduced')
 fixed=run_case(image,values,60,events,bridge) if bridge else None
 if fixed:require(fixed['native_handler_calls']==1,'Compiled production latch did not restore the dropped press')
 triple_events=[(t,down,False) for start in [20,400,760] for t,down in [(start,True),(start+20,False)]]
 triple=[run_case(image,values,hz,triple_events,b,duration=900) for hz,b in [(30,None),(60,None)]+([(60,bridge)] if bridge else [])]
 require(triple[0]['recorded']==[0,11,22] and triple[0]['native_handler_calls']==3,'Native 30Hz three-hit reference drift')
 require(triple[1]['native_handler_calls']==1,'Native 60Hz three-hit lost-input sequence not reproduced')
 if bridge:
  require(triple[2]['recorded']==triple[0]['recorded'] and triple[2]['native_handler_calls']==3,'Compiled latch three-hit records differ from 30Hz')
  require([x['id'] for x in triple[2]['sounds']]==[0x237]*3,'Compiled latch did not retain three native success outcomes')
 sweep_report=phase_sweep(image,values,bridge) if sweep and bridge else None
 return dict(engine_sha256=ENGINE_SHA,value_sha256=VALUE_SHA,guards={hex(k):v for k,v in GUARDS.items()},minimal_events=events,baseline=cases,modified=fixed,triple_events=triple_events,triple=triple,phase_sweep=sweep_report,latch_bridge=bridge_identity(bridge) if bridge else None,game_started=False,commercial_dll_loaded=False,owned_latch_bridge_loaded=bridge is not None,limits=['Win32 queue removal updates thread key state through external API contract shims; no real HWND, OS input injection or game process.','Graphics allocation, sound construction, actor key-match/readiness/completion, animation interruption/action preparation and GUI eligibility are bounded fixture leaves.','Actual battle listener, A3681 handler, A14B2 timer, full CDC4 scheduler and pump drain instructions execute unchanged.'])

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--sample',type=Path,required=True);p.add_argument('--values',type=Path,required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--latch-bridge',type=Path);p.add_argument('--phase-sweep',action='store_true');a=p.parse_args()
 require(a.report.resolve() not in [a.sample.resolve(),a.values.resolve()] and not a.report.exists(),'New report distinct from inputs required')
 r=verify(a.sample.read_bytes(),value_data(a.values.read_bytes()),a.latch_bridge,a.phase_sweep);a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8')
 print('BATTLE_MESSAGE_QUEUE PASS native_pump=true native_scheduler=true native_keyboard=true native_gui_listener=true native_handler=true baseline30=1 baseline60=0 modified60='+str(r['modified']['native_handler_calls'] if r['modified'] else 'not_tested')+' game_started=false')
