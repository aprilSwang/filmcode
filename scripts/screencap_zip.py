"""MKIA screencap ZIP importer — local, permission-cleared archives only.

Never downloads galleries or stores frames in the repository. A ZIP's image
filenames are natural-sorted; numbered names are required for an ordered
timeline. The report records that timestamp/coverage accuracy is *estimated*.

Usage:
  python scripts/screencap_zip.py --zip '/path/to/Film Name (2016).zip' --variants

By default results go to generated/film-name/film-name-barcode*.png,
with the review JSON alongside them. --movie-id, --output and --report
are optional overrides for existing automation.
"""
import argparse
import colorsys
import hashlib
import io
import json
import math
import re
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageStat

STRIPES = 560
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}


def movie_slug(zip_path):
    name = Path(zip_path).stem
    name = re.sub(r'\s*[\[(](?:19|20)\d{2}[\])](?=\s*$)', '', name)
    slug = re.sub(r'[^a-z0-9]+', '-', name.casefold()).strip('-')
    if not slug:
        raise ValueError('Cannot determine movie name from ZIP filename; use --movie-id')
    return slug


def natural_key(name):
    return [int(part) if part.isdigit() else part.casefold()
            for part in re.split(r'(\d+)', name)]


def candidates(archive):
    entries = [member for member in archive.infolist()
               if not member.is_dir()
               and Path(member.filename).suffix.lower() in IMAGE_EXTENSIONS
               and '__MACOSX' not in Path(member.filename).parts
               and not Path(member.filename).name.startswith('.')]
    if len(entries) > 50000:
        raise ValueError('Too many image entries; maximum is 50,000')
    if len(entries) < 30:
        raise ValueError('At least 30 ordered screenshots are needed for a ZIP pilot')
    if sum(item.file_size for item in entries) > 15_000_000_000:
        raise ValueError('Uncompressed image size exceeds the 15 GB cap')
    if any(item.file_size > 100_000_000 for item in entries):
        raise ValueError('An image is too large (>100 MB)')
    # Archives often include both thumb and full-size folders. Prefer the
    # directory with the most images, but never merge disjoint sequences.
    groups = {}
    for entry in entries:
        groups.setdefault(str(Path(entry.filename).parent), []).append(entry)
    folder, chosen = max(groups.items(), key=lambda pair: len(pair[1]))
    if len(chosen) < 30:
        raise ValueError('No single folder contains 30 ordered screenshots')
    chosen.sort(key=lambda x: natural_key(Path(x.filename).name))
    numeric = [re.findall(r'\d+', Path(entry.filename).stem) for entry in chosen]
    if sum(bool(x) for x in numeric)/len(numeric) < .95:
        raise ValueError('Screenshot names must contain sortable frame numbers')
    if len({Path(e.filename).name for e in chosen}) != len(chosen):
        raise ValueError('Duplicate screenshot filenames')
    return folder, chosen


def enhance(color, gamma=.72, saturation=1.3):
    """Contrast-preserving, hue-preserving display treatment for dark films."""
    r, g, b = [v/255 for v in color]
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    s = min(1, s*saturation)
    v = min(1, v**gamma)
    return tuple(round(c*255) for c in colorsys.hsv_to_rgb(h, s, v))


def weighted_color(pixels):
    channels = [0., 0., 0.]
    total = 0.
    for color in pixels:
        h, s, v = colorsys.rgb_to_hsv(*(c/255 for c in color))
        weight = (.15 + 2.4*s**1.7)*(.15 + v**.65)
        for n in range(3):
            channels[n] += color[n]*weight
        total += weight
    return tuple(round(c/total) for c in channels)


def dominant_color(pixels):
    """Find a meaningful hue cluster; ignore pure black and grey dominance."""
    bins = {}
    for color in pixels:
        h, s, v = colorsys.rgb_to_hsv(*(c/255 for c in color))
        if v < .10 or s < .10:
            continue
        bucket = min(11, int(h*12))
        weight = s**1.2*(.25+v)
        count, rgb = bins.setdefault(bucket, [0., [0., 0., 0.]])
        bins[bucket][0] += weight
        for n in range(3):
            rgb[n] += color[n]*weight
    if not bins:
        return weighted_color(pixels)
    count, rgb = max(bins.values(), key=lambda entry: entry[0])
    return tuple(round(c/count) for c in rgb)


def inspect_image(archive, member, variants=False):
    with archive.open(member) as file:
        content = file.read()
    with Image.open(io.BytesIO(content)) as raw:
        image = raw.convert('RGB')
        # Exclude typical letterbox bars and frame-edge overlays.
        w, h = image.size
        image = image.crop((int(w*.02), int(h*.12), int(w*.98), int(h*.88)))
        image.thumbnail((48, 27))
        mean = tuple(round(v) for v in ImageStat.Stat(image).mean)
        gray = image.convert('L')
        pixels = list(gray.getdata())
        near_black = sum(v < 32 for v in pixels)/len(pixels)
        dark = sum(pixels)/len(pixels) < 38 and near_black > .86
        if variants:
            pixels = list(image.getdata())
            perceptual = enhance(weighted_color(pixels), gamma=.80, saturation=1.22)
            dominant = enhance(dominant_color(pixels), gamma=.88, saturation=1.16)
            enhanced = enhance(mean, gamma=.64, saturation=1.4)
            return {'original': mean, 'dominant': dominant,
                    'perceptual': perceptual, 'enhanced': enhanced}, dark
    return mean, dark


