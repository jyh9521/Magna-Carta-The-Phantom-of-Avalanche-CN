"""Read-only dump tail regression; copies bytes into Unicorn, never loads a DLL."""
from pathlib import Path
import argparse, hashlib, json, mmap, struct

def sha(p):
 with open(p,'rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def validate_report(report, inputs):
 for source in inputs:
  if report.resolve()==source.resolve() or (report.exists() and report.samefile(source)):
   raise ValueError('Report must differ from all source inputs')

def disasm(cs,raw,base):
 return [dict(address=hex(i.address),mnemonic=i.mnemonic,operands=i.op_str) for i in cs.disasm(raw,base)]

def replay(d,cs,regs,start,stop,new_pe=None,new_image=None,local_bindings=()):
 cpu=uc.Uc(uc.UC_ARCH_X86,uc.UC_MODE_32);pages=set();reads=[];invalids=[];trace=[];contracts=[]
 new_base=0x70010000
 ranges=[]
 if new_pe:
  ranges=[(new_base+s.VirtualAddress,new_base+s.VirtualAddress+max(s.Misc_VirtualSize,s.SizeOfRawData)) for s in new_pe.sections if s.Characteristics&0x20000000]
 def raw_page(base):
  raw=bytearray(d.read(base,4096))
  for low,high in ranges:
   lo,hi=max(base,low),min(base+4096,high)
   if hi>lo:raw[lo-base:hi-base]=new_image[lo-new_base:hi-new_base]
  return bytes(raw)
 def page(a):
  base=a&~4095
  if base not in pages:cpu.mem_map(base,4096);cpu.mem_write(base,raw_page(base));pages.add(base)
 def invalid(cpu,access,address,size,value,user):
  try:
   if address<4096:raise ValueError('Captured null access')
   for b in range(address&~4095,((address+size-1)&~4095)+1,4096):page(b)
   return True
  except ValueError:
   invalids.append(dict(access=access,address=hex(address),size=size,eip=hex(cpu.reg_read(UC_X86_REG_EIP))))
   return False
 cpu.hook_add(uc.UC_HOOK_MEM_UNMAPPED,invalid)
 cpu.mem_map(0,4096);pages.add(0);cpu.mem_write(0,struct.pack('<I',0xffffffff))
 # Keep zero page unmapped for the actual phase dereference. FS:[0] is not
 # touched in this tail: helper/readable are ordinary non-SEH functions.
 cpu.mem_unmap(0,4096);pages.remove(0)
 regids={'edi':UC_X86_REG_EDI,'esi':UC_X86_REG_ESI,'ebx':UC_X86_REG_EBX,'edx':UC_X86_REG_EDX,'ecx':UC_X86_REG_ECX,'eax':UC_X86_REG_EAX,'ebp':UC_X86_REG_EBP,'eip':UC_X86_REG_EIP,'esp':UC_X86_REG_ESP}
 for name,reg in regids.items():cpu.reg_write(reg,regs[name])
 for address,value in local_bindings:
  page(address);cpu.mem_write(address,struct.pack('<I',value))
 object_p=regs['edi'];query=struct.unpack('<I',d.read(new_base+0x53178,4))[0]
 def code(cpu,address,size,user):
  if address==query:
   sp=cpu.reg_read(UC_X86_REG_ESP);ret,p,out,n=struct.unpack('<IIII',cpu.mem_read(sp,16));info=d.memory_region(p)
   contracts.append(dict(name='VirtualQuery',input=hex(p),length=n,source='snapshot MEMORY_INFO, not live fault-time query'))
   if info:
    data=struct.pack('<7I',int(info['base'],16),int(info['allocation_base'],16),int(info['allocation_protect'],16),int(info['size'],16),int(info['state'],16),int(info['protect'],16),int(info['type'],16));cpu.mem_write(out,data);cpu.reg_write(UC_X86_REG_EAX,28)
   else:cpu.reg_write(UC_X86_REG_EAX,0)
   cpu.reg_write(UC_X86_REG_ESP,sp+16);cpu.reg_write(UC_X86_REG_EIP,ret);return
  i=next(cs.disasm(cpu.mem_read(address,size),address));trace.append(dict(eip=hex(address),mnemonic=i.mnemonic,operands=i.op_str,esi=hex(cpu.reg_read(UC_X86_REG_ESI))))
 def read(cpu,access,address,size,value,user):
  if address==object_p+0x190:reads.append(dict(address=hex(address),value=struct.unpack('<I',cpu.mem_read(address,4))[0],eip=hex(cpu.reg_read(UC_X86_REG_EIP))))
 cpu.hook_add(uc.UC_HOOK_CODE,code);cpu.hook_add(uc.UC_HOOK_MEM_READ,read)
 try:
  page(start);cpu.emu_start(start,stop,count=30000);error=None
 except uc.UcError as exc:error=str(exc)
 return dict(start=hex(start),stop=hex(stop),reached_stop=cpu.reg_read(UC_X86_REG_EIP)==stop,error=error,invalids=invalids,phase_reads=reads,trace=trace,external_contracts=contracts,stack_bindings=[dict(address=hex(a),value=hex(v),source='Captured EDI object identity rebound to newly compiled volatile local') for a,v in local_bindings])

def main():
 p=argparse.ArgumentParser();p.add_argument('--dump',type=Path,required=True);p.add_argument('--old',type=Path,required=True);p.add_argument('--new',type=Path,required=True);p.add_argument('--analysis',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
 validate_report(a.report,(a.dump,a.old,a.new,a.analysis))
 global capstone, pefile, uc
 import capstone, pefile, unicorn as uc
 from unicorn import x86_const
 globals().update({name:value for name,value in vars(x86_const).items() if name.startswith('UC_X86_')})
 from inspect_minidump import Dump
 identity={str(x):sha(x) for x in (a.dump,a.old,a.new)}
 analysis=json.loads(a.analysis.read_text());earlier=analysis['snapshot_threads'][0]['earlier_contexts'][0];regs={k:int(v,16) for k,v in earlier['registers'].items()}
 assert regs['esi']==0 and regs['edi']==0x1f9649f8 and regs['eip']==0x7003a52c
 cs=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_32);cs.detail=True
 old=pefile.PE(str(a.old));old.relocate_image(0x70010000);new=pefile.PE(str(a.new));new.relocate_image(0x70010000);image=new.get_memory_mapped_image();base=0x70010000
 # The production originalTick global retains its source-locked native RVA.
 needle=b'\xff\x15'+struct.pack('<I',base+0x1f2fa0)
 sites=[]
 for sec in new.sections:
  if sec.Characteristics&0x20000000:
   raw=bytes(image[sec.VirtualAddress:sec.VirtualAddress+sec.Misc_VirtualSize]);at=0
   while True:
    at=raw.find(needle,at)
    if at<0:break
    sites.append(base+sec.VirtualAddress+at);at+=6
 assert len(sites)==2,sites
 tail=sites[1]+6;ins=list(cs.disasm(image[tail-base:tail-base+64],tail));helpercall=next(i for i in ins if i.mnemonic=='call' and i.operands[0].type==capstone.x86.X86_OP_IMM)
 helper=helpercall.operands[0].imm;bindings=[]
 for i in ins:
  if i.address>=helpercall.address:break
  for op in i.operands:
   if op.type==capstone.x86.X86_OP_MEM and op.mem.base==capstone.x86.X86_REG_EBP:
    bindings.append((regs['ebp']+op.mem.disp,regs['edi']))
 assert bindings,'New tail must reload preserved object from an explicit stack local'
 with a.dump.open('rb') as f,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as m:
  d=Dump(m)
  assert d.read(regs['eip'],3)==b'\x83\x3e\x06'
  assert d.read(0x7003a516,0x30)==old.get_data(0x2a516,0x30),'Original module tail differs from captured executable bytes'
  old_result=replay(d,cs,regs,0x7003a516,0x7003a5f0)
  new_result=replay(d,cs,regs,tail,helpercall.address+helpercall.size,new,image,bindings)
  saved=struct.unpack('<I',d.read(regs['ebp']-0x18c,4))[0]
 assert old_result['invalids'] and old_result['invalids'][-1]['address']=='0x0',old_result
 assert new_result['reached_stop'] and not new_result['invalids'] and new_result['phase_reads'],new_result
 assert all(sha(Path(path))==digest for path,digest in identity.items()),'Read-only input drift'
 report=dict(schema=1,identities=identity,captured=earlier,old_saved_field_pointer=hex(saved),old=old_result,new=new_result,new_production_tail=disasm(cs,image[tail-base:helpercall.address-base+helpercall.size],tail),new_finish_function_entry=hex(helper),boundaries=['Old tail resumes captured ESI=0/EDI=valid object and captured stack after native update.','New tail uses current compiled bytes; its new volatile-local stack slot is explicitly rebound from captured EDI, not claimed to be a preexisting new-build frame.','Only VirtualQuery uses snapshot MEMORY_INFO contract; native update is not rerun in this fault-tail slice.','No callback clobber is invented in this replay. Deepest origin of captured ESI corruption remains unknown.','Phase snapshot is 2. Voice phase6 purge equivalence belongs to separate production callback tests.'],game_started=False,process_attached=False)
 a.report.write_text(json.dumps(report,indent=2)+'\n');print('CAPTURED_DIALOGUE_TAIL PASS old=null_read new=compiled_phase_read phase=2 esi_zero=captured deepest_origin=unknown game_started=false')
if __name__=='__main__':main()
