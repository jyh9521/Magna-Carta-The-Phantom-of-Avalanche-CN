"""Source-lock a HUD-only hotfix to the delivered release-controls update."""
import argparse,json,zipfile
from pathlib import Path
from build_text_runtime_update import sha,ROOT
from update_runtime_modules import MODULES,check_module
FOLDER='Encounter-HUD-Compact-20261023'
BACKUP='.encounter-hud-compact-20261023'
PREVIOUS_SHA256='0a11e74a4e7963f9c8100164b329f8e4bf0fbee9f62110a52fcf11d98afc53c2'
CHANGES=(*MODULES,'runtime.json')

def prepare(previous,module,work,output,f11=None):
 previous,module,work,output=map(lambda p:Path(p).resolve(),(previous,module,work,output))
 if work.exists() or output.exists() or any(p.is_relative_to(work) for p in (previous,module,output)) or output.suffix!='.zip':raise ValueError('Independent new output required')
 if sha(previous.read_bytes())!=PREVIOUS_SHA256:raise ValueError('Delivered baseline mismatch')
 native=module.read_bytes();check_module(native)
 f11_rows=None
 if f11 is not None:
  f11=Path(f11).resolve()
  if sha(f11.read_bytes())!='040eb0bcad096cd78fb64be85ba8b6606b352ba47757fb27f943ecf6c82a6a33':raise ValueError('F11 baseline mismatch')
  with zipfile.ZipFile(f11) as z:
   if z.testzip():raise ValueError('F11 CRC failure')
   names=[n for n in z.namelist() if n.endswith('/package.json')]
   if len(names)!=1:raise ValueError('F11 manifest count')
   name=names[0];prefix=name.rsplit('/',1)[0]+'/'
   f11_rows=json.loads(z.read(name))['files']
   for row in f11_rows:
    if sha(z.read(prefix+row['payload']))!=row['after']:raise ValueError('F11 payload drift')
 with zipfile.ZipFile(previous) as z:
  if z.testzip():raise ValueError('Baseline CRC failure')
  pm=json.loads(z.read('Release-Controls-20261023/package.json'));before={}
  if f11_rows is not None:
   prior={r['path']:r['after'] for r in f11_rows};next_before={r['path']:r['before'] for r in pm['files']}
   if set(prior)!=set(CHANGES) or any(next_before.get(n)!=h for n,h in prior.items()):raise ValueError('F11 to release-controls chain mismatch')
  for r in pm['files']:
   b=z.read('Release-Controls-20261023/'+r['payload'])
   if r['delta'] or sha(b)!=r['after'] or sha(b)!=r['payload_sha256'] or len(b)!=r['size']:raise ValueError('Baseline payload drift')
   before[r['path']]=b
 if not set(CHANGES)<=before.keys():raise ValueError('Baseline file set')
 manifest=json.loads(before['runtime.json'])
 for n in MODULES:
  if sha(before[n])!=manifest['files'][n]:raise ValueError('Baseline manifest mismatch')
  manifest['files'][n]=sha(native)
 after={n:native for n in MODULES};after['runtime.json']=(json.dumps(manifest,indent=2)+'\n').encode()
 work.mkdir(parents=True);record=work/'record';record.mkdir();states={};payload={};rows=[];blobs={}
 for n in CHANGES:
  p=record/'original'/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(before[n])
  states[n]=dict(before=sha(before[n]),after=sha(after[n]))
  digest=sha(after[n]);key=blobs.get(digest)
  if key is None:
   key='payload/%04d.bin'%len(blobs);blobs[digest]=key;payload[FOLDER+'/'+key]=after[n]
  rows.append(dict(path=n,**states[n],size=len(after[n]),payload=key,payload_sha256=sha(after[n]),delta=False))
 (record/'changes.json').write_text(json.dumps(states,indent=2)+'\n')
 payload[FOLDER+'/package.json']=(json.dumps(dict(schema=1,kind='text_runtime_update',files=rows,in_game_verified=False,saves_and_settings_preserved=True),indent=2)+'\n').encode()
 script=(ROOT/'assets/text-runtime-update/Update.ps1').read_text(encoding='utf-8-sig').replace("'.text-runtime-update'",repr(BACKUP))
 needle='$seen=@{};$prepared=@{};$before=@{}'
 if script.count(needle)!=1:raise ValueError('Updater anchor drift')
 script=script.replace(needle,"""if($Action -eq 'Install' -and (Test-Path -LiteralPath $marker)){
 $prior=Get-Content -LiteralPath $marker -Raw -Encoding UTF8|ConvertFrom-Json
 if($prior.state -eq 'installed' -and $prior.package_sha256 -ceq (Digest $manifest)){$Action='CheckInstalled'}
}
"""+needle)
 payload[FOLDER+'/Update.ps1']=b'\xef\xbb\xbf'+script.encode()
 payload['Update-Encounter-HUD.cmd']=(f'@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0{FOLDER}\\Update.ps1" -Runtime "%~dp0."\r\nif errorlevel 1 pause\r\n').encode()
 payload['README-Encounter-HUD.txt']=('遇敌提示修复 2026-10-23\r\n适用：已经依次安装 MagnaCarta-rage-F11-update-20261023.zip 和 MagnaCarta-release-controls-20261023.zip 的测试版。\r\n'
  '退出游戏，把本包全部内容解压到有 Play.cmd 和 runtime.json 的目录，双击 Update-Encounter-HUD.cmd。\r\n'
  '看到 MODIFIED PASS 后照常用 Play.cmd。仅更新12个自有模块和运行清单。\r\n'
  'F5切换时右下角短暂显示1.8秒；平时不显示，不再常驻顶部。文字先离屏绘制，再整体提交。\r\n'
  '遇敌逻辑、插帧、F10/F11、存档和设置保持不变；旧更新的回滚目录保留。\r\n'
  '离线消息回放已通过；游戏内最终画面由测试者检查。\r\n'
  f'撤回本修复：powershell -NoProfile -ExecutionPolicy Bypass -File {FOLDER}/Update.ps1 -Action Rollback -Runtime .\r\n').encode()
 output.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for n,b in sorted(payload.items()):z.writestr(n,b)
 with zipfile.ZipFile(output) as z:
  if z.testzip() or {n:z.read(n) for n in z.namelist()}!=payload:raise ValueError('Output readback failed')
 output.with_suffix('.zip.sha256').write_text(sha(output.read_bytes())+'  '+output.name+'\n')
 (work/'provenance.json').write_text(json.dumps(dict(previous_sha256=PREVIOUS_SHA256,module_sha256=sha(native),unique_payloads=len(blobs),f11_chain_verified=f11_rows is not None,game_data_copied=False),indent=2)+'\n')
 print('ENCOUNTER_HUD_PACKAGE PASS baseline=delivered_release_controls files=13 sha256='+sha(output.read_bytes())+' game_started=false')
 return record
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--f11',type=Path)
 for n in ('previous','module','work','output'):p.add_argument('--'+n,type=Path,required=True)
 prepare(**vars(p.parse_args()))
