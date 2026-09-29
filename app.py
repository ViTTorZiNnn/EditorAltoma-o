from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
import json,os,secrets,threading,time,subprocess,sys,urllib.parse,webbrowser,hashlib
import core,engine,visuals,exporter,picker,materials,workflow,connections,image_sources,external_cuts,narration,providers
from jobs import Job,Cancelled
from drift_client import Drift,check,send
BASE=Path(__file__).resolve().parent
SECRET=secrets.token_urlsafe(32);LOCK=threading.Lock();ACTIVE=None;SEARCH_RESULTS={}
STATE={'busy':False,'logs':[],'result':None,'error':None,'percent':None,'message':'Pronto.','action':''}
DEFAULT={'project':'','footage':'','audio':'','srt':'','output':'','project_root':'','project_name':'','schema':7,
         'subject':'','language':'es','model':'small','background':'','device':'auto','shot':5,'scene_mode':'full',
         'precut_project':False,'precut_footage':False,'planner':'local','groq_model':'openai/gpt-oss-120b',
         'url':'http://127.0.0.1:4731/mcp','srt_mode':'exact','image_count':20,'image_provider':'google','script':'','voice_url':'http://127.0.0.1:3900','voice_id':'','voice_exe':'','voice_speed':1,'pause_keep':.12,'silence_min':.25,'silence_db':-45,'audio_original':'','audio_sample':'','stock_count':12,'text_overlays':True}
def report(message,percent=None):
    with LOCK:
        STATE['message']=message;STATE['percent']=percent
        if not STATE['logs'] or STATE['logs'][-1]!=message:STATE['logs']=(STATE['logs']+[message])[-150:]
def config_from(data):
    cfg={**DEFAULT,**{k:v for k,v in data.items() if k in DEFAULT}}
    for k in ('project','footage','audio','srt','output'):
        cfg[k]=str(cfg.get(k,'')).strip().strip('"')
        if cfg[k]:cfg[k]=str(Path(cfg[k]).expanduser().resolve())
    if not cfg['output'] or not cfg.get('project_root'):raise ValueError('Crie ou abra um projeto na etapa 1.')
    if cfg['output'] in (cfg['project'],cfg['footage']):raise ValueError('Resultados precisa ficar separado das fontes.')
    if cfg['model'] not in ('tiny','base','small','medium') or cfg['device'] not in ('auto','cpu','cuda'):raise ValueError('Configuração de transcrição inválida.')
    if cfg['language'] not in ('es','pt','en','auto') or cfg['scene_mode'] not in ('fast','full','off'):raise ValueError('Configuração inválida.')
    if cfg['planner'] not in ('local','groq') or not 2<=float(cfg['shot'])<=12:raise ValueError('Configuração de montagem inválida.')
    Path(cfg['output']).mkdir(parents=True,exist_ok=True);workflow.save_config(cfg);return cfg

