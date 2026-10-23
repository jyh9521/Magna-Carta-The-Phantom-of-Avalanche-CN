"""Replay actual FLD/FPB dialogue against a captured, real Miles playback trace.

The trace is historical evidence, not synthetic tick-based audio. Native layout,
reveal and scrolling instructions execute in Unicorn; graphics/font services
remain owned boundaries. No game process or DLL entry point is executed.
"""
import argparse
import bisect
import csv
import hashlib
import io
import json
from pathlib import Path

from audit_dialogue_resources import parse_sound
from resource_field_script import parse as parse_field
from resource_fpb import parse as parse_fpb
from replay_native_dialogue import admit, MARKER
from replay_native_dialogue_autoplay import Scroll, glyphs
from replay_native_title import BASE, BUTTON, STOP, _require
from replay_native_dialogue_scene import initialize_scene, poll_scene, scene_instruction


def digest(data):
    return hashlib.sha256(data).hexdigest()


def playback_trace(raw, log, payload):
    """Bind the CSV to the source-locked fixture log and compressed source."""
    _require('AUDIO_SHA256 '+digest(payload) in log, 'Audio payload/log mismatch')
    _require('TRACE_SHA256 '+digest(raw) in log, 'Playback CSV/log mismatch')
    _require('DIALOGUE_AUDIO PASS' in log and 'seek_ms=0 ' in log,
             'A full natural playback trace is required')
    _require('entry_executed=false' in log, 'Native no-entry query evidence missing')
    reader = csv.DictReader(io.StringIO(raw.decode('ascii')))
    _require(reader.fieldnames == ['wall_ms', 'position_ms', 'total_ms', 'status', 'native_playing'],
             'Unknown playback trace schema')
    rows = [{key: int(value) for key, value in row.items()} for row in reader]
    _require(len(rows) >= 20, 'Insufficient real playback observations')
    previous = -1
    for index, row in enumerate(rows):
        _require(row['wall_ms'] > previous, 'Playback clock must increase')
        _require(row['status'] in (2, 4) and row['native_playing'] == int(row['status'] == 4),
                 'Native/Miles playback status disagreement')
        _require(row['status'] == 4 or index == len(rows)-1, 'Premature trace stop')
        _require(0 <= row['position_ms'] <= row['total_ms']+100, 'Invalid audio position')
        previous = row['wall_ms']
    _require(rows[0]['wall_ms'] < 100 and rows[0]['position_ms'] < 100 and
             rows[0]['status'] == 4 and rows[-1]['status'] == 2, 'Incomplete natural playback')
    _require(rows[-1]['wall_ms'] >= rows[0]['total_ms']-200, 'Truncated wall-clock playback')
    return rows


class VisibleDialogue(Scroll):
    """Observe settled native label prefixes before each actual row deletion."""
    def __init__(self, image, text, delay):
        self.objects = {}
        self.tick = 0
        self.scene_poll = False
        super().__init__(image, text)
        # Exact viewport passed by opcode 700, not the older 640x88 test viewport.
        self.write(BUTTON+0x1b4, 460)
        self.write(BUTTON+0x1b8, 52)
        self.write(BUTTON+0x1d0, delay if delay > 0 else 450)

    def _instruction(self, cpu, address, size, user):
        if self.scene_poll and scene_instruction(self, cpu, address, size, user):
            return
        ecx, esp, _, _ = self.regs
        obj = cpu.reg_read(ecx)
        if address == BASE+0x45040:
            text = self.string(self.read(cpu.reg_read(esp)+4))
            self.objects[obj] = dict(text=text, width=glyphs(text)*14,
                max_prefix=0, created_tick=self.tick, deleted=False)
        if address == MARKER+0x190 and obj in self.objects:
            row = self.objects[obj]
            _require(row['max_prefix'] >= row['width']-1, 'Native row deleted before reveal')
            row.update(deleted=True, deleted_tick=self.tick)
        super()._instruction(cpu, address, size, user)

    def step(self, held):
        ecx, esp, eip, _ = self.regs
        stack = 0x3001f000
        self.write(stack, STOP)
        self.cpu.reg_write(esp, stack)
        self.cpu.reg_write(ecx, BUTTON)
        if held:
            self.write(BUTTON+0x1d0, 0xffffffff)
        self.cpu.emu_start(BASE+0x5b1ef, STOP, count=100000)
        if held:
            self.write(BUTTON+0x1d0, 0)
        _require(self.cpu.reg_read(eip) == STOP and self.cpu.reg_read(esp) == stack+4,
                 'Native dialogue ABI/instruction budget')
        for obj, row in self.objects.items():
            if not row['deleted']:
                row['max_prefix'] = max(row['max_prefix'], self.read(obj+0x12c))


