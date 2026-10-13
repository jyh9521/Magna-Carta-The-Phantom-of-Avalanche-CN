"""Rewrite only explicitly source-locked, verified fixed display-label slots."""
import argparse
import json
from pathlib import Path
from native_text_codec import encode, decode, validate
from locale_package import sha, located


def patch(raw, row, mapping):
    validate(mapping)
    start, capacity = row['offset'], row['capacity']
    expected = bytes.fromhex(row['expected_hex'])
    if (type(start) is not int or type(capacity) is not int or start < 0 or capacity < 1
            or start+capacity > len(raw) or len(expected) != capacity
            or sha(raw) != row['source_sha256'] or raw[start:start+capacity] != expected):
        raise ValueError('field label source identity/slot mismatch')
    if expected.split(b'\0',1)[0].decode('cp949') != row['source']:
        raise ValueError('field label source text mismatch')
    target = encode(row['target'], mapping)
    if len(target) >= capacity or b'\0' in target or decode(target,mapping) != row['target']:
        raise ValueError('field label capacity/encoding mismatch')
    # Never clear unknown padding beyond the original/target string union.
    old_end = expected.find(b'\0')
    if old_end < 0 or any(expected[old_end+1:len(target)+1]):
        raise ValueError('field label would overwrite unknown tail data')
    span = max(old_end+1, len(target)+1)
    return raw[:start]+target+bytes(span-len(target))+raw[start+span:]


def build(source, plans, font_package, output):
    source=Path(source).resolve(strict=True); plans=Path(plans).resolve(strict=True)
    font_package=Path(font_package).resolve(strict=True); output=Path(output).resolve()
    if output.exists() or output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError('field output must be new and independent')
    plan_raw=plans.read_bytes(); map_raw=(font_package/'overlay.json').read_bytes()
    data=json.loads(plan_raw); mapping=json.loads(map_raw)['mapping']
    if data.get('schema')!=1 or not data.get('evidence'):raise ValueError('unverified field plan')
    snapshots={plans:plan_raw,font_package/'overlay.json':map_raw}; results={}; rows=[]
    for row in data['resources']:
        name=row['resource']
        if name in results:raise ValueError('duplicate field identity')
        p=located(source,name); raw=p.read_bytes(); snapshots[p]=raw
        changed=patch(raw,row,mapping);results[name]=changed
        rows.append(dict(resource=name,source_sha256=sha(raw),modified_sha256=sha(changed),
                         target=row['target'],offset=row['offset'],capacity=row['capacity']))
    if any(p.read_bytes()!=b for p,b in snapshots.items()):raise ValueError('field source drift')
    output.mkdir(parents=True)
    for name,raw in results.items():
        p=output/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
        if p.read_bytes()!=raw:raise ValueError('field readback mismatch')
    manifest=dict(schema=1,resources=rows,source_unchanged=True,game_started=False,deployed=False)
    (output/'build.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for key in ('source','plans','font-package','output'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();r=build(a.source,a.plans,a.font_package,a.output)
    print(f'FIELD_LABEL_BUILD PASS resources={len(r["resources"])} game_started=false')
