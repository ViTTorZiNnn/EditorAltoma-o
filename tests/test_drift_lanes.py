import unittest,tempfile,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import drift_client as d
class Fake:
 def __init__(self):self.tracks=[];self.placed=[];self.path=''
 def call(self,n,a=None):
  a=a or {}
  if n=='toolbox':return {'ops':d.REQUIRED}
  if n=='inspect':return {'clips':len(self.placed),'dirty':False,'path':self.path,'dur':15,'tracks':[{'i':i} for i in range(len(self.tracks))]}
  if n=='import_media':return {'assets':[{'id':a['paths'][0]}]}
  if n=='add_track':self.tracks.insert(0,a['type'])
  if n=='place_clip':
   kind='audio' if a['asset'].endswith('.mp3') else 'shape' if a['asset'].endswith('.png') else 'video'
   assert self.tracks[a['track']]==kind,'Track does not accept this asset'
   self.placed.append(a);return {'id':str(len(self.placed)),'w':1920,'h':1080,'x':0,'y':0}
  if n=='set_duration':return {'dur':a['duration']}
  if n=='set_trim':return {'in':a['in'],'dur':a['out']-a['in']}
  if n=='move_clip':return {'placed':a['at']}
  if n=='save_project':self.path=a['path'];Path(self.path).write_text('{}')
  return {}
class LaneTests(unittest.TestCase):
 def test_mixed_video_images_audio_complete(self):
  with tempfile.TemporaryDirectory() as tmp:
   paths=[str(Path(tmp)/x) for x in ['a.mp4','b.png','c.mp4']]
   cat={'items':[{'path':p,'kind':'image' if p.endswith('.png') else 'video','duration':30} for p in paths]}
   plan={'audio':str(Path(tmp)/'voice.mp3'),'duration':15,'rows':[{'path':p,'at':i*5,'duration':5,'source_in':0,'transition':'crossfade','zoom':p.endswith('.png')} for i,p in enumerate(paths)]}
   fake=Fake()
   with patch.object(d,'validate_plan'):d.send({'output':tmp},plan,cat,fake,lambda *a:None)
   self.assertEqual(len(fake.placed),4);self.assertEqual([x['track'] for x in fake.placed],[0,2,1,2])
