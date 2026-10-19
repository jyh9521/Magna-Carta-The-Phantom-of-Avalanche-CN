"""Original Field frame-loop/gate replay; rendering, clock update and gate arming are explicit ABI boundaries."""
import argparse,json
from pathlib import Path
from replay_native_title import NativeTitle,BASE,STOP,SHIM,_require
from replay_native_gui_parent import SOURCE_SHA
import hashlib
SCENE=0x20008000;JOB=0x20003000;NODE=0x20006000;NVT=0x20007000
GUI=0x20004000;GVT=0x20004400;RENDERER=0x20004800;RVT=0x20005000
class Frame(NativeTitle):
    def _instruction(self,cpu,address,size,data):
        if address in self.boundaries or address==BASE+0x631da:return
        super()._instruction(cpu,address,size,data)
    def __init__(self,image):
        if hashlib.sha256(image).hexdigest()!=SOURCE_SHA:raise ValueError('Unsupported complete engine SHA256')
        self.boundaries={};super().__init__(image)
    def run_frame(self,armed):
        from unicorn import UC_HOOK_CODE
        ecx,esp,eip,eax=self.regs;events=[];stack=0x3001f000
        for p,v in [(JOB+12,SCENE),(SCENE,BASE+0xc12bc),(SCENE+0x1c,0),(SCENE+0x156c,2),(SCENE+0x1730,0),(SCENE+0x1734,0),(SCENE+0x1568,NODE),(NODE,NVT),(NVT+0x10,SHIM+0x600),(GUI,GVT),(GVT+0x10,SHIM+0x610),(BASE+0xf220c,GUI),(BASE+0xf1b70,RENDERER),(RENDERER,RVT),(BASE+0xbd058,SHIM+0x620),(BASE+0xbd05c,SHIM+0x630)]:self.write(p,v)
        self.boundaries={SHIM+0x600:('world_draw',0),SHIM+0x610:('gui_draw',0),SHIM+0x620:('clear_queue',0),SHIM+0x630:('render',0),BASE+0x71085:('native_loading_71085',0),BASE+0x0cdc4:('fixed_clock_call',0),BASE+0x1d604:('world_camera',0),BASE+0x1d9d9:('world_projection',0),BASE+0x606eb:('cursor',0),BASE+0x3a180:('frame_finalize',0),BASE+0x0bdbe:('event_pump',0)}
        for i,(offset,name,args) in enumerate([(0x40,'clear_target',4),(0x6c,'white_light',12),(0x288,'identity',0),(0x1a4,'query_depth',8),(0x114,'disable_depth',4),(0xac,'white_color',16),(0x138,'restore_depth',4),(0x14,'present',0)]):
            shim=SHIM+0x700+i*16;self.write(RVT+offset,shim);self.boundaries[shim]=(name,args)
        def hook(cpu,address,size,data):
            if address==BASE+0x631da:
                events.append('before_native_draw')
                if armed:self.write(SCENE+0x1730,1);events.append('arming_boundary')
                return
            if address not in self.boundaries:return
            name,args=self.boundaries[address];events.append(name);sp=cpu.reg_read(esp)
            if name=='fixed_clock_call':
                self.write(SCENE+0x156c,7);self.write(BASE+0xf2280,31)
            if name=='query_depth':self.write(self.read(sp+8),0)
            cpu.reg_write(eax,1 if name in ('present','event_pump') else 0)
            cpu.reg_write(eip,self.read(sp));cpu.reg_write(esp,sp+4+args)
        h=self.cpu.hook_add(UC_HOOK_CODE,hook);self.write(stack,STOP);self.cpu.reg_write(esp,stack);self.cpu.reg_write(ecx,JOB)
        try:self.cpu.emu_start(BASE+0x631a0,STOP,timeout=1000000,count=10000)
        finally:self.cpu.hook_del(h)
        _require(self.cpu.reg_read(eip)==STOP and self.cpu.reg_read(esp)==stack+4,'Original frame loop stack/budget mismatch')
        _require(events.count('present')==1 and events.count('fixed_clock_call')==1,'No synthetic frame or logic tick permitted')
        _require(events.index('white_color')<events.index('present'),'Original UI state restoration precedes present')
        loaded='native_loading_71085' in events
        if armed:_require(loaded and events.index('native_loading_71085')<events.index('render')<events.index('present'),'Native loading must precede normal frame presentation')
        else:_require(not loaded,'Original zero flag must bypass native loading')
        return dict(events=events,loading_before_normal_present=loaded,normal_presents=1,fixed_clock_calls=1,standalone_presents=0,original_loop_executed=True,arming_is_boundary_model=True,native_loading_body_executed=False,rendered_pixels_verified=False,game_started=False)
def verify(image):return dict(schema=1,engine_sha256=SOURCE_SHA,baseline=Frame(image).run_frame(False),modified=Frame(image).run_frame(True),rollback=Frame(image).run_frame(False))
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--sample',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    if a.report.exists():p.error('New report required')
    r=verify(a.sample.read_bytes());a.report.write_text(json.dumps(r,indent=2)+'\n',encoding='utf8');print('NATIVE_LOADING_FRAME PASS original_loop=executed loading_before_normal_present=true presents=1 clock_calls=1 pixels_verified=false game_started=false')
