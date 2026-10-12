"""Windows integration checks for the compiled registry isolation fixture."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import winreg

KEY = r'SOFTWARE\Softmax\MagnaCarta'
VIRTUAL = r'Software\Classes\VirtualStore\MACHINE\SOFTWARE\WOW6432Node\SOFTMAX\MagnaCarta'
SESSIONS = r'Software\MagnaCartaWorkspace\Sessions'


def snapshot(root, path, view):
    values = []
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_READ | view) as key:
            count, total, _ = winreg.QueryInfoKey(key)
            for i in range(total):
                name, value, kind = winreg.EnumValue(key, i)
                values.append((name, value.hex() if isinstance(value, bytes) else value, kind))
            children = [winreg.EnumKey(key, i) for i in range(count)]
        nested = [(name, snapshot(root, path + '\\' + name, view)) for name in children]
        return hashlib.sha256(json.dumps([sorted(values), sorted(nested)], sort_keys=True).encode()).hexdigest()
    except FileNotFoundError:
        return None


def session_names():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, SESSIONS, 0, winreg.KEY_READ | winreg.KEY_WOW64_32KEY) as key:
            return sorted(winreg.EnumKey(key, i) for i in range(winreg.QueryInfoKey(key)[0]))
    except FileNotFoundError:
        return []


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--bin', type=Path, required=True)
    p.add_argument('--profile', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=False)
    fixture = a.output / 'workspace'
    fixture.mkdir()
    shutil.copy2(a.bin / 'registry_probe.exe', fixture / 'registry_probe.exe')
    before = (snapshot(winreg.HKEY_LOCAL_MACHINE, KEY, winreg.KEY_WOW64_32KEY),
              snapshot(winreg.HKEY_CURRENT_USER, VIRTUAL, winreg.KEY_WOW64_64KEY))
    sessions = session_names()
    baseline = subprocess.run([str(fixture / 'registry_probe.exe')], capture_output=True, text=True)
    assert baseline.returncode == 0, baseline.stderr
    command = [str(a.bin / 'workspace_launcher.exe'), '--fixture', '--workspace', str(fixture),
        '--shim', str(a.bin / 'workspace_profile.dll'), '--profile', str(a.profile),
        '--log', str(a.output / 'isolated.log'), '--timeout', '10']
    modified = subprocess.run(list(command), capture_output=True, text=True)
    assert modified.returncode == 0, modified.stderr
    assert 'redirected=true renderer=direct3d' in modified.stdout
    assert before == (snapshot(winreg.HKEY_LOCAL_MACHINE, KEY, winreg.KEY_WOW64_32KEY),
                      snapshot(winreg.HKEY_CURRENT_USER, VIRTUAL, winreg.KEY_WOW64_64KEY))
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, KEY, 0, winreg.KEY_READ | winreg.KEY_WOW64_32KEY) as key:
        original_directory = winreg.QueryValueEx(key, 'Directory')[0]
    command[command.index('--workspace') + 1] = original_directory
    command[command.index('--log') + 1] = str(a.output / 'original-guard.log')
    guarded = subprocess.run(command, capture_output=True, text=True)
    assert guarded.returncode == 125 and 'Original install must not be used' in guarded.stderr
    assert not (a.output / 'original-guard.log').exists()
    assert sessions == session_names()
    cleanup_guard = subprocess.run([str(a.bin / 'workspace_launcher.exe'), '--cleanup-session', '..\\SOFTMAX'], capture_output=True, text=True)
    assert cleanup_guard.returncode == 125 and 'Invalid session token' in cleanup_guard.stderr
    assert before == (snapshot(winreg.HKEY_LOCAL_MACHINE, KEY, winreg.KEY_WOW64_32KEY),
                      snapshot(winreg.HKEY_CURRENT_USER, VIRTUAL, winreg.KEY_WOW64_64KEY))
    assert sessions == session_names()
    restored = subprocess.run([str(fixture / 'registry_probe.exe')], capture_output=True, text=True)
    assert restored.returncode == 0 and restored.stdout == baseline.stdout
    invalid = a.output / 'invalid-profile.bin'
    invalid.write_bytes(b'\0' * 51)
    command[command.index('--workspace') + 1] = str(fixture)
    command[command.index('--profile') + 1] = str(invalid)
    command[command.index('--log') + 1] = str(a.output / 'invalid.log')
    rejected = subprocess.run(command, capture_output=True, text=True)
    assert rejected.returncode == 125 and 'Unsupported settings layout' in rejected.stderr
    assert sessions == session_names()
    assert before == (snapshot(winreg.HKEY_LOCAL_MACHINE, KEY, winreg.KEY_WOW64_32KEY),
                      snapshot(winreg.HKEY_CURRENT_USER, VIRTUAL, winreg.KEY_WOW64_64KEY))
    report = {'baseline': baseline.stdout.strip(), 'modified': modified.stdout.strip(),
        'restored': restored.stdout.strip(), 'source_registry_unchanged': True,
        'session_cleanup': True, 'invalid_profile_rejected': True,
        'original_directory_guard': True, 'cleanup_path_guard': True,
        'source_registry_hashes': before,
        'commands': {'baseline': baseline.args, 'modified': modified.args, 'rollback': restored.args}}
    (a.output / 'results.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('RUNTIME_ISOLATION PASS checks=8 source_registry_unchanged=true session_cleanup=true')
