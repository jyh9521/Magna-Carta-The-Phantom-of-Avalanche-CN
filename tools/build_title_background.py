"""Source-locked HD title background packing; never launches a game.

Creative background generation is stored input. Rebuilds are offline and
deterministic. Only a newly prepared candidate below build is modified.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct

from PIL import Image
from resource_image import parse, ResourceImage
import prepare_advanced_trial


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def master(locale, plan):
    source = locale / plan['source']
    logo = locale / plan['wordmark']
    if sha(source) != plan['source_sha256'] or sha(logo) != plan['wordmark_sha256']:
        raise ValueError('Artwork input drift')
    image = Image.open(source).convert('RGBA').resize(tuple(plan['size']), Image.Resampling.LANCZOS)
    x, y, right, bottom = plan['wordmark_box']
    mark = Image.open(logo).convert('RGBA')
    mark.thumbnail((right-x, bottom-y), Image.Resampling.LANCZOS)
    # Preserve the existing wordmark itself, uniformly scaled, not regenerated.
    factor = min((right-x)/mark.width, (bottom-y)/mark.height)
    mark = mark.resize((round(mark.width*factor), round(mark.height*factor)), Image.Resampling.LANCZOS)
    image.alpha_composite(mark, (x+(right-x-mark.width)//2, y+(bottom-y-mark.height)//2))
    return image


def centered_view(image, width, height):
    """Center-crop to target aspect, then uniformly resample for export."""
    ratio = width / height
    if image.width / image.height > ratio:
        crop_width = round(image.height * ratio)
        left = (image.width-crop_width)//2
        box = (left, 0, left+crop_width, image.height)
    else:
        crop_height = round(image.width/ratio)
        top = (image.height-crop_height)//2
        box = (0, top, image.width, top+crop_height)
    return image.crop(box).resize((width, height), Image.Resampling.LANCZOS)


def pack(original, image, x, y, size=2048):
    src = parse(original)
    if src.format != 'TGA' or (src.width, src.height) != (256, 256) or len(src.wrapper) != 24:
        raise ValueError('Unsupported title tile version/layout')
    tile = Image.new('RGBA', (size, size))
    crop = image.crop((x, y, min(x+size, image.width), min(y+size, image.height)))
    tile.paste(crop, (0, 0))
    header = bytearray(src.header)
    struct.pack_into('<HH', header, 12, size, size)
    pixels = tile.transpose(Image.Transpose.FLIP_TOP_BOTTOM).tobytes('raw', 'BGRA')
    result = ResourceImage(src.wrapper, bytes(header), pixels, src.suffix, 'TGA', size, size, size*4)
    return result.to_bytes()


START = r'''param([string]$Mode='wide4k',[switch]$PrepareOnly,[switch]$Rollback)
$ErrorActionPreference='Stop'
$r=Split-Path -Parent $PSScriptRoot
$m=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'title-background.json') -Raw | ConvertFrom-Json
function Hash($p){$h=[Security.Cryptography.SHA256]::Create();try{([BitConverter]::ToString($h.ComputeHash([IO.File]::ReadAllBytes($p)))).Replace('-','').ToLowerInvariant()}finally{$h.Dispose()}}
foreach($p in $m.tiles.PSObject.Properties){
 $expected=if($m.active){$p.Value.after}else{$p.Value.before}
 if((Hash (Join-Path $r $p.Name)) -ne $expected){throw ('Title asset drift: '+$p.Name)}
}
if($Rollback){
 if(Get-Process MagnaCarta -ErrorAction SilentlyContinue){throw 'Close game before title rollback'}
 foreach($p in $m.tiles.PSObject.Properties){if((Hash (Join-Path $PSScriptRoot ('title-original/'+$p.Name))) -ne $p.Value.before){throw 'Backup drift'}}
 foreach($p in $m.tiles.PSObject.Properties){Copy-Item -LiteralPath (Join-Path $PSScriptRoot ('title-original/'+$p.Name)) -Destination (Join-Path $r $p.Name) -Force}
 $m.active=$false
 $m | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'title-background.json') -Encoding UTF8
 Write-Output 'TITLE_BACKGROUND_ROLLBACK PASS assets=exact hd_flag=off game_started=false'
 exit 0
}
$old=$env:MC_TITLE_BACKGROUND4K
try {
 $env:MC_TITLE_BACKGROUND4K=if($m.active){'1'}else{'0'}
 & (Join-Path $PSScriptRoot 'StartAdvanced.ps1') -Mode $Mode -PrepareOnly:$PrepareOnly
} finally {$env:MC_TITLE_BACKGROUND4K=$old}
'''


def checked_artwork(source, locale):
    plan = json.loads((locale/'title-background-plan.json').read_text('utf8'))
    for name, expected in plan['source_tiles'].items():
        if sha(source/name) != expected:
            raise ValueError('Original title tile drift: '+name)
    return plan, master(locale, plan)


def write_assets(source, output, plan, image):
    runtime = output/'.advanced-runtime'
    runtime.mkdir(parents=True,exist_ok=True)
    image.save(runtime/'title-background-4k.png')
    for width, height in [(1920,1080), (1280,720), (640,480), (800,600)]:
        centered_view(image,width,height).save(runtime/f'title-preview-{width}x{height}.png')
    records = {}
    for group in [357,363]:
        for row, y in enumerate(plan['rows']):
            for col, x in enumerate(plan['columns']):
                name = f'BGR/{group+row*3+col:04d}.BGR'
                dest = output/name
                original = (source/name).read_bytes()
                backup = runtime/'title-original'/name
                backup.parent.mkdir(parents=True,exist_ok=True)
                backup.write_bytes(original)
                dest.parent.mkdir(parents=True,exist_ok=True)
                if dest.exists():dest.chmod(0o666)
                dest.write_bytes(pack(original,image,x,y,plan['tile_size']))
                records[name] = {'before':sha(backup), 'after':sha(dest)}
    (runtime/'title-background.json').write_text(json.dumps({'schema':1,'active':True,'master_sha256':sha(runtime/'title-background-4k.png'),'tiles':records},indent=2)+'\n',encoding='utf8')
    return records


def build(source, native, locale, output):
    plan,image=checked_artwork(source,locale)
    prepare_advanced_trial.prepare(source,native,output)
    records=write_assets(source,output,plan,image)
    runtime=output/'.advanced-runtime'
    (runtime/'StartTitle.ps1').write_text(START,encoding='utf-8-sig')
    for mode in prepare_advanced_trial.render.PROFILES:
        (output/f'Play-{mode}.cmd').write_bytes(('@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0.advanced-runtime\\StartTitle.ps1" -Mode '+mode+'\r\nif errorlevel 1 pause\r\n').encode('ascii'))
    (output/'Rollback-title.cmd').write_bytes(b'@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0.advanced-runtime\\StartTitle.ps1" -Rollback\r\nif errorlevel 1 pause\r\n')
    return records


def export_assets(source, locale, output):
    output=prepare_advanced_trial.render.plain_path(output,strict=False)
    build_root=Path(__file__).resolve().parents[1]/'build'
    if output.exists() or output==build_root or not output.is_relative_to(build_root):
        raise ValueError('New isolated repository build asset directory required')
    source=prepare_advanced_trial.render.checked_source(source)
    plan,image=checked_artwork(source,locale)
    return write_assets(source,output,plan,image)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assets-only',action='store_true')
    parser.add_argument('--native',type=Path)
    for name in ['source','locale','output']:
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    if args.assets_only:
        export_assets(args.source.resolve(),args.locale.resolve(),args.output.resolve())
    else:
        if args.native is None:parser.error('--native is required for a playable candidate')
        build(args.source.resolve(),args.native.resolve(),args.locale.resolve(),args.output.resolve())
    print('TITLE_BACKGROUND_BUILD PASS master=3840x2160 tiles=12 tile_size=2048 source_unchanged=true game_started=false')
