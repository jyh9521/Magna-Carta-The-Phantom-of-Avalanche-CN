"""Update owned shared-runtime modules as one reversible, hash-checked transaction.

No game process, configuration UI, or game entry point is executed.
"""
import argparse
import json
import struct
from pathlib import Path

from integrate_native_loading import runtime_lock
from prepare_field_return_trial import (
    ordinary, relative, load_json, digest, validate_manifest,
    write_file, check_state, restore_state,
)
from update_configuration_runtime import idle

MODULES = tuple('modules/' + name + '.dll' for name in (
    'display', 'modern', 'texture', 'camera', 'maps', 'input-diagnostics',
    'motion-space', 'configuration', 'field-return-height', 'gui-parent-guard',
    'native-loading', 'scaled-font',
))
CHANGES = (*MODULES, 'runtime.json')


def check_module(data):
    if len(data) < 256 or data[:2] != b'MZ':
        raise ValueError('Expected owned Win32 DLL')
    offset = struct.unpack_from('<I', data, 0x3c)[0]
    if offset < 64 or offset + 26 > len(data):
        raise ValueError('Invalid PE header')
    if (data[offset:offset+4] != b'PE\0\0'
            or struct.unpack_from('<H', data, offset+4)[0] != 0x14c
            or not struct.unpack_from('<H', data, offset+22)[0] & 0x2000
            or struct.unpack_from('<H', data, offset+24)[0] != 0x10b):
        raise ValueError('Expected PE32 x86 DLL')


def apply(runtime, module, record):
    root = ordinary(runtime, directory=True)
    module = ordinary(module)
    record = ordinary(record, exists=False)
    if (module.is_relative_to(root) or record.is_relative_to(root)
            or module.is_relative_to(record) or root.is_relative_to(record)):
        raise ValueError('Independent module and transaction record required')
    native = module.read_bytes()
    check_module(native)
    with runtime_lock(root):
        idle()
        raw = ordinary(root/'runtime.json').read_bytes()
        manifest = load_json(raw)
        validate_manifest(root, manifest)
        if any(name not in manifest['files'] for name in MODULES):
            raise ValueError('Expected complete shared-runtime module set')
        before = {name: ordinary(relative(root, name)).read_bytes() for name in MODULES}
        before['runtime.json'] = raw
        after = {name: native for name in MODULES}
        for name in MODULES:
            manifest['files'][name] = digest(native)
        after['runtime.json'] = (json.dumps(manifest, indent=2)+'\n').encode()
        rows = [dict(path=name, before=digest(before[name]), after=digest(after[name]))
                for name in CHANGES]
        record.mkdir(parents=True)
        for name, data in before.items():
            path = record/'original'/name
            path.parent.mkdir(parents=True, exist_ok=True)
            write_file(path, data)
        journal = dict(schema=1, kind='owned_runtime_module_update', runtime=str(root),
                       module_sha256=digest(native), changes=rows,
                       data_modified=False, settings_modified=False, game_started=False)
        write_file(record/'changes.json', (json.dumps(journal, indent=2)+'\n').encode())
        check_state(root, rows, 'before')
        try:
            for name in CHANGES:
                write_file(root/name, after[name])
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
    if journal.get('schema') != 1 or journal.get('kind') != 'owned_runtime_module_update':
        raise ValueError('Unsupported module update record')
    root = ordinary(journal['runtime'], directory=True)
    if record.is_relative_to(root) or root.is_relative_to(record):
        raise ValueError('Independent transaction record required')
    rows = journal['changes']
    if [row['path'] for row in rows] != list(CHANGES):
        raise ValueError('Unexpected rollback file set')
    before = {}
    for row in rows:
        data = ordinary(relative(record/'original', row['path'])).read_bytes()
        if digest(data) != row['before']:
            raise ValueError('Backup changed: '+row['path'])
        before[row['path']] = data
    with runtime_lock(root):
        idle()
        check_state(root, rows, 'after')
        validate_manifest(root, load_json((root/'runtime.json').read_bytes()))
        after = {name: (root/name).read_bytes() for name in CHANGES}
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
    parser.add_argument('--module', type=Path)
    parser.add_argument('--record', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'apply':
        if not args.runtime or not args.module:
            parser.error('apply requires --runtime and --module')
        apply(args.runtime, args.module, args.record)
        print('RUNTIME_MODULE_UPDATE PASS modules=12 manifest=verified settings=preserved data=unchanged game_started=false')
    else:
        if args.runtime or args.module:
            parser.error('rollback uses only --record')
        rollback(args.record)
        print('RUNTIME_MODULE_ROLLBACK PASS modules=12 original_hashes=exact settings=preserved data=unchanged game_started=false')


if __name__ == '__main__':
    main()
