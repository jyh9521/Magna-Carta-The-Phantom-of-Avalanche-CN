"""Create a verified game copy without writing to the source tree."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def inventory(root):
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Source must be a directory')
    rows = []
    for path in sorted(root.rglob('*')):
        if path.is_symlink() or path.is_junction():
            raise ValueError('Linked inputs are not supported: ' + str(path))
        if path.is_file():
            rows.append({'path': path.relative_to(root).as_posix(),
                         'size': path.stat().st_size, 'sha256': digest(path)})
    return rows


def prepare(source, target, manifest):
    source = Path(source).resolve(strict=True)
    target = Path(target).resolve()
    manifest = Path(manifest).resolve()
    if target == source or target.is_relative_to(source) or source.is_relative_to(target):
        raise ValueError('Source and target must be separate trees')
    if manifest.is_relative_to(source):
        raise ValueError('Manifest must not be written inside source')
    if target.exists():
        raise ValueError('Target already exists; use a new workspace')
    before = inventory(source)
    if not before:
        raise ValueError('Source is empty')
    target.mkdir(parents=True)
    for row in before:
        src = source / row['path']
        dst = target / row['path']
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    copied = inventory(target)
    after = inventory(source)
    if before != copied or before != after:
        raise ValueError('Copy mismatch or source changed during preparation')
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps({'schema': 1, 'source': str(source),
        'workspace': str(target), 'files': before, 'source_unchanged': True,
        'copy_verified': True}, ensure_ascii=False, indent=2), encoding='utf-8')
    return before


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--target', type=Path, required=True)
    p.add_argument('--manifest', type=Path, required=True)
    a = p.parse_args()
    rows = prepare(a.source, a.target, a.manifest)
    print(f'WORKSPACE_COPY PASS files={len(rows)} bytes={sum(r["size"] for r in rows)} source_unchanged=true')
