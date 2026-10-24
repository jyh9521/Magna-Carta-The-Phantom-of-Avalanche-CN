"""Execute source-locked native point/segment/actor collision on a bounded GID.

The GID tree is materialized as its native ABI without rendering or game startup.
Polygon payloads are not needed by these point/segment routines. The geometry
resource binding and actor offsets must be supplied separately, not invented.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from resource_gid import parse
from replay_native_title import NativeTitle, BASE, STOP, SHIM, _require

TREE = 0x20008000
LEVEL = 0x20009000
GUIDE = 0x2000a000
NODES = 0x21000000
SCENE = 0x22000000
ACTOR = 0x22002000
OUT = 0x22003000
VELOCITY = 0x22003040
REFLECTED = 0x22003080
OFFSETS = 0x22004000


class NativeCollision(NativeTitle):
    def __init__(self, image, geometry):
        super().__init__(image)
        self.geometry = geometry
        n = len(geometry['nodes'])
        self.cpu.mem_map(NODES, ((n*96+4095)//4096)*4096)
        self.cpu.mem_map(SCENE, 0x10000)
        for row in geometry['nodes']:
            at = NODES+row['index']*96
            self.write(at+4, TREE)
            self.write(at+0x44, int(row['leaf']))
            if row['leaf']:
                self.write(at+0x48, row['solid'])
            else:
                self.write(at+8, NODES+row['front']*96)
                self.write(at+12, NODES+row['back']*96)
                self.write(NODES+row['front']*96+0x10, at)
                self.write(NODES+row['back']*96+0x10, at)
                self.cpu.mem_write(at+0x30, struct.pack('<3f', *row['plane'][:3]))
                self.cpu.mem_write(at+0x40, struct.pack('<f', row['plane'][3]))
        for at, value in ((TREE+0x30, NODES+geometry['root']*96),
                (LEVEL, BASE+0xc15ac), (LEVEL+0xf4, GUIDE), (GUIDE+0x120, TREE),
                (SCENE+0x1558, LEVEL)):
            self.write(at, value)
        # Owned cdecl sqrt(double), the sole extra CRT dependency of the solver.
        self.cpu.mem_write(SHIM+0x100, bytes.fromhex('dd442404d9fac3'))
        self.write(BASE+0xbd2ec, SHIM+0x100)

    def _instruction(self, cpu, address, size, user):
        if SHIM+0x100 <= address < SHIM+0x107:
            return
        super()._instruction(cpu, address, size, user)

    def call(self, rva, args=(), receiver=LEVEL):
        ecx, esp, eip, eax = self.regs
        sp = 0x3001f000
        self.write(sp, STOP)
        for i, value in enumerate(args):
            self.write(sp+4+i*4, value)
        self.cpu.reg_write(ecx, receiver)
        self.cpu.reg_write(esp, sp)
        self.cpu.emu_start(BASE+rva, STOP, timeout=3000000, count=1000000)
        _require(self.cpu.reg_read(eip) == STOP and self.cpu.reg_read(esp) == sp+4+len(args)*4
            and self.read(0) == 0xffffffff, 'Native collision budget/stack/SEH invariant')
        return self.cpu.reg_read(eax)

    @staticmethod
    def words(values):
        return struct.unpack('<'+'I'*len(values), struct.pack('<'+'f'*len(values), *values))

    def point(self, position):
        return self.call(0x8a6a4, self.words(position))

    def segment(self, start, end):
        return self.call(0x8a6eb, self.words((*start, *end)))

    def solve(self, position, velocity, offsets=(), elasticity=0.0):
        if len(offsets) > 8:
            raise ValueError('Actor-offset limit')
        self.cpu.mem_write(VELOCITY, struct.pack('<3f', *velocity))
        if offsets:
            self.cpu.mem_write(OFFSETS, b''.join(struct.pack('<3f', *v) for v in offsets))
        args = (OUT, ACTOR, OFFSETS, len(offsets), *self.words(position), REFLECTED,
            VELOCITY, *self.words((elasticity,)), 0)
        result = self.call(0x6ed4e, args, SCENE)
        _require(result == OUT, 'Native vector return pointer')
        read = lambda p:list(struct.unpack('<3f', self.cpu.mem_read(p, 12)))
        return dict(result=read(OUT), velocity_after=read(VELOCITY), reflected=read(REFLECTED))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--engine', type=Path, required=True)
    p.add_argument('--gid', type=Path, required=True)
    p.add_argument('--point', type=float, nargs=3, required=True)
    args = p.parse_args()
    image, data = args.engine.read_bytes(), args.gid.read_bytes()
    geometry = parse(data)
    replay = NativeCollision(image, geometry)
    result = dict(engine_sha256=hashlib.sha256(image).hexdigest(),
        gid_sha256=geometry['source_sha256'], nodes=len(geometry['nodes']),
        point=args.point, native_inside=replay.point(args.point),
        solves=[dict(velocity=v, **replay.solve(args.point, v)) for v in
            ((100,0,0),(-100,0,0),(0,100,0),(0,-100,0))],
        game_started=False, rendered=False, actor_offsets='center_only_not_full_character',
        resource_binding_verified=False)
    if args.engine.read_bytes() != image or args.gid.read_bytes() != data:
        raise ValueError('Source changed')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
