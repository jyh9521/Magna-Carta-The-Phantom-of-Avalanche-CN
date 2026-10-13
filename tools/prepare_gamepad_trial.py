"""Create an isolated display/motion/XInput comparison without launching the game."""
import argparse
import json
from pathlib import Path
import prepare_motion_trial as motion

START = r'''param([ValidateSet('wide4k','combined')][string]$Mode='combined',[switch]$PrepareOnly,[switch]$NoGamepad,[switch]$VerifyOnly)
$ErrorActionPreference='Stop'
$r=Split-Path -Parent $PSScriptRoot
$lock=ConvertFrom-Json @'
__LOCK__
'@
function Hash($p){$h=[Security.Cryptography.SHA256]::Create();try{([BitConverter]::ToString($h.ComputeHash([IO.File]::ReadAllBytes($p)))).Replace('-','').ToLowerInvariant()}finally{$h.Dispose()}}
foreach($p in $lock.inputs.PSObject.Properties){if((Hash (Join-Path $PSScriptRoot $p.Name)) -ne $p.Value){throw ('Gamepad trial input drift: '+$p.Name)}}
$mutex=New-Object Threading.Mutex($false,'__MUTEX__')
if(-not $mutex.WaitOne(0)){throw 'Another trial entry is active'}
$oldMotion=$env:MC_MOTION60_COMPLETE
$oldArt=$env:MC_TITLE_BACKGROUND4K
try {
 $env:MC_MOTION60_COMPLETE=if($Mode -eq 'combined'){'1'}else{'0'}
 $env:MC_TITLE_BACKGROUND4K='1'
 $prep=& (Join-Path $PSScriptRoot 'StartMotion.ps1') -Mode $Mode -PrepareOnly
 if(-not $?){throw 'Motion preparation failed'}
 $prep | Write-Output
 $line=@($prep|Where-Object {$_ -match '^ADVANCED_PREPARED.*session='})
 if($line.Count -ne 1){throw 'Missing prepared session'}
 $session=[IO.Path]::GetFullPath(($line[0] -replace '^.*session=','').Trim())
 if(-not $session.StartsWith((Join-Path $PSScriptRoot 'session-'),[StringComparison]::OrdinalIgnoreCase)){throw 'Unexpected session path'}
 if($PrepareOnly){Write-Output ('GAMEPAD_PREPARED native_enabled='+(-not $NoGamepad)+' game_started=false session='+$session);exit 0}
 $arguments=@('--workspace',$r,'--shim',(Join-Path $PSScriptRoot 'workspace_profile.dll'),'--profile',(Join-Path $session 'profile.bin'),'--log',(Join-Path $session 'profile.log'),'--native-text-step','--system-messages','--focus-guard','--display-profile',$Mode)
 if(-not $NoGamepad){$arguments+='--native-gamepad'}
 if($VerifyOnly){$arguments+='--verify-only'}
 & (Join-Path $PSScriptRoot 'workspace_launcher.exe') @arguments 1>(Join-Path $session 'launcher.stdout.txt') 2>(Join-Path $session 'launcher.stderr.txt')
 $code=$LASTEXITCODE
 @{native_gamepad=(-not $NoGamepad);verify_only=[bool]$VerifyOnly;exit_code=$code;game_started=(-not $VerifyOnly)}|ConvertTo-Json|Set-Content (Join-Path $session 'gamepad-result.json') -Encoding UTF8
 if($code -ne 0){throw ('Gamepad launcher exit='+$code+'; see '+$session)}
}finally{$env:MC_MOTION60_COMPLETE=$oldMotion;$env:MC_TITLE_BACKGROUND4K=$oldArt;$mutex.ReleaseMutex();$mutex.Dispose()}
'''

def write_entrypoints(output):
    runtime=output/'.advanced-runtime'
    names=['StartMotion.ps1','motion-trial.json','StartTitle.ps1','StartAdvanced.ps1','manifest.json','workspace_profile.dll','workspace_launcher.exe','title-background.json']
    lock={'schema':1,'inputs':{name:motion.title.sha(runtime/name) for name in names},'in_game_verified':False,'physical_controller_verified':False}
    mutex='Local\\MagnaCartaAdvanced_'+motion.title.prepare_advanced_trial.render.graphics.sha(str(output).encode())[:24]
    (runtime/'StartGamepad.ps1').write_text(START.replace('__LOCK__',json.dumps(lock)).replace('__MUTEX__',mutex),encoding='utf-8-sig')
    (runtime/'gamepad-trial.json').write_text(json.dumps(lock,indent=2)+'\n',encoding='utf8')
    for name,args in {'Play-Xbox.cmd':'-Mode combined','Play-keyboard-mouse.cmd':'-Mode combined -NoGamepad','Play-Xbox-30fps.cmd':'-Mode wide4k'}.items():
        (output/name).write_bytes(('@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0.advanced-runtime\\StartGamepad.ps1" '+args+'\r\nif errorlevel 1 pause\r\n').encode('ascii'))
    return lock

def prepare(source,native,locale,output):
    motion.prepare(source,native,locale,output)
    return write_entrypoints(output)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','native','locale','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    prepare(*(getattr(args,k).resolve() for k in ('source','native','locale','output')))
    print('GAMEPAD_TRIAL PASS isolated=true accepted_display_art=retained game_started=false')
