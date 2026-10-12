"""Prepare one pinned Direct3D11 graphics candidate, without running the game."""
import argparse
import json
from pathlib import Path
import zipfile
from graphics_compat import workspace_path, validate_inputs, sha, EXPECTED, LAYER_NAMES, ensure_idle

VERSION = '2.87.5'
PACKAGE_SHA = '5ffde6927f7355ca3fdd5d785b581256a8e6539fa13e395a891ade6ba1040850'
DLLS = {'DDraw.dll': '612a24408a090a3c6f3886557fa18034ee742e94ad0a40ebdf854d2816176c2e',
        'D3DImm.dll': '93c534f2d17419ea78f15551f7e0aac78b3c503733a840914fa063708a5afe8e'}
CONFIG = b'''Version = 0x287
[General]
OutputAPI = d3d11_fl11_0
Adapters = all
FullScreenMode = false
ScalingMode = stretched_ar
KeepWindowAspectRatio = true
[GeneralExt]
WindowedAttributes = borderless, fullscreensize
[DirectX]
DisableAndPassThru = false
VideoCard = geforce_9800_gt
VRAM = 256
Resolution = unforced
Filtering = appdriven
Antialiasing = appdriven
AppControlledScreenMode = false
dgVoodooWatermark = true
DisableD3DTnLDevice = false
'''
STATE = '.dgvoodoo-candidate.json'
HASHES = {**DLLS, 'dgVoodoo.conf': sha(CONFIG)}


def package_files(path):
    if sha(Path(path).read_bytes()) != PACKAGE_SHA:
        raise ValueError('Unsupported package')
    with zipfile.ZipFile(path) as archive:
        outputs = {name: archive.read('MS/x86/' + name, pwd=b'dege') for name in DLLS}
    if any(sha(data) != DLLS[name] for name, data in outputs.items()):
        raise ValueError('DLL hash mismatch')
    return {**outputs, 'dgVoodoo.conf': CONFIG}


def apply(workspace, allowed_root, outputs, expected=EXPECTED):
    workspace = workspace_path(workspace, allowed_root)
    validate_inputs(workspace, expected)
    if set(outputs) != set(HASHES) or any(sha(data) != HASHES[name] for name, data in outputs.items()):
        raise ValueError('Unsupported candidate outputs')
    for folder in (workspace, workspace / 'Drv'):
        if folder.exists() and any(p.name.lower() in LAYER_NAMES for p in folder.iterdir()):
            raise ValueError('Existing graphics layer or configuration')
    state = json.dumps({'layer': 'dgVoodoo2', 'version': VERSION, 'outputs': HASHES}, indent=2).encode()
    written = []
    try:
        for name, data in {**outputs, STATE: state}.items():
            with (workspace / name).open('xb') as stream:
                written.append(workspace / name)
                stream.write(data)
        validate_inputs(workspace, expected)
    except Exception:
        for path in reversed(written):
            path.unlink()
        raise


def remove(workspace, allowed_root):
    workspace = workspace_path(workspace, allowed_root)
    state = json.loads((workspace / STATE).read_text(encoding='utf-8'))
    if state != {'layer': 'dgVoodoo2', 'version': VERSION, 'outputs': HASHES}:
        raise ValueError('Unsupported rollback manifest')
    for name, digest in HASHES.items():
        if sha((workspace / name).read_bytes()) != digest:
            raise ValueError('Changed output; rollback stopped: ' + name)
    for name in [*HASHES, STATE]:
        (workspace / name).unlink()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['apply', 'remove'])
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--package', type=Path)
    args = parser.parse_args()
    ensure_idle()
    root = Path(__file__).resolve().parents[1] / 'build'
    if args.action == 'apply':
        if not args.package:
            parser.error('--package required')
        apply(args.workspace, root, package_files(args.package))
        print('GRAPHICS_CANDIDATE_APPLIED layer=dgVoodoo2 version=2.87.5 original_files_changed=0 game_started=false')
    else:
        remove(args.workspace, root)
        print('GRAPHICS_CANDIDATE_REMOVED files=4 original_files_changed=0 game_started=false')
