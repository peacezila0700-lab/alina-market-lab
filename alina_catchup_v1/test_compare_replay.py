import unittest
from compare_replay import signals,wilder_rsi,rsi_series,HOUR
class Tests(unittest.TestCase):
 def test_constant(self):
  self.assertEqual(signals([(i*HOUR,100.) for i in range(100)]),[]);self.assertEqual(wilder_rsi([100.]*20),50.)
 def test_rsi_incremental_matches_reference(self):
  p=[100+(i%7)*(1 if i%2 else -1) for i in range(100)];r=rsi_series(p)
  for i in range(14,len(p)):self.assertAlmostEqual(r[i],wilder_rsi(p[:i+1]),places=12)
 def test_no_future_leakage(self):
  bars=[(i*HOUR,100+(i%20 if (i//20)%2==0 else 20-i%20)) for i in range(120)];a=signals(bars[:90]);b=signals(bars);strip=lambda xs:[(x['indicator'],x['direction'],x['bar_open_ms'],x['signal_close']) for x in xs if x['bar_open_ms']<90*HOUR];self.assertEqual(strip(a),strip(b));self.assertTrue(a)
 def test_gap_and_invalid(self):
  bars=[(i*HOUR,100.) for i in range(100)];bars[70]=(bars[70][0]+HOUR,100.)
  with self.assertRaises(ValueError):signals(bars)
 def test_signal_own_bar_only_and_outcome(self):
  bars=[(i*HOUR,float(100+(i%20 if (i//20)%2==0 else 20-i%20))) for i in range(120)];events=signals(bars);self.assertTrue(events)
  for e in events:
   i=e['bar_open_ms']//HOUR
   for horizon,o in e['outcomes'].items():self.assertEqual(o['next_close'],bars[i+int(horizon)][1])
if __name__=='__main__':unittest.main()
