#!/usr/bin/env python3
"""Bounded, transactional historical hourly kline catchup; no trading."""
import argparse,datetime,hashlib,json,math,sqlite3,urllib.parse,urllib.request
BASE='https://data-api.binance.vision'; HOUR=3600000;MAX_PAGE=1000;SYMBOL='BTCUSDT';INTERVAL='1h'
def request(path,params=None):
 u=BASE+path+('?' + urllib.parse.urlencode(params) if params else '')
 with urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'ALINA-research-catchup/1.0'}),timeout=30) as r:
  body=r.read(4*1024*1024+1)
  if len(body)>4*1024*1024:raise ValueError('source response too large')
  return json.loads(body)
def init(db):
 db.execute('pragma foreign_keys=on');db.execute('pragma journal_mode=WAL');db.executescript('''
 CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,start_ms INTEGER NOT NULL,end_exclusive_ms INTEGER NOT NULL,next_ms INTEGER NOT NULL,status TEXT NOT NULL CHECK(status IN ('incomplete','complete')));
 CREATE TABLE IF NOT EXISTS pages(id INTEGER PRIMARY KEY,job_id TEXT NOT NULL REFERENCES jobs(id),requested_start_ms INTEGER NOT NULL,requested_end_ms INTEGER NOT NULL,retrieved_utc TEXT NOT NULL,provider_time_ms INTEGER NOT NULL,raw_json TEXT NOT NULL,raw_sha256 TEXT NOT NULL,UNIQUE(job_id,requested_start_ms));
 CREATE TABLE IF NOT EXISTS bars(open_ms INTEGER PRIMARY KEY,close_ms INTEGER NOT NULL,full_row_json TEXT NOT NULL,first_page_id INTEGER NOT NULL REFERENCES pages(id));
 ''');db.commit()
def new_job(db,start,end):
 if not isinstance(start,int) or not isinstance(end,int) or start%HOUR or end%HOUR or start>=end:raise ValueError('start/end must be ordered UTC hour boundaries')
 job=hashlib.sha256(f'{SYMBOL}|{INTERVAL}|{start}|{end}'.encode()).hexdigest()
 with db:db.execute('insert or ignore into jobs values(?,?,?,?,?)',(job,start,end,start,'incomplete'))
 return job

def page_commit(db,job,rows,provider_ms,observed):
 rec=db.execute('select next_ms,end_exclusive_ms,status from jobs where id=?',(job,)).fetchone()
 if rec is None:raise ValueError('unknown job')
 next_ms,end,status=rec
 if status=='complete':return {'status':'complete','new_bars':0}
 limit_end=min(end,next_ms+MAX_PAGE*HOUR)
 if provider_ms<limit_end:raise ValueError('provider clock does not confirm all requested bars closed')
 if not isinstance(rows,list):raise ValueError('malformed page')
 expected=(limit_end-next_ms)//HOUR
 if len(rows)!=expected:raise ValueError(f'incomplete page expected {expected} got {len(rows)}')
 canonical=[]
 for i,r in enumerate(rows):
  if not isinstance(r,list) or len(r)<7:raise ValueError('malformed bar')
  start=int(r[0]);close=int(r[6]);price=float(r[4])
  if start!=next_ms+i*HOUR or close!=start+HOUR-1 or not math.isfinite(price) or price<=0:raise ValueError('gap/order/timestamp/price failure')
  canonical.append(json.dumps(r,separators=(',',':'),allow_nan=False))
 raw=json.dumps(rows,separators=(',',':'),allow_nan=False);sha=hashlib.sha256(raw.encode()).hexdigest()
 with db:
  # Each page and cursor update commit together. Conflicting rows abort the page, preserving originals.
  for r,s in zip(rows,canonical):
   old=db.execute('select full_row_json from bars where open_ms=?',(int(r[0]),)).fetchone()
   if old and old[0]!=s:raise ValueError('provider revision: original retained; manual reconciliation required')
  cur=db.execute('insert into pages(job_id,requested_start_ms,requested_end_ms,retrieved_utc,provider_time_ms,raw_json,raw_sha256) values(?,?,?,?,?,?,?)',(job,next_ms,limit_end,observed,provider_ms,raw,sha));page_id=cur.lastrowid;n=0
  for r,s in zip(rows,canonical):
   cur=db.execute('insert or ignore into bars values(?,?,?,?)',(int(r[0]),int(r[6]),s,page_id));n+=cur.rowcount
  status='complete' if limit_end==end else 'incomplete';db.execute('update jobs set next_ms=?,status=? where id=? and next_ms=?',(limit_end,status,job,next_ms))
 return {'status':status,'page_id':page_id,'new_bars':n,'next_ms':limit_end,'raw_sha256':sha}

def main():
 p=argparse.ArgumentParser(description='Historical backfill only, cap 1000 bars/page, bounded pages per run.')
 p.add_argument('--db',required=True);p.add_argument('--start-ms',type=int,required=True);p.add_argument('--end-exclusive-ms',type=int,required=True);p.add_argument('--max-pages',type=int,default=1);args=p.parse_args()
 if not 1<=args.max_pages<=20:raise ValueError('max pages 1..20')
 db=sqlite3.connect(args.db);init(db);job=new_job(db,args.start_ms,args.end_exclusive_ms)
 for _ in range(args.max_pages):
  nxt,end,status=db.execute('select next_ms,end_exclusive_ms,status from jobs where id=?',(job,)).fetchone()
  if status=='complete':break
  provider=request('/api/v3/time')['serverTime'];stop=min(end,nxt+MAX_PAGE*HOUR)
  if provider<stop:raise ValueError('requested bars not closed under provider clock')
  rows=request('/api/v3/klines',{'symbol':SYMBOL,'interval':INTERVAL,'startTime':nxt,'endTime':stop-1,'limit':min(MAX_PAGE,(stop-nxt)//HOUR)})
  out=page_commit(db,job,rows,provider,datetime.datetime.now(datetime.timezone.utc).isoformat());print(json.dumps(out),flush=True)
 print(json.dumps({'job_id':job,'status':db.execute('select status from jobs where id=?',(job,)).fetchone()[0],'mode':'historical_backfill_not_live','rights':'unknown'}));db.close()
if __name__=='__main__':main()
