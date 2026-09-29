"""Visible Windows console; explicit rescan, no web job owns the detector."""
import os,sys,json,subprocess,hashlib
from pathlib import Path
import core
CUT_DIR='Cenas_Separadas_MontaVideo'

def sources(cfg):
    found=[];seen=set()
    for field,origin,flag in [('project','project','precut_project'),('footage','footage','precut_footage')]:
        if not cfg.get(field):continue
        root=Path(cfg[field]).resolve()
        if not root.is_dir():raise ValueError('Pasta inexistente: '+str(root))
        for p in sorted(root.rglob('*')):
            if not p.is_file() or p.suffix.lower() not in core.VIDEO|core.IMAGE:continue
            if any(x in p.parts for x in (CUT_DIR,'04_Cortes','07_Resultados','runtime')):continue
            if p.resolve() in seen:continue
            seen.add(p.resolve());found.append({'path':str(p.resolve()),'root':str(root),'origin':origin,'precut':bool(cfg.get(flag)),'kind':'image' if p.suffix.lower() in core.IMAGE else 'video'})
    return found

def destination(source):
    p=Path(source)
    # Distinguish equal stems/extensions and invalidate when the source changes.
    return p.parent/CUT_DIR/(p.stem+'_'+core.fingerprint(p)[:12])

def completed_paths(cfg,entry):
    p=Path(entry['path']);fp=core.fingerprint(p)
    folders=[destination(p),Path(cfg['project_root'])/'04_Cortes'/('Broll' if entry['origin']=='footage' else 'Projeto')/(p.stem+'_'+fp[:10])]
    for folder in folders:
        saved=core.read_json(folder/'concluido.json',{})
        if saved.get('source')==fp and saved.get('paths') and all(Path(x).is_file() for x in saved['paths']):return saved['paths']
    return []

def write_batch(folder,manifest):
    folder=Path(folder);bat=folder/'RECORTAR_MONTAVIDEO.bat'
    # Use environment variables for executable/manifest paths, never interpolate media into CMD code.
    # %% escapes literal percent; delayed expansion stays OFF for exclamation marks.
    def value(s):return str(s).replace('%','%%')
    body='\r\n'.join(['@echo off','setlocal DisableDelayedExpansion','chcp 65001 >nul',
        'title MontaVideo - Recorte de cenas',
        'set "MV_PY='+value(sys.executable)+'"',
        'set "MV_RUN='+value(Path(__file__).with_name('cut_console.py').resolve())+'"',
        'set "MV_MANIFEST='+value(Path(manifest).resolve())+'"',
        '"%MV_PY%" "%MV_RUN%" "%MV_MANIFEST%"',
        'if errorlevel 1 (echo Houve falhas. Leia o resumo acima. & pause & exit /b 1)','echo Concluido. Volte ao MontaVideo e clique Atualizar cenas.','exit /b 0',''])
    bat.write_bytes(body.encode('utf-8'));return bat

def launch(cfg):
    if sys.platform!='win32':raise ValueError('Abrir CMD está disponível no Windows.')
    entries=[s for s in sources(cfg) if s['kind']=='video' and not s['precut'] and not completed_paths(cfg,s)]
    if not entries:raise ValueError('Nenhum vídeo pendente de recorte. Clique Atualizar cenas para ler os cortes existentes.')
    folder=Path(cfg['project_root'])/'04_Cortes';folder.mkdir(parents=True,exist_ok=True)
    manifest=folder/'pedido_recortes.json';core.write_json(manifest,{'sources':entries})
    bat=write_batch(folder,manifest)
    # Also leave a standalone BAT in each source folder, as requested.
    groups={}
    for entry in entries:groups.setdefault(str(Path(entry['path']).parent),[]).append(entry)
    for parent,group in groups.items():
        target=Path(parent)/'pedido_recortes_montavideo.json';core.write_json(target,{'sources':group});write_batch(parent,target)
    env=os.environ.copy();env['MV_LAUNCH_BAT']=str(bat)
    command=subprocess.list2cmdline([os.environ.get('COMSPEC','cmd.exe')])+' /d /s /c ""%MV_LAUNCH_BAT%""'
    subprocess.Popen(command,env=env,creationflags=subprocess.CREATE_NEW_CONSOLE,close_fds=True)
    return {'message':'CMD aberto. Aguarde o resumo nessa janela. Depois clique Atualizar cenas; não precisa escolher as pastas novamente.'}

def refresh(cfg,job):
    import engine,workflow
    context=workflow.require_context(cfg);items=[];pending=[];errors=[];db=engine.CatalogDB()
    entries=sources(cfg)
    import connections
    classified=workflow.classify_sources(entries,context,cfg,connections.load().get('groq_key',''),job)
    try:
        for entry in entries:
            job.check();p=Path(entry['path']);meta=core.load_meta(p,Path(entry['root']),entry['origin']=='footage')
            base=dict(meta,origin=entry['origin'],relative_path=str(p.relative_to(entry['root'])),path=str(p),kind=entry['kind'])
            base=workflow.classify(base,context)
            if str(p) in classified:
                base.update(classified[str(p)]);base['tags']+=base.pop('semantic_tags',[])
            if entry['kind']=='image' or entry['precut']:
                paths=[str(p)]
            else:
                paths=completed_paths(cfg,entry)
                if not paths or not all(Path(x).is_file() for x in paths):
                    pending.append(str(p));continue
            for path in paths:
                job.check();fp=core.fingerprint(path);info=db.get('meta:'+fp)
                if not info:
                    job.log('Lendo cena: '+Path(path).name);info=engine.probe(Path(path),job);db.put('meta:'+fp,info)
                bg=entry['kind']=='image' and any(t in core.norm(p.stem).split() for t in ('bg','background','fundo'))
                item=dict(base,**info,id=fp,path=path,original_source=str(p),precut=entry['kind']=='video',role='background' if bg else 'media',selected=base['context_allowed'] and not bg,reviewed=False)
                items.append(item)
        old=core.read_json(Path(cfg['output'])/'catalogo.json',{})
        known={i['path'] for i in items}
        items += [i for i in old.get('items',[]) if i.get('origin') in ('online','stock','ai_local','imported','composite') and i['path'] not in known and Path(i['path']).is_file()]
        cat={'items':items,'pending_sources':pending,'errors':errors,'prepared_signature':workflow.signature(cfg),
             'roots':[str(Path(cfg[k]).resolve()) for k in ('project','footage') if cfg.get(k)],
             'summary':{'project_scenes':sum(i['kind']=='video' and i.get('origin')=='project' and i.get('context_allowed',True) for i in items),
                        'broll_scenes':sum(i['kind']=='video' and i.get('origin') in ('footage','stock') and i.get('context_allowed',True) for i in items),
                        'excluded':sum(not i.get('context_allowed',True) for i in items)}}
        core.write_json(Path(cfg['output'])/'catalogo.json',cat);return cat
    finally:db.close()
