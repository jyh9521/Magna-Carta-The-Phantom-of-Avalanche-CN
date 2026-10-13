"""Version-locked native-font strings and Unicode dialog resource candidates."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

from native_text_codec import encode,decode,validate as validate_mapping
from resource_dialog import replace_text,parse as parse_dialog

FORMATS=re.compile(r'\$[dDcC][0-9]{2}|\$[A-Za-z]|%[-+ #0-9.*]*[sdifuxX]')


def sha(raw):return hashlib.sha256(raw).hexdigest()


def patch(original, plans, mapping):
    import pefile
    if (sha(original)!=plans.get('source_sha256') or len(original)!=plans.get('source_size')):
        raise ValueError('unsupported text module version')
    validate_mapping(mapping)
    pe=pefile.PE(data=original);result=bytearray(original);used=set();report=[]
    try:
        fields=plans.get('native_fields',[])
        if not isinstance(fields,list):raise ValueError('invalid native text field list')
        for row in fields:
            offset=row.get('offset');expected=bytes.fromhex(row['expected_hex']);target=row['target']
            if type(offset) is not int or offset<0 or offset+len(expected)+1>len(original):
                raise ValueError('native field outside module')
            span=len(expected)+1;indices=set(range(offset,offset+span))
            if used&indices or not expected or original[offset:offset+span]!=expected+b'\0':
                raise ValueError('overlapping native field or expected bytes mismatch')
            used.update(indices)
            source=expected.decode('cp949')
            if (not row.get('evidence') or not isinstance(target,str) or not target
                    or FORMATS.findall(source)!=FORMATS.findall(target)):
                raise ValueError('native field evidence or protected formats changed')
            # Only the independently verified game-font display domain accepts
            # private glyph bytes. MessageBoxA/GDI fields are not eligible here.
            if row.get('display_domain')!='game_native_font':raise ValueError('non-native display domain')
            section=pe.get_section_by_rva(pe.get_rva_from_offset(offset))
            if section is None or section.Name.rstrip(b'\0')!=b'.data':
                raise ValueError('native display string is not in the verified data section')
            encoded=encode(target,mapping)
            if len(encoded)+1>span:raise ValueError('native target exceeds original slot')
            if decode(encoded,mapping)!=target:raise ValueError('native text encoding readback mismatch')
            result[offset:offset+span]=encoded+bytes(span-len(encoded))
            report.append(dict(offset=offset,span=span,target=target,domain='game_native_font'))
        for dialog in plans.get('dialogs',[]):
            leaves=[]
            for typ in pe.DIRECTORY_ENTRY_RESOURCE.entries:
                if typ.id!=5:continue
                for name in typ.directory.entries:
                    if name.id!=dialog['resource_id']:continue
                    for lang in name.directory.entries:
                        if lang.id==dialog['language']:leaves.append(lang.data.struct)
            if len(leaves)!=1:raise ValueError('dialog resource identity is missing or ambiguous')
            entry=leaves[0];start=pe.get_offset_from_rva(entry.OffsetToData);size=entry.Size
            section=pe.get_section_by_rva(entry.OffsetToData)
            if (section is None or section.Name.rstrip(b'\0')!=b'.rsrc'
                    or start+size>section.PointerToRawData+section.SizeOfRawData):
                raise ValueError('dialog is not inside the original resource section')
            data=original[start:start+size]
            if sha(data)!=dialog['source_sha256'] or not dialog.get('evidence'):
                raise ValueError('dialog source digest or evidence mismatch')
            if parse_dialog(data)['title']!=dialog['expected_title']:
                raise ValueError('dialog expected title mismatch')
            changed=replace_text(data,dialog['target_title'],dialog['controls'])
            if len(changed)>size:raise ValueError('dialog exceeds original resource allocation')
            entry_size_offset=entry.get_field_absolute_offset('Size')
            indices=set(range(start,start+size))|set(range(entry_size_offset,entry_size_offset+4))
            if used&indices:raise ValueError('dialog overlaps another declared patch')
            used.update(indices);result[start:start+size]=changed+bytes(size-len(changed))
            struct.pack_into('<I',result,entry_size_offset,len(changed))
            report.append(dict(resource_id=dialog['resource_id'],language=dialog['language'],offset=start,
                               original_size=size,modified_size=len(changed),controls=len(dialog['controls']),domain='utf16_dialog'))
        if not report:raise ValueError('text domain plan is empty')
        modified=bytes(result)
        for section in pe.sections:
            if section.Characteristics & 0x20000000:
                start=section.PointerToRawData;end=start+section.SizeOfRawData
                if original[start:end]!=modified[start:end]:
                    raise ValueError('executable section changed')
        if any(a!=b and i not in used for i,(a,b) in enumerate(zip(original,modified))):
            raise ValueError('module changes bytes outside declared text fields')
        checked=pefile.PE(data=modified)
        if (checked.FILE_HEADER.Machine,checked.OPTIONAL_HEADER.SizeOfImage)!=(pe.FILE_HEADER.Machine,pe.OPTIONAL_HEADER.SizeOfImage):
            raise ValueError('module architecture or image size changed')
        checked.close()
        return modified,report
    finally:pe.close()


def build(source,plans_path,font_package,output):
    source,output=Path(source).resolve(strict=True),Path(output).resolve()
    paths=[source,Path(plans_path).resolve(strict=True),Path(font_package).resolve(strict=True)/'overlay.json']
    if output.exists() or output.is_relative_to(source) or any(p.is_relative_to(output) for p in paths):
        raise ValueError('text module output must be new and separate')
    snapshots={p:p.read_bytes() for p in paths};plans=json.loads(snapshots[paths[1]])
    if plans.get('schema')!=1:raise ValueError('unsupported text domain schema')
    font=json.loads(snapshots[paths[2]]);modified,records=patch(snapshots[source],plans,font['mapping'])
    if any(p.read_bytes()!=b for p,b in snapshots.items()):raise ValueError('text module input drift')
    output.mkdir(parents=True);(output/source.name).write_bytes(modified)
    report=dict(schema=1,original_sha256=sha(snapshots[source]),modified_sha256=sha(modified),
                original_size=len(modified),plan_sha256=sha(snapshots[paths[1]]),font_overlay_sha256=sha(snapshots[paths[2]]),
                fields=records,source_unchanged=True,code_bytes_unchanged=True,
                all_game_text_complete=False,deployed=False,commercial_code_executed=False,game_started=False)
    (output/'build.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--plans',type=Path,required=True)
    p.add_argument('--font-package',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=build(a.source,a.plans,a.font_package,a.output)
    print(f'TEXT_DOMAINS_BUILD PASS native_fields={sum(x["domain"]=="game_native_font" for x in r["fields"])} '
          f'dialogs={sum(x["domain"]=="utf16_dialog" for x in r["fields"])} code_bytes_unchanged=true deployed=false game_started=false')
