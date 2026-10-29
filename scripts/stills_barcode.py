"""Build a *chronological-stills* Filmcode barcode from approved local images.

This intentionally does not download, search, scrape or access ShotDeck.
Inputs are images provided separately with permission for the intended use.

Manifest: {"movie_id": "slug", "source": "source description",
           "shots": [{"file": "01.jpg", "time_seconds": 125.0}, ...],
           "duration_seconds": 7200}  # duration and times are optional together
Without timestamps, each still gets equal timeline weight; the result is an
ordered approximation, NOT evenly sampled full-film footage.
"""
import argparse
import json
import math
from bisect import bisect_right
from pathlib import Path

from PIL import Image, ImageDraw, ImageStat


STRIPES = 560


def representative_color(path):
    with Image.open(path) as raw:
        image = raw.convert('RGB').resize((32, 18))
    # A softened mean retains the shot's overall atmosphere, avoiding a
    # single object or highlight taking over the bar's color.
    return tuple(round(x) for x in ImageStat.Stat(image).mean)


def generate(manifest_path, output_path, report_path=None):
    manifest_path = Path(manifest_path).resolve()
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    shots = manifest.get('shots', [])
    if len(shots) < 12:
        raise ValueError('Need at least 12 chronological stills; 30+ recommended')
    if len(shots) > 5000:
        raise ValueError('Too many stills (maximum 5000)')
    if not manifest.get('source'):
        raise ValueError('Manifest requires a descriptive source')
    root = manifest_path.parent
    images = []
    for entry in shots:
        relative = Path(entry['file'])
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError(f'Shot path missing or outside the manifest directory: {relative}')
        images.append(representative_color(path))
    has_times = ['time_seconds' in shot for shot in shots]
    if any(has_times) and not all(has_times):
        raise ValueError('Provide timestamps for every shot or for none')
    if all(has_times):
        duration = float(manifest['duration_seconds'])
        times = [float(shot['time_seconds']) for shot in shots]
        if not (math.isfinite(duration) and duration > 0):
            raise ValueError('Invalid film duration')
        if any(not math.isfinite(t) or not 0 <= t <= duration for t in times):
            raise ValueError('All timestamps must fall within the film duration')
        if times != sorted(times) or len(set(times)) != len(times):
            raise ValueError('Shot timestamps must be strictly increasing')
        # Assign each shot the section of film nearest its timecode.
        boundaries = [(a+b)/2 for a,b in zip(times, times[1:])]
        stripes = [images[bisect_right(boundaries, duration * (i+.5)/STRIPES)]
                   for i in range(STRIPES)]
        mode = 'timestamped_stills'
        edge_coverage = (round(times[0]/duration, 3),
                         round((duration-times[-1])/duration, 3))
    else:
        stripes = [images[min(len(images)-1, int((i+.5)*len(images)/STRIPES))]
                   for i in range(STRIPES)]
        mode = 'ordered_stills_equal_weight'
        edge_coverage = None
    # Reject effectively monochrome material, but do not require every scene
    # to be saturated (many legitimate films contain intentional darkness).
    colorful = sum(max(c)-min(c) >= 20 for c in images)
    if colorful / len(images) < .15:
        raise ValueError('Stills are predominantly monochrome or nearly grayscale')
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    barcode = Image.new('RGB', (STRIPES, 240))
    draw = ImageDraw.Draw(barcode)
    for x, color in enumerate(stripes):
        draw.line((x, 0, x, 239), fill=color)
    barcode.save(output_path, optimize=True)
    report = {'movie_id': manifest.get('movie_id'), 'method': 'B',
              'sampling': mode, 'source': manifest['source'],
              'shot_count': len(shots), 'stripe_count': STRIPES,
              'colorful_fraction': round(colorful/len(images), 3),
              'uncovered_edge_fraction': edge_coverage,
              'note': 'Chronological still-based approximation; not full-film video sampling.'}
    if report_path:
        report_path = Path(report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    print(json.dumps(generate(args.manifest, args.output, args.report), indent=2))
