"""Export only player-facing Filmcode assets for GitHub Pages.

The Control Room is a research/admin tool and is deliberately not deployed.
Note: this does not secure puzzle answers already tracked in a public GitHub repo.
"""
import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'


def export(destination):
    destination = destination.resolve()
    if destination == DIST or DIST in destination.parents:
        raise ValueError('The export destination must be outside dist/')
    if destination.exists():
        raise FileExistsError(f'Refusing to overwrite existing export: {destination}')
    shutil.copytree(DIST, destination, ignore=shutil.ignore_patterns('control-room'))
    print(f'Exported player site to {destination} without Control Room')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('destination', type=Path)
    export(parser.parse_args().destination)