def replay(image, text, delay, trace, guarded, scene_field=None):
    n = VisibleDialogue(image, text, delay)
    if scene_field is not None:
        initialize_scene(n, scene_field)
    times = [row['wall_ms'] for row in trace]
    held_ticks = 0
    complete_ms = None
    barrier_polls = 0
    for tick in range((trace[-1]['wall_ms']+90000)*30//1000):
        n.tick = tick
        wall_ms = tick*1000//30
        observation = trace[max(0, bisect.bisect_right(times, wall_ms)-1)]
        playing = observation['native_playing'] == 1
        held = guarded and n.read(BUTTON+0x190) == 3 and n.read(BUTTON+0x1d0) == 0 and playing
        held_ticks += int(held)
        n.step(held)
        phase = n.read(BUTTON+0x190)
        if scene_field is not None:
            n.scene_poll = True
            try:
                scene = poll_scene(n)
            finally:
                n.scene_poll = False
            if phase != 6:
                barrier_polls += 1
                _require(scene['active_actions'] == 1 and scene['event_cursor'] == 51 and
                         scene['destroyed'] == 0 and not scene['transition_requested'],
                         'Scene crossed the real dialogue barrier prematurely')
            else:
                _require(scene['active_after_dialogue_poll'] == 0 and scene['destroyed'] == 1 and
                         scene['transition_requested'] and n.transition['target_field'] == 663,
                         'Native dialogue cleanup/scene transition did not complete')
        if phase == 3 and complete_ms is None:
            complete_ms = wall_ms
        if phase == 6:
            break
    _require(phase == 6, 'Dialogue did not finish')
    _require(all(row['max_prefix'] >= row['width']-1 for row in n.objects.values()),
             'Dialogue ended with incomplete native reveal')
    reconstructed = b''.join(row['text'] for row in n.objects.values())
    _require(reconstructed == text.replace(b'$n', b''), 'Missing dialogue bytes')
    return dict(guarded=guarded, source_bytes=len(text), source_sha256=digest(text),
        terminal_labels_sha256=digest(reconstructed), label_count=len(n.objects),
        all_labels_revealed_before_delete=True, complete_text_ms=complete_ms,
        dialogue_ended_ms=wall_ms, original_audio_ended_ms=trace[-1]['wall_ms'],
        original_audio_still_playing_at_close=playing, held_ticks=held_ticks,
        scene_barrier_polls=barrier_polls,
        native_transition=n.transition if scene_field is not None else None,
        native_instructions=n.instructions, inputs=0,
        adapters=['historical real Miles status sampled by standalone fixture',
                  'owned font measurement (14px), label construction, graphics and CRT',
                  'guard decision mirrors production; compiled hook tested separately'])


def run(source, trace_path, audio_log, field_id=766, event_id=1, action_id=50):
    paths = [source/'MCAlpha.dll', source/'Field'/f'{field_id:04d}.fld', trace_path, audio_log]
    snapshots = {path: digest(path.read_bytes()) for path in paths}
    image = paths[0].read_bytes()
    admit(image)
    field = parse_field(paths[1].read_bytes())
    actions = field['events'][event_id]['actions']
    command = actions[action_id]
    _require(command['opcode'] == 700, 'Expected a real dialogue command')
    tag, voice_id, delay = command['parameters'][6:9]
    fp = source/'Fpb'/f"{field['playbook_id']:04d}.fpb"
    svd = source/'SVD'/f'{voice_id:04d}.SVD'
    for path in (fp, svd):
        snapshots[path] = digest(path.read_bytes())
    matches = [text for identifier, text in parse_fpb(fp.read_bytes()) if identifier == tag]
    _require(len(matches) == 1, 'Ambiguous/missing dialogue text')
    sound = svd.read_bytes()
    header = parse_sound(sound)
    trace = playback_trace(trace_path.read_bytes(), audio_log.read_text('utf8'),
                           sound[header['header_bytes']:])
    scene_field = paths[1].read_bytes() if (field_id, event_id, action_id) == (766, 1, 50) else None
    cases = [replay(image, matches[0], delay, trace, guarded, scene_field) for guarded in (False, True)]
    _require(not cases[1]['original_audio_still_playing_at_close'],
             'Guard did not prevent premature original close')
    if cases[0]['original_audio_still_playing_at_close']:
        _require(cases[1]['held_ticks'] > 0, 'Guard failed to wait')
    for path, expected in snapshots.items():
        _require(digest(path.read_bytes()) == expected, 'Evidence/source changed during replay')
    return dict(schema=1, field=field_id, event=event_id, action=action_id,
        playbook=field['playbook_id'], tag=tag, voice=voice_id, script_delay=delay,
        following_opcodes=[row['opcode'] for row in actions[action_id+1:]], cases=cases,
        original_premature_close_reproduced=cases[0]['original_audio_still_playing_at_close'],
        sources=[dict(path=str(path), sha256=value) for path, value in snapshots.items()],
        game_started=False, source_unchanged=True,
        limitations=['Not game rendering or player-reported scene acceptance.',
            'Full original UI traversal/constructor is not executed by the text replay.'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'trace', 'audio-log', 'report'):
        p.add_argument('--'+name, required=True, type=Path)
    p.add_argument('--field', type=int, default=766)
    p.add_argument('--event', type=int, default=1)
    p.add_argument('--action', type=int, default=50)
    a = p.parse_args()
    _require(not a.report.exists() and not a.report.resolve().is_relative_to(a.source.resolve()),
             'Report must be new and outside source data')
    result = run(a.source, a.trace, a.audio_log, a.field, a.event, a.action)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    with a.report.open('x', encoding='utf8') as report:
        report.write(json.dumps(result, indent=2)+'\n')
    _require(json.loads(a.report.read_text('utf8')) == result, 'Report reopen mismatch')
    before, after = result['cases']
    print(f'DIALOGUE_CHAIN PASS voice={result["voice"]} text={before["source_bytes"]} '
          f'baseline_close_ms={before["dialogue_ended_ms"]} '
          f'guarded_close_ms={after["dialogue_ended_ms"]} '
          f'real_audio_end_ms={after["original_audio_ended_ms"]} '
          'labels=fully_revealed real_miles_trace=true game_started=false')


if __name__ == '__main__':
    main()
