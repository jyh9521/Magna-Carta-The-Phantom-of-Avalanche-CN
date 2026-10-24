"""Build an opt-in contact/audio observer for a source-locked flat overlay.

Only owned modules, two manifests and the new diagnostic entry change. The
updater retains exact rollback and never includes game assets or settings.
"""
import argparse
import json
from pathlib import Path
import zipfile

from build_text_runtime_update import ROOT, sha
from update_runtime_modules import MODULES, check_module

FOLDER = 'Contact-Audio-Trace-20261024'
BACKUP = '.contact-audio-trace-20261024'
ENTRY = 'Play-contact-audio.cmd'
FILES = (*MODULES, 'runtime.json', 'Overlay-Manifest.json', ENTRY)


def build(previous, module, work, output, previous_sha256):
    previous, module, work, output = [Path(p).resolve() for p in (previous,module,work,output)]
    if (work.exists() or output.exists() or output.suffix != '.zip'
            or any(p.is_relative_to(work) for p in (previous,module,output))):
        raise ValueError('Independent new work directory and ZIP required')
    if sha(previous.read_bytes()) != previous_sha256:
        raise ValueError('Source overlay hash mismatch')
    native = module.read_bytes()
    check_module(native)
    if 'CONTACT_AUDIO_READY'.encode('utf-16le') not in native:
        raise ValueError('Diagnostic module marker missing')
    with zipfile.ZipFile(previous) as z:
        if z.testzip() or ENTRY in z.namelist():
            raise ValueError('Expected unmodified source overlay')
        before = {n:z.read(n) for n in FILES if n != ENTRY}
    runtime = json.loads(before['runtime.json'])
    overlay = json.loads(before['Overlay-Manifest.json'])
    if runtime['data_root'] != '.' or overlay['kind'] != 'clean_game_overlay':
        raise ValueError('Expected flat overlay')
    for n,b in before.items():
        if n != 'Overlay-Manifest.json' and sha(b) != overlay['files'][n]:
            raise ValueError('Overlay manifest mismatch: '+n)
        if n in MODULES and sha(b) != runtime['files'][n]:
            raise ValueError('Runtime manifest mismatch: '+n)
    if ENTRY in runtime['files'] or ENTRY in overlay['files']:
        raise ValueError('Diagnostic entry already registered')
    before[ENTRY] = None
    after = {n:native for n in MODULES}
    after[ENTRY] = (ROOT/'assets/shared-runtime'/ENTRY).read_bytes()
    for n,b in after.items():
        runtime['files'][n] = sha(b)
    after['runtime.json'] = (json.dumps(runtime,indent=2)+'\n').encode()
    for n,b in after.items():
        overlay['files'][n] = sha(b)
    overlay['contact_audio_diagnostic'] = dict(default_enabled=False, module_sha256=sha(native),
        source_sha256={n:sha((ROOT/n).read_bytes()) for n in
            ('src/runtime/contact_audio_trace.cpp','src/runtime/contact_audio_trace.h',
             'src/runtime/workspace_profile.cpp')}, in_game_verified=False)
    after['Overlay-Manifest.json'] = (json.dumps(overlay,ensure_ascii=False,indent=2)+'\n').encode()
    work.mkdir(parents=True)
    payload, rows, blobs = {}, [], {}
    for n in FILES:
        old = before[n]
        if old is not None:
            path = work/'original'/n
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(old)
        digest = sha(after[n])
        key = blobs.setdefault(digest, 'payload/%04d.bin'%len(blobs))
        payload[FOLDER+'/'+key] = after[n]
        rows.append(dict(path=n,before=sha(old) if old is not None else None,after=digest,
            size=len(after[n]),payload=key,payload_sha256=digest,delta=False))
    (work/'changes.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
    package = dict(schema=1,kind='text_runtime_update',files=rows,in_game_verified=False,
        diagnostic_only=True,default_enabled=False,saves_and_settings_preserved=True,
        source_overlay_sha256=previous_sha256)
    payload[FOLDER+'/package.json'] = (json.dumps(package,indent=2)+'\n').encode()
    script = (ROOT/'assets/text-runtime-update/Update.ps1').read_text('utf-8-sig')
    script = script.replace("'.text-runtime-update'", repr(BACKUP))
    anchor = r'runtime\.json|modules/'
    if script.count(anchor)!=1:
        raise ValueError('Updater path anchor drift')
    script = script.replace(anchor,r'Overlay-Manifest\.json|Play-contact-audio\.cmd|runtime\.json|modules/')
    anchor = '$seen=@{};$prepared=@{};$before=@{}'
    if script.count(anchor)!=1:
        raise ValueError('Updater state anchor drift')
    script = script.replace(anchor,"""if($Action -eq 'Install' -and (Test-Path -LiteralPath $marker)){
 $prior=Get-Content -LiteralPath $marker -Raw -Encoding UTF8|ConvertFrom-Json
 if($prior.state -eq 'installed' -and $prior.package_sha256 -ceq (Digest $manifest)){$Action='CheckInstalled'}
}
"""+anchor)
    payload[FOLDER+'/Update.ps1'] = b'\xef\xbb\xbf'+script.encode()
    wrapper = (ROOT/'assets/player-test-package/Fix-Overlay-Launch.cmd').read_bytes()
    wrapper = wrapper.replace(b'Overlay-Launch-Fix-20261023',FOLDER.encode()).replace(
        b'Overlay-Launch-Fix.log',b'Contact-Audio-Install.log').replace(
        b'Applying overlay launch repair...',b'Installing optional contact/audio diagnostics...')
    payload['Install-Contact-Audio.cmd'] = wrapper
    readme = ('碰撞与连招声音诊断包（不是修复包）\r\n'
        '适用：2026-10-23纯净版全合一覆盖包v2；不适用其它模块版本混装。\r\n'
        '关闭游戏，完整解压至原Play.cmd所在目录，双击Install-Contact-Audio.cmd。\r\n'
        '看到MODIFIED PASS后，手动运行新出现的Play-contact-audio.cmd。\r\n'
        '先在水之迷宫中央建筑复现吸入卡死，再尝试反方向移动；退出后立即保留cache/profile.log。\r\n'
        '重新用诊断入口测试一次F10或F11后段缺声，退出后再保留该次cache/profile.log。\r\n'
        '两次日志分别命名，不再启动游戏以免覆盖。附上各自的地图画面或缺声段位录像。\r\n'
        '原Play.cmd默认不开启探针；不改帧数、设置、存档、地图、技能、声音或碰撞结果。\r\n'
        '日志记录原生碰撞响应及采样音效启动/声道占用；尚未证明现场原因或修复。\r\n'
        f'撤回：powershell -NoProfile -ExecutionPolicy Bypass -File {FOLDER}/Update.ps1 -Action Rollback -Runtime .\r\n')
    payload['README-Contact-Audio.txt'] = readme.encode('utf-8')
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for n,b in sorted(payload.items()):
            info=zipfile.ZipInfo(n,(2026,10,24,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,b)
    with zipfile.ZipFile(output) as z:
        if z.testzip() or {n:z.read(n) for n in z.namelist()}!=payload:
            raise ValueError('ZIP readback mismatch')
    if sha(previous.read_bytes())!=previous_sha256 or sha(module.read_bytes())!=sha(native):
        raise ValueError('Input drift')
    output.with_suffix('.zip.sha256').write_text(sha(output.read_bytes())+'  '+output.name+'\n')
    print('CONTACT_AUDIO_PACKAGE PASS files=15 diagnostic_only=true default_enabled=false game_started=false')
    return output


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('previous','module','work','output'):
        p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--previous-sha256',required=True)
    build(**vars(p.parse_args()))
