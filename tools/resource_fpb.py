"""Validated FPB record parsing and byte-preserving rebuilding."""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def parse(data):
    if data == b'\0\0\0\0':
        return []
    if len(data) < 8:
        raise ValueError('truncated header')
    count = struct.unpack_from('<I', data)[0]
    base = 8 + 12 * count
    if base > len(data):
        raise ValueError('table exceeds file')
    total = struct.unpack_from('<I', data, 4 + 12 * count)[0]
    if base + total != len(data):
        raise ValueError('payload size mismatch')
    records = []
    expected = 0
    for i in range(count):
        tag, offset, length = struct.unpack_from('<III', data, 4 + 12 * i)
        if offset != expected or length < 1 or offset + length > total:
            raise ValueError('invalid string range')
        raw = data[base + offset:base + offset + length]
        if raw[-1] != 0:
            raise ValueError('missing terminator')
        records.append((tag, raw[:-1]))
        expected = offset + length
    if expected != total:
        raise ValueError('payload not covered')
    return records


def rebuild(records):
    if not records:
        return b'\0\0\0\0'
    header = bytearray(struct.pack('<I', len(records)))
    body = bytearray()
    for tag, raw in records:
        if not isinstance(raw, bytes) or b'\0' in raw:
            raise ValueError('Invalid string bytes')
        header.extend(struct.pack('<III', tag, len(body), len(raw) + 1))
        body.extend(raw + b'\0')
    header.extend(struct.pack('<I', len(body)))
    return bytes(header + body)


def audit(source, encoding):
    catalog = []
    entries = 0
    empty = 0
    for path in sorted(source.glob('*')):
        if not path.is_file():
            continue
        data = path.read_bytes()
        records = parse(data)
        if rebuild(records) != data:
            raise ValueError('Round-trip mismatch: ' + path.name)
        catalog.append({'resource': path.name, 'sha256': hashlib.sha256(data).hexdigest(),
            'records': [{'id': f'{path.name}:{i}:{tag}', 'ordinal': i, 'tag': tag,
                'source': raw.decode(encoding), 'source_hex': raw.hex(), 'target': None}
                for i, (tag, raw) in enumerate(records)]})
        entries += len(records)
        empty += not records
    return {'files': len(catalog), 'records': entries, 'empty_files': empty,
        'byte_identical': len(catalog), 'encoding': encoding}, catalog


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--encoding', default='cp949')
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--catalog', type=Path)
    a = p.parse_args()
    source = a.source.resolve(strict=True)
    for output in [a.report, a.catalog]:
        if output and output.resolve().is_relative_to(source):
            raise ValueError('Output must be outside source tree')
    report, catalog = audit(source, a.encoding)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(report, indent=2), encoding='utf-8')
    if a.catalog:
        a.catalog.parent.mkdir(parents=True, exist_ok=True)
        a.catalog.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'FPB_ROUNDTRIP PASS files={report["files"]} records={report["records"]} empty={report["empty_files"]} byte_identical={report["byte_identical"]}')
