"""Run the compiled owned collision kernel against the original native BSP oracle.

No DLL entry points, graphics, game process, or invented geometry binding.
Centre-only real-resource cases and owned eight-offset cases remain distinct.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from replay_native_collision import NativeCollision, BASE, LEVEL, TREE, SHIM, STOP, OFFSETS, OUT


class GuardReplay(NativeCollision):
    def __init__(self, image, geometry, kernel):
        super().__init__(image, geometry)
        self.kernel_sha256 = hashlib.sha256(kernel).hexdigest()
        pe = struct.unpack_from('<I', kernel, 60)[0]
        opt = pe+24
        if kernel[:2] != b'MZ' or struct.unpack_from('<H', kernel, opt)[0] != 0x10b:
            raise ValueError('Owned PE32 kernel required')
        self.kbase = struct.unpack_from('<I', kernel, opt+28)[0]
        self.ksize = struct.unpack_from('<I', kernel, opt+56)[0]
        if self.kbase != 0x10000000 or self.ksize > 0x100000:
            raise ValueError('Unexpected owned kernel mapping')
        self.cpu.mem_map(self.kbase, self.ksize)
        self.cpu.mem_write(self.kbase, kernel[:struct.unpack_from('<I', kernel, opt+60)[0]])
        section = opt+struct.unpack_from('<H', kernel, pe+20)[0]
        for i in range(struct.unpack_from('<H', kernel, pe+6)[0]):
            pos = section+i*40
            _, address, size, offset = struct.unpack_from('<IIII', kernel, pos+8)
            if size:
                self.cpu.mem_write(self.kbase+address, kernel[offset:offset+size])
        export = self.kbase+struct.unpack_from('<I', kernel, opt+96)[0]
        functions, names, ordinals = [self.kbase+self.read(export+n) for n in (28,32,36)]
        found = []
        for i in range(self.read(export+24)):
            name = self.kbase+self.read(names+i*4)
            raw = bytes(self.cpu.mem_read(name, 100)).split(b'\0')[0]
            if raw == b'resolveCollisionStep':
                ordinal = struct.unpack('<H', self.cpu.mem_read(ordinals+i*2,2))[0]
                found.append(self.kbase+self.read(functions+ordinal*4))
        if len(found) != 1:
            raise ValueError('Owned compiled kernel export missing')
        self.kernel_entry = found[0]
        self.cpu.mem_write(SHIM+0x500, b'\xc3')
        self.cpu.mem_write(SHIM+0x510, b'\xc3')
        self.query_context = None
        self.native_queries = 0

    def _instruction(self, cpu, address, size, user):
        ecx, esp, eip, eax = self.regs
        if address == SHIM+0x500:
            stack = cpu.reg_read(esp)
            self.query_context = (stack,self.read(stack),bytes(cpu.mem_read(TREE+0x14,28)))
            self.write(stack,SHIM+0x510)
            cpu.reg_write(ecx,LEVEL)
            cpu.reg_write(eip,BASE+0x8a6a4)
            self.native_queries += 1
            return
        if address == SHIM+0x510:
            stack,ret,scratch = self.query_context
            cpu.mem_write(TREE+0x14,scratch)
            cpu.reg_write(esp,stack+4)
            cpu.reg_write(eip,ret)
            self.query_context = None
            return
        if getattr(self,'kbase',0) <= address < getattr(self,'kbase',0)+getattr(self,'ksize',0):
            return
        super()._instruction(cpu,address,size,user)

    def correct(self,before,proposed,offsets=()):
        if len(offsets)>8:
            raise ValueError('Offset limit')
        if offsets:
            self.cpu.mem_write(OFFSETS,b''.join(struct.pack('<3f',*v) for v in offsets))
        args=(*self.words(before),*self.words(proposed),OFFSETS,len(offsets),SHIM+0x500,0,OUT)
        ecx,esp,eip,eax=self.regs
        stack=0x3001f000
        self.write(stack,STOP)
        for i,v in enumerate(args):self.write(stack+4+i*4,v)
        self.cpu.reg_write(esp,stack)
        self.cpu.emu_start(self.kernel_entry,STOP,timeout=15000000,count=4000000)
        if self.cpu.reg_read(eip)!=STOP or self.cpu.reg_read(esp)!=stack+4:
            raise RuntimeError('Owned kernel budget/cdecl stack invariant')
        return dict(status=self.cpu.reg_read(eax),position=list(struct.unpack('<3f',self.cpu.mem_read(OUT,12))))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--kernel',type=Path,required=True)
    p.add_argument('--report',type=Path,required=True)
    a=p.parse_args()
    if a.report.resolve().is_relative_to(a.source.resolve()) or a.report.resolve()==a.kernel.resolve():
        p.error('Report must remain outside resource inputs and separate from the owned kernel')
    from resource_gid import parse
    import random
    image=(a.source/'MCAlpha.dll').read_bytes()
    kernel=a.kernel.read_bytes()
    rng=random.Random(22612)
    cases=[]
    for gid in (28,29,30,31):
        data=(a.source/'Gid'/f'{gid:04}.gid').read_bytes()
        geometry=parse(data)
        n=GuardReplay(image,geometry,kernel)
        pos=1024;count=struct.unpack_from('<I',data,pos)[0];pos+=4;vertices=[]
        for _ in range(count):
            _,_,length=struct.unpack_from('<3I',data,pos);pos+=12
            vertices += [struct.unpack_from('<3f',data,pos+i*32) for i in range(length)]
            pos+=length*32
        match=None
        for _ in range(2000):
            v=rng.choice(vertices)
            start=(v[0]+rng.uniform(-2,2),v[1]+rng.uniform(-2,2),10.)
            if not n.point((start[0],start[1],25.)):continue
            if not any(not n.point((start[0]+dx,start[1]+dy,25.)) for dx,dy in ((2,0),(-2,0),(0,2),(0,-2))):continue
            baseline=[n.solve((start[0],start[1],25.),vel)['result'] for vel in ((100,0,0),(-100,0,0),(0,100,0),(0,-100,0))]
            if any(v != [0.,0.,0.] for v in baseline):raise ValueError('Inside-start native zero behavior differs')
            corrected=n.correct(start,start)
            target=corrected['position']
            if corrected['status']!=2 or n.point((target[0],target[1],target[2]+15)):
                raise ValueError('Compiled correction failed real native oracle')
            blocked=n.correct(target,start)
            q=blocked['position']
            if blocked['status']!=1 or n.point((q[0],q[1],q[2]+15)):
                raise ValueError('Compiled endpoint commit failed native oracle')
            match=dict(gid=gid,gid_sha256=geometry['source_sha256'],start=list(start),native_outward_results=baseline,
                       recovered=corrected,reentry=blocked,native_queries=n.native_queries,
                       actor_offsets='center_only_not_live_character')
            break
        if not match:raise ValueError('No bounded real-geometry case found')
        cases.append(match)
    result=dict(schema=1,engine_sha256=hashlib.sha256(image).hexdigest(),kernel_sha256=hashlib.sha256(kernel).hexdigest(),
                cases=cases,game_started=False,dll_entry_called=False,
                source_geometry_binding='candidate water-temple GIDs, player water-maze identity not confirmed',
                player_ingress_reproduced=False,compiled_kernel_native_oracle_pass=True)
    if (a.source/'MCAlpha.dll').read_bytes()!=image or a.kernel.read_bytes()!=kernel:
        raise ValueError('Replay input changed')
    for case in cases:
        if hashlib.sha256((a.source/'Gid'/f"{case['gid']:04}.gid").read_bytes()).hexdigest()!=case['gid_sha256']:
            raise ValueError('Replay geometry changed')
    result['source_unchanged']=True
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    assert json.loads(a.report.read_text('utf8'))==result
    print('COLLISION_NATIVE PASS cases=4 original_outward=blocked compiled_recovery=clear compiled_reentry=blocked offsets=center_only game_started=false')


if __name__=='__main__':main()
