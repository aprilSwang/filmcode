"""Report how many scheduled Filmcode puzzles remain from today (UTC)."""
import json
import os
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    data = json.loads((ROOT / 'dist' / 'puzzles.json').read_text())
    catalog = json.loads((ROOT / 'catalog.json').read_text())
    today = datetime.now(timezone.utc).date()
    launch = date.fromisoformat(data['launch_date'])
    puzzles = data['puzzles']
    elapsed = max(0, (today - launch).days)
    remaining = max(0, len(puzzles) - elapsed)
    completed = {item['id'] for item in puzzles}
    available = sum(1 for item in catalog if item['id'] not in completed and item.get('video_url') and item.get('license'))
    minimum = int(os.getenv('MKIA_MIN_DAYS', '7'))
    print(f'MKIA queue: {remaining} playable day(s) remaining; {available} unused approved source(s).')
    print(f'Queue target: {minimum} days. Status: {"LOW" if remaining < minimum else "OK"}.')
    output = os.getenv('GITHUB_OUTPUT')
    if output:
        with open(output, 'a') as f:
            f.write(f'remaining={remaining}\navailable={available}\nlow={str(remaining < minimum).lower()}\n')


if __name__ == '__main__':
    main()
