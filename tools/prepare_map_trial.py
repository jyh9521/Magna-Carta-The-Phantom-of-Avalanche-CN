"""Package a non-activating terrain overlay beside the verified game trial."""
import argparse
import json
import shutil
from pathlib import Path
import prepare_texture_overlay as overlay

def write_entrypoints(output,lock,assets):
    manifest=json.loads((assets/'manifest.json').read_text(encoding='utf8'))
    if manifest.get('schema')!=1 or manifest.get('projection')!='first_instance_frame_column_major_XY' or manifest.get('navigation_verified') is not False:raise ValueError('Unsupported map atlas schema')
    lock['inputs'][str(assets/'manifest.json')]=overlay.sha(assets/'manifest.json')
    for row in manifest['accepted']:
        for extension,key in [('png','png_sha256'),('map','metadata_sha256')]:
            path=assets/f"{row['id']:04d}.{extension}"
            if overlay.sha(path)!=row[key]:raise ValueError('Map asset mismatch')
            lock['inputs'][str(path)]=row[key]
    lock['inputs'][str(assets/'label.txt')]=overlay.sha(assets/'label.txt')
    script=overlay.SCRIPT.replace("[string]$SettingsFile='')", "[string]$SettingsFile='',[switch]$WithoutMap)")
    script=script.replace('$oldMotion=$env:MC_MOTION60_COMPLETE;$oldArt=$env:MC_TITLE_BACKGROUND4K', '$oldMotion=$env:MC_MOTION60_COMPLETE;$oldArt=$env:MC_TITLE_BACKGROUND4K;$oldMap=$env:MC_MAP_OVERLAY;$oldAssets=$env:MC_MAP_ASSETS;$oldFree=$env:MC_FREE_VIEW')
    script=script.replace('\ntry{\n', "\ntry{\n $env:MC_MAP_OVERLAY=if($WithoutMap){'0'}else{'1'}\n $env:MC_MAP_ASSETS='__ASSETS__'\n $env:MC_FREE_VIEW='0'\n $WithoutTextureGuard=$true\n",1)
    script=script.replace("if($settings.native_gamepad){$arguments+='--native-gamepad'}", "if($settings.native_gamepad){$arguments+='--native-gamepad'}else{$arguments+='--input-passthrough'}")
    script=script.replace('texture_guard=(-not $WithoutTextureGuard);','texture_guard=(-not $WithoutTextureGuard);map_overlay=(-not $WithoutMap);')
    script=script.replace('TEXTURE_OVERLAY_PASS','MAP_PREFLIGHT_PASS')
    script=script.replace('finally{$env:MC_MOTION60_COMPLETE', 'finally{$env:MC_MAP_OVERLAY=$oldMap;$env:MC_MAP_ASSETS=$oldAssets;$env:MC_FREE_VIEW=$oldFree;$env:MC_MOTION60_COMPLETE')
    script=script.replace('__LOCK__',json.dumps(lock)).replace('__ASSETS__',str(assets).replace("'","''"))
    (output/'StartMap.ps1').write_bytes(script.encode('utf-8-sig'))
    (output/'map-package.json').write_bytes(json.dumps(lock,indent=2).encode('utf8'))
    for name,args in {'Play-maps.cmd':'','Play-without-maps.cmd':'-WithoutMap'}.items():
        (output/name).write_bytes(('@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0StartMap.ps1" '+args+'\r\nif errorlevel 1 pause\r\n').encode('ascii'))
    return lock

def prepare(workspace,native,atlas,locale,output):
    lock=overlay.prepare(workspace,native,output)
    assets=output/'maps';assets.mkdir()
    manifest=json.loads((atlas/'manifest.json').read_text(encoding='utf8'))
    shutil.copy2(atlas/'manifest.json',assets/'manifest.json')
    for row in manifest['accepted']:
        for extension in ['png','map']:shutil.copy2(atlas/f"{row['id']:04d}.{extension}",assets/f"{row['id']:04d}.{extension}")
    label=json.loads((locale/'map-ui.json').read_text(encoding='utf8'))['map_title']
    if not isinstance(label,str) or not label or len(label)>120:raise ValueError('Invalid map title')
    (assets/'label.txt').write_bytes(label.encode('utf-16le'))
    return write_entrypoints(output,lock,assets)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('workspace','native','atlas','locale','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();prepare(*(getattr(a,name).resolve() for name in ('workspace','native','atlas','locale','output')))
    manifest=json.loads((a.atlas/'manifest.json').read_text(encoding='utf8'))
    print(f"MAP_TRIAL PASS initial=off terrain_assets={len(manifest['accepted'])} rejected={len(manifest['rejected'])} source_runtime=retained game_started=false")
