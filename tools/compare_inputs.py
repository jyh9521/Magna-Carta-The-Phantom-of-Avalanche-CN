"""Compare ISO and ZIP-SFX members with an installed workspace, read-only."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import zipfile

import pycdlib


def hash_stream(stream):
    h = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b''):
        h.update(block)
    return h.hexdigest()


def compare(workspace, image, patch):
    index = {p.relative_to(workspace).as_posix().casefold(): p
        for p in workspace.rglob('*') if p.is_file()}

    def row(name, size, stream):
        relative = name.replace('\\', '/').lstrip('/').split(';')[0]
        target = index.get(relative.casefold())
        result = {'path': name, 'size': size}
        if target is None:
            result['status'] = 'not-installed'
        elif target.stat().st_size != size:
            result.update(status='different-size', installed_size=target.stat().st_size)
        else:
            expected = hash_stream(stream)
            with target.open('rb') as src:
                actual = hash_stream(src)
            result.update(status='identical' if actual == expected else 'different-content', sha256=expected)
        return result

    results = {}
    iso = pycdlib.PyCdlib()
    iso.open(str(image))
    members = []
    try:
        for parent, dirs, files in iso.walk(iso_path='/'):
            for name in files:
                full = parent.rstrip('/') + '/' + name
                record = iso.get_record(iso_path=full)
                if record.extent_location() * 2048 + record.data_length > image.stat().st_size:
                    raise ValueError('ISO member exceeds physical image: ' + full)
                with iso.open_file_from_iso(iso_path=full) as src:
                    members.append(row(full, record.data_length, src))
    finally:
        iso.close()
    results['disc'] = {'files': members, 'counts': dict(Counter(r['status'] for r in members))}
    members = []
    with zipfile.ZipFile(patch) as archive:
        for info in archive.infolist():
            if not info.is_dir():
                with archive.open(info) as src:
                    members.append(row(info.filename, info.file_size, src))
    results['patch'] = {'files': members, 'counts': dict(Counter(r['status'] for r in members))}
    return results


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--workspace', type=Path, required=True)
    p.add_argument('--iso', type=Path, required=True)
    p.add_argument('--patch', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    a = p.parse_args()
    root = a.workspace.resolve(strict=True)
    if a.report.resolve().is_relative_to(root):
        raise ValueError('Report must be outside workspace')
    results = compare(root, a.iso, a.patch)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(results, indent=2), encoding='utf-8')
    print('INPUT_COMPARISON PASS disc=' + json.dumps(results['disc']['counts'], sort_keys=True) +
          ' patch=' + json.dumps(results['patch']['counts'], sort_keys=True))
