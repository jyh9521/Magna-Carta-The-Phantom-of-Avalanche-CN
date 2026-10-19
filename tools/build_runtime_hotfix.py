"""Build a small source-locked runtime update, without game files or settings."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import zipfile

ROOT = Path(__file__).resolve().parents[1]
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def located(root, name):
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or ':' in name or '\\' in name:
        raise ValueError('Invalid relative path')
    path = root.joinpath(*p.parts)
    if path.resolve() != path.absolute() or path.is_symlink():
        raise ValueError('Linked path')
    return path

def build(runtime, record, metadata, output):
    runtime, record, output = runtime.resolve(), record.resolve(), output.resolve()
    if output.exists() or output.is_relative_to(runtime) or output.is_relative_to(record):
        raise ValueError('New separate output required')
    states = json.loads((record/'changes.json').read_text(encoding='utf8'))
    if set(states) != {'runtime.json', *('modules/'+n+'.dll' for n in ['display','modern','texture','camera','maps','input-diagnostics','motion-space','configuration'])}:
        raise ValueError('Unexpected runtime update file set')
    required = {}
    for row in json.loads(metadata.read_text(encoding='utf8'))['layouts']:
        for name, digest in row['sha256'].items():
            if sha(located(runtime/'data', name)) != digest:
                raise ValueError('Game resource drift: '+name)
            required[name] = digest
    for name, state in states.items():
        if sha(located(runtime, name)) != state['after'] or sha(located(record/'original', name)) != state['before']:
            raise ValueError('Deployment source drift: '+name)
    output.mkdir(parents=True)
    for name in states:
        dest = located(output/'payload', name)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(located(runtime, name), dest)
    shutil.copy2(ROOT/'assets/runtime-hotfix/Update.ps1', output/'Update.ps1')
    (output/'Update.cmd').write_bytes(b'@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Update.ps1" %*\r\nif errorlevel 1 pause\r\n')
    shutil.copy2(ROOT/'LICENSE', output/'LICENSE')
    (output/'hotfix.json').write_text(json.dumps(dict(schema=1,id='display-motion-20261019',files=states,required_data=required),indent=2)+'\n',encoding='utf8')
    (output/'README.txt').write_text('''2026-10-19 runtime update for the 2026-10-17 unified test package.
No original game files or saves/settings are included.
Extract the ZIP, run Update.cmd, and enter the installed folder containing runtime.json.
Or: Update.cmd -Target "D:\\MagnaCarta-PlayerTest"
Check: Update.cmd -Action CheckInstalled -Target "D:\\MagnaCarta-PlayerTest"
Rollback: Update.cmd -Action Rollback -Target "D:\\MagnaCarta-PlayerTest"
The updater verifies all nine old/new file hashes and opening resources.
It backs up only the nine small runtime files under .runtime-updates, never game data.
Manual acceptance: keep 60 FPS, walk/turn/stop; start New Game and check opening text on 2880x1800.
Mixed skin/static phase and opening coordinates pass offline replay; actual eye geometry remains unverified.
''',encoding='utf8')
    archive=output.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for p in output.rglob('*'):
            if p.is_file(): z.write(p,p.relative_to(output))
    with zipfile.ZipFile(archive) as z:
        if z.testzip() is not None:raise ValueError('ZIP readback failed')
    print(f'RUNTIME_HOTFIX_PACKAGE PASS files={len(states)} zip_readback=exact game_files_included=false sha256={sha(archive)}')
    return archive

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['runtime','record','metadata','output']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();build(a.runtime,a.record,a.metadata,a.output)
