import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core
from drift_client import send

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.video=self.root/'obra__trilhos.mp4';self.video.touch()
        self.audio=self.root/'voz.wav';self.audio.touch()
        self.item={'id':'a','path':str(self.video),'duration':30.,'kind':'video','width':1920,'height':1080,
                   'tags':['obra','trilhos'],'aliases':[],'entity':'','usage':'especifico'}
        self.cfg={'output':str(self.root/'out'),'audio':str(self.audio),'shot':5}
    def tearDown(self): self.tmp.cleanup()
    def plan(self):
        with patch('core.probe',return_value={'duration':12.}):
            return core.make_plan(self.cfg,{'items':[self.item]},[{'start':0,'end':12,'text':'Los trabajadores construyen las vias ferreas'}],lambda x:None)
    def test_span_covers_audio(self):
        p=self.plan();self.assertEqual(sum(r['duration'] for r in p['rows']),12.)
        self.assertTrue(all(r['path'] for r in p['rows']))
        for r in p['rows']: r['approved']=True
        self.assertTrue(core.validate_plan(p,{'items':[self.item]}))
    def test_no_match_not_random(self):
        self.assertEqual(core.candidates([self.item],'La salud del paciente','',{},4),[])
    def test_specific_entity_never_generic(self):
        a=dict(self.item,entity='Toyota Corolla',aliases=['Corolla'],tags=['carro'])
        b=dict(self.item,id='b',entity='Nissan Sentra',tags=['carro'])
        c=dict(self.item,id='c',entity='',tags=['carro'],usage='generico')
        found=core.candidates([a,b,c],'El Toyota Corolla es un carro','',{},4)
        self.assertTrue(found);self.assertTrue(all(x[1]['entity']=='Toyota Corolla' for x in found))
    def test_reject_out_of_bounds_and_unreviewed(self):
        p=self.plan()
        with self.assertRaises(ValueError):core.validate_plan(p,{'items':[self.item]})
        for r in p['rows']:r['approved']=True
        p['rows'][0]['source_in']=29
        with self.assertRaises(ValueError):core.validate_plan(p,{'items':[self.item]})
    def test_srt(self):
        s=self.root/'a.srt';s.write_text('1\n00:00:01,200 --> 00:00:03,500\nHola\nmundo\n\n',encoding='utf-8')
        self.assertEqual(core.read_srt(s),[{'start':1.2,'end':3.5,'text':'Hola mundo'}])
    def test_tags_inherited(self):
        d=self.root/'projeto';(d/'01').mkdir(parents=True)
        p=d/'01'/'obra.mp4';p.touch()
        core.write_json(d/'tags.json',{'entity':'Obra A','aliases':['Proyecto A'],'tags':['mexico']})
        core.write_json(d/'01'/'tags.json',{'tags':['trilhos']})
        m=core.load_meta(p,d,False)
        self.assertEqual(m['entity'],'Obra A');self.assertIn('trilhos',m['tags']);self.assertIn('mexico',m['tags'])
    def test_short_range_rejected(self):
        a=dict(self.item,ranges=[{'start':0,'end':2,'tags':[]}])
        self.assertEqual(core.candidates([a],'trilhos','',{},5),[])
    def test_slot_pauses_and_no_gaps(self):
        rows=core.slots([{'start':3,'end':7,'text':'oi'}],17.,5)
        end=0
        for r in rows:self.assertEqual(r['at'],end);end=r['at']+r['duration']
        self.assertEqual(end,17)
    def test_image_duration_unlimited(self):
        a=dict(self.item,kind='image',duration=0)
        self.assertTrue(core.candidates([a],'trilhos','',{},5))

class FakeDrift:
    def __init__(self): self.calls=[];self.clips={};self.saved='';self.tracks=[];self.assets={}
    def call(self,name,args=None):
        from drift_client import REQUIRED
        a=args or {};self.calls.append((name,a))
        if name=='toolbox':return {'tools':[{'name':n} for n in REQUIRED]}
        if name=='inspect':return {'clips':len(self.clips),'dirty':False,'path':self.saved,'tracks':self.tracks,
                                  'dur':max([x['start']+x['dur'] for x in self.clips.values()]or[0])}
        if name=='import_media':
            id='asset'+str(len(self.assets));self.assets[id]=a['paths'][0];return {'assets':[{'id':id}]}
        if name=='add_track':
            self.tracks.insert(0,{'type':a['type']});self.tracks=[dict(t,i=i) for i,t in enumerate(self.tracks)]
        if name=='place_clip':
            id='clip'+str(len(self.clips));self.clips[id]={'id':id,'start':a['at'],'dur':30.,'w':1920.,'h':1080.,'x':0.,'y':0.};return self.clips[id].copy()
        if name=='set_duration':self.clips[a['clip']]['dur']=a['duration'];return self.clips[a['clip']].copy()
        if name=='set_trim':self.clips[a['clip']].update({'in':a['in'],'dur':a['out']-a['in']});return self.clips[a['clip']].copy()
        if name=='move_clip':self.clips[a['clip']]['start']=a['at'];return {'placed':a['at']}
        if name=='save_project':self.saved=a['path'];Path(self.saved).write_text('{}')
        return {'ok':True}

class IntegrationTests(unittest.TestCase):
    setUp=CoreTests.setUp
    tearDown=CoreTests.tearDown
    plan=CoreTests.plan
    def test_montage_source_ranges_audio_and_overlap(self):
        p=self.plan()
        for r in p['rows']:r['approved']=True;r['transition']='crossfade'
        fake=FakeDrift();result=send(self.cfg,p,{'items':[self.item]},fake,lambda s:None)
        self.assertTrue(Path(result['path']).exists())
        # Áudio inalterado e nenhuma exportação de mídia feita pelo controlador.
        self.assertEqual(fake.clips['clip0']['start'],0)
        self.assertEqual(fake.clips['clip0']['dur'],12)
        self.assertEqual(fake.clips['clip1']['dur'],5.3)
        self.assertEqual(fake.clips['clip2']['start'],5)
        self.assertTrue(any(n=='add_transition' for n,a in fake.calls))
        self.assertFalse(any(n in ('new_project','export_video') for n,a in fake.calls))
    def test_existing_project_preserved(self):
        p=self.plan()
        for r in p['rows']:r['approved']=True
        fake=FakeDrift();fake.clips={'old':{'start':0,'dur':1}}
        with self.assertRaises(ValueError):send(self.cfg,p,{'items':[self.item]},fake,lambda s:None)
        self.assertFalse(any(n=='import_media' for n,a in fake.calls))

if __name__=='__main__':unittest.main()
