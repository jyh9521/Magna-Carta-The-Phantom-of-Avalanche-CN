"""Build byte coverage for a fixed native mapping; keep 1-bit files and metrics intact."""
import argparse
import json
from pathlib import Path
from locale_package import sha, located
from native_text_codec import encode, validate


def validate_module(raw,contract):
    import pefile
    pe=pefile.PE(data=raw)
    if (contract.get('schema')!=1 or pe.FILE_HEADER.Machine!=contract['machine']
            or pe.OPTIONAL_HEADER.Magic!=contract['optional_magic']
            or pe.OPTIONAL_HEADER.SizeOfImage!=contract['image_size']):
        raise ValueError('unsupported coverage engine layout')
    sections=[s for s in pe.sections if s.Name.rstrip(b'\0')==b'.text']
    if len(sections)!=1 or sha(sections[0].get_data())!=contract['text_sha256']:
        raise ValueError('unknown executable code in coverage engine')
    entries={}
    for entry in contract['entries']:
        offset=pe.get_offset_from_rva(entry['rva']);expected=bytes.fromhex(entry['expected_hex'])
        if len(expected)!=32 or raw[offset:offset+32]!=expected:
            raise ValueError('coverage entry contract mismatch')
        entries[entry['name']]=expected
    if set(entries)!={'GLYPH','MEASURE','TEXT'}:raise ValueError('incomplete coverage entry contract')
    return entries


def raster_layout(font,height,characters,cache=None,variations=()):
    """One face size and typographic baseline for the complete native font set."""
    from PIL import ImageFont
    cache={} if cache is None else cache
    for size in range(height,1,-1):
        key=(size,tuple(variations))
        if key not in cache:
            cache[key]=ImageFont.truetype(str(font),size)
            if variations:cache[key].set_variation_by_axes(list(variations))
        face=cache[key];boxes=[face.getbbox(c,anchor='ls') for c in characters]
        top=min(b[1] for b in boxes);bottom=max(b[3] for b in boxes)
        if max(b[2]-b[0] for b in boxes)<=height and bottom-top<=height-1:break
    else:raise ValueError('coverage exceeds fixed native cell')
    baseline=(height-1-(bottom-top))//2-top
    return dict(size=size,baseline=baseline,anchor='ls',source_top=top,source_bottom=bottom)


