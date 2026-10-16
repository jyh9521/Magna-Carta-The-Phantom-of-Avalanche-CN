"""Build a source-locked player trial from the verified local shared runtime.

Commercial inputs remain local; changed files are distributed as block deltas.
Player installation uses Windows PowerShell only, not Python.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]

def sha(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def build(source, runtime, output):
    source = source.resolve(strict=True)
    runtime = runtime.resolve(strict=True)
    output = output.resolve()
    if output.exists() or output.is_relative_to(source) or output.is_relative_to(runtime):
        raise ValueError('new separate output required')
    supported = {
        'MagnaCarta.exe': 'be2ae107373835defc6ec33643eaf435dcc5c882ea0b6e3c47032cd013690651',
        'MCAlpha.dll': '79e4c3d6af4afb2b75367a2b26fd8450ad25fa9f738612ea96809e312d33cb6f',
    }
    for name, digest in supported.items():
        if sha(source/name) != digest:
            raise ValueError('unsupported original version: '+name)
    m = json.loads((runtime/'runtime.json').read_text())
    for collection, base in [('data', runtime/'data'), ('files', runtime)]:
        for name, digest in m[collection].items():
            if sha(base/name) != digest:
                raise ValueError('runtime drift: '+name)
    output.mkdir(parents=True)
    payload = output/'payload'
    payload.mkdir()
    for name in set(m['files']) | {'runtime.json', 'Configure.cmd', 'config/enhancements.json'} | {p.name for p in runtime.glob('Play*.cmd')}:
        dest = payload/name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(runtime/name, dest)
    records = []
    inputs = {}
    for p in sorted(source.rglob('*')):
        if p.is_symlink() or p.is_junction():
            raise ValueError('linked source')
        if not p.is_file():
            continue
        name = p.relative_to(source).as_posix()
        if name.lower().endswith(('.sav', '.log')):
            continue
        target = runtime/'data'/name
        if not target.is_file():
            raise ValueError('missing runtime source: '+name)
        before_hash, after_hash = sha(p), sha(target)
        inputs[name] = before_hash
        if before_hash == after_hash:
            continue
        if name in {'MOV/0023.BMC', 'MOV/MOV.pak'}:
            raise ValueError('protected original changed: '+name)
        patch = bytearray(b'MCD1')
        patch += struct.pack('<Q', target.stat().st_size)
        with p.open('rb') as before, target.open('rb') as after:
            offset = 0
            while block := after.read(4096):
                if block != before.read(len(block)):
                    patch += struct.pack('<QI', offset, len(block)) + block
                offset += len(block)
        patch_name = f'deltas/{len(records):04d}.mcd'
        dst = output/patch_name
        dst.parent.mkdir(exist_ok=True)
        dst.write_bytes(patch)
        records.append(dict(resource=name, source_sha256=before_hash, target_sha256=after_hash,
                            target_size=target.stat().st_size, patch=patch_name, patch_sha256=sha(dst)))
    for name in ['ddraw.dll', 'DDrawCompat-MagnaCarta.ini']:
        dst = payload/'data'/name
        dst.parent.mkdir(exist_ok=True)
        shutil.copy2(runtime/'data'/name, dst)
    licenses = output/'licenses'
    licenses.mkdir()
    for name in ['LICENSE', 'LICENSE-translations.md', 'LICENSING.md']:
        shutil.copy2(ROOT/name, licenses/name)
    shutil.copy2(ROOT/'assets/licenses/NotoSansSC-OFL.txt', licenses/'NotoSansSC-OFL.txt')
    license_url = 'https://raw.githubusercontent.com/narzoul/DDrawCompat/v0.7.1/LICENSE.txt'
    (licenses/'DDrawCompat-v0.7.1.txt').write_bytes(urllib.request.urlopen(license_url).read())
    for name in ['Install.ps1', 'README.txt']:
        shutil.copy2(ROOT/'assets/player-test-package'/name, output/name)
    (output/'Install.cmd').write_bytes(b'@echo off\r\npowershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install.ps1" %*\r\nif errorlevel 1 pause\r\n')
    manifest = dict(schema=1, source_files=inputs, changes=records,
                    payload={p.relative_to(payload).as_posix():sha(p) for p in payload.rglob('*') if p.is_file()},
                    source_commit=__import__('subprocess').check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                    in_game_verified=False, original_unchanged=True,
                    disc_gate=dict(offset='0x1025',before='BB41000000',after='E9A7000000'),
                    ddraw_license=license_url)
    (output/'package.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    archive = output.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in output.rglob('*'):
            if p.is_file():
                z.write(p,p.relative_to(output))
    print(f'PLAYER_PACKAGE PASS changes={len(records)} source_files={len(inputs)} payload={len(manifest["payload"])} archive_bytes={archive.stat().st_size} sha256={sha(archive)}')
    return manifest

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['source','runtime','output']:
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    build(a.source,a.runtime,a.output)
