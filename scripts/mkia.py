"""MKIA (Movie Know-It-All): autonomous curator for the Filmcode game.

The bot only handles entries with explicitly configured video URLs and rights
metadata. It never searches for unauthorized video copies or scrapes film sites.
"""
import argparse
import hashlib
import json
import math
import random
import shutil
import subprocess
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw
from shot_selector import features, shortlist, select_five, vision_review
from stills_barcode import generate as generate_stills_barcode

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'dist'
ASSETS = OUT / 'assets'


class MonochromeMovie(Exception):
    """A mostly grayscale video is unsuitable for the color-barcode game."""

def run(args):
    return subprocess.run(args,check=True,capture_output=True)

def stable_rng(value):
    digest=hashlib.sha256(value.encode()).digest()
    return random.Random(int.from_bytes(digest[:8],'big'))

def tags(movie):
    return set(movie.get('genres') or [g.strip().lower() for g in movie.get('genre','').replace('/ ', ',').split(',') if g.strip()])

def choose_movie(catalog,completed,date):
    done={item['id'] for item in completed}
    pending=[item for item in catalog if item['id'] not in done and (item.get('video_url') or item.get('stills_manifest')) and item.get('license')
             and str(item.get('color_mode','color')).lower() not in ('black-and-white','monochrome','grayscale')]
    if not pending:return None
    recent=completed[-3:]
    rng=stable_rng('movie:'+date)
    def score(movie):
        overlap=sum(len(tags(movie)&tags(old)) for old in recent)
        return movie.get('popularity',50)-overlap*12+rng.uniform(-5,5)
    return max(pending,key=score)

def choose_choices(movie,pool):
    rng=stable_rng('choices:'+movie['id'])
    target_tags=tags(movie)
    candidates=[entry for entry in pool if entry['title'].casefold()!=movie['title'].casefold()]
    # Prefer a shared genre and a nearby era; seeded noise keeps it from always
    # producing the same obvious three films across neighboring puzzles.
    ranked=sorted(candidates,key=lambda entry:len(tags(entry)&target_tags)*30+max(0,18-abs(entry['year']-movie['year'])/3)+rng.uniform(0,16),reverse=True)
    if len(ranked)<3:raise ValueError('Need at least three distinct movie titles in choice_pool.json')
    selected=ranked[:3]+[{'title':movie['title'],'year':movie['year']}]
    rng.shuffle(selected)
    return selected,next(i for i,x in enumerate(selected) if x['title']==movie['title'])

def download(url,destination):
    request=urllib.request.Request(url,headers={'User-Agent':'CHROMA-curator/1.0 (licensed film puzzle processor)'})
    with urllib.request.urlopen(request,timeout=120) as response,destination.open('wb') as stream:
        total=0
        while True:
            chunk=response.read(1024*1024)
            if not chunk:break
            total+=len(chunk)
            if total>2_000_000_000:raise ValueError('Source exceeds 2 GB safety limit')
            stream.write(chunk)

def detect_content_window(video,duration):
    """Trim contiguous near-black leaders/tails, but preserve dark scenes inside.

    A tiny 1 FPS grayscale pass is much cheaper than decoding full-resolution
    frames.  The 20% per-edge cap avoids swallowing an unusually dark film.
    """
    sample=run(['ffmpeg','-hide_banner','-loglevel','error','-i',str(video),
                '-vf','fps=1,scale=16:9,format=gray','-f','rawvideo','-']).stdout
    stride=16*9
    frames=[sample[i:i+stride] for i in range(0,len(sample)-stride+1,stride)]
    if len(frames)<10:return 0.0,duration
    def dark(frame):
        return sum(frame)/len(frame)<38 and sum(pixel<=32 for pixel in frame)/len(frame)>.86
    cap=min(int(len(frames)*.20),180)
    leading=0
    while leading<cap and dark(frames[leading]):leading+=1
    trailing=0
    while trailing<cap and dark(frames[-1-trailing]):trailing+=1
    # Ignore isolated dark frames; don't over-trim short cinematic fades.
    start=float(leading) if leading>=2 else 0.0
    end=min(duration,float(len(frames)-trailing)) if trailing>=2 else duration
    if end-start<max(8,duration*.5):return 0.0,duration
    return start,end


