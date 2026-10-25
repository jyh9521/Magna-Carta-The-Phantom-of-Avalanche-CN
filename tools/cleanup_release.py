"""Remove superseded delivery archives while preserving accepted inputs and engineering evidence."""
import argparse,hashlib,json,subprocess,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
KEEP=('MagnaCarta-zh-CN-v1.0.zip','MagnaCarta-clean-game-caption-complete-test-20261025.zip','MagnaCarta-unified-test-hud-fix-20261023.zip')
def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def checked(p):
 p=p.resolve()
 if not p.is_relative_to(ROOT) or p==ROOT or p.is_symlink() or p.is_junction():raise ValueError('Cleanup path escaped workspace')
 return p

def clean(apply=False):
 kept={}
 for n in KEEP:
  p=checked(ROOT/'dist'/n)
  with zipfile.ZipFile(p) as z:
   if z.testzip():raise ValueError('Retained archive CRC mismatch')
  kept[str(p)]=sha(p)
 with zipfile.ZipFile(ROOT/'dist'/KEEP[0]) as z:
  if json.loads(z.read('Overlay-Manifest.json'))['status']!='released':raise ValueError('Release manifest required')
 state=json.loads((ROOT/'runtime/runtime.json').read_text(encoding='utf-8-sig'))
 for n,h in state['files'].items():
  if sha(ROOT/'runtime'/n)!=h:raise ValueError('Runtime dependency drift: '+n)
 saves={str(p):sha(p) for p in (ROOT/'runtime').rglob('*.sav')}
 targets=[]
 keepnames={n for f in KEEP for n in (f,f+'.sha256')}
 for p in (ROOT/'dist').iterdir():
  if p.is_file() and p.name not in keepnames:
   checked(p)
   if subprocess.check_output(['git','ls-files','--',str(p.relative_to(ROOT))],cwd=ROOT):raise ValueError('Tracked cleanup target')
   targets.append(p)
 report=dict(mode='apply' if apply else 'plan',targets=[str(p) for p in targets],removed_bytes=sum(p.stat().st_size for p in targets),retained=kept,saves=len(saves),build_evidence='preserved',original_discs='preserved',game_data='preserved')
 e=ROOT/'build/release-v1.0-evidence';e.mkdir(exist_ok=True,parents=True)
 (e/('cleanup-'+report['mode']+'.json')).write_text(json.dumps(report,indent=2),encoding='utf8')
 for p in targets:
  print(('REMOVE ' if apply else 'PLAN ')+str(p))
  if apply:p.unlink()
 if apply:
  for n,h in kept.items():
   if sha(Path(n))!=h:raise ValueError('Retained archive changed')
  for n,h in saves.items():
   if sha(Path(n))!=h:raise ValueError('Save changed')
 print(f'RELEASE_CLEANUP PASS mode={report["mode"]} archives_and_checksums={len(targets)} bytes={report["removed_bytes"]} saves={len(saves)} rollback_evidence=preserved')
 return report
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--apply',action='store_true');clean(p.parse_args().apply)
