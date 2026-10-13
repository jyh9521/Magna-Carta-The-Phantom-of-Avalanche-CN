"""Transactional source-locked upgrade of an existing marked locale candidate."""
import argparse
import json
from pathlib import Path
from locale_package import preflight, located, sha, undelta


def apply(workspace,source,old_package,new_package,backup):
    workspace=Path(workspace).resolve(strict=True);backup=Path(backup).resolve()
    if backup.exists() or workspace.is_relative_to(backup) or backup.is_relative_to(workspace):
        raise ValueError('backup must be new and separate')
    old_dir,old_raw,old,source=preflight(old_package,source)
    new_dir,new_raw,new,_=preflight(new_package,source)
    marker=located(workspace,'.locale-install.json');state=json.loads(marker.read_text(encoding='utf8'))
    if state.get('state')!='candidate' or state.get('package_sha256')!=sha(old_raw):
        raise ValueError('existing locale package identity mismatch')
    previous={r['resource']:r for r in old['files']};current={r['resource']:r for r in new['files']}
    if previous.keys()-current.keys():raise ValueError('upgrade would remove a resource')
    expected_exe=old['prerequisites']['MagnaCarta.exe']
    disc_state=workspace/'.disc-gate/state.json'
    if disc_state.is_file():
        from patch_binary_plan import transform
        d=json.loads(disc_state.read_text(encoding='utf8'))
        if d.get('state')!='candidate':raise ValueError('disc-gate candidate is inactive')
        plan=json.loads(located(workspace,'.disc-gate/plan.json').read_text(encoding='utf8'))
        expected_exe=sha(transform(located(source,'MagnaCarta.exe').read_bytes(),plan))
        if sha(located(workspace,'.locale-runtime/workspace_launcher.exe').read_bytes())!=d['launcher_sha256']:
            raise ValueError('disc-gate launcher drift')
    elif sha(located(workspace,'.locale-runtime/workspace_launcher.exe').read_bytes())!=old['runtime']['workspace_launcher.exe']:
        raise ValueError('locale launcher drift')
    if sha(located(workspace,'MagnaCarta.exe').read_bytes())!=expected_exe:raise ValueError('executable drift')
    rows=[];values={}
    for name,row in current.items():
        before=located(workspace,name).read_bytes()
        expected=previous[name]['target_sha256'] if name in previous else row['source_sha256']
        if sha(before)!=expected:raise ValueError('candidate resource drift: '+name)
        original=located(source,name).read_bytes()
        after=undelta(original,located(new_dir,row['patch']).read_bytes(),row['target_size'])
        if sha(after)!=row['target_sha256']:raise ValueError('upgrade target mismatch')
        values[name]=(before,after)
    # The launcher/Start entry point is already accepted and remains unchanged.
    # Only the owned profile module contains the new font/label implementation.
    name='.locale-runtime/workspace_profile.dll';before=located(workspace,name).read_bytes()
    if sha(before)!=old['runtime']['workspace_profile.dll']:raise ValueError('owned profile drift')
    after=located(new_dir,'runtime/workspace_profile.dll').read_bytes();values[name]=(before,after)
    new_state=dict(state,package_sha256=sha(new_raw));values['.locale-install.json']=(marker.read_bytes(),(json.dumps(new_state)+'\n').encode('utf8'))
    saves={p.relative_to(workspace).as_posix():sha(p.read_bytes()) for p in workspace.glob('*.sav')}
    for name,(before,after) in values.items():
        rows.append(dict(resource=name,before_sha256=sha(before),after_sha256=sha(after),changed=before!=after,
                         original_mode=located(workspace,name).stat().st_mode))
    backup.mkdir(parents=True)
    for row in rows:
        if row['changed']:
            p=backup/row['resource'];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(values[row['resource']][0])
    manifest=dict(schema=1,files=rows,saves=saves,old_package_sha256=sha(old_raw),new_package_sha256=sha(new_raw),game_started=False)
    (backup/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8')
    written=[]
    try:
        for row in rows:
            name=row['resource'];p=located(workspace,name);before,after=values[name]
            if p.read_bytes()!=before:raise ValueError('candidate drift before write')
            if not row['changed']:continue
            p.chmod(row['original_mode']|0o200);written.append(row);p.write_bytes(after)
            if p.read_bytes()!=after:raise ValueError('upgrade readback mismatch')
        if any(sha(located(workspace,n).read_bytes())!=v for n,v in saves.items()):raise ValueError('save drift')
    except Exception:
        for row in reversed(written):
            p=located(workspace,row['resource']);p.write_bytes(values[row['resource']][0]);p.chmod(row['original_mode'])
        raise
    return manifest


def rollback(workspace,backup):
    workspace=Path(workspace).resolve(strict=True);backup=Path(backup).resolve(strict=True)
    if workspace.is_relative_to(backup) or backup.is_relative_to(workspace):raise ValueError('rollback paths overlap')
    m=json.loads((backup/'manifest.json').read_text(encoding='utf8'));values={}
    for row in m['files']:
        if sha(located(workspace,row['resource']).read_bytes())!=row['after_sha256']:raise ValueError('rollback target drift; no writes')
        if row['changed']:
            raw=located(backup,row['resource']).read_bytes()
            if sha(raw)!=row['before_sha256']:raise ValueError('rollback backup drift; no writes')
            values[row['resource']]=raw
    for row in m['files']:
        if row['changed']:
            p=located(workspace,row['resource']);p.chmod(p.stat().st_mode|0o200);p.write_bytes(values[row['resource']]);p.chmod(row['original_mode'])
    for row in m['files']:
        if sha(located(workspace,row['resource']).read_bytes())!=row['before_sha256']:raise ValueError('rollback readback mismatch')
    return m


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['apply','rollback'])
    for key in ('workspace','backup'):p.add_argument('--'+key,type=Path,required=True)
    for key in ('source','old-package','new-package'):p.add_argument('--'+key,type=Path)
    a=p.parse_args()
    r=apply(a.workspace,a.source,a.old_package,a.new_package,a.backup) if a.action=='apply' else rollback(a.workspace,a.backup)
    print(f'LOCALE_UPGRADE_{a.action.upper()} PASS resources={len(r["files"])} changed={sum(row["changed"] for row in r["files"])} saves=unchanged game_started=false')
