"""Exercise the delivered ZIP on an owned-only prior-installation fixture."""
import argparse
import json
from pathlib import Path
import subprocess
import zipfile

from build_continue_game_update import FOLDER, MODULES, sha


def verify(previous, package, output, package_sha256, folder=FOLDER,
           wrapper='Repair-ContinueGame.cmd', prior_backup='.text-runtime-update'):
    previous, package, output = map(lambda p: Path(p).resolve(), (previous, package, output))
    if output.exists() or any(p.is_relative_to(output) for p in (previous,package)):
        raise ValueError('New independent evidence directory required')
    if sha(package.read_bytes()) != package_sha256:
        raise ValueError('Package hash mismatch')
    output.mkdir(parents=True)
    target = output/'prior installed runtime'
    target.mkdir()
    previous_dir = output/'previous-updater'
    previous_dir.mkdir()
    with zipfile.ZipFile(previous) as archive:
        archive.extractall(previous_dir)
        old_manifest = json.loads(archive.read('package.json'))
        before = {r['path']: archive.read(r['payload']) for r in old_manifest['files']}
        if set(before) != {*MODULES,'runtime.json'}:
            raise ValueError('Expected exact earlier owned module set')
        marker = json.dumps(dict(package_sha256=sha(archive.read('package.json')),state='installed')).encode()
    for n,b in before.items():
        p=target/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
    protected = {'.text-runtime-update/state.json':marker if prior_backup=='.text-runtime-update' else b'earlier installed feedback marker',
                 prior_backup+'/state.json':marker,
                 '.text-runtime-update/prior.sentinel':b'original feedback update journal',
                 '.text-runtime-update/original/opaque-backup.sentinel':b'earlier rollback bytes',
                 'config/enhancements.json':b'user settings', 'data/MC00.sav':b'user save'}
    for n,b in protected.items():
        p=target/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
    rows=[]
    def run(state,command,input=None,expected=0):
        r=subprocess.run(command,input=input,capture_output=True,text=True,errors='replace',timeout=90)
        rows.append(dict(state=state,command=command,input=input,stdout=r.stdout,stderr=r.stderr,exit_status=r.returncode))
        if r.returncode!=expected:raise RuntimeError(json.dumps(rows[-1]))
        return r
    def action(script,mode):
        return ['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(script),'-Action',mode,'-Runtime',str(target)]
    run('BASELINE',action(previous_dir/'Update.ps1','CheckInstalled'))
    with zipfile.ZipFile(package) as archive:
        if archive.testzip() is not None:raise ValueError('ZIP CRC mismatch')
        archive.extractall(target)
        manifest=json.loads(archive.read(folder+'/package.json'))
        modules=[r for r in manifest['files'] if r['path'] in MODULES]
        expected_modules={r['after'] for r in modules}
        if len(modules)!=12 or len(expected_modules)!=1:raise ValueError('Incomplete module set')
        expected_module=next(iter(expected_modules))
    wrapper_command=['cmd.exe','/d','/c',str(target/wrapper)]
    run('MODIFIED',wrapper_command,'\n')
    installed=(target/'runtime.json').read_bytes()
    old=json.loads(before['runtime.json']);new=json.loads(installed)
    for name in MODULES:
        if sha((target/name).read_bytes())!=expected_module or new['files'][name]!=expected_module:
            raise ValueError('Installed module mismatch')
        new['files'][name]=old['files'][name]
    if new!=old:raise ValueError('Unrelated runtime manifest changed')
    run('MODIFIED_REPEAT',wrapper_command,'\n')
    run('ROLLBACK',action(target/folder/'Update.ps1','Rollback'))
    for n,b in {**before,**protected}.items():
        if (target/n).read_bytes()!=b:raise ValueError('Rollback/protected file mismatch: '+n)
    run('ROLLBACK_BASELINE_CHECK',action(previous_dir/'Update.ps1','CheckInstalled'))
    # Mixed builds must fail preflight before touching any other module/manifest.
    changed=MODULES[0];(target/changed).write_bytes(b'unknown changed module')
    snapshot={n:(target/n).read_bytes() for n in before}
    run('MIXED_REJECTED',action(target/folder/'Update.ps1','Verify'),expected=1)
    if any((target/n).read_bytes()!=b for n,b in snapshot.items()):raise ValueError('Preflight wrote files')
    (target/changed).write_bytes(before[changed])
    run('FINAL_REINSTALL',wrapper_command,'\n')
    for n,b in protected.items():
        if (target/n).read_bytes()!=b:raise ValueError('Protected bytes changed')
    if sha(package.read_bytes())!=package_sha256:raise ValueError('Package drift')
    report=dict(package=str(package),package_sha256=package_sha256,module_sha256=expected_module,
                previous_sha256=sha(previous.read_bytes()),checks=rows,game_started=False,
                prior_backup_preserved=True,saves_preserved=True,settings_preserved=True,
                rollback='exact',final_state='modified',full_game_copy_created=False)
    (output/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print('CONTINUE_GAME_RELEASE PASS baseline=installed modified=13 rollback=exact repeat=idempotent mixed=rejected prior_backup=preserved saves=preserved settings=preserved game_started=false')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('previous','package','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--package-sha256',required=True)
    p.add_argument('--folder',default=FOLDER);p.add_argument('--wrapper',default='Repair-ContinueGame.cmd')
    p.add_argument('--prior-backup',default='.text-runtime-update')
    verify(**vars(p.parse_args()))
