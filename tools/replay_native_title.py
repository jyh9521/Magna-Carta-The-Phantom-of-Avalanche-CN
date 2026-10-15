"""Offline replay of a supported native title mouse path; never loads a DLL."""
from __future__ import annotations
import argparse
import hashlib
import json
import struct
from pathlib import Path

SUPPORTED_SHA = '5c701de93af6267b959c49e6927bee525bc0f3c68c8c6f51413515d13809d427'
BASE = 0x52000000
BUTTON = 0x20001000
SECOND = 0x20001800
ROOT = 0x20002000
TITLE = 0x20003000
STOP = 0x60000000
SHIM = 0x60001000
# Owned x87 ABI shim: save control word, truncate ST0 to EDX:EAX, restore it.
# No original CRT code is embedded or loaded.
FTOL_SHIM = bytes.fromhex('83ec10d93c24668b042480cc0c6689442402d96c2402df7c2404d92c248b4424048b54240883c410c3')

class ReplayError(RuntimeError):
    pass

def _require(condition, message):
    if not condition:
        raise ReplayError(message)

class NativeTitle:
    def __init__(self, image: bytes, identifier: int = 0x16d, phase: int = 4):
        if hashlib.sha256(image).hexdigest() != SUPPORTED_SHA:
            raise ValueError('Unsupported MCAlpha image SHA256')
        from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
        from unicorn.x86_const import UC_X86_REG_ECX, UC_X86_REG_ESP, UC_X86_REG_EIP, UC_X86_REG_EAX
        self.regs = UC_X86_REG_ECX, UC_X86_REG_ESP, UC_X86_REG_EIP, UC_X86_REG_EAX
        pe = struct.unpack_from('<I', image, 60)[0]
        opt = pe + 24
        if image[:2] != b'MZ' or image[pe:pe+4] != b'PE\0\0' or struct.unpack_from('<H', image, opt)[0] != 0x10b:
            raise ValueError('Expected PE32 image')
        base = struct.unpack_from('<I', image, opt+28)[0]
        size = struct.unpack_from('<I', image, opt+56)[0]
        if base != BASE or size != 0x10b000:
            raise ValueError('Unsupported preferred base or image size')
        self.cpu = Uc(UC_ARCH_X86, UC_MODE_32)
        self.cpu.mem_map(BASE, size)
        self.cpu.mem_write(BASE, image[:struct.unpack_from('<I', image, opt+60)[0]])
        section = opt + struct.unpack_from('<H', image, pe+20)[0]
        self.executable = []
        for i in range(struct.unpack_from('<H', image, pe+6)[0]):
            pos = section + i*40
            virtual, address, raw, offset = struct.unpack_from('<IIII', image, pos+8)
            if raw:
                self.cpu.mem_write(BASE+address, image[offset:offset+raw])
            if struct.unpack_from('<I', image, pos+36)[0] & 0x20000000:
                self.executable.append((BASE+address, BASE+address+max(virtual, raw)))
        for address, size in [(0, 0x1000), (0x20000000, 0x10000), (0x30000000, 0x20000), (STOP, 0x2000)]:
            self.cpu.mem_map(address, size)
        self.write(0, 0xffffffff)  # Synthetic FS:0 exception-chain sentinel.
        self.cpu.mem_write(SHIM, FTOL_SHIM)
        self.write(BASE+0xbd31c, SHIM)  # Only the version-bound _ftol IAT slot.
        self.write(BASE+0xf220c, 0x20006000)  # Empty synthetic exclusive GUI stack.
        self.write(ROOT, BASE+0xc2340)
        self.write(ROOT+0x1a8, TITLE)
        self.write(TITLE, BASE+0xc22f0)
        self.write(TITLE+0x70, phase)
        self.widget(BUTTON, identifier, 0x20004000, 0x20005000)
        self.requests = []
        self.boundary = None
        self.instructions = 0
        self.shim_calls = 0
        self.cpu.hook_add(UC_HOOK_CODE, self._instruction)

    def write(self, address, value):
        self.cpu.mem_write(address, struct.pack('<I', value & 0xffffffff))

    def read(self, address):
        return struct.unpack('<I', self.cpu.mem_read(address, 4))[0]

    def widget(self, address, identifier, node, rectangle):
        for offset, value in [(0, BASE+0xbee80), (4, identifier), (0x17c, ROOT), (0x160, 1), (0xe8, 1), (0x100, node)]:
            self.write(address+offset, value)
        self.write(node, rectangle)
        for offset, value in enumerate([300, 400, 500, 440]):
            self.write(rectangle+offset*4, value)

    def _instruction(self, cpu, address, size, _):
        ecx, esp, eip, eax = self.regs
        if address == BASE+0xb874a:
            stack = cpu.reg_read(esp)
            receiver, command = cpu.reg_read(ecx), self.read(stack+4)
            if receiver != ROOT:
                raise ReplayError('Unexpected transition receiver')
            self.requests.append(command)
            # Record, never execute the resource/task transition executor.
            cpu.reg_write(eip, self.read(stack))
            cpu.reg_write(esp, stack+8)
            cpu.reg_write(eax, 0)
            return
        if address == BASE+0xb8b5a:
            self.boundary = {'kind': 'allocation', 'size': self.read(cpu.reg_read(esp)+4)}
            cpu.emu_stop()
            return
        if SHIM <= address < SHIM+len(FTOL_SHIM):
            self.shim_calls += address == SHIM
            return
        if not any(start <= address < end for start, end in self.executable):
            raise ReplayError(f'Unexpected execution outside image code: {address:#x}')
        self.instructions += 1

    def dispatch(self, left, x=400, y=420, root=BUTTON):
        ecx, esp, eip, eax = self.regs
        for offset, value in [(0xf20b0, x), (0xf20a8, y), (0xf20ac, x), (0xf20a4, y), (0xf1c9c+4, left), (0xf1c9c+8, 0)]:
            self.write(BASE+offset, value)
        self.boundary = None
        stack = 0x3001f000
        self.write(stack, STOP)
        self.cpu.reg_write(esp, stack)
        self.cpu.reg_write(ecx, root)
        self.cpu.emu_start(BASE+0x557ee, STOP, timeout=500000, count=20000)
        if self.boundary:
            return {'boundary': self.boundary}
        if self.cpu.reg_read(eip) != STOP or self.cpu.reg_read(esp) != stack+4 or self.read(0) != 0xffffffff:
            raise ReplayError('Instruction budget, stack balance or SEH restoration failed')
        return {'return': self.cpu.reg_read(eax), 'pressed': self.read(BUTTON+0x19c)}


