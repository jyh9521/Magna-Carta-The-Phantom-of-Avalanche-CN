"""Promote a hash-locked accepted flat overlay to v1.0 with compact desktop entries."""
import argparse,hashlib,json,subprocess,zipfile
from pathlib import Path
from build_clean_overlay import safe_name,raw_sha
ROOT=Path(__file__).resolve().parents[1]
README='''《真名法典：冰之魅影》简体中文汉化＋最终修复版 v1.0
发布版本：v1.0。2026-10-25 已收到完整流程通关且测试无误的验收反馈。

将 ZIP 全部内容解压到匹配的纯净游戏目录（MagnaCarta.exe 所在层），替换同名文件。
原版独立备份须保留；发布包只包含汉化、修改资源及运行组件，不包含完整游戏。
双击 Configure.exe 调整配置，双击 Game.exe 启动游戏。
Windows 自带 .NET Framework 4.x、Windows PowerShell 5.1 和 WPF 提供外置依赖，无需安装 Python。
config、modules、fonts、maps 等目录及 Start.ps1 为运行依赖，须随 EXE 一同保留。
默认 1080P、无边框、60 帧；配置工具保留 30/60 帧等选择。
F5 切换随机遇敌，F10 普通连招辅助，F11 暴走连招辅助，F8/F9 地图。
手柄与自由视角研究功能不包含在正式功能范围内。

文件检查：powershell -NoProfile -ExecutionPolicy Bypass -File Verify-Overlay.ps1 -Action CheckInstalled
恢复原版：powershell -NoProfile -ExecutionPolicy Bypass -File Verify-Overlay.ps1 -Action Rollback -Source "原版备份目录"
恢复预检覆盖资源摘要，保留存档与设置；恢复后使用原版游戏入口。
出现启动错误时检查 cache/Game.log、cache/Configure.log 及 cache/profile.log。
游戏验收基于通关反馈；EXE 入口与紧凑界面另经离线验证，不冒充新增游戏画面验收。
'''
def build(source,source_sha256,entries,output):
 source,entries,output=map(lambda p:Path(p).resolve(),(source,entries,output))
 if output.exists() or output==source or output.suffix!='.zip':raise ValueError('New ZIP path required')
 if raw_sha(source.read_bytes())!=source_sha256:raise ValueError('Accepted archive hash mismatch')
 with zipfile.ZipFile(source) as z:
  if z.testzip():raise ValueError('Accepted archive CRC mismatch')
  if len(z.namelist())!=len(set(n.casefold() for n in z.namelist())):raise ValueError('Duplicate archive paths')
  payload={safe_name(n):z.read(n) for n in z.namelist()}
 original=json.loads(payload.pop('Overlay-Manifest.json'))
 if original.get('kind')!='clean_game_overlay' or original.get('layout')!='flat':raise ValueError('Unsupported accepted archive')
 if {n:raw_sha(b) for n,b in payload.items()}!=original['files']:raise ValueError('Accepted overlay manifest mismatch')
 runtime=json.loads(payload['runtime.json'])
 for n,h in runtime['files'].items():
  if n not in payload or raw_sha(payload[n])!=h:raise ValueError('Runtime dependency mismatch: '+n)
 before={r['resource']:raw_sha(payload[r['resource']]) for r in original['changes']}
 for n,h in before.items():
  if h!=next(r['target_sha256'] for r in original['changes'] if r['resource']==n):raise ValueError('Accepted resource mismatch')
 for n in list(payload):
  if n.lower().endswith('.cmd'):payload.pop(n);runtime['files'].pop(n,None)
 for name in ('Configure.exe','Game.exe'):
  b=(entries/name).read_bytes()
  if not b.startswith(b'MZ') or len(b)>32768:raise ValueError('Invalid desktop entry')
  payload[name]=b;runtime['files'][name]=raw_sha(b)
 n='config/Configure.xaml';payload[n]=(ROOT/'src/configuration/Configure.xaml').read_bytes();runtime['files'][n]=raw_sha(payload[n])
 runtime['release']=dict(version='1.0',status='released',acceptance='completed_playthrough_report',date='2026-10-25',configure_entry='Configure.exe',game_entry='Game.exe')
 if runtime.get('test_candidates'):
  runtime['test_candidates']['stable_entry']='Start.ps1 -WithoutTestCandidates'
 if runtime.get('collision_guard'):runtime['collision_guard']['entry']='Game.exe'
 payload['runtime.json']=(json.dumps(runtime,indent=2)+'\n').encode()
 payload['README-Overlay.txt']=README.encode('utf-8-sig')
 for n in ('licenses/LICENSE','licenses/LICENSE-translations.md','licenses/LICENSING.md'):
  if n in payload:payload[n]=(ROOT/Path(n).name).read_bytes()
 manifest=dict(original)
 manifest.update(version='1.0',status='released',in_game_verified=True,acceptance=dict(kind='completed_playthrough_report',date='2026-10-25',automated_game_launch=False),accepted_archive_sha256=source_sha256,source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),files={n:raw_sha(b) for n,b in payload.items()})
 if manifest.get('test_candidates'):manifest['test_candidates']=runtime['test_candidates']
 if any(raw_sha(payload[n])!=h for n,h in before.items()):raise ValueError('Accepted game resources changed')
 payload['Overlay-Manifest.json']=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode()
 output.parent.mkdir(parents=True,exist_ok=True)
 with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  for n,b in sorted(payload.items()):
   info=zipfile.ZipInfo(n,date_time=(2026,10,25,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
   z.writestr(info,b,compress_type=zipfile.ZIP_DEFLATED,compresslevel=6)
 with zipfile.ZipFile(output) as z:
  if z.testzip() or {n:raw_sha(z.read(n)) for n in z.namelist()}!={n:raw_sha(b) for n,b in payload.items()}:raise ValueError('Release readback mismatch')
 h=raw_sha(output.read_bytes());output.with_suffix('.zip.sha256').write_text(h+'  '+output.name+'\n')
 print(f'RELEASE_V1 PASS resources={len(before)} files={len(payload)} cmd_entries=0 accepted_resources=unchanged sha256={h}')
 return manifest
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('source','entries','output'):p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--source-sha256',required=True)
 build(**vars(p.parse_args()))
