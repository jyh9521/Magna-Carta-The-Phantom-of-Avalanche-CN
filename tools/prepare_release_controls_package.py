"""Bind a small update to the actual delivered unified+F11 owned-file baseline."""
import argparse,json,zipfile
from pathlib import Path
from build_release_controls_update import build
from build_text_runtime_update import sha
from update_release_controls import CHANGES
from update_runtime_modules import MODULES

def prepare(base,base_sha256,previous,previous_sha256,runtime,work,output):
    base,previous,runtime,work,output=map(lambda p:Path(p).resolve(),(base,previous,runtime,work,output))
    if work.exists() or output.exists() or any(p.is_relative_to(work) for p in (base,previous,runtime,output)):raise ValueError('New independent work/output required')
    if sha(base.read_bytes())!=base_sha256 or sha(previous.read_bytes())!=previous_sha256:raise ValueError('Delivered baseline hash mismatch')
    with zipfile.ZipFile(base) as first,zipfile.ZipFile(previous) as last:
        if first.testzip() or last.testzip():raise ValueError('Delivered baseline CRC failure')
        entries=[n for n in last.namelist() if n.endswith('/package.json')]
        if len(entries)!=1:raise ValueError('Expected one F11 package manifest')
        name=entries[0];prefix=name.rsplit('/',1)[0]+'/'
        pm=json.loads(last.read(name))
        if pm.get('schema')!=1 or pm.get('kind')!='text_runtime_update' or {r['path'] for r in pm['files']}!={*MODULES,'runtime.json'}:raise ValueError('Unsupported delivered F11 file set')
        before={}
        for r in pm['files']:
            b=last.read(prefix+r['payload'])
            if r['delta'] or sha(b)!=r['after'] or sha(b)!=r['payload_sha256'] or len(b)!=r['size']:raise ValueError('F11 payload mismatch')
            before[r['path']]=b
        m=json.loads(before['runtime.json'])
        for n in CHANGES:
            if n in before or n=='config/encounter-ui.json':continue
            b=first.read('payload/'+n)
            if sha(b)!=m['files'].get(n):raise ValueError('Unified configuration does not match F11 manifest: '+n)
            before[n]=b
        after={n:(runtime/n).read_bytes() for n in CHANGES if n!='runtime.json'}
        current=json.loads((runtime/'runtime.json').read_text())
        for n,b in after.items():
            if sha(b)!=current['files'].get(n):raise ValueError('Active runtime drift: '+n)
            m['files'][n]=sha(b)
        m['archived_features']=['native_gamepad','free_view']
        # Normal Play does not request the optional local diagnostic entry/helper.
        after['runtime.json']=(json.dumps(m,indent=2)+'\n').encode()
        for n,digest in m['files'].items():
            data=after[n] if n in after else before[n] if n in before else first.read('payload/'+n)
            if sha(data)!=digest:raise ValueError('Shipped runtime would reference a missing or mismatched input: '+n)
        work.mkdir(parents=True);record=work/'record';stage=work/'staged';record.mkdir();stage.mkdir()
        states={n:dict(before=sha(before[n]) if n in before else None,after=sha(after[n])) for n in CHANGES}
        for n,b in before.items():
            p=record/'original'/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
        for n,b in after.items():p=stage/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
        (record/'changes.json').write_text(json.dumps(states,indent=2)+'\n')
        (work/'provenance.json').write_text(json.dumps(dict(base_sha256=base_sha256,previous_sha256=previous_sha256,game_data_copied=False,settings_modified=False),indent=2)+'\n')
    build(stage,record,output)
    print('SHIPPED_BASELINE_PACKAGE PASS baseline=unified_plus_F11 owned_only=true diagnostic_dependencies=not_required game_started=false')
    return record
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('base','previous','runtime','work','output'):p.add_argument('--'+n,type=Path,required=True)
    for n in ('base-sha256','previous-sha256'):p.add_argument('--'+n,required=True)
    prepare(**vars(p.parse_args()))
