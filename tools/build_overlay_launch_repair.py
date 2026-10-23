"""Build a four-owned-file launch repair for the first flat overlay release."""
import argparse,json,zipfile,subprocess
from pathlib import Path
from build_text_runtime_update import ROOT,sha
PREVIOUS_SHA256='bb14526bfef32b49edd7a8c0a5dd6694abb1c412d30d52c21ebffc706c3984a5'
FOLDER='Overlay-Launch-Fix-20261023'
BACKUP='.overlay-launch-fix-20261023'
FILES=('modules/workspace_launcher.exe','Start.ps1','runtime.json','Overlay-Manifest.json')
def build(previous,launcher,work,output):
 previous,launcher,work,output=map(lambda p:Path(p).resolve(),(previous,launcher,work,output))
 if work.exists() or output.exists() or any(p.is_relative_to(work) for p in (previous,launcher,output)) or output.suffix!='.zip':raise ValueError('Independent new evidence/output required')
 if sha(previous.read_bytes())!=PREVIOUS_SHA256:raise ValueError('Original flat overlay ZIP mismatch')
 with zipfile.ZipFile(previous) as z:
  if z.testzip():raise ValueError('Original ZIP CRC')
  before={n:z.read(n) for n in FILES}
 native=launcher.read_bytes();start=(ROOT/'src/configuration/StartShared.ps1').read_bytes()
 if '--in-place-overlay'.encode('utf-16le') not in native or b"$args+='--in-place-overlay'" not in start:raise ValueError('Overlay launch route missing')
 runtime=json.loads(before['runtime.json']);overlay=json.loads(before['Overlay-Manifest.json'])
 if runtime['data_root']!='.' or overlay['kind']!='clean_game_overlay':raise ValueError('Expected first flat overlay')
 for n in FILES[:-1]:
  if sha(before[n])!=overlay['files'][n]:raise ValueError('Original overlay manifest mismatch')
 for n in FILES[:2]:
  if sha(before[n])!=runtime['files'][n]:raise ValueError('Original runtime mismatch')
 after={'modules/workspace_launcher.exe':native,'Start.ps1':start}
 for n,b in after.items():runtime['files'][n]=sha(b)
 after['runtime.json']=(json.dumps(runtime,indent=2)+'\n').encode()
 for n,b in after.items():overlay['files'][n]=sha(b)
 overlay['source_commit']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 after['Overlay-Manifest.json']=(json.dumps(overlay,ensure_ascii=False,indent=2)+'\n').encode()
 work.mkdir(parents=True);record=work/'record';record.mkdir();states={};payload={};rows=[]
 for n in FILES:
  p=record/'original'/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(before[n]);states[n]=dict(before=sha(before[n]),after=sha(after[n]));key='payload/%04d.bin'%len(rows)
  payload[FOLDER+'/'+key]=after[n];rows.append(dict(path=n,**states[n],size=len(after[n]),payload=key,payload_sha256=sha(after[n]),delta=False))
 (record/'changes.json').write_text(json.dumps(states,indent=2)+'\n')
 payload[FOLDER+'/package.json']=(json.dumps(dict(schema=1,kind='text_runtime_update',files=rows,in_game_verified=False,saves_and_settings_preserved=True),indent=2)+'\n').encode()
 script=(ROOT/'assets/text-runtime-update/Update.ps1').read_text(encoding='utf-8-sig').replace("'.text-runtime-update'",repr(BACKUP))
 script=script.replace(r'runtime\.json|modules/',r'Overlay-Manifest\.json|Start\.ps1|runtime\.json|modules/',1)
 needle='$seen=@{};$prepared=@{};$before=@{}'
 if script.count(needle)!=1:raise ValueError('Updater anchor drift')
 script=script.replace(needle,"""if($Action -eq 'Install' -and (Test-Path -LiteralPath $marker)){
 $prior=Get-Content -LiteralPath $marker -Raw -Encoding UTF8|ConvertFrom-Json
 if($prior.state -eq 'installed' -and $prior.package_sha256 -ceq (Digest $manifest)){$Action='CheckInstalled'}
}
"""+needle)
 payload[FOLDER+'/Update.ps1']=b'\xef\xbb\xbf'+script.encode()
 payload['Fix-Overlay-Launch.cmd']=(f'@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0{FOLDER}\\Update.ps1" -Runtime "%~dp0."\r\nif errorlevel 1 pause\r\n').encode()
 payload['README-Overlay-Launch-Fix.txt']=('纯净版覆盖包启动修复\r\n适用：MagnaCarta-clean-game-all-in-one-overlay-20261023.zip 已经解压覆盖后的游戏目录。\r\n'
  '退出游戏，完整解压本小包到同一个目录（Play.cmd所在层），双击 Fix-Overlay-Launch.cmd。\r\n'
  '看到 MODIFIED PASS 后使用原 Play.cmd 或 Configure.cmd 启动。不需要重装、移动目录或重下完整包。\r\n'
  '修正 Original install must not be used as workspace 报错，以及检查入口提前返回的问题。\r\n'
  '只更新启动器、启动脚本和两份摘要清单；不改汉化资源、存档、分辨率/帧数设置。\r\n'
  f'撤回：powershell -NoProfile -ExecutionPolicy Bypass -File {FOLDER}/Update.ps1 -Action Rollback -Runtime .\r\n').encode()
 with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for n,b in sorted(payload.items()):z.writestr(n,b)
 with zipfile.ZipFile(output) as z:
  if z.testzip() or {n:z.read(n) for n in z.namelist()}!=payload:raise ValueError('Repair ZIP readback')
 output.with_suffix('.zip.sha256').write_text(sha(output.read_bytes())+'  '+output.name+'\n')
 print('OVERLAY_LAUNCH_REPAIR PASS files=4 bytes='+str(output.stat().st_size)+' sha256='+sha(output.read_bytes()))
 return record
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('previous','launcher','work','output'):p.add_argument('--'+n,type=Path,required=True)
 build(**vars(p.parse_args()))
