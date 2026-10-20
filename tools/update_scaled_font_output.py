"""Update only the scaled-font module, launcher and manifest; retain the previous candidate for rollback."""
import argparse
import json
from pathlib import Path
from integrate_native_loading import runtime_lock
from prepare_field_return_trial import ordinary,load_json,validate_manifest,digest,write_file,check_state,restore_state
from update_configuration_runtime import idle

CHANGES=('modules/scaled-font.dll','modules/workspace_launcher.exe','runtime.json')
BASE_MODULE='72fec1871adf471141e3315a0320935bd34d7eface02448d9691f5021b7c85c5'


def update(runtime,native,record):
    idle()
    with runtime_lock(runtime):
        root=ordinary(runtime,directory=True);native=ordinary(native,directory=True);record=ordinary(record,exists=False)
        if record.is_relative_to(root) or native.is_relative_to(root):raise ValueError('External inputs and record required')
        raw=(root/'runtime.json').read_bytes();m=load_json(raw);validate_manifest(root,m)
        if (m.get('scaled_font')!=dict(schema=1,enabled=True,module='scaled-font',scale=4)
                or 'scaled_font_output' in m or m['files'].get(CHANGES[0])!=BASE_MODULE):raise ValueError('Expected original C candidate baseline')
        after={CHANGES[0]:ordinary(native/'workspace_profile.dll').read_bytes(),CHANGES[1]:ordinary(native/'workspace_launcher.exe').read_bytes()}
        if ('launcher_output_snapshot'.encode('utf-16le') not in after[CHANGES[0]]
                or b'SCALED_FONT_OUTPUT' not in after[CHANGES[1]]):raise ValueError('Missing output snapshot implementation')
        before={p:ordinary(root/p).read_bytes() for p in CHANGES}
        for p,b in after.items():m['files'][p]=digest(b)
        m['scaled_font_output']=dict(schema=1,source='launcher_display_snapshot')
        after['runtime.json']=(json.dumps(m,indent=2)+'\n').encode('utf8')
        rows=[dict(path=p,before=digest(before[p]),after=digest(after[p])) for p in CHANGES]
        check_state(root,rows,'before');record.mkdir(parents=True)
        for p,b in before.items():
            target=record/'original'/p;target.parent.mkdir(parents=True,exist_ok=True);write_file(target,b)
        j=dict(schema=1,kind='scaled_font_output_update',runtime=str(root),changes=rows,in_game_verified=False)
        write_file(record/'changes.json',(json.dumps(j,indent=2)+'\n').encode())
        try:
            for p in CHANGES:write_file(root/p,after[p])
            check_state(root,rows,'after')
        except BaseException:
            restore_state(root,before);check_state(root,rows,'before');raise
        return j


def rollback(record):
    idle();record=ordinary(record,directory=True);j=load_json(ordinary(record/'changes.json').read_bytes())
    if j.get('schema')!=1 or j.get('kind')!='scaled_font_output_update':raise ValueError('Unknown output update record')
    with runtime_lock(j['runtime']):
        root=ordinary(j['runtime'],directory=True);rows=j['changes']
        if record.is_relative_to(root) or [r['path'] for r in rows]!=list(CHANGES):raise ValueError('Unexpected rollback paths')
        before={}
        for row in rows:
            b=ordinary(record/'original'/row['path']).read_bytes()
            if digest(b)!=row['before']:raise ValueError('Backup drift')
            before[row['path']]=b
        check_state(root,rows,'after');validate_manifest(root,load_json((root/'runtime.json').read_bytes()))
        after={p:(root/p).read_bytes() for p in CHANGES}
        try:restore_state(root,before);check_state(root,rows,'before')
        except BaseException:restore_state(root,after);check_state(root,rows,'after');raise
        return j


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('runtime','native','record','rollback'):p.add_argument('--'+n,type=Path)
    a=p.parse_args()
    try:
        if a.rollback:
            if any((a.runtime,a.native,a.record)):p.error('--rollback is exclusive')
            rollback(a.rollback);print('OUTPUT_UPDATE_ROLLBACK PASS previous_candidate=exact data_modified=false')
        else:
            if not all((a.runtime,a.native,a.record)):p.error('--runtime --native --record required')
            update(a.runtime,a.native,a.record);print('OUTPUT_UPDATE PASS entry=Play.cmd policy=launcher_snapshot data_modified=false game_started=false')
    except (OSError,ValueError,KeyError,TypeError) as e:p.error(str(e))


if __name__=='__main__':main()
