"""Replay the source-locked FLD0757 return chain, not a rendered game or collision test.

Original scheduler, op202, vector interpolation, and lock counters execute in
Unicorn. Rendering/actor animation, allocation/constructor layout, and completed
dialogue are explicit fixture boundaries. Candidate mode substitutes only the
Z argument at the native position setter boundary; the compiled production hook
and its admission guards have a separate native CALL-site fixture.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from replay_native_title import NativeTitle, BASE, STOP, SHIM, _require
from resource_field import parse
from resource_field_script import parse as parse_script

FIELD_SHAS = frozenset(['7b92ac0c7fe82aa2d63761c6442ff40f43c0b947644e4f03ea3b48e868b91a87',
                        '13d92e10cddf9bb490bbcfd76c81cf6b7c90b12afebc34a7dd1ba3fd6dff21cf'])
D, S, A, PLANS, SLOTS, ARGS, OBJS, MOVER = (0x20005000,0x20009000,0x20006000,
                                          0x2000c000,0x20010000,0x2000e000,0x2000b000,0x20007000)
# Two actual WRD17 horizontal stair-face centroids; visual geometry is not collision metadata.
STAIR_POINTS = [(258.504368329,-475.699957132,-116.422697488),
                (242.002729485,-482.366624832,-121.447798101)]


class FieldReturn(NativeTitle):
    def __init__(self, image, field, candidate=False):
        _require(hashlib.sha256(field).hexdigest() in FIELD_SHAS,'Unsupported full Field0757 digest')
        super().__init__(image)
        script = parse_script(field)
        _require(len(script['events'])==4 and script['events'][2]['actions'][1]['offset']==0xcac,
                 'Unexpected Field0757 event layout')
        self.events=[];self.candidate=candidate;self.z_writes=0
        self.cpu.mem_map(SLOTS,0x10000)
        # Owned cdecl sqrt(double) and memset(void*,int,size_t) ABI shims.
        self.cpu.mem_write(SHIM+0x100,bytes.fromhex('dd442404d9fac3'))
        self.cpu.mem_write(SHIM+0x120,bytes.fromhex('578b7c240889fa8b44240c8b4c2410f3aa89d05fc3'))
        self.write(BASE+0xbd2ec,SHIM+0x100);self.write(BASE+0xbd33c,SHIM+0x120)
        prefix=parse(field)
        for p,off,value in [(D,0,BASE+0xc1320),(D,0x54,S),(D,0x34,SLOTS),(D,0x38,150),
                            (D,0x2c,PLANS),(D,0x30,4),(S,0x1560,1),(S,0x155c,0x20008000),
                            (0x20008000,0,A),(A,0x328,0),(S,0x1514,len(prefix['objects'])),
                            (S,0x1518,OBJS),(S,0x156c,2)]:self.write(p+off,value)
        for i,obj in enumerate(prefix['objects']):
            self.write(OBJS+72*i,obj['resource_id'])
            self.cpu.mem_write(OBJS+72*i+12,struct.pack('<3f',*obj['position']))
        for i in range(150):self.write(SLOTS+40*i,-1)
        self.cpu.mem_write(ARGS,field[0xc70:0xdd8])
        for off,value in [(4,ARGS),(0x20,6),(0x14,1),(0,2)]:self.write(PLANS+112+off,value)
        self.write(D+0x50,1)

    def return_(self, argument_bytes, value=0):
        _,esp,eip,eax=self.regs;sp=self.cpu.reg_read(esp)
        self.cpu.reg_write(eip,self.read(sp));self.cpu.reg_write(esp,sp+4+argument_bytes)
        self.cpu.reg_write(eax,value)

    def _instruction(self,cpu,address,size,user):
        if SHIM+0x100<=address<SHIM+0x107 or SHIM+0x120<=address<SHIM+0x135:return
        if address==BASE+0xb8b5a:self.return_(0,MOVER);return
        if address==BASE+0x4f877:
            sp=cpu.reg_read(self.regs[1]);self.cpu.mem_write(MOVER,bytes(0x154))
            self.write(MOVER,BASE+0xbea64)
            self.cpu.mem_write(MOVER+0x128,bytes(cpu.mem_read(sp+4,12)));self.write(MOVER+0xf0,1)
            self.return_(24,MOVER);return
        if address==BASE+0x5a799:self.return_(12);return  # animation-facing boundary
        if address==BASE+0x64e25:
            sp=cpu.reg_read(self.regs[1]);mode=self.read(sp+4)
            self.events.append({'boundary':'actor_animation','mode':mode})
            self.write(A+0x2f0,mode);self.return_(36);return
        if address in [BASE+0x6e246,BASE+0x3f21c,BASE+0x71003,BASE+0x3f235]:
            if address==BASE+0x6e246:
                sp=cpu.reg_read(self.regs[1]);self.write(S+0x156c,self.read(sp+4));self.return_(4)
            else:self.return_(0)
            return
        if address==BASE+0x4efd4:
            # Execute its actual movement step/check; omit parent observer callbacks.
            cpu.reg_write(self.regs[2],BASE+0x4fdea);return
        if address==BASE+0x50d60:self.return_(4);return
        if address==BASE+0x78209:
            self.events.append({'boundary':'dialogue','result':'fixture_completed_not_rendered'})
            cpu.reg_write(self.regs[2],BASE+0x4b6ef);return
        if address==BASE+0x5a773 and self.candidate:
            sp=cpu.reg_read(self.regs[1])
            _require(cpu.reg_read(self.regs[0])==A and self.read(sp)==BASE+0x75c0f,
                     'Unexpected candidate position boundary')
            self.cpu.mem_write(sp+12,bytes(cpu.mem_read(MOVER+0x130,4)));self.z_writes+=1
        super()._instruction(cpu,address,size,user)

    def call(self,offset,args=(),receiver=D):
        ecx,esp,eip,_=self.regs;sp=0x3001f000;self.write(sp,STOP)
        for i,value in enumerate(args):self.write(sp+4+i*4,value)
        self.cpu.reg_write(ecx,receiver);self.cpu.reg_write(esp,sp)
        self.cpu.emu_start(BASE+offset,STOP,timeout=3000000,count=300000)
        _require(self.cpu.reg_read(eip)==STOP and self.cpu.reg_read(esp)==sp+4+len(args)*4
                 and self.read(0)==0xffffffff,'Instruction budget, stack or SEH invariant failed')

    def run(self,start,limit=300):
        self.cpu.mem_write(A+0x154,struct.pack('<3f',*start))
        for tick in range(limit):
            self.call(0x4ba72,(PLANS+112,));self.call(0x4b8ec)
            if self.read(PLANS+112+0x18):
                return dict(completed=True,ticks=tick+1,boundaries=self.events,
                            native_lock=self.read(S+0x1574),field_mode=self.read(S+0x156c),
                            start=list(struct.unpack('<3f',struct.pack('<3f',*start))),
                            end=list(struct.unpack('<3f',self.cpu.mem_read(A+0x154,12))),
                            instructions=self.instructions,candidate_z_writes=self.z_writes)
        raise RuntimeError('Return-event instruction replay did not complete within 300 ticks')


def run(image,field,candidate=False):
    cases=[FieldReturn(image,field,candidate).run(point) for point in STAIR_POINTS]
    for case in cases:
        _require(case['completed'] and case['native_lock']==0 and case['field_mode']==2,
                 'Original event unlock path changed')
        _require(case['end'][2]==(-96.0 if candidate else case['start'][2]),'Unexpected return height')
    return dict(schema=1,engine_sha256=hashlib.sha256(image).hexdigest(),field_sha256=hashlib.sha256(field).hexdigest(),
                candidate=candidate,cases=cases,game_started=False,collision_executed=False,
                dialogue_rendered=False,softlock_reproduced=False,
                finding='native XYZ interpolator height discarded by op202 position writeback')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sample',required=True,type=Path);p.add_argument('--field',required=True,type=Path)
    p.add_argument('--report',required=True,type=Path);p.add_argument('--candidate',action='store_true')
    args=p.parse_args()
    try:
        source=args.sample.resolve(strict=True);field=args.field.resolve(strict=True);out=args.report.resolve()
        if out.exists() or out.is_relative_to(source.parent) or out.is_relative_to(field.parent):
            p.error('Report must be new and outside source directories')
        image=source.read_bytes();raw=field.read_bytes();result=run(image,raw,args.candidate)
        if source.read_bytes()!=image or field.read_bytes()!=raw:raise ValueError('Source changed during replay')
        out.parent.mkdir(parents=True,exist_ok=True)
        with out.open('x',encoding='utf8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    except (ValueError,OSError,RuntimeError) as error:p.error(str(error))
    print('FIELD_RETURN_REPLAY PASS candidate='+str(args.candidate).lower()+' cases=2 native_unlock=unchanged '
          'return_z='+('target' if args.candidate else 'stale')+' collision_executed=false game_started=false')


if __name__=='__main__':main()
