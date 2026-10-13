"""Render source-locked image phrases across explicit tile coordinates."""
import argparse
import json
from pathlib import Path, PurePosixPath
import struct

from build_image_text import digest, render, rectangle
from resource_image import parse, TGA_FOOTER


def compose(rows, source, dimensions):
    from PIL import Image
    if (not isinstance(dimensions,list) or len(dimensions)!=2
            or any(type(v) is not int or not 1<=v<=4096 for v in dimensions)):
        raise ValueError('invalid group canvas dimensions')
    width,height=dimensions
    if not isinstance(rows,list) or not rows:raise ValueError('empty group tile list')
    canvas=Image.new('RGBA',(width,height));covered=set();originals={};tiles=[]
    for row in rows:
        if not isinstance(row,dict):raise ValueError('invalid tile row')
        name=row.get('resource')
        if not isinstance(name,str) or ':' in name or '\\' in name:raise ValueError('invalid tile path')
        rel=PurePosixPath(name)
        if rel.is_absolute() or '..' in rel.parts or rel.as_posix()!=name or name in originals:
            raise ValueError('noncanonical or duplicate tile path')
        path=source/rel
        if path.is_symlink() or not path.resolve(strict=True).is_relative_to(source):raise ValueError('linked tile')
        raw=path.read_bytes()
        if digest(raw)!=row.get('source_sha256'):raise ValueError('tile source digest mismatch')
        image=parse(raw);position=row.get('xy')
        if not isinstance(position,list) or len(position)!=2 or any(type(v) is not int for v in position):
            raise ValueError('invalid tile position')
        x,y=position;box=rectangle([x,y,x+image.width,y+image.height],width,height)
        pixels={(a,b) for b in range(y,box[3]) for a in range(x,box[2])}
        if covered & pixels:raise ValueError('overlapping group tiles')
        covered.update(pixels)
        canvas.paste(Image.frombytes('RGBA',(image.width,image.height),image.rgba()),(x,y))
        originals[name]=raw;tiles.append((name,image,box))
    if len(covered)!=width*height:raise ValueError('group tiles do not cover canvas')
    header=bytearray(18);header[2]=2;struct.pack_into('<HH',header,12,width,height);header[16:18]=b'\x20\x08'
    # A synthetic TGA is only a rendering surface. Original resource headers
    # never use it; each crop is written through that tile's original parser.
    synthetic=parse(b'W'*12+bytes(header)+bytes(width*height*4)+TGA_FOOTER).replace_rgba(canvas.tobytes())
    return synthetic,originals,tiles


def build(source,plans_path,font,font_sha,output):
    from PIL import Image
    source=Path(source).resolve(strict=True);output=Path(output).resolve()
    plans_path=Path(plans_path).resolve(strict=True);font=Path(font).resolve(strict=True)
    if (output.exists() or output.is_relative_to(source) or source.is_relative_to(output)
            or any(p.is_relative_to(output) for p in (plans_path,font))):
        raise ValueError('group output must be new and separate')
    snapshots={plans_path:plans_path.read_bytes(),font:font.read_bytes()}
    if digest(snapshots[font])!=font_sha:raise ValueError('group outline digest mismatch')
    data=json.loads(snapshots[plans_path]);groups=data.get('groups')
    if data.get('schema')!=1 or not isinstance(groups,list) or not groups:raise ValueError('invalid group schema')
    originals={};results={};previews={};reports=[];seen=set()
    for group in groups:
        label=group.get('id')
        if (not isinstance(label,str) or not label or Path(label).name!=label or ':' in label
                or '\\' in label or label in seen):raise ValueError('invalid or duplicate group ID')
        seen.add(label)
        if not group.get('layout_evidence'):raise ValueError('missing group layout evidence')
        image,before,tiles=compose(group.get('tiles'),source,group.get('dimensions'))
        if set(before)&set(results):raise ValueError('tile belongs to multiple groups')
        plans=group.get('plans')
        if not isinstance(plans,list) or not plans or any(not isinstance(p,dict) for p in plans):
            raise ValueError('invalid group text plan list')
        _,texts,preview=render(image,plans,font)
        records=[]
        for name,tile,box in tiles:
            cropped=preview.crop(box).tobytes();changed=tile.replace_rgba(cropped).to_bytes()
            if parse(changed).rgba()!=cropped:raise ValueError('tile crop readback mismatch')
            if len(changed)!=len(before[name]):raise ValueError('tile allocation changed')
            results[name]=changed;originals[source/name]=before[name]
            records.append(dict(resource=name,original_sha256=digest(before[name]),modified_sha256=digest(changed),
                                xyxy=list(box),metadata_preserved=True))
        previews[label]=preview
        reports.append(dict(id=label,texts=texts,tiles=records,outside_masks_preserved=True,
                            runtime_placement_verified=False,layout_evidence=group['layout_evidence']))
    if any(p.read_bytes()!=b for p,b in {**snapshots,**originals}.items()):raise ValueError('group input drift')
    output.mkdir(parents=True)
    for name,raw in results.items():
        path=output/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    (output/'previews').mkdir()
    for label,preview in previews.items():preview.save(output/'previews'/f'{label}.png')
    report=dict(schema=1,kind='source_locked_image_phrase_groups',groups=reports,
                plans_sha256=digest(snapshots[plans_path]),font_sha256=font_sha,source_unchanged=True,
                all_game_text_complete=False,deployed=False,game_started=False)
    (output/'build.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for arg in ('source','plans','font','output'):p.add_argument('--'+arg,type=Path,required=True)
    p.add_argument('--font-sha256',required=True);a=p.parse_args()
    r=build(a.source,a.plans,a.font,a.font_sha256,a.output)
    print(f'IMAGE_GROUP_BUILD PASS groups={len(r["groups"])} tiles={sum(len(g["tiles"]) for g in r["groups"])} '
          'metadata_preserved=true outside_masks_preserved=true deployed=false game_started=false')
