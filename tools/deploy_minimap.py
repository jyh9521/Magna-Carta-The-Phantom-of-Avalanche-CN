"""Install the F9 map candidate into an existing test runtime, with exact rollback.

Only the entry, new module and manifest-listed atlas are updated. No installer,
original game resource, save or user preference is produced or modified.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import struct
import subprocess

from prepare_shared_runtime import map_assets
from integrate_native_loading import runtime_lock

ROOT = Path(__file__).resolve().parents[1]
COMPASS_SOURCES = {
    'FrameData/0136.fdi': '175056f4553947d5b2b6725d9f93d24b7271676220ea79adba16a01d40b54254',
    'BGR/0234.BGR': 'a17914d8c60bc0014830c6d8d1920974f8bb6004a4f1040b8883e13f694159aa',
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def child(root, name):
    p = PurePosixPath(name)
    if (not isinstance(name, str) or '\\' in name or ':' in name or p.is_absolute()
            or not p.parts or any(x in ('', '.', '..') for x in name.split('/'))):
        raise ValueError('Invalid relative payload path')
    result = root.joinpath(*p.parts)
    if not result.resolve().is_relative_to(root.resolve()):
        raise ValueError('Payload escapes root')
    for value in [result, *result.parents]:
        if value == root:
            break
        if value.is_symlink() or (hasattr(value, 'is_junction') and value.is_junction()):
            raise ValueError('Linked payload path')
    return result


def idle():
    if os.name == 'nt':
        r = subprocess.run(['powershell.exe', '-NoProfile', '-Command',
                            'if(Get-Process MagnaCarta,workspace_launcher -ErrorAction SilentlyContinue){exit 9}'],
                           capture_output=True, timeout=20)
        if r.returncode:
            raise ValueError('Exit active game and launcher before map deployment')


def check_module(data):
    if len(data) < 256 or data[:2] != b'MZ':
        raise ValueError('Expected F9 map Win32 DLL')
    offset = struct.unpack_from('<I', data, 0x3c)[0]
    if offset < 64 or offset + 26 > len(data):
        raise ValueError('Invalid map DLL PE header')
    if (data[offset:offset+4] != b'PE\0\0'
            or struct.unpack_from('<H', data, offset+4)[0] != 0x14c
            or not struct.unpack_from('<H', data, offset+22)[0] & 0x2000
            or struct.unpack_from('<H', data, offset+24)[0] != 0x10b
            or 'MAP_F9_CYCLE_V1'.encode('utf-16le') not in data):
        raise ValueError('Expected source-built F9 map PE32 DLL')


def atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.minimap-tmp')
    created = False
    try:
        with temp.open('xb') as stream:
            created = True
            stream.write(data)
        os.replace(temp, path)
    finally:
        if created and temp.exists():
            temp.unlink()


def apply(runtime, native, atlas, record):
    with runtime_lock(runtime):
        return apply_locked(runtime, native, atlas, record)


def apply_locked(runtime, native, atlas, record):
    idle()
    runtime, native, atlas, record = [Path(p).resolve() for p in (runtime, native, atlas, record)]
    if record.exists() or (record.is_relative_to(runtime) and not record.is_relative_to(runtime/'maintenance')):
        raise ValueError('New independent deployment record required')
    state = json.loads((runtime/'runtime.json').read_text(encoding='utf-8-sig'))
    if type(state.get('schema')) is not int or state['schema'] != 1:
        raise ValueError('Unsupported runtime schema')
    layout = state.get('data_root', 'data')
    if layout not in ('data', '.'):
        raise ValueError('Unsupported data layout')
    if layout == '.' and record.is_relative_to(runtime):
        raise ValueError('Flat test layouts require an external deployment record')
    game = runtime if layout == '.' else runtime/'data'
    for name, expected in state['files'].items():
        if digest(child(runtime, name)) != expected:
            raise ValueError('Runtime drift: ' + name)
    for name, expected in state['data'].items():
        if digest(child(game, name)) != expected:
            raise ValueError('Game input drift: ' + name)
    module = native.read_bytes()
    check_module(module)
    if 'MAP_FRAME_PRESENT_V2'.encode('utf-16le') in module:
        for name, expected in COMPASS_SOURCES.items():
            source = child(game, name)
            if not source.is_file() or digest(source) != expected:
                raise ValueError('Compass layout source drift: ' + name)
            # Future launches guard the same UI anchor evidence, without changing resources.
            state['data'][name] = expected
    assets = map_assets(atlas, require_nonempty=True)
    stale_points = {name for name in state['files'] if name.startswith('maps/points/')} - set(assets)
    if stale_points:
        raise ValueError('Stale map points require explicit rollback before replacement')
    atlas_state = json.loads((atlas/'manifest.json').read_text(encoding='utf8'))
    if atlas_state.get('projection') != 'first_instance_frame_column_major_XY':
        raise ValueError('Unsupported map coordinate projection')
    for row in atlas_state['accepted']:
        source = game/'MAP'/f"{row['id']:04d}.wrd"
        if digest(source) != row.get('source_sha256'):
            raise ValueError('Map source drift: ' + source.name)
    points_manifest = atlas/'points/manifest.json'
    point_count = 0
    if points_manifest.is_file():
        points = json.loads(points_manifest.read_text(encoding='utf8'))
        if digest(game/'MCAlpha.dll') != points['source_engine_sha256']:
            raise ValueError('Map point loader source drift')
        for row in points['accepted']:
            source = game/'Field'/f"{row['field_id']:04d}.fld"
            if digest(source) != row['source_sha256']:
                raise ValueError('Map point Field source drift: ' + source.name)
        point_count = points['marker_count']
    payload = {'Start.ps1': (ROOT/'src/configuration/StartShared.ps1').read_bytes(),
               'modules/minimap.dll': module}
    for name, expected in assets.items():
        data = child(atlas, PurePosixPath(name).relative_to('maps').as_posix()).read_bytes()
        if sha(data) != expected:
            raise ValueError('Map changed while preparing deployment')
        payload[name] = data
    for name in payload:
        if child(runtime, name).exists() and name not in state['files']:
            raise ValueError('Unregistered existing map target: ' + name)
    state['map_overlay'] = dict(schema=1, enabled=True, module='minimap')
    for name, data in payload.items():
        state['files'][name] = sha(data)
    payload['runtime.json'] = (json.dumps(state, indent=2)+'\n').encode('utf8')
    # A flat test layout can have an additional overlay checksum inventory.
    if (runtime/'Overlay-Manifest.json').is_file():
        overlay = json.loads((runtime/'Overlay-Manifest.json').read_text(encoding='utf-8-sig'))
        if not isinstance(overlay.get('files'), dict):
            raise ValueError('Unsupported overlay inventory')
        for name, expected in overlay['files'].items():
            if digest(child(runtime, name)) != expected:
                raise ValueError('Overlay input drift: ' + name)
        for name, data in payload.items():
            overlay['files'][name] = sha(data)
        overlay['map_overlay'] = state['map_overlay']
        payload['Overlay-Manifest.json'] = (json.dumps(overlay, indent=2)+'\n').encode('utf8')
    changes = {}
    originals = {}
    for name, data in payload.items():
        path = child(runtime, name)
        old = path.read_bytes() if path.exists() else None
        if old == data:
            continue
        if name != 'runtime.json' and name not in state['files'] and name != 'Overlay-Manifest.json':
            raise ValueError('Unlisted payload')
        originals[name] = old
        changes[name] = dict(before=sha(old) if old is not None else None, after=sha(data))
    record.mkdir(parents=True)
    for name, old in originals.items():
        if old is not None:
            saved = child(record/'original', name)
            saved.parent.mkdir(parents=True, exist_ok=True)
            saved.write_bytes(old)
    (record/'changes.json').write_text(json.dumps(changes, indent=2)+'\n', encoding='utf8')
    applied = []
    try:
        for name in changes:
            atomic(child(runtime, name), payload[name])
            applied.append(name)
            if digest(child(runtime, name)) != changes[name]['after']:
                raise ValueError('Map deployment readback mismatch')
    except Exception:
        for name in reversed(applied):
            if originals[name] is None:
                child(runtime, name).unlink()
            else:
                atomic(child(runtime, name), originals[name])
        raise
    print(f'MINIMAP_DEPLOY PASS files={len(changes)} maps={len(atlas_state["accepted"])} exits={point_count} '
          'initial=off key=F9 cycle=mini,full,off game_data=unchanged settings=preserved installer=unchanged')
    return changes


def rollback(runtime, record):
    with runtime_lock(runtime):
        return rollback_locked(runtime, record)


def rollback_locked(runtime, record):
    idle()
    runtime, record = Path(runtime).resolve(), Path(record).resolve()
    changes = json.loads((record/'changes.json').read_text(encoding='utf8'))
    for name, row in changes.items():
        # Rollback records may not target game assets, settings or arbitrary paths.
        if not (name in ('Start.ps1', 'runtime.json', 'Overlay-Manifest.json', 'modules/minimap.dll')
                or name.startswith('maps/')):
            raise ValueError('Unexpected rollback target')
        if digest(child(runtime, name)) != row['after']:
            raise ValueError('Rollback target drift: ' + name)
        if row['before'] is not None and digest(child(record/'original', name)) != row['before']:
            raise ValueError('Rollback source drift: ' + name)
    after = {name: child(runtime, name).read_bytes() for name in changes}
    restored = []
    try:
        for name, row in reversed(list(changes.items())):
            target = child(runtime, name)
            if row['before'] is None:
                target.unlink()
            else:
                atomic(target, child(record/'original', name).read_bytes())
            restored.append(name)
    except Exception:
        for name in reversed(restored):
            atomic(child(runtime, name), after[name])
        raise
    for name, row in changes.items():
        target = child(runtime, name)
        if (target.exists() if row['before'] is None else digest(target) != row['before']):
            raise ValueError('Rollback readback mismatch: ' + name)
    print(f'MINIMAP_ROLLBACK PASS files={len(changes)} original_hashes=exact '
          'new_files=removed game_data=unchanged settings=preserved')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['apply', 'rollback'])
    for key in ('runtime', 'record'):
        parser.add_argument('--'+key, type=Path, required=True)
    parser.add_argument('--native', type=Path)
    parser.add_argument('--atlas', type=Path)
    args = parser.parse_args()
    if args.action == 'apply':
        if args.native is None or args.atlas is None:
            parser.error('--native DLL and --atlas are required for apply')
        apply(args.runtime, args.native, args.atlas, args.record)
    else:
        rollback(args.runtime, args.record)
