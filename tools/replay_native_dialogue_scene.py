"""Source-locked dialogue completion -> event barrier -> scene request replay.

No PE loader, DLL entry point, game process or scene loader is invoked. The
first active dialogue slot is explicitly initialized, not created by replay.
Only its completion and the scheduler/transition-request instructions execute.
The selected real event tail contains only its barrier and transition request;
no subsequent dialogue or action completion is simulated.
"""
from pathlib import Path
import argparse
import hashlib
import json
import struct

from replay_native_dialogue import admit
from replay_native_title import NativeTitle, BASE, BUTTON, STOP, SHIM, _require
from resource_field_script import parse

FIELD_SHA = 'cfee58440e031db69365081cf0023504b0536595d34650dfa89f1727b73b0043'
MANAGER, EVENT, SLOTS, COMMANDS, ARGS, VTABLE = [0x20000000 + n for n in
    (0xa000, 0xa100, 0xa200, 0xb000, 0xc000, 0xd000)]
DESTRUCTOR = SHIM + 0xe00


class Scene(NativeTitle):
    def __init__(self, image, field):
        admit(image)
        super().__init__(image)
        self.initialize_scene(field)

    def initialize_scene(self, field):
        _require(hashlib.sha256(field).hexdigest() == FIELD_SHA, 'Unsupported Field source digest')
        event = parse(field)['events'][1]
        self.actions = event['actions']
        _require([r['opcode'] for r in self.actions[50:]] == [700, 1, 4],
                 'Unsupported event command sequence')
        _require(self.actions[50]['parameters'][:9] ==
                 [10005, 103, 0, 100, 0, 1, 42, 1500, 975], 'Dialogue binding differs')
        self.effect_boundaries, self.destroyed, self.transition = [], 0, None
        self.write(MANAGER, VTABLE)
        self.write(VTABLE + 0x28, BASE + 0x71b9b)
        self.write(MANAGER + 0x2c, EVENT - 0x38)
        self.write(MANAGER + 0x34, SLOTS)
        self.write(MANAGER + 0x38, 16)
        for i in range(16):
            self.write(SLOTS + i * 0x28, -1)
        # One native runtime event and one already-active dialogue action.
        self.write(EVENT, 1)
        self.write(EVENT + 4, COMMANDS)
        self.write(EVENT + 0x14, 1)
        self.write(EVENT + 0x1c, 51)  # First real opcode-1 barrier.
        self.write(EVENT + 0x20, len(self.actions))
        self.write(EVENT + 0x2c, 1)
        for i, row in enumerate(self.actions):
            self.cpu.mem_write(COMMANDS + i * 60,
                               struct.pack('<15i', row['opcode'], *row['parameters']))
        for off, value in [(0, 700), (4, 1), (8, 1), (0x14, ARGS), (0x18, BUTTON)]:
            self.write(SLOTS + off, value)
        self.cpu.mem_write(ARGS, struct.pack('<14i', *self.actions[50]['parameters']))
        original_vtable = self.read(BUTTON)
        self.cpu.mem_write(VTABLE + 0x100, bytes(self.cpu.mem_read(original_vtable, 0x200)))
        self.write(BUTTON, VTABLE + 0x100)
        self.write(VTABLE + 0x100, DESTRUCTOR)

    def scene_instruction(self, cpu, address, size, user):
        ecx, esp, eip, eax = self.regs
        stack = cpu.reg_read(esp)

        def ret(value=0, pop=0):
            cpu.reg_write(eax, value)
            cpu.reg_write(eip, self.read(stack))
            cpu.reg_write(esp, stack + 4 + pop)

        if address == DESTRUCTOR:
            _require(cpu.reg_read(ecx) == BUTTON, 'Unexpected destructor receiver')
            self.destroyed += 1
            ret(0, 4)
            return True
        if address == BASE + 0xb8b4e:
            dest, value, count = [self.read(stack + n) for n in (4, 8, 12)]
            cpu.mem_write(dest, bytes([value & 255]) * count)
            ret(dest)
            return True
        if address == BASE + 0x6e36e:
            self.effect_boundaries.append('scene_cleanup')
            ret()
            return True
        if address == BASE + 0xb8b5a:
            _require(self.read(stack + 4) == 0x20, 'Unexpected allocation')
            ret(0x2000e000)
            return True
        if address == BASE + 0xc9fd:
            self.transition = {'request_rva': '0xc9fd', 'kind': self.read(stack + 4),
                               'target_field': self.read(stack + 8)}
            cpu.emu_stop()
            return True
        return False

    def _instruction(self, cpu, address, size, user):
        if not self.scene_instruction(cpu, address, size, user):
            super()._instruction(cpu, address, size, user)

    def call(self, rva, argument=None):
        ecx, esp, eip, _ = self.regs
        stack = 0x3001f000
        self.write(stack, STOP)
        if argument is not None:
            self.write(stack + 4, argument)
        self.cpu.reg_write(ecx, MANAGER)
        self.cpu.reg_write(esp, stack)
        self.cpu.emu_start(BASE + rva, STOP, count=100000)
        if not self.transition:
            _require(self.cpu.reg_read(eip) == STOP and
                     self.cpu.reg_read(esp) == stack + (8 if argument is not None else 4),
                     'Scene replay instruction budget or ABI restoration')
            _require(self.read(0) == 0xffffffff, 'SEH chain restoration')

    def check_phase(self, phase):
        """Invoke real active-action completion and then the real event scanner."""
        self.write(BUTTON + 0x190, phase)
        return poll_scene(self)


