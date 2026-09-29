"""Imagens online selecionadas pelo usuário e cartões locais para lacunas de cobertura."""
from pathlib import Path
import hashlib,html,io,json,re,urllib.request,urllib.parse
import core
UA='MontaVideo/0.2 (local desktop video editor; user initiated image search)'

def plain(s):return html.unescape(re.sub('<[^>]+>','',str(s)))
def request_json(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA})
    with urllib.request.urlopen(req,timeout=25) as response:return json.load(response)
def search_images(query):
    params={'action':'query','format':'json','generator':'search','gsrsearch':query[:240],
            'gsrnamespace':6,'gsrlimit':40,'prop':'imageinfo','iiprop':'url|size|mime|sha1|extmetadata','iiurlwidth':640}
    data=request_json('https://commons.wikimedia.org/w/api.php?'+urllib.parse.urlencode(params))
    if 'error' in data:raise ValueError('A busca de imagens retornou erro. Tente termos mais curtos.')
    out=[];seen=set()
    for p in sorted(data.get('query',{}).get('pages',{}).values(),key=lambda x:x.get('index',0)):
        info=(p.get('imageinfo') or [{}])[0]
        if info.get('mime') not in ('image/jpeg','image/png','image/webp'):continue
        if info.get('width',0)<1280 or info.get('height',0)<720 or info.get('size',0)>25*1024*1024:continue
        sha=info.get('sha1')
        if sha and sha in seen:continue
        seen.add(sha);m=info.get('extmetadata',{})
        out.append({'id':str(p['pageid']),'title':plain(p['title']).removeprefix('File:'),'url':info['url'],
                    'preview':info.get('thumburl',info['url']),'page':info.get('descriptionurl',''),
                    'width':info['width'],'height':info['height'],'mime':info['mime'],
                    'artist':plain(m.get('Artist',{}).get('value','')),'license':plain(m.get('LicenseShortName',{}).get('value','Ver fonte')),
                    'license_url':m.get('LicenseUrl',{}).get('value',''),'sha1':sha})
    return out

def dhash(image):
    g=image.convert('L').resize((9,8));pixels=list(g.getdata());n=0
    for y in range(8):
        for x in range(8):n=(n<<1)|int(pixels[y*9+x]>pixels[y*9+x+1])
    return n

def download_image(cfg,entry,catalog,job):
    from PIL import Image
    u=urllib.parse.urlsplit(entry['url'])
    if u.scheme!='https' or u.hostname!='upload.wikimedia.org':raise ValueError('Origem de imagem não permitida.')
    req=urllib.request.Request(entry['url'],headers={'User-Agent':UA})
    job.log('Baixando imagem original: '+entry['title']);parts=[];total=0
    with urllib.request.urlopen(req,timeout=25) as r:
        if urllib.parse.urlsplit(r.url).hostname!='upload.wikimedia.org':raise ValueError('Redirecionamento inesperado.')
        while True:
            job.check();chunk=r.read(65536)
            if not chunk:break
            total+=len(chunk)
            if total>25*1024*1024:raise ValueError('Imagem ultrapassa 25 MB.')
            parts.append(chunk)
    raw=b''.join(parts);digest=hashlib.sha256(raw).hexdigest()
    with Image.open(io.BytesIO(raw)) as im:
        if im.width<1280 or im.height<720:raise ValueError('Imagem abaixo da resolução mínima.')
        im.load();visual_hash=dhash(im);width,height=im.size
    for item in catalog['items']:
        if item.get('download_sha256')==digest or (item.get('dhash') is not None and (int(item['dhash'])^visual_hash).bit_count()<=3):
            return item['path'],catalog
    folder=Path(cfg['output'])/'imagens';folder.mkdir(parents=True,exist_ok=True)
    ext={'image/jpeg':'.jpg','image/png':'.png','image/webp':'.webp'}[entry['mime']]
    path=folder/(digest[:20]+ext);path.write_bytes(raw)
    item={'id':core.fingerprint(path),'path':str(path.resolve()),'kind':'image','duration':0,'width':width,'height':height,
          'tags':[entry['title']],'aliases':[],'entity':'','usage':'especifico','origin':'online','role':'media','selected':True,
          'description':entry['title'],'download_sha256':digest,'dhash':str(visual_hash),'source':entry}
    catalog['items'].append(item);core.write_json(Path(cfg['output'])/'catalogo.json',catalog)
    sources=[i['source'] for i in catalog['items'] if i.get('source')]
    core.write_json(Path(cfg['output'])/'fontes_imagens.json',sources)
    (Path(cfg['output'])/'CREDITOS_IMAGENS.txt').write_text('\n\n'.join(f"{s['title']}\nAutor: {s['artist']}\nLicença: {s['license']} {s['license_url']}\nFonte: {s['page']}" for s in sources),encoding='utf-8')
    return str(path.resolve()),catalog

