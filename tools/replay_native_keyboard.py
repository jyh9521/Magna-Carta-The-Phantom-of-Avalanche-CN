"""Version-locked original GUI keyboard replay; records listener events, no game launch."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from replay_native_title import NativeTitle, BASE, BUTTON, ROOT, STOP, SUPPORTED_SHA, ReplayError, _require


class NativeKeyboard(NativeTitle):
    def __init__(self, image):
        super().__init__(image)
        self.events = []

    def _instruction(self, cpu, address, size, user):
        if address == BASE+0xb7ceb:
            ecx, esp, eip, eax = self.regs
            stack = cpu.reg_read(esp)
            _require(cpu.reg_read(ecx) == ROOT and self.read(stack+4) == BUTTON,
                     'Unexpected keyboard listener or sender')
            self.events.append(self.read(stack+8))
            # Boundary recorder replaces the scene listener, not GUI dispatch.
            cpu.reg_write(eip, self.read(stack))
            cpu.reg_write(esp, stack+20)  # thiscall listener has four stack arguments.
            cpu.reg_write(eax, 0)
            return
        super()._instruction(cpu, address, size, user)

    def keyboard(self, mode, key=0x28, counter=1, exclusive=None, visible=1, enabled=1):
        self.write(BUTTON+0x164, mode)
        self.write(BUTTON+0xe8, visible)
        self.write(BUTTON+0x160, enabled)
        self.write(BASE+0xf1c9c+key*4, counter)
        if exclusive is not None:
            self.write(0x20006038, 1)
            self.write(0x2000603c, 0x20006100)
            self.write(0x20006100, exclusive)
        ecx, esp, eip, eax = self.regs
        stack = 0x3001f000
        self.write(stack, STOP)
        self.cpu.reg_write(esp, stack)
        self.cpu.reg_write(ecx, BUTTON)
        self.cpu.emu_start(BASE+0x55134, STOP, timeout=500000, count=20000)
        _require(self.cpu.reg_read(eip) == STOP and self.cpu.reg_read(esp) == stack+4 and
                 self.read(0) == 0xffffffff, 'Keyboard budget, stack or SEH invariant failed')
        _require(self.read(BASE+0xf1c9c+key*4) == (counter & 0xffffffff),
                 'Original keyboard dispatch changed key counters')
        return self.cpu.reg_read(eax)


def run_replay(image):
    cases = []
    total = 0

    def record(name, n, result, **fields):
        nonlocal total
        total += n.instructions
        cases.append({'name': name, 'return': result, 'events': n.events, **fields})

    for mode in [0, 1, 2]:
        n = NativeKeyboard(image)
        result = n.keyboard(mode)
        _require(result == (1 if mode == 0 else 0), 'Nonmodal keyboard admission mismatch')
        _require((15 in n.events) == (mode == 0), 'Nonmodal Down press event mismatch')
        record(f'nonmodal_mode_{mode}', n, result)
        for name, owner in [('exact', BUTTON), ('sibling', BUTTON+0x800)]:
            n = NativeKeyboard(image)
            result = n.keyboard(mode, exclusive=owner)
            _require(result == (1 if name == 'exact' else 0), 'Exclusive keyboard ownership mismatch')
            _require((15 in n.events) == (name == 'exact'), 'Exclusive owner event mismatch')
            record(f'exclusive_{name}_mode_{mode}', n, result)
    for field in ['visible', 'enabled']:
        n = NativeKeyboard(image)
        result = n.keyboard(0, **{field: 0})
        _require(result == 0 and not n.events, 'Inactive widget must reject keyboard events')
        record(f'inactive_{field}', n, result)
    for key, first, held, released in [(0x25, 3, 1, 4), (0x27, 7, 5, 8), (0x26, 11, 9, 12), (0x28, 15, 13, 16)]:
        for counter, expected in [(1, [first, held]), (2, [held]), (-1, [released])]:
            n = NativeKeyboard(image)
            result = n.keyboard(0, key, counter)
            _require(all(event in n.events for event in expected), 'Arrow phase event mismatch')
            _require(not any(event in n.events for event in [first, held, released] if event not in expected),
                     'Unexpected arrow activation phase')
            record(f'key_{key:x}_counter_{counter}', n, result, expected_active_events=expected)
    n = NativeKeyboard(image)
    result = n.keyboard(0, counter=0)
    _require(not any(event in n.events for event in [15, 13, 16]), 'Masked direction emitted active event')
    record('masked_down_zero', n, result, active_events=[])
    # Preserve, do not patch, the original idle-dispatch anomaly.
    n = NativeKeyboard(image)
    result = n.keyboard(0, counter=0)
    _require(n.events.count(10) == 2 and 14 not in n.events, 'Original Down idle route changed')
    record('original_down_idle_route', n, result, up_idle_event_10_count=2, down_idle_event_14_count=0)
    return {'schema': 1, 'sample_sha256': SUPPORTED_SHA, 'cases': cases,
            'native_instructions': total, 'listener': 'boundary_recorder', 'game_started': False,
            'not_proven': ['physical Xbox', 'rendered selection', 'actual scene listener behavior']}


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
    print(f"NATIVE_KEYBOARD_REPLAY PASS cases={len(report['cases'])} mode1_keyboard=rejected exclusive=exact_owner listener=recorder game_started=false")


if __name__ == '__main__':
    main()
