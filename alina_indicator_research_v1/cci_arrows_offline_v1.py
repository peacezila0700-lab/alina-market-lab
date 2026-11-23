#!/usr/bin/env python3
"""Experimental CCI Arrows-inspired PRICE_CLOSE adapter. Not validated against MT5.
Signal rule follows EarnForex CCI Arrows 1.02 (Apache-2.0), source at pinned commit.
Only completed bars; replay outputs are labelled REPLAY, never live observation.
"""
import argparse,csv,collections,datetime,hashlib,json,math,pathlib
from decimal import Decimal,InvalidOperation
COMMIT='843dd190263906958b7ccff4df1661604dee8c9b'
def cci(vals,period):
 if len(vals)<period:return None
 x=vals[-period:]; mean=sum(x)/period;deviation=sum(abs(v-mean) for v in x)/period
 return 0.0 if deviation==0 else (x[-1]-mean)/(0.015*deviation)
def cross(previous,current):
 if previous is None or current is None:return None
 if previous<0 and current>0:return 'buy'
 if previous>0 and current<0:return 'sell'
 return None
def parse_time(t):
 d=datetime.datetime.fromisoformat(t.replace('Z','+00:00'))
 if d.tzinfo is None:raise ValueError('close_utc requires offset')
 return d.astimezone(datetime.timezone.utc)
def replay(path,symbol,timeframe,period):
 if period<2:raise ValueError('period must be >=2')
 vals=collections.deque(maxlen=period);previous=None;last=None;results=[]
 with open(path,'rb') as binary:source_hash=hashlib.file_digest(binary,'sha256').hexdigest()
 with open(path,newline='',encoding='utf-8-sig') as f:
  reader=csv.DictReader(f)
  if not {'close_utc','close'}.issubset(reader.fieldnames or []):raise ValueError('input requires close_utc,close')
  for lineno,row in enumerate(reader,2):
   t=parse_time(row['close_utc']);p=float(row['close'])
   if not math.isfinite(p) or p<=0:raise ValueError(f'bad close at line {lineno}')
   if last is not None and t<=last:raise ValueError(f'timestamps must be strictly increasing at line {lineno}')
   last=t;vals.append(p);now=cci(list(vals),period);direction=cross(previous,now)
   if direction:
    e={'indicator':'EarnForex_CCI_Arrows_close_adapter','version':f'{COMMIT}:period={period}:adapter=v1','symbol':symbol,'timeframe':timeframe,'direction':direction,'observed_utc':t.isoformat().replace('+00:00','Z'),'price':p,'source':'historical_replay_NOT_live','signal_rule':'closed-bar PRICE_CLOSE CCI strict zero-cross','cci_current':now,'cci_previous':previous,'source_input_sha256':source_hash}
    e['id']=hashlib.sha256(json.dumps(e,sort_keys=True,separators=(',',':')).encode()).hexdigest();results.append(e)
   previous=now
 return results
def main():
 a=argparse.ArgumentParser();a.add_argument('--input',required=True);a.add_argument('--output',required=True);a.add_argument('--symbol',required=True);a.add_argument('--timeframe',required=True);a.add_argument('--period',type=int,default=14);args=a.parse_args()
 events=replay(args.input,args.symbol,args.timeframe,args.period)
 with open(args.output,'x',encoding='utf-8') as f:
  for e in events:f.write(json.dumps(e,sort_keys=True)+'\n')
 print(json.dumps({'status':'REPLAY_ONLY_NOT_LIVE','signals':len(events),'output':args.output,'mt5_equivalence':'unverified'}))
if __name__=='__main__':main()
