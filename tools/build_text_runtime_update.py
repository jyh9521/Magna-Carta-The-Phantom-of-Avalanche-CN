"""Build a small, source-locked shared-runtime update (game data is delta-only)."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def allowed(name):
    return bool(re.fullmatch(r'runtime\.json|modules/(?:[A-Za-z0-9_-]+\.dll|workspace_launcher\.exe)|data/BGR/[A-Za-z0-9_-]+\.bgr|data/Fpb/[A-Za-z0-9_-]+\.fpb|data/(?:Itm/0000\.itm|Abi/0000\.abi|Sgi/0000\.sgi|CharData/0000\.cha|MCAlpha\.dll)', name, re.I))


def located(root, name):
    if not allowed(name):
        raise ValueError('Unsupported update path: '+name)
    p = root/name
    if not p.resolve().is_relative_to(root) or any(q.is_symlink() or (hasattr(q, 'is_junction') and q.is_junction()) for q in [p, *p.parents] if q != root.parent):
        raise ValueError('Linked or escaping update path')
    return p


def delta(before, after):
    raw = bytearray(b'MCD1'+struct.pack('<Q', len(after)))
    off = 0
    literal_size = 0
    while off < len(after):
        if off < len(before) and before[off] == after[off]:
            off += 1
            continue
        start = off
        while off < len(after) and off-start < 4096 and (off >= len(before) or before[off] != after[off]):
            off += 1
        raw += struct.pack('<QI', start, off-start)+after[start:off]
        literal_size += off-start
    if after and literal_size == len(after):
        raise ValueError('Delta would contain the entire game resource')
    return bytes(raw)


def build(runtime, record, output):
    runtime = Path(runtime).resolve(strict=True)
    record = Path(record).resolve(strict=True)
    output = Path(output).resolve()
    if output.suffix.lower() != '.zip' or output.exists() or any(output.is_relative_to(p) for p in [runtime, record]):
        raise ValueError('New separate .zip output required')
    states = json.loads((record/'changes.json').read_text(encoding='utf-8-sig'))
    if states.get('kind') == 'owned_runtime_module_update':
        from update_runtime_modules import CHANGES
        changes = states.get('changes', [])
        if states.get('schema') != 1 or [row.get('path') for row in changes] != list(CHANGES):
            raise ValueError('Invalid owned-module deployment record')
        states = {row['path']: {'before': row['before'], 'after': row['after']}
                  for row in changes}
    if not states or 'runtime.json' not in states:
        raise ValueError('Deployment record must include runtime.json')
    if len({name.lower() for name in states}) != len(states):
        raise ValueError('Case-colliding deployment paths')
    payload = {}
    rows = []
    for name, state in sorted(states.items()):
        if not allowed(name) or set(state) != {'before', 'after'}:
            raise ValueError('Unsupported deployment record: '+name)
        after = located(runtime, name).read_bytes()
        before = located(record/'original', name).read_bytes() if state['before'] is not None else None
        if sha(after) != state['after'] or (before is not None and sha(before) != state['before']):
            raise ValueError('Deployment hash mismatch: '+name)
        if before == after:
            continue
        game_data = name.lower().startswith('data/')
        if game_data and before is None:
            raise ValueError('Game resource requires existing source')
        key = 'payload/%04d.%s' % (len(rows), 'mcd' if game_data else 'bin')
        raw = delta(before, after) if game_data else after
        payload[key] = raw
        rows.append(dict(path=name, before=state['before'], after=state['after'],
                         size=len(after), payload=key, payload_sha256=sha(raw), delta=game_data))
    if not rows:
        raise ValueError('Empty update')
    manifest = dict(schema=1, kind='text_runtime_update', files=rows,
                    in_game_verified=False, saves_and_settings_preserved=True)
    payload['package.json'] = (json.dumps(manifest, indent=2)+'\n').encode()
    payload['Update.ps1'] = (ROOT/'assets/text-runtime-update/Update.ps1').read_bytes()
    payload['Update.cmd'] = b'@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Update.ps1" %*\r\nif errorlevel 1 pause\r\n'
    payload['README.txt'] = ('Extract this ZIP. Exit the game first.\r\n'
        'Update.cmd -Action Verify -Runtime "PATH_TO_SHARED_RUNTIME"\r\n'
        'Update.cmd -Action Install -Runtime "PATH_TO_SHARED_RUNTIME"\r\n'
        'Update.cmd -Action CheckInstalled -Runtime "PATH_TO_SHARED_RUNTIME"\r\n'
        'Update.cmd -Action Rollback -Runtime "PATH_TO_SHARED_RUNTIME"\r\n'
        'Only source-locked changed files are touched; saves/settings are preserved.\r\n').encode()
    for name in ['LICENSE', 'LICENSE-translations.md', 'LICENSING.md']:
        payload['licenses/'+name] = (ROOT/name).read_bytes()
    payload['licenses/NotoSansSC-OFL.txt'] = (ROOT/'assets/licenses/NotoSansSC-OFL.txt').read_bytes()
    # Recheck every input immediately before publication.
    for name, state in states.items():
        if sha(located(runtime, name).read_bytes()) != state['after']:
            raise ValueError('Runtime drift during build')
        if state['before'] is not None and sha(located(record/'original', name).read_bytes()) != state['before']:
            raise ValueError('Backup drift during build')
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, raw in sorted(payload.items()):
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, raw)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError('ZIP readback failed')
    print(f'TEXT_RUNTIME_PACKAGE PASS files={len(rows)} zip={output} sha256={sha(output.read_bytes())}')
    return output


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['runtime', 'record', 'output']:
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    build(a.runtime, a.record, a.output)
