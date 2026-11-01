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
python3 scripts/screencap_zip.py --zip '/path/to/Film Name (2016).zip' --variants
```

This is a private curation tool, not a scheduled image downloader. Add a separately authorized poster and review results before scheduling a puzzle. The full ZIP should not be committed to GitHub.

### Compare barcode color treatments

Rerun the same approved ZIP with `--variants` to generate `*-original.png`, `*-dominant.png`, `*-perceptual.png`, `*-enhanced.png` and `*-comparison.png` in one pass. The primary barcode output now uses the Enhanced treatment; the unmodified average is kept separately as `*-original.png`. The review JSON contains per-method brightness, colorful fraction and bright fraction. Color treatments are preview experiments; review before using one in a public puzzle.

```bash
python3 scripts/screencap_zip.py --zip 'hidden-figures(2016).zip' --variants
```

The ZIP filename automatically determines the movie name. Results are saved together under `generated/<movie-name-year>/` (for example, `generated/hidden-figures-2016/hidden-figures-2016-barcode-comparison.png`). The `--movie-id`, `--output` and `--report` arguments remain optional overrides. `generated/` and the local Python environment are Git-ignored.

### MKIA quality gate

Every generated barcode has a 0–100 visual quality score and explanatory flags (brightness, colorfulness, highlights and palette variation). The primary treatment is **Enhanced** for screencap ZIPs, full-film video and chronological stills. Scores below 75 or individual warning thresholds are marked `needs_review`; higher scores are only visual *candidates*. This does **not** verify source rights, chronological accuracy or how easily players can guess the answer. Original RGB samples are retained for full-film video, and comparison variants retain the original ZIP averages.

Release years in ZIP filenames are preserved in the slug to distinguish remakes (e.g., `Dune (2021).zip` → `dune-2021`). Existing generated folders are not renamed automatically.
