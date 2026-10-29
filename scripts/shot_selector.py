"""Rank MKIA reveal frames for composition, diversity, and optional plot relevance.

The optional vision pass uses OPENAI_API_KEY and a human-supplied plot_summary.
Without either one, selection stays deterministic and fully offline.
"""
import base64
import io
import json
import math
import os
import urllib.request
from pathlib import Path

from PIL import Image, ImageChops, ImageFilter, ImageStat


def features(path, index):
    with Image.open(path) as source:
        image=source.convert('RGB').resize((160,90))
    gray=image.convert('L')
    stats=ImageStat.Stat(gray)
    edges=gray.filter(ImageFilter.FIND_EDGES)
    sharpness=ImageStat.Stat(edges).stddev[0]
    channel_means=ImageStat.Stat(image).mean
    saturation=max(channel_means)-min(channel_means)
    exposure=max(0,1-abs(stats.mean[0]-122)/122)
    # Avoid empty fades, but don't require every good scene to be brightly lit.
    quality=(gray.entropy()*5+stats.stddev[0]*.35+min(sharpness,45)*.48
             +saturation*.10+exposure*10)
    if stats.mean[0]<22 or stats.mean[0]>239:quality-=30
    return {'index':index,'path':path,'preview':image.resize((48,27)),
            'quality':round(quality,2),'sharpness':round(sharpness,2)}


def difference(a,b):
    return sum(ImageStat.Stat(ImageChops.difference(a['preview'],b['preview'])).mean)/3


def shortlist(items,count=15):
    """Build a diverse review pool rather than keeping 15 adjacent good frames."""
    chosen=[]
    for _ in range(min(count,len(items))):
        def score(item):
            if item in chosen:return -1e9
            visual=min((difference(item,other) for other in chosen),default=45)
            spacing=min((abs(item['index']-other['index']) for other in chosen),default=len(items))
            return item['quality']*.8+visual*1.7+min(spacing,6)*2
        chosen.append(max(items,key=score))
    return sorted(chosen,key=lambda x:x['index'])


def vision_review(items,movie):
    """Optional single-request image review; never fail daily publication on API errors."""
    key=os.environ.get('OPENAI_API_KEY')
    plot=movie.get('plot_summary') or movie.get('synopsis')
    if not key or not plot:return {}
    parts=[{'type':'input_text','text':(
        'You are curating a fair daily movie guessing puzzle. Evaluate these numbered '
        'film frames from the same movie. Movie plot synopsis: '+str(plot)[:1300]+'. '
        'Return ONLY a JSON object {"frames":[{"id":1,"relevance":0-10,'
        '"spoiler":0-10,"reason":"short explanation"},...]}. '
        'Relevance means how strongly an image illustrates the plot; spoiler means '
        'how instantly recognizable or revealing it may be. Do not assert scene '
        'identities you cannot verify. Give one result per image.') }]
    for i,item in enumerate(items,1):
        with Image.open(item['path']) as image:
            image.thumbnail((320,180))
            buffer=io.BytesIO();image.convert('RGB').save(buffer,format='JPEG',quality=65)
        encoded=base64.b64encode(buffer.getvalue()).decode('ascii')
        parts.append({'type':'input_text','text':f'Frame {i}'})
        parts.append({'type':'input_image','image_url':'data:image/jpeg;base64,'+encoded,'detail':'low'})
    payload={'model':os.environ.get('MKIA_VISION_MODEL','gpt-4.1-mini'),
             'input':[{'role':'user','content':parts}], 'max_output_tokens':1700}
    request=urllib.request.Request('https://api.openai.com/v1/responses',
        data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,
        'Content-Type':'application/json'},method='POST')
    try:
        with urllib.request.urlopen(request,timeout=100) as response:
            data=json.load(response)
        result=''.join(part.get('text','') for item in data.get('output',[])
                       for part in item.get('content',[]) if part.get('type')=='output_text')
        result=result.strip().removeprefix('```json').removeprefix('```').removesuffix('```').strip()
        rows=json.loads(result).get('frames',[])
        return {int(row['id']):{'relevance':max(0,min(10,float(row['relevance']))),
                 'spoiler':max(0,min(10,float(row['spoiler']))),
                 'reason':str(row.get('reason',''))[:180]}
                for row in rows if isinstance(row,dict)}
    except (OSError,ValueError,KeyError,TypeError) as error:
        print('Optional vision review unavailable; using offline ranking:',error)
        return {}


def select_five(items,reviews):
    selected=[]
    for step in range(min(5,len(items))):
        target=(step+.5)/5*(len(items)-1)
        def score(item):
            if item in selected:return -1e9
            position=items.index(item)+1
            review=reviews.get(position,{})
            novelty=min((difference(item,prior) for prior in selected),default=40)
            spread=abs(items.index(item)-target)*1.3
            # Plot relevance matters, but an instantly obvious shot is a poor clue.
            return (item['quality']*.7+novelty*1.8-spread
                    +review.get('relevance',0)*2.5-review.get('spoiler',0)*2.2)
        selected.append(max(items,key=score))
    return sorted(selected,key=lambda x:x['index'])
