"""Build a corrective update on top of a source-locked installed player package.

Only owned modules and their old package manifest are replaced. The earlier
updater and its rollback journal are deliberately kept in a separate namespace.
"""
import argparse
import json
from pathlib import Path
import zipfile

from build_text_runtime_update import build, sha
from update_runtime_modules import MODULES, check_module

FOLDER = 'ContinueGame-Fix-20261023'
BACKUP = '.continue-game-fix-20261023'


def assemble(previous, module, output, work, previous_sha256, module_sha256):
    previous, module = Path(previous).resolve(), Path(module).resolve()
    output, work = Path(output).resolve(), Path(work).resolve()
    if output.exists() or work.exists() or output.suffix.lower() != '.zip':
        raise ValueError('New ZIP and independent empty work directory required')
    if any(p.is_relative_to(work) for p in (previous, module, output)):
        raise ValueError('Inputs and output must be outside work directory')
    old_zip, native = previous.read_bytes(), module.read_bytes()
    if sha(old_zip) != previous_sha256 or sha(native) != module_sha256:
        raise ValueError('Source hash mismatch')
    check_module(native)
    with zipfile.ZipFile(previous) as archive:
        manifest = json.loads(archive.read('package.json'))
        rows = manifest['files']
        if manifest.get('kind') != 'text_runtime_update' or manifest.get('schema') != 1:
            raise ValueError('Unsupported previous package')
        if len(rows) != 13 or {r['path'] for r in rows} != {*MODULES, 'runtime.json'}:
            raise ValueError('Expected previous owned-module package')
        before = {}
        for row in rows:
            data = archive.read(row['payload'])
            if row['delta'] or sha(data) != row['payload_sha256'] or sha(data) != row['after'] or len(data) != row['size']:
                raise ValueError('Previous package payload mismatch')
            before[row['path']] = data
    runtime_manifest = json.loads(before['runtime.json'])
    if runtime_manifest.get('schema') != 1:
        raise ValueError('Unsupported runtime manifest')
    for name in MODULES:
        if runtime_manifest['files'].get(name) != sha(before[name]):
            raise ValueError('Previous module/manifest mismatch')
        runtime_manifest['files'][name] = module_sha256
    after = {name: native for name in MODULES}
    after['runtime.json'] = (json.dumps(runtime_manifest, indent=2)+'\n').encode()
    states = {}
    for name, data in after.items():
        for folder, raw in [('candidate', data), ('record/original', before[name])]:
            p = work/folder/name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(raw)
        states[name] = dict(before=sha(before[name]), after=sha(data))
    (work/'record/changes.json').write_text(json.dumps(states))
    inner = build(work/'candidate', work/'record', work/'inner.zip')
    with zipfile.ZipFile(inner) as archive:
        payload = {n: archive.read(n) for n in archive.namelist()}
    anchor = b"Located $Runtime '.text-runtime-update'"
    if payload['Update.ps1'].count(anchor) != 1:
        raise ValueError('Updater namespace anchor changed')
    payload['Update.ps1'] = payload['Update.ps1'].replace(anchor, f"Located $Runtime '{BACKUP}'".encode())
    readme = ('继续游戏崩溃修复更新包\r\n'
              '适用：已经安装上一个反馈/连招更新包的用户。不要先撤回旧更新。\r\n'
              '1. 关闭游戏，将压缩包全部内容解压到有 Play.cmd、runtime.json 的共享运行目录。\r\n'
              '2. 双击 Repair-ContinueGame.cmd，等待出现 REPAIR PASS。仅解压不会完成安装。\r\n'
              '3. 再手动运行原来的 Play.cmd。存档、增强设置、上一版撤回记录不会被覆盖。\r\n'
              '请勿只复制 payload 或单个 DLL；脚本会一起校验并更新12份模块与清单。\r\n\r\n'
              'Continue-game crash repair\r\n'
              'For users who installed MagnaCarta-feedback-assist-update-20261023.zip.\r\n'
              'Exit the game. Extract ALL contents into the shared runtime folder\r\n'
              '(the folder containing Play.cmd and runtime.json), then run Repair-ContinueGame.cmd.\r\n'
              'Do not roll back the previous update first. Saves/settings are not replaced.\r\n'
              'The previous updater and its backup remain untouched.\r\n'
              'Rollback: powershell -NoProfile -ExecutionPolicy Bypass -File ContinueGame-Fix-20261023/Update.ps1 -Action Rollback -Runtime .\r\n'
              'Rollback restores the earlier faulty modules; use only for diagnosis.\r\n')
    payload['README.txt'] = readme.encode()
    command = ('@echo off\r\nsetlocal\r\n'
               'set "TARGET=%~dp0."\r\nif not "%~1"=="" set "TARGET=%~1"\r\n'
               f'set "REPAIR=%~dp0{FOLDER}\\Update.ps1"\r\n'
               'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%REPAIR%" -Action CheckInstalled -Runtime "%TARGET%" >nul 2>&1\r\n'
               'if not errorlevel 1 goto success\r\n'
               'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%REPAIR%" -Action Verify -Runtime "%TARGET%"\r\n'
               'if errorlevel 1 goto failed\r\n'
               'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%REPAIR%" -Action Install -Runtime "%TARGET%"\r\n'
               'if errorlevel 1 goto failed\r\n'
               'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%REPAIR%" -Action CheckInstalled -Runtime "%TARGET%"\r\n'
               'if errorlevel 1 goto failed\r\n:success\r\necho REPAIR PASS - use Play.cmd to start manually.\r\npause\r\nexit /b 0\r\n'
               ':failed\r\necho REPAIR FAILED - no game was started.\r\npause\r\nexit /b 1\r\n')
    files = {f'{FOLDER}/{n}': b for n,b in payload.items()}
    files['Repair-ContinueGame.cmd'] = command.encode('ascii')
    files['README-ContinueGame.txt'] = readme.encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2026, 10, 23, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None or {n: archive.read(n) for n in archive.namelist()} != files:
            raise ValueError('ZIP readback mismatch')
    if sha(previous.read_bytes()) != previous_sha256 or sha(module.read_bytes()) != module_sha256:
        raise ValueError('Input drift during packaging')
    output.with_suffix('.zip.sha256').write_text(f'{sha(output.read_bytes())}  {output.name}\n')
    print(f'CONTINUE_GAME_PACKAGE PASS files=13 sha256={sha(output.read_bytes())} previous_backup=preserved game_started=false')
    return output


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('previous', 'module', 'output', 'work'):
        p.add_argument('--'+name, type=Path, required=True)
    for name in ('previous-sha256', 'module-sha256'):
        p.add_argument('--'+name, required=True)
    assemble(**vars(p.parse_args()))
