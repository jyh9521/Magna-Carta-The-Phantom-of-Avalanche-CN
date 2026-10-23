"""Package F11 on top of the delivered continue-game repair, without game data."""
import argparse
from pathlib import Path
import zipfile

import build_continue_game_update as previous_builder
from build_text_runtime_update import sha

FOLDER='RageCombo-F11-20261023'
BACKUP='.rage-combo-f11-20261023'
WRAPPER='Update-F11.cmd'


def build(previous,module,output,work,previous_sha256,module_sha256):
    previous,module,output,work=map(lambda p:Path(p).resolve(),(previous,module,output,work))
    if work.exists() or output.exists() or output.suffix.lower()!='.zip' or any(p.is_relative_to(work) for p in (previous,module,output)):
        raise ValueError('New independent work directory and ZIP required')
    if sha(previous.read_bytes())!=previous_sha256 or sha(module.read_bytes())!=module_sha256:
        raise ValueError('Source hash mismatch')
    work.mkdir(parents=True)
    # Flatten only the earlier repair updater, keeping its real backup namespace.
    # It contains owned modules/manifest/scripts/licenses, never original game data.
    prefix=previous_builder.FOLDER+'/'
    with zipfile.ZipFile(previous) as archive:
        files={n[len(prefix):]:archive.read(n) for n in archive.namelist() if n.startswith(prefix)}
    if 'package.json' not in files or 'Update.ps1' not in files:
        raise ValueError('Expected delivered continue-game repair')
    prior=work/'previous.zip'
    with zipfile.ZipFile(prior,'x',zipfile.ZIP_DEFLATED) as archive:
        for n,b in sorted(files.items()):archive.writestr(n,b)
    staged=previous_builder.assemble(prior,module,work/'staged.zip',work/'staged-work',sha(prior.read_bytes()),module_sha256)
    with zipfile.ZipFile(staged) as archive:
        files={n:archive.read(n) for n in archive.namelist()}
    result={}
    for n,b in files.items():
        if n.startswith(prefix):n=FOLDER+'/'+n[len(prefix):]
        elif n=='Repair-ContinueGame.cmd':
            n=WRAPPER;b=b.replace(previous_builder.FOLDER.encode(),FOLDER.encode())
        elif n=='README-ContinueGame.txt':n='README-F11.txt'
        if n==FOLDER+'/Update.ps1':
            needle=f"Located $Runtime '{previous_builder.BACKUP}'".encode()
            if b.count(needle)!=1:raise ValueError('Unexpected updater backup anchor')
            b=b.replace(needle,f"Located $Runtime '{BACKUP}'".encode())
        result[n]=b
    readme=('F11 暴走模式一键连招更新\r\n'
            '前提：已安装 MagnaCarta-continue-game-fix-20261023.zip 的修复。\r\n'
            '1. 关闭游戏，将本包全部内容解压到有 Play.cmd、runtime.json 的共享运行目录。\r\n'
            '2. 双击 Update-F11.cmd，看到 REPAIR PASS 后才算安装完成。仅解压不会更新模块。\r\n'
            '3. 运行原 Play.cmd；普通模式 F10/R3，暴走模式 F11。\r\n'
            '选好攻击和目标后按一次F11；辅助包含启动节奏的第一次Space。不要额外按Space打断。\r\n'
            '手动按键、失焦或模式/角色切换会取消。已错过最佳时限时不会强行补发。\r\n'
            '保留继续游戏修正、存档、设置和前两版更新的撤回记录。不需要先撤回旧包。\r\n'
            '原生计时/评分和技能选择已离线验证；本包F11战斗画面由测试者手动验收。\r\n'
            f'模块SHA256：{module_sha256}\r\n'
            f'撤回：powershell -NoProfile -ExecutionPolicy Bypass -File {FOLDER}/Update.ps1 -Action Rollback -Runtime .\r\n')
    result['README-F11.txt']=result[FOLDER+'/README.txt']=readme.encode('utf-8')
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for n,b in sorted(result.items()):
            info=zipfile.ZipInfo(n,(2026,10,23,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
            archive.writestr(info,b)
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None or {n:archive.read(n) for n in archive.namelist()}!=result:
            raise ValueError('ZIP readback mismatch')
    if sha(previous.read_bytes())!=previous_sha256 or sha(module.read_bytes())!=module_sha256:
        raise ValueError('Input drift')
    output.with_suffix('.zip.sha256').write_text(f'{sha(output.read_bytes())}  {output.name}\n')
    print(f'RAGE_PACKAGE PASS sha256={sha(output.read_bytes())} continue_fix=preserved game_started=false')
    return output


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('previous','module','output','work'):p.add_argument('--'+n,type=Path,required=True)
    for n in ('previous-sha256','module-sha256'):p.add_argument('--'+n,required=True)
    build(**vars(p.parse_args()))
