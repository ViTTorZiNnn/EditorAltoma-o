import tempfile,sys,unittest
from pathlib import Path
from PIL import Image
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import visuals,core
class Job:
 def check(self):pass
 def log(self,*a):pass
class BackgroundTests(unittest.TestCase):
 def test_portrait_background_cache_and_original_preserved(self):
  with tempfile.TemporaryDirectory() as d:
   src=Path(d)/'portrait.png';bg=Path(d)/'bg.png'
   Image.new('RGB',(800,1200),'red').save(src);Image.new('RGB',(100,100),'white').save(bg)
   cat={'items':[{'path':str(src),'kind':'image','id':core.fingerprint(src)}]}
   plan={'rows':[{'path':str(src),'zoom':True,'zoom_direction':'out'}]}
   cfg={'output':d,'background':str(bg)}
   with patch.object(core,'save_plan'):
    plan,cat=visuals.fit_image_backgrounds(cfg,plan,cat,Job());first=plan['rows'][0]['path']
    plan,cat=visuals.fit_image_backgrounds(cfg,plan,cat,Job())
   self.assertEqual(first,plan['rows'][0]['path']);self.assertEqual(len(cat['items']),2)
   with Image.open(first) as image:
    self.assertEqual(image.size,(1920,1080));self.assertEqual(image.getpixel((0,0)),(255,255,255));self.assertEqual(image.getpixel((960,540)),(255,0,0))
   self.assertTrue(src.exists());self.assertEqual(plan['rows'][0]['zoom_direction'],'out')
 def test_widescreen_unchanged(self):
  with tempfile.TemporaryDirectory() as d:
   src=Path(d)/'wide.png';Image.new('RGB',(1280,720)).save(src)
   plan={'rows':[{'path':str(src)}]};cat={'items':[{'path':str(src),'kind':'image'}]}
   with patch.object(core,'save_plan'):plan,cat=visuals.fit_image_backgrounds({'output':d},plan,cat,Job())
   self.assertEqual(plan['rows'][0]['path'],str(src));self.assertEqual(len(cat['items']),1)
