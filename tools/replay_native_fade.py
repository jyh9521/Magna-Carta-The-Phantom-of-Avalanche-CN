"""Replay the native scene-254 opening curtain, not a displayed game frame.

The original fade tick and mover execute. Input/owner notifications are empty
owned boundaries; there is no GPU draw, resource construction or game entry.
A paused negative control demonstrates a held opaque curtain, not a captured
cause of the player's black screen.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from replay_native_title import NativeTitle, BASE, SHIM, STOP, _require
from resource_field_script import parse

FADER=0x23000000
MOVER=0x23001000
BOX=0x23002000
OWNER=0x23003000
VTABLE=0x23004000


class NativeFade(NativeTitle):
    def __init__(self, image, frames, paused=False):
        super().__init__(image)
        self.cpu.mem_map(FADER,0x10000)
        self.cpu.mem_write(SHIM+0x100,bytes.fromhex('dd442404d9fac3'))
        self.write(BASE+0xbd2ec,SHIM+0x100)
        for at,value in [(FADER,BASE+0xbf270),(FADER+0x194,BOX),(FADER+0x198,MOVER),
                (FADER+0xec,OWNER),(FADER+0xe8,1),(FADER+0x164,1),
                (FADER+0xd8,-1 if paused else 0),(MOVER,BASE+0xbea64),
                (MOVER+0xec,OWNER),(MOVER+0xe8,1),(OWNER,VTABLE),
                (VTABLE+4,BASE+0x37690),(VTABLE+8,BASE+0x02b16),
                (BOX+0x1b8,3),(BOX+0x1bc,100)]:self.write(at,value)
        self.cpu.mem_write(MOVER+0x128,struct.pack('<3f',100,0,0))
        self.call(0x4facc,(*self.words((0.,0.,0.)),frames,*self.words((0.,)),2),MOVER)

    @staticmethod
    def words(values):return struct.unpack('<'+'I'*len(values),struct.pack('<'+'f'*len(values),*values))

    def _instruction(self,cpu,address,size,user):
        if SHIM+0x100<=address<SHIM+0x107:return
        # The native mover's general parent observer is outside this replay.
        # Preserve its actual movement, completion and fade-percentage code.
        if address==BASE+0x4efd4:
            cpu.reg_write(self.regs[2],BASE+0x4fdea);return
        super()._instruction(cpu,address,size,user)

    def call(self,rva,args=(),receiver=FADER):
        ecx,esp,eip,eax=self.regs;sp=0x3001f000;self.write(sp,STOP)
        for i,value in enumerate(args):self.write(sp+4+i*4,value)
        self.cpu.reg_write(ecx,receiver);self.cpu.reg_write(esp,sp)
        self.cpu.emu_start(BASE+rva,STOP,timeout=2000000,count=200000)
        _require(self.cpu.reg_read(eip)==STOP and self.cpu.reg_read(esp)==sp+4+len(args)*4
            and self.read(0)==0xffffffff,'Native fade budget/stack/SEH invariant')
        return self.cpu.reg_read(eax)

    def run(self,ticks):
        rows=[]
        for i in range(ticks):
            self.call(0x5786c)
            rows.append(dict(tick=i+1,percentage=self.read(BOX+0x1bc),
                complete=self.read(FADER+0x190),phase=self.read(FADER+0x19c),
                mover_active=self.read(MOVER+0xf0)))
        return rows


def replay(image,field,paused=False):
    script=parse(field)
    command=next(c for c in script['events'][1]['actions'] if c['opcode']==502)
    _require(command['parameters'][:5]==[8,30,0,0,0], 'Unsupported scene-opening curtain')
    frames=command['parameters'][1]+1
    n=NativeFade(image,frames,paused)
    rows=n.run(frames*2)
    expected=100 if paused else 0
    _require(rows[-1]['percentage']==expected,'Unexpected native fade result')
    _require(rows[-1]['complete']==(0 if paused else 1),'Unexpected native completion flag')
    return dict(schema=1,engine_sha256=hashlib.sha256(image).hexdigest(),
        field_sha256=hashlib.sha256(field).hexdigest(),paused_negative_control=paused,
        frames=frames,ticks=rows,native_instructions=n.instructions,
        rendered=False,game_started=False,player_black_screen_reproduced=False,
        boundaries=['empty_owner_notifications','no_mover_parent_observer','no_GPU_or_resource_construction'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--engine',type=Path,required=True)
    p.add_argument('--field',type=Path,required=True)
    p.add_argument('--paused-negative',action='store_true')
    a=p.parse_args();print(json.dumps(replay(a.engine.read_bytes(),a.field.read_bytes(),a.paused_negative),indent=2))


if __name__=='__main__':main()
