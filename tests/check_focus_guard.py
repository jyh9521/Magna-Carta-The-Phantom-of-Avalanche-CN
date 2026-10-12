"""Owned focus fixture and rejected launch input; no game startup."""
import argparse
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import winreg
p=argparse.ArgumentParser();p.add_argument('--bin',type=Path,required=True)
p.add_argument('--game',type=Path,required=True);p.add_argument('--profile',type=Path,required=True)
p.add_argument('--output',type=Path,required=True);a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=False)
spec=importlib.util.spec_from_file_location('isolation',Path(__file__).with_name('check_runtime_isolation.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
before=m.snapshot(winreg.HKEY_LOCAL_MACHINE,m.KEY,winreg.KEY_WOW64_32KEY)
sessions=m.snapshot(winreg.HKEY_CURRENT_USER,m.SESSIONS,0)
fixture=subprocess.run([str(a.bin/'focus_guard_fixture.exe')],capture_output=True,text=True)
assert fixture.returncode==0 and 'FOCUS_FIXTURE_PASS' in fixture.stdout
game=a.output/'unsupported-game';(game/'Drv').mkdir(parents=True)
for n in ['MagnaCarta.exe','MCAlpha.dll','Drv/AsrD3DDrv.dll']:shutil.copyfile(a.game/n,game/n)
(game/'ddraw.dll').write_bytes(b'unsupported-fixture')
command=[str(a.bin/'workspace_launcher.exe'),'--workspace',str(game),'--shim',str(a.bin/'workspace_profile.dll'),
         '--profile',str(a.profile),'--log',str(a.output/'rejected.log'),'--focus-guard']
rejected=subprocess.run(command,capture_output=True,text=True)
assert rejected.returncode==125 and 'Unsupported focus graphics layer' in rejected.stderr
assert 'ISOLATED_PROCESS_STARTED' not in rejected.stdout
assert before==m.snapshot(winreg.HKEY_LOCAL_MACHINE,m.KEY,winreg.KEY_WOW64_32KEY)
assert sessions==m.snapshot(winreg.HKEY_CURRENT_USER,m.SESSIONS,0)
(a.output/'results.json').write_text(json.dumps(dict(fixture_stdout=fixture.stdout,fixture_exit=fixture.returncode,
    rejected_command=command,rejected_stderr=rejected.stderr,rejected_exit=rejected.returncode,
    original_registry_unchanged=True,sessions_unchanged=True,game_started=False),indent=2))
print('FOCUS_GUARD_CHECK_PASS policy=true unknown_layer_rejected=true registry_unchanged=true sessions_unchanged=true game_started=false')
