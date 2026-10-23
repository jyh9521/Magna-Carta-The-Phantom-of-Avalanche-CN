"""Opt-in shared exception diagnostics; exact rollback, no game execution."""
import argparse
import json
from pathlib import Path

from integrate_native_loading import runtime_lock
from prepare_field_return_trial import (
    ordinary, relative, load_json, digest, validate_manifest, write_file,
    check_state, restore_state, check_digest,
)
from prepare_shared_runtime import check_capture_helper
from update_configuration_runtime import idle

ROOT = Path(__file__).resolve().parents[1]
# Verified git HEAD StartShared.ps1 == retained runtime/Start.ps1 before this update.
BASE_START_SHA = '737f94e930d0d672ecb53eca21fb00bb37954eb3cff78ddc157ecd1b28e08c97'
CHANGES = ('Start.ps1', 'modules/capture_helper.exe', 'Play-diagnostic.cmd', 'runtime.json')
KIND = 'shared_exception_capture_integration'


def independent(root, record):
    if record.is_relative_to(root) or root.is_relative_to(record):
        raise ValueError('Independent transaction record required')


def apply(runtime, helper, record):
    root = ordinary(runtime, directory=True)
    helper = ordinary(helper)
    record = ordinary(record, exists=False)
    independent(root, record)
    if helper.is_relative_to(root) or helper.is_relative_to(record):
        raise ValueError('Independent helper source required')
    native = helper.read_bytes()
    check_capture_helper(native)
    canonical = ordinary(ROOT/'src/configuration/StartShared.ps1')
    entry = ordinary(ROOT/'assets/shared-runtime/Play-diagnostic.cmd')
    script, command = canonical.read_bytes(), entry.read_bytes()
    if b'[switch]$CaptureException' not in script or b'-CaptureException' not in command:
        raise ValueError('Missing explicit capture route')
    with runtime_lock(root):
        idle()
        raw = ordinary(relative(root, 'runtime.json')).read_bytes()
        manifest = load_json(raw)
        validate_manifest(root, manifest)
        if digest(ordinary(relative(root, 'Start.ps1')).read_bytes()) != BASE_START_SHA:
            raise ValueError('Unsupported shared Start.ps1 baseline')
        ordinary(root/'modules', directory=True)
        before = {'runtime.json': raw}
        for name in CHANGES[:-1]:
            path = relative(root, name)
            # Do not silently replace an unrecorded or differently-cased file.
            aliases = [key for key in manifest['files'] if key.casefold() == name.casefold()]
            if aliases and aliases != [name]:
                raise ValueError('Unexpected diagnostic destination case')
            if path.exists() and name not in manifest['files']:
                raise ValueError('Unrecorded diagnostic destination: '+name)
            before[name] = ordinary(path).read_bytes() if path.exists() else None
        after = {'Start.ps1': script, CHANGES[1]: native, CHANGES[2]: command}
        for name, data in after.items():
            manifest['files'][name] = digest(data)
        after['runtime.json'] = (json.dumps(manifest, indent=2)+'\n').encode()
        rows = [dict(path=name, before=digest(before[name]) if before[name] is not None else None,
                     after=digest(after[name])) for name in CHANGES]
        validate_manifest(root, load_json(raw))
        check_state(root, rows, 'before')
        if helper.read_bytes() != native or canonical.read_bytes() != script or entry.read_bytes() != command:
            raise ValueError('Capture integration input drift')
        record.mkdir(parents=True, exist_ok=False)
        for name, data in before.items():
            if data is not None:
                path = record/'original'/name
                path.parent.mkdir(parents=True, exist_ok=True)
                write_file(path, data)
        journal = dict(schema=1, kind=KIND, runtime=str(root), changes=rows,
                       helper_sha256=digest(native), data_modified=False,
                       settings_modified=False, game_started=False)
        write_file(record/'changes.json', (json.dumps(journal, indent=2)+'\n').encode())
        check_state(root, rows, 'before')
        try:
            for name in CHANGES:
                write_file(relative(root, name), after[name])
            check_state(root, rows, 'after')
            validate_manifest(root, load_json((root/'runtime.json').read_bytes()))
        except BaseException:
            restore_state(root, before)
            check_state(root, rows, 'before')
            raise
        return journal


def rollback(record):
    record = ordinary(record, directory=True)
    journal = load_json(ordinary(record/'changes.json').read_bytes())
    if journal.get('schema') != 1 or journal.get('kind') != KIND:
        raise ValueError('Unsupported capture integration record')
    root = ordinary(journal['runtime'], directory=True)
    independent(root, record)
    rows = journal.get('changes')
    if not isinstance(rows, list) or [row.get('path') for row in rows] != list(CHANGES):
        raise ValueError('Unexpected capture rollback file set')
    before = {}
    for row in rows:
        name, expected = row['path'], row['before']
        check_digest(row['after'])
        if expected is None:
            if name in ('Start.ps1', 'runtime.json'):
                raise ValueError('Missing required original capture file')
            before[name] = None
        else:
            check_digest(expected)
            data = ordinary(relative(record/'original', name)).read_bytes()
            if digest(data) != expected:
                raise ValueError('Capture backup drift: '+name)
            before[name] = data
    with runtime_lock(root):
        idle()
        check_state(root, rows, 'after')
        validate_manifest(root, load_json((root/'runtime.json').read_bytes()))
        after = {name: ordinary(relative(root, name)).read_bytes() for name in CHANGES}
        try:
            restore_state(root, before)
            check_state(root, rows, 'before')
            validate_manifest(root, load_json((root/'runtime.json').read_bytes()))
        except BaseException:
            restore_state(root, after)
            check_state(root, rows, 'after')
            raise
        return journal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['apply', 'rollback'])
    parser.add_argument('--runtime', type=Path)
    parser.add_argument('--helper', type=Path)
    parser.add_argument('--record', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'apply':
        if not args.runtime or not args.helper:
            parser.error('apply requires --runtime and --helper')
        apply(args.runtime, args.helper, args.record)
        print('SHARED_CAPTURE_APPLY PASS explicit_entry=true data_modified=false game_started=false')
    else:
        if args.runtime or args.helper:
            parser.error('rollback uses only --record')
        rollback(args.record)
        print('SHARED_CAPTURE_ROLLBACK PASS original_hashes=exact absent_files=restored game_started=false')


if __name__ == '__main__':
    main()
