"""Accept offscreen graphics evidence only when rendering and process exit pass."""
import argparse
import json
from pathlib import Path
import subprocess

MARKER = 'GRAPHICS_PROBE_PASS frames=120 depth=16 near_visible=120 display_mode_changed=false game_started=false'


def accepted(exit_status, stdout, hal_only=False):
    return (exit_status == 0 and MARKER in stdout.splitlines()
            and (not hal_only or 'DEVICE_ENUM hal=1 tnl=0' in stdout.splitlines()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--probe', type=Path, required=True)
    parser.add_argument('--dll', type=Path, required=True)
    parser.add_argument('--hal-only', action='store_true')
    parser.add_argument('--repeat', type=int, default=3)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.repeat <= 10 or args.report.exists():
        parser.error('Use 1..10 repeats and a new report path')
    command = [str(args.probe.resolve(strict=True)), str(args.dll.resolve(strict=True))]
    if args.hal_only:
        command.append('--expect-hal-only')
    rows = []
    for index in range(args.repeat):
        try:
            proc = subprocess.run(command, capture_output=True, text=True, timeout=20)
            row = {'index': index, 'exit_status': proc.returncode,
                   'stdout': proc.stdout, 'stderr': proc.stderr,
                   'accepted': accepted(proc.returncode, proc.stdout, args.hal_only)}
        except subprocess.TimeoutExpired:
            row = {'index': index, 'exit_status': 'timeout', 'accepted': False}
        rows.append(row)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({'command': command, 'runs': rows}, indent=2), encoding='utf-8')
    count = sum(row['accepted'] for row in rows)
    print(f'GRAPHICS_ACCEPTANCE accepted={count}/{len(rows)}')
    raise SystemExit(0 if count == len(rows) else 1)
