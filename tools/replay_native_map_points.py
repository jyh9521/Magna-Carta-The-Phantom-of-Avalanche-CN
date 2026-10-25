"""Source-locked exit-condition and Field-transition instruction replay.

Executes selected x86 instructions in Unicorn with owned scene/actor/region
records. Scene cleanup and allocation are explicit boundaries; the transition
executor, game entry points, rendering and real event prerequisites never run.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from replay_native_title import BASE, STOP, NativeTitle, _require

SCENE, REGION, ACTOR0, ACTOR1, ACTORS, MANAGER, SLOT, ARGS, ALLOC, GLOBAL, ENTRY = [
    0x20000000+n for n in (0x6000, 0x8000, 0x9000, 0x9400, 0x9800,
                         0xa000, 0xa100, 0xa200, 0xb000, 0xe100, 0xe200)]


class Exits(NativeTitle):
    def __init__(self, image):
        super().__init__(image)
        self.transition, self.effects = None, []
        self.write(MANAGER+0x34, SLOT)
        self.write(MANAGER+0x54, SCENE)
        self.write(SLOT+0x14, ARGS)
        self.write(SCENE+0x1524, 1)
        self.write(SCENE+0x1528, REGION)
        self.write(SCENE+0x1560, 2)
        self.write(SCENE+0x155c, ACTORS)
        self.write(ACTORS, ACTOR0)
        self.write(ACTORS+4, ACTOR1)
        self.write(ACTOR0+0x328, 0)
        self.write(ACTOR1+0x328, 1)
        self.write(REGION, 7)
        # Six outward-facing planes for the owned box [-1,+1]^3.
        for index, normal in enumerate(((1,0,0),(-1,0,0),(0,1,0),(0,-1,0),(0,0,1),(0,0,-1))):
            self.cpu.mem_write(REGION+0x70+index*20, struct.pack('<5f', *normal, 0, -1))
        self.write(BASE+0xf2304, GLOBAL)
        self.write(GLOBAL+0x24, ENTRY)

    def _instruction(self, cpu, address, size, user):
        ecx, esp, eip, eax = self.regs
        stack = cpu.reg_read(esp)
        if address in (BASE+0x6e36e, BASE+0x71065, BASE+0xb8b5a):
            if address == BASE+0xb8b5a:
                _require(self.read(stack+4) == 0x20, 'Unexpected allocation size')
                value = ALLOC
                self.effects.append('owned 32-byte allocation')
            else:
                _require(cpu.reg_read(ecx) == SCENE, 'Unexpected scene cleanup receiver')
                value = 0
                self.effects.append(f'scene side effect boundary {address-BASE:#x}')
            cpu.reg_write(eax, value)
            cpu.reg_write(eip, self.read(stack))
            cpu.reg_write(esp, stack+4)
            return
        if address == BASE+0xc9fd:
            self.transition = {'kind': self.read(stack+4), 'target_field': self.read(stack+8)}
            cpu.emu_stop()
            return
        super()._instruction(cpu, address, size, user)

    def call(self, rva, argument):
        ecx, esp, eip, eax = self.regs
        stack = 0x3001f000
        self.write(stack, STOP)
        self.write(stack+4, argument)
        self.cpu.reg_write(esp, stack)
        self.cpu.reg_write(ecx, MANAGER)
        self.cpu.emu_start(BASE+rva, STOP, count=10000)
        if self.transition is None:
            _require(self.cpu.reg_read(eip) == STOP and self.cpu.reg_read(esp) == stack+8,
                     'Condition replay did not restore its ABI')
        return self.cpu.reg_read(eax)

    def condition(self, selector, xyz0, xyz1):
        self.cpu.mem_write(ARGS, struct.pack('<2i', selector, 7))
        for actor, xyz in ((ACTOR0, xyz0), (ACTOR1, xyz1)):
            self.cpu.mem_write(actor+0x154, struct.pack('<3f', *xyz))
        return self.call(0x727e6, ARGS)


def run(image):
    conditions = []
    for selector, xyz0, xyz1, expected in (
            (10000, (0,0,-10), (2,0,-10), 1),
            (10000, (2,0,-10), (0,0,-10), 0),
            (10001, (2,0,-10), (0,0,-10), 1),
            (10001, (0,0,-10), (2,0,-10), 0),
            (9999, (0,0,-10), (0,0,-10), 0),
            (10000, (0,0,0), (0,0,-10), 0)):
        replay = Exits(image)
        actual = replay.condition(selector, xyz0, xyz1)
        _require(actual == expected, 'Native actor-region result differs')
        conditions.append({'selector': selector, 'actor0_xyz': xyz0, 'actor1_xyz': xyz1,
                           'result': actual, 'native_instructions': replay.instructions})
    transitions = []
    for opcode, rva, target in ((4, 0x729b9, 663), (5, 0x72a76, 751)):
        replay = Exits(image)
        replay.cpu.mem_write(ARGS, struct.pack('<3i', target, 7, 8))
        replay.call(rva, 0)
        _require(replay.transition == {'kind': 31, 'target_field': target}, 'Native transition target differs')
        entry = [replay.read(ENTRY+n) for n in (0x14, 0x18, 0x1c)]
        _require(entry == ([1, 7, 8] if opcode == 5 else [0, 0, 0]), 'Native entry-marker routing differs')
        transitions.append({'opcode': opcode, 'transition': replay.transition, 'entry_state': entry,
                            'boundaries': replay.effects, 'native_instructions': replay.instructions})
    return {'schema': 1, 'engine_sha256': hashlib.sha256(image).hexdigest(),
            'conditions': conditions, 'transitions': transitions,
            'source_unchanged': True, 'game_started': False, 'scene_loader_executed': False,
            'not_proven': ['real event prerequisites', 'current exit passability', 'collision or rendering']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists() or args.report.resolve() == args.engine.resolve():
        parser.error('Report must be new and distinct from the engine')
    image = args.engine.read_bytes()
    result = run(image)
    _require(args.engine.read_bytes() == image, 'Engine changed during replay')
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open('x', encoding='utf8') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print('NATIVE_MAP_POINTS PASS conditions=6 transitions=2 actor_ids=0,1 target_parameter=0 '
          'loader=not_executed source_unchanged=true game_started=false')


if __name__ == '__main__':
    main()
