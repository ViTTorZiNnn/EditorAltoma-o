"""Local VoiceStudio integration, resumable synthesis, pause trimming, final timing."""
from pathlib import Path
import urllib.request,urllib.parse,json,hashlib,re,wave,shutil,sys
import core,engine
import os,subprocess,time

def base_url(cfg):
    u=urllib.parse.urlsplit(cfg.get('voice_url','http://127.0.0.1:3900'))
    if u.scheme!='http' or u.hostname not in ('localhost','127.0.0.1','::1') or u.username or u.password:raise ValueError('VoiceStudio: use um endereço HTTP local.')
    return urllib.parse.urlunsplit((u.scheme,u.netloc,'','','')).rstrip('/')

def request(cfg,path,data=None,timeout=30):
    headers={};body=None
    if data is not None:body=urllib.parse.urlencode(data).encode();headers['Content-Type']='application/x-www-form-urlencoded'
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(urllib.request.Request(base_url(cfg)+path,body,headers),timeout=timeout) as r:return r.read()
    except urllib.error.HTTPError as e:
        detail=e.read(2048).decode('utf-8','replace');raise ValueError(f'VoiceStudio HTTP {e.code}: {detail}') from None
    except urllib.error.URLError:raise ValueError('Abra o VoiceStudio e confira o endereço local em Integrações. O modelo e a voz precisam estar disponíveis nele.') from None

def ensure_service(cfg,job=None):
    try:
        request(cfg,'/health',timeout=2);return
    except ValueError:pass
    if sys.platform!='win32':raise ValueError('VoiceStudio local não respondeu. Inicie seu serviço local e confira o endereço.')
    candidates=[]
    explicit=str(cfg.get('voice_exe','')).strip().strip('"')
    if explicit:candidates=[Path(explicit)]
    else:
        for base in (Path(os.environ.get('LOCALAPPDATA',''))/'Programs',Path(os.environ.get('ProgramFiles','C:/Program Files'))):
            if base.is_dir():
                for directory in base.iterdir():
                    if directory.is_dir() and 'voicestudio' in directory.name.lower().replace(' ',''):
                        candidates.extend(directory.glob('*.exe'))
    exe=next((p for p in candidates if p.is_file() and p.suffix.lower()=='.exe' and 'uninstall' not in p.name.lower() and (explicit or 'voicestudio' in p.stem.lower().replace(' ',''))),None)
    if not exe:raise ValueError('VoiceStudio não encontrado nas instalações comuns. Informe o caminho do VoiceStudio.exe em Configurar serviço local.')
    if job:job.log('Iniciando VoiceStudio instalado. Aguardando o serviço local…')
    subprocess.Popen([str(exe)],cwd=str(exe.parent),close_fds=True)
    for _ in range(60):
        if job:job.check()
        try:request(cfg,'/health',timeout=1);return
        except ValueError:time.sleep(.5)
    raise ValueError('VoiceStudio foi iniciado, mas o serviço não respondeu. Confira a porta em Integrações e aguarde o carregamento do programa.')

def voices(cfg,job=None):
    ensure_service(cfg,job)
    json.loads(request(cfg,'/health'))
    profiles=json.loads(request(cfg,'/profiles'))
    if isinstance(profiles,dict):profiles=profiles.get('profiles',profiles.get('voices',[]))
    if not isinstance(profiles,list):raise ValueError('VoiceStudio retornou lista de vozes inválida.')
    rows=[{'id':str(p['id']),'name':p.get('name',str(p['id'])),'group':'Perfis salvos','description':p.get('instruct','')} for p in profiles if isinstance(p,dict) and 'id' in p]
    warning=''
    try:
        offset=0
        while True:
            page=json.loads(request(cfg,f'/archetypes?limit=500&offset={offset}'))
            items=page.get('items',[])
            rows.extend({'id':'archetype:'+str(p['id']),'name':p.get('name',str(p['id'])),'group':'Galeria','description':p.get('instruct','')} for p in items)
            offset+=len(items)
            if not items or offset>=page.get('total',offset):break
    except ValueError as e:warning=' Galeria indisponível nesta instalação: '+str(e)
    return {'voices':rows,'message':f'{len(rows)} vozes encontradas. Escolha uma e gere uma amostra antes da narração.'+warning}

def prepare_voice(cfg,job):
    choice=str(cfg.get('voice_id','')).strip()
    if not choice:raise ValueError('Escolha uma voz. A geração sem perfil foi desativada para evitar trocar de narrador.')
    ensure_service(cfg,job)
    root=folder(cfg);cache=root/'partes';cache.mkdir(exist_ok=True)
    ident=hashlib.sha256((base_url(cfg)+choice).encode()).hexdigest()[:20]
    req=cache/(ident+'.voice-request.json');out=cache/(ident+'.voice.json')
    core.write_json(req,{'operation':'resolve','config':{'voice_url':base_url(cfg),'voice_id':choice},'path':str(out)})
    try:job.run([sys.executable,str(Path(__file__).with_name('voice_worker.py')),str(req)],timeout=1900)
    finally:req.unlink(missing_ok=True)
    voice=core.read_json(out)
    job.log('Voz selecionada: '+voice['name']+'. A mesma referência será usada em todas as partes.')
    return voice

