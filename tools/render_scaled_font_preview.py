"""Compose labeled comparisons from owned native fixture outputs, never from a game screenshot."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def render(cache, fixture, font, output):
    from PIL import Image, ImageDraw, ImageFont
    cache=Path(cache).resolve(strict=True);fixture=Path(fixture).resolve(strict=True);font=Path(font).resolve(strict=True);output=Path(output).resolve()
    if output.exists():raise ValueError('New preview folder required')
    manifest=json.loads((cache/'manifest.json').read_bytes())
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    if manifest.get('schema')!=1 or sha(font)!=manifest['source_font_sha256']:raise ValueError('Preview input identity mismatch')
    for name,digest in manifest['files'].items():
        p=cache/name
        if p.resolve().parent!=cache or sha(p)!=digest:raise ValueError('Cache file drift')
    output.mkdir(parents=True)
    runs=[];images={}
    for height in (14,22):
        images[height]=[]
        for row in range(len(manifest['sample_lines'])):
            pair=[]
            for mode in ('baseline','modified'):
                name=f'{mode}-{height}-{row}.bmp'
                cmd=[str(fixture),mode,str(cache/f'baseline-{height}.sgc'),str(cache/f'candidate-{height}.sgc'),str(cache/f'line-{row}.seq'),str(output/name)]
                p=subprocess.run(cmd,capture_output=True,text=True,timeout=30)
                if p.returncode:raise ValueError('Native fixture failed: '+p.stdout+p.stderr)
                runs.append(dict(command=cmd,exit=p.returncode,output=p.stdout))
                with Image.open(output/name) as im:pair.append(im.convert('RGB'))
            low,high=pair
            if high.size!=tuple(v*manifest['scale'] for v in low.size):raise ValueError('Physical/logical size mismatch')
            images[height].append(pair)
    scale=manifest['scale'];label=ImageFont.truetype(str(font),22);small=ImageFont.truetype(str(font),18)
    if manifest.get('axis_values'):
        label.set_variation_by_axes(manifest['axis_values']);small.set_variation_by_axes(manifest['axis_values'])
    for height in (14,22):
        rows=images[height];width=max(p[1].width for p in rows)+64
        row_step=height*scale+16;panel_height=60+len(rows)*row_step
        canvas=Image.new('RGB',(width,100+3*panel_height),(12,18,22));draw=ImageDraw.Draw(canvas)
        draw.text((24,16),'OFFLINE FONT RASTER COMPARISON — NOT A GAME SCREENSHOT',font=label,fill='white')
        draw.text((24,51),f'Logical cell {height}px; physical cell {height*scale}px; same face/weight/advance. No runtime changes.',font=small,fill=(160,185,196))
        labels=['A  Native coverage enlarged: nearest (coarse pixels)', 'B  Same native coverage enlarged: bilinear (smoothing only)', f'C  Outline rerasterized at {scale}x (new glyph detail)']
        for panel,title in enumerate(labels):
            y=100+panel*panel_height
            draw.text((24,y+8),title,font=label,fill=(255,176,78) if panel==2 else (211,221,227))
            for row,(low,high) in enumerate(rows):
                image=high if panel==2 else low.resize(high.size,Image.Resampling.NEAREST if panel==0 else Image.Resampling.BILINEAR)
                canvas.paste(image,(32,y+50+row*row_step))
        canvas.save(output/f'comparison-{height}.png')
    report=dict(schema=1,fixture_sha256=sha(fixture),cache_manifest_sha256=sha(cache/'manifest.json'),runs=runs,
                previews={f'comparison-{h}.png':sha(output/f'comparison-{h}.png') for h in (14,22)},
                screenshot_modified=False,runtime_installed=False,game_started=False)
    (output/'preview.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for k in ('cache','fixture','font','output'):p.add_argument('--'+k,type=Path,required=True)
    a=p.parse_args();render(a.cache,a.fixture,a.font,a.output)
    print('SCALED_FONT_PREVIEW PASS native_fixture=executed baseline=active_exact candidate=outline_raster screenshot_modified=false runtime_installed=false')
