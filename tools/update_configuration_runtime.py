"""Install or roll back the small configuration UI/runtime, never game data."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from build_configuration_profiles import profiles

ROOT = Path(__file__).resolve().parents[1]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def idle():
    if os.name == 'nt':
        p = subprocess.run(['powershell.exe', '-NoProfile', '-Command',
                            "if(Get-Process MagnaCarta -ErrorAction SilentlyContinue){exit 9}"],
                           capture_output=True, timeout=20)
        if p.returncode:
            raise ValueError('Exit game before updating the configuration runtime')


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.configuration-tmp')
    if temp.exists():
        raise ValueError('Unexpected existing update temporary file')
    temp.write_bytes(data)
    os.replace(temp, path)


def apply(runtime, native, record):
    idle()
    if record.exists():
        raise ValueError('New deployment record required')
    manifest = json.loads((runtime/'runtime.json').read_text(encoding='utf-8-sig'))
    if manifest['schema'] != 1:
        raise ValueError('Unsupported runtime layout')
    for name, digest in manifest['files'].items():
        if sha((runtime/name).read_bytes()) != digest:
            raise ValueError('Runtime input changed: ' + name)
    replacements = {}
    for name in ['Configure.ps1', 'Configure.xaml', 'EnhancementSettings.psm1']:
        replacements['config/'+name] = (ROOT/'src/configuration'/name).read_bytes()
    replacements['Start.ps1'] = (ROOT/'src/configuration/StartShared.ps1').read_bytes()
    replacements['config/configuration-ui.json'] = (ROOT/'locales/zh-CN/configuration-ui.json').read_bytes()
    replacements['config/configuration-logo.png'] = (ROOT/'locales/zh-CN/art/title-wordmark.png').read_bytes()
    replacements['modules/configuration.dll'] = (native/'workspace_profile.dll').read_bytes()
    replacements['modules/workspace_launcher.exe'] = (native/'workspace_launcher.exe').read_bytes()
    for name, data, _ in profiles():
        replacements['config/profiles/'+name+'.ini'] = data
        manifest['profiles'][name] = sha(data)
    for name, data in replacements.items():
        manifest['files'][name] = sha(data)
    replacements['runtime.json'] = (json.dumps(manifest, indent=2)+'\n').encode('utf8')
    record.mkdir(parents=True)
    (record/'settings.sha256').write_text(sha((runtime/'config/enhancements.json').read_bytes()),encoding='ascii')
    states = {}
    for name, data in replacements.items():
        target = runtime/name
        before = target.read_bytes() if target.is_file() else None
        if target.exists() and before is None:
            raise ValueError('Unexpected target path type: '+name)
        states[name] = {'before': sha(before) if before is not None else None, 'after': sha(data)}
        if before is not None:
            saved = record/'original'/name
            saved.parent.mkdir(parents=True, exist_ok=True)
            saved.write_bytes(before)
    (record/'changes.json').write_text(json.dumps(states, indent=2), encoding='utf8')
    applied = []
    try:
        for name, data in replacements.items():
            write(runtime/name, data)
            applied.append(name)
            if sha((runtime/name).read_bytes()) != states[name]['after']:
                raise ValueError('Update readback mismatch: '+name)
    except Exception:
        for name in reversed(applied):
            if states[name]['before'] is None:
                (runtime/name).unlink()
            else:
                write(runtime/name, (record/'original'/name).read_bytes())
        raise
    print(f'CONFIGURATION_UPDATE PASS files={len(states)} game_data_changed=false settings_preserved=true')


def rollback(runtime, record):
    idle()
    states = json.loads((record/'changes.json').read_text(encoding='utf8'))
    settings_guard=record/'settings.sha256'
    if settings_guard.exists() and sha((runtime/'config/enhancements.json').read_bytes()) != settings_guard.read_text(encoding='ascii'):
        raise ValueError('Settings changed since deployment; preserving settings and current UI')
    # 整批校验后才恢复；后续修改保留，拒绝部分覆盖。
    for name, state in states.items():
        if sha((runtime/name).read_bytes()) != state['after']:
            raise ValueError('Rollback target changed: '+name)
        if state['before'] is not None and sha((record/'original'/name).read_bytes()) != state['before']:
            raise ValueError('Rollback source changed: '+name)
    for name, state in reversed(list(states.items())):
        if state['before'] is None:
            (runtime/name).unlink()
        else:
            write(runtime/name, (record/'original'/name).read_bytes())
    for name, state in states.items():
        target = runtime/name
        if (target.exists() if state['before'] is None else sha(target.read_bytes()) != state['before']):
            raise ValueError('Rollback readback mismatch: '+name)
    print(f'CONFIGURATION_ROLLBACK PASS files={len(states)} original_hashes=exact settings_preserved=true')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['apply', 'rollback'])
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--record', type=Path, required=True)
    parser.add_argument('--native', type=Path)
    args = parser.parse_args()
    if args.action == 'apply':
        if args.native is None:
            parser.error('--native is required for apply')
        apply(args.runtime, args.native, args.record)
    else:
        rollback(args.runtime, args.record)
