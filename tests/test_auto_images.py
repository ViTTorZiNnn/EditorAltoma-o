import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import visuals
class Job:
 def check(self):pass
 def log(self,*a):pass
class ImagesTests(unittest.TestCase):
 def test_twenty_unique_alternating_and_preserves_timing(self):
  with tempfile.TemporaryDirectory() as d:
   cfg={'output':d,'subject':'Mexico railway','image_count':20,'planner':'local','image_terms':'railway'}
   plan={'rows':[dict(text='obra',at=i*5,duration=5,path='video',source_in=10) for i in range(180)]}
   cat={'items':[]};entries=[{'id':str(i),'title':'railway '+str(i)} for i in range(20)]
   def download(c,e,cat,j):
    path='image'+e['id'];cat['items'].append({'path':path,'source':e});return path,cat
   with patch.object(visuals,'search_images',return_value=entries),patch.object(visuals,'download_image',side_effect=download),patch.object(visuals.core,'save_plan'):
    result,_=visuals.automatic_images(cfg,plan,cat,Job())
   rows=[r for r in result['rows'] if r.get('online_auto')]
   self.assertEqual(len(rows),20);self.assertEqual(len({r['path'] for r in rows}),20)
   self.assertEqual([r['zoom_direction'] for r in rows],['in','out']*10)
   self.assertEqual(sum(r['duration'] for r in result['rows']),900)
 def test_network_error_preserves_video(self):
  plan={'rows':[dict(text='obra',path='original',at=0,duration=5)]}
  with patch.object(visuals,'search_images',side_effect=ValueError('offline')),patch.object(visuals.core,'save_plan'):
   result,_=visuals.automatic_images({'subject':'obra','image_count':20,'image_terms':'obra'},plan,{'items':[]},Job())
  self.assertEqual(result['rows'][0]['path'],'original')
  self.assertEqual(result['image_report']['added'],0)
