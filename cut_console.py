"""Independent console process. Inherits stdout: PySceneDetect progress is live."""
import json,sys,os,shutil,subprocess,time
from pathlib import Path
import core
from external_cuts import destination

def run(manifest):
    request=core.read_json(manifest);failures=[];done=0
    entries=request['sources']
    # Prefer the same global CLI the user already runs successfully in their BAT.
    system_cli=shutil.which('scenedetect')
    command=[system_cli] if system_cli else [sys.executable,'-m','scenedetect']
    # Keep the user's working BAT environment. Only supply bundled FFmpeg if absent.
    env=os.environ.copy();env['PYTHONUNBUFFERED']='1'
    binary=shutil.which('ffmpeg')
    if not binary:
        tools=Path(__file__).parent/'runtime'/'ffmpeg_tools';tools.mkdir(parents=True,exist_ok=True)
        binary=tools/('ffmpeg.exe' if os.name=='nt' else 'ffmpeg')
        if not binary.exists():shutil.copy2(core.ffmpeg(),binary)
        env['PATH']=str(tools)+os.pathsep+env.get('PATH','')
    print('Detector: '+str(command)+'\nFFmpeg: '+str(binary),flush=True)
    print('Detecting scenes = analise. Splitting video = gravacao dos cortes. Cada etapa tem seu progresso.',flush=True)
    for n,entry in enumerate(entries,1):
        source=Path(entry['path']);folder=destination(source);folder.mkdir(parents=True,exist_ok=True)
        saved=core.read_json(folder/'concluido.json',{})
        if saved.get('source')==core.fingerprint(source) and saved.get('paths') and all(Path(p).is_file() for p in saved['paths']):
            print(f'[{n}/{len(entries)}] Ja recortado: {source.name}',flush=True);done+=1;continue
        lock=folder/'executando.lock'
        try:
            with lock.open('x') as f:f.write(str(os.getpid()))
        except FileExistsError:
            failures.append(str(source));print('Recorte marcado em execucao. Se o CMD anterior foi encerrado a forca, remova apenas '+str(lock),flush=True);continue
        try:
            staging=folder/('Cenas_'+str(time.time_ns()));staging.mkdir()
            print(f'\n[{n}/{len(entries)}] {source}\nCORTES SALVOS DIRETAMENTE EM: {staging}',flush=True)
            input_path=source
            if '%' in str(source):
                input_path=folder.parent/('entrada_'+core.fingerprint(source)+'.mp4')
                if not input_path.exists():os.link(source,input_path)
            args=command+['-i',str(input_path),'-o',str(staging),'detect-content','split-video']
            print('Comando: '+subprocess.list2cmdline(args),flush=True)
            started=time.monotonic()
            code=subprocess.call(args,env=env,cwd=str(source.parent))
            generated=sorted(staging.glob('*.mp4'))
            if code or not generated:raise RuntimeError('Detector terminou sem cenas validas. Codigo '+str(code))
            # Files stay where FFmpeg writes them, visible throughout splitting.
            paths=[str(p.resolve()) for p in generated]
            print(f'{len(paths)} cenas salvas. Tempo deste video: {time.monotonic()-started:.1f}s.',flush=True)
            core.write_json(folder/'concluido.json',{'source':core.fingerprint(source),'paths':paths,'original_source':str(source)})
            done+=1
        except Exception as e:
            failures.append(str(source));print('ERRO: '+str(e),flush=True)
        finally:
            (folder.parent/('entrada_'+core.fingerprint(source)+'.mp4')).unlink(missing_ok=True)
            lock.unlink(missing_ok=True)
    report={'completed':done,'total':len(entries),'failures':failures};core.write_json(Path(manifest).with_name('resumo_recortes.json'),report)
    print(f'\nFINALIZADO: {done}/{len(entries)} videos; {len(failures)} falhas. Volte e clique ATUALIZAR CENAS.',flush=True)
    return 1 if failures else 0
if __name__=='__main__':
    try:sys.exit(run(sys.argv[1]))
    except Exception as e:print('ERRO: '+str(e),flush=True);sys.exit(1)
