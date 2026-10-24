"""Build a reversible opt-in audio policy update for the installed observer version."""
import argparse
import json
from pathlib import Path
import zipfile
from build_text_runtime_update import ROOT, sha
from update_runtime_modules import MODULES, check_module

FOLDER = 'Audio-Provider-Fix-20261024'
BACKUP = '.audio-provider-fix-20261024'
ENTRY = 'Play-audio-fix.cmd'
FILES = (*MODULES, 'runtime.json', 'Overlay-Manifest.json', ENTRY)


def read_previous(path, expected):
    if sha(path.read_bytes()) != expected:
        raise ValueError('Diagnostic package hash mismatch')
    with zipfile.ZipFile(path) as z:
        if z.testzip():
            raise ValueError('Diagnostic ZIP integrity')
        folder = 'Contact-Audio-Trace-20261024/'
        m = json.loads(z.read(folder+'package.json'))
        rows = m['files']
        if (not m.get('diagnostic_only') or len(rows) != 15
                or {r['path'] for r in rows} != {*MODULES, 'runtime.json', 'Overlay-Manifest.json', 'Play-contact-audio.cmd'}):
            raise ValueError('Expected complete observer package')
        before = {}
        for row in rows:
            blob = z.read(folder+row['payload'])
            if row['delta'] or sha(blob) != row['after'] or sha(blob) != row['payload_sha256'] or len(blob) != row['size']:
                raise ValueError('Observer payload mismatch')
            before[row['path']] = blob
    return before


