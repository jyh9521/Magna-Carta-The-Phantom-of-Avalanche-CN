"""Integrate the scoped height fix into existing entries; retain original role DLLs."""
import argparse
import json
from pathlib import Path
from prepare_field_return_trial import (ordinary, relative, validate_manifest, load_json,
                                       digest, write_file, check_state, restore_state)

ROOT=Path(__file__).resolve().parents[1]
BASE_START_SHA='8400d8fed441504b2007bab3d6f7e1507d6e3b00a9244410c74a66c541d5cc4a'
CHANGES=('Start.ps1','runtime.json','modules/field-return-height.dll')


def integrate(runtime,module,record):
    root=ordinary(runtime,directory=True);module=ordinary(module);record=ordinary(record,exists=False)
    if module.is_relative_to(root) or record.is_relative_to(root):raise ValueError('External module and record required')
    raw=(root/'runtime.json').read_bytes();manifest=load_json(raw);validate_manifest(root,manifest)
    start=(root/'Start.ps1').read_bytes()
    if (digest(start)!=BASE_START_SHA or 'field_return_height_module' in manifest
            or 'field_return_height' in manifest or (root/'Play-stairwell-fix.cmd').exists()):
        raise ValueError('Restore the recorded pre-trial baseline before integrating')
    dest=relative(root,CHANGES[2]);ordinary(dest,exists=False)
    canonical=ordinary(ROOT/'src/configuration/StartShared.ps1');script=canonical.read_bytes()
    if b'# FIELD_RETURN_DEFAULT_ROUTE:' not in script:raise ValueError('Missing default route implementation')
    native=module.read_bytes()
    before={'Start.ps1':start,'runtime.json':raw,CHANGES[2]:None}
    after={'Start.ps1':script,CHANGES[2]:native}
    manifest['field_return_height']=dict(schema=1,enabled=True,module='field-return-height')
    for name,data in after.items():manifest['files'][name]=digest(data)
    after['runtime.json']=(json.dumps(manifest,indent=2)+'\n').encode('utf8')
    rows=[dict(path=name,before=digest(before[name]) if before[name] is not None else None,
               after=digest(after[name])) for name in CHANGES]
    validate_manifest(root,load_json(raw));check_state(root,rows,'before')
    if module.read_bytes()!=native or canonical.read_bytes()!=script:raise ValueError('Integration input drift')
    record.mkdir(parents=True)
    for name,data in before.items():
        if data is not None:
            p=record/'original'/name;p.parent.mkdir(parents=True,exist_ok=True);write_file(p,data)
    journal=dict(schema=1,kind='field_return_default_integration',runtime=str(root),changes=rows,
                 original_modules_preserved=True,data_modified=False)
    write_file(record/'changes.json',(json.dumps(journal,indent=2)+'\n').encode())
    try:
        for name in (CHANGES[2],'Start.ps1','runtime.json'):write_file(root/name,after[name])
        check_state(root,rows,'after')
    except BaseException:
        restore_state(root,before);check_state(root,rows,'before');raise
    return journal


def rollback(record):
    record=ordinary(record,directory=True);j=load_json(ordinary(record/'changes.json').read_bytes())
    if j.get('schema')!=1 or j.get('kind')!='field_return_default_integration':raise ValueError('Unknown integration record')
    root=ordinary(j['runtime'],directory=True);rows=j['changes']
    if record.is_relative_to(root) or [r['path'] for r in rows]!=list(CHANGES):raise ValueError('Unexpected integration paths')
    before={}
    for row in rows:
        name=row['path'];expected=row['before']
        if name==CHANGES[2]:
            if expected is not None:raise ValueError('Unexpected existing candidate')
            before[name]=None
        else:
            b=ordinary(record/'original'/name).read_bytes()
            if digest(b)!=expected:raise ValueError('Backup drift: '+name)
            before[name]=b
    check_state(root,rows,'after');validate_manifest(root,load_json((root/'runtime.json').read_bytes()))
    after={name:(root/name).read_bytes() for name in CHANGES}
    try:
        restore_state(root,before);check_state(root,rows,'before')
    except BaseException:
        restore_state(root,after);check_state(root,rows,'after');raise
    return j


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['runtime','module','record','rollback']:p.add_argument('--'+name,type=Path)
    a=p.parse_args()
    try:
        if a.rollback:
            if any([a.runtime,a.module,a.record]):p.error('--rollback is exclusive')
            rollback(a.rollback);print('FIELD_RETURN_INTEGRATION_ROLLBACK PASS original_entry=restored original_modules=unchanged saves=preserved')
        else:
            if not all([a.runtime,a.module,a.record]):p.error('--runtime --module --record required')
            integrate(a.runtime,a.module,a.record);print('FIELD_RETURN_INTEGRATION PASS Play.cmd=enabled baseline=original separate_entry=false data_modified=false')
    except (OSError,ValueError,KeyError,TypeError) as e:p.error(str(e))


if __name__=='__main__':main()
