"""MKIA automatic discovery of clearly licensed Blender open movies.

Queries the official Wikimedia Commons API. Unknown titles or ambiguous
licenses are skipped and logged, never silently treated as usable footage.
"""
import argparse
import html
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
API='https://commons.wikimedia.org/w/api.php'

# Metadata mapping resolves film identities from the public media catalog;
# video locations and licensing are discovered afresh from Wikimedia.
KNOWN={
 'caminandes - gran dillama':('Caminandes: Gran Dillama',2013,['animation','comedy','adventure']),
 'caminandes- llama drama':('Caminandes: Llama Drama',2013,['animation','comedy','adventure']),
 'charge -':('Charge',2022,['animation','science fiction','action']),
 'cosmos laundromat':('Cosmos Laundromat',2015,['animation','fantasy','drama']),
 'elephants dream':('Elephants Dream',2006,['animation','science fiction']),
 'glass half':('Glass Half',2015,['animation','comedy']),
 'hero -':('Hero',2018,['animation','fantasy','adventure']),
 'spring -':('Spring',2019,['animation','fantasy','adventure']),
 'sprite fright':('Sprite Fright',2021,['animation','horror','comedy']),
 'tears of steel':('Tears of Steel',2012,['science fiction','action','drama']),
 'the daily dweebs':('The Daily Dweebs',2017,['animation','comedy']),
 'wing it':('WING IT!',2023,['animation','comedy','adventure']),
 'coffee run':('Coffee Run',2020,['animation','drama','romance']),
 'big buck bunny':('Big Buck Bunny',2008,['animation','comedy'])
}

def query(**params):
    url=API+'?'+urllib.parse.urlencode({'action':'query','format':'json',**params})
    req=urllib.request.Request(url,headers={'User-Agent':'Filmcode-MKIA/1.0 (film discovery)'})
    with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)

def discover(limit):
    catalog_path=ROOT/'catalog.json';pool_path=ROOT/'choice_pool.json'
    catalog=json.loads(catalog_path.read_text());pool=json.loads(pool_path.read_text())
    existing={x['id'] for x in catalog};added=[];review=[];seen=set()
    members=query(list='categorymembers',cmtitle='Category:Blender movies',cmtype='file',cmlimit='100')['query']['categorymembers']
    for member in members:
        title=member['title'];filename=title.lower().replace('_',' ')
        if not filename.endswith(('.webm','.ogv')):continue
        match=next((v for k,v in KNOWN.items() if k in filename),None)
        if not match:
            review.append({'file':title,'reason':'Film identity/year unknown'})
            continue
        name,year,genres=match;slug=re.sub(r'[^a-z0-9]+','-',name.lower()).strip('-')
        if slug in existing or slug in seen:continue
        seen.add(slug)
        if len(added)>=limit:continue
        pages=query(prop='imageinfo',titles=title,iiprop='url|extmetadata')['query']['pages']
        info=next(iter(pages.values())).get('imageinfo',[{}])[0]
        meta=info.get('extmetadata',{})
        uri=meta.get('LicenseUrl',{}).get('value','')
        # Exclude ShareAlike variants pending a license-specific distribution review.
        if not (uri.startswith('https://creativecommons.org/licenses/by/') or 'publicdomain' in uri) or '/by-sa/' in uri:
            review.append({'file':title,'reason':'License not verified as CC BY/public domain'})
            continue
        video=info.get('url')
        if not video:continue
        license_name=re.sub('<[^>]*>','',html.unescape(meta.get('LicenseShortName',{}).get('value','CC BY')))
        item={'id':slug,'title':name,'year':year,'genre':' / '.join(genres[:2]),'genres':genres,'popularity':50,
              'license':license_name+' · Wikimedia Commons','source':info.get('descriptionurl',video),'video_url':video}
        added.append(item)
    return added,review,catalog,pool

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--dry-run',action='store_true');parser.add_argument('--max-new',type=int,default=4)
    args=parser.parse_args()
    added,review,catalog,pool=discover(args.max_new)
    print('MKIA found:',', '.join(x['title'] for x in added) or 'no new eligible movies')
    if args.dry_run:return
    catalog.extend(added);existing={x['title'].casefold() for x in pool}
    for movie in added:
        if movie['title'].casefold() not in existing:
            pool.append({'title':movie['title'],'year':movie['year'],'genres':movie['genres']})
    (ROOT/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n')
    (ROOT/'choice_pool.json').write_text(json.dumps(pool,ensure_ascii=False,indent=2)+'\n')
    (ROOT/'discovery_review.json').write_text(json.dumps(review,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
