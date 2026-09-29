"""Provider APIs. Credentials stay in the local backend; source records persist."""
import json,urllib.request,urllib.parse,urllib.error,hashlib,time
from pathlib import Path
import core,image_sources,workflow

def api(url,headers=None,payload=None):
    try:
        req=urllib.request.Request(url,json.dumps(payload).encode() if payload is not None else None,headers or {})
        with urllib.request.urlopen(req,timeout=40) as r:return json.load(r)
    except urllib.error.HTTPError as e:
        # Never include request URLs: Pixabay carries the user's key in the query.
        text=e.read(4096).decode('utf-8','replace')
        try:text=json.loads(text).get('error',{}).get('message','Acesso recusado pelo serviço.')
        except (ValueError,AttributeError):text='Acesso recusado pelo serviço.'
        raise ValueError(f'Serviço HTTP {e.code}: {text[:300]}') from None
    except urllib.error.URLError:raise ValueError('Não foi possível alcançar o serviço. Confira a conexão.') from None

def search(provider,query,kind,key,cache_dir):
    if not key:raise ValueError('Salve sua chave '+provider+' nas conexões.')
    cache=Path(cache_dir)/(hashlib.sha256((provider+query+kind).encode()).hexdigest()+'.json')
    if cache.exists() and time.time()-cache.stat().st_mtime<86400:return core.read_json(cache)
    q=urllib.parse.urlencode({'query':query,'per_page':12,'orientation':'landscape'})
    records=[]
    if provider=='pexels':
        data=api('https://api.pexels.com/v1/'+('videos/search?' if kind=='video' else 'search?')+q,{'Authorization':key})
        for item in data.get('videos' if kind=='video' else 'photos',[]):
            if kind=='video':
                files=[f for f in item.get('video_files',[]) if f.get('file_type')=='video/mp4' and f.get('height',0)>=720 and f.get('width',0)>=1280]
                if not files:continue
                f=min(files,key=lambda x:abs(x['height']-1080));url=f['link'];author=item.get('user',{}).get('name','');width,height=f['width'],f['height']
            else:url=item['src']['original'];author=item.get('photographer','');width,height=item['width'],item['height']
            records.append({'url':url,'page':item['url'],'author':author,'id':str(item['id']),'provider':provider,'kind':kind,'query':query,'width':width,'height':height,'license':'Pexels License — https://www.pexels.com/license/'})
    elif provider=='pixabay':
        q=urllib.parse.urlencode({'key':key,'q':query,'per_page':12,'safesearch':'true','min_width':1280,'min_height':720,'image_type':'photo'})
        data=api('https://pixabay.com/api/'+('videos/' if kind=='video' else '')+'?'+q)
        for item in data.get('hits',[]):
            if kind=='video':
                files=[v for v in item.get('videos',{}).values() if v.get('url') and v.get('width',0)>=1280 and v.get('height',0)>=720]
                if not files:continue
                f=min(files,key=lambda v:abs(v['height']-1080));url=f['url'];width,height=f['width'],f['height']
            else:url=item.get('largeImageURL');width,height=item.get('imageWidth',0),item.get('imageHeight',0)
            if url:records.append({'url':url,'page':item['pageURL'],'author':item.get('user',''),'id':str(item['id']),'provider':provider,'kind':kind,'query':query,'width':width,'height':height,'license':'Pixabay Content License — https://pixabay.com/service/license-summary/'})
    elif provider=='serper' and kind=='image':
        data=api('https://google.serper.dev/images',{'X-API-KEY':key,'Content-Type':'application/json'},{'q':query,'num':12})
        for item in data.get('images',[]):
            if item.get('imageUrl'):records.append({'url':item['imageUrl'],'page':item.get('link',''),'author':item.get('source',''),'id':hashlib.sha256(item['imageUrl'].encode()).hexdigest()[:16],'provider':provider,'kind':'image','query':query,'license':'Verificar direitos na fonte original'})
    else:raise ValueError('Fonte ou tipo não suportado.')
    core.write_json(cache,records);return records

def download_video(rec,folder,job):
    from image_sources import public_url,Redirect
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    path=folder/(core.norm(rec['query']).replace(' ','-')[:50]+'_'+rec['provider']+'_'+rec['id']+'.mp4')
    if path.exists():return path
    tmp=path.with_suffix('.partial');opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),Redirect());total=0
    try:
        with opener.open(urllib.request.Request(public_url(rec['url']),headers={'User-Agent':'MontaVideo/0.7'}),timeout=40) as response,tmp.open('wb') as out:
            while True:
                job.check();block=response.read(1024*1024)
                if not block:break
                total+=len(block)
                if total>400*1024*1024:raise ValueError('Vídeo acima de 400 MB; ignorado.')
                out.write(block)
        if total<100:raise ValueError('Vídeo vazio.')
        tmp.replace(path);return path
    finally:tmp.unlink(missing_ok=True)

def gather(cfg,cat,queries,kind,providers,keys,job):
    queries=list(dict.fromkeys(str(q).strip() for q in queries if str(q).strip()))[:8]
    if not queries:raise ValueError('Analise o roteiro antes de buscar material.')
    limit=int(cfg.get('image_count',20) if kind=='image' else cfg.get('stock_count',12));limit=max(1,min(40,limit));warnings=[];added=0;seen=set()
    folder=Path(cfg['project_root'])/('05_Imagens' if kind=='image' else '08_Broll_Baixado')
    per_query=max(1,(limit+len(queries)-1)//len(queries))
    for query in queries:
        per_added=0
        for provider in providers:
            if added>=limit or per_added>=per_query:break
            job.check();job.log('Buscando '+provider+': '+query)
            try:
                for rec in search(provider,query,kind,keys.get(provider+'_key',''),Path(cfg['output'])/'cache'/'providers'):
                    job.check()
                    ident=rec['provider']+rec['id']
                    if ident in seen:continue
                    seen.add(ident)
                    try:
                        if kind=='image':
                            raw,url=image_sources.fetch(rec['url']);stored=image_sources.store_image(folder,raw,query,url);stored.update(rec);core.write_json(Path(stored['path']+'.fonte.json'),stored)
                            before=len(cat['items']);cat=image_sources.import_records(cfg,cat,[stored],job)
                            if len(cat['items'])==before:continue
                        else:
                            path=download_video(rec,folder,job);before=len(cat['items']);cat=workflow.add_asset(cfg,cat,path,job,'stock',query)
                            if len(cat['items'])==before:continue
                            item=cat['items'][-1];item.update(precut=True,source=rec,usage='generico',context_allowed=True,reviewed=False)
                            core.write_json(Path(str(path)+'.fonte.json'),rec)
                        added+=1;per_added+=1
                        if added>=limit or per_added>=per_query:break
                    except Exception as e:job.check();warnings.append(str(e)[:200])
            except Exception as e:job.check();warnings.append(provider+': '+str(e)[:250])
    core.write_json(Path(cfg['output'])/'catalogo.json',cat)
    return cat,{'downloaded':added,'folder':str(folder),'warnings':list(dict.fromkeys(warnings))[:8]}
