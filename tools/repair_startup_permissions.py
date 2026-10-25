"""Apply the source-locked existing-INI permission repair without touching game data."""
import argparse,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASELINE='0b3b82902d8439e4fa997861730f4a254b1487f8bd5891bab62cf6215f4c7097'
def sha(b):return hashlib.sha256(b).hexdigest()
def idle():
 r=subprocess.run(['powershell.exe','-NoProfile','-Command',"if(Get-Process MagnaCarta,workspace_launcher -ErrorAction SilentlyContinue){exit 9}"],capture_output=True,timeout=20)
 if r.returncode:raise ValueError('Exit active game before startup repair')
def apply(target,record):
 idle()
 target,record=Path(target).resolve(),Path(record).resolve()
 if record.exists():raise ValueError('New repair record required')
 module='config/EnhancementSettings.psm1';state=json.loads((target/'runtime.json').read_text(encoding='utf-8-sig'))
 if state['files'].get(module)!=BASELINE or sha((target/module).read_bytes())!=BASELINE:raise ValueError('Unsupported settings module baseline')
 for n,h in state['files'].items():
  if sha((target/n).read_bytes())!=h:raise ValueError('Runtime drift: '+n)
 payload={module:(ROOT/'src/configuration/EnhancementSettings.psm1').read_bytes()}
 state['files'][module]=sha(payload[module]);payload['runtime.json']=(json.dumps(state,indent=2)+'\n').encode()
 if (target/'Overlay-Manifest.json').exists():
  overlay=json.loads((target/'Overlay-Manifest.json').read_text(encoding='utf-8-sig'))
  for n,b in payload.items():overlay['files'][n]=sha(b)
  overlay['startup_permission_repair']='existing_file_locked_write_v1'
  payload['Overlay-Manifest.json']=(json.dumps(overlay,ensure_ascii=False,indent=2)+'\n').encode()
 record.mkdir(parents=True);changes={}
 for n,b in payload.items():
  old=(target/n).read_bytes();p=record/'original'/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(old)
  changes[n]=dict(before=sha(old),after=sha(b))
 (record/'changes.json').write_text(json.dumps(changes,indent=2))
 written=[]
 try:
  for n,b in payload.items():
   (target/n).write_bytes(b);written.append(n)
   if sha((target/n).read_bytes())!=changes[n]['after']:raise ValueError('Repair readback mismatch')
 except Exception:
  for n in reversed(written):(target/n).write_bytes((record/'original'/n).read_bytes())
  raise
 print(f'STARTUP_REPAIR PASS files={len(payload)} game_data=unchanged settings=preserved directory_acl=unchanged')
def rollback(target,record):
 idle()
 target,record=Path(target).resolve(),Path(record).resolve();changes=json.loads((record/'changes.json').read_text())
 for n,r in changes.items():
  if sha((target/n).read_bytes())!=r['after'] or sha((record/'original'/n).read_bytes())!=r['before']:raise ValueError('Rollback drift: '+n)
 for n in reversed(list(changes)):(target/n).write_bytes((record/'original'/n).read_bytes())
 print('STARTUP_ROLLBACK PASS original_bytes=exact settings=preserved')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['apply','rollback']);p.add_argument('--target',type=Path,required=True);p.add_argument('--record',type=Path,required=True);a=p.parse_args();globals()[a.action](a.target,a.record)