def resolve_voice(cfg):
    choice=cfg['voice_id']
    if choice.startswith('archetype:'):
        result=json.loads(request(cfg,'/archetypes/'+urllib.parse.quote(choice.split(':',1)[1],safe='')+'/use',{},timeout=1800))
        choice=str(result.get('profile_id',''))
        if not choice:raise ValueError('VoiceStudio não criou o perfil da voz escolhida.')
    endpoint='/profiles/'+urllib.parse.quote(choice,safe='')
    # This endpoint materializes a pending design sample before synthesis.
    raw=request(cfg,endpoint+'/audio',timeout=1800)
    if len(raw)<44:raise ValueError('A voz selecionada não possui uma referência de áudio válida.')
    profile=json.loads(request(cfg,endpoint))
    if not (profile.get('ref_audio_path') or profile.get('locked_audio_path')):
        raise ValueError('O perfil não possui referência persistente. Salve uma voz com amostra no VoiceStudio.')
    return {'id':choice,'name':profile.get('name',choice),'reference_hash':hashlib.sha256(raw).hexdigest(),'seed':profile.get('seed') if profile.get('seed') is not None else 42}

def chunks(text,limit=900):
    # Sentence boundaries first; hard split unusually long sentences at whitespace.
    result=[];current=''
    for sentence in re.split(r'(?<=[.!?])\s+|\n+',text.strip()):
        words=sentence.split();parts=[];part=''
        for word in words:
            if len(part)+len(word)+1>limit and part:parts.append(part);part=''
            part=(part+' '+word).strip()
        if part:parts.append(part)
        for part in parts:
            if current and len(current)+len(part)+1>limit:result.append(current);current=''
            current=(current+' '+part).strip()
    if current:result.append(current)
    return result

def folder(cfg):
    p=Path(cfg['project_root'])/'03_Audio';p.mkdir(parents=True,exist_ok=True);return p

def generate(cfg,job,sample=False):
    text=cfg.get('script','').strip()
    if not text:raise ValueError('Cole o roteiro na etapa Criar narração.')
    voice=prepare_voice(cfg,job)
    root=folder(cfg);parts=chunks(text,240 if sample else 900)
    if sample:parts=parts[:1]
    cache=root/'partes';cache.mkdir(exist_ok=True);paths=[]
    for n,part in enumerate(parts,1):
        job.check();payload={'text':part,'language':cfg.get('language','es') if cfg.get('language')!='auto' else 'Auto','speed':str(cfg.get('voice_speed',1)),'num_step':'32','profile_id':voice['id'],'seed':str(voice['seed'])}
        ident=hashlib.sha256(json.dumps(['fixed-voice-v1',base_url(cfg),voice['reference_hash'],payload],sort_keys=True).encode()).hexdigest()[:24];path=cache/(ident+'.wav')
        if not path.exists():
            job.log(f'Gerando narração com {voice["name"]} · bloco {n}/{len(parts)}. Os blocos serão unidos em um áudio.',(n-1)/len(parts)*100)
            reqfile=cache/(ident+'.request.json');core.write_json(reqfile,{'config':{'voice_url':base_url(cfg)},'payload':payload,'path':str(path)})
            try:job.run([sys.executable,str(Path(__file__).with_name('voice_worker.py')),str(reqfile)],timeout=1900)
            finally:reqfile.unlink(missing_ok=True)
            job.check()
        paths.append(path)
    fingerprint=hashlib.sha256(''.join(str(p) for p in paths).encode()).hexdigest()[:12]
    target=root/(('amostra_' if sample else 'narracao_original_')+fingerprint+'.wav')
    # Normalize every chunk to consistent PCM before joining; no shell, no concat-path quoting.
    if not target.exists():
        temp=target.with_suffix('.partial.wav')
        with wave.open(str(temp),'wb') as out:
            out.setnchannels(1);out.setsampwidth(2);out.setframerate(24000)
            for p in paths:
                job.check();norm=cache/(p.stem+'_pcm.wav')
                if not norm.exists():job.run([core.ffmpeg(),'-y','-v','error','-i',str(p),'-ac','1','-ar','24000','-c:a','pcm_s16le',str(norm)],timeout=120)
                with wave.open(str(norm),'rb') as src:
                    while True:
                        frames=src.readframes(24000*10)
                        if not frames:break
                        out.writeframesraw(frames)
        temp.replace(target)
    core.write_json(target.with_suffix('.voz.json'),{'voice':voice,'parts':len(parts),'language':cfg.get('language'),'speed':cfg.get('voice_speed',1),'audio':str(target)})
    if not sample:(root/'roteiro.txt').write_text(text,encoding='utf-8')
    return target

