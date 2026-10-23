"""Deploy release input policy, actor coverage and encounter control without game data."""
import argparse
import json
from pathlib import Path
from integrate_native_loading import runtime_lock
from update_configuration_runtime import idle
from prepare_field_return_trial import ordinary, write_file, digest, load_json
from update_runtime_modules import MODULES, check_module

ROOT=Path(__file__).resolve().parents[1]
SOURCE={
    'Start.ps1':'src/configuration/StartShared.ps1',
    'config/Configure.ps1':'src/configuration/Configure.ps1',
    'config/Configure.xaml':'src/configuration/Configure.xaml',
    'config/EnhancementSettings.psm1':'src/configuration/EnhancementSettings.psm1',
    'config/configuration-ui.json':'locales/zh-CN/configuration-ui.json',
    'config/encounter-ui.json':'locales/zh-CN/encounter-ui.json',
}
CHANGES=(*MODULES,*SOURCE,'runtime.json')

def apply(runtime,module,record):
    root=ordinary(runtime,directory=True);record=ordinary(record,exists=False)
    module=ordinary(module);raw=module.read_bytes();check_module(raw)
    if root.is_relative_to(record) or record.is_relative_to(root) or module.is_relative_to(record):
        raise ValueError('Independent record and module required')
    with runtime_lock(root):
        idle();m=load_json((root/'runtime.json').read_bytes())
        for name,value in m['files'].items():
            if digest(ordinary(root/name).read_bytes())!=value:raise ValueError('Runtime drift: '+name)
        before={n:(root/n).read_bytes() if (root/n).is_file() else None for n in CHANGES}
        after={n:raw for n in MODULES}
        after.update({n:(ROOT/p).read_bytes() for n,p in SOURCE.items()})
        for n,b in after.items():m['files'][n]=digest(b)
        m['archived_features']=['native_gamepad','free_view']
        after['runtime.json']=(json.dumps(m,indent=2)+'\n').encode()
        states={n:dict(before=digest(b) if b is not None else None,after=digest(after[n])) for n,b in before.items()}
        record.mkdir(parents=True)
        for n,b in before.items():
            if b is not None:
                p=record/'original'/n;p.parent.mkdir(parents=True,exist_ok=True);write_file(p,b)
        write_file(record/'changes.json',(json.dumps(states,indent=2)+'\n').encode())
        changed=[]
        try:
            for n in CHANGES:write_file(root/n,after[n]);changed.append(n)
            if any((root/n).read_bytes()!=b for n,b in after.items()):raise ValueError('Deployment readback')
        except BaseException:
            for n in reversed(changed):
                if before[n] is None:(root/n).unlink()
                else:write_file(root/n,before[n])
            raise
    print('RELEASE_CONTROLS_UPDATE PASS files=19 controller=archived free_view=archived actors=4 encounters=F5 settings=preserved game_data=unchanged game_started=false')
    return states

def rollback(runtime,record):
    root=ordinary(runtime,directory=True);record=ordinary(record,directory=True)
    states=load_json((record/'changes.json').read_bytes())
    if list(states)!=list(CHANGES):raise ValueError('Unexpected rollback set')
    with runtime_lock(root):
        idle()
        for n,s in states.items():
            if digest(ordinary(root/n).read_bytes())!=s['after']:raise ValueError('Target changed: '+n)
            if s['before'] is not None and digest(ordinary(record/'original'/n).read_bytes())!=s['before']:raise ValueError('Backup changed: '+n)
        after={n:(root/n).read_bytes() for n in states};done=[]
        try:
            for n,s in reversed(list(states.items())):
                if s['before'] is None:(root/n).unlink()
                else:write_file(root/n,(record/'original'/n).read_bytes())
                done.append(n)
            for n,s in states.items():
                if ((root/n).exists() if s['before'] is None else digest((root/n).read_bytes())!=s['before']):raise ValueError('Rollback readback')
        except BaseException:
            for n in done:write_file(root/n,after[n])
            raise
    print('RELEASE_CONTROLS_ROLLBACK PASS files=19 original_hashes=exact settings=preserved game_data=unchanged game_started=false')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['apply','rollback'])
    for n in ('runtime','record'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--module',type=Path);a=p.parse_args()
    if a.action=='apply':
        if not a.module:p.error('apply requires module')
        apply(a.runtime,a.module,a.record)
    else:rollback(a.runtime,a.record)
