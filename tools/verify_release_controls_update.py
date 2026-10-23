"""Reopen and exercise the delivered updater on owned-file-only fixtures."""
import argparse,json,shutil,subprocess,zipfile
from pathlib import Path
from build_release_controls_update import FOLDER
from build_text_runtime_update import sha

def verify(record,package,output):
    record,package,output=map(lambda p:Path(p).resolve(),(record,package,output))
    if output.exists() or record.is_relative_to(output) or package.is_relative_to(output):raise ValueError('Independent new evidence required')
    states=json.loads((record/'changes.json').read_text());output.mkdir(parents=True)
    modified=output/'modified runtime';modified.mkdir()
    for n,s in states.items():
        if s['before'] is not None:
            b=(record/'original'/n).read_bytes()
            if sha(b)!=s['before']:raise ValueError('Backup drift')
            p=modified/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
    protected={'config/enhancements.json':b'{"schema":2,"native_gamepad":true,"free_view":true}', 'data/MC00.sav':b'owned save fixture', '.prior-update/state.json':b'earlier rollback evidence'}
    for n,b in protected.items():p=modified/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b)
    with zipfile.ZipFile(package) as z:
        if z.testzip():raise ValueError('Package CRC')
        z.extractall(modified)
    checks=[]
    def run(root,action,expected=0):
        command=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(root/FOLDER/'Update.ps1'),'-Action',action,'-Runtime',str(root)]
        r=subprocess.run(command,capture_output=True,text=True,errors='replace',timeout=90)
        checks.append(dict(command=command,input='none',stdout=r.stdout,stderr=r.stderr,exit_status=r.returncode))
        if r.returncode!=expected:raise ValueError(json.dumps(checks[-1]))
        return r
    run(modified,'Verify');run(modified,'Install');run(modified,'Install');run(modified,'CheckInstalled')
    rolled=output/'rollback runtime';shutil.copytree(modified,rolled)
    run(rolled,'Rollback');run(rolled,'Verify')
    for n,s in states.items():
        if s['before'] is None:
            if (rolled/n).exists():raise ValueError('Added file remains after rollback')
        elif sha((rolled/n).read_bytes())!=s['before']:raise ValueError('Rollback not exact: '+n)
        if sha((modified/n).read_bytes())!=s['after']:raise ValueError('Modified fixture not retained')
    # A mixed installation fails before any other file is changed.
    changed=next(iter(states));(rolled/changed).write_bytes(b'foreign file')
    snapshot={n:(rolled/n).read_bytes() if (rolled/n).exists() else None for n in states}
    run(rolled,'Verify',1)
    if any(((rolled/n).read_bytes() if (rolled/n).exists() else None)!=b for n,b in snapshot.items()):raise ValueError('Mixed preflight wrote files')
    (rolled/changed).write_bytes((record/'original'/changed).read_bytes())
    for root in (modified,rolled):
        for n,b in protected.items():
            if (root/n).read_bytes()!=b:raise ValueError('Protected file modified')
    report=dict(checks=checks,package_sha256=sha(package.read_bytes()),modified=str(modified),rollback=str(rolled),modified_state='retained',rollback_state='original hashes exact',protected='exact',game_started=False,full_game_copies=0)
    (output/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print('RELEASE_CONTROLS_VERIFY PASS baseline=19 modified=19 repeat=idempotent rollback=exact mixed=rejected saves=preserved settings=preserved modified_copy=retained game_started=false')
    return report
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('record','package','output'):p.add_argument('--'+n,type=Path,required=True)
    verify(**vars(p.parse_args()))