def run_replay(image: bytes):
    cases = []
    total = 0
    def record(name, replay, **evidence):
        nonlocal total
        total += replay.instructions
        cases.append({'name': name, 'native_instructions': replay.instructions, 'ftol_shim_calls': replay.shim_calls, **evidence})
    for identifier, command in [(0x16c, 6), (0x16d, 7), (0x16e, 9), (0x16f, 11)]:
        n = NativeTitle(image, identifier)
        _require(n.dispatch(1)['pressed'] == 1 and not n.requests, "Native replay invariant failed")
        _require(n.dispatch(2)['pressed'] == 1 and not n.requests, "Native replay invariant failed")
        release = n.dispatch(-1)
        if identifier == 0x16c:
            _require(release == {'boundary': {'kind': 'allocation', 'size': 0x13c}} and not n.requests, "Native replay invariant failed")
            record('start_release_resource_boundary', n, transition_request='not_reached', boundary=release['boundary'])
        else:
            _require(n.requests == [command] and release['pressed'] == 0, "Native replay invariant failed")
            n.dispatch(0)
            _require(n.requests == [command], "Native replay invariant failed")
            record(f'title_{identifier:x}_press_hold_release_idle', n, transition_requests=n.requests)
    for phase in range(4):
        for identifier in range(0x16c, 0x170):
            n = NativeTitle(image, identifier, phase)
            n.dispatch(-1)
            _require(not n.requests and n.boundary is None, "Native replay invariant failed")
            record(f'phase_{phase}_rejects_{identifier:x}', n)
    for field, value in [(0x160, 0), (0xe8, 0), (0x164, 2)]:
        n = NativeTitle(image)
        n.write(BUTTON+field, value)
        _require(n.dispatch(1)['return'] == 0, "Native replay invariant failed")
        _require(n.dispatch(-1)['return'] == 0 and not n.requests, "Native replay invariant failed")
        record(f'admission_{field:x}_{value}', n)
    for selected in [BUTTON, SECOND]:
        n = NativeTitle(image)
        n.write(BUTTON+0x164, 2)
        n.write(0x20006000+0x38, 1)
        n.write(0x20006000+0x3c, 0x20006100)
        n.write(0x20006100, selected)
        n.dispatch(-1)
        _require(n.requests == ([7] if selected == BUTTON else []), "Native replay invariant failed")
        record('exclusive_exact_top' if selected == BUTTON else 'exclusive_rejects_sibling', n, admitted=selected == BUTTON)
    for x, y, inside in [(300,400,True), (500,440,True), (299,420,False), (501,420,False), (400,399,False), (400,441,False)]:
        n = NativeTitle(image)
        n.dispatch(-1, x, y)
        _require(n.requests == ([7] if inside else []), "Native replay invariant failed")
        record(f'hit_{x}_{y}', n, inside=inside)
    n = NativeTitle(image)
    n.cpu.mem_write(BUTTON+0x24, struct.pack('<ff', 10.75, 20.75))
    n.dispatch(-1, 310, 420)
    _require(n.requests == [7], "Native replay invariant failed")
    record('fractional_offset_ftol', n)
    n = NativeTitle(image)
    n.write(ROOT+0x18, BUTTON)
    n.write(BUTTON+0x10, SECOND)
    n.write(BUTTON+0x160, 0)
    n.widget(SECOND, 0x16e, 0x20004100, 0x20005100)
    n.dispatch(-1, root=ROOT)
    _require(n.requests == [9], "Native replay invariant failed")
    record('disabled_first_child_continues_to_second', n)
    return {'schema': 1, 'sample_sha256': SUPPORTED_SHA, 'cases': cases, 'native_instructions': total,
            'native_bytes_emulated': True, 'game_dll_loaded': False, 'game_started': False,
            'boundaries': ['owned _ftol ABI shim', 'transition request recorder', 'start allocation stop'],
            'not_proven': ['actual controller', 'rendered pointer or highlight', 'real resource loading or transitions']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample', type=Path, required=True)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    if args.report and (args.report.resolve() == args.sample.resolve() or
                        (args.report.exists() and args.report.samefile(args.sample))):
        parser.error('Report must differ from the sample path')
    image = args.sample.read_bytes()
    report = run_replay(image)
    if hashlib.sha256(args.sample.read_bytes()).hexdigest() != SUPPORTED_SHA:
        raise ReplayError('Sample changed during replay')
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')
    print(f"NATIVE_TITLE_REPLAY PASS cases={len(report['cases'])} instructions={report['native_instructions']} native_bytes_emulated=true game_dll_loaded=false start=allocation_boundary transitions=not_run game_started=false")

if __name__ == '__main__':
    main()
