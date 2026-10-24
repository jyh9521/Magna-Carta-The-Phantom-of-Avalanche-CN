"""Read-only, source-locked classification of the Field258 sound-only opening.

Script intent is separate from rendered-frame acceptance. The contact observer
does not sample every cutscene frame; missing fade rows are not stuck fades.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from resource_field_script import parse

FIELD_SHA = 'cff00dc78522d6de1845c1c80b5e697abd64cee94a2e9895c2910c6ab9cec9f8'
ENGINE_SHA = '7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e'


def opening_matches(actions):
    expected = {1: (503, [8, 1, 0, 0, 100]),
                6: (603, [470, 1]), 8: (603, [471, 1]),
                10: (507, [30, 0]), 11: (603, [472, 1])}
    if len(actions) <= 29:
        return False
    for index, (opcode, parameters) in expected.items():
        row = actions[index]
        if row['opcode'] != opcode or row['parameters'][:len(parameters)] != parameters:
            return False
    dialogues = [i for i, row in enumerate(actions) if row['opcode'] == 700]
    return bool(dialogues and dialogues[0] == 29 and
                actions[29]['parameters'][6:8] == [5, 1342])


def audit(source, trace):
    source, trace = Path(source), Path(trace)
    paths = [source/'MCAlpha.dll', source/'Field/0258.fld', source/'Fpb/0233.fpb', trace]
    snapshots = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    if snapshots[paths[0]] != ENGINE_SHA or snapshots[paths[1]] != FIELD_SHA:
        raise ValueError('Unsupported engine/Field258 source digest')
    script = parse(paths[1].read_bytes())
    actions = script['events'][1]['actions']
    if (script['map_resource_id'], script['playbook_id']) != (279, 233) or not opening_matches(actions):
        raise ValueError('Field258 opening differs from the inspected native sequence')
    states, transitions = [], []
    for line in trace.read_text('utf8', errors='replace').splitlines():
        if line.startswith('BLOCKER_STATE '):
            row = {k: int(v) for k, v in re.findall(r'(ms|field|map|mode)=([0-9]+)', line)}
            states.append(row)
            if not transitions or transitions[-1]['field'] != row['field']:
                transitions.append(row)
    if not any(a['field'] == 257 and b['field'] == 258 for a, b in zip(transitions, transitions[1:])):
        raise ValueError('Trace does not contain the reported 257-to-258 transition')
    for path, expected in snapshots.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('Source changed during audit')
    return dict(schema=1, verdict='scripted_sound_only_opening_high_confidence',
                field=258, map=279, playbook=233,
                blackout=dict(opcode=503, target_percentage=100, duration_parameter=1),
                standalone_sound_ids=[470, 471, 472],
                curtain_release=dict(opcode=507, duration_parameter=30, action=10),
                first_regular_dialogue=dict(action=29, tag=5, voice=1342),
                ordinary_dialogue_absent_before_action29=True,
                transitions=transitions,
                field258_observer_samples=sum(r['field'] == 258 for r in states),
                rendered_picture_verified=False, source_unchanged=True,
                game_started_by_audit=False,
                limits=['Only this opening is classified; other black screens and collision softlocks remain separate.',
                        'No pixel capture or post-transition continuous fade samples; no duration acceptance claim.'],
                inputs=[dict(path=str(p.resolve()), sha256=h) for p, h in snapshots.items()])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--trace', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    a = parser.parse_args()
    if a.report.resolve().is_relative_to(a.source.resolve()) or a.report.resolve() == a.trace.resolve():
        parser.error('Report must remain separate from source resources and trace')
    result = audit(a.source, a.trace)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(result, indent=2)+'\n', encoding='utf8')
    assert json.loads(a.report.read_text('utf8')) == result
    print('STORY_BLACKOUT PASS field=258 black_target=100 sounds=470,471,472 release=507 first_dialogue=29:tag5 source_unchanged=true pixels_verified=false')


if __name__ == '__main__':
    main()
