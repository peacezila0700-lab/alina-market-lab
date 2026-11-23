#!/usr/bin/env python3
"""Offline research; every event is retrospective, not a live or executable trade."""
import argparse,datetime,hashlib,json,math,os,sqlite3,sys,urllib.parse,urllib.request
sys.path.insert(0,os.path.join(os.path.dirname(__file__),'..','alina_indicator_research_v1'))
from cci_arrows_offline_v1 import cci,cross
from collector import fetch,SYMBOL,INTERVAL,PERIOD
HOUR=3600000

def analyze(rows,server_ms):
 bars=[]
 for row in rows:
  if not isinstance(row,list) or len(row)<7: raise ValueError('malformed kline')
  start,end,p=int(row[0]),int(row[6]),float(row[4])
  if not math.isfinite(p) or p<=0 or end!=start+HOUR-1:raise ValueError('invalid price or bar time')
  if end<server_ms:bars.append((start,end,p))
 if len(bars)<PERIOD+2:raise ValueError('insufficient bars')
 if any(bars[i][0]-bars[i-1][0]!=HOUR for i in range(1,len(bars))):raise ValueError('gap, duplicate or disorder')
 signals=[]
 for i in range(PERIOD,len(bars)):
  prev=cci([b[2] for b in bars[i-PERIOD:i]],PERIOD)
  cur=cci([b[2] for b in bars[i-PERIOD+1:i+1]],PERIOD)
  direction=cross(prev,cur)
  if direction:
   # Future close is a research benchmark only; unavailable at signal time.
   future=bars[i+1][2] if i+1<len(bars) else None
   ret=None if future is None else (future/bars[i][2]-1)*(1 if direction=='buy' else -1)
   signals.append({'bar_open_ms':bars[i][0],'bar_close_ms':bars[i][1],'close':bars[i][2],'direction':direction,'cci_previous':prev,'cci_current':cur,'next_close':future,'gross_directional_return_1bar':ret})
 realized=[s['gross_directional_return_1bar'] for s in signals if s['gross_directional_return_1bar'] is not None]
 return {'mode':'HISTORICAL_REPLAY_NOT_LIVE','instrument':SYMBOL,'interval':INTERVAL,'period':PERIOD,'closed_bars':len(bars),'first_open_ms':bars[0][0],'last_open_ms':bars[-1][0],'signals':signals,'summary':{'signal_count':len(signals),'outcomes_available':len(realized),'positive':sum(x>0 for x in realized),'negative':sum(x<0 for x in realized),'flat':sum(x==0 for x in realized),'mean_gross_directional_return_1bar':sum(realized)/len(realized) if realized else None},'limitations':['no spread, slippage, commissions or execution','CCI approximation not validated against MT5','historical replay; not live observations','data rights unknown','single fetch; no continuous coverage']}

def main():
 a=argparse.ArgumentParser();a.add_argument('--output',required=True,help='new JSON file; never overwrite');args=a.parse_args()
 server=fetch('/api/v3/time')['serverTime'];rows=fetch('/api/v3/klines',{'symbol':SYMBOL,'interval':INTERVAL,'limit':500});obj=analyze(rows,server);obj['source_url']='https://data-api.binance.vision/api/v3/klines';obj['raw_klines']=rows;raw=json.dumps(rows,separators=(',',':'),allow_nan=False).encode();obj['raw_sha256']=hashlib.sha256(raw).hexdigest();obj['server_time_ms']=server;obj['retrieved_utc_unverified_clock']=datetime.datetime.now(datetime.timezone.utc).isoformat();
 with open(args.output,'x',encoding='utf-8') as f:json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False)
 print(json.dumps({'output':args.output,'summary':obj['summary'],'closed_bars':obj['closed_bars'],'mode':obj['mode']}))
if __name__=='__main__':main()
