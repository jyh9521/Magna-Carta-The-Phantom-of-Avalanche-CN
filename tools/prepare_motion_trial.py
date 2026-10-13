"""Prepare an isolated full-motion comparison on the existing display/art pipeline."""
import argparse
import json
from pathlib import Path
import build_title_background as title

START = r'''param([ValidateSet('wide4k','combined','fps60')][string]$Mode='combined',
 [switch]$LegacyPose,[switch]$PrepareOnly,[switch]$Rollback)
$ErrorActionPreference='Stop'
$lock=ConvertFrom-Json @'
__LOCK__
'@
function Hash($p){$h=[Security.Cryptography.SHA256]::Create();try{([BitConverter]::ToString($h.ComputeHash([IO.File]::ReadAllBytes($p)))).Replace('-','').ToLowerInvariant()}finally{$h.Dispose()}}
foreach($p in $lock.inputs.PSObject.Properties){if((Hash (Join-Path $PSScriptRoot $p.Name)) -ne $p.Value){throw ('Motion input drift: '+$p.Name)}}
$old=$env:MC_MOTION60_COMPLETE
try {
 $env:MC_MOTION60_COMPLETE=if(-not $Rollback -and -not $LegacyPose -and $Mode -ne 'wide4k'){'1'}else{'0'}
 if($Rollback){& (Join-Path $PSScriptRoot 'StartAdvanced.ps1') -Rollback}
 else {& (Join-Path $PSScriptRoot 'StartTitle.ps1') -Mode $Mode -PrepareOnly:$PrepareOnly}
}finally{$env:MC_MOTION60_COMPLETE=$old}
'''

def write_entrypoints(output):
    runtime = output / '.advanced-runtime'
    names = ['StartTitle.ps1', 'StartAdvanced.ps1', 'manifest.json',
             'workspace_profile.dll', 'workspace_launcher.exe', 'title-background.json']
    lock = {'schema': 1, 'inputs': {name: title.sha(runtime/name) for name in names},
            'full_motion_default': True, 'logic_interval_ms': 33,
            'in_game_verified': False}
    (runtime/'motion-trial.json').write_text(json.dumps(lock, indent=2)+'\n', encoding='utf8')
    (runtime/'StartMotion.ps1').write_text(START.replace('__LOCK__', json.dumps(lock)), encoding='utf-8-sig')
    for name, arguments in {
        'Play-30fps.cmd': '-Mode wide4k',
        'Play-60fps-legacy.cmd': '-Mode combined -LegacyPose',
        'Play-60fps-complete.cmd': '-Mode combined',
        'Rollback-motion.cmd': '-Rollback',
    }.items():
        command = '@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0.advanced-runtime\\StartMotion.ps1" '+arguments+'\r\nif errorlevel 1 pause\r\n'
        (output/name).write_bytes(command.encode('ascii'))
    return lock

def prepare(source, native, locale, output):
    title.build(source, native, locale, output)
    return write_entrypoints(output)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'native', 'locale', 'output'):
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    prepare(*(getattr(args, name).resolve() for name in ('source','native','locale','output')))
    print('MOTION_TRIAL PASS isolated=true display_art=retained full_motion=opt_in game_started=false')
