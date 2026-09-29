import subprocess,threading,queue,time,os,signal
class Cancelled(Exception): pass
class Job:
    def __init__(self,report=lambda *a:None):self.event=threading.Event();self.report=report
    def check(self):
        if self.event.is_set():raise Cancelled('Cancelado. Resultados já concluídos foram preservados.')
    def log(self,message,percent=None):self.check();self.report(str(message),percent)
    def run(self,cmd,line=None,timeout=3600):
        self.check();q=queue.Queue();tail=[]
        p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),start_new_session=os.name!='nt')
        def reader():
            for raw in iter(p.stdout.readline,b''):q.put(raw.decode('utf-8','replace').strip())
            q.put(None)
        t=threading.Thread(target=reader,daemon=True);t.start();started=time.monotonic()
        try:
            while True:
                self.check()
                if time.monotonic()-started>timeout:raise TimeoutError('Processamento excedeu o limite de tempo.')
                try:s=q.get(timeout=.15)
                except queue.Empty:continue
                if s is None:break
                tail=(tail+[s])[-40:]
                if line:line(s)
            code=p.wait(timeout=10);self.check()
            if code:raise RuntimeError('Processo terminou com código '+str(code)+': '+'\n'.join(tail)[-1200:])
            return '\n'.join(tail)
        finally:
            if p.poll() is None:
                if os.name=='nt':
                    subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                else:
                    try:os.killpg(p.pid,signal.SIGTERM)
                    except ProcessLookupError:pass
                try:p.wait(timeout=3)
                except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)
            t.join(timeout=2);p.stdout.close()
