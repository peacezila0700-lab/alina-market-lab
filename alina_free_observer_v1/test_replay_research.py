import unittest
from replay_research import analyze,HOUR
class TestReplay(unittest.TestCase):
 def rows(self):
  start=1700000000000;return [[start+i*HOUR,'0','0','0',str(100+(i%20 if (i//20)%2==0 else 20-i%20)),'0',start+(i+1)*HOUR-1] for i in range(100)]
 def test_no_lookahead_for_last_signal(self):
  r=self.rows();res=analyze(r,r[-1][6]+1);self.assertGreater(res['summary']['signal_count'],0);self.assertEqual(res['mode'],'HISTORICAL_REPLAY_NOT_LIVE');self.assertLessEqual(res['summary']['outcomes_available'],res['summary']['signal_count'])
 def test_gaps_fail(self):
  r=self.rows();del r[30]
  with self.assertRaises(ValueError):analyze(r,r[-1][6]+1)
 def test_unclosed_excluded(self):
  r=self.rows();res=analyze(r,r[-1][0]+1);self.assertEqual(res['closed_bars'],99)
if __name__=='__main__':unittest.main()
