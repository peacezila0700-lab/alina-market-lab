import unittest,math
from execution_eval import evaluate,HOUR
class Tests(unittest.TestCase):
 def test_next_open_and_cost_and_short(self):
  bars=[(i*HOUR,100.,102.) for i in range(30)];events=[{'bar_open_ms':0,'direction':'buy','indicator':'a'},{'bar_open_ms':0,'direction':'sell','indicator':'a'}];out=evaluate(bars,events)
  self.assertAlmostEqual(out['results'][0]['horizons']['1']['gross_directional_return'],.02);self.assertAlmostEqual(out['results'][0]['horizons']['1']['net_scenarios']['10'],.019);self.assertAlmostEqual(out['results'][1]['horizons']['1']['gross_directional_return'],-.02)
 def test_not_use_signal_close_as_entry(self):
  bars=[(0,100.,500.),(HOUR,200.,210.)];out=evaluate(bars,[{'bar_open_ms':0,'direction':'buy','indicator':'a'}]);self.assertEqual(out['results'][0]['horizons']['1']['entry_price'],200.)
 def test_unavailable_outcome(self):
  bars=[(i*HOUR,100.,100.) for i in range(5)];out=evaluate(bars,[{'bar_open_ms':4*HOUR,'direction':'buy','indicator':'a'}]);self.assertEqual(out['results'][0]['horizons'],{})
 def test_invalid_and_gap(self):
  with self.assertRaises(ValueError):evaluate([(0,100.,100.),(2*HOUR,100.,100.)],[])
  with self.assertRaises(ValueError):evaluate([(0,math.nan,100.)],[])
if __name__=='__main__':unittest.main()
