"""Emulate the locked launch function with recording API stubs, not a game process.

Requires pefile 2024.8.26 and Unicorn 2.1.4 in a research environment.
The game module and graphics/audio APIs are never loaded or executed.
"""
import argparse, json, struct
from collections import Counter
from pathlib import Path
import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import UC_X86_REG_ESP, UC_X86_REG_EAX, UC_X86_REG_EIP
from patch_binary_plan import transform

def emulate(raw, disc=False, load_error=False):
    pe=pefile.PE(data=raw)
    if pe.OPTIONAL_HEADER.ImageBase != 0x400000:
        raise ValueError('unexpected PE image base')
    uc=Uc(UC_ARCH_X86,UC_MODE_32)
    size=(pe.OPTIONAL_HEADER.SizeOfImage+4095)&~4095
    uc.mem_map(0x400000,size)
    uc.mem_write(0x400000,pe.get_memory_mapped_image())
    uc.mem_map(0x600000,0x20000)
    uc.mem_map(0x700000,0x100000)
    functions={};counts=Counter();paths=[];game_args=[];result={}
    pops={'GetDriveTypeA':4,'FindFirstFileA':8,'FindClose':4,'LoadLibraryA':4,
          'GetLastError':0,'GetProcAddress':8,'GetModuleHandleA':4,'FreeLibrary':4,
          'MessageBoxA':16,'ExitProcess':4,'TerminateProcess':8}
    for group in pe.DIRECTORY_ENTRY_IMPORT:
        for item in group.imports:
            if not item.name: continue
            name=item.name.decode('ascii');addr=0x700000+len(functions)*0x100
            functions[addr]=name
            uc.mem_write(item.address,struct.pack('<I',addr))
    functions[0x7f0000]='GameMain'
    functions[0x4012b0]='FormatError'
    functions[0x4011bd]='ExitRoutine'
    stop=0x7fff00;esp=0x61f000
    for address in functions:
        if address >= 0x700000:
            uc.mem_write(address,b'\xc3')
    uc.mem_write(stop,b'\xc3')
    uc.mem_write(esp,struct.pack('<5I',stop,0x400000,0,0,10));uc.reg_write(UC_X86_REG_ESP,esp)
    def read32(at):return struct.unpack('<I',uc.mem_read(at,4))[0]
    def text(at):
        b=bytearray()
        for n in range(2048):
            c=uc.mem_read(at+n,1)[0]
            if not c:return b.decode('ascii')
            b.append(c)
        raise ValueError('unterminated stub string')
    def hook(machine,address,size,data):
        if address==stop:
            result['return']=uc.reg_read(UC_X86_REG_EAX);uc.emu_stop();return
        if address not in functions:return
        name=functions[address];counts[name]+=1;stack=uc.reg_read(UC_X86_REG_ESP)
        ret=read32(stack);args=stack+4;value=0;pop=pops.get(name,0)
        if name=='GetDriveTypeA':
            paths.append(text(read32(args)));value=5 if disc else 3
        elif name=='FindFirstFileA':
            path=text(read32(args));assert path=='A:\\MC_03',path
            paths.append(path);value=0x1234 if disc else 0xffffffff
        elif name=='FindClose':assert read32(args)==0x1234;value=1
        elif name=='LoadLibraryA':
            assert text(read32(args))=='MCAlpha.dll';value=0 if load_error else 0x8888
        elif name=='GetLastError':value=126 if load_error else 0
        elif name=='GetProcAddress':
            assert read32(args)==0x8888 and text(read32(args+4))=='_GameMain@16';value=0x7f0000
        elif name=='GetModuleHandleA':assert read32(args)==0;value=0x400000
        elif name=='GameMain':
            row=[read32(args+i*4) for i in range(4)]
            assert row==[0x400000,0x8888,0x408068,10],row
            assert text(row[2])=='/job:51 /file:0'
            game_args.append(row);value=1 if counts[name]==1 else 0;pop=16
        elif name=='FreeLibrary':assert read32(args)==0x8888;value=1
        elif name=='MessageBoxA':value=2
        elif name=='FormatError':
            uc.mem_write(read32(args),b'owned error stub\0');value=16
        elif name in ['ExitProcess','ExitRoutine']:
            result['exit']=read32(args);uc.emu_stop();return
        else:raise ValueError('unexpected API call '+name)
        uc.reg_write(UC_X86_REG_EAX,value)
        uc.reg_write(UC_X86_REG_ESP,stack+4+pop)
        uc.reg_write(UC_X86_REG_EIP,ret)
    uc.hook_add(UC_HOOK_CODE,hook)
    uc.emu_start(0x401000,stop+1,count=100000)
    if not result:raise ValueError('emulator did not reach a declared endpoint')
    return dict(calls=dict(counts),paths=paths,game_args=game_args,result=result,
                authority='controlled_emulation',game_started=False,module_executed=False)

def check(source,plan):
    raw=Path(source).read_bytes();changed=transform(raw,plan)
    baseline=emulate(raw);present=emulate(raw,disc=True);modified=emulate(changed)
    missing=emulate(changed,load_error=True);restored=emulate(transform(changed,plan,True))
    assert baseline['calls']['GetDriveTypeA']==26 and baseline['result']=={'return':1}
    assert not baseline['game_args'] and baseline==restored
    assert present['calls']['FindClose']==1 and len(present['game_args'])==2
    assert modified['result']=={'return':0} and len(modified['game_args'])==2
    assert not any(n in modified['calls'] for n in ['GetDriveTypeA','FindFirstFileA','FindClose','MessageBoxA'])
    assert missing['result']=={'exit':0xffffffff} and missing['calls']['MessageBoxA']==1
    return dict(baseline=baseline,disc_present=present,modified=modified,module_load_failure=missing,rollback=restored)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    p.add_argument('--plan',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();report=check(a.source,json.loads(a.plan.read_text(encoding='utf8')))
    a.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n')
    print('DISC_GATE_MODEL PASS baseline_scan=26 modified_scan=0 game_main_stub_calls=2 reload=preserved load_error=preserved rollback=exact game_started=false')
