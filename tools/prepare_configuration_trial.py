"""Package the built-in Windows Forms configuration UI with locked runtime inputs."""
import argparse
import json
from pathlib import Path
import shutil
import prepare_gamepad_trial as gamepad

START=r'''param([string]$SettingsFile='',[switch]$PrepareOnly,[switch]$VerifyOnly,[switch]$Rollback)
$ErrorActionPreference='Stop'
$r=Split-Path -Parent $PSScriptRoot
$lock=ConvertFrom-Json @'
__LOCK__
'@
function Hash($p){$h=[Security.Cryptography.SHA256]::Create();try{([BitConverter]::ToString($h.ComputeHash([IO.File]::ReadAllBytes($p)))).Replace('-','').ToLowerInvariant()}finally{$h.Dispose()}}
foreach($p in $lock.inputs.PSObject.Properties){if((Hash (Join-Path $PSScriptRoot $p.Name)) -ne $p.Value){throw ('Enhancement input drift: '+$p.Name)}}
Import-Module (Join-Path $PSScriptRoot 'EnhancementSettings.psm1') -Force
if(-not $SettingsFile){$SettingsFile=Join-Path $PSScriptRoot 'enhancements.json'}
$settings=Read-EnhancementSettings $SettingsFile
$mutex=New-Object Threading.Mutex($false,'__MUTEX__')
if(-not $mutex.WaitOne(0)){throw 'Another trial entry is active'}
$oldMotion=$env:MC_MOTION60_COMPLETE;$oldArt=$env:MC_TITLE_BACKGROUND4K
try {
 if($Rollback){& (Join-Path $PSScriptRoot 'StartAdvanced.ps1') -Rollback;exit 0}
 $env:MC_MOTION60_COMPLETE=if($settings.motion60){'1'}else{'0'}
 $env:MC_TITLE_BACKGROUND4K='1'
 $prep=& (Join-Path $PSScriptRoot 'StartTitle.ps1') -Mode $settings.display_profile -PrepareOnly
 if(-not $?){throw 'Enhancement preparation failed'}
 $prep|Write-Output
 $line=@($prep|Where-Object {$_ -match '^ADVANCED_PREPARED.*session='});if($line.Count -ne 1){throw 'Missing session'}
 $session=[IO.Path]::GetFullPath(($line[0] -replace '^.*session=','').Trim())
 if(-not $session.StartsWith((Join-Path $PSScriptRoot 'session-'),[StringComparison]::OrdinalIgnoreCase)){throw 'Unexpected session'}
 $settings|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $session 'enhancement-selection.json') -Encoding UTF8
 if($PrepareOnly){Write-Output ('ENHANCEMENTS_PREPARED profile='+$settings.display_profile+' motion='+$settings.motion60+' gamepad='+$settings.native_gamepad+' game_started=false session='+$session);exit 0}
 $arguments=@('--workspace',$r,'--shim',(Join-Path $PSScriptRoot 'workspace_profile.dll'),'--profile',(Join-Path $session 'profile.bin'),'--log',(Join-Path $session 'profile.log'),'--native-text-step','--system-messages','--focus-guard','--display-profile',$settings.display_profile)
 if($settings.native_gamepad){$arguments+='--native-gamepad'}
 if($VerifyOnly){$arguments+='--verify-only'}
 & (Join-Path $PSScriptRoot 'workspace_launcher.exe') @arguments 1>(Join-Path $session 'launcher.stdout.txt') 2>(Join-Path $session 'launcher.stderr.txt')
 $code=$LASTEXITCODE
 @{exit_code=$code;game_started=$(if($VerifyOnly){$false}else{$null});launcher_invoked=$true;verify_only=[bool]$VerifyOnly;settings=$settings}|ConvertTo-Json -Depth 4|Set-Content -LiteralPath (Join-Path $session 'enhancement-result.json') -Encoding UTF8
 if($code -ne 0){throw ('Enhancement launcher exit='+$code+'; see '+$session)}
}finally{$env:MC_MOTION60_COMPLETE=$oldMotion;$env:MC_TITLE_BACKGROUND4K=$oldArt;$mutex.ReleaseMutex();$mutex.Dispose()}
'''

def write_entrypoints(output,locale):
    runtime=output/'.advanced-runtime';root=Path(__file__).resolve().parents[1]
    for name in ('Configure.ps1','EnhancementSettings.psm1'):shutil.copy2(root/'src/configuration'/name,runtime/name)
    shutil.copy2(locale/'configuration-ui.json',runtime/'configuration-ui.json')
    names=['StartTitle.ps1','StartAdvanced.ps1','manifest.json','title-background.json','workspace_profile.dll','workspace_launcher.exe','Configure.ps1','EnhancementSettings.psm1','configuration-ui.json']
    lock={'schema':1,'inputs':{n:gamepad.motion.title.sha(runtime/n) for n in names},'in_game_verified':False}
    mutex='Local\\MagnaCartaAdvanced_'+gamepad.motion.title.prepare_advanced_trial.render.graphics.sha(str(output).encode())[:24]
    (runtime/'StartEnhanced.ps1').write_text(START.replace('__LOCK__',json.dumps(lock)).replace('__MUTEX__',mutex),encoding='utf-8-sig')
    (runtime/'enhancement-package.json').write_text(json.dumps(lock,indent=2)+'\n',encoding='utf8')
    settings=runtime/'enhancements.json'
    if not settings.exists():settings.write_text(json.dumps(dict(schema=1,display_profile='wide4k',motion60=False,native_gamepad=False),indent=2)+'\n',encoding='utf8')
    for name,args in {'Configure.cmd':'-STA -File "%~dp0.advanced-runtime\\Configure.ps1"','Play-configured.cmd':'-File "%~dp0.advanced-runtime\\StartEnhanced.ps1"','Rollback-configured.cmd':'-File "%~dp0.advanced-runtime\\StartEnhanced.ps1" -Rollback'}.items():
        (output/name).write_bytes(('@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass '+args+'\r\nif errorlevel 1 pause\r\n').encode('ascii'))
    return lock

def prepare(source,native,locale,output):
    gamepad.prepare(source,native,locale,output)
    return write_entrypoints(output,locale)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('source','native','locale','output'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();prepare(*(getattr(args,n).resolve() for n in ('source','native','locale','output')))
    print('CONFIGURATION_TRIAL PASS settings=validated ui=windows_forms source_unchanged=true game_started=false')
