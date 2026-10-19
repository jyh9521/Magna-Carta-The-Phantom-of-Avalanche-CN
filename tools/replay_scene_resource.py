"""Replay source-locked map resource branches offline, not a game/crash reproducer."""
import argparse
import hashlib
import json
from pathlib import Path

from replay_native_title import NativeTitle, BASE, STOP, SHIM, ReplayError, _require
from replay_native_gui_parent import SOURCE_SHA

ITEM = 0x20007000
MANAGER = 0x20008000
RESULT = 0x20009000
SLEEP = SHIM + 0x600


class ResourceReplay(NativeTitle):
    def _instruction(self, cpu, address, size, data):
        if address == SLEEP:
            return
        super()._instruction(cpu, address, size, data)

    def __init__(self, image):
        if hashlib.sha256(image).hexdigest() != SOURCE_SHA:
            raise ValueError('Unsupported full engine SHA256')
        super().__init__(image)
        self.write(BASE + 0xbd288, SLEEP)

    def getter(self, state=None, result=0, complete=True):
        from unicorn import UC_HOOK_CODE
        ecx, esp, eip, eax = self.regs
        stack = 0x3001f000
        self.write(ITEM, 8); self.write(ITEM + 4, 757); self.write(ITEM + 8, 0)
        self.write(ITEM + 12, state or 0); self.write(ITEM + 16, result)
        self.write(stack, STOP); self.write(stack + 4, 757); self.write(stack + 8, 0)
        self.cpu.reg_write(ecx, MANAGER); self.cpu.reg_write(esp, stack)
        events = []

        def ret(cleanup, value=0):
            sp = self.cpu.reg_read(esp)
            self.cpu.reg_write(eip, self.read(sp))
            self.cpu.reg_write(esp, sp + 4 + cleanup)
            self.cpu.reg_write(eax, value)

        def hook(cpu, address, size, data):
            sp = cpu.reg_read(esp)
            if address == BASE + 0x32b3e:
                _require(cpu.reg_read(ecx) == MANAGER and self.read(sp + 4) == 8 and
                         self.read(sp + 8) == 757, 'Unexpected query ABI')
                events.append('query_type8'); ret(8, ITEM if state is not None else 0)
            elif address == BASE + 0x2a723:
                _require(cpu.reg_read(ecx) == MANAGER and self.read(sp + 4) == 757 and
                         self.read(sp + 8) == 0, 'Unexpected synchronous loader ABI')
                events.append('sync_load_boundary'); ret(8, RESULT)
            elif address == SLEEP:
                _require(self.read(sp + 4) == 30, 'Unexpected sleep interval')
                events.append('sleep_30_boundary')
                if complete:
                    self.write(ITEM + 12, 3)
                ret(4)
            elif not (BASE + 0x2a673 <= address < BASE + 0x2a723 or
                      BASE + 0x355d0 <= address < BASE + 0x355e4):
                raise ReplayError('Unexpected native getter boundary: ' + hex(address))

        handle = self.cpu.hook_add(UC_HOOK_CODE, hook)
        try:
            self.cpu.emu_start(BASE + 0x2a673, STOP, timeout=500000, count=1500)
        finally:
            self.cpu.hook_del(handle)
        returned = self.cpu.reg_read(eip) == STOP
        if returned:
            _require(self.cpu.reg_read(esp) == stack + 12, 'Getter stack mismatch')
        else:
            _require(not complete and events.count('sleep_30_boundary') > 1 and
                     BASE + 0x2a673 <= self.cpu.reg_read(eip) < BASE + 0x2a723,
                     'Unexpected replay budget exhaustion')
        return dict(returned=returned, result=hex(self.cpu.reg_read(eax)) if returned else None,
                    state=self.read(ITEM + 12), sync_loads=events.count('sync_load_boundary'),
                    sleeps=events.count('sleep_30_boundary'),
                    boundaries=sorted(set(events)),
                    outcome='returned' if returned else 'bounded_wait_not_crash')

    def worker_dispatch(self, resource_type, state):
        from unicorn import UC_HOOK_CODE
        from unicorn.x86_const import UC_X86_REG_EBP
        ecx, esp, eip, eax = self.regs
        frame = 0x3001e000
        self.write(ITEM, resource_type); self.write(ITEM + 4, 757); self.write(ITEM + 8, 0)
        self.write(ITEM + 12, state); self.write(ITEM + 16, 0)
        self.write(frame - 0x10, ITEM); self.write(frame - 0x12c, MANAGER)
        self.write(frame - 0x14, 99)
        self.cpu.reg_write(UC_X86_REG_EBP, frame); self.cpu.reg_write(esp, frame - 0x180)
        events = []

        def hook(cpu, address, size, data):
            if address in (BASE + 0x29c9d, BASE + 0x3299f):
                sp = cpu.reg_read(esp)
                _require(cpu.reg_read(ecx) == MANAGER, 'Worker manager mismatch')
                cleanup = 8 if address == BASE + 0x29c9d else 4
                _require(self.read(sp + 4) == (757 if cleanup == 8 else ITEM),
                         'Worker boundary argument mismatch')
                events.append('type3_load_boundary' if cleanup == 8 else 'delete_boundary')
                cpu.reg_write(eip, self.read(sp)); cpu.reg_write(esp, sp + 4 + cleanup)
                cpu.reg_write(eax, RESULT)
            elif not (BASE + 0x32c55 <= address < BASE + 0x32dc6 or
                      BASE + 0x35530 <= address < BASE + 0x35540):
                raise ReplayError('Unexpected worker boundary: ' + hex(address))

        handle = self.cpu.hook_add(UC_HOOK_CODE, hook)
        try:
            self.cpu.emu_start(BASE + 0x32c55, BASE + 0x32dc6, count=1000, timeout=500000)
        finally:
            self.cpu.hook_del(handle)
        _require(self.cpu.reg_read(eip) == BASE + 0x32dc6, 'Worker budget exhausted')
        return dict(state=self.read(ITEM + 12), result=hex(self.read(ITEM + 16)),
                    continue_scan=self.read(frame - 0x14), boundaries=events)


