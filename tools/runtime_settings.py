"""Prepare a graphics setting candidate without writing the registry."""
import argparse
import hashlib
from pathlib import Path

RENDERERS = {'direct3d': 0, 'opengl': 1}


def renderer(data):
    if len(data) != 52 or data[1] not in RENDERERS.values():
        raise ValueError('Unsupported MCSetting layout or renderer')
    return next(name for name, value in RENDERERS.items() if value == data[1])


def convert(data, target):
    renderer(data)
    if target not in RENDERERS:
        raise ValueError('Unsupported renderer')
    result = bytearray(data)
    result[1] = RENDERERS[target]
    return bytes(result)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--source', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--renderer', choices=RENDERERS, required=True)
    a = p.parse_args()
    if a.output.resolve() == a.source.resolve() or a.output.exists():
        raise ValueError('Output must be a new file')
    data = a.source.read_bytes()
    output = convert(data, a.renderer)
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_bytes(output)
    print(f'PROFILE_CANDIDATE PASS renderer={renderer(output)} changed_bytes={sum(x != y for x, y in zip(data, output))} registry_written=false sha256={hashlib.sha256(output).hexdigest()}')
