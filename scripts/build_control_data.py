"""Build read-only control-room data for the static GitHub Pages deployment."""
import json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'dist' / 'control-room' / 'data.json'


def main():
    puzzles = json.loads((ROOT / 'dist' / 'puzzles.json').read_text())
    catalog = json.loads((ROOT / 'catalog.json').read_text())
    by_id = {movie['id']: movie for movie in catalog}
    start = date.fromisoformat(puzzles['launch_date'])
    scheduled = []
    for index, puzzle in enumerate(puzzles['puzzles']):
        scheduled.append({
            'id': puzzle['id'], 'title': puzzle['title'], 'year': puzzle.get('year'),
            'date': (start + timedelta(days=index)).isoformat(),
            'choices': puzzle['choices'], 'answer': puzzle['answer'],
            'license': puzzle.get('license'), 'source': puzzle.get('source'),
            'plot_summary': by_id.get(puzzle['id'], {}).get('plot_summary'),
        })
    used = {entry['id'] for entry in scheduled}
    pending = [{
        'id': movie['id'], 'title': movie['title'], 'year': movie.get('year'),
        'license': movie.get('license'), 'source': movie.get('source'),
        'plot_summary': movie.get('plot_summary'),
    } for movie in catalog if movie['id'] not in used]
    research_path = ROOT / 'research_catalog.json'
    research = json.loads(research_path.read_text()) if research_path.exists() else []
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({'scheduled': scheduled, 'pending': pending, 'research': research}, ensure_ascii=False, indent=2) + '\n')
    print(f'Control Room: {len(scheduled)} generated, {len(pending)} approved sources, {len(research)} research candidates')


if __name__ == '__main__':
    main()
