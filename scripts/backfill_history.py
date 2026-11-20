#!/usr/bin/env python3
"""
backfill_history.py — the daily collector only appends the LAST observation of each source, so every
dataset in data/collect/ starts today and gets useful only after months. This script fixes that for
the two sources where free deep history actually exists:

1. US Treasury daily yield curve, 1990 -> today, one request per calendar year
   (home.treasury.gov .../daily-treasury-rates.csv/{YYYY}/all?type=daily_treasury_yield_curve
    &field_tdr_date_value={YYYY}&page&_format=csv  -> verified 200, ~250 rows/year)
   This unlocks real bond-carry work: the term spread has 30+ years of history instead of 222 rows.

2. OKX perpetual candles + funding history, paginated with `after` (100 rows/call).
   history-candles gives ~9,500 hourly bars per symbol (~13 months); funding-rate-history gives ~3
   months per call and is paginated the same way.

Everything is idempotent: rows are merged and de-duplicated on the timestamp, sorted ascending.
Uncertainty, written down:
  * Treasury CSV is published with a one-day lag and is revised; the whole file is re-fetched each run
    so revisions land automatically. Do not treat it as point-in-time (it is a revision-free series).
  * OKX funding settles every 8h; hourly candles are exchange time (UTC). The funding history depth
    is limited by the endpoint, not by us — longer history would need paid data.
"""
import csv
import io
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
COLLECT = ROOT / "data" / "collect"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=45) as r:
                return r.read().decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            if i == tries - 1:
                raise
            time.sleep(1.5 + i)
    return ""


def backfill_treasury(start_year=1990):
    frames = []
    ok, fail = [], []
    for y in range(start_year, datetime.now(timezone.utc).year + 1):
        url = ("https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
               f"daily-treasury-rates.csv/{y}/all?type=daily_treasury_yield_curve"
               f"&field_tdr_date_value={y}&page&_format=csv")
        try:
            txt = get(url)
            if len(txt) < 100 or "Date" not in txt[:200]:
                fail.append(y)
                continue
            frames.append(pd.read_csv(inn := io.StringIO(txt)))
            ok.append(y)
        except Exception:  # noqa: BLE001
            fail.append(y)
        time.sleep(0.3)
    if not frames:
        print("  treasury: no data")
        return
    df = pd.concat(frames, ignore_index=True)
    df["Date"] = pd.to_datetime(df["Date"], format="%m/%d/%Y", errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date")
    df = df.drop_duplicates(subset=["Date"], keep="last")
    df = df.rename(columns={"1 Mo": "3m_proxy_1m", "3 Mo": "3 Mo", "2 Yr": "2 Yr", "10 Yr": "10 Yr"})
    out = COLLECT / "treasury_yield_curve_full.csv"
    df.to_csv(out, index=False)
    print(f"  treasury: {len(df)} rows {df['Date'].iloc[0].date()} .. {df['Date'].iloc[-1].date()} "
          f"({len(ok)} years ok, {len(fail)} failed: {fail})")


def okx(path, params):
    qs = "&".join(f"{k}={v}" for k, v in params.items())
    txt = get(f"https://www.okx.com{path}?{qs}")
    j = json.loads(txt)
    if j.get("code") != "0":
        raise RuntimeError(f"okx {j.get('code')} {j.get('msg')}")
    return j["data"]


def backfill_okx(inst="BTC-USDT", pages=100):
    deep = COLLECT / f"okx_{inst.replace('-', '')}_1h_deep.csv"
    if deep.exists():
        print(f"  okx {inst} candles: already backfilled ({deep.name}), skipping")
        rows = None
    else:
        rows = {}
    after = ""
    got = 0
    for _ in range(pages if rows is not None else 0):
        p = {"instId": inst, "bar": "1H", "limit": "100"}
        if after:
            p["after"] = after
        try:
            data = okx(" /api/v5/market/history-candles".strip(), p)
        except Exception as e:  # noqa: BLE001
            print(f"  okx candles stopped: {e}")
            break
        if not data:
            break
        for r in data:
            rows[r[0]] = r
        after = data[-1][0]
        got += len(data)
        time.sleep(0.12)
    if rows:
        recs = sorted(rows.values(), key=lambda r: int(r[0]))
        out = COLLECT / f"okx_{inst.replace('-', '')}_1h_deep.csv"
        with open(out, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["ts", "o", "h", "l", "c", "vol", "volCcy", "volCcyQuote", "confirm"])
            for r in recs:
                ts = datetime.fromtimestamp(int(r[0]) / 1000, tz=timezone.utc).isoformat()
                w.writerow([ts] + r[1:])
        print(f"  okx {inst} candles: {len(recs)} bars "
              f"{datetime.fromtimestamp(int(recs[0][0])/1000, tz=timezone.utc).date()} .. "
              f"{datetime.fromtimestamp(int(recs[-1][0])/1000, tz=timezone.utc).date()}")

    # funding history
    frows = {}
    after = ""
    for _ in range(pages):
        # NOTE: funding-rate-history requires the SWAP instrument id ("BTC-USDT-SWAP"), while
        # candles use the spot id. Passing the spot id returns code 51000 "Parameter instId error".
        p = {"instId": f"{inst}-SWAP", "limit": "100"}
        if after:
            p["after"] = after
        try:
            data = okx("/api/v5/public/funding-rate-history", p)
        except Exception as e:  # noqa: BLE001
            print(f"  okx funding stopped: {e}")
            break
        if not data:
            break
        for r in data:
            frows[r["fundingTime"]] = r
        after = data[-1]["fundingTime"]
        time.sleep(0.12)
    if frows:
        recs = sorted(frows.values(), key=lambda r: int(r["fundingTime"]))
        out = COLLECT / f"okx_{inst.replace('-', '')}_funding_deep.csv"
        with open(out, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["ts", "fundingRate", "realizedRate", "method"])
            for r in recs:
                ts = datetime.fromtimestamp(int(r["fundingTime"]) / 1000, tz=timezone.utc).isoformat()
                w.writerow([ts, r.get("fundingRate"), r.get("realizedRate", ""), r.get("method", "")])
        print(f"  okx {inst} funding: {len(recs)} settlements "
              f"{datetime.fromtimestamp(int(recs[0]['fundingTime'])/1000, tz=timezone.utc).date()} .. "
              f"{datetime.fromtimestamp(int(recs[-1]['fundingTime'])/1000, tz=timezone.utc).date()}")


def main(skip_treasury=False):
    COLLECT.mkdir(parents=True, exist_ok=True)
    if not skip_treasury:
        print("backfilling Treasury yield curve 1990->today")
        backfill_treasury(1990)
    print("backfilling OKX candles + funding")
    for inst in ("BTC-USDT", "ETH-USDT"):
        backfill_okx(inst)


if __name__ == "__main__":
    import sys
    main(skip_treasury="--funding-only" in sys.argv)