def execute(action,data,job):
    private={}
    try:
        private=connections.load();private.update({k:data[k] for k in ('token','groq_key','pexels_key','pixabay_key','serper_key') if data.get(k)})
        if action=='check_connections':
            messages=[]
            url=data.get('url') or private.get('url') or DEFAULT['url']
            if private.get('token'):
                try:check(Drift(url,private['token']));messages.append('Drift conectado.')
                except Exception as e:messages.append('Drift: '+str(e))
            else:messages.append('Drift: salve o token da sessão. Você pode preparar o material sem conectar o editor.')
            if private.get('groq_key'):
                import urllib.request
                req=urllib.request.Request('https://api.groq.com/openai/v1/chat/completions',json.dumps({'model':data.get('model') or DEFAULT['groq_model'],'messages':[{'role':'user','content':'Reply OK'}],'max_tokens':8}).encode(),{'Content-Type':'application/json','User-Agent':'MontaVideo/0.7','Authorization':'Bearer '+private['groq_key']})
                try:
                    with urllib.request.urlopen(req,timeout=30) as response:json.load(response)
                    messages.append('Groq conectado e modelo respondeu.')
                except Exception as e:messages.append('Groq: '+engine.service_error(e,private['groq_key'])+'. Não foi confirmado acesso ao modelo.')
            else:messages.append('Groq não configurado. Modo local disponível.')
            result={'message':' '.join(messages),'connections':connections.status()}
        else:
            cfg=config_from(data.get('config',{}));out=Path(cfg['output'])
            cat=core.read_json(out/'catalogo.json',{'items':[]})
            if action=='context':
                result={'context':workflow.analyze(cfg,job,private.get('groq_key','')),'catalog':None,'plan':None,'message':'Confira o contexto identificado e clique Confirmar contexto.'}
            elif action in ('prepare','refresh_cuts'):
                cat=external_cuts.refresh(cfg,job)
                pending=len(cat.get('pending_sources',[]))
                result={'catalog':cat,'plan':None,'message':f"{len(cat['items'])} arquivos catalogados. {pending} vídeos ainda sem recorte concluído. "+('Conclua o CMD e atualize novamente.' if pending else 'Cenas prontas para revisão.')}
            elif action=='voice_list':result=narration.voices(cfg,job)
            elif action in ('voice_sample','voice_generate','voice_complete','audio_finish','audio_sync'):
                if action in ('voice_sample','voice_generate','voice_complete'):
                    path=narration.generate(cfg,job,action=='voice_sample')
                    if action=='voice_sample':cfg['audio_sample']=str(path)
                    else:cfg.update(audio_original=str(path),audio=str(path),srt='')
                    workflow.save_config(cfg)
                    if action!='voice_sample':
                        with LOCK:STATE['audio_ready']={'path':cfg['audio'],'config':dict(cfg)}
                if action in ('audio_finish','voice_complete'):
                    path,info=narration.trim(cfg,cfg.get('audio_original') or cfg['audio'],job);cfg.update(audio=str(path),srt='')
                    core.write_json(out/'audio_processado.json',info);workflow.save_config(cfg)
                    with LOCK:STATE['audio_ready']={'path':cfg['audio'],'config':dict(cfg)}
                if action in ('audio_finish','audio_sync','voice_complete'):
                    job.log('Áudio salvo. Criando SRT com os tempos da narração final…')
                    cfg['srt']=str(narration.synchronize(cfg,job));cfg['srt_mode']='exact'
                workflow.save_config(cfg)
                result={'config':cfg,'audio_path':cfg.get('audio_sample') if action=='voice_sample' else cfg['audio'],'message':'Amostra pronta para ouvir.' if action=='voice_sample' else 'Áudio salvo no projeto. Ouça o resultado antes de continuar.'}
                if action!='voice_sample':result.update(context=None,catalog=None,plan=None)
            elif action=='search_stock':
                context=workflow.require_context(cfg)
                if cat.get('prepared_signature')!=workflow.signature(cfg):raise ValueError('Clique Atualizar cenas antes de buscar B-roll.')
                selected=[p for p in ('pexels','pixabay') if private.get(p+'_key')]
                if not selected:raise ValueError('Salve uma chave Pexels ou Pixabay nas conexões.')
                queries=context.get('broll_queries') or context.get('queries',[])
                cat,info=providers.gather(cfg,cat,queries,'video',selected,private,job)
                result={'catalog':cat,'image_report':info,'message':f"{info['downloaded']} vídeos de apoio baixados. "+' '.join(info['warnings'])}
            elif action in ('search_images','import_images','download_url','review_images'):
                workflow.require_context(cfg)
                if cat.get('prepared_signature')!=workflow.signature(cfg):raise ValueError('Prepare os cortes antes de organizar as imagens.')
                if action=='search_images':
                    queries=data.get('queries') or workflow.require_context(cfg).get('queries',[])
                    if cfg['image_provider'] in ('pexels','pixabay','serper'):cat,info=providers.gather(cfg,cat,queries,'image',[cfg['image_provider']],private,job)
                    else:cat,info=image_sources.search(cfg,cat,queries,cfg['image_provider'],job)
                    result={'catalog':cat,'image_report':info,'message':f"{info['downloaded']} imagens baixadas. Confira e marque as fotos que podem entrar no vídeo. "+' '.join(info['warnings'])}
                elif action=='import_images':
                    root=Path(data['path']);paths=sorted(root.rglob('*')) if root.is_dir() else [root]
                    for path in paths:
                        job.check()
                        if path.is_file() and path.suffix.lower() in core.IMAGE:cat=workflow.add_asset(cfg,cat,path,job,'ai_local' if data.get('is_ai') else 'imported')
                    result={'catalog':cat,'message':'Imagens locais adicionadas para revisão. Nenhuma imagem foi gerada por IA.'}
                elif action=='download_url':
                    raw,url=image_sources.fetch(data['url']);record=image_sources.store_image(Path(cfg['project_root'])/'05_Imagens',raw,data.get('name') or cfg['subject'],url)
                    cat=image_sources.import_records(cfg,cat,[record],job);result={'catalog':cat,'message':'Imagem original salva no computador. Confira antes de aprovar.'}
                else:
                    reviewed=set(data.get('reviewed',[]))
                    for i in cat['items']:
                        if i['kind']=='image' and i.get('role')!='background':i['reviewed']=i['path'] in reviewed
                    result={'catalog':cat,'message':'Escolha de imagens salva.'}
                core.write_json(out/'catalogo.json',cat)
            elif action=='plan':
                workflow.require_context(cfg)
                if cat.get('prepared_signature')!=workflow.signature(cfg):raise ValueError('Prepare os cortes do material atual na etapa 2.')
                if not all(Path(i['path']).is_file() for i in cat['items'] if i.get('selected') and i.get('context_allowed',True)):raise ValueError('Uma mídia foi movida. Prepare o material novamente.')
                cfg['variation_seed']=secrets.randbits(32)
                plan=engine.make_plan(cfg,cat,core.read_json(out/'falas.json'),job,private.get('groq_key',''))
                plan['project_signature']=workflow.signature(cfg)
                plan,cat=visuals.fit_image_backgrounds(cfg,plan,cat,job)
                origins={i['path']:i.get('original_source',i['path']) for i in cat['items']}
                counts={}
                for row in plan['rows']:
                    if row.get('path'):counts[origins[row['path']]]=counts.get(origins[row['path']],0)+1
                plan['source_usage']=counts;core.save_plan(cfg,plan)
                result={'plan':plan,'catalog':cat,'message':'Base criada. Abra Revisar vídeo para assistir e trocar cenas.'}
            elif action in ('save','send'):
                plan=data.get('plan')
                if not plan or plan.get('project_signature')!=workflow.signature(cfg):raise ValueError('Esta montagem não corresponde ao projeto atual. Gere uma nova base.')
                core.save_plan(cfg,plan)
                if action=='save':result={'message':'Revisão salva neste projeto.'}
                else:
                    plan,cat=visuals.fit_image_backgrounds(cfg,plan,cat,job)
                    client=Drift(private.get('url') or cfg['url'],private.get('token',''));original=client.call
                    def call(name,args=None):job.check();return original(name,args)
                    client.call=call;result=send(cfg,plan,cat,client,job.log)
                    core.write_json(out/'ultimo_projeto_drift.json',result)
            elif action=='export':result=exporter.export(cfg,Drift(private.get('url') or cfg['url'],private.get('token','')),job)
            else:raise ValueError('Ação desconhecida.')
        job.check()
        with LOCK:STATE['result']=result
        report(result.get('message','Concluído.'),100)
    except Exception as e:
        message=str(e)
        for k in ('token','groq_key','pexels_key','pixabay_key','serper_key'):
            if private.get(k):message=message.replace(private[k],'[chave protegida]')
        with LOCK:
            STATE.update(message=message,error=message)
            if action in ('voice_complete','voice_generate','audio_finish','audio_sync') and 'cfg' in locals():STATE['result']={'config':cfg,'context':None,'catalog':None,'plan':None}
    finally:
        with LOCK:STATE['busy']=False

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def reply(self,status,data,ctype='application/json; charset=utf-8'):
        raw=data if isinstance(data,bytes) else json.dumps(data,ensure_ascii=False).encode()
        self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(raw)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(raw)
    def auth(self):return self.headers.get('X-MontaVideo-Key')==SECRET
    def do_GET(self):
        path=urllib.parse.urlsplit(self.path).path
        if path=='/app.js':return self.reply(200,(BASE/'ui/app.js').read_text(encoding='utf-8').replace('__SESSION_KEY__',SECRET).encode(),'text/javascript; charset=utf-8')
        if path=='/':return self.reply(200,(BASE/'ui/index.html').read_text(encoding='utf-8').replace('__SESSION_KEY__',SECRET).encode(),'text/html; charset=utf-8')
        if not self.auth():return self.reply(403,{'error':'Sessão inválida.'})
        if path=='/state':
            with LOCK:s=dict(STATE)
            return self.reply(200,s)
        if path=='/load':
            return self.reply(200,{'config':{**DEFAULT,**core.read_json(workflow.HOME/'preferencias.json',{})},'connections':connections.status(),'projects':core.read_json(workflow.HOME/'projetos.json',[])})
        return self.reply(404,{'error':'Não encontrado.'})
    def do_POST(self):
        global ACTIVE
        if not self.auth():return self.reply(403,{'error':'Sessão inválida.'})
        origin=self.headers.get('Origin')
        if origin and origin!=f'http://127.0.0.1:{self.server.server_port}':return self.reply(403,{'error':'Origem inválida.'})
        try:
            size=int(self.headers.get('Content-Length',0))
            if not 0<size<=8_000_000:raise ValueError('Pedido inválido.')
            data=json.loads(self.rfile.read(size));action=self.path.lstrip('/')
            if action not in ('cancel','preview','thumb','search','audio_preview') and STATE['busy']:return self.reply(409,{'error':'Aguarde ou cancele a tarefa em andamento.'})
            if action=='credentials_save':
                state=connections.save(data)
                if data.get('config',{}).get('project_root'):config_from(data['config'])
                return self.reply(200,{'connections':state})
            if action=='launch_cuts':return self.reply(200,external_cuts.launch(config_from(data['config'])))
            if action=='audio_preview':
                cfg={**DEFAULT,**data['config']};requested=Path(data.get('path','')).resolve()
                allowed=[Path(cfg[k]).resolve() for k in ('audio','audio_original','audio_sample') if cfg.get(k)]
                if requested not in allowed or not requested.is_file():raise ValueError('Áudio não pertence ao projeto.')
                mime='audio/wav' if requested.suffix.lower()=='.wav' else 'audio/mpeg'
                return self.reply(200,requested.read_bytes(),mime)
            if action=='new_project':return self.reply(200,{'config':workflow.create(data['parent'],data.get('name',''),DEFAULT),'catalog':None,'plan':None,'context':None})
            if action=='open_project':
                path=Path(data['file'])
                if path.is_dir():path=path/'07_Resultados'/'projeto.json' if (path/'07_Resultados'/'projeto.json').is_file() else path/'projeto.json'
                cfg=core.read_json(path)
                if not cfg or cfg.get('schema') not in (6,7):raise ValueError('Escolha um projeto criado nesta versão.')
                cfg={**DEFAULT,**cfg,'schema':7};workflow.save_config(cfg);workflow.register(cfg)
                return self.reply(200,{'config':cfg,**workflow.valid_state(cfg)})
            if action=='confirm_context':
                cfg=config_from(data['config']);out=Path(cfg['output']);context=core.read_json(out/'contexto.json',{})
                if context.get('signature')!=workflow.context_signature(cfg):raise ValueError('O material mudou. Analise o roteiro novamente.')
                context['confirmed']=True;core.write_json(out/'contexto.json',context)
                return self.reply(200,{'context':context,'message':'Contexto confirmado. Prepare o material na etapa 2.'})
            if action=='cancel':
                if ACTIVE:ACTIVE.event.set()
                return self.reply(200,{'message':'Cancelando… Uma chamada de rede em andamento pode levar até 90 s para terminar.'})
            if action=='pick':
                return self.reply(200,picker.choose(data.get('kind')))
            if action=='open_output':
                cfg=config_from(data.get('config',{}))
                if sys.platform!='win32':raise ValueError('Abrir pasta disponível no Windows.')
                target=cfg['output']
                if data.get('folder') in ('03_Audio','04_Cortes','05_Imagens','06_Imagens_IA','08_Broll_Baixado'):target=str(Path(cfg['project_root'])/data['folder'])
                os.startfile(target)
                return self.reply(200,{'message':'Pasta de resultados aberta.'})
            if action=='config':return self.reply(200,{'config':config_from(data.get('config',{}))})
            if action=='search':
                q=str(data.get('query',''))[:300]
                webbrowser.open('https://www.google.com/search?tbm=isch&q='+urllib.parse.quote(q))
                return self.reply(200,{'message':'Busca aberta no navegador. Confira a imagem e sua origem antes de usar.'})
            if action=='preview':
                out=Path(data['config']['output']);cat=core.read_json(out/'catalogo.json',{'items':[]})
                item=next((i for i in cat['items'] if i['path']==data.get('path')),None)
                if not item or item.get('kind')!='video':raise ValueError('Selecione um vídeo catalogado.')
                start=float(data.get('at',0));duration=min(15,float(data.get('duration',5)))
                if not 0<=start<item['duration'] or not 0<duration<=15:raise ValueError('Trecho inválido.')
                duration=min(duration,item['duration']-start)
                folder=out/'cache'/'previas';folder.mkdir(parents=True,exist_ok=True)
                name=hashlib.sha256((core.fingerprint(item['path'])+str(start)+str(duration)).encode()).hexdigest()[:24]
                target=folder/(name+'.mp4')
                if not target.exists():
                    tmp=folder/(name+'.partial.mp4')
                    p=core.run([core.ffmpeg(),'-y','-v','error','-ss',str(start),'-i',item['path'],'-t',str(duration),'-an','-vf','scale=640:-2','-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p','-movflags','+faststart',str(tmp)])
                    if p.returncode:raise ValueError('Não foi possível gerar a prévia.')
                    tmp.replace(target)
                return self.reply(200,target.read_bytes(),'video/mp4')
            if action=='thumb':
                out=Path(data['config']['output']);cat=core.read_json(out/'catalogo.json',{'items':[]})
                item=next((i for i in cat['items'] if i['path']==data.get('path')),None)
                if not item:raise ValueError('Arquivo não catalogado.')
                pos=float(data.get('at',0))
                if not 0<=pos<=max(item['duration'],0):raise ValueError('Tempo inválido.')
                thumbs=out/'cache'/'miniaturas';thumbs.mkdir(parents=True,exist_ok=True)
                cache=thumbs/(hashlib.sha256((core.fingerprint(item['path'])+str(pos)).encode()).hexdigest()[:24]+'.jpg')
                if cache.exists():return self.reply(200,cache.read_bytes(),'image/jpeg')
                p=core.run([core.ffmpeg(),'-v','error','-ss',str(pos),'-i',item['path'],'-frames:v','1','-vf','scale=640:-2','-f','image2pipe','-vcodec','mjpeg','-'])
                if p.returncode or not p.stdout:raise ValueError('Prévia indisponível.')
                cache.write_bytes(p.stdout)
                return self.reply(200,p.stdout,'image/jpeg')
            if action not in ('voice_list','voice_sample','voice_generate','voice_complete','audio_finish','audio_sync','refresh_cuts','search_stock','context','prepare','search_images','import_images','download_url','review_images','plan','save','check_connections','send','export'):raise ValueError('Ação desconhecida.')
            with LOCK:
                if STATE['busy']:return self.reply(409,{'error':'Aguarde ou cancele a tarefa atual.'})
                ACTIVE=Job(report);STATE.update(audio_ready=None,busy=True,result=None,error=None,logs=[],percent=None,action=action,message='Iniciando…')
            threading.Thread(target=execute,args=(action,data,ACTIVE),daemon=True).start();self.reply(202,{'started':True})
        except Exception as e:self.reply(400,{'error':str(e)})

def main():
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    url=f'http://127.0.0.1:{server.server_port}'
    try:
        if '--browser' in sys.argv:
            print('Modo navegador local: '+url,flush=True);webbrowser.open(url)
            while True:time.sleep(.5)
        else:
            import webview
            picker.WINDOW=webview.create_window('MontaVideo 0.7.1',url,width=1280,height=900,min_size=(850,600),background_color='#10151d',confirm_close=True)
            webview.start(gui='edgechromium' if sys.platform=='win32' else None)
    except KeyboardInterrupt:pass
    except Exception as e:
        print('Não foi possível abrir a janela: '+str(e),flush=True)
        print('Use INICIAR_NAVEGADOR.bat como alternativa, ou confira a instalação do Microsoft Edge WebView2.',flush=True)
        picker.WINDOW=None
        webbrowser.open(url)
        print('Modo navegador aberto automaticamente: '+url,flush=True)
        try:
            while True:time.sleep(.5)
        except KeyboardInterrupt:pass
    finally:
        if ACTIVE:ACTIVE.event.set()
        until=time.monotonic()+5
        while STATE['busy'] and time.monotonic()<until:time.sleep(.1)
        server.shutdown();server.server_close()
if __name__=='__main__':main()
