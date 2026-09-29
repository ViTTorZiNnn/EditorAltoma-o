import unittest,sys,random
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core,engine
class RhythmTests(unittest.TestCase):
 def test_varied_durations_cover_narration(self):
  rows=core.slots([{'start':0,'end':120,'text':'obra'}],120,5,random.Random(7))
  self.assertGreater(len({r['duration'] for r in rows}),5)
  for a,b in zip(rows,rows[1:]):self.assertAlmostEqual(a['at']+a['duration'],b['at'],places=2)
  self.assertAlmostEqual(sum(r['duration'] for r in rows),120,places=2)
 def test_random_entry_across_long_source(self):
  rng=random.Random(10);used={};item={'id':'x'};entries=[]
  for _ in range(6):
   duration,start,end=engine.choose_range(item,[{'start':0,'end':120}],5,used,rng)
   self.assertLessEqual(start+duration,end)
   for a,b in used.get('x',[]):self.assertTrue(start+duration<=a or start>=b)
   used.setdefault('x',[]).append((start,start+duration));entries.append(start)
  self.assertGreater(max(entries),60)
