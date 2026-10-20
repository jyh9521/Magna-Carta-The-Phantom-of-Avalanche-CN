"""Image-only transaction for the existing shared Play entry; no game launch."""
import argparse
import json
from pathlib import Path
import re
import stat

from integrate_native_loading import runtime_lock
from prepare_field_return_trial import (ordinary, relative, load_json, validate_manifest,
                                       digest, write_file, check_state)
from locale_package import collect
from update_configuration_runtime import idle


def guarded_paths(root):
    files = [*root.rglob('*.sav'),root/'config/enhancements.json']
    return {p.relative_to(root).as_posix():digest(p.read_bytes()) for p in files if p.is_file()}


def replace_file(path, data, mode):
    """CD-installed resources may be read-only; retain that exact attribute."""
    ordinary(path)
    path.chmod(mode | stat.S_IWUSR)
    try:
        if path.read_bytes()!=data:
            write_file(path,data)
    finally:
        path.chmod(mode)


def restore(root, content, modes):
    for name,data in content.items():
        replace_file(relative(root,name),data,modes[name])


def apply(runtime, packages, inventory, checks, record):
    idle()
    root = ordinary(runtime,directory=True)
    record = ordinary(record,exists=False)
    packages = [ordinary(p,directory=True) for p in packages]
    if (record.is_relative_to(root) or root.is_relative_to(record) or
            any(record.is_relative_to(p) or p.is_relative_to(record) or p.is_relative_to(root) for p in packages)):
        raise ValueError('Separate candidate packages and transaction required')
    with runtime_lock(root):
        raw = ordinary(root/'runtime.json').read_bytes()
        manifest = load_json(raw)
        validate_manifest(root,manifest)
        for name, expected in manifest.get('data',{}).items():
            if digest(ordinary(relative(root,'data/'+name)).read_bytes())!=expected:
                raise ValueError('Runtime data drift: '+name)
        inv = load_json(ordinary(inventory).read_bytes())
        rows = inv.get('records')
        if not isinstance(rows,list) or not rows or inv.get('game_started') is not False:
            raise ValueError('Expected read-only baseline inventory')
        expected = {row['resource']:row['current_sha256'] for row in rows}
        if len(expected)!=len(rows):
            raise ValueError('Duplicate baseline images')
        for name, sha in expected.items():
            if not re.fullmatch(r'BGR/[0-9]{4}\.BGR',name) or digest(ordinary(relative(root,'data/'+name)).read_bytes())!=sha:
                raise ValueError('Image baseline drift: '+name)
        checks_path = ordinary(checks)
        rules = load_json(checks_path.read_bytes())
        approved = {r['resource']:r['target_sha256'] for r in rules.get('approved_replacements',[])}
        for name, sha in approved.items():
            if expected.get(name)!=sha:
                raise ValueError('Approved title replacement drift: '+name)
        before,after = {},{}
        for name, path in sorted(collect(packages).items()):
            if name not in expected:
                raise ValueError('Candidate image absent from baseline inventory: '+name)
            if name in approved:
                continue
            data = ordinary(path).read_bytes()
            target = 'data/'+name
            old = ordinary(relative(root,target)).read_bytes()
            if data==old:
                continue
            before[target],after[target] = old,data
            manifest['data'][name] = digest(data)
        if not after:
            raise ValueError('No image changes')
        before['runtime.json'] = raw
        after['runtime.json'] = (json.dumps(manifest,indent=2)+'\n').encode('utf8')
        modes = {n:ordinary(relative(root,n)).stat().st_mode for n in after}
        changes = [dict(path=n,before=digest(before[n]),after=digest(b),mode=modes[n]) for n,b in after.items()]
        guards = guarded_paths(root)
        journal = dict(schema=1,kind='image_runtime_repair',runtime=str(root),changes=changes,
                       baseline_inventory_sha256=digest(ordinary(inventory).read_bytes()),
                       checks_sha256=digest(checks_path.read_bytes()),guards=guards,
                       packages=[digest((p/'build.json').read_bytes()) for p in packages],
                       game_started=False,in_game_verified=False)
        check_state(root,changes,'before')
        record.mkdir(parents=True)
        for name,data in before.items():
            dest = record/'original'/name
            dest.parent.mkdir(parents=True,exist_ok=True)
            write_file(dest,data)
        write_file(record/'changes.json',(json.dumps(journal,indent=2)+'\n').encode('utf8'))
        try:
            idle()
            check_state(root,changes,'before')
            for name,data in after.items():
                replace_file(relative(root,name),data,modes[name])
            check_state(root,changes,'after')
            if guarded_paths(root)!=guards:
                raise ValueError('Saves/settings changed during transaction')
            validate_manifest(root,load_json((root/'runtime.json').read_bytes()))
        except BaseException:
            restore(root,before,modes)
            check_state(root,changes,'before')
            raise
        return journal


def rollback(record, runtime=None):
    """An explicit different root supports the minimal offline rollback fixture."""
    idle()
    record = ordinary(record,directory=True)
    journal = load_json(ordinary(record/'changes.json').read_bytes())
    if journal.get('schema')!=1 or journal.get('kind')!='image_runtime_repair':
        raise ValueError('Unknown image repair transaction')
    root = ordinary(runtime or journal['runtime'],directory=True)
    if record.is_relative_to(root) or root.is_relative_to(record):
        raise ValueError('Separate rollback record required')
    changes = journal.get('changes')
    if not isinstance(changes,list) or not changes or changes[-1]['path']!='runtime.json':
        raise ValueError('Invalid image repair change set')
    names = [r['path'] for r in changes]
    if len(set(names))!=len(names) or any(not re.fullmatch(r'data/BGR/[0-9]{4}\.BGR|runtime\.json',n) for n in names):
        raise ValueError('Unexpected rollback path')
    with runtime_lock(root):
        before = {}
        for row in changes:
            data = ordinary(relative(record/'original',row['path'])).read_bytes()
            if digest(data)!=row['before']:
                raise ValueError('Rollback backup drift: '+row['path'])
            before[row['path']] = data
        check_state(root,changes,'after')
        after = {n:ordinary(relative(root,n)).read_bytes() for n in names}
        modes = {row['path']:row['mode'] for row in changes}
        after_modes = {n:ordinary(relative(root,n)).stat().st_mode for n in names}
        guards = guarded_paths(root)
        try:
            restore(root,before,modes)
            check_state(root,changes,'before')
            if guarded_paths(root)!=guards:
                raise ValueError('Rollback changed saves/settings')
        except BaseException:
            restore(root,after,after_modes)
            check_state(root,changes,'after')
            raise
    return journal


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=['apply','rollback'])
    p.add_argument('--record',type=Path,required=True)
    for name in ['runtime','inventory','checks']:
        p.add_argument('--'+name,type=Path)
    p.add_argument('--packages',type=Path,nargs='+')
    a = p.parse_args()
    if a.action=='apply':
        if not all((a.runtime,a.inventory,a.checks,a.packages)):
            p.error('apply requires runtime, inventory, checks and packages')
        j = apply(a.runtime,a.packages,a.inventory,a.checks,a.record)
    else:
        if a.inventory or a.checks or a.packages:
            p.error('rollback accepts only record and optional runtime')
        j = rollback(a.record,a.runtime)
    print('IMAGE_RUNTIME_%s PASS images=%d entry=Play.cmd saves_settings=preserved game_started=false' %
          (a.action.upper(),len(j['changes'])-1))


if __name__=='__main__':
    main()
