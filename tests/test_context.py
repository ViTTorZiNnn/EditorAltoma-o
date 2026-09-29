import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from workflow import classify
class ContextTests(unittest.TestCase):
 def test_country_and_person_derived_from_context(self):
  c={'countries':['México'],'primary_country':'México','people':[]}
  self.assertFalse(classify({'path':'clip.mp4','relative_path':'El Salvador/obra.mp4'},c)['context_allowed'])
  self.assertTrue(classify({'path':'clip.mp4','relative_path':'Mexico/Queretaro.mp4'},c)['context_allowed'])
  self.assertTrue(classify({'path':'clip.mp4','relative_path':'reuniao escritorio.mp4'},c)['context_allowed'])
 def test_country_mentioned_in_script_can_be_used(self):
  c={'countries':['México','El Salvador'],'primary_country':'México','people':['Nayib Bukele']}
  self.assertTrue(classify({'path':'bukele.mp4'},c)['context_allowed'])
