"""Replay original cursor preparation in CPU memory, stopping before graphics APIs."""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
from pathlib import Path
from replay_native_title import NativeTitle, BASE, STOP, SUPPORTED_SHA, ReplayError, _require

CURSOR = 0x20007000
OTHER = 0x20007800


class NativeCursor(NativeTitle):
    def __init__(self, image):
        super().__init__(image)
        self.stop_at_matrix = False
        self.stop_at_render = False
        self.matrix_receiver = None
        for obj in [CURSOR, OTHER]:
            self.write(obj, BASE+0xbe374)
        self.write(BASE+0xf2388, CURSOR)
        self.write(BASE+0xf235c, CURSOR)
        self.write(BASE+0xf2360, OTHER)

    def _instruction(self, cpu, address, size, user):
        if (self.stop_at_matrix and address == BASE+0x4846b) or (self.stop_at_render and address == BASE+0x48445):
            self.matrix_receiver = cpu.reg_read(self.regs[0])
            cpu.emu_stop()
            return
        super()._instruction(cpu, address, size, user)

    def invoke(self, rva, *arguments, matrix_boundary=False, render_boundary=False):
        ecx, esp, eip, eax = self.regs
        stack = 0x3001f000
        self.write(stack, STOP)
        for index, value in enumerate(arguments):
            self.write(stack+4+index*4, value)
        self.cpu.reg_write(esp, stack)
        self.stop_at_matrix = matrix_boundary
        self.stop_at_render = render_boundary
        self.matrix_receiver = None
        self.cpu.emu_start(BASE+rva, STOP, timeout=500000, count=20000)
        if matrix_boundary or render_boundary:
            boundary = 0x4846b if matrix_boundary else 0x48445
            _require(self.cpu.reg_read(eip) == BASE+boundary and self.matrix_receiver == self.read(BASE+0xf2388),
                     'Cursor must reach the requested preparation boundary with the current object')
        else:
            _require(self.cpu.reg_read(eip) == STOP and self.cpu.reg_read(esp) == stack+4,
                     'Cursor call did not return with cdecl stack balance')
        _require(self.read(0) == 0xffffffff, 'Cursor call corrupted synthetic SEH chain')


def run_replay(image):
    cases = []
    instructions = 0
    for x, y in [(0, 0), (400, 420), (1919, 1079), (3839, 2159), (-10, -20)]:
        n = NativeCursor(image)
        n.write(BASE+0xf20b0, x)
        n.write(BASE+0xf20a8, y)
        n.invoke(0x606eb, matrix_boundary=True)
        expected = (float(x), float(y), struct.unpack('<f', struct.pack('<I', 0xbdcccccc))[0])
        local = struct.unpack('<fff', n.cpu.mem_read(CURSOR+0x24, 12))
        prepared = struct.unpack('<fff', n.cpu.mem_read(CURSOR+0xf4, 12))
        _require(local == expected and prepared == expected, 'Native cursor preparation differs from click coordinates')
        cases.append({'name': f'position_{x}_{y}', 'click': [x, y], 'local_position': local,
                      'prepared_position': prepared, 'boundary': 'before_matrix_external_APIs'})
        instructions += n.instructions
    n = NativeCursor(image)
    n.invoke(0x60735)
    _require(n.read(CURSOR+0x118) == 0xffffffff and n.read(BASE+0xd9c3c) == 0,
             'Native hide must disable current cursor and visibility state')
    cases.append({'name': 'hide', 'render_order': -1, 'visibility': 0})
    n.invoke(0x607b9, 1)
    _require(n.read(BASE+0xf2388) == OTHER and n.read(OTHER+0x118) == 0 and n.read(BASE+0xd9c3c) == 0,
             'Switching hidden cursor must not implicitly show it')
    cases.append({'name': 'hidden_type_switch', 'current': 'other', 'visibility': 0})
    n.invoke(0x60777)
    _require(n.read(OTHER+0x118) == 0 and n.read(BASE+0xd9c3c) == 1,
             'Native show must enable current cursor and visibility state')
    cases.append({'name': 'show', 'render_order': 0, 'visibility': 1})
    n.invoke(0x607b9, 0)
    _require(n.read(BASE+0xf2388) == CURSOR and n.read(CURSOR+0x118) == 0 and
             n.read(OTHER+0x118) == 0xffffffff and n.read(BASE+0xd9c3c) == 1,
             'Visible type switch must hide old object and show new one')
    cases.append({'name': 'visible_type_switch', 'old_render_order': -1, 'current_render_order': 0})
    instructions += n.instructions
    n = NativeCursor(image)
    n.write(CURSOR+0x118, 0xffffffff)
    n.cpu.reg_write(n.regs[0], CURSOR)
    n.invoke(0x48774)
    cases.append({'name': 'hidden_original_render', 'result': 'returns_without_graphics_setup'})
    instructions += n.instructions
    n = NativeCursor(image)
    n.cpu.reg_write(n.regs[0], CURSOR)
    n.invoke(0x48774, render_boundary=True)
    cases.append({'name': 'visible_original_render', 'boundary': 'before_graphics_setup_48445'})
    instructions += n.instructions
    return {'schema': 1, 'sample_sha256': SUPPORTED_SHA, 'cases': cases,
            'native_instructions': instructions, 'native_bytes_emulated': True,
            'graphics_APIs_executed': False, 'game_started': False,
            'not_proven': ['rendered pixels', 'physical controller', 'live cursor visibility state']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample', type=Path, required=True)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if args.report and (args.report.resolve() == args.sample.resolve() or
                        (args.report.exists() and args.report.samefile(args.sample))):
        parser.error('Report must differ from the sample path')
    report = run_replay(args.sample.read_bytes())
    if hashlib.sha256(args.sample.read_bytes()).hexdigest() != SUPPORTED_SHA:
        raise ReplayError('Sample changed during replay')
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')
    print(f"NATIVE_CURSOR_REPLAY PASS cases={len(report['cases'])} click_coordinates=matched native_visibility=preserved graphics_APIs_executed=false game_started=false")


if __name__ == '__main__':
    main()
