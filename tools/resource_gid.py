"""Bounded read-only GID BSP reader, corroborated with native RVA fb56/11586.

There is no version marker. The supported layout requires an exact EOF,
bounded counts, finite planes and binary node/leaf flags. Polygon fields remain
opaque; parsing does not establish a Field/WRD-to-GID resource binding.
"""
import hashlib
import math
import struct


def parse(data, *, max_nodes=65536, max_depth=512):
    pos = 0

    def take(n):
        nonlocal pos
        if n < 0 or pos+n > len(data):
            raise ValueError(f'Truncated GID at {pos}')
        b = data[pos:pos+n]
        pos += n
        return b

    def uint():
        return struct.unpack('<I', take(4))[0]

    take(1024)  # Opaque native-reserved header.
    sublevels = []
    count = uint()
    if count > 4096:
        raise ValueError('GID sublevel limit')
    for _ in range(count):
        identifier, tag, vertices = struct.unpack('<3I', take(12))
        if vertices > 1000000:
            raise ValueError('GID vertex limit')
        take(vertices*32)
        sublevels.append(dict(identifier=identifier, tag=tag, vertices=vertices))
    native_count = uint()
    nodes = []

    def node(depth):
        if depth > max_depth or len(nodes) >= max_nodes:
            raise ValueError('GID node/depth limit')
        index = len(nodes)
        flag = uint()
        if flag not in (0, 1):
            raise ValueError('Unsupported GID node flag')
        row = dict(index=index, leaf=bool(flag), depth=depth)
        nodes.append(row)
        if flag:
            row['solid'] = uint()
            if row['solid'] not in (0, 1):
                raise ValueError('Unsupported GID leaf flag')
        else:
            row['polygon_hex'] = take(22).hex()
            plane = struct.unpack('<4f', take(16))
            if not all(math.isfinite(v) for v in plane):
                raise ValueError('Nonfinite GID plane')
            row['plane'] = list(plane)
            coplanar = uint()
            if coplanar > max_nodes:
                raise ValueError('GID coplanar limit')
            row['coplanar_count'] = coplanar
            take(coplanar*22)
            row['front'] = node(depth+1)
            row['back'] = node(depth+1)
        return index

    root = node(0)
    if native_count != len(nodes):
        raise ValueError('GID native node count mismatch')
    if pos != len(data):
        raise ValueError(f'GID trailing bytes: {len(data)-pos}')
    return dict(schema=1, source_sha256=hashlib.sha256(data).hexdigest(), size=len(data),
        consumed=pos, native_count=native_count, sublevels=sublevels, root=root, nodes=nodes,
        exact_eof=True, resource_binding_verified=False)
