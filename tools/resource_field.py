"""Read the supported native Field static prefix, never interpreting script tails."""
import argparse
import hashlib
import json
import math
import struct
from pathlib import Path

ENGINE_SHA256 = '5c701de93af6267b959c49e6927bee525bc0f3c68c8c6f51413515d13809d427'
ENGINE_SHA256S = frozenset([ENGINE_SHA256, '7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e'])


class Reader:
    def __init__(self, data):
        self.data, self.pos = data, 0

    def take(self, size):
        if size < 0 or self.pos+size > len(self.data):
            raise ValueError(f'Truncated Field at {self.pos}: need {size} bytes')
        value = memoryview(self.data)[self.pos:self.pos+size]
        self.pos += size
        return value

    def count(self, limit=65536):
        value = struct.unpack('<I', self.take(4))[0]
        if value > limit:
            raise ValueError(f'Field count exceeds limit at {self.pos-4}')
        return value


def position(record, offset):
    value = struct.unpack_from('<3f', record, offset)
    if not all(math.isfinite(x) and abs(x) < 1e8 for x in value):
        raise ValueError('Invalid Field coordinate')
    return value


def parse(data):
    r = Reader(data)
    header = r.take(1060)
    map_id = struct.unpack_from('<i', header, 0)[0]
    playbook_id = struct.unpack_from('<i', header, 8)[0]
    waves = struct.unpack_from('<I', header, 244)[0]
    if waves > 65536:
        raise ValueError('Field wave count exceeds limit')
    lights = r.count()
    r.take(lights*76)
    actors = []
    for _ in range(r.count()):
        row = r.take(52)
        actors.append({'resource_id': struct.unpack_from('<i', row, 4)[0], 'position': position(row, 8)})
    objects = []
    for _ in range(r.count()):
        row = r.take(56)
        objects.append({'resource_id': struct.unpack_from('<i', row, 4)[0],
                        'kind': struct.unpack_from('<I', row, 8)[0], 'position': position(row, 12)})
    cameras = r.count()
    r.take(cameras*124)
    regions = []
    for _ in range(r.count()):
        row = r.take(112)
        corners = [position(row, 16+i*12) for i in range(8)]
        regions.append({'id': struct.unpack_from('<i', row, 12)[0], 'center': position(row, 0),
                        'corners': corners})
    event_cameras = r.count()
    for _ in range(event_cameras):
        row = r.take(20)
        samples = struct.unpack_from('<I', row, 16)[0]
        if not 1 <= samples <= 100000:
            raise ValueError('Unsupported Field event camera sample count')
        r.take((samples+1)*76)
    for _ in range(waves):
        r.take(4)  # Opaque identifier.
        points, samples = r.count(), r.count(100000)
        r.take(points*samples*36+192)
    return {'schema': 1, 'format': 'native_field_static_prefix', 'source_sha256': hashlib.sha256(data).hexdigest(),
            'size': len(data), 'map_resource_id': map_id, 'playbook_id': playbook_id,
            'lights': lights, 'actors': actors, 'objects': objects, 'cameras': cameras,
            'region_volumes': regions, 'event_cameras': event_cameras, 'waves': waves,
            'parsed_bytes': r.pos, 'remaining_opaque_bytes': len(data)-r.pos,
            'full_file_parsed': False, 'navigation_verified': False}


def audit(source, maps, engine):
    engine_before = hashlib.sha256(engine.read_bytes()).hexdigest()
    if engine_before not in ENGINE_SHA256S:
        raise ValueError('Unsupported Field loader image')
    map_ids = {int(p.stem) for p in maps.glob('*.wrd') if p.stem.isdigit()}
    accepted, rejected = [], []
    for path in sorted(source.glob('*.fld')):
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        item = {'file': path.name, 'source_sha256': digest, 'size': len(data)}
        try:
            value = parse(data)
            kinds = {}
            for obj in value['objects']:
                key = str(obj['kind']); kinds[key] = kinds.get(key, 0)+1
            item.update(map_resource_id=value['map_resource_id'], map_file_exists=value['map_resource_id'] in map_ids,
                        playbook_id=value['playbook_id'], actors=len(value['actors']), objects=len(value['objects']),
                        object_kind_counts=kinds, region_volumes=len(value['region_volumes']),
                        event_cameras=value['event_cameras'], parsed_bytes=value['parsed_bytes'],
                        remaining_opaque_bytes=value['remaining_opaque_bytes'], full_file_parsed=False)
            accepted.append(item)
        except ValueError as error:
            item['reason'] = str(error); rejected.append(item)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Field source changed during audit')
    if not accepted and not rejected:
        raise ValueError('No Field resources found')
    if hashlib.sha256(engine.read_bytes()).hexdigest() != engine_before:
        raise ValueError('Field loader image changed during audit')
    return {'schema': 1, 'loader_sha256': engine_before, 'accepted_prefixes': accepted, 'rejected': rejected,
            'full_file_parsed': False, 'source_unchanged': True, 'navigation_verified': False, 'game_started': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['source', 'maps', 'engine', 'report']:
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    source, maps, engine, report = args.source.resolve(strict=True), args.maps.resolve(strict=True), args.engine.resolve(strict=True), args.report.resolve()
    if report.exists() or report.is_relative_to(source) or report.is_relative_to(maps) or report == engine:
        parser.error('Report must be new and outside source data')
    result = audit(source, maps, engine)
    report.parent.mkdir(parents=True, exist_ok=True)
    with report.open('x', encoding='utf8') as stream:
        json.dump(result, stream, indent=2); stream.write('\n')
    print(f"FIELD_PREFIX_AUDIT PASS accepted={len(result['accepted_prefixes'])} rejected={len(result['rejected'])} full_file_parsed=false navigation_verified=false source_unchanged=true game_started=false")


if __name__ == '__main__':
    main()
