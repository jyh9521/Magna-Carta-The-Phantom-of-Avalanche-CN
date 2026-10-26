"""Replay one complete ZIP over a minimal old-overlay fixture; never launch the game."""
import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import uuid
import zipfile

from build_clean_overlay import safe_name
from verify_compiled_release import read_embedded


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def target(root, name):
    safe_name(name)
    path = Path(root)/name
    for part in (path, *path.parents):
        if part.is_symlink() or part.is_junction():
            raise ValueError('Linked replay path rejected: '+str(part))
    return path


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('write-'+uuid.uuid4().hex+'.tmp')
    try:
        temporary.write_bytes(data)
        os.replace(temporary, path)  # Break hardlinks instead of changing the shared inode.
    finally:
        temporary.unlink(missing_ok=True)


def save(path, value):
    write(path, (json.dumps(value, ensure_ascii=False, indent=2)+'\n').encode('utf8'))


def check_effective_base(archive, source, overlay):
    """Hash original files not replaced by this ZIP; do not copy the complete game."""
    with zipfile.ZipFile(archive) as z:
        supplied = set(z.namelist())
    checked = covered = 0
    mismatches = []
    for name, expected in overlay['source_files'].items():
        if name in supplied:
            covered += 1
            continue
        path = target(source, name)
        checked += 1
        if not path.is_file() or sha(path) != expected:
            mismatches.append(name)
    if mismatches:
        raise ValueError('Uncovered original input differences: '+str(len(mismatches))+' '+
                         ', '.join(mismatches[:8]))
    return dict(original_files=len(overlay['source_files']), supplied_by_zip=covered,
                checked_in_place=checked, uncovered_differences=0)


def rollback(work):
    work = Path(work).resolve()
    state = json.loads((work/'rollback-state.json').read_bytes())
    root = work/'rollback-copy'
    for name, row in state.items():
        if sha(target(root, name)) != row['after']:
            raise ValueError('Rollback target drift: '+name)
        if row['before'] is not None and sha(target(work/'before', name)) != row['before']:
            raise ValueError('Rollback backup drift: '+name)
    for name, row in state.items():
        path = target(root, name)
        if row['before'] is None:
            path.unlink()
        else:
            write(path, target(work/'before', name).read_bytes())
    for name, row in state.items():
        path = target(root, name)
        if (path.exists() if row['before'] is None else sha(path) != row['before']):
            raise ValueError('Rollback readback mismatch: '+name)
    print('UNIFIED_ROLLBACK PASS files='+str(len(state))+' original_bytes=exact isolated=true')


