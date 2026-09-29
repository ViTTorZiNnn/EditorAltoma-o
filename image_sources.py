"""Real image files with origin records; no text-slide fallback."""
from pathlib import Path
import hashlib,io,json,ipaddress,socket,urllib.request,urllib.parse,sys,re
from PIL import Image
import core,workflow,visuals

def public_url(url):
    u=urllib.parse.urlsplit(url)
    if u.scheme not in ('https','http') or not u.hostname or u.username or u.password:raise ValueError('Use um endereço público http/https.')
    for row in socket.getaddrinfo(u.hostname,u.port or (443 if u.scheme=='https' else 80)):
        if not ipaddress.ip_address(row[4][0]).is_global:raise ValueError('Endereço privado não permitido na busca online.')
    return url
class Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        return super().redirect_request(req,fp,code,msg,headers,public_url(newurl))
def fetch(url):
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),Redirect())
    req=urllib.request.Request(public_url(url),headers={'User-Agent':'Mozilla/5.0 MontaVideo/0.6'})
    with opener.open(req,timeout=20) as r:
        raw=r.read(25*1024*1024+1)
        if len(raw)>25*1024*1024:raise ValueError('Imagem acima de 25 MB.')
        return raw,r.url

def store_image(folder,raw,query,url):
    with Image.open(io.BytesIO(raw)) as im:
        if min(im.size)<600 or max(im.size)<1000:raise ValueError('Resolução insuficiente; miniatura ignorada.')
        im.load();ph=str(visuals.dhash(im));width,height=im.size
        ext={'JPEG':'.jpg','PNG':'.png','WEBP':'.webp'}.get(im.format)
        if not ext:raise ValueError('Formato de imagem não suportado.')
    slug=core.norm(query).replace(' ','-')[:65] or 'imagem';digest=hashlib.sha256(raw).hexdigest()
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);path=folder/(slug+'_'+digest[:12]+ext)
    if not path.exists():path.write_bytes(raw)
    record={'path':str(path.resolve()),'query':query,'url':url,'sha256':digest,'dhash':ph,'width':width,'height':height,'license':'Verificar na fonte original'}
    core.write_json(Path(str(path)+'.fonte.json'),record);return record

def gallery(cfg,cat):return [i for i in cat['items'] if i.get('origin') in ('online','ai_local','imported') and i['kind']=='image']
def import_records(cfg,cat,records,job):
    for rec in records:
        job.check()
        if any(i.get('download_sha256')==rec['sha256'] or (i.get('dhash') and (int(i['dhash'])^int(rec['dhash'])).bit_count()<=3) for i in cat['items']):continue
        cat=workflow.add_asset(cfg,cat,rec['path'],job,'online',rec['query'])
        item=next(i for i in cat['items'] if i['path']==rec['path']);item.update(download_sha256=rec['sha256'],dhash=rec['dhash'],source=rec,reviewed=False)
    core.write_json(Path(cfg['output'])/'catalogo.json',cat);return cat

def search(cfg,cat,queries,provider,job):
    limit=max(1,min(40,int(cfg.get('image_count',20))));queries=[str(q).strip()[:250] for q in queries if str(q).strip()][:5]
    if not queries:raise ValueError('Confira as buscas sugeridas após analisar o roteiro.')
    folder=Path(cfg['project_root'])/'05_Imagens';records=[];failures=[]
    for n,query in enumerate(queries):
        job.check();job.log(f'Buscando imagens {n+1}/{len(queries)}: {query}')
        count=max(1,(limit-len(records))//max(1,len(queries)-n))
        if provider=='google':
            req=Path(cfg['output'])/'pedido_imagens.json';result=Path(cfg['output'])/'resposta_imagens.json'
            result.unlink(missing_ok=True);core.write_json(req,{'query':query,'folder':str(folder),'count':count,'result':str(result)})
            try:job.run([sys.executable,str(Path(__file__).with_name('google_worker.py')),str(req)],timeout=150)
            except Exception as e:job.check();failures.append(query+': busca não concluiu. '+str(e)[:160])
            records+=core.read_json(result,[])
        elif provider=='commons':
            try:
                for entry in visuals.search_images(query)[:count]:
                    job.check();raw,url=fetch(entry['url']);rec=store_image(folder,raw,query,url);rec.update(page=entry['page'],artist=entry['artist'],license=entry['license']);core.write_json(Path(rec['path']+'.fonte.json'),rec);records.append(rec)
            except Exception as e:job.check();failures.append(query+': '+str(e)[:160])
        else:raise ValueError('Fonte de imagens inválida.')
    cat=import_records(cfg,cat,records,job)
    report={'provider':provider,'downloaded':len(records),'folder':str(folder),'warnings':failures}
    if not records:report['warnings'].append('Nenhuma foto baixada. O Google pode bloquear a busca automática. Use Abrir Google e importar o arquivo ou seu link direto; não foram criados slides.')
    core.write_json(Path(cfg['output'])/'busca_imagens.json',report)
    return cat,report
