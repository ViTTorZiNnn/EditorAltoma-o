import unittest,json,tempfile,wave
from pathlib import Path
from unittest.mock import patch
import narration,core
class VoiceTests(unittest.TestCase):
 def test_no_voice_never_calls_service(self):
  with patch.object(narration,'request') as req:
   with self.assertRaisesRegex(ValueError,'Escolha uma voz'):narration.prepare_voice({'voice_id':''},None)
   req.assert_not_called()
 def test_archetype_materializes_then_checks_reference(self):
  calls=[]
  def request(cfg,path,data=None,timeout=30):
   calls.append(path)
   if path.endswith('/use'):return b'{"profile_id":"fixed"}'
   if path.endswith('/audio'):return b'RIFF'+b'x'*50
   return b'{"id":"fixed","name":"Documentarian","ref_audio_path":"fixed.wav"}'
  with patch.object(narration,'request',side_effect=request):v=narration.resolve_voice({'voice_id':'archetype:doc'})
  self.assertEqual(v['id'],'fixed');self.assertEqual(calls,['/archetypes/doc/use','/profiles/fixed/audio','/profiles/fixed'])
 def test_missing_reference_rejected(self):
  with patch.object(narration,'request',side_effect=[b'x'*50,b'{"name":"unstable"}']):
   with self.assertRaisesRegex(ValueError,'referência persistente'):narration.resolve_voice({'voice_id':'unstable'})
 def test_all_parts_same_profile_seed_and_old_cache_not_reused(self):
  payloads=[]
  class Job:
   def check(self):pass
   def log(self,*a):pass
   def run(self,args,**kw):
    if 'voice_worker.py' in args[1]:
     req=core.read_json(args[2]);payloads.append(req['payload']);target=Path(req['path'])
     with wave.open(str(target),'wb') as w:w.setparams((1,2,24000,0,'NONE','not compressed'));w.writeframes(b'\0\0'*240)
     target.with_name(target.stem+'_pcm.wav').write_bytes(target.read_bytes())
  with tempfile.TemporaryDirectory() as tmp,patch.object(narration,'prepare_voice',return_value={'id':'one','name':'One','seed':42,'reference_hash':'abc'}):
   cfg={'project_root':tmp,'script':'Texto de prueba. '*150,'voice_id':'one'}
   audio=narration.generate(cfg,Job())
   self.assertGreater(len(payloads),1);self.assertTrue(audio.exists())
   self.assertEqual({p['profile_id'] for p in payloads},{'one'});self.assertEqual({p['seed'] for p in payloads},{'42'})
   self.assertTrue(audio.with_suffix('.voz.json').exists())
if __name__=='__main__':unittest.main()
