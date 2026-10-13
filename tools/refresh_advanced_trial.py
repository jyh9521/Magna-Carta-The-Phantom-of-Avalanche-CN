"""Refresh owned runtime in an existing trial, retaining a hash-locked rollback."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import ctypes
import prepare_advanced_trial as trial

RESTORE = r'''$ErrorActionPreference='Stop'
$workspace=Split-Path -Parent $PSScriptRoot
$lock=ConvertFrom-Json @'
__RESTORE_LOCK__
'@
function Hash($p) { $h=[Security.Cryptography.SHA256]::Create();try {([BitConverter]::ToString($h.ComputeHash([IO.File]::ReadAllBytes($p)))).Replace('-','').ToLowerInvariant()}finally{$h.Dispose()} }
$mutex=New-Object Threading.Mutex($false,'__MUTEX__')
if(-not $mutex.WaitOne(0)){throw 'Another trial entry is active.'}
try {
 foreach($p in (Get-CimInstance Win32_Process -Filter "Name='MagnaCarta.exe'")) {
  if(-not $p.ExecutablePath){throw 'Process path unavailable.'}
  if([IO.Path]::GetFullPath($p.ExecutablePath) -eq (Join-Path $workspace 'MagnaCarta.exe')){throw 'Exit candidate game first.'}
 }
 foreach($p in $lock.current.PSObject.Properties){if((Hash (Join-Path $PSScriptRoot $p.Name)) -ne $p.Value){throw ('Unknown current runtime: '+$p.Name)}}
 foreach($p in $lock.previous.PSObject.Properties){if((Hash (Join-Path $PSScriptRoot ($lock.backup+'/'+$p.Name))) -ne $p.Value){throw ('Changed backup: '+$p.Name)}}
 if((Hash (Join-Path $workspace $lock.config)) -notin @($lock.profiles.PSObject.Properties.Value)){throw 'Unknown active config.'}
 if((Hash (Join-Path $PSScriptRoot 'baseline.ini')) -ne $lock.profiles.baseline){throw 'Changed baseline config.'}
 foreach($p in $lock.previous.PSObject.Properties){Copy-Item -LiteralPath (Join-Path $PSScriptRoot ($lock.backup+'/'+$p.Name)) -Destination (Join-Path $PSScriptRoot $p.Name)}
 Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'baseline.ini') -Destination (Join-Path $workspace $lock.config)
 foreach($p in $lock.previous.PSObject.Properties){if((Hash (Join-Path $PSScriptRoot $p.Name)) -ne $p.Value){throw 'Restore verification failed.'}}
 Write-Output 'PREVIOUS_RUNTIME_RESTORED PASS old_runtime=exact config=baseline saves=untouched game_started=false'
}finally{$mutex.ReleaseMutex();$mutex.Dispose()}
'''


def _refresh(workspace, native):
    workspace = trial.render.plain_path(workspace)
    native = trial.render.plain_path(native)
    runtime = trial.render.plain_path(workspace / '.advanced-runtime')
    manifest = runtime / 'manifest.json'
    old = json.loads(manifest.read_text('utf8'))
    if (old.get('schema') != 1 or old['workspace'] != str(workspace)
            or set(old['runtime_hashes']) != {'workspace_profile.dll', 'workspace_launcher.exe'}
            or old['config'] != trial.render.CONFIG_NAME
            or old['profiles'] != {n: trial.render.graphics.sha(d) for n, d in trial.render.PROFILES.items()}):
        raise ValueError('Moved candidate')
    query = "foreach($p in (Get-CimInstance Win32_Process -Filter \"Name='MagnaCarta.exe'\")){if(-not $p.ExecutablePath -or $p.ExecutablePath -eq '" + str(workspace / 'MagnaCarta.exe').replace("'", "''") + "'){exit 92}}"
    subprocess.run(['powershell.exe', '-NoProfile', '-Command', query], check=True,
                   capture_output=True, timeout=30)
    trial.render.checked_source(Path(old['source']))
    digest = trial.prepare_workspace.digest
    for name, sha in old['runtime_hashes'].items():
        if digest(runtime / name) != sha:
            raise ValueError('Changed runtime: ' + name)
    for name, sha in trial.render.SOURCE_INPUTS.items():
        if digest(workspace / name) != sha:
            raise ValueError('Changed candidate source: ' + name)
    for mode, sha in old['profiles'].items():
        if digest(runtime / (mode + '.ini')) != sha:
            raise ValueError('Changed profile: ' + mode)
    if digest(workspace / old['config']) not in old['profiles'].values():
        raise ValueError('Unknown config')
    new = json.loads(json.dumps(old))
    new['source_hashes'] = trial.render.SOURCE_HASHES
    new['runtime_hashes'] = {name: digest(native / name) for name in old['runtime_hashes']}
    mutex = 'Local\\MagnaCartaAdvanced_' + trial.render.graphics.sha(str(workspace).encode())[:24]
    expected_script = trial.SCRIPT.replace('__LOCK__', json.dumps(old, ensure_ascii=True)).replace(
        '__MANIFEST_HASH__', digest(manifest)).replace('__MUTEX__', mutex).encode('utf-8-sig')
    if (runtime / 'StartAdvanced.ps1').read_bytes() != expected_script:
        raise ValueError('Changed preparation script; no writes')
    names = [*old['runtime_hashes'], 'manifest.json', 'StartAdvanced.ps1']
    backup = runtime / ('previous-runtime-' + old['runtime_hashes']['workspace_profile.dll'][:16])
    if backup.exists():
        raise ValueError('Backup exists; no writes')
    current = {name: digest(runtime / name) for name in names}
    backup.mkdir()
    for name in names:
        shutil.copy2(runtime / name, backup / name)
        if digest(backup / name) != current[name]:
            raise ValueError('Backup mismatch')
    try:
        for name in old['runtime_hashes']:
            shutil.copy2(native / name, runtime / name)
        manifest.write_text(json.dumps(new, ensure_ascii=True, indent=2), encoding='utf8')
        script = trial.SCRIPT.replace('__LOCK__', json.dumps(new, ensure_ascii=True)).replace(
            '__MANIFEST_HASH__', digest(manifest)).replace('__MUTEX__', mutex)
        (runtime / 'StartAdvanced.ps1').write_text(script, encoding='utf-8-sig')
        restore = dict(current={n: digest(runtime / n) for n in names}, previous=current,
                       backup=backup.name, profiles=new['profiles'], config=new['config'])
        (runtime / 'RestorePrevious.ps1').write_text(RESTORE.replace('__RESTORE_LOCK__',
            json.dumps(restore, ensure_ascii=True)).replace('__MUTEX__', mutex), encoding='utf-8-sig')
        (workspace / 'Restore-previous.cmd').write_bytes(b'@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0.advanced-runtime\\RestorePrevious.ps1"\r\nif errorlevel 1 pause\r\n')
        (backup / 'rollback-manifest.json').write_text(json.dumps(restore, indent=2), encoding='utf8')
        return restore
    except BaseException:
        for name in names:
            shutil.copy2(backup / name, runtime / name)
        raise


def refresh(workspace, native):
    workspace = trial.render.plain_path(workspace)
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    k.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    k.CreateMutexW.restype = ctypes.c_void_p
    k.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    k.ReleaseMutex.argtypes = k.CloseHandle.argtypes = [ctypes.c_void_p]
    name = 'Local\\MagnaCartaAdvanced_' + trial.render.graphics.sha(str(workspace).encode())[:24]
    handle = k.CreateMutexW(None, False, name)
    if not handle:
        raise OSError(ctypes.get_last_error(), 'Mutex creation failed')
    owned = False
    try:
        owned = k.WaitForSingleObject(handle, 0) in (0, 128)
        if not owned:
            raise ValueError('Another trial entry is active')
        return _refresh(workspace, native)
    finally:
        if owned:
            k.ReleaseMutex(handle)
        k.CloseHandle(handle)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--native', type=Path, required=True)
    args = parser.parse_args()
    refresh(args.workspace, args.native)
    print('ADVANCED_REFRESH PASS runtime_updated=true previous_backup=verified saves=untouched game_started=false')
