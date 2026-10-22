"""Replay source-locked battle timing comparisons and Space-event routing offline."""
from pathlib import Path
import argparse,hashlib,json
from replay_native_title import NativeTitle,BASE

class BattleReplay(NativeTitle):
 def __init__(self,image):
  super().__init__(image);self.outcome=None;self.mode='window'
 def _instruction(self,cpu,address,size,data):
  if self.mode=='window' and address in (BASE+0xa398e,BASE+0xa3a1f):
   self.outcome=address==BASE+0xa3a1f;cpu.emu_stop();return
  if self.mode=='space' and address==BASE+0x5610e:
   self.outcome=self.read(cpu.reg_read(self.regs[1]));cpu.emu_stop();return
  if self.mode=='space' and address==BASE+0x55275:
   self.outcome=None;cpu.emu_stop();return
  super()._instruction(cpu,address,size,data)
 def window(self,tick,count,interval=10,width=4):
  from unicorn.x86_const import UC_X86_REG_EBP
  bp=0x3001e000;scene=0x20003000
  for a,v in [(bp-0x94,scene),(bp-0x20,interval),(bp-0x1c,width),(scene+0x1ddc,count),(scene+0x1de0,tick)]:self.write(a,v)
  self.cpu.reg_write(UC_X86_REG_EBP,bp);self.cpu.reg_write(self.regs[1],bp-0x200)
  self.cpu.emu_start(BASE+0xa394b,BASE+0xa3a20,count=30)
  if self.outcome is None:raise ValueError('Window replay did not finish')
  return self.outcome
 def space(self,counter):
  from unicorn.x86_const import UC_X86_REG_EBP
  self.mode='space';bp=0x3001e000;gui=0x20001000;table=0x20004000
  for a,v in [(bp-8,gui),(gui,table),(table+0x10c,BASE+0x560fe),(BASE+0xf1c9c+32*4,counter)]:self.write(a,v)
  self.cpu.reg_write(UC_X86_REG_EBP,bp);self.cpu.reg_write(self.regs[1],bp-0x100)
  self.cpu.emu_start(BASE+0x55258,BASE+0x56114,count=80)
  return self.outcome

def verify(image):
 probe=BattleReplay(image)
 guards={0xa0b8d:'e80324f6ff8b45fc',0xa1711:'8b88e01d000083c101',0xa0c13:'558bec51894dfc',
         0x8b153:'c70044160c52',0x47256:'c70200e20b52',0x472c7:'898240010000',0x3de42:'c7002cda0b52',
         0x3dfd0:'89515c',0x3e021:'89485c',0x3a244:'c701f4d90b52',0x3cd81:'c70114da0b52'}
 for rva,expected in guards.items():
  if bytes(probe.cpu.mem_read(BASE+rva,len(bytes.fromhex(expected))))!=bytes.fromhex(expected):raise ValueError(f'Native source guard drift {rva:x}')
 if probe.read(BASE+0xc196c)!=BASE+0xa0c13:raise ValueError('Battle draw vtable mismatch')
 cases=[]
 for count in (1,2):
  for tick in range(count*10-1,count*10+5):
   result=BattleReplay(image).window(tick,count)
   if result!=(count*10<=tick<count*10+4):raise ValueError('Native timing comparison changed')
   cases.append(dict(tick=tick,count=count,accepted=result))
 routes={str(c):BattleReplay(image).space(c) for c in (0,1,2,-1)}
 if routes!={'0':None,'1':19,'2':None,'-1':None}:raise ValueError('Native Space-down event mismatch')
 return dict(engine_sha256=hashlib.sha256(image).hexdigest(),cases=cases,space_routes=routes,source_guards={hex(k):v for k,v in guards.items()},game_started=False,game_dll_loaded=False,limits=['Comparison/Space-event instructions only, not the full battle or render loop.','No physical-controller or rendered-timing acceptance.'])
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--sample',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
 if a.report.resolve()==a.sample.resolve():p.error('Report must differ from input')
 r=verify(a.sample.read_bytes());a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8')
 print('BATTLE_NATIVE_REPLAY PASS windows=12 space_down_event=0x13 held_release=ignored dll_loaded=false game_started=false')