def kept_intervals(duration,silences,pause):
    keep=[];cursor=0.
    for a,b in sorted(silences):
        a=max(cursor,min(duration,a));b=max(a,min(duration,b))
        # Retain a small pause split around the cut, not zero breathing room.
        left=min(duration,a+pause/2);right=max(left,b-pause/2)
        if left>cursor:keep.append((cursor,left))
        cursor=right
    if cursor<duration:keep.append((cursor,duration))
    return [(a,b) for a,b in keep if b-a>.001]

def trim(cfg,source,job):
    source=Path(source)
    if not source.is_file():raise ValueError('Escolha ou gere um arquivo de narração.')
    root=folder(cfg);pause=float(cfg.get('pause_keep',.12));minimum=float(cfg.get('silence_min',.25));threshold=float(cfg.get('silence_db',-45))
    if not 0<=pause<=1 or not .1<=minimum<=3 or not -80<=threshold<=-15:raise ValueError('Ajuste de pausas inválido.')
    ident=hashlib.sha256(json.dumps([core.fingerprint(source),pause,minimum,threshold]).encode()).hexdigest()[:12]
    target=root/('narracao_final_'+ident+'.wav');manifest=target.with_suffix('.json')
    if target.exists() and manifest.exists():return target,core.read_json(manifest)
    info=engine.probe(source,job);duration=info['duration'];starts=[];ends=[]
    def line(s):
        a=re.search(r'silence_start:\s*([\d.]+)',s);b=re.search(r'silence_end:\s*([\d.]+)',s)
        if a:starts.append(float(a[1]))
        if b:ends.append(float(b[1]))
    job.log('Identificando pausas do áudio…')
    job.run([core.ffmpeg(),'-hide_banner','-nostdin','-i',str(source),'-af',f'silencedetect=noise={threshold}dB:d={minimum}','-f','null','-'],line=line,timeout=1800)
    if len(starts)>len(ends):ends.append(duration)
    intervals=kept_intervals(duration,list(zip(starts,ends)),pause)
    if not intervals or sum(b-a for a,b in intervals)<duration*.08:raise ValueError('O limiar classificou quase todo o áudio como silêncio. Reduza a sensibilidade; o original foi preservado.')
    # Stream PCM once and copy ranges. Linear memory; handles long narrations without huge filters.
    pcm=root/('pcm_'+ident+'.wav');job.run([core.ffmpeg(),'-y','-v','error','-i',str(source),'-ac','1','-ar','24000','-c:a','pcm_s16le',str(pcm)],timeout=1800)
    temp=target.with_suffix('.partial.wav');mapping=[];at=0
    try:
        with wave.open(str(pcm),'rb') as src,wave.open(str(temp),'wb') as out:
            out.setparams(src.getparams());rate=src.getframerate()
            for a,b in intervals:
                job.check();first=round(a*rate);last=min(src.getnframes(),round(b*rate));src.setpos(first);remain=last-first
                mapping.append({'source_start':first/rate,'source_end':last/rate,'final_start':at/rate});at+=remain
                while remain>0:
                    size=min(remain,rate*10);out.writeframesraw(src.readframes(size));remain-=size
        temp.replace(target)
    finally:pcm.unlink(missing_ok=True)
    result={'original':str(source),'final':str(target),'original_seconds':duration,'final_seconds':at/24000,'intervals':mapping};core.write_json(manifest,result);return target,result

def timestamp(seconds):
    ms=round(max(0,seconds)*1000);h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000);return f'{h:02}:{m:02}:{s:02},{ms:03}'

def synchronize(cfg,job):
    # Always analyze final audio, never stretch the original script into invented times.
    cues=engine.transcript(dict(cfg,srt=''),job);root=folder(cfg);fp=core.fingerprint(cfg['audio'])[:12]
    srt=root/('narracao_'+fp+'.srt');srt.write_text('\n\n'.join(f'{n}\n{timestamp(c["start"])} --> {timestamp(c["end"])}\n{c["text"]}' for n,c in enumerate(cues,1))+'\n',encoding='utf-8')
    core.write_json(root/('palavras_'+fp+'.json'),cues);core.write_json(Path(cfg['output'])/'falas.json',cues)
    # Preserve word timestamps when this SRT is selected later.
    core.write_json(Path(str(srt)+'.timing.json'),{'audio_fingerprint':core.fingerprint(cfg['audio']),'srt_fingerprint':core.fingerprint(srt),'cues':cues})
    return srt
