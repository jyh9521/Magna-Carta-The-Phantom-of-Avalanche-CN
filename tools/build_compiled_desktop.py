"""Compile desktop behavior to IL and embed static data; never embed or extract scripts."""
import argparse
import hashlib
import os
from pathlib import Path
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def icon_bytes(icon):
    data = Path(icon).read_bytes()
    if len(data) < 22 or data[:4] != b'\x00\x00\x01\x00':
        raise ValueError('Valid ICO input required')
    count = struct.unpack_from('<H', data, 4)[0]
    if not 1 <= count <= 64 or len(data) < 6+16*count:
        raise ValueError('Invalid icon directory')
    for i in range(count):
        length, offset = struct.unpack_from('<II', data, 6+16*i+8)
        if not length or offset < 6+16*count or offset+length > len(data):
            raise ValueError('Invalid icon image bounds')
    return data


def compiler():
    return Path(os.environ['WINDIR'])/'Microsoft.NET/Framework/v4.0.30319/csc.exe'


def entries(output, icon):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    icon = Path(icon).resolve()
    icon_bytes(icon)
    for name, define in [('Configure', True), ('Game', False)]:
        target = output/(name+'.exe')
        args = [str(compiler()), '/nologo', '/target:winexe', '/platform:anycpu', '/optimize+',
                '/reference:System.Windows.Forms.dll', '/win32icon:'+str(icon),
                '/win32manifest:'+str(ROOT/'src/desktop/app.manifest'), '/out:'+str(target)]
        if define:
            args.append('/define:CONFIGURE')
        subprocess.run(args+[str(ROOT/'src/desktop/CompiledEntry.cs')], check=True)
    return {n: (output/n).read_bytes() for n in ('Configure.exe', 'Game.exe')}


def core(output, resources):
    output, resources = Path(output).resolve(), Path(resources).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    framework = compiler().parent
    args = [str(compiler()), '/nologo', '/target:library', '/platform:anycpu', '/optimize+',
            '/out:'+str(output), '/reference:System.Core.dll', '/reference:System.Web.Extensions.dll',
            '/reference:'+str(framework/'WPF/WindowsBase.dll'),
            '/reference:'+str(framework/'WPF/PresentationCore.dll'),
            '/reference:'+str(framework/'WPF/PresentationFramework.dll'), '/reference:System.Xaml.dll']
    for path in sorted(resources.rglob('*')):
        if not path.is_file():
            continue
        if path.suffix.lower() in ('.ps1', '.psm1', '.cs', '.cmd', '.bat', '.py'):
            raise ValueError('Source code cannot be a runtime resource: '+path.name)
        name = path.relative_to(resources).as_posix()
        args.append('/resource:'+str(path)+',mc/'+name)
    sources = ['RuntimeCore.cs', 'Configuration.cs', 'Elevation.cs']
    subprocess.run(args+[str(ROOT/'src/desktop'/n) for n in sources], check=True)
    print('COMPILED_DESKTOP PASS core_sha256='+hashlib.sha256(output.read_bytes()).hexdigest())


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--icon', type=Path, required=True)
    p.add_argument('--resources', type=Path, required=True)
    a = p.parse_args()
    entries(a.output, a.icon)
    core(a.output/'modules/DesktopRuntime.dll', a.resources)
