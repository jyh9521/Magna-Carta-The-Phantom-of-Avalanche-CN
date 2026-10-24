"""Bounded EFS sections and original event commands; no opcode normalization."""
import hashlib
import struct
from resource_field_script import parse_script_tail


def parse(data):
    pos = 0
    sections = []
    for index in range(7):
        if pos + 8 > len(data):
            raise ValueError('Truncated effect section header')
        count, version = struct.unpack_from('<2i', data, pos)
        pos += 8
        stride = 28 if index == 6 else 8
        if not 0 <= count <= 4096 or pos + count * stride > len(data):
            raise ValueError('Invalid effect section count')
        rows = [list(struct.unpack_from('<'+'i'*(stride//4), data, pos+i*stride))
                for i in range(count)]
        sections.append(dict(index=index, version=version, rows=rows))
        pos += count * stride
    tail = parse_script_tail(data, pos)
    return dict(sections=sections, events=tail['events'], exact_eof=tail['exact_eof'],
                sha256=hashlib.sha256(data).hexdigest())
