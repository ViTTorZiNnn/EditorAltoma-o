"""Cliente MCP HTTP local. Compatibilidade baseada nos comandos do Drift v0.6.0."""
import json, time, urllib.request, urllib.parse
from pathlib import Path
from core import validate_plan, write_json

class Drift:
    def __init__(self,url,token):
        u=urllib.parse.urlsplit(url)
        if u.scheme!='http' or u.hostname not in ('127.0.0.1','localhost','::1') or u.username or u.password:
            raise ValueError('Use apenas o endereço HTTP local mostrado pelo Drift.')
        self.url=url.rstrip('/')
        if not u.path or u.path=='/': self.url+='/mcp'
        self.token=token; self.counter=0; self.session=None
        # Não permitir proxies ambientais para o token local.
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        self.rpc('initialize',{'protocolVersion':'2025-03-26','capabilities':{},
                              'clientInfo':{'name':'MontaVideo','version':'0.2.0'}})
        self.rpc('notifications/initialized',{},notify=True)

    def rpc(self,method,params,notify=False):
        self.counter+=1
        body={'jsonrpc':'2.0','method':method,'params':params}
        if not notify: body['id']=self.counter
        headers={'Content-Type':'application/json','Accept':'application/json, text/event-stream',
                 'Authorization':'Bearer '+self.token,'MCP-Protocol-Version':'2025-03-26'}
        if self.session: headers['Mcp-Session-Id']=self.session
        req=urllib.request.Request(self.url,json.dumps(body).encode(),headers)
        try:
            with self.opener.open(req,timeout=90) as response:
                self.session=response.headers.get('Mcp-Session-Id',self.session)
                raw=response.read().decode('utf-8')
        except urllib.error.HTTPError as e:
            raise RuntimeError(f'Drift HTTP {e.code}. Confira Agent access, endereço e token da sessão.') from None
        except urllib.error.URLError:
            raise RuntimeError('Não foi possível conectar. Abra o Drift e ative Settings > Agent access.') from None
        if notify and not raw.strip(): return {}
        if raw.lstrip().startswith('data:') or '\ndata:' in raw:
            responses=[]
            for line in raw.splitlines():
                if line.startswith('data:'):
                    try: responses.append(json.loads(line[5:].strip()))
                    except ValueError: pass
            obj=next((x for x in responses if x.get('id')==self.counter),{})
        else: obj=json.loads(raw) if raw.strip() else {}
        if 'error' in obj: raise RuntimeError(str(obj['error']))
        if not notify and obj.get('id')!=self.counter: raise RuntimeError('Resposta MCP sem o identificador esperado.')
        return obj.get('result',{})

    def call(self,name,args=None):
        r=self.rpc('tools/call',{'name':name,'arguments':args or {}})
        data=r.get('structuredContent')
        if data is None:
            for block in r.get('content',[]):
                if block.get('type')=='text':
                    try: data=json.loads(block['text']); break
                    except (ValueError,KeyError): pass
        if data is None: data=r
        if r.get('isError') or data.get('ok') is False or 'error' in data:
            raise RuntimeError(f'{name}: {data}')
        return data

REQUIRED=['import_media','add_track','place_clip','set_trim','set_duration','set_track',
          'set_project_setup','set_overlap','set_snap','set_ripple','save_project','move_clip','set_keyframe','add_transition']

def check(client):
    # toolbox retorna schemas completos. Confirmar nomes, não presumir versão.
    tools=client.call('toolbox',{'ops':REQUIRED})
    raw=json.dumps(tools)
    missing=[n for n in REQUIRED if '"'+n+'"' not in raw]
    if missing: raise RuntimeError('Esta versão não expõe os comandos: '+', '.join(missing))
    state=client.call('inspect',{'clips':True,'detail':True})
    return {'state':state,'message':'Conectado. Comandos necessários encontrados.'}

def number_close(value,expected,label):
    if value is None or abs(float(value)-expected)>.04:
        raise RuntimeError(f'Drift não aplicou {label}: esperado {expected}, recebido {value}. A montagem foi interrompida.')

