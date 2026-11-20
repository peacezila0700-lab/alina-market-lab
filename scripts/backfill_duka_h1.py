#!/usr/bin/env python3
"""
backfill_duka_h1.py — hourly BID and ASK candles from Dukascopy's public chart endpoint, 2003 -> now.

Why this is the most valuable data addition for hour-scale work: it is the only free source that gives
both sides of the quote, so hour-of-day spread widening, real fill costs and latency effects can be
measured instead of assumed. Verified behaviour (2026-11-20):

  GET https://freeserv.dukascopy.com/2.0/index.php?path=chart%2Fjson3
      &instrument=EUR%2FUSD&offer_side=B|A&interval=1HOUR&splits=true&stocks=true
      &time_direction=P&timestamp=<ms>&jsonp=cb
  -> JSONP `cb([...])`, exactly 30,000 bars per call, descending from <ms>.
  -> Row layout is [ts_ms, open, high, low, close, volume]. Verified empirically: treating col 1..4 as
     OHLC satisfies high>=max(open,close) and low<=min(open,close) for 100.0% of bars (the alternative
     open/close/low/high layout fails on 99.3% of bars). The binary tick feed uses open,close,low,high
     — the JSON does NOT. Do not "harmonise" the two.

Output: data/intraday/{PAIR}_H1_bidask.csv with
  ts_utc, bid_o, bid_h, bid_l, bid_c, ask_o, ask_h, ask_l, ask_c, spread_close_pips, spread_mean_of_bar_pips
where spread_mean_of_bar_pips uses (bid_h+bid_l)/2 vs (ask_h+ask_l)/2 as a conservative mid — it is an
approximation, because only the bar extremes carry the quote, not every tick.

Uncertainty written down:
  * Dukascopy quotes are a broker's own feed, not the interbank market; absolute spreads are optimistic
    versus a retail account (no commission, no slippage). Treat measured spreads as a FLOOR.
  * Weekend flat hours are present as bars with zero volume and constant price; they are dropped when
    volume == 0 to avoid fake zero returns.
  * Rate limit: ~2 requests/second is safe; a full 6-pair, both-sides, 2003->now backfill is ~60 calls.
"""
import json
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "intraday"
UA = "Mozilla/5.0 (X11; Linux x86_64)"
PAIRS = ["EURUSD", "EURGBP", "GBPUSD", "EURCHF", "USDJPY", "XAUUSD"]
START_YEAR = 2003
N_BARS = 30000


def fetch(sym, side, ts_ms, tries=3):
    inst = sym[:3] + "%2F" + sym[3:]
    url = ("https://freeserv.dukascopy.com/2.0/index.php?path=chart%2Fjson3"
           f"&instrument={inst}&offer_side={side}&interval=1HOUR&splits=true&stocks=true"
           f"&time_direction=P&timestamp={ts_ms}&jsonp=cb")
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                              "Referer": "https://freeserv.dukascopy.com/"})
    for a in range(tries):
        try:
            txt = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
            m = re.search(r"cb\((.*)\)\s*;?\s*$", txt, re.S)
            return json.loads(m.group(1)) if m else []
        except Exception:                                        # noqa: BLE001
            time.sleep(2 + 3 * a)
    return None


def side_frame(sym, side):
    stop_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    floor_ms = int(datetime(START_YEAR, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    rows = {}
    calls = 0
    while stop_ms > floor_ms and calls < 12:
        data = fetch(sym, side, stop_ms)
        calls += 1
        if data is None:
            print(f"    {sym} {side}: fetch failed, stopping")
            break
        if not data:
            break
        for r in data:
            rows[int(r[0])] = (float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5]))
        oldest = int(data[-1][0])
        if oldest >= stop_ms:          # no progress
            break
        stop_ms = oldest - 1
        time.sleep(0.45)
    print(f"    {sym} {side}: {len(rows)} bars in {calls} calls")
    return rows


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    summary = {}
    for sym in PAIRS:
        bid = side_frame(sym, "B")
        ask = side_frame(sym, "A")
        if not bid or not ask:
            summary[sym] = "FAIL"
            continue
        common = sorted(set(bid) & set(ask))
        recs = []
        for ts in common:
            bo, bh, bl, bc, bv = bid[ts]
            ao, ah, al, ac, av = ask[ts]
            pip = 0.01 if sym.endswith("JPY") or sym == "XAUUSD" else 0.0001
            if sym == "XAUUSD":
                pip = 0.01
            sp_close = (ac - bc) / pip
            mid_b = (bh + bl) / 2
            mid_a = (ah + al) / 2
            sp_mean = (mid_a - mid_b) / pip
            if bv <= 0:
                continue
            recs.append((datetime.fromtimestamp(ts / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                         bo, bh, bl, bc, ao, ah, al, ac, round(sp_close, 3), round(sp_mean, 3)))
        df = pd.DataFrame(recs, columns=["ts_utc", "bid_o", "bid_h", "bid_l", "bid_c",
                                         "ask_o", "ask_h", "ask_l", "ask_c",
                                         "spread_close_pips", "spread_mean_of_bar_pips"])
        path = OUT / f"{sym}_H1_bidask.csv"
        df.to_csv(path, index=False)
        med = float(df["spread_close_pips"].median())
        summary[sym] = {"rows": len(df), "first": df["ts_utc"].iloc[0], "last": df["ts_utc"].iloc[-1],
                        "median_spread_pips": med,
                        "median_spread_by_hour_utc": {
                            str(h): round(float(v), 3) for h, v in
                            df.assign(h=pd.to_datetime(df["ts_utc"]).dt.hour)
                              .groupby("h")["spread_close_pips"].median().items()}}
        print(f"  {sym}: {len(df)} bars {df['ts_utc'].iloc[0][:10]} .. {df['ts_utc'].iloc[-1][:10]}  "
              f"median spread {med:.2f} pips")
    (OUT / "MANIFEST_H1_BIDASK.json").write_text(json.dumps(
        {"built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "source": "dukascopy freeserv chart/json3, offer_side B and A, interval 1HOUR",
         "layout": "[ts, open, high, low, close, volume]; verified OHLC order empirically",
         "pairs": summary}, indent=2))
    print(f"\n  -> {OUT/'MANIFEST_H1_BIDASK.json'}")


if __name__ == "__main__":
    main()
