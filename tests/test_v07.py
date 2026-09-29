import unittest,tempfile,json,wave,math,struct,threading,urllib.parse,sys,subprocess
from pathlib import Path
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core,engine,narration,external_cuts,workflow,connections,providers
from jobs import Job

class Tests07(unittest.TestCase):
 def test_pause_trim_real_audio_and_original_preserved(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);source=root/'original.wav'
   with wave.open(str(source),'wb') as w:
    w.setparams((1,2,24000,0,'NONE','not compressed'))
    for seconds,amplitude in [(1,.4),(1,0),(1,.4)]:
     w.writeframes(b''.join(struct.pack('<h',int(amplitude*32767*math.sin(2*math.pi*440*i/24000))) for i in range(int(seconds*24000))))
   before=source.read_bytes();cfg={'project_root':tmp,'output':str(root/'out'),'pause_keep':.12,'silence_min':.25,'silence_db':-45}
   result,report=narration.trim(cfg,source,Job(lambda *a:None))
   self.assertEqual(before,source.read_bytes());self.assertAlmostEqual(report['final_seconds'],2.12,delta=.04)
   self.assertGreater(len(report['intervals']),1);self.assertTrue(result.is_file())
   self.assertEqual(narration.trim(cfg,source,Job(lambda *a:None))[0],result)
 def test_word_timing_sidecar_validated_against_audio(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);audio=root/'final.wav';audio.write_bytes(b'test');out=root/'out';out.mkdir()
   cfg={'project_root':tmp,'output':str(out),'audio':str(audio),'srt':'','model':'small','language':'es'}
   cues=[{'start':0,'end':1,'text':'Hola mundo','words':[{'start':0,'end':.5,'text':'Hola'},{'start':.5,'end':1,'text':'mundo'}]}]
   with patch.object(engine,'transcript',return_value=cues):srt=narration.synchronize(cfg,Job(lambda *a:None))
   cfg['srt']=str(srt);self.assertEqual(engine.transcript(cfg,Job(lambda *a:None)),cues)
   self.assertIn('00:00:00,000 --> 00:00:01,000',srt.read_text())
 def test_voices_generate_through_real_http_transport_cache(self):
  import io
  stream=io.BytesIO()
  with wave.open(stream,'wb') as w:w.setparams((1,2,24000,0,'NONE','not compressed'));w.writeframes(b'\0\0'*2400)
  calls=[]
  class Handler(BaseHTTPRequestHandler):
   def log_message(self,*a):pass
   def do_GET(self):
    raw=(stream.getvalue() if self.path=='/profiles/voice-1/audio' else json.dumps([{'id':'voice-1','name':'Narrador'}] if self.path=='/profiles' else {'id':'voice-1','name':'Narrador','ref_audio_path':'reference.wav'} if self.path=='/profiles/voice-1' else {'items':[],'total':0} if self.path.startswith('/archetypes') else {'status':'ok'}).encode());self.send_response(200);self.end_headers();self.wfile.write(raw)
   def do_POST(self):
    data=urllib.parse.parse_qs(self.rfile.read(int(self.headers['Content-Length'])).decode());calls.append((self.path,data));self.send_response(200);self.end_headers();self.wfile.write(stream.getvalue())
  server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
  try:
   with tempfile.TemporaryDirectory() as tmp:
    cfg={'project_root':tmp,'voice_url':f'http://127.0.0.1:{server.server_port}','voice_id':'voice-1','script':'Una narración sobre México.','language':'es','voice_speed':1}
    self.assertEqual(narration.voices(cfg)['voices'][0]['id'],'voice-1')
    target=narration.generate(cfg,Job(lambda *a:None));self.assertTrue(target.is_file());narration.generate(cfg,Job(lambda *a:None))
    self.assertEqual(len(calls),1);self.assertEqual(calls[0][0],'/generate');self.assertEqual(calls[0][1]['profile_id'],['voice-1'])
  finally:server.shutdown();server.server_close()
 def test_cuts_launch_does_not_start_web_job_or_scan_frames(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);src=root/'videos';src.mkdir();(src/'obra ! & % teste.mp4').write_bytes(b'test');cfg={'project':str(src),'project_root':str(root),'footage':''}
   with patch.object(external_cuts.sys,'platform','win32'),patch.object(external_cuts.subprocess,'CREATE_NEW_CONSOLE',16,create=True),patch.object(external_cuts.subprocess,'Popen') as pop:
    result=external_cuts.launch(cfg)
   self.assertIn('CMD aberto',result['message']);self.assertEqual(pop.call_args.kwargs['creationflags'],16)
   self.assertTrue((src/'RECORTAR_MONTAVIDEO.bat').is_file());text=(src/'RECORTAR_MONTAVIDEO.bat').read_text();self.assertNotIn('obra !',text)
 def test_pending_original_never_becomes_a_scene(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);src=root/'videos';src.mkdir();source=src/'obra.mp4';source.write_bytes(b'test');out=root/'out';out.mkdir()
   cfg={'project':str(src),'footage':'','project_root':tmp,'output':str(out),'audio':'','srt':'','subject':'México','planner':'local'}
   context={'confirmed':True,'signature':workflow.context_signature(cfg),'countries':['México'],'primary_country':'México','people':[]};core.write_json(out/'contexto.json',context)
   with patch.object(connections,'load',return_value={}):cat=external_cuts.refresh(cfg,Job(lambda *a:None))
   self.assertEqual(cat['items'],[]);self.assertEqual(cat['pending_sources'],[str(source)])
 def test_first_shot_video_even_when_image_scores_higher(self):
  with tempfile.TemporaryDirectory() as tmp:
   cfg={'audio':str(Path(tmp)/'audio.wav'),'output':tmp,'shot':5,'scene_mode':'off','subject':'obra','variation_seed':9};Path(cfg['audio']).write_bytes(b'a')
   video={'id':'v','path':'v.mp4','kind':'video','origin':'project','duration':90,'tags':['obra'],'precut':True}
   image={'id':'i','path':'i.jpg','kind':'image','origin':'online','duration':0,'tags':['obra'],'reviewed':True}
   with patch.object(engine,'probe',return_value={'duration':30}):plan=engine.make_plan(cfg,{'items':[image,video]},[{'start':0,'end':30,'text':'obra'}],Job(lambda *a:None))
   self.assertEqual(plan['rows'][0]['path'],'v.mp4');self.assertGreater(len({r['duration'] for r in plan['rows']}),1)
 def test_synthesis_chunks_do_not_drop_words(self):
  text=('Una frase para narrar con precisión. '*300).strip();parts=narration.chunks(text)
  self.assertEqual(' '.join(parts),text);self.assertTrue(all(len(p)<=900 for p in parts))
if __name__=='__main__':unittest.main()
