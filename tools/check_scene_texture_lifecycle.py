"""Observe source-locked native texture replacement using the real Windows D3D7 COM API.

This is not a game-scene/crash acceptance test. Both original and candidate
sequences may succeed: retained COM references alone do not prove a UAF.
The driver is mapped without DllMain; only verified Bind/Delete bodies execute
on an owned table and hidden offscreen device. Game entry points never execute.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

DRIVER_SHA='00d443327abf56c94f9f088515ab29be63bab9650771a5cacdcef20ab85eff29'
MODES=('baseline','candidate','rollback')

def observe(driver, probe, ddraw, mode, report=None):
    if mode not in MODES:raise ValueError('Unknown observation mode')
    driver=Path(driver).resolve(strict=True);probe=Path(probe).resolve(strict=True);ddraw=Path(ddraw).resolve(strict=True)
    if hashlib.sha256(driver.read_bytes()).hexdigest()!=DRIVER_SHA:raise ValueError('Unsupported full driver SHA256')
    if not all(p.is_file() for p in (driver,probe,ddraw)):raise ValueError('Expected regular input files')
    if report is not None:
        report=Path(report).resolve()
        if report.exists() or not report.parent.is_dir():raise ValueError('New report in existing directory required')
        if report in (driver,probe,ddraw):raise ValueError('Report overlaps input')
    command=[str(probe),str(driver),str(ddraw)]+([] if mode=='candidate' else ['--'+mode])
    p=subprocess.run(command,capture_output=True,text=True,timeout=90)
    expected=f'mode={mode} cycles=200 residual_bound_after_delete='+('0' if mode=='candidate' else '200')
    valid=(p.returncode==0 and expected in p.stdout and
           'NATIVE_TEXTURE_OBSERVATION_PASS access_violation=false' in p.stdout and
           'game_crash_reproduced=false' in p.stdout and 'NATIVE_TEXTURE_REFS after_bind=2' in p.stdout)
    result=dict(schema=1,mode=mode,command=command,driver_sha256=DRIVER_SHA,
                ddraw_sha256=hashlib.sha256(ddraw.read_bytes()).hexdigest(),
                probe_sha256=hashlib.sha256(probe.read_bytes()).hexdigest(),
                stdout=p.stdout,stderr=p.stderr,exit_status=p.returncode,
                observation_verified=valid,game_started=False,game_crash_reproduced=False,
                limitations=['Owned resource table; no actual scene loading or collision/UI.',
                             '200 texture replacements, not 200 game scene transitions.',
                             'Candidate unbinding succeeds; not proof of a crash fix.',
                             'Original binding retains a live COM reference; not demonstrated UAF.'])
    if report is not None:
        with report.open('x',encoding='utf8') as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write('\n')
    if not valid:raise RuntimeError('Native observation did not match; stdout='+p.stdout+' stderr='+p.stderr+' exit='+str(p.returncode))
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('driver','probe','ddraw'):p.add_argument('--'+n,required=True,type=Path)
    p.add_argument('--mode',choices=MODES,required=True);p.add_argument('--report',type=Path)
    a=p.parse_args()
    r=observe(a.driver,a.probe,a.ddraw,a.mode,a.report)
    print(r['stdout'],end='')

if __name__=='__main__':main()
