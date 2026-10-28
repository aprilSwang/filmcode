"""Generate one queued daily puzzle from an approved film source.

Add licensed titles and video URLs to catalog.json. A nightly job processes
the next ungenerated item and appends its metadata to dist/puzzles.json.
"""
import json
from pathlib import Path
import subprocess
import tempfile
import urllib.request
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'catalog.json'
PUZZLES = ROOT / 'dist/puzzles.json'
ASSETS = ROOT / 'dist/assets'
ASSETS.mkdir(exist_ok=True, parents=True)

def run(command):
    return subprocess.run(command, check=True, capture_output=True)

def generate(film):
    with tempfile.TemporaryDirectory(prefix='chroma-film-') as directory:
        video = Path(directory) / 'source.video'
        request = urllib.request.Request(film['video_url'], headers={'User-Agent':'CHROMA-film-game/1.0 (licensed media processor)'})
        with urllib.request.urlopen(request, timeout=120) as response, video.open('wb') as output:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk: break
                output.write(chunk)
        duration = float(json.loads(run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(video)]).stdout)['format']['duration'])
        count = 560
        raw = run(['ffmpeg','-v','error','-i',str(video),'-vf',f'fps={count/duration:.8f},scale=24:14,format=rgb24','-f','rawvideo','-']).stdout
        stride = 24*14*3
        colors=[]
        for start in range(0,len(raw)-stride+1,stride):
            sample=raw[start:start+stride]
            colors.append(tuple(sum(sample[channel::3])//(24*14) for channel in range(3)))
        if len(colors)<50: raise RuntimeError('Unexpectedly few frames')
        barcode=Image.new('RGB',(len(colors),240));draw=ImageDraw.Draw(barcode)
        for x,color in enumerate(colors):draw.line((x,0,x,239),fill=color)
        barcode.save(ASSETS/f"{film['id']}-barcode.png",optimize=True)
        for i,fraction in enumerate((.10,.29,.48,.67,.87),1):
            run(['ffmpeg','-v','error','-ss',str(duration*fraction),'-i',str(video),'-frames:v','1','-vf','scale=720:-2','-y',str(ASSETS/f"{film['id']}-{i}.jpg")])

def main():
    catalog=json.loads(CATALOG.read_text())
    db=json.loads(PUZZLES.read_text())
    existing={film['id'] for film in db['puzzles']}
    pending=next((film for film in catalog if film['id'] not in existing),None)
    if not pending:
        print('No approved movies left in queue. No change; add catalog entries.')
        return
    if not pending.get('video_url') or not pending.get('license'):
        raise ValueError('Every film requires a verified source URL and license')
    generate(pending)
    db['puzzles'].append({key:value for key,value in pending.items() if key!='video_url'})
    PUZZLES.write_text(json.dumps(db,indent=2,ensure_ascii=False)+'\n')
    print(f"Generated: {pending['title']}")

if __name__=='__main__':main()
