"""Collect exit evidence from an existing session without starting a process."""
import argparse
import json
from pathlib import Path
import re

LABELS = {0: 'normal_exit', 124: 'launcher_timeout', 125: 'launcher_failure',
          0xc0000005: 'access_violation', 0xc000041d: 'unhandled_callback_exception',
          0xc0000409: 'fail_fast'}


def parse_exit(text):
    starts = re.findall(r'^ISOLATED_PROCESS_STARTED pid=(\d+)\s*$', text, re.M)
    ends = re.findall(r'^ISOLATED_PROCESS_ENDED exit=(\d+)\s*$', text, re.M)
    if len(starts) != 1 or len(ends) != 1:
        raise ValueError('Expected one completed session')
    code = int(ends[0])
    if code > 0xffffffff:
        raise ValueError('Exit code out of range')
    return {'pid': int(starts[0]), 'exit_status': code, 'exit_hex': f'0x{code:08x}',
            'category': LABELS.get(code, 'other_exit'),
            'natural_exit': code not in (124, 125), 'root_cause': 'not established'}


def collect(session):
    session = Path(session)
    result = parse_exit((session / 'stdout.log').read_text(encoding='utf-8'))
    result['stderr'] = (session / 'stderr.log').read_text(encoding='utf-8')
    trace = (session / 'profile.log').read_text(encoding='utf-8')
    result['observed_module_loads'] = re.findall(r'^MODULE_LOADED path=(.+)$', trace, re.M)
    result['graphics_inputs_at_launch'] = None
    snapshot = session / 'graphics-inputs.json'
    if snapshot.exists():
        result['graphics_inputs_at_launch'] = json.loads(snapshot.read_text(encoding='utf-8-sig'))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / 'build'
    if not args.session.resolve().is_relative_to(root) or not args.report.resolve().is_relative_to(root):
        parser.error('Session and report must remain inside build/')
    if args.report.exists():
        parser.error('Report already exists')
    result = collect(args.session)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"SESSION_EVIDENCE pid={result['pid']} exit={result['exit_hex']} category={result['category']} game_started=false")
