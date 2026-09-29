"""MontaVideo: catálogo local, transcrição e decisões de edição sem recortes físicos."""
from pathlib import Path
import csv, hashlib, json, math, os, re, subprocess, unicodedata
from functools import lru_cache

BASE = Path(__file__).resolve().parent
VIDEO = {'.mp4', '.mkv', '.mov', '.webm', '.avi', '.m4v', '.mts'}
IMAGE = {'.jpg', '.jpeg', '.png', '.webp', '.bmp'}
STOP = set('a o as os e de da do das dos um uma com para por em no na nos nas que se el la los las un una con del y en es este esta estos estas su sus sobre como mais mas muito muy video videos footage especifico generico'.split())

def norm(s):
    return re.sub(r'[^a-z0-9]+', ' ', unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode().lower()).strip()

def words(s):
    return {w for w in norm(s).split() if len(w)>1 and not w.isdigit()} - STOP

def read_json(p, default=None):
    return json.loads(Path(p).read_text(encoding='utf-8-sig')) if Path(p).exists() else default

def write_json(p, data):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + '.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8'); tmp.replace(p)

def fingerprint(p):
    p = Path(p); st = p.stat()
    return hashlib.sha256(f'{p.resolve()}|{st.st_size}|{st.st_mtime_ns}'.encode()).hexdigest()[:24]

def ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()

def run(cmd, timeout=120):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
                          creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))

def probe(path):
    p = run([ffmpeg(), '-hide_banner', '-i', str(path)])
    t = p.stderr.decode('utf-8', 'replace')
    dur = re.search(r'Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)', t)
    size = re.search(r'Video:.*?\b(\d{2,5})x(\d{2,5})\b', t)
    if not size and Path(path).suffix.lower() in VIDEO | IMAGE:
        raise ValueError('Não foi possível ler vídeo/imagem: ' + str(path))
    duration = int(dur[1])*3600 + int(dur[2])*60 + float(dur[3]) if dur else 0
    if Path(path).suffix.lower() in VIDEO and duration <= 0:
        raise ValueError('Duração indisponível: ' + str(path))
    return {'duration': duration, 'width': int(size[1]) if size else 0, 'height': int(size[2]) if size else 0}

def load_meta(path, root, generic):
    """tags.json de pastas são herdadas; arquivo.mp4.tags.json pode refinar e marcar intervalos."""
    path, root = Path(path), Path(root)
    meta = {'tags': [], 'aliases': [], 'entity': '', 'usage': 'generico' if generic else 'especifico'}
    dirs = [root] + [root.joinpath(*path.relative_to(root).parts[:i]) for i in range(1, len(path.relative_to(root).parts))]
    for p in [d/'tags.json' for d in dirs] + [Path(str(path)+'.tags.json')]:
        if p.exists():
            val = read_json(p)
            if not isinstance(val, dict): raise ValueError(f'{p}: esperado objeto JSON.')
            for key in ('tags','aliases'):
                if key in val:
                    if not isinstance(val[key], list): raise ValueError(f'{p}: {key} precisa ser lista.')
                    meta[key] += val[key]
            for key in ('entity','usage','ranges'):
                if key in val: meta[key] = val[key]
    if meta['usage'] not in ('generico','especifico'):
        raise ValueError(f'{path}: usage deve ser generico ou especifico.')
    meta['tags'] += [x for x in path.stem.split('__') if x]
    meta['tags'] += list(path.relative_to(root).parts[:-1])
    return meta

