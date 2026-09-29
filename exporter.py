from pathlib import Path
import time
import core,engine
from jobs import Cancelled

def export(cfg,client,job):
    record=core.read_json(Path(cfg['output'])/'ultimo_projeto_drift.json')
    if not record:raise ValueError('Envie a montagem ao Drift primeiro.')
    state=client.call('inspect')
    if not state.get('path') or Path(state['path']).resolve()!=Path(record['path']).resolve():
        raise ValueError('O Drift não está com a montagem enviada aberta. Abra o projeto correto antes de exportar.')
    if not state.get('clips'):raise ValueError('A timeline está vazia.')
    if state.get('export',{}).get('active'):raise ValueError('O Drift já está exportando. Aguarde a exportação atual.')
    options=client.call('list_export_options')
    video=next((x['id'] for x in options.get('video',[]) if x.get('id')=='h264'),None)
    audio=next((x['id'] for x in options.get('audio',[]) if x.get('id')=='aac'),None)
    if not video or not audio:raise ValueError('H.264/AAC não disponíveis nesta instalação. Use Exportar dentro do Drift para escolher os codecs.')
    path=Path(cfg['output'])/('video_'+time.strftime('%Y%m%d_%H%M%S')+'.mp4')
    if path.exists():raise ValueError('Arquivo de saída já existe. Tente novamente em um segundo.')
    job.log('Iniciando exportação pelo Drift…')
    result=client.call('export_video',{'path':str(path.resolve()),'height':1080,'fps':30,'video':video,'audio':audio,'rate':'crf','crf':20,'audio_bitrate':192,'audio_only':False,'gif':False,'work_area':False,'in':0,'out':state['dur']})
    actual=Path(result.get('path',str(path)))
    try:
        until=time.monotonic()+7200
        while True:
            job.check();status=client.call('export_status')
            if not status.get('busy'):break
            job.log('Exportando pelo Drift…',max(0,min(100,float(status.get('progress',0))*100)))
            if time.monotonic()>until:raise TimeoutError('Exportação excedeu duas horas.')
            job.event.wait(.5)
    except (Cancelled,TimeoutError):
        client.call('cancel_export');raise
    if not actual.is_file() or actual.stat().st_size<1024:raise ValueError('Drift terminou sem produzir um arquivo válido. Confira o erro no editor.')
    info=engine.probe(actual,job)
    if abs(info['duration']-float(state['dur']))>1:raise ValueError('A duração exportada difere da timeline. Confira o arquivo antes de usar.')
    return {'path':str(actual),'message':'Vídeo exportado e duração verificada: '+str(actual)}
