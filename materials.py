"""Project context filters and cached physical scene preparation."""
from pathlib import Path
import hashlib,json,sys
import core

def allowed(cfg,item):
    return item.get('context_allowed',True)

def prepare(cfg,cat,job):
    items=[]
    for item in cat['items']:
        job.check()
        if item.get('origin') not in ('project','footage') or item['kind']!='video' or not item.get('selected',True) or not allowed(cfg,item):
            items.append(item);continue
        if item.get('original_source') or cfg.get('precut_footage' if item.get('origin')=='footage' else 'precut_project'):
            items.append(dict(item,precut=True,original_source=item.get('original_source',item['path'])));continue
        folder=Path(cfg.get('project_root',cfg['output']))/'04_Cortes'/('Broll' if item.get('origin')=='footage' else 'Projeto')/(Path(item['path']).stem+'_'+item['id'][:10])
        manifest=folder/'concluido.json';saved=core.read_json(manifest,{})
        paths=saved.get('paths',[]) if saved.get('source')==item['id'] else []
        if not paths or not all(Path(p).is_file() for p in paths):
            folder.mkdir(parents=True,exist_ok=True)
            job.log('Preparando cortes completos: '+Path(item['path']).name)
            staging=folder/'parcial';staging.mkdir(exist_ok=True)
            job.run([sys.executable,str(Path(__file__).with_name('split_worker.py')),item['path'],str(staging)],line=lambda s:job.log(s[-250:]),timeout=14400)
            generated=list(sorted(staging.glob('*.mp4')))
            for p in generated:p.replace(folder/p.name)
            paths=[str((folder/p.name).resolve()) for p in generated]
            if not paths:raise ValueError('O detector não gerou cenas: '+item['path'])
            core.write_json(manifest,{'source':item['id'],'paths':paths})
        else:job.log('Reutilizando cortes: '+Path(item['path']).name)
        import engine
        for path in paths:
            job.check();cached=folder/(Path(path).name+'.meta.json');info=core.read_json(cached)
            if not info:info=engine.probe(Path(path),job);core.write_json(cached,info)
            scene=dict(item,**{k:v for k,v in info.items() if k not in item})
            scene.update(info);scene.update(path=path,id=core.fingerprint(path),precut=True,original_source=item['path'])
            items.append(scene)
    result=dict(cat,items=items);core.write_json(Path(cfg['output'])/'catalogo.json',result);return result
