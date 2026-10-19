"""Install an opt-in, reversible Field return-height runtime candidate.

The default module/settings/game data are retained. Only the versioned shared
launcher and runtime manifest change; two candidate-only files are added.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile

CHANGED = ('Start.ps1', 'runtime.json', 'modules/field-return-height.dll', 'Play-stairwell-fix.cmd')
BACKUPS = {'Start.ps1': 'before/Start.ps1', 'runtime.json': 'before/runtime.json'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def ordinary(path, *, exists=True, directory=False):
    """Reject symlinks/junctions in every existing component before resolving."""
    path = Path(os.path.abspath(path))
    for item in reversed((path, *path.parents)):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError(f'Reparse path rejected: {item}')
    if exists:
        if not path.exists() or (not path.is_dir() if directory else not path.is_file()):
            raise ValueError(f'Unexpected path type: {path}')
    elif path.exists():
        raise ValueError(f'New path already exists: {path}')
    return path


def relative(root, name):
    if (not isinstance(name, str) or '\\' in name or ':' in name
            or PurePosixPath(name).is_absolute() or not name
            or any(part in ('', '.', '..') for part in name.split('/'))):
        raise ValueError('Invalid runtime-relative path')
    target = root.joinpath(*name.split('/'))
    ordinary(target, exists=target.exists())
    return target


def load_json(data):
    def unique(pairs):
        result = {}
        for name, value in pairs:
            if name in result:
                raise ValueError('Duplicate JSON key')
            result[name] = value
        return result
    return json.loads(data.decode('utf-8-sig'), object_pairs_hook=unique)


def check_digest(value):
    if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
        raise ValueError('Invalid SHA256 record')


def validate_manifest(root, manifest):
    if (manifest.get('schema') != 1 or not isinstance(manifest.get('files'), dict)
            or 'Start.ps1' not in manifest['files']):
        raise ValueError('Unsupported runtime manifest or missing Start.ps1 digest')
    seen = set()
    for name, expected in manifest['files'].items():
        key = name.casefold()
        if key in seen:
            raise ValueError('Case-colliding runtime manifest paths')
        seen.add(key)
        check_digest(expected)
        path = relative(root, name)
        ordinary(path)
        if digest(path.read_bytes()) != expected:
            raise ValueError(f'Runtime input changed: {name}')


def patch_start(data):
    text = data.decode('utf8')
    if '$FieldReturnHeight' in text or 'MC_FIELD_RETURN_HEIGHT' in text:
        raise ValueError('Field return-height entry already installed')
    newline = '\r\n' if '\r\n' in text else '\n'
    substitutions = [
        ("[string]$SettingsFile='')", "[string]$SettingsFile='',[switch]$FieldReturnHeight)"),
        ("$ini=Join-Path $game 'DDrawCompat-MagnaCarta.ini'",
         "if($FieldReturnHeight){if(-not $manifest.field_return_height_module){throw 'Missing field return-height module'};$module=$manifest.field_return_height_module}"
         + newline + "$ini=Join-Path $game 'DDrawCompat-MagnaCarta.ini'"),
        ("'MC_WINDOWED','MC_WINDOW_RESOLUTION'", "'MC_WINDOWED','MC_WINDOW_RESOLUTION','MC_FIELD_RETURN_HEIGHT'"),
        (' $env:MC_WINDOW_RESOLUTION=', " $env:MC_FIELD_RETURN_HEIGHT=if($FieldReturnHeight){'1'}else{'0'}"
         + newline + ' $env:MC_WINDOW_RESOLUTION=')]
    restore = "foreach($key in $environment.Keys){[Environment]::SetEnvironmentVariable($key,$environment[$key],'Process')}"
    if text.count(restore) != 1:
        raise ValueError('Unknown or ambiguous environment restore anchor')
    for before, after in substitutions:
        if text.count(before) != 1:
            raise ValueError(f'Unknown or ambiguous launcher anchor: {before}')
        text = text.replace(before, after)
    return text.encode('utf8')


def write_file(path, data):
    """Replace one ordinary file atomically, never truncate a live target."""
    ordinary(path, exists=path.exists())
    ordinary(path.parent, directory=True)
    fd, temporary = tempfile.mkstemp(prefix='.field-return-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def check_state(root, rows, phase):
    for row in rows:
        path = relative(root, row['path'])
        expected = row[phase]
        if expected is None:
            ordinary(path, exists=False)
        else:
            ordinary(path)
            if digest(path.read_bytes()) != expected:
                raise ValueError(f'Runtime drift at {row["path"]}')


def restore_state(root, content):
    for name, data in content.items():
        path = relative(root, name)
        if data is None:
            if path.exists():
                ordinary(path)
                path.unlink()
        else:
            write_file(path, data)


def prepare(runtime, module, record):
    root = ordinary(runtime, directory=True)
    module = ordinary(module)
    record = ordinary(record, exists=False)
    if module.is_relative_to(root) or record.is_relative_to(root):
        raise ValueError('Module source and transaction record must be outside runtime')
    manifest_path = relative(root, 'runtime.json')
    manifest_bytes = manifest_path.read_bytes()
    manifest = load_json(manifest_bytes)
    validate_manifest(root, manifest)
    if 'field_return_height_module' in manifest:
        raise ValueError('Field return-height manifest already installed')
    for name in CHANGED[2:]:
        ordinary(relative(root, name), exists=False)
        if any(key.casefold() == name.casefold() for key in manifest['files']):
            raise ValueError('Candidate destination already recorded')
    ordinary(root/'modules', directory=True)
    before = {'Start.ps1': (root/'Start.ps1').read_bytes(), 'runtime.json': manifest_bytes,
              CHANGED[2]: None, CHANGED[3]: None}
    module_bytes = module.read_bytes()
    after = {'Start.ps1': patch_start(before['Start.ps1']), CHANGED[2]: module_bytes,
             CHANGED[3]: b'@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Start.ps1" -Recipe configured -FieldReturnHeight\r\nif errorlevel 1 pause\r\n'}
    manifest['field_return_height_module'] = 'field-return-height'
    for name, data in after.items():
        manifest['files'][name] = digest(data)
    after['runtime.json'] = (json.dumps(manifest, indent=2, ensure_ascii=False)+'\n').encode('utf8')
    rows = [{'path': name, 'before': digest(before[name]) if before[name] is not None else None,
             'after': digest(after[name]), 'backup': BACKUPS.get(name)} for name in CHANGED]
    transaction = {'schema': 1, 'kind': 'field_return_height_trial', 'runtime': str(root),
                   'module_source': str(module), 'module_source_sha256': digest(module_bytes),
                   'changes': rows, 'data_modified': False, 'default_candidate_enabled': False}
    # Recheck the complete read set immediately before creating the transaction.
    validate_manifest(root, load_json(manifest_bytes))
    check_state(root, rows, 'before')
    if digest(module.read_bytes()) != digest(module_bytes):
        raise ValueError('Module source changed during preflight')
    record.mkdir(parents=True, exist_ok=False)
    (record/'before').mkdir()
    for name, backup in BACKUPS.items():
        write_file(record/backup, before[name])
    write_file(record/'changes.json', (json.dumps(transaction, indent=2)+'\n').encode('utf8'))
    try:
        for name in (CHANGED[2], CHANGED[3], 'Start.ps1', 'runtime.json'):
            write_file(relative(root, name), after[name])
        check_state(root, rows, 'after')
    except BaseException:
        restore_state(root, before)
        check_state(root, rows, 'before')
        raise
    return transaction


def rollback(record):
    record = ordinary(record, directory=True)
    journal = ordinary(record/'changes.json')
    transaction = load_json(journal.read_bytes())
    if transaction.get('schema') != 1 or transaction.get('kind') != 'field_return_height_trial':
        raise ValueError('Unknown field return-height transaction')
    root = ordinary(transaction['runtime'], directory=True)
    if record.is_relative_to(root):
        raise ValueError('Transaction record must be outside runtime')
    rows = transaction.get('changes')
    if not isinstance(rows, list) or [r.get('path') for r in rows] != list(CHANGED):
        raise ValueError('Unexpected transaction change set')
    before, after = {}, {}
    for row in rows:
        check_digest(row['after'])
        name = row['path']
        if row.get('backup') != BACKUPS.get(name):
            raise ValueError('Unexpected transaction backup path')
        if name in BACKUPS:
            check_digest(row['before'])
            backup = ordinary(record/BACKUPS[name])
            content = backup.read_bytes()
            if digest(content) != row['before']:
                raise ValueError(f'Transaction backup changed: {name}')
            before[name] = content
        else:
            if row['before'] is not None:
                raise ValueError('Candidate destination was not originally absent')
            before[name] = None
    # All modified files and all originals must pass before any restoration.
    check_state(root, rows, 'after')
    for name in CHANGED:
        after[name] = relative(root, name).read_bytes()
    validate_manifest(root, load_json(after['runtime.json']))
    try:
        restore_state(root, before)
        check_state(root, rows, 'before')
    except BaseException:
        restore_state(root, after)
        check_state(root, rows, 'after')
        raise
    return transaction


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime', type=Path)
    parser.add_argument('--module', type=Path)
    parser.add_argument('--record', type=Path)
    parser.add_argument('--rollback', type=Path)
    args = parser.parse_args()
    try:
        if args.rollback:
            if any((args.runtime, args.module, args.record)):
                parser.error('--rollback is exclusive')
            rollback(args.rollback)
            print('FIELD_RETURN_TRIAL_ROLLBACK PASS original_bytes=restored candidate_files=removed data_modified=false')
        else:
            if not all((args.runtime, args.module, args.record)):
                parser.error('--runtime, --module and --record are required')
            prepare(args.runtime, args.module, args.record)
            print('FIELD_RETURN_TRIAL PASS default=baseline candidate=Play-stairwell-fix.cmd data_modified=false')
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
