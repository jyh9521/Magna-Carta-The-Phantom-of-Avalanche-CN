"""Whole-tree text coverage inventory with validated records and quarantined candidates."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

from prepare_workspace import inventory
from resource_fpb import parse as parse_fpb, rebuild
from resource_sgi import catalog as sgi_catalog


LAYOUTS = {
    '.itm': (264, [('name', 4, 100), ('description', 164, 100)]),
    '.abi': (344, [('name', 4, 60)]),
    '.cha': (267, [('name', 4, 100)]),
}
SCAN_EXTENSIONS = {'.uis', '.jmu', '.wdi', '.mdi', '.msg', '.dll', '.exe', '.gsw', '.mon'}
MEDIA_EXTENSIONS = {'.bgr', '.bmp', '.dds', '.tga', '.jpg', '.png', '.wav', '.mp3', '.ogg', '.avi', '.mpg', '.mpeg', '.bik'}
TOKENS = re.compile(r'\$[A-Za-z]|%[-+ #0-9.*]*[sdifuxX]|\{[^{}]*\}|<[^<>]*>|[\x01-\x1f]')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def text_row(resource, ordinal, identifier, field, offset, raw, capacity=None):
    source = raw.decode('cp949')
    return dict(id=f'{resource}:{field}:{ordinal}:{identifier}', resource=resource,
                ordinal=ordinal, identifier=identifier, field=field, offset=offset,
                source_hex=raw.hex(), source=source, target=None,
                original_span=len(raw) + 1, candidate_capacity=capacity,
                protected_tokens=TOKENS.findall(source), state='extracted_not_translated')


def fixed_records(data, resource, extension):
    record_size, fields = LAYOUTS[extension]
    if len(data) < 8:
        raise ValueError('truncated record header')
    count = struct.unpack_from('<I', data)[0]
    if not 1 <= count <= 65536 or len(data) != 8 + count * record_size:
        raise ValueError('record size/count mismatch: ' + resource)
    rows = []
    for ordinal in range(count):
        start = 8 + ordinal * record_size
        identifier = struct.unpack_from('<I', data, start)[0]
        for field, relative, capacity in fields:
            block = data[start + relative:start + relative + capacity]
            if b'\0' not in block:
                raise ValueError('field missing terminator: ' + resource)
            row = text_row(resource, ordinal, identifier, field, start + relative,
                           block.split(b'\0', 1)[0], capacity)
            if extension == '.cha':
                row['field_semantics'] = 'display_name_or_internal_object_name'
                row['save_name_override'] = True
                row['translation_eligibility'] = 'requires_per_record_role_review'
            rows.append(row)
    return rows


def heuristic_strings(data):
    """Only clues: native-range null-terminated strings with at least two Hangul syllables."""
    pattern = rb'(?:[\x20-\x7e]|[\xa4-\xfe][\xa1-\xfe]){2,1024}\x00'
    rows = []
    for match in re.finditer(pattern, data):
        raw = match.group()[:-1]
        try:
            source = raw.decode('cp949')
        except UnicodeDecodeError:
            continue
        if sum('\uac00' <= ch <= '\ud7a3' for ch in source) < 2:
            continue
        rows.append(dict(offset=match.start(), source_hex=raw.hex(), source=source,
                         state='quarantined_not_safe_to_patch', evidence='heuristic_native_byte_pattern'))
    return rows


def extract(source, output):
    source = Path(source).resolve(strict=True)
    output = Path(output).resolve()
    if output.exists() or output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError('output must be a new separate directory')
    before = inventory(source)
    rows = []
    candidates = []
    coverage = []
    parsed = 0
    for item in before:
        relative = item['path']; path = source / relative; ext = path.suffix.lower()
        record = dict(**item)
        if ext == '.fpb':
            data = path.read_bytes(); table = parse_fpb(data)
            if rebuild(table) != data:
                raise ValueError('FPB roundtrip mismatch')
            base = 8 + 12 * len(table); offset = 0
            for ordinal, (tag, raw) in enumerate(table):
                row = text_row(relative, ordinal, tag, 'text', base + offset, raw)
                row['legacy_id'] = f'{path.name}:{ordinal}:{tag}'
                rows.append(row); offset += len(raw) + 1
            record.update(state='structured_text_extracted', records=len(table), roundtrip_exact=True)
            parsed += 1
        elif ext == '.sgi':
            data = path.read_bytes(); cat = sgi_catalog(data, relative)
            for row in cat['records']:
                raw = bytes.fromhex(row['source_hex'])
                rows.append(text_row(relative, row['ordinal'], row['identifier'], 'name', row['offset'], raw, 100))
            record.update(state='structured_text_extracted', records=len(cat['records']), roundtrip_exact=True)
            parsed += 1
        elif ext in LAYOUTS:
            data = path.read_bytes(); extracted = fixed_records(data, relative, ext)
            rows.extend(extracted)
            # Extraction never rebuilds interpreted numeric fields.
            record.update(state='structured_fields_extracted', fields=len(extracted), input_preserved=True)
            parsed += 1
        elif ext in SCAN_EXTENSIONS:
            found = heuristic_strings(path.read_bytes())
            candidates.extend(dict(resource=relative, sha256=item['sha256'], **row) for row in found)
            record.update(state='unparsed_binary_scanned_not_complete', candidate_strings=len(found))
        elif ext in MEDIA_EXTENSIONS:
            record.update(state='opaque_media_or_image_text_not_extracted')
        else:
            record.update(state='unparsed_resource_not_complete')
        coverage.append(record)
    ids = [row['id'] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError('duplicate structured text ID')
    if before != inventory(source):
        raise ValueError('input tree changed during extraction')
    report = dict(schema=1, input_files=len(before), parsed_files=parsed,
                  structured_fields=len(rows), nonempty_fields=sum(bool(row['source']) for row in rows),
                  quarantined_candidates=len(candidates), source_unchanged=True,
                  all_text_extracted=False, all_translated=False, game_started=False,
                  pending_coverage=[item for item in coverage if item['state'].startswith(('unparsed', 'opaque'))])
    output.mkdir(parents=True)
    for filename, value in [('catalog.json', rows), ('quarantine.json', candidates),
                            ('coverage.json', coverage), ('report.json', report)]:
        with (output / filename).open('x', encoding='utf8', newline='\n') as stream:
            json.dump(value, stream, ensure_ascii=True, indent=2); stream.write('\n')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True); args = p.parse_args()
    report = extract(args.source, args.output)
    print(f'TEXT_EXTRACT PASS files={report["input_files"]} fields={report["structured_fields"]} '
          f'quarantined={report["quarantined_candidates"]} all_text_extracted=false game_started=false')
