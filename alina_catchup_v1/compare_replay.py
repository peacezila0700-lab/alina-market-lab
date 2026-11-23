#!/usr/bin/env python3
"""Retrospective closed-price research only; no positions or execution."""
import argparse,datetime,hashlib,json,math,sqlite3,statistics
HOUR=3600000;HORIZONS=(1,4,24)
def sign(x):return 1 if x>0 else -1 if x<0 else 0
def cci(values,n=14):
 a=values[-n:];avg=sum(a)/n;dev=sum(abs(v-avg) for v in a)/n;return (a[-1]-avg)/(0.015*dev) if dev else 0.0
def wilder_rsi(values,n=14):
 if len(values)<n+1:return None
 # Warm from the start of the series; start point affects RSI. This is not MT5-validated.
 d=[values[i]-values[i-1] for i in range(1,len(values))];g=sum(max(x,0) for x in d[:n])/n;l=sum(max(-x,0) for x in d[:n])/n
 for x in d[n:]:g=(g*(n-1)+max(x,0))/n;l=(l*(n-1)+max(-x,0))/n
 if l==0:return 100.0 if g else 50.0
 return 100-100/(1+g/l)
def rsi_series(values,n=14):
 result=[None]*len(values)
 if len(values)<=n:return result
 changes=[values[i]-values[i-1] for i in range(1,len(values))]
 gain=sum(max(x,0) for x in changes[:n])/n;loss=sum(max(-x,0) for x in changes[:n])/n
 def value():return (100.0 if gain else 50.0) if loss==0 else 100-100/(1+gain/loss)
 result[n]=value()
 for i in range(n+1,len(values)):
  delta=changes[i-1];gain=(gain*(n-1)+max(delta,0))/n;loss=(loss*(n-1)+max(-delta,0))/n;result[i]=value()
 return result

def signals(bars):
 if len(bars)<51:raise ValueError('need at least 51 contiguous bars')
 if any(bars[i][0]-bars[i-1][0]!=HOUR for i in range(1,len(bars))):raise ValueError('gap, duplicate or disorder')
 p=[b[1] for b in bars]
 if any(not math.isfinite(x) or x<=0 for x in p):raise ValueError('invalid price')
 # Fixed warm-up of 50 bars for a comparable evaluation interval. Signals are based exclusively on prior/current closes.
 out=[];rsi_values=rsi_series(p);rsi_previous=rsi_values[49];cci_previous=cci(p[36:50]);sma_previous=sum(p[30:50])/20
 for i in range(50,len(p)):
  cur_cci=cci(p[i-13:i+1]);cur_rsi=rsi_values[i];cur_sma=sum(p[i-19:i+1])/20
  decisions={'CCI14_zero_cross':(cci_previous,cur_cci),'RSI14_50_cross':(rsi_previous-50,cur_rsi-50),'CLOSE_SMA20_cross':(p[i-1]-sma_previous,p[i]-cur_sma)}
  for name,(a,b) in decisions.items():
   direction='buy' if a<0 and b>0 else 'sell' if a>0 and b<0 else None
   if direction:
    ev={'indicator':name,'direction':direction,'bar_open_ms':bars[i][0],'signal_close':p[i],'outcomes':{}}
    for h in HORIZONS:
     if i+h<len(p):ev['outcomes'][str(h)]={'next_close':p[i+h],'gross_directional_return':(p[i+h]/p[i]-1)*(1 if direction=='buy' else -1)}
    out.append(ev)
  cci_previous=cur_cci;rsi_previous=cur_rsi;sma_previous=cur_sma
 return out

def build(db):
 # Refuse ambiguous versions across jobs, uncommitted datasets or timestamp gaps.
 if db.execute("select count(*) from jobs where status != 'complete'").fetchone()[0]:raise ValueError('incomplete catchup jobs; isolated snapshot required')
 for page_id,raw,sha in db.execute('select id,raw_json,raw_sha256 from pages'):
  if hashlib.sha256(raw.encode()).hexdigest()!=sha:raise ValueError('source page hash mismatch')
  page={int(row[0]):json.dumps(row,separators=(',',':'),allow_nan=False) for row in json.loads(raw)}
  for open_ms,bar in db.execute('select open_ms,full_row_json from bars where first_page_id=?',(page_id,)):
   if page.get(open_ms)!=bar:raise ValueError('bar differs from first source page')
 rows=db.execute('select open_ms,full_row_json from bars order by open_ms').fetchall();bars=[(int(t),float(json.loads(raw)[4])) for t,raw in rows];events=signals(bars);summary={} 
 for name in ('CCI14_zero_cross','RSI14_50_cross','CLOSE_SMA20_cross'):
  group=[e for e in events if e['indicator']==name];stats={}
  for h in HORIZONS:
   vals=[e['outcomes'][str(h)]['gross_directional_return'] for e in group if str(h) in e['outcomes']]
   stats[str(h)]={'available':len(vals),'positive':sum(v>0 for v in vals),'negative':sum(v<0 for v in vals),'flat':sum(v==0 for v in vals),'mean_gross_directional_return':statistics.fmean(vals) if vals else None}
  summary[name]={'signals':len(group),'horizons_bars':stats}
 return {'mode':'historical_replay_not_live','dataset':{'symbol':'BTCUSDT','timeframe':'1h','bars':len(bars),'first_open_ms':bars[0][0],'last_open_ms':bars[-1][0],'provider':'data-api.binance.vision','raw_page_sha256':[r[0] for r in db.execute('select raw_sha256 from pages order by id')],'rights':'unknown'},'method':{'warmup_bars':50,'horizons_bars':HORIZONS,'rules':'strict crosses; close price only; RSI Wilder seeded from first bar','price_assumption':'signal bar close, not guaranteed executable','costs':'excluded','mt5_equivalence':'not verified','no_real_trades':True},'summary':summary,'signals':events}
def main():
 a=argparse.ArgumentParser();a.add_argument('--db',required=True);a.add_argument('--output',required=True);args=a.parse_args();db=sqlite3.connect('file:'+args.db+'?mode=ro',uri=True);r=build(db);db.close()
 with open(args.output,'x',encoding='utf-8') as f:json.dump(r,f,indent=2,allow_nan=False)
 print(json.dumps({'bars':r['dataset']['bars'],'summary':r['summary'],'mode':r['mode']}))
if __name__=='__main__':main()
