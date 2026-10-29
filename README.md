# Filmcode — daily movie color barcode game

Play: https://aprilswang.github.io/filmcode/

Each day, Filmcode shows a color barcode generated from a film. Players choose one of four movie titles; afterward, five movie frames reveal the answer. Progress and streaks are stored locally in the browser.

## Hosting and automation

- **Public repository (`aprilSwang/filmcode`)** contains the static player website and reusable generation scripts.
- **Private repository (`aprilSwang/filmcode-admin`)** owns MKIA's full queue, approved movie sources, research catalog, candidate frames, and daily publishing schedule.
- The private `MKIA — private daily publisher` GitHub Action runs at **00:05 UTC**, prepares the next approved film when possible, and pushes **only the current day's puzzle and six game images** to the public repository.
- The public `Filmcode — deploy website` GitHub Action builds and deploys GitHub Pages when the public repository changes.
- GitHub's scheduled Actions are not guaranteed to start at the exact scheduled minute. Until the next daily payload arrives, the game displays a temporary availability message.

To preview locally:

```bash
python3 -m http.server 8000 --directory dist
```

Open http://localhost:8000.

## Content and licensing

MKIA processes only video sources with configured rights metadata; it does not scrape or automatically license commercial movies. The existing launch-era demo films include openly licensed productions and public-domain footage. A ShotDeck subscription is not treated as permission to scrape or republish images.

## Security limitations

The public payload necessarily contains the **current day's answer**, which a determined player can inspect. Future answers are no longer present in the current public tree, but **earlier public commits still contain historic queued answers and assets**. Fully preventing historical Git access would require a separate, carefully planned history rewrite, and static hosting cannot prevent inspection of today's answer.

Administration and full movie queues belong in the private `filmcode-admin` repository. Do not add secrets, research queues, candidate frames, or future answers to this public repository.
