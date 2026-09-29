import json,sys
from pathlib import Path
def emit(message,percent=None):print(json.dumps({'message':message,'percent':percent}),flush=True)
if __name__=='__main__':
    try:
        req=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
        from faster_whisper import WhisperModel
        emit('Carregando modelo. O primeiro uso pode baixar arquivos.')
        engine=WhisperModel(req['model'],device=req['device'],compute_type='float16' if req['device']=='cuda' else 'int8',download_root=req['models'],cpu_threads=6)
        segs,_=engine.transcribe(req['audio'],language=None if req['language']=='auto' else req['language'],word_timestamps=True,vad_filter=True,beam_size=3)
        cues=[]
        for seg in segs:
            cues.append({'start':seg.start,'end':seg.end,'text':seg.text.strip(),'words':[{'start':w.start,'end':w.end,'text':w.word} for w in (seg.words or [])]})
            emit(f'Transcrevendo: {seg.end:.0f} de {req["duration"]:.0f} segundos',min(100,seg.end/req['duration']*100))
        if not cues:raise ValueError('Nenhuma fala detectada.')
        Path(req['target']).write_text(json.dumps(cues,ensure_ascii=False),encoding='utf-8')
    except Exception as e:emit(str(e));sys.exit(1)