def render_barcode(colors, output):
    out = Image.new('RGB', (STRIPES, 240))
    draw = ImageDraw.Draw(out)
    for x, color in enumerate(colors):
        draw.line((x, 0, x, 239), fill=color)
    output.parent.mkdir(parents=True, exist_ok=True)
    out.save(output, optimize=True)


def metrics(colors):
    return {
        'mean_rgb': [round(sum(c[i] for c in colors)/len(colors)) for i in range(3)],
        'median_brightness': sorted(max(c) for c in colors)[len(colors)//2],
        'colorful_fraction': round(sum(max(c)-min(c) >= 20 for c in colors)/len(colors), 3),
        'bright_fraction': round(sum(max(c) >= 130 for c in colors)/len(colors), 3),
    }


def comparison_image(paths, destination):
    order = ('original', 'dominant', 'perceptual', 'enhanced')
    width, block_height = STRIPES, 280
    sheet = Image.new('RGB', (width, block_height*4+32), '#101116')
    draw = ImageDraw.Draw(sheet)
    for i, name in enumerate(order):
        y = i*block_height+18
        draw.text((12, y-14), name.upper().replace('-', ' '), fill='white')
        with Image.open(paths[name]) as frame:
            sheet.paste(frame, (0, y+12))
    sheet.save(destination, optimize=True)


def build(zip_path, movie_id=None, output=None, report=None, variants=False):
    zip_path = Path(zip_path)
    movie_id = movie_id or movie_slug(zip_path)
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', movie_id):
        raise ValueError('movie_id must be a lowercase hyphenated slug')
    if output is None:
        destination = Path('generated') / movie_id
        output = destination / f'{movie_id}-barcode.png'
        if report is None:
            report = destination / f'{movie_id}-review.json'
    digest = hashlib.sha256()
    with zip_path.open('rb') as input_file:
        for block in iter(lambda: input_file.read(1024*1024), b''):
            digest.update(block)
    with zipfile.ZipFile(zip_path) as archive:
        folder, frames = candidates(archive)
        total = len(frames)
        # Only trim sustained black footage at the edges. Sample at most 20%
        # of the archive on either side, leaving dark narrative scenes intact.
        limit = min(int(total*.20), 500)
        first, last = 0, total-1
        while first < limit and inspect_image(archive, frames[first])[1]:
            first += 1
        while last >= total-1-limit and inspect_image(archive, frames[last])[1]:
            last -= 1
        if first > 0 and first < 2:
            first = 0
        if last < total-1 and total-1-last < 2:
            last = total-1
        if last-first+1 < max(30, total*.5):
            raise ValueError('Too few frames remain after edge trimming')
        usable = last-first+1
        indices = [first + min(usable-1, int((i+.5)*usable/STRIPES))
                   for i in range(STRIPES)]
        cache = {}
        colors = []
        for index in indices:
            if index not in cache:
                cache[index] = inspect_image(archive, frames[index], variants=variants)[0]
            colors.append(cache[index])
    original = [x['original'] for x in colors] if variants else colors
    fraction = sum(max(c)-min(c) >= 20 for c in original)/len(original)
    if fraction < .15:
        raise ValueError('Images are predominantly monochrome; not suitable for Filmcode')
    output = Path(output)
    if variants:
        outputs = {}
        for name in ('original', 'dominant', 'perceptual', 'enhanced'):
            path = output.with_name(output.stem+'-'+name+output.suffix)
            render_barcode([entry[name] for entry in colors], path)
            outputs[name] = path
        # Preserve the user's existing output argument as the unmodified
        # baseline, while the named files make comparisons explicit.
        render_barcode(original, output)
        comparison = output.with_name(output.stem+'-comparison.png')
        comparison_image(outputs, comparison)
    else:
        render_barcode(colors, output)
    result = {
        'movie_id': movie_id, 'method': 'B',
        'sampling': 'ordered_screencap_zip_equal_weight',
        'source_zip_sha256': digest.hexdigest(),
        'source_folder': folder, 'source_frame_count': total,
        'first_kept_index': first, 'last_kept_index': last,
        'trimmed_opening_frames': first,
        'trimmed_ending_frames': total-1-last,
        'stripe_count': STRIPES,
        'sampled_unique_frames': len(cache),
        'colorful_stripe_fraction': round(fraction, 3),
        'first_filename': Path(frames[first].filename).name,
        'last_filename': Path(frames[last].filename).name,
        'caution': 'Numbered screenshot order is assumed, not verified against film timecodes. Review sequence and usage rights before publishing.',
    }
    if variants:
        result['treatments'] = {
            name: {'file': outputs[name].name,
                   **metrics([entry[name] for entry in colors])}
            for name in outputs
        }
        result['comparison_file'] = comparison.name
    if report:
        report = Path(report)
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--zip', required=True, type=Path)
    parser.add_argument('--movie-id', help='Optional override; normally inferred from ZIP filename')
    parser.add_argument('--output', type=Path, help='Optional output path; defaults to generated/<movie-name>/')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--variants', action='store_true',
                        help='Generate four color treatments and a comparison sheet')
    args = parser.parse_args()
    print(json.dumps(build(args.zip, args.movie_id, args.output, args.report, args.variants), indent=2))
