import unittest,tempfile,sys,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import workflow,core,connections,engine
from jobs import Job
class WorkflowTests(unittest.TestCase):
 def test_project_folders_and_no_implicit_old_plan(self):
  with tempfile.TemporaryDirectory() as d,patch.object(workflow,'HOME',Path(d)/'settings'):
   a=workflow.create(d,'Teste',{'footage':'','audio':'','srt':'','subject':''})
   b=workflow.create(d,'Teste',{'footage':'','audio':'','srt':'','subject':''})
   self.assertNotEqual(a['project_root'],b['project_root'])
   self.assertTrue((Path(a['project_root'])/'06_Imagens_IA').is_dir())
   self.assertIsNone(workflow.valid_state(a)['plan'])
 def test_context_survives_cut_option_but_plan_does_not(self):
  cfg={'project':'a','footage':'b','subject':'Mexico','audio':'','srt':''};other=dict(cfg,precut_footage=True)
  self.assertEqual(workflow.context_signature(cfg),workflow.context_signature(other))
  self.assertNotEqual(workflow.signature(cfg),workflow.signature(other))
 def test_persisted_keys_preserve_blank_updates(self):
  with tempfile.TemporaryDirectory() as d,patch.object(connections,'HOME',Path(d)),patch.object(connections,'FILE',Path(d)/'keys'),patch.object(connections,'_protect',side_effect=lambda raw,decrypt=False:raw[::-1]):
   connections.save({'token':'example-token','groq_key':'example-key','url':'http://127.0.0.1:4731/mcp'})
   connections.save({'token':'','groq_key':''})
   self.assertEqual(connections.load()['token'],'example-token')
   self.assertNotIn(b'example-token',(Path(d)/'keys').read_bytes())
 def test_source_balancing_not_scene_count(self):
  with tempfile.TemporaryDirectory() as d,patch.object(engine,'DATA',Path(d)/'cache'):
   audio=Path(d)/'audio';audio.write_bytes(b'a');items=[]
   for source,n in [('A',30),('B',3),('C',3)]:
    for i in range(n):
     p=Path(d)/f'{source}-{i}.mp4';p.write_bytes(b'x')
     items.append({'path':str(p),'id':core.fingerprint(p),'kind':'video','duration':10,'tags':['obra'],'origin':'project','precut':True,'original_source':source,'selected':True})
   cfg={'audio':str(audio),'output':d,'subject':'obra','shot':5,'planner':'local','variation_seed':5}
   with patch.object(engine,'probe',return_value={'duration':45}):plan=engine.make_plan(cfg,{'items':items},[{'start':0,'end':45,'text':'obra'}],Job())
   counts={s:0 for s in ['A','B','C']};known={i['path']:i['original_source'] for i in items}
   for r in plan['rows']:
    if r['path']:counts[known[r['path']]]+=1
   self.assertLessEqual(counts['A'],max(counts['B'],counts['C'])+1)