def build(previous, previous_sha256, module, work, output, policy='audio'):
    if policy not in ('audio', 'blockers'):
        raise ValueError('Unknown update policy')
    FOLDER, BACKUP, ENTRY = (('Audio-Provider-Fix-20261024', '.audio-provider-fix-20261024', 'Play-audio-fix.cmd')
        if policy == 'audio' else ('Blocker-Trace-20261024', '.blocker-trace-20261024', 'Play-contact-audio.cmd'))
    FILES = (*MODULES, 'runtime.json', 'Overlay-Manifest.json', ENTRY)
    previous, module, work, output = [Path(x).resolve() for x in (previous, module, work, output)]
    if work.exists() or output.exists() or output.suffix != '.zip' or any(x.is_relative_to(work) for x in (previous, module, output)):
        raise ValueError('Independent new output paths required')
    before = read_previous(previous, previous_sha256)
    native = module.read_bytes()
    check_module(native)
    for marker in ('AUDIO_PROVIDER_POLICY_READY' if policy == 'audio' else 'BLOCKER_TRACE_READY', 'CONTACT_AUDIO_READY'):
        if marker.encode('utf-16le') not in native:
            raise ValueError('Candidate marker missing')
    runtime = json.loads(before['runtime.json'])
    overlay = json.loads(before['Overlay-Manifest.json'])
    if (runtime['data_root'] != '.' or overlay['kind'] != 'clean_game_overlay'
            or (policy == 'audio' and (ENTRY in runtime['files'] or ENTRY in overlay['files']))):
        raise ValueError('Expected installed flat observer baseline')
    for n, blob in before.items():
        if n != 'Overlay-Manifest.json' and overlay['files'].get(n) != sha(blob):
            raise ValueError('Observer overlay mismatch')
        if n in MODULES and runtime['files'].get(n) != sha(blob):
            raise ValueError('Observer runtime mismatch')
    after = {n:native for n in MODULES}
    after[ENTRY] = (ROOT/'assets/shared-runtime'/ENTRY).read_bytes()
    for n, blob in after.items():
        runtime['files'][n] = sha(blob)
    after['runtime.json'] = (json.dumps(runtime, indent=2)+'\n').encode()
    for n, blob in after.items():
        overlay['files'][n] = sha(blob)
    overlay['contact_audio_diagnostic']['module_sha256'] = sha(native)
    overlay['contact_audio_diagnostic']['source_sha256'] = {n:sha((ROOT/n).read_bytes()) for n in
        ('src/runtime/contact_audio_trace.cpp', 'src/runtime/contact_audio_trace.h', 'src/runtime/workspace_profile.cpp')}
    metadata = dict(default_enabled=False, in_game_verified=False,
        preferred='DirectSound3D 7+ Software - Pan and Volume', native_fallback=True,
        capacity='provider_reported', source_sha256={n:sha((ROOT/n).read_bytes()) for n in
            ('src/runtime/audio_provider_policy.cpp', 'src/runtime/audio_provider_policy.h', 'src/runtime/workspace_profile.cpp')})
    if policy == 'audio':
        overlay['audio_provider_policy'] = metadata
    else:
        overlay['blocker_trace'] = dict(default_enabled=False, read_only=True,
            scene_gates=True, native_fades=4, no_extra_collision_queries=True,
            source_sha256=overlay['contact_audio_diagnostic']['source_sha256'])
    after['Overlay-Manifest.json'] = (json.dumps(overlay, ensure_ascii=False, indent=2)+'\n').encode()
    before.setdefault(ENTRY, None)
    work.mkdir(parents=True)
    payload, rows, dedup = {}, [], {}
    for n in FILES:
        old = before[n]
        if old is not None:
            p = work/'original'/n
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(old)
        blob = after[n]
        digest = sha(blob)
        key = dedup.setdefault(digest, f'payload/{len(dedup):04d}.bin')
        payload[FOLDER+'/'+key] = blob
        rows.append(dict(path=n, before=sha(old) if old is not None else None, after=digest,
            size=len(blob), payload=key, payload_sha256=digest, delta=False))
    manifest = dict(schema=1, kind='text_runtime_update', files=rows, in_game_verified=False,
        default_enabled=False, source_diagnostic_sha256=previous_sha256,
        saves_and_settings_preserved=True)
    payload[FOLDER+'/package.json'] = (json.dumps(manifest, indent=2)+'\n').encode()
    (work/'changes.json').write_text(json.dumps(rows, indent=2)+'\n')
    script = (ROOT/'assets/text-runtime-update/Update.ps1').read_text('utf-8-sig')
    script = script.replace("'.text-runtime-update'", repr(BACKUP))
    anchor = r'runtime\.json|modules/'
    if script.count(anchor) != 1:
        raise ValueError('Updater allow-list anchor drift')
    escaped_entry = ENTRY.replace('.', r'\.')
    script = script.replace(anchor, r'Overlay-Manifest\.json|'+escaped_entry+r'|runtime\.json|modules/')
    anchor = '$seen=@{};$prepared=@{};$before=@{}'
    if script.count(anchor) != 1:
        raise ValueError('Updater state anchor drift')
    script = script.replace(anchor, """if($Action -eq 'Install' -and (Test-Path -LiteralPath $marker)){
 $prior=Get-Content -LiteralPath $marker -Raw -Encoding UTF8|ConvertFrom-Json
 if($prior.state -eq 'installed' -and $prior.package_sha256 -ceq (Digest $manifest)){$Action='CheckInstalled'}
}
"""+anchor)
    payload[FOLDER+'/Update.ps1'] = b'\xef\xbb\xbf'+script.encode()
    wrapper = (ROOT/'assets/player-test-package/Fix-Overlay-Launch.cmd').read_bytes()
    wrapper = wrapper.replace(b'Overlay-Launch-Fix-20261023', FOLDER.encode()).replace(
        b'Overlay-Launch-Fix.log', b'Audio-Provider-Install.log').replace(
        b'Applying overlay launch repair...', b'Installing opt-in audio provider candidate...')
    if policy == 'blockers':
        wrapper = wrapper.replace(b'Audio-Provider-Install.log', b'Blocker-Trace-Install.log').replace(
            b'Installing opt-in audio provider candidate...', b'Installing read-only scene and collision observations...')
    payload['Install-Audio-Fix.cmd' if policy == 'audio' else 'Install-Blocker-Trace.cmd'] = wrapper
    payload['README-Audio-Fix.txt'] = ("声音候选修复包；黑屏和卡墙尚未修复。\r\n"
        "适用：已成功安装2026-10-24碰撞与声音诊断包的覆盖版；其它版本会拒绝安装。\r\n"
        "退出游戏，完整解压至原Play.cmd所在目录，双击Install-Audio-Fix.cmd。\r\n"
        "出现MODIFIED PASS后，手动运行新入口Play-audio-fix.cmd。原Play.cmd不启用这项候选。\r\n"
        "候选优先尝试随游戏提供的DS3D7软件Pan and Volume后端；失败则保留全部原生后端顺序。\r\n"
        "声道数量仍由后端报告并由原引擎分配；不强改容量、不抢占播放、不替换声音文件。\r\n"
        "本地原生离线测试声道池8→56，16个并发分配8→16；这不等于角色F11已通过游戏实测。\r\n"
        "复测佩里西亚F11及其他角色F10/F11，退出后保留cache/profile.log和缺声段位录像。\r\n"
        "日志应包含AUDIO_PROVIDER_POLICY_SELECTED，后续声音记录可查看slots_capacity及失败数。\r\n"
        "不更改存档、设置、场景资源、技能、碰撞、动作及播放时序。\r\n"
        f"撤回：powershell -NoProfile -ExecutionPolicy Bypass -File {FOLDER}/Update.ps1 -Action Rollback -Runtime .\r\n").encode('utf-8')
    if policy == 'blockers':
        payload.pop('README-Audio-Fix.txt')
        payload['README-Blocker-Trace.txt'] = ("黑屏与卡墙补充状态记录；不是修复包，不测试音效。\r\n"
            "适用：已成功安装2026-10-24碰撞/声音诊断包的平铺版；其它模块会拒绝混装。\r\n"
            "原始存档与profile.log已保留；上一份探针缺少淡出层状态，本包补充四个全屏层及场景控制状态。\r\n"
            "退出游戏，完整解压至原Play.cmd目录，运行Install-Blocker-Trace.cmd，看到MODIFIED PASS后\r\n"
            "手动运行Play-contact-audio.cmd，读同一个原存档，往前触发整屏黑屏后停留约3秒，再退出。\r\n"
            "保留这一次的cache/profile.log；应新增BLOCKER_TRACE_READY、BLOCKER_STATE及BLOCKER_FADE。\r\n"
            "无需重发上一份日志，不改原存档/设置/游戏资源，不额外查询碰撞，不改任何碰撞返回或遮罩状态。\r\n"
            "水之迷宫卡死若另测，复现吸入后尝试反向移动，再退出保留另一份日志；不要覆盖黑屏日志。\r\n"
            f"撤回：powershell -NoProfile -ExecutionPolicy Bypass -File {FOLDER}/Update.ps1 -Action Rollback -Runtime .\r\n").encode('utf-8')
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for n, blob in sorted(payload.items()):
            info = zipfile.ZipInfo(n, (2026,10,24,0,0,0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, blob)
    with zipfile.ZipFile(output) as z:
        if z.testzip() or {n:z.read(n) for n in z.namelist()} != payload:
            raise ValueError('Package readback mismatch')
    if sha(previous.read_bytes()) != previous_sha256 or module.read_bytes() != native:
        raise ValueError('Input changed')
    output.with_suffix('.zip.sha256').write_text(sha(output.read_bytes())+'  '+output.name+'\n')
    print(('AUDIO_PROVIDER_PACKAGE' if policy == 'audio' else 'BLOCKER_TRACE_PACKAGE')+' PASS files=15 default_enabled=false game_started=false')
    return output


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('previous', 'module', 'work', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--previous-sha256', required=True)
    build(**vars(p.parse_args()))
