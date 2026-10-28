# Filmcode daily movie guessing game

**MKIA (Movie Know-It-All)** discovers eligible films, chooses the next movie,
generates multiple-choice answers, barcodes, and reveal frames. **Filmcode** is
the provisional player-facing game brand.

Static, mobile-first daily movie challenge. One shared puzzle per UTC day, four
choices, one guess, five reveal frames, countdown, and browser-local streaks.

## Run locally

From this directory:

```bash
python3 -m http.server 8000 --directory dist
```

Open http://localhost:8000. The game uses `fetch` for the puzzle catalog, so
opening `index.html` directly from the filesystem may be blocked by browser
file-origin restrictions.

## Daily automation

The included GitHub Actions workflow runs each day at **00:05 UTC**. MKIA first
discovers openly licensed film sources from Wikimedia Commons using machine-readable
license metadata. Unknown film identities and ambiguous rights are recorded in
`discovery_review.json` instead of published. MKIA then selects an unused film,
favors well-known films
and variety over recent genres, and automatically builds four answer choices
using `choice_pool.json`. It uses FFmpeg to sample roughly 560 frames, creates
a barcode, selects five high-detail frames spread through the movie, appends
the puzzle, then deploys the static site with GitHub Pages.

Enable GitHub Pages **Source: GitHub Actions** in the repository settings and
keep Actions enabled. A push also deploys the initial catalog. The workflow
requires write permission to commit generated assets.

The discovery feed is limited; it won't automatically obtain Hollywood movies.
To expand beyond the openly licensed sources, add entries to `catalog.json` with a lawfully usable video URL,
title, year, genre tags, and rights/source reference. The bot chooses the
answer distractors and reveal frames automatically. It does **not** acquire
commercial movie videos on its own. It stops when the approved queue
is empty. To inspect the next selection without downloading anything, run
`python scripts/mkia.py --dry-run`.

Three pilot films are pre-generated (Big Buck Bunny, A Trip to the Moon and
Coffee Run), and three more Blender films are in the approved input queue.
Add additional approved films before the catalog runs out. Editing `launch_date` in
`dist/puzzles.json` changes the day assigned to the first film; later films
follow in array order. Avoid changing this after launch, or existing streaks
and puzzle assignments will shift.

## Production caveats

- Local storage is per device; no accounts or cross-device sync.
- Answer data is in public JSON, so this is a casual game, not cheat-proof.
- GitHub scheduled workflows can be delayed; the two-day seed gives a small buffer.
- The project has **not** been published or scheduled on a user-owned GitHub
  account. The workflow becomes active only after repository setup.
- Film assets and sources must be checked for appropriate rights before adding
  them to the catalog.
