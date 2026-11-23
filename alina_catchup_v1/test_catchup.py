import sqlite3,unittest
from catchup import init,new_job,page_commit,HOUR,MAX_PAGE
class Tests(unittest.TestCase):
 def setUp(self):self.db=sqlite3.connect(':memory:');init(self.db);self.s=18000*HOUR
 def tearDown(self):self.db.close()
 def rows(self,start,n):return [[start+i*HOUR,'1','1','1','1','1',start+(i+1)*HOUR-1,'1',1,'1','1','0'] for i in range(n)]
 def test_multi_page_resume(self):
  job=new_job(self.db,self.s,self.s+1003*HOUR);a=page_commit(self.db,job,self.rows(self.s,1000),self.s+1003*HOUR,'test');self.assertEqual(a['status'],'incomplete');self.assertEqual(new_job(self.db,self.s,self.s+1003*HOUR),job);b=page_commit(self.db,job,self.rows(self.s+1000*HOUR,3),self.s+1003*HOUR,'test');self.assertEqual(b['status'],'complete');self.assertEqual(self.db.execute('select count(*) from bars').fetchone()[0],1003);self.assertEqual(page_commit(self.db,job,[],self.s+1003*HOUR,'test')['status'],'complete')
 def test_gap_and_partial_are_atomic(self):
  j=new_job(self.db,self.s,self.s+20*HOUR);rows=self.rows(self.s,20);del rows[4]
  with self.assertRaises(ValueError):page_commit(self.db,j,rows,self.s+20*HOUR,'test')
  self.assertEqual(self.db.execute('select count(*) from pages').fetchone()[0],0);self.assertEqual(self.db.execute('select next_ms from jobs').fetchone()[0],self.s)
 def test_conflict_aborts_new_job(self):
  j=new_job(self.db,self.s,self.s+20*HOUR);page_commit(self.db,j,self.rows(self.s,20),self.s+30*HOUR,'test');j2=new_job(self.db,self.s,self.s+30*HOUR);r=self.rows(self.s,30);r[10][4]='2'
  with self.assertRaises(ValueError):page_commit(self.db,j2,r,self.s+30*HOUR,'test')
  self.assertEqual(self.db.execute('select count(*) from pages').fetchone()[0],1);self.assertEqual(self.db.execute('select count(*) from bars').fetchone()[0],20)
 def test_no_open_bars(self):
  j=new_job(self.db,self.s,self.s+3*HOUR)
  with self.assertRaises(ValueError):page_commit(self.db,j,self.rows(self.s,3),self.s+3*HOUR-1,'test')
if __name__=='__main__':unittest.main()
