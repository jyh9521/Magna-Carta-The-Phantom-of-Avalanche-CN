"""Hash-locked migration of launch scripts and entries to per-install user storage."""
import argparse,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(b):return hashlib.sha256(b).hexdigest()
def migrate_start(blob):
 text=blob.decode('utf-8-sig').replace('\r\n','\n')
 for old,new in [("if(-not $SettingsFile){$SettingsFile=Join-Path $runtimeRoot 'config/enhancements.json'}","if(-not $SettingsFile){$SettingsFile=Initialize-EnhancementUserSettings $runtimeRoot}"),(" $cache=Join-Path $runtimeRoot 'cache'"," $cache=(Get-EnhancementUserPaths $runtimeRoot).Cache")]:
  if text.count(old)==1:text=text.replace(old,new)
  elif text.count(new)!=1:raise ValueError('Unsupported startup migration anchor: '+old)
 return text.replace('see runtime/cache','see user cache').encode('utf-8-sig')
def replacements(start,entries,launcher):
 entries,launcher=Path(entries),Path(launcher)
 native=launcher.read_bytes()
 if not native.startswith(b'MZ') or b'USER_DATA_CACHE_V1' not in native:raise ValueError('Native launcher lacks user-cache guard')
 payload={'Start.ps1':migrate_start(start),'modules/workspace_launcher.exe':native}
 for n in ('Configure.exe','Game.exe'):
  b=(entries/n).read_bytes()
  if not b.startswith(b'MZ') or len(b)>32768:raise ValueError('Invalid small desktop entry')
  payload[n]=b
 for n in ('Configure.ps1','EnhancementSettings.psm1'):payload['config/'+n]=(ROOT/'src/configuration'/n).read_bytes()
 return payload

def apply(runtime,entries,launcher,record):
 runtime,record=Path(runtime).resolve(),Path(record).resolve()
 if record.exists():raise ValueError('New migration record required')
 r=subprocess.run(['powershell.exe','-NoProfile','-Command',"if(Get-Process MagnaCarta,workspace_launcher -ErrorAction SilentlyContinue){exit 9}"],capture_output=True,timeout=20)
 if r.returncode:raise ValueError('Exit active game before migration')
 state=json.loads((runtime/'runtime.json').read_text(encoding='utf-8-sig'))
 if state.get('schema')!=1:raise ValueError('Unsupported runtime schema')
 for n,h in state['files'].items():
  if sha((runtime/n).read_bytes())!=h:raise ValueError('Runtime drift: '+n)
 payload=replacements((runtime/'Start.ps1').read_bytes(),entries,launcher)
 for n,b in payload.items():state['files'][n]=sha(b)
 state['user_storage']=dict(schema=1,kind='localappdata_per_installation',legacy_settings='config/enhancements.json')
 payload['runtime.json']=(json.dumps(state,indent=2)+'\n').encode()
 if (runtime/'Overlay-Manifest.json').exists():
  overlay=json.loads((runtime/'Overlay-Manifest.json').read_text(encoding='utf-8-sig'))
  for n,b in payload.items():overlay['files'][n]=sha(b)
  overlay['user_storage']=state['user_storage'];payload['Overlay-Manifest.json']=(json.dumps(overlay,ensure_ascii=False,indent=2)+'\n').encode()
 record.mkdir(parents=True);changes={}
 for n,b in payload.items():
  p=runtime/n;old=p.read_bytes() if p.exists() else None;changes[n]=dict(before=sha(old) if old is not None else None,after=sha(b))
  if old is not None:
   backup=record/'original'/n;backup.parent.mkdir(parents=True,exist_ok=True);backup.write_bytes(old)
 (record/'changes.json').write_text(json.dumps(changes,indent=2))
 applied=[]
 try:
  for n,b in payload.items():
   (runtime/n).write_bytes(b);applied.append(n)
   if sha((runtime/n).read_bytes())!=changes[n]['after']:raise ValueError('Migration readback mismatch')
 except Exception:
  for n in reversed(applied):
   if changes[n]['before'] is None:(runtime/n).unlink(missing_ok=True)
   else:(runtime/n).write_bytes((record/'original'/n).read_bytes())
  raise
 print(f'USER_STORAGE_DEPLOY PASS files={len(payload)} game_data=unchanged legacy_settings=preserved')
def rollback(runtime,record):
 runtime,record=Path(runtime).resolve(),Path(record).resolve();changes=json.loads((record/'changes.json').read_text())
 for n,r in changes.items():
  if sha((runtime/n).read_bytes())!=r['after']:raise ValueError('Rollback target drift: '+n)
  if r['before'] is not None and sha((record/'original'/n).read_bytes())!=r['before']:raise ValueError('Rollback source drift: '+n)
 for n,r in reversed(list(changes.items())):
  if r['before'] is None:(runtime/n).unlink()
  else:(runtime/n).write_bytes((record/'original'/n).read_bytes())
 for n,r in changes.items():
  p=runtime/n
  if (p.exists() if r['before'] is None else sha(p.read_bytes())!=r['before']):raise ValueError('Rollback readback mismatch')
 print('USER_STORAGE_ROLLBACK PASS original_files=exact migrated_user_preferences=preserved')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['apply','rollback'])
 for n in ('runtime','record'):p.add_argument('--'+n,type=Path,required=True)
 for n in ('entries','launcher'):p.add_argument('--'+n,type=Path)
 a=p.parse_args()
 if a.action=='apply':apply(a.runtime,a.entries,a.launcher,a.record)
 else:rollback(a.runtime,a.record)
