"""Check the source inventory and current documentation without local game inputs."""
import argparse
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
CURRENT_DOCS = ('README.md', 'BUILDING.md', 'CONTRIBUTING.md')
GENERATED_ROOTS = {'build', 'dist', 'out', 'runtime', 'game', '__pycache__', '.venv'}
GENERATED_SUFFIXES = {'.exe', '.dll', '.pdb', '.obj', '.pyc', '.sav', '.log', '.iso', '.zip'}
LINK = re.compile(r'!?\[[^\]\n]*\]\(([^)\n]+)\)')


def tracked_paths(root):
    result = subprocess.run(['git', '-C', str(root), 'ls-files', '-z'],
                            check=True, capture_output=True)
    return result.stdout.decode('utf8').rstrip('\0').split('\0')


def audit(root, paths=None):
    root = Path(root).resolve()
    paths = set(tracked_paths(root) if paths is None else paths)
    errors, links = [], 0
    total = 0
    for name in sorted(paths):
        relative = PurePosixPath(name)
        if (not name or relative.is_absolute() or '..' in relative.parts
                or '\\' in name or ':' in name or relative.as_posix() != name):
            errors.append('invalid source path: ' + name)
            continue
        file = root/name
        if not file.is_file():
            errors.append('missing tracked source: ' + name)
            continue
        if not file.resolve().is_relative_to(root) or file.is_symlink():
            errors.append('linked source: ' + name)
            continue
        total += file.stat().st_size
        if (relative.parts[0] in GENERATED_ROOTS or '__pycache__' in relative.parts
                or relative.suffix.lower() in GENERATED_SUFFIXES):
            errors.append('generated file in source inventory: ' + name)
        if relative.name == '.gitkeep' and any(
                other != name and PurePosixPath(other).is_relative_to(relative.parent)
                for other in paths):
            errors.append('redundant directory placeholder: ' + name)
    for name in CURRENT_DOCS:
        if name not in paths or not (root/name).is_file():
            errors.append('missing current guide: ' + name)
            continue
        for target in LINK.findall((root/name).read_text(encoding='utf-8-sig')):
            target = target.strip().strip('<>')
            parts = urlsplit(target)
            if parts.scheme or parts.netloc or not parts.path:
                continue
            path = ((root/name).parent/unquote(parts.path)).resolve()
            if not path.is_relative_to(root):
                errors.append('guide link escapes source tree: ' + name + ' -> ' + target)
                continue
            relative = path.relative_to(root).as_posix()
            links += 1
            if relative not in paths or not path.is_file():
                errors.append('guide link is not tracked: ' + name + ' -> ' + target)
    return dict(files=len(paths), bytes=total, local_links=links, errors=errors,
                game_started=False, requires_local_runtime=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    report = audit(args.root)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')
    for error in report['errors']:
        print(error)
    state = 'FAIL' if report['errors'] else 'PASS'
    print(f'SOURCE_TREE {state} files={report["files"]} local_links={report["local_links"]} '
          f'errors={len(report["errors"])} game_started=false')
    return int(bool(report['errors']))


if __name__ == '__main__':
    raise SystemExit(main())
