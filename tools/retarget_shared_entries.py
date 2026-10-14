"""Retarget recognized owned launch scripts to the shared runtime; never launch/copy game."""
import argparse
import hashlib
import json
from pathlib import Path

ENTRIES={
 'Play-configured.cmd':('StartEnhanced.ps1','','configured'),
 'Play-baseline.cmd':('StartTitle.ps1','-Mode baseline','baseline'),
 'Play-render4k.cmd':('StartTitle.ps1','-Mode render4k','render4k'),
 'Play-wide4k.cmd':('StartTitle.ps1','-Mode wide4k','wide4k'),
 'Play-fps60.cmd':('StartTitle.ps1','-Mode fps60','fps60'),
 'Play-combined.cmd':('StartTitle.ps1','-Mode combined','combined'),
 'Play-60fps-complete.cmd':('StartMotion.ps1','-Mode combined','motion'),
 'Play-30fps.cmd':('StartMotion.ps1','-Mode wide4k','wide4k'),
 'Play-keyboard-mouse.cmd':('StartGamepad.ps1','-Mode combined -NoGamepad','motion'),
 'Play-Xbox-30fps.cmd':('StartGamepad.ps1','-Mode wide4k','gamepad'),
 'Play-Xbox.cmd':('StartGamepad.ps1','-Mode combined','motion-gamepad'),
}

def original(script,args):
 suffix=(' '+args) if args else ''
 return f'@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0.advanced-runtime\\{script}"{suffix}\r\nif errorlevel 1 pause\r\n'.encode('ascii')

def replacement(recipe):
 return f'@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\\Start.ps1" -Recipe {recipe} %*\r\nif errorlevel 1 pause\r\n'.encode('ascii')

def retarget(runtime,apply=False):
 runtime=runtime.resolve(strict=True)
 manifest=json.loads((runtime/'runtime.json').read_text(encoding='utf8'))
 if manifest.get('schema')!=1 or manifest.get('data_root')!='data':raise ValueError('Shared runtime required')
 for name,digest in manifest['files'].items():
  if hashlib.sha256((runtime/name).read_bytes()).hexdigest()!=digest:raise ValueError('Runtime drift: '+name)
 plan=[]
 for name,(script,args,recipe) in ENTRIES.items():
  path=runtime/'data'/name
  if not path.exists():continue
  if path.resolve().parent!=(runtime/'data').resolve():raise ValueError('Owned data entry required')
  if recipe not in manifest['recipes']:raise ValueError('Missing shared recipe: '+recipe)
  before=path.read_bytes();after=replacement(recipe)
  if before not in (original(script,args),after):raise ValueError('Unknown entry preserved: '+name)
  plan.append((path,before,after,recipe))
 configuration=runtime/'data/Configure.cmd'
 if configuration.exists():
  if configuration.resolve().parent!=(runtime/'data').resolve():raise ValueError('Owned configuration entry required')
  before=configuration.read_bytes()
  old=b'@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File "%~dp0.advanced-runtime\\Configure.ps1"\r\nif errorlevel 1 pause\r\n'
  after=b'@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -STA -File "%~dp0..\\config\\Configure.ps1"\r\nif errorlevel 1 pause\r\n'
  if before not in (old,after):raise ValueError('Unknown configuration entry preserved')
  plan.append((configuration,before,after,'configuration-ui'))
 # Validate every entry before any write; do not replace user-customized scripts.
 if apply:
  for path,before,after,recipe in plan:
   if path.read_bytes()!=before:raise ValueError('Entry changed during migration')
  for path,before,after,recipe in plan:
   path.write_bytes(after)
   manifest['files'][path.relative_to(runtime).as_posix()]=hashlib.sha256(after).hexdigest()
  (runtime/'runtime.json').write_bytes((json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf8'))
 return [{'entry':str(p),'recipe':recipe,'changed':before!=after,
          'before_sha256':hashlib.sha256(before).hexdigest(),'after_sha256':hashlib.sha256(after).hexdigest()} for p,before,after,recipe in plan]

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--runtime',type=Path,required=True);parser.add_argument('--apply',action='store_true')
 a=parser.parse_args();result=retarget(a.runtime,a.apply)
 print(json.dumps({'entries':result,'applied':a.apply,'game_started':False,'copied_game_data':False},indent=2))
