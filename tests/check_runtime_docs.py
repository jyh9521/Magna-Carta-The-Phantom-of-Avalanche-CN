"""Compatibility entry point for current source/documentation checks."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from check_source_tree import audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--expect', choices=['modified'], default='modified')
    args = parser.parse_args()
    result = audit(args.root)
    for error in result['errors']:
        print(error)
    state = 'FAIL' if result['errors'] else 'PASS'
    print(f'DOCS_CHECK MODIFIED {state} files={result["files"]} '
          f'links={result["local_links"]} game_started=false')
    return int(bool(result['errors']))


if __name__ == '__main__':
    raise SystemExit(main())
