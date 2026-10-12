"""Apply or remove one hash-pinned graphics layer in an isolated workspace."""
import argparse
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import zipfile

VERSION = 'v0.7.1'
PACKAGE_SHA256 = '0c33ecb1c01c1c779063b490a2e818f6d9227b3b4ee827c51790fb0fd59b17c5'
DLL_SHA256 = 'f75f0ac48d2782f225c483dc2f1142303a513e8dd8a60793891ade89f64755ea'
EXPECTED = {
    'MagnaCarta.exe': 'be2ae107373835defc6ec33643eaf435dcc5c882ea0b6e3c47032cd013690651',
    'MCAlpha.dll': '79e4c3d6af4afb2b75367a2b26fd8450ad25fa9f738612ea96809e312d33cb6f',
    'Drv/AsrD3DDrv.dll': '27db21dee7dde8ca3463e11fab57cc0b7cf6a7ed3338c950b6b1181eed7959ed',
}
CONFIG = b'FullscreenMode = borderless\nDisplayAspectRatio = app\nResolutionScale = app\nLogLevel = info\n'
CONFIG_NAME = 'DDrawCompat-MagnaCarta.ini'
STATE_NAME = '.graphics-compat.json'
LAYER_NAMES = {'ddraw.dll', 'd3d8.dll', 'd3d9.dll', 'dxgi.dll', 'opengl32.dll',
               'glide.dll', 'glide2x.dll', 'glide3x.dll', 'dxwnd.dll',
               'dgvoodoo.conf', 'ddraw.ini', 'ddrawcompat.ini',
               CONFIG_NAME.lower(), 'ddrawcompatoverlay-magnacarta.ini', STATE_NAME}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def workspace_path(workspace, allowed_root):
    root = Path(allowed_root).resolve(strict=True)
    workspace = Path(workspace)
    # Resolve only after checking all components for links.
    for part in (workspace, *workspace.parents):
        if part.is_symlink() or part.is_junction():
            raise ValueError('Linked workspace rejected')
    workspace = workspace.resolve(strict=True)
    if workspace == root or not workspace.is_relative_to(root) or not workspace.is_dir():
        raise ValueError('Workspace must be below the isolated build root')
    for relative in ['Drv', *EXPECTED, 'ddraw.dll', CONFIG_NAME, STATE_NAME]:
        candidate = workspace / relative
        if candidate.is_symlink() or candidate.is_junction():
            raise ValueError('Linked input rejected')
    return workspace


def validate_inputs(workspace, expected=EXPECTED):
    for name, digest in expected.items():
        path = workspace / name
        if not path.is_file() or sha(path.read_bytes()) != digest:
            raise ValueError('Unsupported input: ' + name)


def package_dll(package):
    data = Path(package).read_bytes()
    if sha(data) != PACKAGE_SHA256:
        raise ValueError('Unsupported graphics package')
    with zipfile.ZipFile(Path(package)) as archive:
        if archive.namelist() != ['ddraw.dll']:
            raise ValueError('Unexpected package members')
        dll = archive.read('ddraw.dll')
    if sha(dll) != DLL_SHA256:
        raise ValueError('Graphics DLL hash mismatch')
    return dll


def apply(workspace, allowed_root, dll, expected=EXPECTED):
    workspace = workspace_path(workspace, allowed_root)
    validate_inputs(workspace, expected)
    if sha(dll) != DLL_SHA256:
        raise ValueError('Graphics DLL hash mismatch')
    for folder in (workspace, workspace / 'Drv'):
        if folder.exists():
            for path in folder.iterdir():
                if path.name.lower() in LAYER_NAMES:
                    raise ValueError('Existing graphics layer or configuration: ' + path.name)
    outputs = {'ddraw.dll': dll, CONFIG_NAME: CONFIG}
    state = {'schema': 1, 'layer': 'DDrawCompat', 'version': VERSION,
             'inputs': expected, 'outputs': {name: sha(data) for name, data in outputs.items()}}
    written = []
    try:
        for name, data in {**outputs, STATE_NAME: json.dumps(state, indent=2).encode('utf-8')}.items():
            with (workspace / name).open('xb') as stream:
                written.append(workspace / name)
                stream.write(data)
        validate_inputs(workspace, expected)
    except Exception:
        for path in reversed(written):
            path.unlink()
        raise
    return state


def remove(workspace, allowed_root):
    workspace = workspace_path(workspace, allowed_root)
    state = json.loads((workspace / STATE_NAME).read_text(encoding='utf-8'))
    expected_outputs = {'ddraw.dll': DLL_SHA256, CONFIG_NAME: sha(CONFIG)}
    if (state.get('schema') != 1 or state.get('layer') != 'DDrawCompat'
            or state.get('version') != VERSION or state.get('outputs') != expected_outputs):
        raise ValueError('Unsupported rollback manifest')
    # Verify every output before removing anything. Changed files are preserved.
    for name, digest in expected_outputs.items():
        if sha((workspace / name).read_bytes()) != digest:
            raise ValueError('Changed output; rollback stopped: ' + name)
    for name in expected_outputs:
        (workspace / name).unlink()
    (workspace / STATE_NAME).unlink()
    return len(expected_outputs) + 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['apply', 'remove'])
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--package', type=Path)
    args = parser.parse_args()
    if os.name == 'nt':
        listing = subprocess.run([str(Path(os.environ['SystemRoot']) / 'System32/tasklist.exe'),
                                  '/FO', 'CSV', '/NH'], capture_output=True, text=True, check=True)
        active = {row[0].casefold() for row in csv.reader(io.StringIO(listing.stdout)) if row}
        if active & {'magnacarta.exe', 'mcsetup.exe', 'workspace_launcher.exe'}:
            raise ValueError('Close the game and launcher before changing the graphics layer')
    root = Path(__file__).resolve().parents[1] / 'build'
    if args.action == 'apply':
        if not args.package:
            parser.error('--package required for apply')
        apply(args.workspace, root, package_dll(args.package))
        print('GRAPHICS_APPLY_PASS layer=DDrawCompat version=v0.7.1 original_files_changed=0 game_started=false')
    else:
        count = remove(args.workspace, root)
        print(f'GRAPHICS_ROLLBACK_PASS removed={count} original_files_changed=0 game_started=false')
