import unittest,tempfile,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import providers
class ProviderTests(unittest.TestCase):
 def test_pexels_hd_choice_new_endpoint_and_cache(self):
  payload={'videos':[{'id':9,'url':'https://www.pexels.com/video/9','user':{'name':'Autor'},'video_files':[{'file_type':'video/mp4','width':640,'height':360,'link':'https://example.com/small.mp4'},{'file_type':'video/mp4','width':1920,'height':1080,'link':'https://example.com/hd.mp4'}]}]}
  with tempfile.TemporaryDirectory() as tmp,patch.object(providers,'api',return_value=payload) as api:
   rows=providers.search('pexels','construction','video','test',tmp);providers.search('pexels','construction','video','test',tmp)
   self.assertEqual(api.call_count,1);self.assertIn('/v1/videos/search?',api.call_args.args[0]);self.assertEqual(rows[0]['url'],'https://example.com/hd.mp4');self.assertEqual(rows[0]['author'],'Autor')
 def test_pixabay_video_format(self):
  payload={'hits':[{'id':7,'pageURL':'https://pixabay.com/videos/7','user':'Autor','videos':{'large':{'width':3840,'height':2160,'url':'https://example.com/4k.mp4'},'medium':{'width':1920,'height':1080,'url':'https://example.com/hd.mp4'}}}]}
  with tempfile.TemporaryDirectory() as tmp,patch.object(providers,'api',return_value=payload):
   rows=providers.search('pixabay','workers','video','test',tmp);self.assertEqual(rows[0]['url'],'https://example.com/hd.mp4')
 def test_serper_original_not_thumbnail(self):
  payload={'images':[{'imageUrl':'https://example.com/full.jpg','thumbnailUrl':'https://example.com/small.jpg','link':'https://example.com/article','source':'Original'}]}
  with tempfile.TemporaryDirectory() as tmp,patch.object(providers,'api',return_value=payload):
   rows=providers.search('serper','Tren México Querétaro','image','test',tmp);self.assertEqual(rows[0]['url'],'https://example.com/full.jpg');self.assertEqual(rows[0]['page'],'https://example.com/article')
