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
