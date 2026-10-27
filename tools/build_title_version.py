"""Compile locale-owned title labels for the existing native ASCII font path."""
import argparse
import json
from pathlib import Path


def labels(path):
    data = json.loads(Path(path).read_text(encoding='utf8'))
    if set(data) != {'schema', 'original_prefix', 'patch_line'} or type(data['schema']) is not int or data['schema'] != 1:
        raise ValueError('Unsupported title version catalog')
    for name, limit in (('original_prefix', 24), ('patch_line', 80)):
        value = data[name]
        if not isinstance(value, str) or not 1 <= len(value) <= limit or any(not 32 <= ord(c) <= 126 for c in value):
            raise ValueError('Native title label must be bounded printable ASCII: ' + name)
    return data


def build(catalog, output):
    data = labels(catalog)
    text = '// Generated from the selected locale catalog.\n#pragma once\n'
    for name, key in (('titleOriginalPrefix', 'original_prefix'), ('titlePatchLine', 'patch_line')):
        text += 'constexpr char ' + name + '[] = ' + json.dumps(data[key]) + ';\n'
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding='utf8')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--catalog', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    build(**vars(p.parse_args()))
