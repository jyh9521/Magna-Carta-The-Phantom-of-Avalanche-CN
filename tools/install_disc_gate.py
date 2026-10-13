"""Install the source-locked disc-gate candidate into a new copy; never launch."""
import argparse, hashlib, json, shutil
from pathlib import Path
from patch_binary_plan import transform, digest

def install(source, package, output):
    source=Path(source).resolve(strict=True);package=Path(package).resolve(strict=True);output=Path(output).resolve()
    if output.exists() or output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError('output must be a new independent copy')
    if (source/'.disc-gate').exists():raise ValueError('source already contains a disc-gate installation')
    for p in source.rglob('*'):
        if p.is_symlink() or (hasattr(p,'is_junction') and p.is_junction()):raise ValueError('source contains links')
    m=json.loads((package/'bundle.json').read_text(encoding='utf8'))
    for n,sha in m['files'].items():
        if digest((package/n).read_bytes())!=sha:raise ValueError('bundle input mismatch')
    plan=json.loads((package/'disc-gate.json').read_text(encoding='utf8'))
    raw=(source/'MagnaCarta.exe').read_bytes();after=transform(raw,plan)
    if digest((source/'MCAlpha.dll').read_bytes()) not in m['engine_sha256']:
        raise ValueError('unsupported engine module')
    stage=output.with_name(output.name+'.assembling')
    if stage.exists():raise ValueError('assembly stage exists')
    shutil.copytree(source,stage)
    if (stage/'MagnaCarta.exe').read_bytes()!=raw:raise ValueError('copied executable drift')
    (stage/'MagnaCarta.exe').write_bytes(after)
    state=stage/'.disc-gate';state.mkdir()
    launcher=stage/'.locale-runtime/workspace_launcher.exe'
    prior=None
    if launcher.exists():
        prior=digest(launcher.read_bytes());shutil.copyfile(launcher,state/'original-launcher.exe')
        shutil.copyfile(package/'workspace_launcher.exe',launcher)
    else:
        shutil.copyfile(package/'workspace_launcher.exe',state/'workspace_launcher.exe')
    shutil.copyfile(package/'disc-gate.json',state/'plan.json')
    (state/'state.json').write_text(json.dumps(dict(state='candidate',prior_launcher_sha256=prior,
        launcher_sha256=m['files']['workspace_launcher.exe'],game_started=False))+'\n',encoding='utf8')
    if (source/'MagnaCarta.exe').read_bytes()!=raw or (stage/'MagnaCarta.exe').read_bytes()!=after:
        raise ValueError('source or output drift')
    stage.rename(output)

def restore(target):
    target=Path(target).resolve(strict=True);state=target/'.disc-gate'
    if target.is_symlink() or not state.is_dir():raise ValueError('not a disc-gate copy')
    m=json.loads((state/'state.json').read_text(encoding='utf8'))
    if m['state']!='candidate':raise ValueError('rollback state mismatch')
    plan=json.loads((state/'plan.json').read_text(encoding='utf8'))
    exe=target/'MagnaCarta.exe';raw=exe.read_bytes();original=transform(raw,plan,True)
    launcher=target/'.locale-runtime/workspace_launcher.exe' if m['prior_launcher_sha256'] else state/'workspace_launcher.exe'
    if digest(launcher.read_bytes())!=m['launcher_sha256']:raise ValueError('launcher drift; no writes')
    prior=None
    if m['prior_launcher_sha256']:
        prior=(state/'original-launcher.exe').read_bytes()
        if digest(prior)!=m['prior_launcher_sha256']:raise ValueError('rollback launcher mismatch')
    exe.write_bytes(original)
    if prior:launcher.write_bytes(prior)
    if exe.read_bytes()!=original or (prior and launcher.read_bytes()!=prior):raise ValueError('rollback readback mismatch')
    m['state']='rolled_back';(state/'state.json').write_text(json.dumps(m)+'\n',encoding='utf8')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['apply','rollback']);p.add_argument('--source',type=Path)
    p.add_argument('--package',type=Path);p.add_argument('--output',type=Path);p.add_argument('--target',type=Path)
    a=p.parse_args()
    if a.action=='apply':install(a.source,a.package,a.output)
    else:restore(a.target)
    print('DISC_GATE_'+a.action.upper()+' PASS original_install_unchanged=true game_started=false')
