import sys,tempfile,threading,time,json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import engine,core,visuals
from jobs import Job,Cancelled

class V2Tests(TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.old_data=engine.DATA;engine.DATA=self.root/'data'
        self.voice=self.root/'voice.wav';self.voice.touch()
        self.video=self.root/'obra.mp4';self.video.touch()
        self.item={'path':str(self.video),'id':'a','kind':'video','duration':15,'tags':['obra','trilhos'],'entity':'','aliases':[], 'origin':'project','role':'media','selected':True,'precut':True}
        self.cfg={'audio':str(self.voice),'output':str(self.root/'out'),'shot':5,'planner':'local','scene_mode':'off','subject':'','model':'small','language':'es','device':'auto'}
    def tearDown(self):engine.DATA=self.old_data;self.tmp.cleanup()
    def test_cancel_real_child(self):
        job=Job();timer=threading.Timer(.2,job.event.set);timer.start();start=time.monotonic()
        with self.assertRaises(Cancelled):job.run([sys.executable,'-c','import time;time.sleep(30)'])
        timer.join();self.assertLess(time.monotonic()-start,4)
    def test_no_overlap_reuse(self):
        opt=engine.choose_range(self.item,[{'start':0,'end':10}],5,{'a':[(0,4),(8,10)]})
        self.assertEqual(opt,(4.,4,8))
    def test_manual_ranges_preserved(self):
        a=dict(self.item,manual_ranges=True,ranges=[{'start':4,'end':8}]);db=engine.CatalogDB()
        try:self.assertEqual(engine.scene_ranges(a,'full',db,Job()),a['ranges'])
        finally:db.close()
    def test_cache_across_jobs(self):
        d=engine.CatalogDB();d.put('test',{'a':1});d.close();d=engine.CatalogDB()
        try:self.assertEqual(d.get('test'),{'a':1})
        finally:d.close()
    def test_plan_splits_short_scenes(self):
        item=dict(self.item,precut=False,manual_ranges=True,ranges=[{'start':0,'end':3},{'start':3,'end':6},{'start':6,'end':10}])
        with patch('engine.probe',return_value={'duration':10}):
            p=engine.make_plan(self.cfg,{'items':[item]},[{'start':0,'end':10,'text':'Obra de trilhos'}],Job())
        self.assertEqual(sum(r['duration'] for r in p['rows']),10)
        self.assertTrue(all(r['source_in']+r['duration']<=r['source_limit']+.001 for r in p['rows']))
        for r in p['rows']:r['approved']=True
        core.validate_plan(p,{'items':[item]})
    def test_excluded_and_background_never_selected(self):
        for item in [dict(self.item,selected=False),dict(self.item,role='background')]:
            with patch('engine.probe',return_value={'duration':5}):
                with self.assertRaises(ValueError):engine.make_plan(self.cfg,{'items':[item]},[{'start':0,'end':5,'text':'obra'}],Job())
    def test_bad_ai_ids_and_counts(self):
        for raw in [{'segments':[]},{'segments':[{'id':2,'tags':[]}]},{'segments':[{'id':0,'tags':'bad'}]}]:
            with self.assertRaises(ValueError):engine.validate_ai(raw,[{}])
    def test_gpu_failure_retries_cpu(self):
        calls=[]
        class FakeJob(Job):
            def run(s,cmd,**kw):
                req=core.read_json(cmd[-1]);calls.append(req['device'])
                if req['device']=='cuda':raise RuntimeError('CUDA DLL not found')
                Path(req['target']).write_text('[{"start":0,"end":5,"text":"hola"}]')
        with patch('engine.probe',return_value={'duration':5}):
            cues=engine.transcript(self.cfg,FakeJob())
        self.assertEqual(calls,['cuda','cpu']);self.assertEqual(cues[0]['text'],'hola')
    def test_cached_transcription_no_worker(self):
        cache=engine.DATA/'transcricoes';cache.mkdir(parents=True)
        key=core.fingerprint(self.voice)+'_small_es';core.write_json(cache/(key+'.json'),[{'start':0,'end':1,'text':'cached'}])
        j=Job();j.run=lambda *a,**k:self.fail('Worker should not run')
        self.assertEqual(engine.transcript(self.cfg,j)[0]['text'],'cached')
    def test_card_fills_missing_and_validates(self):
        p={'audio':str(self.voice),'duration':5,'rows':[{'at':0,'duration':5,'text':'La obra ferroviaria avanza.','path':'','source_in':0,'transition':'none','zoom':False,'approved':False,'reason':''}]}
        result=visuals.make_cards(self.cfg,p,{'items':[]},Job())
        self.assertTrue(Path(p['rows'][0]['path']).is_file());p['rows'][0]['approved']=True
        self.assertTrue(core.validate_plan(p,result['catalog']))
    def test_image_search_filters_low_resolution_duplicates(self):
        def page(id,w,sha):return {'pageid':id,'title':'File:Train.jpg','imageinfo':[{'width':w,'height':1080,'size':100,'sha1':sha,'url':'https://upload.wikimedia.org/a.jpg','mime':'image/jpeg'}]}
        with patch('visuals.request_json',return_value={'query':{'pages':{'1':page(1,1920,'a'),'2':page(2,1920,'a'),'3':page(3,640,'b')}}}):
            r=visuals.search_images('train')
        self.assertEqual(len(r),1)

class ExportTests(TestCase):
    def test_refuses_other_project(self):
        import exporter
        with tempfile.TemporaryDirectory() as t:
            core.write_json(Path(t)/'ultimo_projeto_drift.json',{'path':str(Path(t)/'mine.drift')})
            class Client:
                def call(s,name,args=None):
                    if name!='inspect':raise AssertionError('No mutations expected')
                    return {'path':str(Path(t)/'other.drift'),'clips':1}
            with self.assertRaises(ValueError):exporter.export({'output':t},Client(),Job())
    def test_export_checks_file_duration(self):
        import exporter
        with tempfile.TemporaryDirectory() as t:
            target=Path(t)/'mine.drift';core.write_json(Path(t)/'ultimo_projeto_drift.json',{'path':str(target)})
            class Client:
                def call(s,name,args=None):
                    if name=='inspect':return {'path':str(target),'clips':3,'dur':10,'export':{'active':False}}
                    if name=='list_export_options':return {'video':[{'id':'h264'}],'audio':[{'id':'aac'}]}
                    if name=='export_video':Path(args['path']).write_bytes(b'x'*2048);return {'path':args['path'],'started':True}
                    if name=='export_status':return {'busy':False,'progress':1}
            with patch('engine.probe',return_value={'duration':10}):
                result=exporter.export({'output':t},Client(),Job());self.assertTrue(Path(result['path']).exists())
