"""Integrate the scene loading presentation prelude into existing entries; retain original role DLLs."""
import argparse
import json
import os
from contextlib import contextmanager
from pathlib import Path
from prepare_field_return_trial import (ordinary, relative, validate_manifest, load_json,
                                       digest, write_file, check_state, restore_state)

ROOT=Path(__file__).resolve().parents[1]
BASE_START_SHA='19298b94a647cbc3cf47485477c4913407d24f8aa4aa2dcc38fc8b32e5b255c8'
CHANGES=('Start.ps1','runtime.json','modules/scene-loading.dll')

@contextmanager
def runtime_lock(runtime):
    root=ordinary(runtime,directory=True)
    if os.name!='nt':
        yield
        return
    import ctypes
    from ctypes import wintypes
    k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.CreateMutexW.argtypes=[ctypes.c_void_p,wintypes.BOOL,wintypes.LPCWSTR]
    k.CreateMutexW.restype=wintypes.HANDLE
    k.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
    k.ReleaseMutex.argtypes=[wintypes.HANDLE];k.CloseHandle.argtypes=[wintypes.HANDLE]
    h=k.CreateMutexW(None,False,'Local\\MagnaCartaShared_'+digest((root/'runtime.json').read_bytes())[:24])
    if not h:raise OSError('Runtime mutex creation failed')
    acquired=False
    try:
        status=k.WaitForSingleObject(h,0)
        if status not in (0,0x80):raise ValueError('Shared runtime entry is active; leave files unchanged')
        acquired=True
        yield
    finally:
        if acquired:k.ReleaseMutex(h)
        k.CloseHandle(h)


def integrate(runtime,module,record):
    with runtime_lock(runtime):
        return integrate_locked(runtime,module,record)


def integrate_locked(runtime,module,record):
    root=ordinary(runtime,directory=True);module=ordinary(module);record=ordinary(record,exists=False)
    if module.is_relative_to(root) or record.is_relative_to(root):raise ValueError('External module and record required')
    raw=(root/'runtime.json').read_bytes();manifest=load_json(raw);validate_manifest(root,manifest)
    start=(root/'Start.ps1').read_bytes()
    if (digest(start)!=BASE_START_SHA or 'scene_loading_module' in manifest
            or 'scene_loading' in manifest
            or manifest.get('gui_parent_guard')!=dict(schema=1,enabled=True,module='gui-parent-guard')
            or manifest.get('field_return_height')!=dict(schema=1,enabled=True,module='field-return-height') or (root/'Play-stairwell-fix.cmd').exists()):
        raise ValueError('Restore the recorded pre-trial baseline before integrating')
    dest=relative(root,CHANGES[2]);ordinary(dest,exists=False)
    canonical=ordinary(ROOT/'src/configuration/StartShared.ps1');script=canonical.read_bytes()
    if b'# SCENE_LOADING_DEFAULT_ROUTE:' not in script:raise ValueError('Missing default route implementation')
    native=module.read_bytes()
    before={'Start.ps1':start,'runtime.json':raw,CHANGES[2]:None}
    after={'Start.ps1':script,CHANGES[2]:native}
    manifest['scene_loading']=dict(schema=1,enabled=True,module='scene-loading')
    for name,data in after.items():manifest['files'][name]=digest(data)
    after['runtime.json']=(json.dumps(manifest,indent=2)+'\n').encode('utf8')
    rows=[dict(path=name,before=digest(before[name]) if before[name] is not None else None,
               after=digest(after[name])) for name in CHANGES]
    validate_manifest(root,load_json(raw));check_state(root,rows,'before')
    if module.read_bytes()!=native or canonical.read_bytes()!=script:raise ValueError('Integration input drift')
    record.mkdir(parents=True)
    for name,data in before.items():
        if data is not None:
            p=record/'original'/name;p.parent.mkdir(parents=True,exist_ok=True);write_file(p,data)
    journal=dict(schema=1,kind='scene_loading_default_integration',runtime=str(root),changes=rows,
                 original_modules_preserved=True,data_modified=False)
    write_file(record/'changes.json',(json.dumps(journal,indent=2)+'\n').encode())
    try:
        for name in (CHANGES[2],'Start.ps1','runtime.json'):write_file(root/name,after[name])
        check_state(root,rows,'after')
    except BaseException:
        restore_state(root,before);check_state(root,rows,'before');raise
    return journal


def rollback(record):
    path=ordinary(record,directory=True)
    root=load_json(ordinary(path/'changes.json').read_bytes())['runtime']
    with runtime_lock(root):
        return rollback_locked(record)


def rollback_locked(record):
    record=ordinary(record,directory=True);j=load_json(ordinary(record/'changes.json').read_bytes())
    if j.get('schema')!=1 or j.get('kind')!='scene_loading_default_integration':raise ValueError('Unknown integration record')
    root=ordinary(j['runtime'],directory=True);rows=j['changes']
    if record.is_relative_to(root) or [r['path'] for r in rows]!=list(CHANGES):raise ValueError('Unexpected integration paths')
    before={}
    for row in rows:
        name=row['path'];expected=row['before']
        if name==CHANGES[2]:
            if expected is not None:raise ValueError('Unexpected existing candidate')
            before[name]=None
        else:
            b=ordinary(record/'original'/name).read_bytes()
            if digest(b)!=expected:raise ValueError('Backup drift: '+name)
            before[name]=b
    check_state(root,rows,'after');validate_manifest(root,load_json((root/'runtime.json').read_bytes()))
    after={name:(root/name).read_bytes() for name in CHANGES}
    try:
        restore_state(root,before);check_state(root,rows,'before')
    except BaseException:
        restore_state(root,after);check_state(root,rows,'after');raise
    return j


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['runtime','module','record','rollback']:p.add_argument('--'+name,type=Path)
    a=p.parse_args()
    try:
        if a.rollback:
            if any([a.runtime,a.module,a.record]):p.error('--rollback is exclusive')
            rollback(a.rollback);print('SCENE_LOADING_INTEGRATION_ROLLBACK PASS original_entry=restored original_modules=unchanged saves=preserved')
        else:
            if not all([a.runtime,a.module,a.record]):p.error('--runtime --module --record required')
            integrate(a.runtime,a.module,a.record);print('SCENE_LOADING_INTEGRATION PASS Play.cmd=enabled baseline=original separate_entry=false data_modified=false scene_transition_crash_fixed=false')
    except (OSError,ValueError,KeyError,TypeError) as e:p.error(str(e))


if __name__=='__main__':main()
