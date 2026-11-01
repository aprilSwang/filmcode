# Filmcode — movie barcode guessing game

Site: https://aprilswang.github.io/filmcode/

**Status: temporarily paused for a complete movie-catalog relaunch.** The initial pilot queue and generated images have been removed from the current branch. The public website displays a relaunch page and no active daily puzzle.

## Architecture

- GitHub Pages publishes the static files in `dist/` using `.github/workflows/deploy.yml`.
- [Private MKIA repository](https://github.com/aprilSwang/filmcode-admin) retains the generation code integration and future curation process.
- MKIA's **automatic daily publisher is paused** until new film footage is cleared, barcodes are generated, and a new launch date is chosen.
- The old game frontend code remains available for restoration in `dist/app.js`, but is not loaded on the relaunch page.

## Rights

Famous-film research metadata does not grant permission to download or republish underlying movie footage. New sources will be checked individually before entering the playable queue. See [copyright and content reports](https://aprilswang.github.io/filmcode/copyright.html).

## Offline screencap ZIP pilot

Use only an archive you are authorized to process. The importer does not fetch websites, scrape galleries, publish screencaps, or upload the ZIP. It processes numbered local image filenames, removes sustained near-black edges, and emits a Method B barcode plus a source/quality report. Filename order is **assumed**, so verify the actual movie sequence manually.

```bash
python -m pip install Pillow
python scripts/screencap_zip.py --zip /path/to/approved-screenshots.zip \
  --movie-id test-movie --output /tmp/test-movie-barcode.png \
  --report /tmp/test-movie-review.json
```

This is a private curation tool, not a scheduled image downloader. Add a separately authorized poster and review results before scheduling a puzzle. The full ZIP should not be committed to GitHub.

### Compare barcode color treatments

Rerun the same approved ZIP with `--variants` to generate `*-original.png`, `*-dominant.png`, `*-perceptual.png`, `*-enhanced.png` and `*-comparison.png` in one pass. The original output path remains the unmodified average baseline. The review JSON contains per-method brightness, colorful fraction and bright fraction. Color treatments are preview experiments; review before using one in a public puzzle.

```bash
python3 scripts/screencap_zip.py --zip 'hidden-figures(2016).zip' \
  --movie-id hidden-figures --output hidden-figures-barcode.png \
  --report hidden-figures-review.json --variants
```
