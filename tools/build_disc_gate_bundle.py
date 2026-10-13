"""Package the disc-gate plan, source tools, and an owned compiled launcher."""
import argparse,json,shutil
from pathlib import Path
from patch_binary_plan import digest

def build(launcher,output):
    root=Path(__file__).resolve().parents[1];output=Path(output).resolve();launcher=Path(launcher).resolve(strict=True)
    if output.exists() or launcher.is_relative_to(output):raise ValueError('bundle output must be new')
    inputs={'workspace_launcher.exe':launcher,'disc-gate.json':root/'patches/disc-gate.json',
            'install_disc_gate.py':root/'tools/install_disc_gate.py','patch_binary_plan.py':root/'tools/patch_binary_plan.py',
            'README.md':root/'docs/DISC_GATE.md','LICENSE':root/'LICENSE'}
    snapshots={n:p.read_bytes() for n,p in inputs.items()}
    output.mkdir(parents=True)
    for n,b in snapshots.items():(output/n).write_bytes(b)
    manifest=dict(schema=1,kind='disc_gate_offline_candidate',files={n:digest(b) for n,b in snapshots.items()},
                  engine_sha256=['79e4c3d6af4afb2b75367a2b26fd8450ad25fa9f738612ea96809e312d33cb6f',
                                 '5c701de93af6267b959c49e6927bee525bc0f3c68c8c6f51413515d13809d427'],
                  game_started=False,in_game_verified=False)
    if any(p.read_bytes()!=snapshots[n] for n,p in inputs.items()):raise ValueError('bundle input drift')
    (output/'bundle.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8',newline='\n')
    return manifest

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--launcher',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();build(a.launcher,a.output)
    print('DISC_GATE_BUNDLE PASS proprietary_binary_included=false game_started=false')
