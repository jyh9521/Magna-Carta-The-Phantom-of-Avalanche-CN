"""Replace only guarded title assets; preserve a hash-locked previous revision."""
import argparse
import ctypes
import json
from pathlib import Path
import shutil
import subprocess
import uuid

from build_title_background import sha
import render_candidate

TILES = {f'BGR/{i:04d}.BGR' for i in range(357,369)}
EXTRAS = ['.advanced-runtime/title-background-4k.png'] + [
    f'.advanced-runtime/title-preview-{w}x{h}.png'
    for w,h in [(1920,1080),(1280,720),(640,480),(800,600)]]
MANIFEST = '.advanced-runtime/title-background.json'
RESTORE = r'''$ErrorActionPreference='Stop'
$root=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
function Hash($p){$h=[Security.Cryptography.SHA256]::Create();try{([BitConverter]::ToString($h.ComputeHash([IO.File]::ReadAllBytes($p)))).Replace('-','').ToLowerInvariant()}finally{$h.Dispose()}}
if(Get-Process MagnaCarta -ErrorAction SilentlyContinue){throw 'Close game before background restore'}
$m=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'restore.json') -Raw | ConvertFrom-Json
foreach($p in $m.PSObject.Properties){
 if((Hash (Join-Path $root $p.Name)) -ne $p.Value.after){throw ('Modified file drift: '+$p.Name)}
 if((Hash (Join-Path $PSScriptRoot ('files/'+$p.Name))) -ne $p.Value.before){throw ('Backup drift: '+$p.Name)}
}
foreach($p in $m.PSObject.Properties){Copy-Item -LiteralPath (Join-Path $PSScriptRoot ('files/'+$p.Name)) -Destination (Join-Path $root $p.Name) -Force}
Write-Output 'TITLE_PREVIOUS_RESTORE PASS assets=exact previous_background=restored game_started=false'
'''


def _refresh(workspace, replacement):
    old=json.loads((workspace/MANIFEST).read_text('utf-8-sig'))
    new=json.loads((replacement/MANIFEST).read_text('utf-8-sig'))
    if not old.get('active') or not new.get('active'):
        raise ValueError('Active HD candidates required')
    if set(old['tiles']) != TILES or set(new['tiles']) != TILES:
        raise ValueError('Unexpected tile set')
    for name in sorted(TILES):
        if old['tiles'][name]['before'] != new['tiles'][name]['before']:
            raise ValueError('Original version mismatch')
        if sha(workspace/name) != old['tiles'][name]['after'] or sha(replacement/name) != new['tiles'][name]['after']:
            raise ValueError('Title tile drift: '+name)
    if sha(workspace/EXTRAS[0]) != old['master_sha256'] or sha(replacement/EXTRAS[0]) != new['master_sha256']:
        raise ValueError('Master drift')
    names=sorted(TILES)+EXTRAS+[MANIFEST]
    rows={name:{'before':sha(workspace/name),'after':sha(replacement/name)} for name in names}
    backup=workspace/'.advanced-runtime'/('previous-title-'+old['master_sha256'][:16]+'-'+uuid.uuid4().hex[:8])
    backup.mkdir()
    for name,row in rows.items():
        dest=backup/'files'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(workspace/name,dest)
        if sha(dest)!=row['before']:raise ValueError('Backup mismatch')
    (backup/'restore.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf8')
    (backup/'Restore.ps1').write_text(RESTORE,encoding='utf-8-sig')
    tried=[]
    try:
        for name in names:
            tried.append(name);shutil.copyfile(replacement/name,workspace/name)
            if sha(workspace/name)!=rows[name]['after']:raise ValueError('Write mismatch')
    except Exception:
        for name in tried:shutil.copyfile(backup/'files'/name,workspace/name)
        raise
    cmd='@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0.advanced-runtime\\'+backup.name+'\\Restore.ps1"\r\nif errorlevel 1 pause\r\n'
    (workspace/'Restore-previous-background.cmd').write_bytes(cmd.encode('ascii'))
    return backup


def refresh(workspace,replacement):
    workspace=render_candidate.plain_path(workspace);replacement=render_candidate.plain_path(replacement)
    build=Path(__file__).resolve().parents[1]/'build'
    if workspace==replacement or not workspace.is_relative_to(build) or not replacement.is_relative_to(build):
        raise ValueError('Independent repository build candidates required')
    # Same named mutex as StartAdvanced: no live candidate is replaced.
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p];k.CreateMutexW.restype=ctypes.c_void_p
    k.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_uint]
    k.ReleaseMutex.argtypes=k.CloseHandle.argtypes=[ctypes.c_void_p]
    handle=k.CreateMutexW(None,False,'Local\\MagnaCartaAdvanced_'+render_candidate.graphics.sha(str(workspace).encode())[:24])
    if not handle:raise OSError(ctypes.get_last_error())
    owned=False
    try:
        owned=k.WaitForSingleObject(handle,0) in (0,128)
        if not owned:raise ValueError('Candidate entry is active')
        process=subprocess.run(['powershell.exe','-NoProfile','-Command','if(Get-Process MagnaCarta -ErrorAction SilentlyContinue){exit 1}'],capture_output=True)
        if process.returncode:raise ValueError('Close game before title refresh')
        return _refresh(workspace,replacement)
    finally:
        if owned:k.ReleaseMutex(handle)
        k.CloseHandle(handle)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace',type=Path,required=True)
    parser.add_argument('--replacement',type=Path,required=True)
    args=parser.parse_args()
    backup=refresh(args.workspace,args.replacement)
    print('TITLE_BACKGROUND_REFRESH PASS tiles=12 previous_backup='+str(backup)+' game_started=false')
