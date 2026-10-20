"""Replay the retained image baseline, installed repair, or isolated shell rollback."""
import argparse
from contextlib import redirect_stderr
import io
import json
from pathlib import Path
import subprocess
import tempfile

from audit_image_resources import audit, original_images
from prepare_field_return_trial import digest, load_json, check_state, validate_manifest

ROOT=Path(__file__).resolve().parents[1]


def check(mode,evidence):
    evidence=Path(evidence).resolve(strict=True)
    record=evidence/'integration-verified'
    journal=load_json((record/'changes.json').read_bytes())
    runtime=Path(journal['runtime'])
    if runtime.resolve()!= (ROOT/'runtime').resolve():
        raise ValueError('Expected this checkout shared runtime')
    changes=journal['changes']
    check_state(runtime,changes,'after')
    validate_manifest(runtime,load_json((runtime/'runtime.json').read_bytes()))
    baseline=load_json((evidence/'baseline-final-audit.json').read_bytes())
    with redirect_stderr(io.StringIO()):
        originals=original_images(ROOT/'game/Magna Carta CD 1.iso',ROOT/'game/MCV104a.exe')
    plans,groups,rules=[load_json((ROOT/'locales/zh-CN'/n).read_bytes()) for n in
                       ['image-text-plans.json','image-group-plans.json','image-integrity-checks.json']]
    for n,key in [('plans','image-text-plans.json'),('groups','image-group-plans.json'),('checks','image-integrity-checks.json')]:
        if digest((ROOT/'locales/zh-CN'/key).read_bytes())!=baseline['input_sha256'][n]:
            raise ValueError('Verification recipe changed since baseline')
    def inspect(overrides):
        return audit(originals,runtime/'data',plans,groups,rules,overrides)
    overrides={}
    shell_output=None
    if mode=='baseline':
        overrides={r['path'][5:]:(record/'original'/r['path']).read_bytes()
                   for r in changes if r['path'].startswith('data/')}
    elif mode=='rollback':
        bash=Path('C:/Program Files/Git/bin/bash.exe')
        if not bash.is_file():
            raise ValueError('Git Bash required to verify ROLLBACK.sh')
        with tempfile.TemporaryDirectory(prefix='owned-rollback-',dir=evidence) as folder:
            fixture=Path(folder)
            for row in changes:
                p=fixture/row['path'];p.parent.mkdir(parents=True,exist_ok=True)
                p.write_bytes((runtime/row['path']).read_bytes());p.chmod(row['mode'])
            for n,data in [('data/MC00.sav',b'owned rollback save sentinel'),('config/enhancements.json',b'{"owned":true}')]:
                p=fixture/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
            sentinels={n:(fixture/n).read_bytes() for n in ['data/MC00.sav','config/enhancements.json']}
            proc=subprocess.run([str(bash),str(evidence/'ROLLBACK.sh'),'--runtime',fixture.as_posix()],
                                cwd=ROOT,capture_output=True,text=True,encoding='utf8',timeout=60)
            if proc.returncode:
                raise ValueError('Isolated shell rollback failed: '+proc.stdout+proc.stderr)
            shell_output=proc.stdout.strip()
            check_state(fixture,changes,'before')
            if any((fixture/n).read_bytes()!=b for n,b in sentinels.items()):
                raise ValueError('Rollback changed fixture saves/settings')
            for row in changes:
                if (fixture/row['path']).stat().st_mode!=row['mode']:
                    raise ValueError('Rollback file attributes changed')
            overrides={r['path'][5:]:(fixture/r['path']).read_bytes()
                       for r in changes if r['path'].startswith('data/')}
    result=inspect(overrides)
    if mode=='modified':
        if result['errors']:
            raise ValueError('Installed image audit failed')
    else:
        expected={r['resource']:r['current_sha256'] for r in baseline['records']}
        actual={r['resource']:r['current_sha256'] for r in result['records']}
        if expected!=actual or len(result['errors'])!=len(baseline['errors']) or not baseline['errors']:
            raise ValueError('Retained baseline was not restored exactly')
    check_state(runtime,changes,'after')  # The real shared runtime stays repaired.
    print('IMAGE_REPAIR_%s PASS images=%d errors=%d retained_modified=true game_started=false' %
          (mode.upper(),result['images'],len(result['errors'])))
    return dict(mode=mode,images=result['images'],errors=len(result['errors']),
                retained_modified=True,game_started=False,shell_output=shell_output,
                isolated_rollback=mode=='rollback',changed_images=len(changes)-1)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=['baseline','modified','rollback'])
    p.add_argument('--evidence',type=Path,default=ROOT/'build/image-integrity-evidence')
    p.add_argument('--record',type=Path)
    a=p.parse_args()
    if a.record and a.record.exists():
        p.error('New verification record required')
    result=check(a.mode,a.evidence)
    if a.record:
        a.record.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8',newline='\n')


if __name__=='__main__':
    main()
