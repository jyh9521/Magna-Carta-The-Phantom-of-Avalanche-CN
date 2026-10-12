"""Build a reversible diagnostic glyph overlay; never starts a game process."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

from resource_font import parse, native_slot


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def slot(character):
    if not isinstance(character, str) or len(character) != 1:
        raise ValueError('probe mapping requires one character')
    encoded = character.encode('cp949')
    family, index, consumed = native_slot(encoded)
    if consumed != len(encoded):
        raise ValueError('character byte length unsupported by native renderer')
    return family, index


def validate_files(root, expected):
    for name, digest in expected.items():
        path = root / name
        if path.is_symlink() or path.is_junction():
            raise ValueError('linked input is not supported')
        if sha(path.read_bytes()) != digest:
            raise ValueError('input hash mismatch: ' + name)


def transform(inputs, mappings):
    """Copy same-sized native glyphs; preserve metrics, headers and every other slot."""
    original = {name: parse(data) for name, data in inputs.items()}
    modified = dict(original)
    changes = []
    seen = set()
    if not mappings:
        raise ValueError('empty probe mapping')
    for mapping in mappings:
        source_family, source_index = slot(mapping['source'])
        target_family, target_index = slot(mapping['target'])
        key = (source_family, source_index)
        if key in seen:
            raise ValueError('duplicate source slot')
        seen.add(key)
        for font_set in (0, 1):
            source_name = f'{source_family}{font_set}.dat'
            target_name = f'{target_family}{font_set}.dat'
            source, target = original[source_name], original[target_name]
            if (source.height, source.pitch, source.width(source_index)) != (
                    target.height, target.pitch, target.width(target_index)):
                raise ValueError('glyph geometry or advance mismatch')
            glyph = target.glyph(target_index)
            if not any(glyph) or glyph == source.glyph(source_index):
                raise ValueError('empty or unchanged diagnostic glyph')
            modified[source_name] = modified[source_name].replace_glyph(source_index, glyph)
            changes.append(dict(file=source_name, slot=source_index,
                                target_file=target_name, target_slot=target_index,
                                offset=100 + len(source.advances) + source_index * source.glyph_bytes,
                                length=source.glyph_bytes))
    return {name: font.to_bytes() for name, font in modified.items()}, changes


def build(source, spec_path, output):
    source = Path(source).resolve(strict=True)
    output = Path(output).resolve()
    if output == source or output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError('source and output must be separate')
    if output.exists():
        raise ValueError('output already exists')
    spec = read_json(spec_path)
    expected_names = {f'{f}{i}.dat' for f in ('Eng', 'Kor', 'Chi') for i in (0, 1)}
    if spec.get('schema') != 1 or set(spec['fonts']) != expected_names:
        raise ValueError('unsupported probe specification')
    validate_files(source / 'Font', spec['fonts'])
    validate_files(source, spec['binaries'])
    inputs = {name: (source / 'Font' / name).read_bytes() for name in sorted(expected_names)}
    outputs, changes = transform(inputs, spec['mappings'])
    # All rejection checks finish before creating output or writing files.
    output.mkdir(parents=True)
    (output / 'Font').mkdir()
    (output / 'original').mkdir()
    changed = {name: sha(data) for name, data in outputs.items() if data != inputs[name]}
    for name in changed:
        (output / 'Font' / name).write_bytes(outputs[name])
        (output / 'original' / name).write_bytes(inputs[name])
    state = dict(schema=1, fonts=spec['fonts'], binaries=spec['binaries'], modified=changed,
                 changes=changes, mappings=spec['mappings'], game_started=False,
                 in_game_display_verified=False, kind='diagnostic_glyph_overlay_not_translation')
    (output / 'probe.json').write_text(json.dumps(state, ensure_ascii=True, indent=2) + '\n', encoding='utf-8')
    validate_files(source / 'Font', spec['fonts'])
    return state


def check_package(package):
    package = Path(package).resolve(strict=True)
    state = read_json(package / 'probe.json')
    if state.get('schema') != 1 or not state['modified']:
        raise ValueError('unsupported probe package')
    for name in (*state['fonts'], *state['modified'], *state['binaries']):
        if Path(name).name != name or '/' in name or '\\' in name:
            raise ValueError('unsafe package filename')
    validate_files(package / 'Font', state['modified'])
    validate_files(package / 'original', {n: state['fonts'][n] for n in state['modified']})
    return package, state


def operate(command, package, workspace):
    package, state = check_package(package)
    workspace = Path(workspace).resolve(strict=True)
    if package == workspace or package.is_relative_to(workspace) or workspace.is_relative_to(package):
        raise ValueError('package and workspace must be separate')
    validate_files(workspace, state['binaries'])
    marker = workspace / '.glyph-probe.json'
    original = state['fonts']
    modified = {**original, **state['modified']}
    if command == 'apply':
        if marker.exists():
            raise ValueError('probe already applied')
        validate_files(workspace / 'Font', original)
    else:
        if read_json(marker) != state:
            raise ValueError('workspace probe marker mismatch')
        validate_files(workspace / 'Font', modified)
    if command in ('apply', 'restore'):
        before = {name: (workspace / 'Font' / name).read_bytes() for name in state['modified']}
        old_marker = marker.read_bytes() if marker.exists() else None
        try:
            folder = 'Font' if command == 'apply' else 'original'
            for name in state['modified']:
                shutil.copyfile(package / folder / name, workspace / 'Font' / name)
            if command == 'apply':
                marker.write_text(json.dumps(state, ensure_ascii=True, indent=2) + '\n', encoding='utf-8')
            else:
                marker.unlink()
            validate_files(workspace / 'Font', original if command == 'restore' else modified)
        except Exception:
            # Recover partial ordinary I/O failure, including a partially copied second font.
            # Power loss or a destination that becomes unwritable requires baseline recovery.
            for name, data in before.items():
                (workspace / 'Font' / name).write_bytes(data)
            if old_marker is None:
                if marker.exists():
                    marker.unlink()
            else:
                marker.write_bytes(old_marker)
            raise
    validate_files(workspace / 'Font', original if command == 'restore' else modified)
    return state


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='command', required=True)
    build_parser = sub.add_parser('build')
    build_parser.add_argument('--source', type=Path, required=True)
    build_parser.add_argument('--spec', type=Path, required=True)
    build_parser.add_argument('--output', type=Path, required=True)
    for name in ('apply', 'verify', 'restore'):
        p = sub.add_parser(name)
        p.add_argument('--package', type=Path, required=True)
        p.add_argument('--workspace', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'build':
        state = build(args.source, args.spec, args.output)
    else:
        state = operate(args.command, args.package, args.workspace)
    print(f'GLYPH_PROBE {args.command.upper()} PASS files={len(state["modified"])} '
          f'slots={len(state["changes"])} game_started=false')


if __name__ == '__main__':
    main()
