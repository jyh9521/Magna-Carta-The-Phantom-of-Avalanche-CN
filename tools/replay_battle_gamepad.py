"""Bounded actual-PE battle GUI replay with compiled controller/focus traces.

Commercial modules are mapped as data in Unicorn; never loaded or launched.
"""
import argparse,hashlib,json,math,struct,subprocess
from pathlib import Path
from replay_battle_message_queue import *
class BattleGamepadReplay(QueueReplay):
 def __init__(self,image,values,data,width=800,height=600,mode=1):
  require((width,height) in [(800,600),(1067,600),(853,480)],"Unsupported logical canvas")
  self.data=Path(data);self.width=width;self.height=height
  self.rotations={};self.files={};self.skipped_decorations=0;self.resource_hashes={};self.fdihandles={};self.fdihandle=100;self.ev=[];self.visits=[];self.keybytes=bytes(256)
  super().__init__(image,values,30,[])
  self.import_stub(0xbd0dc,'ASR matrix ctor',0,lambda:self.cpu.reg_read(UC_X86_REG_ECX));self.import_stub(0xbd0d8,'ASR identity',0)
  self.stub(0x4191d,'ASR inverse matrix submission',0);self.stub(0x41614,'ASR matrix submission',0);self.stub(0x38c61,'ASR model transform',0);self.stub(0x38f6a,'ASR modelview transform',0)
  self.import_stub(0xbd358,'sprintf FDI filename',0,self.fmt);self.import_stub(0xbd028,'Cfopen',0,self.fopen);self.import_stub(0xbd020,'Cfread',0,self.fread);self.import_stub(0xbd030,'Cfclose',0);self.stub(0xb8a86,'owned free',0);self.import_stub(0xbd344,'owned list free',0);self.stub(0x323a1,'BGR metadata GPU boundary',4,self.bgr);self.stub(0x49720,'sound resource leaf',16,self.sound)
  self.write(BASE+0xf1b48,width);self.write(BASE+0xf1b4c,height)
  self.call(0xae3d0,MENU,SCENE,SCENE,GUI,0xf6)
  del self.stubs[BASE+0x8e0ef];del self.stubs[BASE+0xa9025];del self.stubs[BASE+0x565d2];del self.stubs[BASE+0x557ee]
  self.call(0x1aa0,GUI+0x20);self.call(0x1aa0,GUI+0x34);self.write(GUI+4,2)
  self.child=0x2000d000;self.call(0x54fce,self.child,0x39,0,0,MENU,MENU,0xf8)
  self.write(MENU+0x194,self.child)
  # Same relevant constructors/arguments as AE6E8. Unused system-menu content is blank.
  for field,ctor,tex,ident in [(0x1b0,0x5c5fa,0x38,0x104),(0x1b4,0x5e260,0x38,0x10c),(0x1b8,0x5e260,0x38,0x123),(0x1ac,0x5e260,0xffffffff,0xff),(0x1c8,0x54fce,0x39,0xfc)]:
   p=self.hooks.allocate(0x220);self.call(ctor,p,tex,0,0,MENU,MENU,ident);self.write(MENU+field,p)
  # AE6E8 supplies these logical-canvas hit rectangles explicitly, not from artwork.
  for field in [0x194,0x1b0,0x1b4,0x1b8,0x1c8]:
   self.call(0x5c510,0x2000c200,0,0,width,height);self.call(0x4e3e9,self.read(MENU+field),0x2000c200)
  cmd=self.read(MENU+0x1b0)
  for a,b,i in [(0xee,0xef,0x105),(0x2b,0x2c,0x106),(0x35,0x36,0x10b)]:self.call(0x5c7fb,cmd,a,b,0xffffffff,i,0)
  for field in [0x1b0,0x1b4,0x1b8,0x1ac]:self.call(0x5d39e,self.read(MENU+field))
  self.call(0x55d4e,self.read(MENU+0x1c8))
  # Character-specific availability/content is an explicit resource boundary, not event handling.
  self.stub(0xb03d6,'actor command content availability',0);self.stub(0xb0c25,'actor command enable attributes',0);self.stub(0xb0a89,'actor alternate command attributes',0)
  self.ability=self.hooks.allocate(0x80);self.write(self.ability+0x54,0xffffffff)
  self.stub(0xb5967,'selected ability resource row',4,lambda:self.ability)
  self.call(0x4c223,ACTOR,0,0,0x41);self.write(ACTOR,BASE+0xc1644)
  self.stub(0x59e29,'actor orientation matrix submission',0)
  self.import_stub(0xbd11c,'ASRMatrix SetRotateZ contract',4,self.rotate_z);self.import_stub(0xbd0fc,'ASRMatrix vector multiplication contract',8,self.rotate_vector)
  self.write(ACTOR+0x298,0)  # Native B1B94 slot-zero ability ID for the provided actor fixture.
  self.cpu.mem_write(BASE+0xf1c9c,bytes(256*4));self.cpu.mem_write(BASE+0xf1b94,bytes(256))
  self.call(0xaff96,MENU,mode)
  self.set_cursor(width//2,height//2)
  self.ev=[];self.visits=[];self.steps=0
 def populate_ability(self):
  # B03D6 uses this exact builder, FDI IDs and button ID for actor slot one.
  # Glyph shaping is a rendering-only boundary; native hit rectangles remain resource-derived.
  self.stub(0x4e514,'glyph text assignment',4)
  label=self.hooks.allocate(32);self.cpu.mem_write(label,b'Fixture ability\0')
  self.write(ACTOR+0x29c,0)
  self.call(0x5ca57,self.read(MENU+0x1b4),label,0x11,0x14,0xffffffff,0x10f,0)
 def rotate_z(self):
  self.rotations[self.cpu.reg_read(UC_X86_REG_ECX)]=struct.unpack("<f",struct.pack("<I",self.arg(0)))[0];return 0
 def rotate_vector(self):
  out,src=self.arg(0),self.arg(1);x,y,z=struct.unpack("<3f",self.cpu.mem_read(src,12));a=self.rotations.get(self.cpu.reg_read(UC_X86_REG_ECX),0);self.cpu.mem_write(out,struct.pack("<3f",x*math.cos(a)-y*math.sin(a),x*math.sin(a)+y*math.cos(a),z));return out
 def sound(self):
  p=self.cpu.reg_read(UC_X86_REG_ECX);self.write(p,BASE+0xbe7e0);self.write(p+0xec,self.arg(2));self.write(p+0xe8,1);return p
 def cstring(self,p):
  out=bytearray()
  for i in range(300):
   a=self.cpu.mem_read(p+i,1)[0]
   if not a:return out.decode('ascii')
   out.append(a)
  raise ValueError('cstring bound')
 def fmt(self):
  raw=('FrameData/%04d.fdi'%self.arg(2)).encode()+b'\0';self.cpu.mem_write(self.arg(0),raw);return len(raw)-1
 def fopen(self):
  import hashlib
  p=self.data/self.cstring(self.arg(0));require(p.parent.resolve()==(self.data/'FrameData').resolve(),'FDI resource path');b=p.read_bytes();require(len(b)==787 and b[:8]==struct.pack('<II',186,1),'Unsupported FDI version/size');self.resource_hashes[str(p)]=hashlib.sha256(b).hexdigest();self.fdihandle+=1;self.fdihandles[self.fdihandle]=[b,0];return self.fdihandle
 def fread(self):
  a=self.fdihandles[self.arg(3)];n=self.arg(1)*self.arg(2);require(a[1]+n<=len(a[0]),'Cfread bounds');self.cpu.mem_write(self.arg(0),a[0][a[1]:a[1]+n]);a[1]+=n;return self.arg(2)
 def bgr(self):
  from resource_image import parse
  import hashlib
  n=self.arg(0);p=self.data/'BGR'/f'{n:04d}.BGR';b=p.read_bytes();self.resource_hashes[str(p)]=hashlib.sha256(b).hexdigest();im=parse(b);count=struct.unpack_from('<I',b,4)[0];require(count<=8,'BGR rect bounds');obj=self.hooks.allocate(24);rect=self.hooks.allocate(max(16,16*count));self.cpu.mem_write(rect,b[8:8+16*count]);
  for o,v in [(0,n),(4,1),(8,im.width),(12,im.height),(16,count),(20,rect)]:self.write(obj+o,v)
  return obj
 def keyboard(self):self.cpu.mem_write(self.arg(0),self.keybytes);return 1
 def _instruction(self,cpu,address,size,data):
  if address in [BASE+r for r in (0x4c600,0x4d480)]:
   NativeTitle._instruction(self,cpu,address,size,data);return

  if address==BASE+0x4d984:
   dec=self.read(cpu.reg_read(UC_X86_REG_EBP)-0x20)
   if self.read(dec+0x18) in (0,1,4):
    require(self.cpu.mem_read(dec+1,1)==b'\0','Clickable non-BGR decoration not supported');self.skipped_decorations+=1;cpu.reg_write(UC_X86_REG_EIP,BASE+0x4debc);return
  if address==BASE+0xa2f7a:self.ev.append([self.arg(i) for i in range(4)])
  if address in [BASE+r for r in [0xa8ac6,0xa7303,0xa3681]]:self.visits.append(hex(address-BASE))
  super()._instruction(cpu,address,size,data)
 def set_cursor(self,x,y):
  for r,v in [(0xf20b0,x),(0xf20a8,y),(0xf20ac,x),(0xf20a4,y)]:self.write(BASE+r,v)
 def feed(self,keys,cursor=None,clear=0):
  require(len(keys)==256,'Keyboard snapshot length')
  if cursor:self.set_cursor(*cursor)
  for bit,key in [(1,1),(2,2)]:
   if clear&bit:self.write(BASE+0xf1c9c+4*key,0)
  self.keybytes=keys;before=len(self.ev)
  self.call(0xa0b7e,SCENE)
  return dict(events=self.ev[before:],command=self.read(SCENE+0x1980),target_mode=self.read(SCENE+0x1740),ability=self.read(SCENE+0x1744),combo_count=self.read(SCENE+0x1ddc),result_ready=self.read(SCENE+0x16e0),pressed_buttons={str(n['id']):n['pressed'] for n in self.snapshot()['nodes'] if n['vt']==0xc00dc},mode=self.read(MENU+0x190),actor_angle=struct.unpack('<f',self.cpu.mem_read(ACTOR+0x104,4))[0])
 def rects(self,p):
  node=self.read(p+0x100);result=[];seen=set()
  while node:
   require(node not in seen and len(seen)<32,'Bounded rectangle list');seen.add(node);r=self.read(node);result.append(list(struct.unpack('<4i',self.cpu.mem_read(r,16))));node=self.read(node+4)
  return result
 def snapshot(self):
  allowed={0xbec88,0xbee80,0xc00dc,0xc02d4,0xc06fc,0xc203c}
  nodes=[];seen=set()
  def visit(p):
   require(p not in seen and len(seen)<256,'Bounded GUI tree');seen.add(p)
   if self.read(p)-BASE not in allowed:return
   nodes.append(p);child=self.read(p+0x18)
   while child:visit(child);child=self.read(child+0x10)
  visit(MENU);index={p:i for i,p in enumerate(nodes)}
  out=[]
  for p in nodes:
   child=self.read(p+0x18)
   while child and child not in index:child=self.read(child+0x10)
   sibling=self.read(p+0x10)
   while sibling and sibling not in index:sibling=self.read(sibling+0x10)
   vt=self.read(p);out.append(dict(address=p,vt=vt-BASE,id=self.read(p+4),child=index.get(child,-1),sibling=index.get(sibling,-1),visible=self.read(p+0xe8),enabled=self.read(p+0x160),input_mode=self.read(p+0x164),listener=int(bool(self.read(p+0x17c))),x=struct.unpack('<f',self.cpu.mem_read(p+0x24,4))[0],y=struct.unpack('<f',self.cpu.mem_read(p+0x28,4))[0],rects=self.rects(p),pressed=self.read(p+0x19c),arrows=[self.read(vt+0xc8+4*i)-BASE for i in range(4)]))
  modal=self.read(self.read(GUI+0x3c)) if self.read(GUI+0x38) else 0
  return dict(width=self.width,height=self.height,modal=index.get(modal,-1),nodes=out)

def focus_input(snapshot,frame,cursor,events=False):
 nodes=snapshot['nodes'];lines=['%d %d %d %d %d %d %d %d %d %d %d'%(len(nodes),frame['nav_active'],frame['nav_held'],frame['nav_pressed'],frame['serial']+1,frame.get('nav_time',frame['serial']*33),snapshot['width'],snapshot['height'],*cursor,snapshot['modal'])+(' '+str(int(frame.get('cancel_menu',False))) if events else '')]
 for n in nodes:
  lines.append(' '.join(map(str,[n['vt'],n['id'],n['child'],n['sibling'],n['visible'],n['enabled'],n['input_mode'],n['listener'],n['x'],n['y'],len(n['rects']),*n['arrows'],*([n['pressed']] if events else [])])))
  lines.extend(' '.join(map(str,r)) for r in n['rects'])
 return '\n'.join(lines)+'\n'

def read_trace(path):
 rows=[json.loads(l) for l in Path(path).read_text().splitlines() if l]
 require(rows and rows[0].get('kind')=='metadata','Compiled production trace metadata required')
 frames=[r for r in rows if r.get('kind')=='frame'];require(len(frames)<=200,'Trace frame bound')
 for f in frames:require(len(bytes.fromhex(f['keys']))==256,'Complete production keyboard trace required')
 return frames

def focused_feed(q,frame,bridge,cursor):
 snapshot=q.snapshot();raw=focus_input(snapshot,frame,cursor,events=True)
 r=subprocess.run([str(Path(bridge).resolve()),'--events'],input=raw,text=True,capture_output=True,timeout=10)
 require(r.returncode==0,'Compiled focus bridge failed: '+r.stderr)
 output=json.loads(r.stdout);cursor=output['cursor']
 indices=output.get('native_clear_indices',[])
 for index in indices:
  require(0<=index<len(snapshot['nodes']),'Focus cancellation index bounds')
  q.call(0x5718f,snapshot['nodes'][index]['address'])
 result=q.feed(bytes.fromhex(frame['keys']),cursor,frame.get('clear_mouse_counters',0))
 return dict(input=frame,focus=output,result=result),cursor

def run_stage(image,values,data,trace,bridge,width=800,height=600):
 frames=read_trace(trace);by={f['action']:f for f in frames}
 def replay(mode,actions,focus=False,start_mode=None,populate=False):
  mode_frames=read_trace(Path(trace).with_name(Path(trace).name.rsplit('-mode',1)[0]+f'-mode{mode}.jsonl'));mode_by={f['action']:f for f in mode_frames}
  q=BattleGamepadReplay(image,values,data,width,height,start_mode or mode);cursor=[width//2,height//2];records=[]
  if populate:q.populate_ability()
  if start_mode:q.call(0xaff96,MENU,mode)
  if mode==7:
   ready=q.hooks.allocate(0x50);q.write(ready+0x3c,1);q.write(SCENE+0x16dc,ready)
  snapshot=q.snapshot()
  for action in actions:
   f=mode_by[action]
   if focus:record,cursor=focused_feed(q,f,bridge,cursor)
   else:record=dict(input=f,result=q.feed(bytes.fromhex(f['keys']),cursor,f.get('clear_mouse_counters',0)))
   records.append(record)
  return dict(records=records,initial_tree=snapshot,final_tree=q.snapshot(),resources=q.resource_hashes,steps=q.steps,
              boundaries=sorted(v[0] for v in q.stubs.values()),
              combo_resource_boundaries=['B8B5A owned allocation','A412D normal timed-attack type','A40DF matching actor command','B5B0E ValueData getter contract','AAF58 damage/combo popup resource constructor','493E0 audio resource constructor','4D340/4D370 matrix render state push/pop'],non_hit_render_decorations_omitted=q.skipped_decorations,native_state_machine_boundary='A0DC9 -> native timed-attack A14B2; later scene transitions not executed')
 result={}
 result['menu_cancel_outside_buttons']=replay(4,['B_down','B_hold','B_up'])
 result['first_confirm_outside_buttons']=replay(4,['A_down','A_hold','A_up'])
 result['navigate_confirm']=replay(4,['up_down','up_up','A_down','A_hold','A_up'],True)
 result['navigate_confirm_cancel_visual']=replay(4,['up_down','up_up','fresh_A_enter4','held_A_enter5','context_A_release'],True)
 result['field_cancel']=replay(1,['B_down','B_hold','B_up'])
 result['field_direction']=replay(1,['left_down','left_up','right_down','right_up','stick_left','stick_left_up'])
 result['field_combo']=replay(1,['A_down','A_hold','A_up'])
 result['ability_choose']=replay(5,['up_down','up_up','A_down','A_hold','A_up'],True,start_mode=4,populate=True)
 result['ability_cancel']=replay(5,['B_down','B_hold','B_up'],start_mode=4)
 result['item_original_boundary']=replay(6,['B_down','B_hold','B_up'],start_mode=4)
 result['result_confirm']=replay(7,['A_down','A_hold','A_up'],start_mode=4)
 result['trace_sha256']=hashlib.sha256(Path(trace).read_bytes()).hexdigest();result['focus_bridge_sha256']=hashlib.sha256(Path(bridge).read_bytes()).hexdigest()
 stage=Path(trace).name.rsplit('-mode',1)[0];src=Path(trace).parent/f'stage-{stage}-src';result['source_sha256']={f:hashlib.sha256((src/f).read_bytes()).hexdigest() for f in ['modern_gamepad.cpp','gamepad_ui.cpp']}
 return result

def main():
 p=argparse.ArgumentParser();p.add_argument('--sample',type=Path,required=True);p.add_argument('--values',type=Path,required=True);p.add_argument('--data',type=Path,required=True);p.add_argument('--trace-dir',type=Path,required=True);p.add_argument('--bridge-dir',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
 require(not a.report.exists(),'Report must be new')
 require(not a.report.resolve().is_relative_to(a.data.resolve()),'Report must be outside source data')
 start_tool_sha=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
 image=a.sample.read_bytes();values=value_data(a.values.read_bytes());result={}
 for stage in ['baseline','modified','rollback']:
  bridge=a.bridge_dir/f'stage-{stage}-native'/'Release'/'battle_gamepad_focus_fixture.exe'
  require(bridge.is_file(),'Build the tracked owned focus bridge for '+stage)
  for w,h in [(800,600),(1067,600)]:result[f'{stage}-{w}x{h}']=run_stage(image,values,a.data,a.trace_dir/f'{stage}-mode4.jsonl',bridge,w,h)
 checks={}
 for w,h in [(800,600),(1067,600)]:
  for stage in ['baseline','modified','rollback']:
   runs=result[f'{stage}-{w}x{h}'];last=lambda name:runs[name]['records'][-1]['result']
   checks[f'{stage}-{w}-cancel']=last('menu_cancel_outside_buttons')['command']==(5 if stage=='modified' else 0)
   checks[f'{stage}-{w}-outside-A-native-noop']=last('first_confirm_outside_buttons')['command']==0
   checks[f'{stage}-{w}-nav-A']=last('navigate_confirm')['command']==(5 if stage=='modified' else 0)
   checks[f'{stage}-{w}-field-cancel']=last('field_cancel')['command']==(14 if stage=='modified' else 0)
   checks[f'{stage}-{w}-field-native-turn']=abs(last('field_direction')['actor_angle']-0.15)<0.00001
   checks[f'{stage}-{w}-field-native-combo']=last('field_combo')['combo_count']==1
   checks[f'{stage}-{w}-ability-native-selection']=last('ability_choose')['command']==(5 if stage=='modified' else 0) and last('ability_choose')['target_mode']==(5 if stage=='modified' else 0)
   checks[f'{stage}-{w}-ability-back']=last('ability_cancel')['mode']==(4 if stage=='modified' else 5)
   checks[f'{stage}-{w}-item-native-boundary']=last('item_original_boundary')['mode']==6
   checks[f'{stage}-{w}-result-native-ready']=last('result_confirm')['result_ready']==1
   visual=runs['navigate_confirm_cancel_visual']['records'];checks[f'{stage}-{w}-cancel-no-additional-event']=not visual[-1]['result']['events'] and visual[-1]['result']['command']==visual[2]['result']['command']
   if stage=='modified':
    checks[f'{stage}-{w}-actual-native-button-press-clear']=visual[2]['result']['pressed_buttons']['261']==1 and visual[3]['result']['pressed_buttons']['261']==0 and bool(visual[3]['focus']['native_clear_indices'])
 require(all(checks.values()),'Native battle controller chain red/green/rollback mismatch: '+str(checks))
 require(hashlib.sha256(Path(__file__).read_bytes()).hexdigest()==start_tool_sha,"Replay source changed during execution")
 out=dict(schema=1,tool_sha256=start_tool_sha,focus_adapter_sha256=hashlib.sha256((Path(__file__).resolve().parents[1]/'src/runtime/battle_gamepad_focus_fixture.cpp').read_bytes()).hexdigest(),engine_sha256=hashlib.sha256(image).hexdigest(),values_sha256=hashlib.sha256(a.values.read_bytes()).hexdigest(),checks=checks,runs=result,game_started=False,commercial_dll_loaded=False,owned_fixture_executables_started=True)
 a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(out,indent=2),encoding='utf-8');json.loads(a.report.read_text());print('BATTLE_GAMEPAD_NATIVE_CHAIN_PASS checks=%d game_started=false'%len(checks))
if __name__=='__main__':main()
