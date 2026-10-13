"""Source-locked image-only upgrade of a marked independent locale copy."""
import argparse,json
from pathlib import Path
from locale_package import collect,located,sha

def apply(workspace,old_packages,new_packages,backup):
    workspace=Path(workspace).resolve(strict=True);backup=Path(backup).resolve()
    marker=workspace/'.locale-install.json'
    if json.loads(marker.read_text(encoding='utf8')).get('state')!='candidate':raise ValueError('not an active independent locale copy')
    if backup.exists() or backup.is_relative_to(workspace) or workspace.is_relative_to(backup):raise ValueError('backup must be new and independent')
    old=collect(old_packages);new=collect(new_packages)
    if old.keys()!=new.keys():raise ValueError('image upgrade identities differ')
    rows=[];snapshots={}
    for name,path in old.items():
        before=path.read_bytes();after=new[name].read_bytes();target=located(workspace,name)
        if target.read_bytes()!=before:raise ValueError('existing candidate image drift; no writes')
        snapshots[name]=(before,after)
        rows.append(dict(resource=name,before_sha256=sha(before),after_sha256=sha(after),changed=before!=after))
    backup.mkdir(parents=True)
    for name,(before,after) in snapshots.items():
        p=backup/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(before)
    (backup/'manifest.json').write_text(json.dumps(dict(schema=1,files=rows,game_started=False),indent=2)+'\n',encoding='utf8')
    for name,(before,after) in snapshots.items():
        target=located(workspace,name)
        if target.read_bytes()!=before:raise ValueError('image changed before write')
        target.write_bytes(after)
        if target.read_bytes()!=after:raise ValueError('image readback mismatch')
    return rows

def rollback(workspace,backup):
    workspace=Path(workspace).resolve(strict=True);backup=Path(backup).resolve(strict=True)
    if workspace==backup or workspace.is_relative_to(backup) or backup.is_relative_to(workspace):raise ValueError('rollback target overlaps backup')
    rows=json.loads((backup/'manifest.json').read_text(encoding='utf8'))['files']
    restored={}
    for row in rows:
        name=row['resource'];raw=located(backup,name).read_bytes()
        if sha(raw)!=row['before_sha256'] or sha(located(workspace,name).read_bytes())!=row['after_sha256']:raise ValueError('rollback drift; no writes')
        restored[name]=raw
    for name,raw in restored.items():
        p=located(workspace,name);p.write_bytes(raw)
        if p.read_bytes()!=raw:raise ValueError('rollback readback mismatch')
    return rows

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['apply','rollback']);p.add_argument('--workspace',type=Path,required=True)
    p.add_argument('--backup',type=Path,required=True);p.add_argument('--old-packages',type=Path,nargs='+');p.add_argument('--new-packages',type=Path,nargs='+')
    a=p.parse_args()
    rows=apply(a.workspace,a.old_packages,a.new_packages,a.backup) if a.action=='apply' else rollback(a.workspace,a.backup)
    print(f'IMAGE_CANDIDATE_{a.action.upper()} PASS verified_resources={len(rows)} changed_resources={sum(r["changed"] for r in rows)} game_started=false')