def scan(config, log=print):
    cache_dir = Path(config['output'])/'cache'; cache_dir.mkdir(parents=True, exist_ok=True)
    cache = read_json(cache_dir/'catalog.json', {})
    items, errors, seen = [], [], set()
    roots = [(config['project'], False)] + ([(config['footage'], True)] if config.get('footage') else [])
    if not Path(config['project']).is_dir(): raise ValueError('Pasta VD do projeto não encontrada.')
    excluded = Path(config['output']).resolve()
    for root, generic in roots:
        root = Path(root).resolve()
        if not root.is_dir(): raise ValueError(f'Pasta não encontrada: {root}')
        for p in sorted(root.rglob('*')):
            if not p.is_file() or p.suffix.lower() not in VIDEO | IMAGE: continue
            if excluded in p.resolve().parents: continue
            if p.resolve() in seen: continue
            seen.add(p.resolve())
            try:
                key = fingerprint(p)
                info = cache.get(key) or probe(p)
                cache[key] = info
                meta = load_meta(p, root, generic)
                ranges = meta.get('ranges', [])
                for r in ranges:
                    if not (0 <= float(r['start']) < float(r['end']) <= info['duration']+.02):
                        raise ValueError('Intervalo de tags fora da duração do vídeo.')
                items.append(dict(info, **meta, path=str(p), id=key,
                                  kind='image' if p.suffix.lower() in IMAGE else 'video'))
                log(f'Catalogado {len(items)}: {p.name}')
            except Exception as e: errors.append(f'{p.name}: {e}'); log(errors[-1])
    write_json(cache_dir/'catalog.json', cache)
    write_json(Path(config['output'])/'catalogo.json', {'items':items,'errors':errors})
    if not items: raise ValueError('Nenhuma mídia válida encontrada. ' + '; '.join(errors[:3]))
    return {'items': items, 'errors': errors}

@lru_cache(maxsize=8192)
def concepts(text):
    found = words(text)
    aliases = read_json(BASE/'tags_vocabulario.json', {})
    normalized = ' ' + norm(text) + ' '
    for canonical, synonyms in aliases.items():
        if any(' '+norm(term)+' ' in normalized for term in [canonical]+synonyms): found.add('@'+canonical)
    return found

def srt_time(v):
    h,m,s = v.replace(',', '.').split(':'); return int(h)*3600+int(m)*60+float(s)

def read_srt(path):
    raw = Path(path).read_text(encoding='utf-8-sig').replace('\r','')
    pattern = r'(\d{1,2}:\d{2}:\d{2}[,.]\d+)\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,.]\d+)[^\n]*\n(.*?)(?=\n\s*\n|\Z)'
    cues = [{'start':srt_time(a),'end':srt_time(b),'text':re.sub('<[^>]+>', '', t.replace('\n',' ')).strip()} for a,b,t in re.findall(pattern, raw, re.S)]
    if not cues: raise ValueError('SRT vazio ou inválido.')
    cues.sort(key=lambda x:x['start'])
    for c in cues:
        if c['start'] < 0 or c['end'] <= c['start']: raise ValueError('SRT com tempos inválidos.')
    return cues

def transcribe(config, log=print):
    try: from faster_whisper import WhisperModel
    except ImportError: raise ValueError('Execute INSTALAR_TRANSCRICAO.bat ou informe um SRT já existente.')
    audio = Path(config['audio'])
    if not audio.is_file(): raise ValueError('Áudio não encontrado.')
    out = Path(config['output']); cache = out/'cache'; cache.mkdir(parents=True,exist_ok=True)
    model = config.get('model','small'); language = config.get('language','es')
    key = fingerprint(audio) + '_' + model + '_' + language
    target = cache/(key+'.transcript.json')
    if target.exists(): log('Transcrição reutilizada do cache.'); return read_json(target)
    device = config.get('device','cpu')
    log(f'Carregando modelo {model} em {device}. Primeiro uso baixa o modelo gratuito.')
    try:
        engine = WhisperModel(model, device=device, compute_type='float16' if device=='cuda' else 'int8',
                              download_root=str(BASE/'modelos'))
        segs, info = engine.transcribe(str(audio), language=None if language=='auto' else language,
                                      word_timestamps=True, vad_filter=True)
        cues = []
        for seg in segs:
            cues.append({'start':seg.start,'end':seg.end,'text':seg.text.strip(),
                         'words':[{'start':w.start,'end':w.end,'text':w.word} for w in (seg.words or [])]})
            log(f'Transcrição: {seg.end:.0f} segundos processados')
    except Exception as e:
        raise ValueError(f'Transcrição falhou ({device}). Se CUDA estiver indisponível, selecione CPU. Detalhe: {e}')
    if not cues: raise ValueError('Não foi encontrada fala no áudio.')
    write_json(target, cues)
    return cues

