"""Build an incremental candidate against the active source-locked locale mapping.

Only reviewed punctuation changes are accepted. Existing glyph pairs are read
from the generated SystemGlyph table rather than regenerated from a new corpus.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

from build_system_messages import wide, TOKENS as SYSTEM_TOKENS
from extract_text_catalog import LAYOUTS
from native_text_codec import encode, decode, validate
from normalize_prompt_punctuation import normalize
from resource_font import native_slot


def sha(data):
    return hashlib.sha256(data).hexdigest()


def mapping_from_header(header):
    block = header.split('const SystemGlyph localeSystemGlyphs[] = {', 1)[1].split('};', 1)[0]
    mapping = {}
    for pair, literal in re.findall(r'\{0x([0-9a-fA-F]{4}),L("(?:\\.|[^"\\])*")\}', block):
        char = json.loads(literal)
        if char in mapping:
            raise ValueError('duplicate generated glyph')
        raw = bytes.fromhex(pair)
        mapping[char] = dict(encoded_hex=pair.lower(), index=native_slot(raw)[1])
    if not mapping:
        raise ValueError('missing generated mapping')
    validate(mapping)
    return mapping


def checked_replace(raw, offset, before, after, capacity):
    if len(after) > len(before) or len(before) + 1 > capacity:
        raise ValueError('incremental update must not expand a field')
    if raw[offset:offset+len(before)+1] != before+b'\0':
        raise ValueError('active field differs from reviewed baseline')
    result = bytearray(raw)
    result[offset:offset+len(before)+1] = after+bytes(len(before)+1-len(after))
    if result[offset:offset+len(after)+1] != after+b'\0':
        raise ValueError('updated field readback mismatch')
    return bytes(result)


def build(data_root, locale, changes_path, header_path, output, font_path=None, font_lock=None):
    import pefile
    data_root = Path(data_root).resolve(strict=True)
    locale = Path(locale).resolve(strict=True)
    output = Path(output).resolve()
    header_path = Path(header_path).resolve(strict=True)
    if output.exists() or output.is_relative_to(data_root) or data_root.is_relative_to(output):
        raise ValueError('candidate output must be new and separate')
    changes = json.loads(Path(changes_path).read_text('utf8'))['changes']
    punctuation_policy=json.loads((locale/'prompt-punctuation-policy.json').read_text('utf8'))
    header = header_path.read_text('ascii')
    original_header = header
    mapping = mapping_from_header(header)
    originals = {}
    results = {}
    manifest = []
    def read(resource):
        if resource not in originals:
            originals[resource] = (data_root/resource).read_bytes()
            results[resource] = originals[resource]
        return results[resource]
    domains = json.loads((locale/'text-domain-plans.json').read_text('utf8'))
    for change in changes:
        before, after = change['before'], change['after']
        if after != normalize(before,punctuation_policy) or len(after) >= len(before):
            raise ValueError('change is not terminal removal')
        name, pointer = change['file'], change['pointer'].split('/')
        if name == 'text/fixed-tables.json':
            resource, field, ordinal, identifier = change['id'].split(':')
            raw = read(resource)
            layout, fields = LAYOUTS[Path(resource).suffix.lower()]
            row = next(r for r in fields if r[0] == field)
            offset = 8+int(ordinal)*layout
            if struct.unpack_from('<I', raw, offset)[0] != int(identifier):
                raise ValueError('fixed record identifier drift')
            results[resource] = checked_replace(raw, offset+row[1], encode(before,mapping), encode(after,mapping),row[2])
        elif name == 'text-domain-plans.json' and pointer[1] == 'native_fields':
            row = domains['native_fields'][int(pointer[2])]
            resource = 'MCAlpha.dll'
            results[resource] = checked_replace(read(resource),row['offset'], encode(before,mapping),encode(after,mapping),len(bytes.fromhex(row['expected_hex']))+1)
        elif name == 'text-domain-plans.json' and pointer[1] == 'dialogs':
            # Group/rebuild all selected controls after other native updates.
            continue
        elif name == 'system-message-plans.json':
            old, new = wide(before), wide(after)
            if old not in original_header:
                raise ValueError('generated system target drift')
            header = header.replace(old, new)
            values=['0007' if t=='%04d' else 'sample' if t=='%s' else str(11+i)
                    for i,t in enumerate(SYSTEM_TOKENS.findall(before))]
            def example(text):
                it=iter(values)
                return SYSTEM_TOKENS.sub(lambda _:next(it),text)
            header=header.replace(wide(example(before)),wide(example(after)))
        elif name == 'image-text-plans.json':
            if font_path is None or font_lock is None:
                raise ValueError('image update requires the locked outline font')
            from build_image_text import render
            from resource_image import parse
            lock = json.loads(Path(font_lock).read_text('utf8'))
            if sha(Path(font_path).read_bytes()) != lock['sha256']:
                raise ValueError('outline font hash drift')
            image_plans=json.loads((locale/name).read_text('utf8'))
            image_entry=image_plans['resources'][int(pointer[2])]
            plan=image_entry['plans'][int(pointer[4])]
            resource=image_entry['resource']
            raw=read(resource)
            # The active image already contains reviewed localized lettering.
            # Original-source cleanup footprints would erase the nearby 注意
            # label, so only repaint the current target's own layout rectangle.
            incremental=dict(plan,erase_rects_xyxy=[plan['mask_xyxy']])
            prior=dict(incremental,target=before)
            roundtrip,_,_=render(parse(raw),[prior],font_path)
            if roundtrip != raw:
                raise ValueError('active image does not match baseline font/render plan')
            rebuilt,record,preview=render(parse(raw),[incremental],font_path)
            results[resource]=rebuilt
        else:
            raise ValueError('unsupported changed context: '+name)
    dialog_changes=[c for c in changes if c['file']=='text-domain-plans.json' and c['pointer'].startswith('/dialogs/')]
    if dialog_changes:
        from resource_dialog import parse, replace_text
        raw=read('MCAlpha.dll'); pe=pefile.PE(data=raw)
        result=bytearray(raw)
        try:
            for index, dialog in enumerate(domains['dialogs']):
                group=[c for c in dialog_changes if int(c['pointer'].split('/')[2])==index]
                if not group:
                    continue
                leaves=[lang.data.struct for typ in pe.DIRECTORY_ENTRY_RESOURCE.entries if typ.id==5
                        for name in typ.directory.entries if name.id==dialog['resource_id']
                        for lang in name.directory.entries if lang.id==dialog['language']]
                if len(leaves)!=1:
                    raise ValueError('dialog resource missing/ambiguous')
                entry=leaves[0];start=pe.get_offset_from_rva(entry.OffsetToData);size=entry.Size
                original=raw[start:start+size];table=parse(original); controls=[]
                for change in group:
                    control=dialog['controls'][int(change['pointer'].split('/')[4])]
                    controls.append(dict(ordinal=control['ordinal'],identifier=control['identifier'],expected=change['before'],target=change['after']))
                modified=replace_text(original,table['title'],controls)
                if len(modified)>size:
                    raise ValueError('dialog slot expansion')
                result[start:start+size]=modified+bytes(size-len(modified))
                struct.pack_into('<I',result,entry.get_field_absolute_offset('Size'),len(modified))
                if parse(bytes(result[start:start+len(modified)]))['controls'] == table['controls']:
                    raise ValueError('dialog update did not take effect')
            results['MCAlpha.dll']=bytes(result)
        finally:
            pe.close()
    original_module=originals['MCAlpha.dll']
    locked=re.search(r'localeSystemSourceSha\[\] = "([0-9a-f]{64})"',header).group(1)
    if locked != sha(original_module):
        raise ValueError('active module does not match source-locked header')
    header=header.replace(locked,sha(results['MCAlpha.dll']))
    if mapping_from_header(header)!=mapping:
        raise ValueError('generated glyph mapping changed')
    if any((data_root/name).read_bytes()!=raw for name,raw in originals.items()):
        raise ValueError('source changed during candidate build')
    output.mkdir(parents=True)
    for resource, raw in results.items():
        path=output/resource;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
        if path.read_bytes()!=raw:
            raise ValueError('candidate readback mismatch')
        manifest.append(dict(resource=resource,before_sha256=sha(originals[resource]),after_sha256=sha(raw)))
    (output/'system_message_rules.h').write_bytes(header.encode('ascii'))
    if font_path is not None:
        from PIL import Image
        from resource_image import parse
        for resource in results:
            if resource.lower().endswith('.bgr'):
                for label,raw in [('before',originals[resource]),('after',results[resource])]:
                    image=parse(raw)
                    Image.frombytes('RGBA',(image.width,image.height),image.rgba()).save(output/(Path(resource).stem+'-'+label+'.png'))
    report=dict(schema=1,files=manifest,changed_fields=len(changes),mapping_glyphs=len(mapping),
                mapping_unchanged=True,original_header_sha256=sha(original_header.encode('ascii')),
                header_sha256=sha(header.encode('ascii')),source_unchanged=True,game_started=False)
    (output/'build.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('data-root','locale','changes','header','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--font',type=Path);p.add_argument('--font-lock',type=Path)
    a=p.parse_args()
    result=build(a.data_root,a.locale,a.changes,a.header,a.output,a.font,a.font_lock)
    print(f'PROMPT_UPDATE PASS resources={len(result["files"])} fields={result["changed_fields"]} mapping_unchanged=true source_unchanged=true')
