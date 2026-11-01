"""Exercise MKIA's full-film sampling with synthetic, rights-free footage.

This is a pipeline test, NOT a playable Filmcode puzzle or film source.
Run: python scripts/mkia_smoke_test.py
Requires ffmpeg, ffprobe and Pillow; uses no network services or secrets.
"""
import json
import subprocess
import tempfile
from pathlib import Path

import mkia
from stills_barcode import generate as generate_stills
from screencap_zip import build as build_screencap_zip, movie_slug, quality_assessment


def command(args):
    subprocess.run(args, check=True, capture_output=True, text=True)


def make_fixture(path):
    # Black head/tail and five long, vivid acts; chronological order matters.
    acts = [
        ("black", 6), ("red", 12), ("cyan", 12), ("yellow", 12),
        ("magenta", 12), ("green", 12), ("black", 6),
    ]
    args = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for color, seconds in acts:
        args += ["-f", "lavfi", "-i", f"color=c={color}:s=320x180:r=2:d={seconds}"]
    filter_graph = "".join(f"[{i}:v]" for i in range(len(acts)))
    filter_graph += f"concat=n={len(acts)}:v=1:a=0,format=yuv420p[v]"
    args += ["-filter_complex", filter_graph, "-map", "[v]",
             "-c:v", "mpeg4", "-q:v", "4", str(path)]
    command(args)


def main():
    with tempfile.TemporaryDirectory(prefix="mkia-smoke-") as directory:
        root = Path(directory)
        source = root / "fixture.mp4"
        make_fixture(source)
        duration = float(json.loads(mkia.run([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "json", str(source),
        ]).stdout)["format"]["duration"])
        assert 71 <= duration <= 73, duration
        assert not mkia.is_monochrome(source), "Color test rejected vivid source"

        start, end = mkia.detect_content_window(source, duration)
        assert 4 <= start <= 8, (start, end)
        assert duration - 8 <= end <= duration - 4, (start, end)

        original_out, original_assets = mkia.OUT, mkia.ASSETS
        try:
            mkia.OUT = root / "dist"
            mkia.ASSETS = mkia.OUT / "assets"
            mkia.ASSETS.mkdir(parents=True)
            stripes = mkia.generate_barcode(source, "test", end - start, start)
            assert 550 <= stripes <= 565, stripes
            report = json.loads((mkia.OUT/'control-room/reviews/test-barcode.json').read_text())
            assert report['primary_treatment'] == 'enhanced'
            assert len(report['original_colors_rgb']) == stripes
            assert report['quality']['status'] in ('candidate', 'needs_review')
            from PIL import Image
            with Image.open(mkia.ASSETS / "test-barcode.png") as barcode:
                assert barcode.size == (stripes, 240), barcode.size
                # All five chronological color acts must be represented.
                samples = [barcode.getpixel((int(stripes * f), 10))
                           for f in (.10, .30, .50, .70, .90)]
                expected_channels = [(0,), (1, 2), (0, 1), (0, 2), (1,)]
                for sample, channels in zip(samples, expected_channels):
                    assert all(sample[c] > 100 for c in channels), samples
            frames = mkia.choose_frames(
                source, {"id": "test", "title": "Synthetic Fixture", "year": 2026},
                end - start, root, start,
            )
            assert len(frames) == 5, frames
            assert len(list(mkia.ASSETS.glob("test-*.jpg"))) >= 5
            assert (mkia.OUT / "control-room/reviews/test.json").exists()
        finally:
            mkia.OUT, mkia.ASSETS = original_out, original_assets
        # Separate pipeline: chronological stills can generate a barcode
        # without implying we sampled the whole movie.
        still_dir = root / 'stills'
        still_dir.mkdir()
        from PIL import Image
        colors = ['#b72e2a', '#22b8c8', '#eac14a', '#a2309f', '#299858']
        shots = []
        for i in range(30):
            filename = f'{i:02d}.png'
            Image.new('RGB', (64, 36), colors[i//6]).save(still_dir/filename)
            shots.append({'file': filename, 'time_seconds': i*90+20})
        manifest = still_dir/'manifest.json'
        manifest.write_text(json.dumps({'movie_id': 'test', 'source': 'Synthetic color fixture',
                                        'duration_seconds': 2700, 'shots': shots}))
        report = generate_stills(manifest, root/'stills-barcode.png', root/'stills-report.json')
        assert report['stripe_count'] == 560
        assert report['sampling'] == 'timestamped_stills'
        assert report['shot_count'] == 30
        assert report['primary_treatment'] == 'enhanced'
        assert 'score' in report['quality']
        assert (root/'stills-report.json').exists()
        # The ZIP importer must honor numbered ordering and exclude black
        # leaders/tails without extracting thousands of frames to disk.
        import io
        import zipfile
        screencaps = root/'synthetic-screencaps.zip'
        with zipfile.ZipFile(screencaps, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for i in range(120):
                color = '#050505' if i < 6 or i >= 114 else colors[min(4, (i-6)//22)]
                buffer = io.BytesIO()
                Image.new('RGB', (80, 45), color).save(buffer, format='PNG')
                archive.writestr(f'stills/frame_{i+1:04d}.png', buffer.getvalue())
        result = build_screencap_zip(screencaps, 'synthetic-test',
                                    root/'zip-barcode.png', root/'zip-report.json',
                                    variants=True)
        assert result['stripe_count'] == 560
        assert result['source_frame_count'] == 120
        assert result['trimmed_opening_frames'] == 6
        assert result['trimmed_ending_frames'] == 6
        assert (root/'zip-barcode.png').exists()
        assert quality_assessment({'median_brightness':91,'colorful_fraction':.595,
                                   'bright_fraction':.091,'palette_variation':21.42})['status'] == 'needs_review'
        assert quality_assessment({'median_brightness':98,'colorful_fraction':.754,
                                   'bright_fraction':.223,'palette_variation':35.25})['status'] == 'candidate'
        assert movie_slug('Hidden Figures (2016).zip') == 'hidden-figures-2016'
        assert movie_slug('hidden-figures(2016).zip') == 'hidden-figures-2016'
        assert movie_slug('Dune (1984).zip') != movie_slug('Dune (2021).zip')
        assert movie_slug('Blade Runner 2049.zip') == 'blade-runner-2049'
        assert (root/'zip-barcode-comparison.png').exists()
        assert set(result['treatments']) == {'original', 'dominant', 'perceptual', 'enhanced'}
        assert result['primary_treatment'] == 'enhanced'
        assert 0 <= result['quality']['score'] <= 100
        assert result['quality']['status'] in ('candidate', 'needs_review')
        for name in result['treatments']:
            assert (root/f'zip-barcode-{name}.png').exists()
        with Image.open(root/'zip-barcode.png') as primary, Image.open(root/'zip-barcode-enhanced.png') as expected:
            assert primary.tobytes() == expected.tobytes()
        import os
        previous = Path.cwd()
        try:
            os.chdir(root)
            default = build_screencap_zip(screencaps, variants=True)
            assert default['movie_id'] == 'synthetic-screencaps'
            assert (root/'generated/synthetic-screencaps/synthetic-screencaps-barcode-comparison.png').exists()
            assert (root/'generated/synthetic-screencaps/synthetic-screencaps-review.json').exists()
        finally:
            os.chdir(previous)
        print(f"MKIA smoke test passed: {stripes} chronological stripes, "
              f"5 legacy frame selections, trimmed black head/tail ({start:.0f}s/{duration-end:.0f}s), "
              '30 timestamped stills and ordered screencap ZIP → 560 stripes')


if __name__ == "__main__":
    main()
