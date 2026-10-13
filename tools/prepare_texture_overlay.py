"""Package an opt-in texture guard without replacing existing game/runtime files."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

SCRIPT=r'''param([switch]$VerifyOnly,[switch]$WithoutTextureGuard,[string]$SettingsFile='')
$ErrorActionPreference='Stop'
$lock=ConvertFrom-Json @'
__LOCK__
'@
function Hash($p){$h=[Security.Cryptography.SHA256]::Create();try{([BitConverter]::ToString($h.ComputeHash([IO.File]::ReadAllBytes($p)))).Replace('-','').ToLowerInvariant()}finally{$h.Dispose()}}
foreach($p in $lock.inputs.PSObject.Properties){if((Hash $p.Name) -ne $p.Value){throw ('Texture overlay input drift: '+$p.Name)}}
$game=$lock.workspace;$prior=Join-Path $game '.advanced-runtime'
Import-Module (Join-Path $prior 'EnhancementSettings.psm1') -Force
$mutex=New-Object Threading.Mutex($false,$lock.mutex)
if(-not $mutex.WaitOne(0)){throw 'Another configured entry is active'}
$oldMotion=$env:MC_MOTION60_COMPLETE;$oldArt=$env:MC_TITLE_BACKGROUND4K
try{
 if(-not $SettingsFile){$SettingsFile=Join-Path $prior 'enhancements.json'}
 $settings=Read-EnhancementSettings $SettingsFile
 $prep=& (Join-Path $prior 'StartEnhanced.ps1') -PrepareOnly -SettingsFile $SettingsFile
 if(-not $?){throw 'Configured preparation failed'}
 $prep|Write-Output
 $line=@($prep|Where-Object {$_ -match '^ENHANCEMENTS_PREPARED.*session='});if($line.Count -ne 1){throw 'Missing configured session'}
 $session=[IO.Path]::GetFullPath(($line[0] -replace '^.*session=','').Trim())
 if(-not $session.StartsWith((Join-Path $prior 'session-'),[StringComparison]::OrdinalIgnoreCase)){throw 'Unexpected session'}
 $env:MC_MOTION60_COMPLETE=if($settings.motion60){'1'}else{'0'};$env:MC_TITLE_BACKGROUND4K='1'
 $arguments=@('--workspace',$game,'--shim',(Join-Path $PSScriptRoot 'workspace_profile.dll'),'--profile',(Join-Path $session 'profile.bin'),'--log',(Join-Path $session 'profile.log'),'--native-text-step','--system-messages','--focus-guard','--display-profile',$settings.display_profile)
 if($settings.native_gamepad){$arguments+='--native-gamepad'}
 if(-not $WithoutTextureGuard){$arguments+='--texture-lifetime'}
 if($VerifyOnly){$arguments+='--verify-only'}
 & (Join-Path $PSScriptRoot 'workspace_launcher.exe') @arguments 1>(Join-Path $session 'launcher.stdout.txt') 2>(Join-Path $session 'launcher.stderr.txt')
 $code=$LASTEXITCODE
 @{exit_code=$code;texture_guard=(-not $WithoutTextureGuard);game_started=$(if($VerifyOnly){$false}else{$null});settings=$settings}|ConvertTo-Json -Depth 4|Set-Content -LiteralPath (Join-Path $session 'texture-overlay-result.json') -Encoding UTF8
 if($code -ne 0){throw ('Texture overlay exit='+$code+'; session='+$session)}
 Write-Output ('TEXTURE_OVERLAY_PASS guard='+(-not $WithoutTextureGuard)+' verify_only='+[bool]$VerifyOnly+' session='+$session)
}finally{$env:MC_MOTION60_COMPLETE=$oldMotion;$env:MC_TITLE_BACKGROUND4K=$oldArt;$mutex.ReleaseMutex();$mutex.Dispose()}
'''

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def prepare(workspace,native,output):
    workspace=workspace.resolve(strict=True);native=native.resolve(strict=True);output=output.resolve()
    if output.exists() or output==workspace or output.is_relative_to(workspace):
        raise ValueError('New independent runtime output required')
    prior=workspace/'.advanced-runtime'
    required=['StartEnhanced.ps1','EnhancementSettings.psm1','manifest.json','title-background.json','workspace_profile.dll','workspace_launcher.exe']
    for n in required:
        if not (prior/n).is_file():raise ValueError('Missing configured trial input: '+n)
    output.mkdir(parents=True)
    for n in ['workspace_profile.dll','workspace_launcher.exe']:shutil.copy2(native/n,output/n)
    lock=dict(schema=1,workspace=str(workspace),inputs={str(prior/n):sha(prior/n) for n in required},mutex='Local\\MagnaCartaAdvanced_'+hashlib.sha256(str(workspace).encode()).hexdigest()[:24])
    lock['inputs'].update({str(output/n):sha(output/n) for n in ['workspace_profile.dll','workspace_launcher.exe']})
    (output/'Start.ps1').write_bytes(SCRIPT.replace('__LOCK__',json.dumps(lock)).encode('utf-8-sig'))
    (output/'manifest.json').write_bytes((json.dumps(lock,indent=2)+'\n').encode('utf8'))
    for name,args in {'Play-texture-guard.cmd':'','Play-without-texture-guard.cmd':'-WithoutTextureGuard'}.items():
        (output/name).write_bytes(('@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start.ps1" '+args+'\r\nif errorlevel 1 pause\r\n').encode('ascii'))
    return lock

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('workspace','native','output'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();prepare(a.workspace,a.native,a.output)
    print('TEXTURE_OVERLAY_PACKAGE PASS original_runtime=retained copied_game_data=false game_started=false')
