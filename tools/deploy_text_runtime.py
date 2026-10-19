"""Deploy a hash-checked text candidate and owned runtime without copying saves."""
import argparse
import json
from pathlib import Path

from build_runtime_hotfix import located, sha
from update_configuration_runtime import idle, write, rollback
from build_text_runtime_update import allowed


def apply(runtime, candidate, native, record):
    runtime, candidate, native, record = map(lambda p: Path(p).resolve(), (runtime, candidate, native, record))
    idle()
    if record.exists() or any(record.is_relative_to(p) or p.is_relative_to(record) for p in (runtime, candidate, native)):
        raise ValueError('New separate deployment record required')
    manifest = json.loads((runtime/'runtime.json').read_text(encoding='utf-8-sig'))
    for collection, base in [('files', runtime), ('data', runtime/'data')]:
        for name, digest in manifest[collection].items():
            if sha(located(base, name)) != digest:
                raise ValueError('Runtime drift: '+name)
    replacements = {}
    seen = set()
    for row in json.loads((candidate/'build.json').read_text(encoding='utf8'))['files']:
        name = row['resource']
        if not allowed('data/'+name) or name.lower() in seen or sha(located(runtime/'data', name)) != row['before_sha256']:
            raise ValueError('Candidate source mismatch: '+name)
        seen.add(name.lower())
        path = located(candidate, name)
        if sha(path) != row['after_sha256']:
            raise ValueError('Candidate output mismatch: '+name)
        replacements['data/'+name] = path.read_bytes()
        manifest['data'][name] = row['after_sha256']
    module = (native/'workspace_profile.dll').read_bytes()
    for name in manifest['files']:
        if name.startswith('modules/') and name.endswith('.dll'):
            replacements[name] = module
    replacements['modules/workspace_launcher.exe'] = (native/'workspace_launcher.exe').read_bytes()
    import hashlib
    digest = lambda b: hashlib.sha256(b).hexdigest()
    for name, data in replacements.items():
        if not name.startswith('data/'):
            manifest['files'][name] = digest(data)
    replacements['runtime.json'] = (json.dumps(manifest, indent=2)+'\n').encode('utf8')
    originals = {name: located(runtime, name).read_bytes() for name in replacements}
    states = {name: dict(before=digest(originals[name]), after=digest(data)) for name, data in replacements.items()}
    # Preserve only changed files, not a second complete game installation.
    states = {name: row for name, row in states.items() if row['before'] != row['after']}
    settings = runtime/'config/enhancements.json'
    saves = {p: sha(p) for p in runtime.rglob('*.sav')}
    settings_hash = sha(settings)
    record.mkdir(parents=True)
    for name in states:
        path = located(record/'original', name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(originals[name])
    (record/'settings.sha256').write_text(settings_hash, encoding='ascii')
    (record/'changes.json').write_text(json.dumps(states, indent=2)+'\n', encoding='utf8')
    done = []
    try:
        for name in states:
            if located(runtime, name).read_bytes() != originals[name]:
                raise ValueError('Target changed before write: '+name)
            done.append(name)
            write(located(runtime, name), replacements[name])
            if sha(located(runtime, name)) != states[name]['after']:
                raise ValueError('Deployment readback mismatch: '+name)
        if sha(settings) != settings_hash or any(sha(p) != h for p, h in saves.items()):
            raise ValueError('Saves/settings changed during deployment')
    except Exception:
        for name in reversed(done):
            write(located(runtime, name), originals[name])
        raise
    print(f'TEXT_RUNTIME_DEPLOY PASS files={len(states)} saves={len(saves)} settings_preserved=true game_started=false')
    return states


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['apply', 'rollback'])
    for key in ('runtime', 'record'):
        p.add_argument('--'+key, type=Path, required=True)
    for key in ('candidate', 'native'):
        p.add_argument('--'+key, type=Path)
    a = p.parse_args()
    if a.action == 'apply':
        if a.candidate is None or a.native is None:
            p.error('apply requires --candidate and --native')
        apply(a.runtime, a.candidate, a.native, a.record)
    else:
        rollback(a.runtime, a.record)
