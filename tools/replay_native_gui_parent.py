"""Offline native replay of a recorded GUI-root bounds fault; never starts/loads a game.

The guard is a replay-only proposal, not a deployed game patch or scene acceptance.
Original native transform/vector-add instructions execute in Unicorn. Two virtual
notifications use explicit owned RET boundaries; no renderer/resources/UI execute.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from replay_native_title import NativeTitle, BASE, STOP, SHIM

SOURCE_SHA='7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e'
ENTRY=0x38afb
SITE=0x38b45
EXPECTED=bytes.fromhex('837a08007472')
ROOT_SLOT=0xf220c
ROOT_VTABLE=0xbd604
ROOT=0x00baef30
CHILD=0x02638cf0
VTABLE=0x20008000
OTHER=0x20007000
TRAMPOLINE=SHIM+0x200
NOTIFY=SHIM+0x180


def trampoline(base=BASE,address=TRAMPOLINE):
    """Guard only the exact live generic UI root; preserve native flags/registers."""
    code=bytearray();labels={};fixups=[]
    def emit(b):code.extend(b)
    def jump(op,target):
        emit(op);fixups.append((len(code),target));emit(bytes(4))
    emit(bytes.fromhex('508b420885c0'));jump(b'\x0f\x84','skip')
    emit(b'\x3b\x05'+struct.pack('<I',base+ROOT_SLOT));jump(b'\x0f\x85','inherit')
    emit(b'\x81\x38'+struct.pack('<I',base+ROOT_VTABLE));jump(b'\x0f\x85','inherit')
    emit(bytes.fromhex('83780402'));jump(b'\x0f\x85','inherit')
    emit(bytes.fromhex('83780800'));jump(b'\x0f\x85','inherit')
    labels['skip']=len(code);emit(bytes.fromhex('58837a0800'));jump(b'\xe9',base+0x38bbd)
    labels['inherit']=len(code);emit(bytes.fromhex('58837a0800'));jump(b'\xe9',base+0x38b4b)
    for pos,target in fixups:
        dest=address+labels[target] if isinstance(target,str) else target
        struct.pack_into('<i',code,pos,dest-(address+pos+4))
    return bytes(code)


class NativeGuiParent(NativeTitle):
    def __init__(self,image,parent='generic_root'):
        if hashlib.sha256(image).hexdigest()!=SOURCE_SHA:raise ValueError('Unsupported full engine SHA256')
        super().__init__(image)
        self.cpu.mem_map(ROOT&~0xfff,0x1000)  # Ends at recorded MEM_RESERVE page0xbaf000.
        self.cpu.mem_map(CHILD&~0xfff,0x2000)
        self.cpu.mem_write(NOTIFY,b'\xc3')
        self.cpu.mem_write(TRAMPOLINE,trampoline())
        self.write(VTABLE+0x28,NOTIFY);self.write(VTABLE+0x2c,NOTIFY)
        self.write(CHILD,VTABLE)
        self.write(ROOT,BASE+ROOT_VTABLE);self.write(ROOT+4,2);self.write(ROOT+8,0)
        self.write(BASE+ROOT_SLOT,ROOT)
        self.cpu.mem_write(CHILD+0x24,struct.pack('<3f',10,20,30))
        self.cpu.mem_write(CHILD+0x40,struct.pack('<3f',2,3,4))
        self.cpu.mem_write(OTHER+0xf4,struct.pack('<3f',100,200,300))
        self.cpu.mem_write(OTHER+0x100,struct.pack('<3f',3,4,5))
        self.write(OTHER,BASE+0xbd934)
        if parent=='generic_root':p=ROOT
        elif parent=='spatial':p=OTHER
        elif parent=='none':p=0
        else:raise ValueError('Unknown parent scenario')
        self.write(CHILD+8,p)
        self.fault=None;self.notifications=0;self.instructions=0
        from unicorn import UC_HOOK_MEM_INVALID
        self.cpu.hook_add(UC_HOOK_MEM_INVALID,self._invalid)
        if bytes(self.cpu.mem_read(BASE+SITE,6))!=EXPECTED:raise ValueError('Native guard site mismatch')

    def _instruction(self,cpu,address,size,_):
        if address==NOTIFY:self.notifications+=1;return
        if (BASE+ENTRY<=address<BASE+0x38bd7 or BASE+0x1e940<=address<BASE+0x1e983
            or TRAMPOLINE<=address<TRAMPOLINE+len(trampoline())):
            self.instructions+=1;return
        raise ValueError('Unexpected instruction outside bounded transform replay: '+hex(address))

    def _invalid(self,cpu,access,address,size,value,_):
        self.fault=dict(instruction=hex(cpu.reg_read(self.regs[2])),address=hex(address),bytes=size)
        return False

    def patched_bytes(self):return b'\xe9'+struct.pack('<i',TRAMPOLINE-(BASE+SITE+5))+b'\x90'

    def patch(self):
        current=bytes(self.cpu.mem_read(BASE+SITE,6))
        if current not in (EXPECTED,self.patched_bytes()):raise ValueError('Patch site drift')
        self.cpu.mem_write(BASE+SITE,self.patched_bytes());self.cpu.ctl_remove_cache(BASE+SITE,BASE+SITE+6)

    def rollback(self):
        if bytes(self.cpu.mem_read(BASE+SITE,6))!=self.patched_bytes():raise ValueError('Rollback site drift')
        self.cpu.mem_write(BASE+SITE,EXPECTED);self.cpu.ctl_remove_cache(BASE+SITE,BASE+SITE+6)

    def run(self):
        from unicorn import UcError
        ecx,esp,eip,eax=self.regs
        self.cpu.reg_write(ecx,CHILD);self.cpu.reg_write(esp,0x3001f000);self.write(0x3001f000,STOP)
        self.fault=None;self.notifications=0
        error=None
        try:self.cpu.emu_start(BASE+ENTRY,STOP,count=1000)
        except UcError as e:error=str(e)
        completed=self.cpu.reg_read(eip)==STOP and self.fault is None and error is None
        return dict(completed=completed,fault=self.fault,emulator_error=error,
                    translation=list(struct.unpack('<3f',self.cpu.mem_read(CHILD+0xf4,12))),
                    scale=list(struct.unpack('<3f',self.cpu.mem_read(CHILD+0x100,12))),
                    parent_unchanged=hex(self.read(CHILD+8)),notifications=self.notifications,
                    stack_balanced=self.cpu.reg_read(esp)==0x3001f004 if completed else None)


def replay(image):
    n=NativeGuiParent(image)
    baseline=n.run();n.patch();modified=n.run();n.rollback();rollback=n.run()
    fault=dict(instruction='0x5201e94f',address='0xbaf024',bytes=4)
    if baseline['fault']!=fault or rollback['fault']!=fault:raise AssertionError('Recorded fault not replayed exactly')
    if not modified['completed'] or modified['translation']!=[10,20,30] or modified['scale']!=[2,3,4] or modified['notifications']!=2:raise AssertionError('Proposal did not preserve local transform/notifications')
    controls={}
    for parent in ('spatial','none'):
        c=NativeGuiParent(image,parent);before=c.run();c.patch();after=c.run();c.rollback();restored=c.run()
        if not before['completed'] or before!=after or before!=restored:raise AssertionError('Control behavior changed')
        controls[parent]=before
    return dict(schema=1,engine_sha256=SOURCE_SHA,baseline=baseline,modified=modified,rollback=rollback,
                controls=controls,guard_original=EXPECTED.hex(),guard_proposal=n.patched_bytes().hex(),
                os_game_started=False,game_dll_loaded=False,scene_transition_verified=False,
                proposal_deployed=False,source_function='GUI transform38afb -> vector addition1e940',
                limits=['Recorded startup GUI fault, not a scene-transition crash.',
                        'Emulated instructions and owned callback RET boundaries, no actual UI/resource load.',
                        'Proposal is confined to this emulator; normal runtime and unified ZIP unchanged.'])

def single(image,mode):
    if mode not in ('baseline','proposal','rollback'):raise ValueError('Unknown replay mode')
    n=NativeGuiParent(image)
    if mode in ('proposal','rollback'):n.patch()
    if mode=='rollback':n.rollback()
    return dict(mode=mode,result=n.run(),original_guard_restored=bytes(n.cpu.mem_read(BASE+SITE,6))==EXPECTED,
                os_game_started=False,game_dll_loaded=False,scene_transition_verified=False,proposal_deployed=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--sample',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    p.add_argument('--mode',choices=('verify','baseline','proposal','rollback'),default='verify');a=p.parse_args()
    if a.report.exists() or not a.report.parent.is_dir():p.error('New report in existing directory required')
    image=a.sample.read_bytes();r=replay(image) if a.mode=='verify' else single(image,a.mode)
    with a.report.open('x',encoding='utf8') as f:json.dump(r,f,indent=2);f.write('\n')
    if a.mode=='verify':
        print('GUI_PARENT_REPLAY PASS original_fault=5201e94f/read_baf024 proposal=local_transform_preserved rollback=exact ordinary_parents=unchanged os_game_started=false scene_transition_verified=false deployed=false')
    else:
        completed=r['result']['completed']
        print('GUI_PARENT_'+a.mode.upper()+' completed='+str(completed).lower()+' original_guard_restored='+str(r['original_guard_restored']).lower()+' os_game_started=false scene_transition_verified=false deployed=false')
        raise SystemExit(0 if completed else 1)