def coverage(char, font, height, weight=500, cache=None, variations=(),layout=None):
    from PIL import Image,ImageDraw,ImageFont
    cache={} if cache is None else cache
    if layout is None:layout=raster_layout(font,height,[char],cache,variations)
    key=(layout['size'],tuple(variations))
    if key not in cache:
        cache[key]=ImageFont.truetype(str(font),layout['size'])
        if variations:cache[key].set_variation_by_axes(list(variations))
    face=cache[key];box=face.getbbox(char,anchor='ls');w=box[2]-box[0]
    if w>height or layout['baseline']+box[1]<0 or layout['baseline']+box[3]>height-1:
        raise ValueError('glyph exceeds uniform native baseline')
    result=Image.new('L',(height,height))
    ImageDraw.Draw(result).text(((height-w)//2-box[0],layout['baseline']),char,font=face,fill=255,anchor='ls')
    if not result.getbbox():raise ValueError('empty coverage glyph')
    return result.tobytes()


def build(font,expected_sha,font_package,labels,module,module_sha,output):
    font=Path(font).resolve(strict=True);font_package=Path(font_package).resolve(strict=True)
    labels=Path(labels).resolve(strict=True);output=Path(output).resolve()
    if output.exists():raise ValueError('coverage output already exists')
    module=Path(module).resolve(strict=True)
    snapshots={font:font.read_bytes(),font_package/'overlay.json':(font_package/'overlay.json').read_bytes(),labels:labels.read_bytes(),module:module.read_bytes()}
    if sha(snapshots[font])!=expected_sha:raise ValueError('coverage outline source hash mismatch')
    if sha(snapshots[module])!=module_sha:raise ValueError('coverage module identity mismatch')
    contract_path=Path(__file__).resolve().parents[1]/'assets/runtime/native-font-contract.json'
    snapshots[contract_path]=contract_path.read_bytes();contract=json.loads(snapshots[contract_path])
    entries=validate_module(snapshots[module],contract)
    overlay=json.loads(snapshots[font_package/'overlay.json']);mapping=overlay['mapping'];validate(mapping)
    if overlay.get('source_font_sha256')!=expected_sha:raise ValueError('coverage differs from mapped font source')
    from fontTools.ttLib import TTFont
    with TTFont(font) as outline:
        cmap=outline.getBestCmap()
        if any(ord(c) not in cmap for c in mapping):raise ValueError('coverage outline lacks mapped glyph')
        axes=outline['fvar'].axes if 'fvar' in outline else []
        variations=tuple(500 if a.axisTag=='wght' else a.defaultValue for a in axes)
    from resource_font import parse
    for i,height in enumerate([14,22]):
        p=font_package/f'Chi{i}.dat';snapshots[p]=p.read_bytes()
        if sha(snapshots[p])!=overlay['native_modified_sha256'][i] or parse(snapshots[p]).height!=height:
            raise ValueError('coverage native font identity mismatch')
    pairs=[];planes=[];rows=[]
    for char,item in sorted(mapping.items(),key=lambda p:int(p[1]['encoded_hex'],16)):
        pairs.append(int(item['encoded_hex'],16));rows.append(char)
    cache={};layouts=[]
    for height in [14,22]:
        layout=raster_layout(font,height,rows,cache,variations);layouts.append(layout)
        planes.append(b''.join(coverage(char,font,height,cache=cache,variations=variations,layout=layout) for char in rows))
    lines=['// Reproducible fixed-mapping grayscale coverage; no runtime font dependency.']
    for key,raw in entries.items():lines.append('#define EXPECTED_'+key+'_BYTES '+','.join(hex(v) for v in raw))
    lines += [
           'const unsigned short coveragePairs[] = {'+','.join(hex(p) for p in pairs)+'};']
    for i,raw in enumerate(planes):
        lines+=['const unsigned char coveragePlane'+str(i)+'[] = {']
        lines += [','.join(str(v) for v in raw[n:n+128])+',' for n in range(0,len(raw),128)]
        lines+=['};']
    lines+=['const NativeLabel nativeLabels[] = {']
    unique={r['source']:r['target'] for r in json.loads(snapshots[labels])['resources']}
    literal=lambda b:'"'+''.join('\\x'+f'{v:02x}' for v in b)+'"'
    for s,t in sorted(unique.items()):lines.append('{'+literal(s.encode('cp949'))+','+literal(encode(t,mapping))+'},')
    lines+=['};']
    if any(p.read_bytes()!=b for p,b in snapshots.items()):raise ValueError('coverage input drift')
    output.mkdir(parents=True)
    header=('\n'.join(lines)+'\n').encode('ascii');(output/'native_font_data.h').write_bytes(header)
    for i,b in enumerate(planes):(output/f'coverage{i}.bin').write_bytes(b)
    report=dict(schema=1,mapping_sha256=sha(snapshots[font_package/'overlay.json']),source_font_sha256=expected_sha,
                glyphs=len(pairs),pairs=pairs,heights=[14,22],labels=len(unique),weight=500,
                coverage_sha256=list(map(sha,planes)),header_sha256=sha(header),raster_layouts=layouts,
                metrics_unchanged=True,mapping_unchanged=True,module_sha256=module_sha,
                engine_contract_sha256=sha(snapshots[contract_path]),derived_font_name='Locale Glyph Coverage',
                source_font_notices=overlay['source_font_notices'],game_started=False)
    (output/'build.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ('font','font-package','labels','module','output'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--font-sha256',required=True);p.add_argument('--module-sha256',required=True);a=p.parse_args()
    r=build(a.font,a.font_sha256,a.font_package,a.labels,a.module,a.module_sha256,a.output)
    print(f'FONT_COVERAGE_BUILD PASS glyphs={r["glyphs"]} labels={r["labels"]} metrics_unchanged=true game_started=false')
