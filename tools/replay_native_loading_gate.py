"""Replay original loading gates offline; does not execute the resource/renderer body."""
import argparse
import hashlib
import json
from pathlib import Path
from replay_native_title import NativeTitle,BASE,STOP,SHIM,_require
from replay_native_gui_parent import SOURCE_SHA

SCENE=0x20008000
NODE=0x20006000
VTABLE=0x20007000
NOTIFY=SHIM+0x600

class Gate(NativeTitle):
    def _instruction(self,cpu,address,size,data):
        if address in (NOTIFY,BASE+0x71085):return
        super()._instruction(cpu,address,size,data)

    def __init__(self,image):
        if hashlib.sha256(image).hexdigest()!=SOURCE_SHA:raise ValueError('Unsupported complete engine SHA256')
        super().__init__(image)
        self.write(SCENE+0x1568,NODE);self.write(NODE,VTABLE);self.write(VTABLE+0x10,NOTIFY)

    def run(self,mode=7,flag=0,paused=0,counter=0,exit_check=False):
        from unicorn import UC_HOOK_CODE
        ecx,esp,eip,eax=self.regs;stack=0x3001f000;events=[]
        for offset,value in [(0x156c,mode),(0x1730,flag),(0x28,paused),(0x2c,0),(0x1734,counter)]:self.write(SCENE+offset,value)
        self.write(stack,STOP);self.cpu.reg_write(esp,stack);self.cpu.reg_write(ecx,SCENE)
        def hook(cpu,address,size,data):
            if address not in (NOTIFY,BASE+0x71085):return
            _require(cpu.reg_read(ecx)==(NODE if address==NOTIFY else SCENE),'Unexpected native receiver')
            events.append('root_draw_boundary' if address==NOTIFY else 'original_loading_71085_boundary')
            sp=cpu.reg_read(esp);cpu.reg_write(eip,self.read(sp));cpu.reg_write(esp,sp+4)
        h=self.cpu.hook_add(UC_HOOK_CODE,hook)
        try:self.cpu.emu_start(BASE+(0x6e697 if exit_check else 0x6b3bc),STOP,timeout=500000,count=3000)
        finally:self.cpu.hook_del(h)
        _require(self.cpu.reg_read(eip)==STOP and self.cpu.reg_read(esp)==stack+4,'Native gate budget/stack mismatch')
        _require(self.read(SCENE+0x1730)==flag and self.read(SCENE+0x156c)==mode,'Unexpected mode/flag mutation')
        return dict(events=events,exit_result=self.cpu.reg_read(eax) if exit_check else None,counter=self.read(SCENE+0x1734))

def verify(image):
    cases={}
    for name,mode,flag,paused,expected in [('ordinary_exit_flag0',7,0,0,False),('native_loading_flag1',7,1,0,True),('active_scene',2,1,0,False),('paused_root',7,1,1,False)]:
        r=Gate(image).run(mode,flag,paused)
        _require(('original_loading_71085_boundary' in r['events'])==expected,name+' gate mismatch')
        cases[name]=r
    for count,result,after in [(0,1,0xffffffff),(1,1,0),(2,0,1)]:
        r=Gate(image).run(counter=count,exit_check=True)
        _require(r['exit_result']==result and r['counter']==after,'Exit countdown mismatch')
        cases['exit_counter'+str(count)]=r
    return dict(schema=1,engine_sha256=SOURCE_SHA,cases=cases,game_started=False,game_dll_loaded=False,
                native_loading_body_executed=False,actual_scene_delay_reproduced=False,
                limits=['Original gate and countdown instructions only; owned scene memory.',
                        'Loading and root rendering use explicit ABI boundaries.',
                        'No on-screen presentation or real transition timing is measured.'])

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--sample',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists() or not a.report.parent.is_dir():p.error('New report in existing directory required')
    r=verify(a.sample.read_bytes())
    with a.report.open('x',encoding='utf8') as f:json.dump(r,f,indent=2);f.write('\n')
    print('NATIVE_LOADING_GATE PASS cases=7 flag0=no_loading flag1=original_71085 exit_counter0=immediate game_started=false')
