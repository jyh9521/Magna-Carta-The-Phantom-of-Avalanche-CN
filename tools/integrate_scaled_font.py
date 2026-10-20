"""Install the approved scaled coverage in the existing shared runtime, without game execution."""
import argparse
import json
from pathlib import Path

from integrate_native_loading import runtime_lock
from prepare_field_return_trial import (ordinary, relative, load_json, digest,
                                       write_file, validate_manifest, check_state, restore_state)

ROOT=Path(__file__).resolve().parents[1]
BASE_START_SHA='7cfac6837c19ec4afc951b10cb952c33ee8bfce1fa9bb85f7d2b85350c01d9bc'
ADDED=('modules/scaled-font.dll','fonts/candidate-14.sgc','fonts/candidate-22.sgc','fonts/FONT-LICENSE.txt')
CHANGES=('Start.ps1','runtime.json',*ADDED)


def payload(cache):
    cache=ordinary(cache,directory=True)
    m=load_json(ordinary(cache/'manifest.json').read_bytes())
    if (type(m.get('schema')) is not int or m['schema']!=1 or type(m.get('scale')) is not int or m['scale']!=4
            or type(m.get('glyphs')) is not int or not 1<=m['glyphs']<=4096):
        raise ValueError('Unsupported scaled coverage')
    files={}
    import struct
    ids=[]
    for h in (14,22):
        name=f'candidate-{h}.sgc';b=ordinary(cache/name).read_bytes()
        if digest(b)!=m['files'][name] or len(b)<20 or len(b)>32*1024*1024:
            raise ValueError('Coverage hash drift')
        magic,version,height,scale,n=struct.unpack_from('<4sIIII',b)
        if (magic,version,height,scale,n)!=(b'SGC1',1,h,4,m['glyphs']) or len(b)!=20+2*n+n*(h*4)**2:
            raise ValueError('Coverage dimensions')
        pairs=struct.unpack_from('<'+str(n)+'H',b,20)
        if not pairs[0] or tuple(sorted(set(pairs)))!=pairs:raise ValueError('Coverage mapping')
        ids.append(pairs);files['fonts/'+name]=b
    if ids[0]!=ids[1]:raise ValueError('Coverage mapping mismatch')
    b=ordinary(cache/'FONT-LICENSE.txt').read_bytes()
    if digest(b)!=m['files']['FONT-LICENSE.txt']:raise ValueError('Coverage license drift')
    files['fonts/FONT-LICENSE.txt']=b
    return files


def header(cache,output):
    files=payload(cache);output=ordinary(output,exists=False)
    hashes=[digest(files[f'fonts/candidate-{h}.sgc']) for h in (14,22)]
    write_file(output,('// Generated locale data binding; no engine/font assets.\n'
                       'static const char* scaledCacheHashes[]={'+','.join('"'+h+'"' for h in hashes)+'};\n').encode())


