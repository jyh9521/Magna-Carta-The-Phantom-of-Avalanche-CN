"""Deploy only desktop entries and compact configuration with hash-locked rollback."""
import argparse,json,hashlib,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def idle():
 r=subprocess.run(['powershell.exe','-NoProfile','-Command',"if(Get-Process MagnaCarta,workspace_launcher -ErrorAction SilentlyContinue){exit 9}"],capture_output=True,timeout=20)
 if r.returncode:raise ValueError('Exit active game and launcher before desktop deployment')
def sha(b):return hashlib.sha256(b).hexdigest()
def apply(runtime,entries,record):
 idle()
 runtime,entries,record=map(lambda p:Path(p).resolve(),(runtime,entries,record))
 if record.exists():raise ValueError('New deployment record required')
 state=json.loads((runtime/'runtime.json').read_text(encoding='utf-8-sig'))
 for n,h in state['files'].items():
  if sha((runtime/n).read_bytes())!=h:raise ValueError('Runtime drift: '+n)
 payload={n:(entries/n).read_bytes() for n in ('Configure.exe','Game.exe')}
 payload['config/Configure.xaml']=(ROOT/'src/configuration/Configure.xaml').read_bytes()
 for n,b in payload.items():state['files'][n]=sha(b)
 payload['runtime.json']=(json.dumps(state,indent=2)+'\n').encode()
 record.mkdir(parents=True)
 changes={}
 for n,b in payload.items():
  p=runtime/n;old=p.read_bytes() if p.exists() else None
  changes[n]=dict(before=sha(old) if old is not None else None,after=sha(b))
  if old is not None:
   backup=record/'original'/n;backup.parent.mkdir(parents=True,exist_ok=True);backup.write_bytes(old)
 (record/'changes.json').write_text(json.dumps(changes,indent=2))
 try:
  for n,b in payload.items():
   (runtime/n).write_bytes(b)
   if sha((runtime/n).read_bytes())!=changes[n]['after']:raise ValueError('Deployment readback mismatch')
 except Exception:
  rollback(runtime,record,verify=False);raise
 print('DESKTOP_DEPLOY PASS files=4 game_data_changed=false settings_preserved=true')
def rollback(runtime,record,verify=True):
 idle()
 runtime,record=Path(runtime).resolve(),Path(record).resolve()
 changes=json.loads((record/'changes.json').read_text())
 for n,r in changes.items():
  if verify and sha((runtime/n).read_bytes())!=r['after']:raise ValueError('Rollback target drift: '+n)
  if r['before'] is not None and sha((record/'original'/n).read_bytes())!=r['before']:raise ValueError('Rollback source drift: '+n)
 for n,r in changes.items():
  if r['before'] is None:(runtime/n).unlink(missing_ok=True)
  else:(runtime/n).write_bytes((record/'original'/n).read_bytes())
 for n,r in changes.items():
  p=runtime/n
  if (p.exists() if r['before'] is None else sha(p.read_bytes())!=r['before']):raise ValueError('Rollback readback mismatch')
 print('DESKTOP_ROLLBACK PASS files=4 original_bytes=restored new_entries=removed settings_preserved=true')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['apply','rollback']);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--record',type=Path,required=True);p.add_argument('--entries',type=Path)
 a=p.parse_args()
 if a.action=='apply':apply(a.runtime,a.entries,a.record)
 else:rollback(a.runtime,a.record)
