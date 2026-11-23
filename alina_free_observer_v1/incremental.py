#!/usr/bin/env python3
"""Incremental completed-bar research store. Local only; no order placement."""
import argparse,datetime,hashlib,json,math,sqlite3,sys,time
from collector import fetch,SYMBOL,INTERVAL,PERIOD
from replay_research import analyze,HOUR

def db_init(db):
 db.execute('PRAGMA foreign_keys=ON');db.execute('PRAGMA journal_mode=WAL');db.executescript('''
 CREATE TABLE IF NOT EXISTS batches(id INTEGER PRIMARY KEY,retrieved_utc TEXT NOT NULL,server_ms INTEGER NOT NULL,sha256 TEXT NOT NULL,raw_json TEXT NOT NULL);
 CREATE TABLE IF NOT EXISTS bars(symbol TEXT NOT NULL,interval TEXT NOT NULL,open_ms INTEGER NOT NULL,close_ms INTEGER NOT NULL,close_value TEXT NOT NULL,first_batch INTEGER NOT NULL REFERENCES batches(id),PRIMARY KEY(symbol,interval,open_ms));
 CREATE TABLE IF NOT EXISTS revisions(batch_id INTEGER NOT NULL REFERENCES batches(id),symbol TEXT NOT NULL,interval TEXT NOT NULL,open_ms INTEGER NOT NULL,old_close TEXT NOT NULL,new_close TEXT NOT NULL,PRIMARY KEY(batch_id,symbol,interval,open_ms));
 CREATE TABLE IF NOT EXISTS runs(id INTEGER PRIMARY KEY,batch_id INTEGER NOT NULL REFERENCES batches(id),mode TEXT NOT NULL,first_ms INTEGER,last_ms INTEGER,new_bars INTEGER NOT NULL,revisions INTEGER NOT NULL,quality TEXT NOT NULL);
 ''');db.commit()

def ingest(db,rows,server_ms,retrieved_utc):
 # Reuse strict replay input validation including gaps, order, numerical and time checks.
 result=analyze(rows,server_ms)
 valid=[r for r in rows if int(r[6])<server_ms]
 raw=json.dumps(rows,separators=(',',':'),allow_nan=False);sha=hashlib.sha256(raw.encode()).hexdigest();n=rev=0
 with db:
  batch=db.execute('insert into batches(retrieved_utc,server_ms,sha256,raw_json) values(?,?,?,?)',(retrieved_utc,server_ms,sha,raw)).lastrowid
  for row in valid:
   start,end,value=int(row[0]),int(row[6]),str(row[4]);old=db.execute('select close_value,close_ms from bars where symbol=? and interval=? and open_ms=?',(SYMBOL,INTERVAL,start)).fetchone()
   if old is None:
    db.execute('insert into bars values(?,?,?,?,?,?)',(SYMBOL,INTERVAL,start,end,value,batch));n+=1
   elif old!=(value,end):
    db.execute('insert into revisions values(?,?,?,?,?,?)',(batch,SYMBOL,INTERVAL,start,old[0],value));rev+=1
  # Query whole retained history for gaps; never silently claim completeness.
  starts=[x[0] for x in db.execute('select open_ms from bars where symbol=? and interval=? order by open_ms',(SYMBOL,INTERVAL))];gaps=[{'after':a,'before':b,'missing_bars':(b-a)//HOUR-1} for a,b in zip(starts,starts[1:]) if b-a!=HOUR]
  quality='revision_detected' if rev else ('gaps_detected' if gaps else 'contiguous_observed_range_only')
  db.execute('insert into runs(batch_id,mode,first_ms,last_ms,new_bars,revisions,quality) values(?,?,?,?,?,?,?)',(batch,'historical_backfill_not_live',starts[0],starts[-1],n,rev,quality))
 return {'mode':'historical_backfill_not_live','batch_sha256':sha,'batch_id':batch,'new_bars':n,'revisions':rev,'stored_bars':len(starts),'gaps':gaps,'quality':quality,'latest_sample_replay':result['summary']}

def main():
 p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--limit',type=int,default=500,choices=range(16,1001));a=p.parse_args()
 server=fetch('/api/v3/time')['serverTime'];rows=fetch('/api/v3/klines',{'symbol':SYMBOL,'interval':INTERVAL,'limit':a.limit});db=sqlite3.connect(a.db);db_init(db);print(json.dumps(ingest(db,rows,server,datetime.datetime.now(datetime.timezone.utc).isoformat()),ensure_ascii=False));db.close()
if __name__=='__main__':main()
