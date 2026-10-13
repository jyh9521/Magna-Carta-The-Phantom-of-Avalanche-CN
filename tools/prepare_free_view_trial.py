"""Package opt-in render-only orbit candidate with the accepted 4K/60Hz profile."""
import argparse
from pathlib import Path
import prepare_texture_overlay as overlay

def write_entrypoints(output,lock):
    script=overlay.SCRIPT.replace("[string]$SettingsFile='')", "[string]$SettingsFile='',[switch]$WithoutFreeView)")
    script=script.replace("$oldMotion=$env:MC_MOTION60_COMPLETE;$oldArt=$env:MC_TITLE_BACKGROUND4K", "$oldMotion=$env:MC_MOTION60_COMPLETE;$oldArt=$env:MC_TITLE_BACKGROUND4K;$oldFree=$env:MC_FREE_VIEW")
    script=script.replace("$settings=Read-EnhancementSettings $SettingsFile", """$settings=Read-EnhancementSettings $SettingsFile
 $settings.display_profile='combined';$settings.motion60=$true
 $SettingsFile=Join-Path $PSScriptRoot ('free-view-settings-'+[Guid]::NewGuid().ToString('N')+'.json')
 $settings|ConvertTo-Json|Set-Content -LiteralPath $SettingsFile -Encoding UTF8
 $env:MC_FREE_VIEW=if($WithoutFreeView){'0'}else{'1'}
 $WithoutTextureGuard=$true""")
    script=script.replace('texture_guard=(-not $WithoutTextureGuard);','texture_guard=(-not $WithoutTextureGuard);free_view=(-not $WithoutFreeView);')
    script=script.replace('TEXTURE_OVERLAY_PASS','FREE_VIEW_PREFLIGHT_PASS')
    script=script.replace("finally{$env:MC_MOTION60_COMPLETE", "finally{$env:MC_FREE_VIEW=$oldFree;$env:MC_MOTION60_COMPLETE")
    (output/'StartFreeView.ps1').write_bytes(script.replace('__LOCK__',__import__('json').dumps(lock)).encode('utf-8-sig'))
    for name,args in {'Play-free-view.cmd':'','Play-without-free-view.cmd':'-WithoutFreeView'}.items():
        (output/name).write_bytes(('@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0StartFreeView.ps1" '+args+'\r\nif errorlevel 1 pause\r\n').encode('ascii'))
    return lock

def prepare(workspace,native,output):
    lock=overlay.prepare(workspace,native,output)
    return write_entrypoints(output,lock)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','native','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();prepare(a.workspace.resolve(),a.native.resolve(),a.output.resolve())
    print('FREE_VIEW_TRIAL PASS display=combined motion=complete texture_guard=off original_settings=retained game_started=false')
