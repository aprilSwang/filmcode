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

from PIL import Image, ImageChops, ImageDraw, ImageStat

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'dist'
ASSETS = OUT / 'assets'

def run(args):
    return subprocess.run(args,check=True,capture_output=True)

def stable_rng(value):
    digest=hashlib.sha256(value.encode()).digest()
    return random.Random(int.from_bytes(digest[:8],'big'))

def tags(movie):
    return set(movie.get('genres') or [g.strip().lower() for g in movie.get('genre','').replace('/ ', ',').split(',') if g.strip()])

def choose_movie(catalog,completed,date):
    done={item['id'] for item in completed}
    pending=[item for item in catalog if item['id'] not in done and item.get('video_url') and item.get('license')]
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

def frame_score(image):
    image=image.convert('RGB').resize((120,68))
    gray=image.convert('L')
    mean=ImageStat.Stat(gray).mean[0]
    std=ImageStat.Stat(gray).stddev[0]
    # Dark/white cuts and low-information fades should lose to actual scenes.
    brightness=max(0,1-abs(mean-118)/118)
    return gray.entropy()*7+std*.25+brightness*12

def choose_frames(video,slug,duration,temp,start=0):
    interval=max(3,duration/45)
    candidate_dir=temp/'candidates';candidate_dir.mkdir()
    run(['ffmpeg','-hide_banner','-loglevel','error','-ss',str(start),'-i',str(video),'-t',str(duration),'-vf',f'fps=1/{interval:.6f},scale=720:-2','-q:v','3','-y',str(candidate_dir/'%04d.jpg')])
    paths=sorted(candidate_dir.glob('*.jpg'))
    if len(paths)<10:raise ValueError('Not enough candidate frames')
    # Rank visual *distinctiveness* alongside image quality: otherwise a long
    # static scene can occupy all five reveal slots despite good entropy.
    candidates=[]
    for index,path in enumerate(paths):
        if index<max(1,int(.04*len(paths))) or index>int(.96*len(paths)):
            continue
        with Image.open(path) as frame:
            feature=frame.convert('RGB').resize((48,27))
            quality=frame_score(frame)
        candidates.append((index,path,feature,quality))
    if len(candidates)<5:raise ValueError('Not enough useful frame candidates')
    chosen=[]
    def difference(a,b):
        return sum(ImageStat.Stat(ImageChops.difference(a,b)).mean)/3
    for step in range(5):
        target=(step+.5)/5*len(paths)
        def score(item):
            index,_,image,quality=item
            if any(abs(index-prev[0])<max(2,len(paths)*.06) for prev in chosen):
                return -1e5
            novelty=min((difference(image,prev[2]) for prev in chosen),default=42)
            spread_penalty=abs(index-target)/len(paths)*18
            return novelty*2.2+quality*.45-spread_penalty
        candidate=max((item for item in candidates if item not in chosen),key=score)
        chosen.append(candidate)
    chosen.sort(key=lambda item:item[0])
    for i,(_,path,_,_) in enumerate(chosen,1):
        shutil.copyfile(path,ASSETS/f'{slug}-{i}.jpg')
    return [item[1].name for item in chosen]

def generate(movie):
    ASSETS.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='chroma-curator-') as root:
        temp=Path(root);video=temp/'source.video'
        download(movie['video_url'],video)
        probe=json.loads(run(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(video)]).stdout)
        duration=float(probe['format']['duration'])
        if duration<=0:raise ValueError('Invalid video duration')
        start,end=detect_content_window(video,duration)
        print(f'Content window: {start:.1f}s–{end:.1f}s of {duration:.1f}s (excluded {start:.1f}s opening, {duration-end:.1f}s ending)')
        usable=end-start
        count=generate_barcode(video,movie['id'],usable,start)
        frame_names=choose_frames(video,movie['id'],usable,temp,start)
        return count,frame_names

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--dry-run',action='store_true',help='Choose the next movie and answers without downloading')
    parser.add_argument('--date',default=datetime.now(timezone.utc).date().isoformat())
    args=parser.parse_args()
    catalog=json.loads((ROOT/'catalog.json').read_text())
    pool=json.loads((ROOT/'choice_pool.json').read_text())
    data=json.loads((OUT/'puzzles.json').read_text())
    movie=choose_movie(catalog,data['puzzles'],args.date)
    if not movie:
        print('No eligible movies remain. Add a rights-cleared video source to catalog.json.')
        return
    choices,answer=choose_choices(movie,pool)
    print(f"Selected: {movie['title']} ({movie['year']}); answer slot {answer+1}")
    if args.dry_run:
        print('Choices:',', '.join(item['title'] for item in choices));return
    count,frames=generate(movie)
    record={key:value for key,value in movie.items() if key not in ('video_url','popularity','genres')}
    record['choices']=choices;record['answer']=answer
    data['puzzles'].append(record)
    (OUT/'puzzles.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(f'Published puzzle #{len(data["puzzles"])}: {count} barcode stripes; selected frames {frames}')

if __name__=='__main__':main()
