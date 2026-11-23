import unittest,sqlite3,datetime
from collector import evaluate,init,record
class CollectorTest(unittest.TestCase):
 def setUp(self):
  self.start=1700000000000;self.rows=[[self.start+i*3600000,'0','0','0',str(100+i%5),'0',self.start+(i+1)*3600000-1] for i in range(20)];self.server=self.start+21*3600000;self.now=datetime.datetime.fromtimestamp(self.server/1000,datetime.timezone.utc).isoformat();self.db=sqlite3.connect(':memory:');init(self.db)
 def test_repeat_and_revision(self):
  self.assertEqual(record(self.db,self.rows,self.server,self.now)['status'],'new_observation');self.assertEqual(record(self.db,self.rows,self.server,self.now)['status'],'repeat_same');self.rows[-1][4]='120';self.assertEqual(record(self.db,self.rows,self.server,self.now)['status'],'revision_detected_original_retained');self.assertEqual(self.db.execute('select count(*) from observations').fetchone()[0],1)
 def test_gap(self):
  with self.assertRaises(ValueError):evaluate(self.rows[:5]+self.rows[6:],self.server)
 def test_clock(self):
  with self.assertRaises(ValueError):record(self.db,self.rows,self.server,'2020-01-01T00:00:00Z')
if __name__=='__main__':unittest.main()
