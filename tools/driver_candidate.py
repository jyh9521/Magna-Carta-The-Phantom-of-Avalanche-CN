"""Version-locked, reversible driver trial; never starts a game process."""
import argparse
import json
from pathlib import Path
from graphics_compat import EXPECTED, LAYER_NAMES, ensure_idle, sha, workspace_path, validate_inputs, replace_bytes

COMMIT = '9ce77cace0d717f5ad75bb2910517802e55932c8'
ENGINE_EXPECTED = {name: digest for name, digest in EXPECTED.items() if not name.startswith('Drv/')}
ENGINE_EXPECTED.update({
    'Asura.dll': 'f81e7c458d43b77210311499b39b9be2c4895e3a3b356d2e848b6e84210d2557',
    'Core.dll': '72c91c8102ee268ef491c41b56180babca90760df31a00075f63aed018d62571',
})
ORIGINAL = {
    'AsrD3DDrv.dll': '27db21dee7dde8ca3463e11fab57cc0b7cf6a7ed3338c950b6b1181eed7959ed',
    'AsrGlDrv.dll': 'ad6b5cafdcebcecf41754dbd0b225fe898a08282b917c2205a00da4317ca4e46',
}
CANDIDATE = {
    'AsrD3DDrv.dll': '00d443327abf56c94f9f088515ab29be63bab9650771a5cacdcef20ab85eff29',
    'AsrGlDrv.dll': '54d037a13d2e76dc06b6eff47219ca25f0af8cc1ec66683bd856b07088a518fc',
}
STATE = '.driver-trial.json'
BACKUP = '.driver-trial-original'


def checked_workspace(workspace, root, expected):
    workspace = workspace_path(workspace, root)
    validate_inputs(workspace, expected)
    for folder in (workspace, workspace / 'Drv'):
        for path in folder.iterdir():
            if path.name.lower() in LAYER_NAMES:
                raise ValueError('Graphics layers rejected for driver-only trial')
    for name in [STATE, BACKUP, *['Drv/' + n for n in ORIGINAL]]:
        path = workspace / name
        if path.is_symlink() or path.is_junction():
            raise ValueError('Linked trial path rejected')
    return workspace


def apply(workspace, root, source, expected=ENGINE_EXPECTED, original=ORIGINAL, candidate=CANDIDATE):
    if set(original) != set(candidate) or set(original) != set(ORIGINAL):
        raise ValueError('Unexpected driver list')
    workspace = checked_workspace(workspace, root, expected)
    state_path, backup = workspace / STATE, workspace / BACKUP
    if state_path.exists() or backup.exists():
        raise ValueError('Existing trial history; use a fresh copy')
    old, new = {}, {}
    for name in original:
        old[name] = (workspace / 'Drv' / name).read_bytes()
        new[name] = (Path(source) / name).read_bytes()
        if sha(old[name]) != original[name] or sha(new[name]) != candidate[name]:
            raise ValueError('Unsupported driver bytes: ' + name)
    backup.mkdir()
    for name, data in old.items():
        (backup / name).write_bytes(data)
    state = dict(schema=1, upstream='Nejuf/magnacarta', commit=COMMIT,
                 status='applied', original=original, candidate=candidate)
    try:
        for name, data in new.items():
            replace_bytes(workspace / 'Drv' / name, data)
        replace_bytes(state_path, json.dumps(state, indent=2).encode())
        for name in candidate:
            if sha((workspace / 'Drv' / name).read_bytes()) != candidate[name]:
                raise ValueError('Driver output mismatch')
    except Exception:
        for name, data in old.items():
            replace_bytes(workspace / 'Drv' / name, data)
        raise
    return state


def rollback(workspace, root, expected=ENGINE_EXPECTED, original=ORIGINAL, candidate=CANDIDATE):
    workspace = checked_workspace(workspace, root, expected)
    state_path, backup = workspace / STATE, workspace / BACKUP
    state = json.loads(state_path.read_text())
    if state != dict(schema=1, upstream='Nejuf/magnacarta', commit=COMMIT,
                     status='applied', original=original, candidate=candidate):
        raise ValueError('Unknown or already restored trial')
    old, new = {}, {}
    for name in original:
        path = backup / name
        if path.is_symlink() or path.is_junction():
            raise ValueError('Linked backup rejected')
        old[name], new[name] = path.read_bytes(), (workspace / 'Drv' / name).read_bytes()
        if sha(old[name]) != original[name] or sha(new[name]) != candidate[name]:
            raise ValueError('Changed trial or backup; preserve files')
    state['status'] = 'restored'
    try:
        for name, data in old.items():
            replace_bytes(workspace / 'Drv' / name, data)
        replace_bytes(state_path, json.dumps(state, indent=2).encode())
    except Exception:
        for name, data in new.items():
            replace_bytes(workspace / 'Drv' / name, data)
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['apply', 'rollback'])
    p.add_argument('--workspace', type=Path, required=True)
    p.add_argument('--source', type=Path)
    args = p.parse_args()
    ensure_idle()
    root = Path(__file__).resolve().parents[1] / 'build'
    if args.action == 'apply':
        if not args.source:
            p.error('--source required for apply')
        apply(args.workspace, root, args.source)
        print('DRIVER_TRIAL_PASS files=2 graphics_layers=0 game_started=false')
    else:
        rollback(args.workspace, root)
        print('DRIVER_ROLLBACK_PASS files=2 restored=exact_bytes game_started=false')