def slots(cues, duration, shot, rng=None):
    # Fronteiras de fala próximas ao tamanho desejado; pausas continuam cobertas.
    bounds = sorted({float(c['start']) for c in cues} | {float(c['end']) for c in cues})
    out=[]; at=0.
    while at < duration-.001:
        length = rng.uniform(max(2,shot-2),min(12,shot+3)) if rng else shot
        target = min(at+length,duration)
        near = [b for b in bounds if at+max(1.5,length-1) <= b <= min(duration,at+length+1)]
        end = min(near,key=lambda b:abs(b-target)) if near and target<duration else target
        if duration-end < 1.: end=duration
        # Word timestamps reduce context spill; SRT-only cues necessarily have coarser context.
        text=[]
        for c in cues:
            if c['end']<=at or c['start']>=end: continue
            if c.get('words'):
                text += [w['text'] for w in c['words'] if w['end']>at and w['start']<end]
            else: text.append(c['text'])
        out.append({'at':round(at,3),'duration':round(end-at,3),'text':' '.join(text).strip()})
        at=end
    return out

def candidates(items, text, context, used, need):
    explicit=[]; nt=' '+norm(text)+' '
    for item in items:
        if item.get('entity') and any(' '+norm(x)+' ' in nt for x in [item['entity']]+item.get('aliases',[]) if norm(x)):
            explicit.append(item['entity'])
    explicit=set(explicit)
    q=concepts(text); qc=concepts(context)
    ranked=[]
    for item in items:
        if explicit and item.get('entity') not in explicit: continue
        segments=item.get('ranges') or [{'start':0,'end':item['duration'],'tags':[]}]
        for r in segments:
            if item['kind']=='video' and float(r['end'])-float(r['start']) < need-.001: continue
            tags=' '.join(map(str,item['tags']+r.get('tags',[])+[item.get('entity','')]+item.get('aliases',[])))
            iw=concepts(tags); direct=q & iw
            score=sum(3 if x.startswith('@') else 1 for x in direct)
            score+=.2*len(qc & iw)
            if explicit: score+=5
            if not direct and not explicit: continue
            score-=min(used.get(item['id'],0)*.6,2)
            ranked.append((score,item,r))
    return sorted(ranked,key=lambda x:(-x[0],x[1]['path'],x[2]['start']))

def make_plan(config, catalog, cues, log=print):
    duration=probe(config['audio'])['duration']
    if not duration: raise ValueError('Duração da narração indisponível.')
    if max(c['end'] for c in cues)>duration+2: raise ValueError('SRT ultrapassa o áudio em mais de 2 segundos. Confira o arquivo.')
    shot=float(config.get('shot',5))
    if not 2<=shot<=12: raise ValueError('Duração dos planos deve ficar entre 2 e 12 segundos.')
    rows=slots(cues,duration,shot); used={}; last=''; warnings=[]
    for i,row in enumerate(rows):
        context=rows[i-1]['text'] if i else ''
        ranked=candidates(catalog['items'],row['text'],context,used,row['duration'])
        alt=next((x for x in ranked if x[1]['id']!=last and x[0]>=ranked[0][0]-1),None) if ranked else None
        chosen=alt or (ranked[0] if ranked else None)
        row.update({'path':'','source_in':0,'approved':False,'transition':'crossfade' if i and i%3==0 else 'none','zoom':False})
        if chosen:
            score,item,r=chosen
            count=used.get(item['id'],0)
            room=max(0,float(r['end'])-float(r['start'])-row['duration'])
            offset=min(room,1.+count*(row['duration']+1.)) if item['kind']=='video' else 0
            row.update(path=item['path'],source_in=round(float(r['start'])+offset,3),
                       zoom=item['kind']=='image',reason=f'Tags coincidentes; pontuação {score:.1f}. Conferir imagem e contexto.')
            used[item['id']]=count+1; last=item['id']
        else: row['reason']='SEM CORRESPONDÊNCIA: escolha uma mídia na revisão.'
    result={'version':1,'audio':str(Path(config['audio']).resolve()),'duration':duration,'rows':rows,
            'warnings':warnings,'selection':'tags; não há reconhecimento visual nesta versão','audio_fingerprint':fingerprint(config['audio'])}
    save_plan(config,result)
    log(f'Plano: {len(rows)} trechos, {sum(not r["path"] for r in rows)} sem correspondência. Revise antes de enviar.')
    return result