def verify(image):
    cases = {}
    def getter(name, state, result, complete, expected):
        r = ResourceReplay(image).getter(state, result, complete)
        for key, value in expected.items():
            _require(r[key] == value, name + ': unexpected ' + key)
        cases[name] = r
    getter('missing', None, 0, True, dict(returned=True, sync_loads=1, sleeps=0))
    getter('state2', 2, 0, True, dict(returned=True, sync_loads=1, state=2))
    getter('complete_cached', 3, RESULT, True, dict(returned=True, sync_loads=0, state=4))
    getter('complete_empty', 3, 0, True, dict(returned=True, sync_loads=1, state=4))
    getter('pending_completed_at_boundary', 1, 0, True,
           dict(returned=True, sync_loads=1, sleeps=1, state=4))
    getter('pending_never_completed', 1, 0, False,
           dict(returned=False, sync_loads=0, state=1))
    for name, r in cases.items():
        if r['returned']:
            _require(r['result'] == hex(RESULT), name + ': return value mismatch')
    for state in range(5):
        r = ResourceReplay(image).worker_dispatch(8, state)
        expected = 3 if state in (0, 1) else state
        _require(r['state'] == expected and r['result'] == '0x0' and
                 r['boundaries'] == (['delete_boundary'] if state == 4 else []) and
                 r['continue_scan'] == (1 if state == 3 else 0), 'Type8 dispatch mismatch')
        cases['worker_type8_state' + str(state)] = r
    r = ResourceReplay(image).worker_dispatch(3, 0)
    _require(r['state'] == 3 and r['result'] == hex(RESULT) and
             r['boundaries'] == ['type3_load_boundary'], 'Type3 control mismatch')
    cases['worker_type3_control'] = r
    return dict(schema=1, engine_sha256=SOURCE_SHA, cases=cases, game_started=False,
                game_dll_loaded=False, scene_transition_verified=False,
                scene_root_cause_confirmed=False, production_modified=False,
                limits=['Owned resource records; query, loader, Sleep and delete are ABI boundaries.',
                        'Worker replay starts at dispatch, not at the thread/list traversal.',
                        'Wait completion and non-completion are injected scheduling conditions.',
                        'No real Field, file loading, renderer, concurrency or scene crash reproduced.'])


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--sample', required=True, type=Path)
    p.add_argument('--report', required=True, type=Path)
    a = p.parse_args()
    if a.report.exists() or not a.report.parent.is_dir() or a.report.resolve() == a.sample.resolve():
        p.error('New report in existing directory required')
    report = verify(a.sample.read_bytes())
    with a.report.open('x', encoding='utf8') as f:
        json.dump(report, f, indent=2); f.write('\n')
    print('SCENE_RESOURCE_REPLAY PASS cases=12 native_branches=true game_started=false scene_crash_reproduced=false')
