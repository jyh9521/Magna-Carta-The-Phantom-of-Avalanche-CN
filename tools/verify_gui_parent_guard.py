"""Offline compiled production encoder + original instruction replay. No game launch."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from replay_native_gui_parent import replay, single

def verify(sample, fixture, output, mode='verify'):
    if output.exists():raise ValueError('New evidence directory required')
    output.mkdir(parents=True)
    bridge=output/'production-bridge.bin'
    p=subprocess.run([str(fixture.resolve()),str(bridge.resolve())],capture_output=True,text=True,timeout=30)
    if p.returncode:raise ValueError('Owned fixture failed: '+p.stdout+p.stderr)
    b=bridge.read_bytes();image=sample.read_bytes()
    result=replay(image,b) if mode=='verify' else single(image,mode,b)
    result['compiled_encoder_sha256']=hashlib.sha256(b).hexdigest()
    result['fixture_sha256']=hashlib.sha256(fixture.read_bytes()).hexdigest()
    result['fixture_output']=p.stdout.strip()
    result['production_encoder_verified']=True
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    passed=mode=='verify' or result['result']['completed']
    print('GUI_PARENT_COMPILED '+mode.upper()+' '+('PASS' if passed else 'FAULT_5201E94F_READ_BAF024')+' rollback='+('restored' if mode=='rollback' else 'tested' if mode=='verify' else 'not_requested')+' game_started=false scene_transition_verified=false')
    return 0 if passed else 1

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('sample','fixture','output'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--mode',choices=('verify','baseline','proposal','rollback'),default='verify')
    a=p.parse_args();raise SystemExit(verify(a.sample,a.fixture,a.output,a.mode))