def save_plan(config, plan):
    out=Path(config['output']); write_json(out/'plano.json',plan)
    with (out/'plano.csv').open('w',encoding='utf-8-sig',newline='') as f:
        keys=['at','duration','text','path','source_in','transition','zoom','approved','reason']
        w=csv.DictWriter(f,fieldnames=keys,extrasaction='ignore'); w.writeheader(); w.writerows(plan['rows'])

def validate_plan(plan, catalog):
    known={i['path']:i for i in catalog['items']}; end=0
    if not Path(plan['audio']).is_file(): raise ValueError('Narração não encontrada.')
    if not plan['rows']: raise ValueError('Plano vazio.')
    if plan.get('audio_fingerprint') and fingerprint(plan['audio']) != plan['audio_fingerprint']:
        raise ValueError('A narração mudou depois do planejamento. Gere o plano novamente.')
    for n,r in enumerate(plan['rows'],1):
        for key in ('at','duration','source_in'):
            if not isinstance(r[key],(int,float)) or not math.isfinite(r[key]): raise ValueError(f'Trecho {n}: número inválido.')
        if abs(r['at']-end)>.02 or r['duration']<=0 or r['source_in']<0: raise ValueError(f'Trecho {n}: tempos inválidos ou lacuna.')
        if not r.get('approved'): raise ValueError(f'Trecho {n}: falta marcar revisão.')
        item=known.get(r['path'])
        if not item or not Path(r['path']).is_file(): raise ValueError(f'Trecho {n}: escolha um arquivo do catálogo.')
        if re.fullmatch(r'[0-9a-f]{24}',item['id']) and fingerprint(r['path'])!=item['id']:
            raise ValueError(f'Trecho {n}: arquivo modificado; catalogue e gere novamente.')
        if item['kind']=='video' and r['source_in']+r['duration']>item['duration']+.02:
            raise ValueError(f'Trecho {n}: corte ultrapassa o vídeo original.')
        if r.get('transition') not in ('none','crossfade'): raise ValueError('Transição inválida.')
        end=r['at']+r['duration']
    if abs(end-plan['duration'])>.05: raise ValueError('Plano não cobre a narração inteira.')
    return True

def detect_scenes(config, catalog, log=print):
    """Passagem opcional em baixa resolução; salva somente limites, nunca clipes."""
    root=Path(config['output'])/'cache'; root.mkdir(parents=True,exist_ok=True)
    for item in catalog['items']:
        if item['kind']!='video' or item.get('ranges'): continue
        target=root/(item['id']+'.scenes-v1.json')
        if target.exists():
            ranges=read_json(target); log('Cenas reutilizadas: '+Path(item['path']).name)
        else:
            log('Detectando mudanças visuais: '+Path(item['path']).name+' (pode demorar)')
            cmd=[ffmpeg(),'-hide_banner','-nostdin','-i',item['path'],'-an',
                 '-vf',"scale=256:-2,fps=3,select='gt(scene,0.25)',showinfo",'-f','null','-']
            p=run(cmd,timeout=3600)
            if p.returncode: raise RuntimeError('Falha ao analisar cenas: '+p.stderr.decode('utf-8','replace')[-1000:])
            times=[float(x) for x in re.findall(r'pts_time:([\d.]+)',p.stderr.decode('utf-8','replace'))]
            times=sorted(set([0.]+[t for t in times if 0<t<item['duration']]+[item['duration']]))
            ranges=[{'start':a,'end':b,'tags':[]} for a,b in zip(times,times[1:]) if b-a>=.1]
            write_json(target,ranges)
        item['ranges']=ranges
    write_json(Path(config['output'])/'catalogo.json',catalog)
    return catalog
