# Filmcode — movie barcode guessing game

Website: https://playfilmcode.com/

**Status: temporarily paused for the movie-catalog relaunch.** The public GitHub Pages site remains a static relaunch page until new film barcodes have been reviewed and a future launch date has been set.

## Architecture

- This **public repository** contains only the game UI, player-facing metadata, and approved daily assets under `dist/`.
- [Private MKIA repository](https://github.com/aprilSwang/filmcode-admin) owns movie research, ZIP processing, barcode generation, video/stills processing, quality checks, multiple-choice suggestions, private Control Room and publishing approvals.
- GitHub Pages deploys `dist/` via [the deploy workflow](.github/workflows/deploy.yml). The daily publisher remains paused.

## Preparing a local screencap ZIP

The former `scripts/screencap_zip.py` and MKIA generation scripts were moved to the private admin repository. After cloning that repository and installing Pillow there, run:

```bash
cd /path/to/filmcode-admin
python3 scripts/mkia.py --zip '/path/to/Dune (2021).zip'
```

The generator creates four barcode treatments, a private quality report, four proposed movie-title choices and a review entry. Original ZIPs and screenshots stay on the operator's computer. Imported candidates are not added to the public daily queue without explicit approvals and footage/poster usage checks.

## Rights

Research metadata and access to a screencap gallery do not imply permission to republish film footage, posters or derived visual assets. Sources must be reviewed individually before publication. See the site's [copyright and content reports](https://playfilmcode.com/copyright.html).
