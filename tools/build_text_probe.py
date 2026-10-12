"""Build and manage one version-locked SGI text probe without launching the game."""
import argparse
import json
from pathlib import Path, PurePosixPath
import shutil

from build_glyph_probe import sha, read_json, validate_files
from resource_font import parse as parse_font, coverage
from resource_sgi import parse


def relative(value):
    p = PurePosixPath(value)
    if p.is_absolute() or not p.parts or any(x in ('.', '..') for x in p.parts) or '\\' in value or ':' in value:
        raise ValueError('unsafe relative resource path')
    return Path(*p.parts)


def guards(workspace, state):
    expected_fonts = {f'{family}{i}.dat' for family in ('Eng', 'Kor', 'Chi') for i in (0, 1)}
    if set(state['fonts']) != expected_fonts or not {'MCAlpha.dll', 'MagnaCarta.exe'} <= set(state['binaries']):
        raise ValueError('incomplete runtime or font guards')
    if any(Path(name).name != name or '/' in name or '\\' in name for name in state['binaries']):
        raise ValueError('unsafe binary filename')
    validate_files(workspace, state['binaries'])
    validate_files(workspace / 'Font', state['fonts'])


def build(source, spec_path, output):
    source = Path(source).resolve(strict=True)
    output = Path(output).resolve()
    if output == source or output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError('source and output must be separate')
    if output.exists():
        raise ValueError('output already exists')
    spec = read_json(spec_path)
    if spec.get('schema') != 1 or spec.get('format') != 'sgi':
        raise ValueError('unsupported text probe schema')
    resource = relative(spec['resource'])
    guards(source, spec)
    path = source / resource
    if path.is_symlink() or not path.resolve(strict=True).is_relative_to(source):
        raise ValueError('linked resource is not supported')
    original = path.read_bytes()
    if sha(original) != spec['original_sha256']:
        raise ValueError('resource hash mismatch')
    if len(original) != spec['original_size']:
        raise ValueError('resource size mismatch')
    target = spec['target'].encode('cp949')
    for font_set in (0, 1):
        fonts = {family: parse_font((source / 'Font' / f'{family}{font_set}.dat').read_bytes())
                 for family in ('Eng', 'Kor', 'Chi')}
        if any(row['status'] != 'supported' for row in coverage(spec['target'], fonts)):
            raise ValueError('target lacks native glyph coverage')
    table = parse(original)
    modified = table.replace_name(spec['ordinal'], spec['identifier'], bytes.fromhex(spec['expected_hex']), target).to_bytes()
    if original == modified:
        raise ValueError('probe produces no change')
    state = {**spec, 'modified_sha256': sha(modified), 'game_started': False,
             'in_game_display_verified': False, 'kind': 'diagnostic_text_not_final_translation'}
    output.mkdir(parents=True)
    (output / 'original.sgi').write_bytes(original)
    (output / 'modified.sgi').write_bytes(modified)
    (output / 'probe.json').write_text(json.dumps(state, ensure_ascii=True, indent=2) + '\n', encoding='utf-8')
    guards(source, state)
    if path.read_bytes() != original:
        raise ValueError('source changed during build')
    return state


def operate(command, package, workspace):
    package = Path(package).resolve(strict=True)
    workspace = Path(workspace).resolve(strict=True)
    if package == workspace or package.is_relative_to(workspace) or workspace.is_relative_to(package):
        raise ValueError('package and workspace must be separate')
    state = read_json(package / 'probe.json')
    if state.get('schema') != 1 or state.get('format') != 'sgi':
        raise ValueError('unsupported text probe package')
    path = workspace / relative(state['resource'])
    if path.is_symlink() or not path.resolve(strict=True).is_relative_to(workspace):
        raise ValueError('linked resource is not supported')
    guards(workspace, state)
    original = (package / 'original.sgi').read_bytes()
    modified = (package / 'modified.sgi').read_bytes()
    if sha(original) != state['original_sha256'] or sha(modified) != state['modified_sha256']:
        raise ValueError('package hash mismatch')
    expected = parse(original).replace_name(state['ordinal'], state['identifier'],
                                          bytes.fromhex(state['expected_hex']), state['target'].encode('cp949')).to_bytes()
    if modified != expected:
        raise ValueError('package modifies unexpected resource bytes')
    marker = workspace / '.text-probe.json'
    before = path.read_bytes()
    if command == 'apply':
        if marker.exists() or before != original:
            raise ValueError('workspace resource changed or probe already applied')
    else:
        if read_json(marker) != state or before != modified:
            raise ValueError('workspace probe drift')
    if command in ('apply', 'restore'):
        old_marker = marker.read_bytes() if marker.exists() else None
        try:
            shutil.copyfile(package / ('modified.sgi' if command == 'apply' else 'original.sgi'), path)
            if command == 'apply':
                marker.write_text(json.dumps(state, ensure_ascii=True, indent=2) + '\n', encoding='utf-8')
            else:
                marker.unlink()
            if path.read_bytes() != (modified if command == 'apply' else original):
                raise ValueError('resource write verification mismatch')
        except Exception:
            path.write_bytes(before)
            if old_marker is None:
                if marker.exists():
                    marker.unlink()
            else:
                marker.write_bytes(old_marker)
            raise
    return state


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('build')
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--spec', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    for name in ('apply', 'verify', 'restore'):
        p = sub.add_parser(name)
        p.add_argument('--package', type=Path, required=True)
        p.add_argument('--workspace', type=Path, required=True)
    args = parser.parse_args()
    state = build(args.source, args.spec, args.output) if args.command == 'build' else operate(args.command, args.package, args.workspace)
    print(f'TEXT_PROBE {args.command.upper()} PASS records=1 identifier={state["identifier"]} game_started=false')


if __name__ == '__main__':
    main()
