#!/usr/bin/env python3
"""EXPERIMENTAL Binance public klines observation. No orders. Not a reliable 24/7 service."""
import argparse,collections,datetime,hashlib,json,math,os,sqlite3,sys,time,urllib.error,urllib.parse,urllib.request
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..','alina_indicator_research_v1'))
from cci_arrows_offline_v1 import cci,cross
BASE='https://data-api.binance.vision';PERIOD=14;VERSION='CCI_ARROWS_PRICE_CLOSE_APPROX_V1_P14';INTERVAL='1h';SYMBOL='BTCUSDT'
def fetch(path,params=None):
 url=BASE+path+('?' + urllib.parse.urlencode(params) if params else '')
 req=urllib.request.Request(url,headers={'User-Agent':'ALINA-observer/1.0','Accept':'application/json'})
 with urllib.request.urlopen(req,timeout=20) as r:
  data=r.read(1024*1024+1)
  if len(data)>1024*1024:raise ValueError('response size limit')
  return json.loads(data)
def evaluate(rows,server_ms):
 if not isinstance(server_ms,int):raise ValueError('invalid server time')
 closed=[]
 for r in rows:
  if not isinstance(r,list) or len(r)<7:raise ValueError('bad kline')
  start=int(r[0]);close_ms=int(r[6]);price=float(r[4]);
  if not math.isfinite(price) or price<=0 or close_ms<start:raise ValueError('bad price/time')
  if close_ms<server_ms:closed.append((start,close_ms,price))
 if len(closed)<PERIOD+1:raise ValueError('insufficient completed bars')
 if any(closed[i][0]<=closed[i-1][0] for i in range(1,len(closed))):raise ValueError('duplicate/out-of-order bars')
 if any(closed[i][0]-closed[i-1][0]!=3600000 for i in range(1,len(closed))):raise ValueError('bar gap in source input')
 prices=[r[2] for r in closed];prior=cci(prices[:-1],PERIOD);current=cci(prices,PERIOD)
 return {'bar_open_ms':closed[-1][0],'bar_close_ms':closed[-1][1],'bar_close_price':closed[-1][2],'cci_previous':prior,'cci_current':current,'direction':cross(prior,current),'closed_bars_count':len(closed)}
def init(db):
 db.execute('pragma journal_mode=WAL');db.executescript('''create table if not exists runs(id integer primary key,observed_utc text not null,server_ms integer not null,raw_json text not null,raw_sha256 text not null);create table if not exists observations(symbol text not null,interval text not null,version text not null,bar_open_ms integer not null,bar_close_ms integer not null,first_observed_utc text not null,bar_close_price real not null,cci_previous real not null,cci_current real not null,direction text,run_id integer not null references runs(id),primary key(symbol,interval,version,bar_open_ms));''');db.commit()
def record(db,rows,server_ms,observed):
 result=evaluate(rows,server_ms);raw=json.dumps(rows,separators=(',',':'),allow_nan=False);sha=hashlib.sha256(raw.encode()).hexdigest();observed=datetime.datetime.fromisoformat(observed.replace('Z','+00:00'))
 if observed.tzinfo is None:raise ValueError('observation timezone missing')
 # local wall clock can be wrong; never claim bar closed before actual observation time if clocks disagree.
 obs_ms=int(observed.timestamp()*1000)
 if abs(obs_ms-server_ms)>120000:raise ValueError('clock mismatch >120 seconds')
 seen=observed.astimezone(datetime.timezone.utc).isoformat();key=(SYMBOL,INTERVAL,VERSION,result['bar_open_ms']);existing=db.execute('select bar_close_price,cci_previous,cci_current,direction from observations where symbol=? and interval=? and version=? and bar_open_ms=?',key).fetchone()
 with db:
  cur=db.execute('insert into runs(observed_utc,server_ms,raw_json,raw_sha256) values(?,?,?,?)',(seen,server_ms,raw,sha));run=cur.lastrowid
  if existing is None:
   db.execute('insert into observations values(?,?,?,?,?,?,?,?,?,?,?)',(*key,result['bar_close_ms'],seen,result['bar_close_price'],result['cci_previous'],result['cci_current'],result['direction'],run));status='new_observation'
  else:
   latest=(result['bar_close_price'],result['cci_previous'],result['cci_current'],result['direction']);status='repeat_same' if existing==latest else 'revision_detected_original_retained'
 return {**result,'observed_utc':seen,'server_ms':server_ms,'raw_sha256':sha,'status':status,'rights':'unknown','live_signal':'only if direction exists and status new_observation; bar close price is not an executable quote'}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--db',required=True);args=ap.parse_args();server=fetch('/api/v3/time')['serverTime'];rows=fetch('/api/v3/klines',{'symbol':SYMBOL,'interval':INTERVAL,'limit':50});now=datetime.datetime.now(datetime.timezone.utc).isoformat();db=sqlite3.connect(args.db);init(db);print(json.dumps(record(db,rows,server,now),ensure_ascii=False));db.close()
if __name__=='__main__':
 try:main()
 except Exception as e:print(json.dumps({'status':'error','type':type(e).__name__,'detail':str(e)[:200]}),file=sys.stderr);sys.exit(1)