def verify(archive, archive_sha256, previous, previous_sha256, source, settings, work):
    archive, previous, source, settings, work = [Path(p).resolve() for p in
                                               (archive, previous, source, settings, work)]
    if work.exists() or work == source or work.is_relative_to(source) or source.is_relative_to(work):
        raise ValueError('Independent new replay directory required')
    if sha(archive) != archive_sha256 or sha(previous) != previous_sha256:
        raise ValueError('Replay archive identity mismatch')
    settings_bytes = settings.read_bytes()
    with tempfile.TemporaryDirectory(prefix='overlay metadata ') as folder:
        core = Path(folder)/'DesktopRuntime.dll'
        with zipfile.ZipFile(archive) as z:
            core.write_bytes(z.read('modules/DesktopRuntime.dll'))
        metadata = read_embedded(core)
    runtime = metadata['runtime.json']
    if runtime.get('complete_inputs', {}).get('files') != runtime['data']:
        raise ValueError('Complete input metadata required')
    effective = check_effective_base(archive, source, metadata['Overlay-Manifest.json'])
    work.mkdir(parents=True)
    root = work/'modified-copy'
    root.mkdir()
    with zipfile.ZipFile(previous) as z:
        for name in z.namelist():
            write(target(root, name), z.read(name))
    seeded = {}
    for name in runtime['data']:
        path = target(root, name)
        original = target(source, name)
        if not path.exists() and original.is_file():
            write(path, original.read_bytes())
            seeded[name] = sha(original)
    # These are owned sentinels, not copies of a complete game or personal saves.
    write(root/'MC00.SAV', b'owned replay save sentinel')
    write(root/'user-note.txt', b'owned replay unrelated file')
    protected = {name: sha(root/name) for name in ('MC00.SAV', 'user-note.txt')}
    env = dict(os.environ, LOCALAPPDATA=str(work/'user-data'))
    key = hashlib.sha256(str(root).rstrip('\\/').upper().encode()).hexdigest()[:16]
    user = work/'user-data/MagnaCarta/Installations'/key
    write(user/'enhancements.json', settings_bytes)
    records = {}

    def run(label, location, name, args, expected):
        cmd = [str(location/(name+'.exe')), *map(str, args)]
        result = subprocess.run(cmd, capture_output=True, env=env, timeout=30)
        installation = hashlib.sha256(str(location).rstrip('\\/').upper().encode()).hexdigest()[:16]
        cache = work/'user-data/MagnaCarta/Installations'/installation/'cache'
        log = cache/(name+'.log')
        record = dict(command=subprocess.list2cmdline(cmd), exit_status=result.returncode,
                      output=log.read_text(encoding='utf-8-sig') if log.exists() else '',
                      stderr=result.stderr.decode('utf8', errors='replace'))
        if (cache/'launcher.stdout.txt').exists():
            record['native_output'] = (cache/'launcher.stdout.txt').read_text(encoding='utf-8-sig')
        records[label] = record
        save(work/'commands.json', records)
        if result.returncode != expected:
            raise ValueError(label+' exit mismatch: '+json.dumps(record, ensure_ascii=True))
        return record

    baseline = run('BASELINE', root, 'Game', ['--verify-only'], 1)
    if 'Hash mismatch: Asura.dll' not in baseline['output']:
        raise ValueError('Baseline did not reproduce the observed library failure')
    state = {}
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            path = target(root, name)
            data = z.read(name)
            after = hashlib.sha256(data).hexdigest()
            before = sha(path) if path.exists() else None
            if before != after:
                if before is not None:
                    write(target(work/'before', name), path.read_bytes())
                state[name] = dict(before=before, after=after)
            write(path, data)
    save(work/'rollback-state.json', state)
    ini = (root/'DDrawCompat-MagnaCarta.ini').read_bytes()
    run('CHECK_INSTALLED', root, 'Game', ['--check-installed'], 0)
    modified = run('MODIFIED', root, 'Game', ['--verify-only'], 0)
    if 'WORKSPACE_VERIFY PASS' not in modified.get('native_output', ''):
        raise ValueError('Real native preflight marker missing')
    for resolution, mode, fps in itertools.product(('1080p', '2k', '4k', 'auto'),
                                                   ('fullscreen', 'windowed', 'borderless'), (30, 60)):
        value = json.loads(settings_bytes)
        value.update(schema=2, resolution=resolution, window_mode=mode, frame_rate=fps,
                     native_gamepad=False, free_view=False, window_resolution='1280x720')
        profile = work/'profile-settings.json'
        save(profile, value)
        record = run('PROFILE_'+resolution+'_'+mode+'_'+str(fps), root, 'Game',
                     ['--verify-only', '--settings-file', profile], 0)
        if 'WORKSPACE_VERIFY PASS' not in record.get('native_output', ''):
            raise ValueError('Profile did not reach native preflight')
        if (root/'DDrawCompat-MagnaCarta.ini').read_bytes() != ini:
            raise ValueError('Display INI not restored')
    run('CONFIGURE', root, 'Configure', ['--self-test', '--preview', work/'configuration.png'], 0)
    restored = work/'rollback-copy'
    for path in root.rglob('*'):
        if path.is_file():
            dest = target(restored, path.relative_to(root).as_posix())
            dest.parent.mkdir(parents=True, exist_ok=True)
            os.link(path, dest)
    script = work/'ROLLBACK.sh'
    script.write_bytes(('#!/usr/bin/env bash\nset -eu\npython '+
                        shlex.quote(Path(__file__).resolve().as_posix())+' rollback --work '+
                        shlex.quote(work.as_posix())+'\n').encode())
    script.chmod(0o755)
    bash = Path(os.environ.get('ProgramFiles', 'C:/Program Files'))/'Git/bin/bash.exe'
    cmd = [str(bash), str(script)]
    result = subprocess.run(cmd, capture_output=True, timeout=30)
    records['ROLLBACK'] = dict(command=subprocess.list2cmdline(cmd), exit_status=result.returncode,
                               output=result.stdout.decode('utf8').strip(),
                               stderr=result.stderr.decode('utf8', errors='replace'))
    if result.returncode:
        save(work/'commands.json', records)
        raise ValueError('Independent rollback failed')
    old = run('RESTORED', restored, 'Game',
              ['--verify-only', '--settings-file', user/'enhancements.json'], 1)
    if 'Hash mismatch: Asura.dll' not in old['output']:
        raise ValueError('Restored behavior differs from the baseline')
    # Prove replacement in the hardlinked view did not change the modified deliverable.
    for name, row in state.items():
        if sha(target(root, name)) != row['after']:
            raise ValueError('Modified fixture changed during rollback: '+name)
    for location in (root, restored):
        if any(sha(location/name) != digest for name, digest in protected.items()):
            raise ValueError('User-file sentinel changed')
    if (user/'enhancements.json').read_bytes() != settings_bytes or settings.read_bytes() != settings_bytes:
        raise ValueError('User settings changed')
    if any(sha(target(source, name)) != digest for name, digest in seeded.items()):
        raise ValueError('Original installation input changed')
    report = dict(archive=str(archive), sha256=archive_sha256, previous_sha256=previous_sha256,
                  bundled_inputs=len(runtime['data']), changed_files=len(state), profiles=24,
                  baseline_exit=1, modified_exit=0, rollback_exit=0, restored_exit=1,
                  original_inputs_preserved=True, settings_preserved=True, saves_preserved=True,
                  rollback_storage='hardlinked sparse overlay view; changed inodes replaced',
                  game_started=False)
    report['effective_original'] = effective
    save(work/'report.json', report)
    print('UNIFIED_OVERLAY PASS baseline_exit=1 modified_exit=0 rollback_exit=0 restored_exit=1 '
          'profiles=24 bundled_inputs='+str(len(runtime['data']))+' game_started=false')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest='action', required=True)
    p = actions.add_parser('verify')
    for name in ('archive', 'previous', 'source', 'settings', 'work'):
        p.add_argument('--'+name, type=Path, required=True)
    for name in ('archive-sha256', 'previous-sha256'):
        p.add_argument('--'+name, required=True)
    actions.add_parser('rollback').add_argument('--work', type=Path, required=True)
    args = vars(parser.parse_args())
    action = args.pop('action')
    if action == 'verify':
        verify(**args)
    else:
        rollback(**args)