def send(config,plan,catalog,client,log=print):
    validate_plan(plan,catalog)
    state=check(client)['state']
    if state.get('clips',0)!=0 or state.get('dirty',False):
        raise ValueError('Abra um projeto novo e vazio no Drift. O controlador não apaga o projeto aberto.')
    known={i['path']:i for i in catalog['items']}
    output=Path(config['output'])/('montagem_'+time.strftime('%Y%m%d_%H%M%S')+'.drift')
    if output.exists(): raise ValueError('Arquivo de saída já existe; aguarde um segundo e tente novamente.')
    journal=[]
    def call(name,args):
        result=client.call(name,args)
        journal.append({'tool':name,'args':args,'result':result})
        write_json(Path(config['output'])/'operacoes_drift.json',journal)
        return result
    # Importação acontece antes da timeline. Nunca substituir nem apagar conteúdo existente.
    assets={}
    for path in dict.fromkeys([plan['audio']]+[r['path'] for r in plan['rows']]):
        log('Importando: '+Path(path).name)
        r=call('import_media',{'paths':[str(Path(path).resolve())]})
        if r.get('missing') or not r.get('assets') or r['assets'][0].get('pending'):
            raise RuntimeError('Drift não concluiu a importação de '+path)
        assets[path]=r['assets'][0]['id']
    call('set_project_setup',{'width':1920,'height':1080,'fps':30})
    call('set_overlap',{'enabled':True})
    call('set_snap',{'enabled':False})
    call('set_ripple',{'enabled':False})
    # Images require Shape tracks in Drift; create all lanes before placing clips.
    call('add_track',{'type':'video'}); call('add_track',{'type':'shape'}); call('add_track',{'type':'audio'})
    lanes={'video':2,'image':1}
    # Mutar também as pistas vazias originais; áudio associado a B-roll nunca deve soar.
    s=client.call('inspect')
    for t in s.get('tracks',[]):
        if t['i']!=0: call('set_track',{'track':t['i'],'muted':True})
    voice=call('place_clip',{'asset':assets[plan['audio']],'at':0,'track':0})
    voice_trim=call('set_duration',{'clip':voice['id'],'duration':plan['duration']})
    number_close(voice_trim.get('dur'),plan['duration'],'duração da narração')
    placed=[]
    for index,row in enumerate(plan['rows']):
        item=known[row['path']]; at=row['at']; duration=row['duration']
        # Extender a ponta anterior para criar overlap sem mover nenhum início nem o áudio.
        overlap=0.
        if (index+1<len(plan['rows']) and plan['rows'][index+1].get('transition')=='crossfade'
                and known[plan['rows'][index+1]['path']]['kind']==item['kind']):
            available=(min(item['duration'],row.get('source_limit') if row.get('source_limit') is not None else item['duration'])-row['source_in']-duration) if item['kind']=='video' else 100.
            overlap=min(.3,duration/4,plan['rows'][index+1]['duration']/4,max(0,available))
            if overlap<.1: overlap=0.; log(f'Trecho {index+1}: sem margem para transição; mantido corte.')
        log(f'Montando {index+1}/{len(plan["rows"])}: {Path(row["path"]).name}')
        p=call('place_clip',{'asset':assets[row['path']],'at':at,'track':lanes[item['kind']]}); cid=p['id']
        if item['kind']=='video':
            trim=call('set_trim',{'clip':cid,'in':row['source_in'],'out':row['source_in']+duration+overlap})
            number_close(trim.get('in'),row['source_in'],'entrada')
        else: trim=call('set_duration',{'clip':cid,'duration':duration+overlap})
        number_close(trim.get('dur'),duration+overlap,'duração')
        moved=call('move_clip',{'clip':cid,'at':at})
        number_close(moved.get('placed',moved.get('start')),at,'posição')
        if row.get('zoom'):
            # Transform preserva a proporção inicial calculada pelo editor.
            w=p.get('w'); h=p.get('h'); x=p.get('x',0); y=p.get('y',0)
            if not w or not h: raise RuntimeError('Drift não retornou dimensões para aplicar zoom.')
            end=at+duration+overlap
            for prop,start,finish in [('width',w,w*1.06),('height',h,h*1.06),('x',x,x-w*.03),('y',y,y-h*.03)]:
                if row.get('zoom_direction')=='out':start,finish=finish,start
                call('set_keyframe',{'clip':cid,'prop':prop,'at':at,'value':start})
                call('set_keyframe',{'clip':cid,'prop':prop,'at':end,'value':finish})
        placed.append((cid,overlap))
    for i,(cid,overlap) in enumerate(placed[:-1]):
        if overlap:
            call('add_transition',{'clip':cid,'kind':'crossfade','duration':overlap})
    # Add text only after all media: a new text lane can shift track indexes.
    for row in plan['rows']:
        text=str(row.get('overlay','')).strip()
        if not text:continue
        at=max(row['at'],min(row['at']+row['duration'],float(row.get('overlay_at',row['at']))))
        duration=min(float(row.get('overlay_duration',3)),row['at']+row['duration']-at)
        if duration<.15:continue
        caption=call('add_text',{'text':text,'at':at})
        call('set_duration',{'clip':caption['id'],'duration':duration})
        call('set_text',{'clip':caption['id'],'style':{'fontWeight':700,'pixelSize':64,'align':'center','color':'#FFFFFF','outlineEnabled':True,'outlineColor':'#000000','outlineWidth':3,'animIn':{'kind':'slideUp','duration':min(.3,duration/3)},'animOut':{'kind':'fade','duration':min(.25,duration/3)}}})
        moved=call('move_clip',{'clip':caption['id'],'at':at});number_close(moved.get('placed',moved.get('start')),at,'posição do texto')
    call('save_project',{'path':str(output.resolve())})
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        s=client.call('inspect')
        if not s.get('dirty',True) and s.get('path') and Path(s['path']).resolve()==output.resolve() and output.is_file(): break
        time.sleep(.2)
    else: raise RuntimeError('Montagem enviada, mas o salvamento não foi confirmado. Salve manualmente no Drift.')
    number_close(s.get('dur'),plan['duration'],'duração final')
    log('Montagem salva: '+str(output))
    return {'path':str(output),'message':'Montagem editável salva. Revise no Drift e exporte pelo editor.'}