def initialize_scene(replay, field):
    """Attach the supported already-active event to a NativeTitle/Scroll instance.

    The caller delegates instruction hooks to scene_instruction only while
    poll_scene is running, so ordinary text/graphics boundaries stay separate.
    """
    Scene.initialize_scene(replay, field)


def scene_instruction(replay, cpu, address, size, user):
    return Scene.scene_instruction(replay, cpu, address, size, user)


def poll_scene(replay):
    """Poll actual native script with the current native dialogue phase unchanged."""
    phase = replay.read(BUTTON + 0x190)
    Scene.call(replay, 0x78209, 0)
    dialogue_cleanup_active = replay.read(EVENT + 0x2c)
    Scene.call(replay, 0x4ba72, EVENT)
    return {'phase': phase, 'active_actions': replay.read(EVENT + 0x2c),
            'active_after_dialogue_poll': dialogue_cleanup_active,
            'event_cursor': replay.read(EVENT + 0x1c),
            'destroyed': replay.destroyed, 'transition_requested': replay.transition is not None}


def run(image, field):
    replay = Scene(image, field)
    held = [replay.check_phase(phase) for phase in (0, 1, 2, 3, 4, 5)]
    _require(all(r['active_actions'] == 1 and r['event_cursor'] == 51 and
                 not r['destroyed'] and not r['transition_requested'] for r in held),
             'Event crossed the dialogue barrier before phase 6')
    replay.write(BUTTON + 0x190, 6)
    replay.call(0x78209, 0)
    after_cleanup = {'active_actions': replay.read(EVENT + 0x2c),
                     'slot_opcode': replay.read(SLOTS), 'destroyed': replay.destroyed}
    _require(after_cleanup == {'active_actions': 0, 'slot_opcode': 0xffffffff, 'destroyed': 1},
             'Native completion did not release the dialogue slot')
    replay.call(0x4ba72, EVENT)
    _require(replay.transition == {'request_rva': '0xc9fd', 'kind': 31, 'target_field': 663},
             'Wrong native transition request')
    return {'schema': 1, 'sample_sha256': hashlib.sha256(image).hexdigest(),
            'field_sha256': FIELD_SHA, 'field': '0766', 'event': 1, 'action': 50,
            'dialogue': {'fpb': '0738', 'tag': 42, 'svd': 1500},
            'held_before_phase6': held, 'native_cleanup': after_cleanup,
            'transition': replay.transition, 'native_instructions': replay.instructions,
            'completed_effect_boundaries': replay.effect_boundaries,
            'game_started': False, 'scene_loader_executed': False,
            'not_proven': ['dialogue creation', 'dialogue text layout', 'audio playback',
                           'earlier event actions', 'scene loading/rendering']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sample', required=True, type=Path)
    parser.add_argument('--field', required=True, type=Path)
    parser.add_argument('--report', required=True, type=Path)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Report must be a new file')
    for source in (args.sample, args.field):
        if args.report.resolve() == source.resolve() or (
                args.report.exists() and args.report.samefile(source)):
            parser.error('Report must differ from source')
    image, field = args.sample.read_bytes(), args.field.read_bytes()
    result = run(image, field)
    _require(args.sample.read_bytes() == image and args.field.read_bytes() == field, 'Source changed')
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open('x', encoding='utf8') as report:
        report.write(json.dumps(result, indent=2) + '\n')
    print('NATIVE_DIALOGUE_SCENE PASS field=0766 event=1 action=50 phases0_5=held phase6=cleanup '
          'active=1_to_0 transition=31:663 loader=not_executed game_started=false')


if __name__ == '__main__':
    main()