def make_cards(cfg,plan,catalog,job):
    from PIL import Image,ImageDraw,ImageFont,ImageOps
    backgrounds={i['path']:i for i in catalog['items'] if i.get('role')=='background' and i['kind']=='image'}
    bg=cfg.get('background','')
    if bg and bg not in backgrounds:raise ValueError('Selecione um fundo PNG/JPG catalogado.')
    fonts=[Path('C:/Windows/Fonts/arial.ttf'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')]
    fontfile=next((p for p in fonts if p.exists()),None)
    if not fontfile:raise ValueError('Fonte Arial não encontrada para os cartões.')
    folder=Path(cfg['output'])/'cartoes';folder.mkdir(parents=True,exist_ok=True)
    made=0
    for n,row in enumerate(plan['rows']):
        job.check()
        if row.get('path'):continue
        text=row.get('text','').strip()
        if not text:continue
        image=Image.new('RGB',(1920,1080),'#111b2a')
        if bg:
            with Image.open(bg) as src:image=ImageOps.fit(src.convert('RGB'),(1920,1080))
        overlay=Image.new('RGBA',image.size,(0,0,0,0));draw=ImageDraw.Draw(overlay)
        draw.rounded_rectangle((110,120,1810,960),radius=35,fill=(8,17,29,230))
        lines=[]
        for size in (66,60,54,48,42,36):
            font=ImageFont.truetype(str(fontfile),size);lines=[];line=''
            for word in text.split():
                candidate=(line+' '+word).strip()
                if draw.textlength(candidate,font=font)>1510 and line:lines.append(line);line=word
                else:line=candidate
            if line:lines.append(line)
            if len(lines)*(size+18)<=680:break
        if len(lines)*(size+18)>680:raise ValueError('Texto longo demais para cartão; reduza o trecho.')
        y=(1080-len(lines)*(size+18))/2
        for line in lines:
            x=(1920-draw.textlength(line,font=font))/2;draw.text((x,y),line,font=font,fill='#f1f6ff');y+=size+18
        result=Image.alpha_composite(image.convert('RGBA'),overlay).convert('RGB')
        card_id=hashlib.sha256((text+bg+(core.fingerprint(bg) if bg else '')).encode()).hexdigest()[:20]
        path=folder/f'cartao_{card_id}.png'
        if not path.exists():result.save(path)
        item={'id':core.fingerprint(path),'path':str(path.resolve()),'kind':'image','duration':0,'width':1920,'height':1080,
              'tags':[text],'aliases':[],'entity':'','usage':'generico','origin':'card','role':'media','selected':False}
        catalog['items']=[i for i in catalog['items'] if i['path']!=item['path']]+[item]
        row.update(path=item['path'],source_in=0,zoom=False,approved=False,reason='Cartão gerado com a fala. Revise o texto; não representa uma filmagem.');made+=1
        job.log(f'Cartão {made} criado.')
    core.save_plan(cfg,plan);core.write_json(Path(cfg['output'])/'catalogo.json',catalog)
    return {'plan':plan,'catalog':catalog,'message':f'{made} cartões criados. Trechos de silêncio sem mídia continuam pendentes.'}

def automatic_images(cfg,plan,catalog,job):
    """Spread at most N distinct online images across the narration; preserve failed slots."""
    from jobs import Cancelled
    limit=max(0,min(40,int(cfg.get('image_count',20))))
    candidates=[i for i,r in enumerate(plan['rows']) if r.get('text','').strip()]
    count=min(limit,max(0,len(candidates)//9))
    targets=[candidates[min(len(candidates)-1,int((n+.5)*len(candidates)/count))] for n in range(count)] if count else []
    if not cfg.get('image_terms','').strip():
        plan['image_report']={'requested':limit,'added':0,'warnings':['Informe a identidade obrigatória das imagens (ex.: Querétaro). Busca genérica desativada.']}
        core.save_plan(cfg,plan);return plan,catalog
    used={r['path'] for r in plan['rows'] if r.get('online_auto') and r.get('path')}
    cache={};made=0;warnings=[]
    for index in targets:
        job.check();row=plan['rows'][index]
        if row.get('online_auto'):continue
        subject=cfg.get('subject','').strip()
        query=((row.get('search_query') if cfg.get('planner')=='groq' else '') or subject or row['text'])[:180]
        job.log(f'Imagens da internet · {made}/{count} · buscando {query}')
        try:
            if query not in cache:cache[query]=search_images(query)
            from materials import allowed
            terms=[core.norm(t).strip() for t in cfg.get('image_terms','').split(',') if t.strip()]
            options=[e for e in cache[query] if terms and all(t in core.norm(e['title']) for t in terms) and allowed(cfg,{'description':e['title']})]
            # Never silently replace a specific query with an unrelated generic topic.
            for entry in options:
                job.check()
                existing=next((i for i in catalog['items'] if i.get('source',{}).get('id')==entry['id']),None)
                if existing and existing['path'] in used:continue
                path,catalog=download_image(cfg,entry,catalog,job)
                if path in used:continue
                used.add(path);row.pop('source_limit',None)
                row.update(path=path,source_in=0,zoom=True,zoom_direction='in' if made%2==0 else 'out',
                           online_auto=True,approved=False,reason='Imagem da internet sugerida por texto. Confira se representa este assunto.')
                made+=1;break
            else:warnings.append(f'Trecho {index+1}: sem imagem inédita adequada à busca.')
        except Cancelled:raise
        except Exception as e:warnings.append(f'Trecho {index+1}: {e}')
        core.save_plan(cfg,plan)
    plan['image_report']={'requested':limit,'added':made,'warnings':warnings}
    core.save_plan(cfg,plan)
    job.log(f'{made} imagens adicionadas de até {limit} solicitadas. '+('Algumas buscas não tiveram resultado; os vídeos foram mantidos.' if warnings else ''))
    return plan,catalog

def fit_image_backgrounds(cfg,plan,catalog,job):
    """Create cached 1080p compositions so foreground and BG share one transform."""
    from PIL import Image,ImageOps
    folder=Path(cfg['output'])/'imagens_compostas'
    known={i['path']:i for i in catalog['items']}
    bg=cfg.get('background','')
    if bg and not Path(bg).is_file():raise ValueError('O fundo selecionado não existe mais. Escolha outro BG.')
    for row in plan['rows']:
        job.check()
        item=known.get(row.get('path'))
        if not item or item.get('kind')!='image' or item.get('origin')=='card':continue
        original=item.get('composition_original',item['path'])
        with Image.open(original) as src:
            src=ImageOps.exif_transpose(src).convert('RGBA')
            w,h=src.size
            if abs(w/h-16/9)<.005:
                if item.get('composition_original'):row['path']=original
                continue
            identity=hashlib.sha256(('bg-v1'+core.fingerprint(original)+(core.fingerprint(bg) if bg else 'dark')).encode()).hexdigest()[:24]
            folder.mkdir(parents=True,exist_ok=True);path=(folder/(identity+'.png')).resolve()
            if not path.exists():
                canvas=Image.new('RGBA',(1920,1080),'#111b2a')
                if bg:
                    with Image.open(bg) as source:
                        background=ImageOps.fit(ImageOps.exif_transpose(source).convert('RGBA'),canvas.size)
                        canvas.alpha_composite(background)
                # Safe margin keeps the whole foreground inside the frame at 106% zoom.
                foreground=ImageOps.contain(src,(1760,960),Image.Resampling.LANCZOS)
                canvas.alpha_composite(foreground,((1920-foreground.width)//2,(1080-foreground.height)//2))
                canvas.convert('RGB').save(path)
        output=str(path)
        if output not in known:
            composite=dict(item,path=output,id=core.fingerprint(path),width=1920,height=1080,
                           origin='composite',composition_original=original,composition_background=bg)
            catalog['items'].append(composite);known[output]=composite
        row['path']=output;row['source_in']=0
        job.log('Imagem ajustada sobre o BG: '+Path(original).name)
    core.write_json(Path(cfg['output'])/'catalogo.json',catalog)
    core.save_plan(cfg,plan)
    return plan,catalog
