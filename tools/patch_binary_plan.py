"""Apply/reverse an exact version-locked equal-size binary plan; no execution."""
import argparse, hashlib, json
from pathlib import Path

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def transform(raw, plan, reverse=False):
    if plan.get('schema') != 1 or len(raw) != plan['source_size']:
        raise ValueError('unsupported plan or file size')
    key = 'target_sha256' if reverse else 'source_sha256'
    if digest(raw) != plan[key]:
        raise ValueError('unsupported binary identity')
    out = bytearray(raw)
    previous_end = 0
    for row in plan['changes']:
        offset = row['offset']
        before = bytes.fromhex(row['replacement_hex'] if reverse else row['expected_hex'])
        after = bytes.fromhex(row['expected_hex'] if reverse else row['replacement_hex'])
        if (type(offset) is not int or offset < previous_end or not before
                or len(before) != len(after) or offset + len(before) > len(raw)):
            raise ValueError('invalid or overlapping patch range')
        if raw[offset:offset+len(before)] != before:
            raise ValueError('expected bytes mismatch')
        out[offset:offset+len(before)] = after
        previous_end = offset + len(before)
    result = bytes(out)
    if digest(result) != plan['source_sha256' if reverse else 'target_sha256']:
        raise ValueError('rebuilt binary identity mismatch')
    return result

def apply(source, output, plan):
    source = Path(source).resolve(strict=True)
    output = Path(output).resolve()
    if output.exists() or source == output:
        raise ValueError('output must be a new independent file')
    raw = source.read_bytes()
    after = transform(raw, plan)
    if source.read_bytes() != raw:
        raise ValueError('source drift before publication')
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('xb') as f:
        f.write(after)
    if output.read_bytes() != after or source.read_bytes() != raw:
        raise ValueError('source/output readback mismatch')

def rollback(target, plan):
    target = Path(target)
    if target.is_symlink():
        raise ValueError('rollback target must not be a link')
    raw = target.read_bytes()
    after = transform(raw, plan, True)
    if target.read_bytes() != raw:
        raise ValueError('target drift before rollback')
    target.write_bytes(after)
    if target.read_bytes() != after:
        raise ValueError('rollback readback mismatch')

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['apply', 'verify', 'rollback'])
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--source', type=Path)
    p.add_argument('--output', type=Path)
    p.add_argument('--target', type=Path)
    a = p.parse_args()
    plan = json.loads(a.plan.read_text(encoding='utf8'))
    if a.action == 'apply':
        apply(a.source, a.output, plan)
    elif a.action == 'rollback':
        rollback(a.target, plan)
    else:
        transform(a.source.read_bytes(), plan)
    print('BINARY_PLAN_' + a.action.upper() + ' PASS game_started=false')
