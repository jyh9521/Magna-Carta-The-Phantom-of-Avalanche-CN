"""Build an owned-file collision-guard update for the verified shared data/ runtime.

This differs from the tester's flat overlay. No game resources or player saves
are packaged. The ordinary entry and configuration remain unchanged; the candidate is opt-in.
"""
import argparse
import json
from pathlib import Path
import zipfile
from build_text_runtime_update import ROOT, sha
from prepare_field_return_trial import ordinary, validate_manifest
from update_runtime_modules import MODULES, check_module

FOLDER='Collision-Guard-20261024'
ENTRY='Play-collision-fix.cmd'
FILES=(*MODULES,'runtime.json',ENTRY)


def build(runtime,module,work,output):
    runtime=ordinary(runtime,directory=True)
    module=ordinary(module)
    work,output=Path(work).resolve(),Path(output).resolve()
    if (work.exists() or output.exists() or output.suffix!='.zip'
            or any(p.is_relative_to(runtime) for p in (work,output,module))
            or any(p.is_relative_to(work) for p in (runtime,module,output))):
        raise ValueError('Independent new build outputs required')
    raw=(runtime/'runtime.json').read_bytes();manifest=json.loads(raw)
    validate_manifest(runtime,manifest)
    engine_sha='7e8649425217d3b99d52d11c679761a88c57b125c241b331aea5c25e00e3b15e'
    if (manifest.get('data_root')!='data' or manifest.get('data',{}).get('MCAlpha.dll')!=engine_sha
            or sha((runtime/'data/MCAlpha.dll').read_bytes())!=engine_sha
            or any(n not in manifest['files'] for n in MODULES) or ENTRY in manifest['files']
            or (runtime/ENTRY).exists()):
        raise ValueError('Expected supported shared runtime without the added collision entry')
    native=module.read_bytes();check_module(native)
    for marker in ('COLLISION_GUARD_READY','CONTACT_AUDIO_READY'):
        if marker.encode('utf-16le') not in native:raise ValueError('Collision guard marker missing')
    before={n:(runtime/n).read_bytes() for n in MODULES};before['runtime.json']=raw;before[ENTRY]=None
    after={n:native for n in MODULES};after[ENTRY]=(ROOT/'assets/shared-runtime'/ENTRY).read_bytes()
    for n,b in after.items():manifest['files'][n]=sha(b)
    manifest['collision_guard']=dict(schema=1,default_enabled=False,entry=ENTRY,candidate=True,
        generic=True,native_physics_retained=True,native_offsets=8,clearance_step=15,
        recovery_max=16,scripted_movement_excluded=True,in_game_verified=False,
        source_sha256={n:sha((ROOT/n).read_bytes()) for n in
            ('src/runtime/collision_guard.cpp','src/runtime/collision_guard.h',
             'src/runtime/collision_kernel.cpp','src/runtime/collision_kernel.h')})
    after['runtime.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    work.mkdir(parents=True);payload={};rows=[];dedup={}
    for n in FILES:
        b=after[n];h=sha(b);key=dedup.setdefault(h,f'payload/{len(dedup):04d}.bin')
        payload[FOLDER+'/'+key]=b
        rows.append(dict(path=n,before=sha(before[n]) if before[n] is not None else None,
            after=h,size=len(b),payload=key,payload_sha256=h,delta=False))
        if before[n] is not None:
            p=work/'original'/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(before[n])
    payload[FOLDER+'/package.json']=(json.dumps(dict(schema=1,kind='text_runtime_update',files=rows,
        diagnostic_only=False,default_enabled=False,in_game_verified=False),indent=2)+'\n').encode()
    script=(ROOT/'assets/text-runtime-update/Update.ps1').read_text('utf-8-sig')
    script=script.replace("'.text-runtime-update'","'.collision-guard-20261024'")
    anchor=r'runtime\.json|modules/'
    if script.count(anchor)!=1:raise ValueError('Updater allow-list drift')
    script=script.replace(anchor,r'Play-collision-fix\.cmd|runtime\.json|modules/')
    anchor='$seen=@{};$prepared=@{};$before=@{}'
    if script.count(anchor)!=1:raise ValueError('Updater state drift')
    script=script.replace(anchor,"""if($Action -eq 'Install' -and (Test-Path -LiteralPath $marker)){
 $prior=Get-Content -LiteralPath $marker -Raw -Encoding UTF8|ConvertFrom-Json
 if($prior.state -eq 'installed' -and $prior.package_sha256 -ceq (Digest $manifest)){$Action='CheckInstalled'}
}
"""+anchor)
    payload[FOLDER+'/Update.ps1']=b'\xef\xbb\xbf'+script.encode()
    wrapper=(ROOT/'assets/player-test-package/Fix-Overlay-Launch.cmd').read_bytes()
    wrapper=wrapper.replace(b'Overlay-Launch-Fix-20261023',FOLDER.encode()).replace(
        b'Overlay-Launch-Fix.log',b'Collision-Guard-Install.log').replace(
        b'Applying overlay launch repair...',b'Installing generic collision guard candidate...')
    payload['Install-Collision-Guard.cmd']=wrapper
    payload['README-Collision-Guard.txt']=("通用移动碰撞修复候选，不按地图坐标特判。\r\n"
        "安装后用Play-collision-fix.cmd测试贴墙、窄路和中央建筑；普通Play.cmd不启用候选。\r\n"
        "保留原生物理及八个碰撞偏移；提交时阻止新增穿入，并尝试16单位内的水平脱离。\r\n"
        "剧情移动不处理；实际水之迷宫尚待人工验收，不将离线检查当作全地图已修复。\r\n"
        "不改游戏数据、存档或设置；新记录cache/profile.log包含COLLISION_GUARD_READY/STEP。\r\n"
        f"撤回：powershell -NoProfile -ExecutionPolicy Bypass -File {FOLDER}/Update.ps1 -Action Rollback -Runtime .\r\n").encode('utf-8')
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for n,b in sorted(payload.items()):
            i=zipfile.ZipInfo(n,(2026,10,24,0,0,0));i.compress_type=zipfile.ZIP_DEFLATED;z.writestr(i,b)
    with zipfile.ZipFile(output) as z:
        if z.testzip() or {n:z.read(n) for n in z.namelist()}!=payload:raise ValueError('ZIP readback')
    if (runtime/'runtime.json').read_bytes()!=raw or module.read_bytes()!=native:raise ValueError('Source drift')
    output.with_suffix('.zip.sha256').write_text(sha(output.read_bytes())+'  '+output.name+'\n')
    print('SHARED_COLLISION_PACKAGE PASS files=14 data_root=data game_resources_included=false game_started=false')
    return output


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('runtime','module','work','output'):p.add_argument('--'+name,type=Path,required=True)
    build(**vars(p.parse_args()))
