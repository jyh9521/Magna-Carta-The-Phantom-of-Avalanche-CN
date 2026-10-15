"""Read-only WRD geometry coverage report; no texture/model payload export."""
import argparse
import hashlib
import json
from pathlib import Path
from resource_wrd import parse
from build_map_atlas import project_scene


def audit(source):
    source = source.resolve(strict=True)
    accepted, rejected = [], []
    for path in sorted(source.glob('*.wrd')):
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        item = {'file': path.name, 'source_sha256': digest, 'size': len(data)}
        try:
            result = parse(data)
            meshes, bounds = project_scene(result)
            item.update(version=result['version'], consumed=result['consumed'],
                        vertices=result['vertices'], triangles=result['triangles'], bounds=bounds)
            accepted.append(item)
        except ValueError as error:
            item['reason'] = str(error)
            rejected.append(item)
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Source changed during map audit: '+path.name)
    if not accepted and not rejected:
        raise ValueError('No WRD resources found')
    return {'schema': 1, 'accepted': accepted, 'rejected': rejected,
            'source_unchanged': True, 'navigation_verified': False, 'game_started': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    report = args.report.resolve()
    if report.exists() or report.is_relative_to(source):
        parser.error('Report must be new and outside source data')
    result = audit(source)
    report.parent.mkdir(parents=True, exist_ok=True)
    with report.open('x', encoding='utf8') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(f"MAP_GEOMETRY_AUDIT PASS accepted={len(result['accepted'])} rejected={len(result['rejected'])} source_unchanged=true navigation_verified=false game_started=false")


if __name__ == '__main__':
    main()
