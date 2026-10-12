"""Check lifetime policy and unknown-driver rejection without running a game."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import winreg

parser = argparse.ArgumentParser()
parser.add_argument('--bin', type=Path, required=True)
parser.add_argument('--game', type=Path, required=True)
parser.add_argument('--profile', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(parents=True, exist_ok=False)
spec = importlib.util.spec_from_file_location('isolation_checks', Path(__file__).with_name('check_runtime_isolation.py'))
isolation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(isolation)
before = (isolation.snapshot(winreg.HKEY_LOCAL_MACHINE, isolation.KEY, winreg.KEY_WOW64_32KEY),
          isolation.snapshot(winreg.HKEY_CURRENT_USER, isolation.VIRTUAL, winreg.KEY_WOW64_64KEY))
sessions = isolation.session_names()
fixture = subprocess.run([str(args.bin / 'texture_lifetime_fixture.exe')], capture_output=True, text=True)
assert fixture.returncode == 0 and 'TEXTURE_LIFETIME_FIXTURE_PASS' in fixture.stdout
assert 'release_while_bound=true' in fixture.stdout
workspace = args.output / 'unsupported-game'
(workspace / 'Drv').mkdir(parents=True)
for name in ('MagnaCarta.exe', 'MCAlpha.dll'):
    shutil.copy2(args.game / name, workspace / name)
(workspace / 'Drv/AsrD3DDrv.dll').write_bytes(b'unsupported-fixture')
command = [str(args.bin / 'workspace_launcher.exe'), '--workspace', str(workspace),
           '--shim', str(args.bin / 'workspace_profile.dll'), '--profile', str(args.profile),
           '--log', str(args.output / 'rejected.log'), '--texture-lifetime']
guard = subprocess.run(command, capture_output=True, text=True)
assert guard.returncode == 125 and 'Unsupported graphics driver' in guard.stderr
assert 'ISOLATED_PROCESS_STARTED' not in guard.stdout
assert sessions == isolation.session_names()
assert before == (isolation.snapshot(winreg.HKEY_LOCAL_MACHINE, isolation.KEY, winreg.KEY_WOW64_32KEY),
                  isolation.snapshot(winreg.HKEY_CURRENT_USER, isolation.VIRTUAL, winreg.KEY_WOW64_64KEY))
report = {'fixture': {'command': fixture.args, 'stdout': fixture.stdout, 'stderr': fixture.stderr, 'exit_status': fixture.returncode},
          'unknown_driver': {'command': guard.args, 'stdout': guard.stdout, 'stderr': guard.stderr, 'exit_status': guard.returncode},
          'source_registry_unchanged': True, 'sessions_unchanged': True, 'game_started': False}
(args.output / 'results.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print('TEXTURE_CANDIDATE_CHECK_PASS policy=true version_guard=true registry_unchanged=true game_started=false')