def integrate(runtime,module,cache,record):
    with runtime_lock(runtime):
        root=ordinary(runtime,directory=True);module=ordinary(module);record=ordinary(record,exists=False)
        if module.is_relative_to(root) or record.is_relative_to(root):raise ValueError('External inputs/record required')
        raw=(root/'runtime.json').read_bytes();m=load_json(raw);validate_manifest(root,m)
        start=(root/'Start.ps1').read_bytes()
        if digest(start)!=BASE_START_SHA or 'scaled_font' in m or m.get('native_scene_loading')!=dict(schema=1,enabled=True,module='native-loading'):
            raise ValueError('Expected retained native-loading baseline')
        after=payload(cache);after[ADDED[0]]=module.read_bytes()
        if ('launcher_output_snapshot'.encode('utf-16le') in after[ADDED[0]]
                and b'SCALED_FONT_OUTPUT' not in ordinary(root/'modules/workspace_launcher.exe').read_bytes()):
            raise ValueError('A snapshot-capable launcher is required; rebuild the shared runtime with the matching launcher')
        if len(after[ADDED[0]])<64 or after[ADDED[0]][:2]!=b'MZ':raise ValueError('Expected Win32 module')
        for h in (14,22):
            if digest(after[f'fonts/candidate-{h}.sgc']).encode() not in after[ADDED[0]]:
                raise ValueError('Module coverage binding mismatch; rebuild with generated header')
        canonical=ordinary(ROOT/'src/configuration/StartShared.ps1').read_bytes()
        if b'# SCALED_FONT_DEFAULT_ROUTE:' not in canonical:raise ValueError('Missing scaled font route')
        before={'Start.ps1':start,'runtime.json':raw,**{p:None for p in ADDED}}
        after['Start.ps1']=canonical
        for name,b in after.items():m['files'][name]=digest(b)
        m['scaled_font']=dict(schema=1,enabled=True,module='scaled-font',scale=4)
        after['runtime.json']=(json.dumps(m,indent=2)+'\n').encode('utf8')
        rows=[dict(path=p,before=digest(before[p]) if before[p] is not None else None,after=digest(after[p])) for p in CHANGES]
        check_state(root,rows,'before')
        record.mkdir(parents=True)
        for name,b in before.items():
            if b is not None:
                p=record/'original'/name;p.parent.mkdir(parents=True,exist_ok=True);write_file(p,b)
        journal=dict(schema=1,kind='scaled_font_integration',runtime=str(root),changes=rows,
                     original_modules_preserved=True,data_modified=False,in_game_verified=False)
        write_file(record/'changes.json',(json.dumps(journal,indent=2)+'\n').encode())
        try:
            for p in ADDED:
                relative(root,p).parent.mkdir(parents=True,exist_ok=True)
            for p in (*ADDED,'Start.ps1','runtime.json'):write_file(root/p,after[p])
            check_state(root,rows,'after');validate_manifest(root,load_json((root/'runtime.json').read_bytes()))
        except BaseException:
            restore_state(root,before);check_state(root,rows,'before');raise
        return journal


def rollback(record):
    record=ordinary(record,directory=True);j=load_json(ordinary(record/'changes.json').read_bytes())
    if j.get('schema')!=1 or j.get('kind')!='scaled_font_integration':raise ValueError('Unknown integration record')
    with runtime_lock(j['runtime']):
        root=ordinary(j['runtime'],directory=True);rows=j['changes']
        if record.is_relative_to(root) or [r['path'] for r in rows]!=list(CHANGES):raise ValueError('Unexpected rollback paths')
        before={}
        for row in rows:
            p=row['path'];b=None
            if p in ADDED:
                if row['before'] is not None:raise ValueError('Unexpected existing font integration')
            else:
                b=ordinary(record/'original'/p).read_bytes()
                if digest(b)!=row['before']:raise ValueError('Backup drift')
            before[p]=b
        check_state(root,rows,'after');validate_manifest(root,load_json((root/'runtime.json').read_bytes()))
        after={p:(root/p).read_bytes() for p in CHANGES}
        try:
            restore_state(root,before);check_state(root,rows,'before')
        except BaseException:
            restore_state(root,after);check_state(root,rows,'after');raise
        return j


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('runtime','module','cache','record','rollback','header'):p.add_argument('--'+n,type=Path)
    a=p.parse_args()
    try:
        if a.rollback:
            if any((a.runtime,a.module,a.cache,a.record,a.header)):p.error('--rollback is exclusive')
            rollback(a.rollback);print('SCALED_FONT_ROLLBACK PASS entry=restored native_loading=retained data_modified=false')
        elif a.header:
            if not a.cache or any((a.runtime,a.module,a.record)):p.error('--cache --header required')
            header(a.cache,a.header);print('SCALED_FONT_HEADER PASS hashes=bound')
        else:
            if not all((a.runtime,a.module,a.cache,a.record)):p.error('--runtime --module --cache --record required')
            integrate(a.runtime,a.module,a.cache,a.record)
            print('SCALED_FONT_INTEGRATION PASS entry=Play.cmd variant=C scale=4 baseline=retained data_modified=false game_started=false')
    except (OSError,ValueError,KeyError,TypeError) as e:p.error(str(e))


if __name__=='__main__':main()
