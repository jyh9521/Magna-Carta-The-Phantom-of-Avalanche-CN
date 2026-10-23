"""Build a namespace-isolated owned-file update from its deployment journal."""
import argparse,json,zipfile
from pathlib import Path
from update_release_controls import CHANGES,ROOT
from build_text_runtime_update import sha
FOLDER='Release-Controls-20261023'
BACKUP='.release-controls-20261023'

def build(runtime,record,output):
    runtime,record,output=map(lambda p:Path(p).resolve(),(runtime,record,output))
    if output.exists() or output.suffix!='.zip' or output.is_relative_to(runtime) or output.is_relative_to(record):raise ValueError('New independent ZIP required')
    states=json.loads((record/'changes.json').read_text())
    if list(states)!=list(CHANGES):raise ValueError('Unexpected deployment')
    result={};rows=[]
    for n,s in states.items():
        b=(runtime/n).read_bytes()
        if sha(b)!=s['after']:raise ValueError('Deployment drift')
        if s['before'] is not None and sha((record/'original'/n).read_bytes())!=s['before']:raise ValueError('Backup drift')
        key='payload/%04d.bin'%len(rows);result[FOLDER+'/'+key]=b
        rows.append(dict(path=n,before=s['before'],after=s['after'],size=len(b),payload=key,payload_sha256=sha(b),delta=False))
    m=dict(schema=1,kind='text_runtime_update',files=rows,in_game_verified=False,saves_and_settings_preserved=True)
    result[FOLDER+'/package.json']=(json.dumps(m,indent=2)+'\n').encode()
    script=(ROOT/'assets/text-runtime-update/Update.ps1').read_text(encoding='utf-8-sig')
    # Extend only this updater's exact owned-file allowlist; existing packages stay untouched.
    script=script.replace(r"runtime\.json|modules/",r"Start\.ps1|config/(?:Configure\.ps1|Configure\.xaml|EnhancementSettings\.psm1|configuration-ui\.json|encounter-ui\.json)|runtime\.json|modules/",1)
    script=script.replace("'.text-runtime-update'",repr(BACKUP))
    needle='$seen=@{};$prepared=@{};$before=@{}'
    repeat="""if($Action -eq 'Install' -and (Test-Path -LiteralPath $marker)){
 $prior=Get-Content -LiteralPath $marker -Raw -Encoding UTF8|ConvertFrom-Json
 if($prior.state -eq 'installed' -and $prior.package_sha256 -ceq (Digest $manifest)){$Action='CheckInstalled'}
}
"""
    if script.count(needle)!=1:raise ValueError('Updater anchor drift')
    script=script.replace(needle,repeat+needle)
    result[FOLDER+'/Update.ps1']=b'\xef\xbb\xbf'+script.encode()
    result['Update-Release-Controls.cmd']=(f'@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0{FOLDER}\\Update.ps1" -Runtime "%~dp0."\r\nif errorlevel 1 pause\r\n').encode('ascii')
    text=('发布功能调整更新 2026-10-23\r\n前提：已安装2026-10-23的F11暴走辅助更新，模块与入口摘要须匹配。\r\n'
          '关闭游戏，完整解压本包到含Play.cmd和runtime.json的目录，双击Update-Release-Controls.cmd。\r\n'
          '看到MODIFIED PASS后使用原Play.cmd。手柄与自由视角归档并从设置中移除。\r\n'
          '60帧新增底层蒙皮/刚性模型入口，沿用人物相位与恢复流程；怪物最终画面待人工验收。\r\n'
          'F5随机遇敌开关：默认开启，按一次关闭，再按一次开启，状态显示在屏幕上方。\r\n'
          '关闭时不推进随机遇敌计数；剧情战斗、当前战斗、存档及F10/F11不变；重启恢复开启。\r\n'
          '屏幕提示使用点击穿透窗口，失焦隐藏；独占全屏叠加效果仍需实机检查。\r\n'
          f'回滚：powershell -NoProfile -ExecutionPolicy Bypass -File {FOLDER}/Update.ps1 -Action Rollback -Runtime .\r\n')
    result['README-Release-Controls.txt']=text.encode('utf8')
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for n,b in sorted(result.items()):z.writestr(n,b)
    with zipfile.ZipFile(output) as z:
        if z.testzip() or {n:z.read(n) for n in z.namelist()}!=result:raise ValueError('ZIP readback')
    output.with_suffix('.zip.sha256').write_text(sha(output.read_bytes())+'  '+output.name+'\n')
    print('RELEASE_CONTROLS_PACKAGE PASS files=19 sha256='+sha(output.read_bytes())+' game_data=absent game_started=false')
    return output
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('runtime','record','output'):p.add_argument('--'+n,type=Path,required=True)
    build(**vars(p.parse_args()))
