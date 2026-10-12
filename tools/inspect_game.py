"""Read-only PE, ISO and resource inventory; no game launch or patching."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import struct

import pefile
import pycdlib


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def inspect_pe(path):
    pe = pefile.PE(str(path))
    result = {'file': path.name, 'size': path.stat().st_size,
        'sha256': digest(path), 'machine': hex(pe.FILE_HEADER.Machine),
        'optional_magic': hex(pe.OPTIONAL_HEADER.Magic),
        'timestamp': pe.FILE_HEADER.TimeDateStamp, 'imports': {}, 'versions': {}}
    for entry in getattr(pe, 'DIRECTORY_ENTRY_IMPORT', []):
        result['imports'][entry.dll.decode('ascii', 'replace')] = [
            imp.name.decode('ascii', 'replace') if imp.name else f'ordinal:{imp.ordinal}'
            for imp in entry.imports]
    for group in getattr(pe, 'FileInfo', []):
        for info in group:
            for table in getattr(info, 'StringTable', []):
                result['versions'].update({k.decode('utf-8', 'replace'): v.decode('utf-8', 'replace')
                    for k, v in table.entries.items()})
    result['exports'] = [e.name.decode('ascii', 'replace') for e in
        getattr(getattr(pe, 'DIRECTORY_ENTRY_EXPORT', None), 'symbols', []) if e.name]
    pe.close()
    return result


def inspect_iso(path):
    result = {'file': path.name, 'size': path.stat().st_size, 'sha256': digest(path)}
    with path.open('rb') as stream:
        stream.seek(16 * 2048)
        pvd = stream.read(2048)
    if len(pvd) != 2048 or pvd[1:6] != b'CD001':
        result['error'] = 'ISO9660 primary descriptor not found at sector 16'
        return result
    result['volume_id'] = pvd[40:72].decode('ascii', 'replace').rstrip('\x00 ')
    result['declared_bytes'] = struct.unpack_from('<I', pvd, 80)[0] * struct.unpack_from('<H', pvd, 128)[0]
    result['files'] = []
    iso = pycdlib.PyCdlib()
    try:
        iso.open(str(path))
        for parent, dirs, files in iso.walk(iso_path='/'):
            for name in files:
                full = parent.rstrip('/') + '/' + name
                record = iso.get_record(iso_path=full)
                result['files'].append({'path': full, 'size': record.data_length,
                    'extent': record.extent_location(),
                    'within_image': record.extent_location() * 2048 + record.data_length <= path.stat().st_size})
        result['file_count'] = len(result['files'])
        result['declared_file_bytes'] = sum(row['size'] for row in result['files'])
    except Exception as error:
        result['error'] = type(error).__name__ + ': ' + str(error)
    finally:
        try:
            iso.close()
        except Exception:
            pass
    return result


def fpb_stats(root):
    result = {'files': 0, 'records': 0, 'valid': 0, 'empty': 0, 'errors': [],
        'cp949_valid': 0, 'utf8_valid': 0, 'non_ascii': 0}
    for path in sorted((root / 'Fpb').glob('*')):
        if not path.is_file():
            continue
        result['files'] += 1
        data = path.read_bytes()
        try:
            if data == b'\x00\x00\x00\x00':
                result['valid'] += 1
                result['empty'] += 1
                continue
            if len(data) < 8:
                raise ValueError('truncated header')
            count = struct.unpack_from('<I', data)[0]
            base = 8 + 12 * count
            if base > len(data):
                raise ValueError('table exceeds file')
            total = struct.unpack_from('<I', data, 4 + 12 * count)[0]
            if base + total != len(data):
                raise ValueError('payload size mismatch')
            expected = 0
            strings = []
            for i in range(count):
                tag, offset, length = struct.unpack_from('<III', data, 4 + 12 * i)
                if offset != expected or length < 1 or offset + length > total:
                    raise ValueError('invalid string range')
                raw = data[base + offset:base + offset + length]
                if raw[-1] != 0:
                    raise ValueError('missing terminator')
                strings.append(raw[:-1])
                expected = offset + length
            if expected != total:
                raise ValueError('payload not covered')
            result['records'] += count
            result['valid'] += 1
            for raw in strings:
                if any(b > 127 for b in raw):
                    result['non_ascii'] += 1
                for encoding, key in [('cp949', 'cp949_valid'), ('utf-8', 'utf8_valid')]:
                    try:
                        raw.decode(encoding)
                        result[key] += 1
                    except UnicodeDecodeError:
                        pass
        except (ValueError, struct.error) as error:
            result['errors'].append({'file': path.name, 'error': str(error)})
    return result


def inspect(root, images):
    files = [p for p in root.rglob('*') if p.is_file()]
    report = {'schema': 1, 'file_count': len(files), 'bytes': sum(p.stat().st_size for p in files),
        'groups': dict(Counter(p.relative_to(root).parts[0] for p in files)),
        'extensions': dict(Counter(p.suffix.lower() for p in files)), 'pe': [], 'images': [],
        'fonts': [], 'fpb': fpb_stats(root)}
    for path in sorted(files):
        if path.suffix.lower() in ('.exe', '.dll'):
            entry = inspect_pe(path)
            entry['file'] = path.relative_to(root).as_posix()
            report['pe'].append(entry)
        if path.parent.name == 'Font':
            report['fonts'].append({'file': path.name, 'size': path.stat().st_size, 'sha256': digest(path)})
    for path in sorted(images.glob('*')):
        if path.suffix.lower() == '.iso':
            report['images'].append(inspect_iso(path))
        elif path.suffix.lower() == '.exe':
            report.setdefault('patches', []).append(inspect_pe(path))
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--workspace', type=Path, required=True)
    p.add_argument('--images', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    root = a.workspace.resolve(strict=True)
    images = a.images.resolve(strict=True)
    output = a.report.resolve()
    if output.is_relative_to(root) or output.is_relative_to(images):
        raise ValueError('Report must be outside inspected inputs')
    data = inspect(root, images)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'STATIC_SURVEY PASS files={data["file_count"]} pe={len(data["pe"])} images={len(data["images"])} fpb_valid={data["fpb"]["valid"]}')