def is_monochrome(video):
    """Detect predominantly grayscale footage using sampled chroma, not title/year.

    Faintly tinted black-and-white footage also fails the colorfulness test.
    We sample frames from across the film so monochrome opening logos alone
    won't disqualify a genuinely colorful movie.
    """
    raw=run(['ffmpeg','-hide_banner','-loglevel','error','-i',str(video),
             '-vf','fps=1/15,scale=24:14,format=rgb24','-f','rawvideo','-']).stdout
    stride=24*14*3
    frames=[raw[offset:offset+stride] for offset in range(0,len(raw)-stride+1,stride)]
    if len(frames)<3:return False
    colorful=0
    for frame in frames:
        saturated=0
        for j in range(0,stride,3):
            rgb=frame[j:j+3]
            if max(rgb)-min(rgb)>18:saturated+=1
        if saturated/(24*14)>.07:colorful+=1
    fraction=colorful/len(frames)
    print(f'Colorfulness check: {colorful}/{len(frames)} sample frames show meaningful color')
    return fraction<.15

def generate_barcode(video,slug,duration,start=0):
    frame_count=560
    raw=run(['ffmpeg','-hide_banner','-loglevel','error','-ss',str(start),'-i',str(video),'-t',str(duration),'-vf',f'fps={frame_count/duration:.8f},scale=24:14,format=rgb24','-f','rawvideo','-']).stdout
    stride=24*14*3
    colors=[]
    for offset in range(0,len(raw)-stride+1,stride):
        sample=raw[offset:offset+stride]
        colors.append(tuple(sum(sample[channel::3])//(24*14) for channel in range(3)))
    if len(colors)<30:raise ValueError('Video yielded too few frames')
    image=Image.new('RGB',(len(colors),240));draw=ImageDraw.Draw(image)
    for x,color in enumerate(colors):draw.line((x,0,x,239),fill=color)
    image.save(ASSETS/f'{slug}-barcode.png',optimize=True)
    return len(colors)

def choose_frames(video,movie,duration,temp,start=0):
    slug=movie['id']
    interval=max(3,duration/45)
    candidate_dir=temp/'candidates';candidate_dir.mkdir()
    run(['ffmpeg','-hide_banner','-loglevel','error','-ss',str(start),'-i',str(video),'-t',str(duration),'-vf',f'fps=1/{interval:.6f},scale=720:-2','-q:v','3','-y',str(candidate_dir/'%04d.jpg')])
    paths=sorted(candidate_dir.glob('*.jpg'))
    if len(paths)<10:raise ValueError('Not enough candidate frames')
    candidates=[]
    for index,path in enumerate(paths):
        if index<max(1,int(.04*len(paths))) or index>int(.96*len(paths)):
            continue
        candidates.append(features(path,index))
    if len(candidates)<5:raise ValueError('Not enough useful frame candidates')
    pool=shortlist(candidates,15)
    reviews=vision_review(pool,movie)
    chosen=select_five(pool,reviews)
    selected={item['index'] for item in chosen}
    report=[]
    for i,item in enumerate(pool,1):
        filename=f'{slug}-candidate-{i:02d}.jpg'
        shutil.copyfile(item['path'],ASSETS/filename)
        review=reviews.get(i,{})
        report.append({'image':'assets/'+filename,'time_seconds':round(start+item['index']*interval,1),
                       'quality':item['quality'],'sharpness':item['sharpness'],
                       'plot_relevance':review.get('relevance'),
                       'spoiler_risk':review.get('spoiler'),
                       'reason':review.get('reason') or 'Selected by visual quality, distinctiveness and scene spacing.',
                       'selected':item['index'] in selected})
    for i,item in enumerate(chosen,1):
        shutil.copyfile(item['path'],ASSETS/f'{slug}-{i}.jpg')
    review_dir=OUT/'control-room'/'reviews';review_dir.mkdir(parents=True,exist_ok=True)
    (review_dir/f'{slug}.json').write_text(json.dumps({
        'movie_id':slug,'selection_mode':'vision+plot' if reviews else 'visual-only',
        'plot_available':bool(movie.get('plot_summary') or movie.get('synopsis')),
        'candidates':report},ensure_ascii=False,indent=2)+'\n')
    return [item['path'].name for item in chosen]

def generate(movie):
    ASSETS.mkdir(parents=True,exist_ok=True)
    # A poster is the only public answer-reveal image. Keep it in the private
    # source checkout until the scheduled day; never publish upcoming posters.
    poster=(ROOT / 'posters' / f"{movie['id']}.jpg").resolve()
    if not poster.is_relative_to(ROOT / 'posters') or not poster.is_file():
        raise ValueError(f"Missing authorized poster: posters/{movie['id']}.jpg")
    if movie.get('stills_manifest'):
        manifest=(ROOT / movie['stills_manifest']).resolve()
        if not manifest.is_relative_to(ROOT / 'stills'):
            raise ValueError('Stills manifest must be stored under stills/')
        report=generate_stills_barcode(manifest,ASSETS/f"{movie['id']}-barcode.png",
                                      OUT/'control-room'/'reviews'/f"{movie['id']}.json")
        shutil.copyfile(poster,ASSETS/f"{movie['id']}-poster.jpg")
        return report['stripe_count'],[]
    with tempfile.TemporaryDirectory(prefix='chroma-curator-') as root:
        temp=Path(root);video=temp/'source.video'
        download(movie['video_url'],video)
        probe=json.loads(run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(video)]).stdout)
        duration=float(probe['format']['duration'])
        if duration<=0:raise ValueError('Invalid video duration')
        if is_monochrome(video):raise MonochromeMovie(f'{movie["title"]} is predominantly monochrome')
        start,end=detect_content_window(video,duration)
        print(f'Content window: {start:.1f}s–{end:.1f}s of {duration:.1f}s (excluded {start:.1f}s opening, {duration-end:.1f}s ending)')
        usable=end-start
        count=generate_barcode(video,movie['id'],usable,start)
        shutil.copyfile(poster,ASSETS/f"{movie['id']}-poster.jpg")
        return count,[]

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--dry-run',action='store_true',help='Choose the next movie and answers without downloading')
    parser.add_argument('--regenerate',metavar='MOVIE_ID',help='Replace an existing puzzle barcode and five frames without changing the queue or answer')
    parser.add_argument('--date',default=datetime.now(timezone.utc).date().isoformat())
    args=parser.parse_args()
    catalog=json.loads((ROOT/'catalog.json').read_text())
    pool=json.loads((ROOT/'choice_pool.json').read_text())
    data=json.loads((OUT/'puzzles.json').read_text())
    if args.regenerate:
        existing=next((p for p in data['puzzles'] if p['id']==args.regenerate),None)
        source=next((m for m in catalog if m['id']==args.regenerate),None)
        if existing is None:raise ValueError(f'Puzzle {args.regenerate!r} is not scheduled; cannot regenerate')
        if source is None or not (source.get('video_url') or source.get('stills_manifest')) or not source.get('license'):
            raise ValueError(f'No approved source for {args.regenerate!r}')
        print(f'Regenerating assets for {existing["title"]}; keeping its scheduled date, choices, and answer unchanged')
        if args.dry_run:return
        count,frames=generate(source)
        print(f'Regenerated {count} barcode stripes and one poster reveal')
        return
    while True:
        movie=choose_movie(catalog,data['puzzles'],args.date)
        if not movie:
            print('No eligible color movies remain. Add an approved video or chronological-stills manifest to catalog.json.')
            return
        choices,answer=choose_choices(movie,pool)
        print(f"Selected: {movie['title']} ({movie['year']}); answer slot {answer+1}")
        if args.dry_run:
            print('Choices:',', '.join(item['title'] for item in choices));return
        try:
            count,frames=generate(movie)
            break
        except MonochromeMovie as error:
            print(f'Skipping unsuitable film: {error}')
            movie['color_mode']='monochrome'
            (ROOT/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n')
    # Local still paths and source video URLs belong in the private MKIA repo.
    # Only player-facing metadata may enter the public daily JSON.
    record={key:value for key,value in movie.items()
            if key not in ('video_url','stills_manifest','popularity','genres')}
    record['barcode_method']='B' if movie.get('stills_manifest') else 'A'
    record['choices']=choices;record['answer']=answer
    data['puzzles'].append(record)
    (OUT/'puzzles.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(f'Prepared puzzle #{len(data["puzzles"])}: {count} barcode stripes; poster reveal')

if __name__=='__main__':main()
