import sqlite3,unittest
from incremental import db_init,ingest,HOUR
class TestIngest(unittest.TestCase):
 def setUp(self):
  self.db=sqlite3.connect(':memory:');db_init(self.db);self.start=1700000000000;self.rows=[[self.start+i*HOUR,'0','0','0',str(100+i%8),'0',self.start+(i+1)*HOUR-1] for i in range(30)];self.server=self.start+31*HOUR
 def test_repeat_and_revision(self):
  a=ingest(self.db,self.rows,self.server,'test');self.assertEqual(a['new_bars'],30);b=ingest(self.db,self.rows,self.server,'test');self.assertEqual(b['new_bars'],0);self.rows[2][4]='999';c=ingest(self.db,self.rows,self.server,'test');self.assertEqual(c['revisions'],1);self.assertEqual(self.db.execute('select close_value from bars where open_ms=?',(self.start+2*HOUR,)).fetchone()[0],'102')
 def test_gap_rejected_atomic(self):
  r=self.rows[:];del r[4]
  with self.assertRaises(ValueError):ingest(self.db,r,self.server,'test')
  self.assertEqual(self.db.execute('select count(*) from batches').fetchone()[0],0)
 def test_detect_gap_between_batches(self):
  ingest(self.db,self.rows,self.server,'test');r=[[x[0]+40*HOUR,*x[1:6],x[6]+40*HOUR] for x in self.rows];out=ingest(self.db,r,self.server+40*HOUR,'test');self.assertEqual(out['quality'],'gaps_detected');self.assertEqual(out['gaps'][0]['missing_bars'],10)
if __name__=='__main__':unittest.main()
