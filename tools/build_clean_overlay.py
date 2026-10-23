"""Build a flat extract-and-overwrite package from source-locked changed files only."""
import argparse,hashlib,json,subprocess,zipfile
from pathlib import Path
from build_player_test_bundle import ROOT,sha,validate_engine_fixes
from refresh_player_package import ARCHIVED

def raw_sha(b):return hashlib.sha256(b).hexdigest()
def safe_name(n):
 if not isinstance(n,str) or not n or n.startswith('/') or any(x in n for x in ('\\',':','\x00')) or any(v in ('','.','..') for v in n.split('/')):raise ValueError('Invalid package path')
 return n
def build(previous,previous_sha256,runtime,output):
 previous,runtime,output=map(lambda p:Path(p).resolve(),(previous,runtime,output))
 if output.exists() or output.suffix!='.zip' or output.is_relative_to(runtime) or output==previous:raise ValueError('Independent new archive required')
 if sha(previous)!=previous_sha256:raise ValueError('Source package drift')
 current=json.loads((runtime/'runtime.json').read_text(encoding='utf-8-sig'))
 for section,root in [('files',runtime),('data',runtime/'data')]:
  for n,h in current[section].items():
   safe_name(n)
   if sha(root/n)!=h:raise ValueError('Runtime drift: '+n)
 release=json.loads(json.dumps(current));release['data_root']='.'
 archived={'Play-'+n+'.cmd' for n in ARCHIVED}
 for n in ARCHIVED:release['recipes'].pop(n,None)
 release['archived_features']=['native_gamepad','free_view']
 payload={n:(runtime/n).read_bytes() for n in current['files'] if not n.startswith('data/') and n not in archived}
 for n in list(release['files']):
  if n.startswith('data/') or n in archived:release['files'].pop(n)
 for p in runtime.glob('Play*.cmd'):
  if p.name not in archived:payload[p.name]=p.read_bytes()
 payload['Configure.cmd']=(runtime/'Configure.cmd').read_bytes()
 payload['Start.ps1']=(ROOT/'src/configuration/StartShared.ps1').read_bytes()
 if '--in-place-overlay'.encode('utf-16le') not in payload.get('modules/workspace_launcher.exe',b''):raise ValueError('Flat-capable native launcher required')
 if b"$layout -notin @('data','.')" not in payload['Start.ps1']:raise ValueError('Flat layout launcher unavailable')
 release['files']['Start.ps1']=raw_sha(payload['Start.ps1'])
 payload['config/enhancements.json']=(json.dumps(dict(schema=2,resolution='1080p',window_mode='borderless',frame_rate=30,native_gamepad=False,free_view=False,window_resolution='1280x720'),indent=2)+'\n').encode()
 with zipfile.ZipFile(previous) as old:
  if old.testzip():raise ValueError('Source ZIP CRC')
  base=json.loads(old.read('package.json'))
  for row in base['changes']:
   n=safe_name(row['resource']);p=runtime/'data'/n
   if (base['source_files'].get(n)!=row['source_sha256'] or row['source_sha256']==row['target_sha256'] or sha(p)!=row['target_sha256'] or raw_sha(old.read(row['patch']))!=row['patch_sha256']):raise ValueError('Changed resource drift: '+n)
   if n.lower().endswith(('.sav','.log')) or n in payload:raise ValueError('Resource collision/protected input')
   blob=p.read_bytes()
   if raw_sha(blob)!=row['target_sha256'] or len(blob)!=row['target_size']:raise ValueError('Resource changed during read: '+n)
   payload[n]=blob
  for n in ('ddraw.dll','DDrawCompat-MagnaCarta.ini'):payload[n]=old.read('payload/data/'+n)
  for n in old.namelist():
   if n.startswith('licenses/'):payload[n]=old.read(n)
 for n,h in release['data'].items():
  effective=raw_sha(payload[n]) if n in payload else base['source_files'].get(n)
  if effective!=h:raise ValueError('Overlay+pristine data dependency mismatch: '+n)
 for n,h in release['files'].items():
  if n not in payload or raw_sha(payload[n])!=h:raise ValueError('Overlay runtime dependency mismatch: '+n)
 payload['runtime.json']=(json.dumps(release,indent=2)+'\n').encode()
 payload['Verify-Overlay.ps1']=(ROOT/'assets/player-test-package/Verify-Overlay.ps1').read_bytes()
 for name,action in [('Verify-Overlay.cmd','CheckInstalled'),('Restore-Original.cmd','Rollback')]:
  payload[name]=(f'@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Verify-Overlay.ps1" -Action {action} %*\r\nif errorlevel 1 pause\r\n').encode()
 payload['README-Overlay.txt']=('《真名法典：冰之魅影》纯净版完整覆盖测试包\r\n'
  '包含当前汉化（正文、图片、字体、视频字幕）及全部现行现代化改造和修复；不需要任何历史补丁。\r\n'
  '把本ZIP内全部文件和文件夹解压到纯净游戏目录（MagnaCarta.exe所在层），选择替换同名文件。\r\n'
  '保留测试者已有的纯净备份，不要覆盖唯一备份。包内不是完整游戏，不含未修改的游戏资源。\r\n'
  '解压完成直接双击本层 Play.cmd 启动，Configure.cmd 设置分辨率、窗口模式及30/60帧。\r\n'
  '不需要 Install.cmd、Python、旧更新包或移动到data目录。不要直接启动原 MagnaCarta.exe。\r\n'
  '默认1080P、无边框、30帧、键鼠；可选择60帧。手柄和自由视角已经归档，不包含在现行功能中。\r\n'
  'F10普通连招辅助、F11暴走辅助；F5随机遇敌开关默认开启，切换后右下角短提示1.8秒。\r\n'
  '包含四类模型插帧、宽屏与高分辨率文字、高清标题/图片、继续游戏/键鼠、楼梯/GUI等既有修正及当前F5提示候选。\r\n'
  '所有候选的游戏画面仍由测试者确认；F5提示消失问题正在复核；换区崩溃和眼球偶发外突未宣称修复。\r\n'
  '可选双击 Verify-Overlay.cmd 检查覆盖文件。cache/profile.log保留运行记录。\r\n'
  '撤回：双击 Restore-Original.cmd，输入独立纯净备份目录；先完整预检摘要，再恢复覆盖的原资源。\r\n'
  '回滚保留存档、个人设置、显示INI和日志；恢复后使用原游戏入口，现代化入口会按版本锁拒绝原资源。\r\n').encode()
 manifest=dict(schema=1,kind='clean_game_overlay',layout='flat',source_files=base['source_files'],changes=[{k:r[k] for k in ('resource','source_sha256','target_sha256','target_size')} for r in base['changes']],files={n:raw_sha(b) for n,b in payload.items()},source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),previous_sha256=previous_sha256,in_game_verified=False,engine_fixes=validate_engine_fixes(runtime,current))
 payload['Overlay-Manifest.json']=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode()
 names=[n.casefold() for n in payload]
 if len(names)!=len(set(names)) or any(n.startswith(('data/','payload/','deltas/','cache/')) or n.endswith(('.sav','.log')) for n in names):raise ValueError('Invalid flat overlay file set')
 output.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for n,b in sorted(payload.items()):z.writestr(n,b)
 with zipfile.ZipFile(output) as z:
  if z.testzip() or {n:raw_sha(z.read(n)) for n in z.namelist()}!={n:raw_sha(b) for n,b in payload.items()}:raise ValueError('ZIP readback failed')
 if sha(previous)!=previous_sha256:raise ValueError('Source archive changed')
 output.with_suffix('.zip.sha256').write_text(sha(output)+'  '+output.name+'\n')
 print('CLEAN_OVERLAY PASS changed_resources='+str(len(base['changes']))+' files='+str(len(payload))+' bytes='+str(output.stat().st_size)+' sha256='+sha(output)+' game_started=false full_game_copy=false')
 return manifest
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('previous','runtime','output'):p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--previous-sha256',required=True)
 build(**vars(p.parse_args()))
