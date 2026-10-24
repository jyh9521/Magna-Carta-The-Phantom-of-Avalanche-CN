"""Package scene/fade observations for the exact installed diagnostic baseline."""
import argparse
from pathlib import Path
from build_audio_provider_update import build as build_update


def build(previous, previous_sha256, module, work, output):
    return build_update(previous, previous_sha256, module, work, output, policy='blockers')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('previous', 'module', 'work', 'output'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--previous-sha256', required=True)
    build(**vars(p.parse_args()))
