#!/usr/bin/env python3
"""Research-only next-bar-open proxy. No trades. Simplified scenario costs."""
import argparse,collections,datetime,hashlib,json,math,pathlib,sqlite3,statistics,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent.parent/'alina_catchup_v1'))
from compare_replay import build,HOUR
HORIZONS=(1,4,24); COSTS_BPS=(0,10,20)
def evaluate(bars,events):
 # bars: ordered (open_ms, open, close), event signal generated after its bar closes.
 by_time={row[0]:i for i,row in enumerate(bars)}
 if len(by_time)!=len(bars):raise ValueError('duplicate time')
 if any(bars[i][0]-bars[i-1][0]!=HOUR for i in range(1,len(bars))):raise ValueError('gaps or order errors')
 if any(not math.isfinite(x) or x<=0 for b in bars for x in b[1:]):raise ValueError('invalid OHLC')
 output=[];groups=collections.defaultdict(list)
 for ev in events:
  i=by_time.get(ev['bar_open_ms']);direction=ev['direction'];name=ev['indicator']
  if i is None or direction not in ('buy','sell'):raise ValueError('bad event')
  result={'indicator':name,'direction':direction,'signal_bar_open_ms':ev['bar_open_ms'],'entry_assumption':'next_bar_open','horizons':{}}
  for h in HORIZONS:
   if i+h>=len(bars):continue
   entry=bars[i+1][1];exit=bars[i+h][2];gross=(exit/entry-1)*(1 if direction=='buy' else -1)
   ret={'entry_price':entry,'exit_close_price':exit,'gross_directional_return':gross,'net_scenarios':{str(bps):gross-bps/10000 for bps in COSTS_BPS}}
   result['horizons'][str(h)]=ret;groups[(name,h)].append(gross)
  output.append(result)
 summary={}
 for name in sorted({ev['indicator'] for ev in events}):
  summary[name]={'events':sum(e['indicator']==name for e in events),'horizons':{}}
  for h in HORIZONS:
   values=groups[(name,h)];summary[name]['horizons'][str(h)]={'available':len(values),'gross_mean':statistics.fmean(values) if values else None,'positive_gross':sum(x>0 for x in values),'net_mean_by_roundtrip_bps':{str(b):statistics.fmean(x-b/10000 for x in values) if values else None for b in COSTS_BPS},'positive_after_10bps':sum(x-0.001>0 for x in values)}
 return {'results':output,'summary':summary}
def load(db):
 source=build(db);rows=db.execute('select open_ms,full_row_json from bars order by open_ms').fetchall();bars=[]
 for ms,raw in rows:
  row=json.loads(raw);bars.append((ms,float(row[1]),float(row[4])))
 calc=evaluate(bars,source['signals'])
 return {'mode':'historical_research_not_live','dataset':source['dataset'],'method':{'signal':'closed-bar, strict crossings with common 50 bar warmup','entry':'next bar open, idealized proxy not guaranteed fill','exit':'close after 1, 4, or 24 bars','cost_scenarios_bps_roundtrip':COSTS_BPS,'costs':'simple fixed subtraction, not actual exchange fees or live spread/slippage','position_overlap':'each signal measured independently, not a portfolio','mt5_equivalence':'unverified','trading':'none','datetime_discrepancy':'retrieval/server clock conflicts with trusted session date; historical bars precede session date; not independently certified'},**calc}
def main():
 p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--output',required=True);a=p.parse_args();db=sqlite3.connect('file:'+a.db+'?mode=ro',uri=True);x=load(db);db.close()
 with open(a.output,'x') as f:json.dump(x,f,indent=2,allow_nan=False)
 print(json.dumps({'dataset':x['dataset'],'summary':x['summary']}))
if __name__=='__main__':main()
