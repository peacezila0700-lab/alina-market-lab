#!/usr/bin/env python3
"""
fetch_stock_panel.py — daily OHLC for individual equities, so the screener and the fundamental layer have
prices to attach to.

The pack's price files were all ETFs/indices/futures. Without single-stock series, three of the owner's
categories cannot be answered at all ("is this company cheap", "did earnings justify the move", "screen
for X"), and any cross-sectional test is limited to 68 ETFs. This fetches the top N US names by market cap
from the Nasdaq screener, using the same Yahoo chart route already proven for the broad panel.

Route: https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range=10y&interval=1d  (no key)
  -> result[0].timestamp[], indicators.quote[0].{open,high,low,close,volume},
     indicators.adjclose[0].adjclose

Uncertainty written down:
  * Yahoo is unofficial and rate-limits; we sleep between calls and record a per-symbol status. A 429 is
    recorded as RATE_LIMITED, never as "no data" (incident QR-001 in this repo).
  * 10 years of history is requested, so a long-history study on individual names is not possible here.
  * Splits/dividends are reflected in adjclose only; `close` is the raw print. Mixing the two across
    files is a real bug source — both are stored so the choice is explicit.
  * Survivorship: the list is today's largest companies. Any cross-sectional study on it is biased
    upward; say so in every result.

Outputs
  data/stocks/{SYMBOL}.csv          date, open, high, low, close, adjclose, volume
  data/stocks/MANIFEST_STOCKS.json  per-symbol status, rows, first/last date
"""
import argparse
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "stocks"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def get_json(url, tries=3, timeout=45):
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception as e:                                   # noqa: BLE001
            if "429" in str(e) or "Too Many" in str(e):
                time.sleep(6 + 6 * a)
                continue
            if a == tries - 1:
                return {"__err__": f"{type(e).__name__}: {e}"}
            time.sleep(1.5 + 2 * a)
    return {"__err__": "RATE_LIMITED"}


def chart(sym, rng="10y"):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
           f"?range={rng}&interval=1d&includeAdjustedClose=true")
    j = get_json(url)
    if not j or "__err__" in j:
        return None, (j or {}).get("__err__", "empty")
    res = (j.get("chart") or {}).get("result") or []
    if not res:
        return None, "no result"
    r = res[0]
    ts = r.get("timestamp") or []
    q = ((r.get("indicators") or {}).get("quote") or [{}])[0]
    adj = ((r.get("indicators") or {}).get("adjclose") or [{}])[0].get("adjclose")
    if not ts:
        return None, "no timestamps"
    df = pd.DataFrame({
        "date": pd.to_datetime(ts, unit="s", utc=True).tz_convert(None).normalize(),
        "open": q.get("open"), "high": q.get("high"), "low": q.get("low"),
        "close": q.get("close"), "volume": q.get("volume"),
        "adjclose": adj if adj is not None else q.get("close")})
    return df.dropna(subset=["close"]).reset_index(drop=True), "ok"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=120)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    scr = pd.read_csv(ROOT / "data" / "screener" / "nasdaq_all.csv")
    scr = scr.dropna(subset=["market_cap"]).sort_values("market_cap", ascending=False)
    # keep plain US listings only: no warrants/units/preferred suffixes
    scr = scr[scr["symbol"].astype(str).str.match(r"^[A-Z]{1,5}$")]
    syms = list(dict.fromkeys(scr["symbol"].head(args.top)))

    manifest = {}
    ok = 0
    for i, sym in enumerate(syms, 1):
        df, status = chart(sym)
        if df is None or len(df) < 250:
            manifest[sym] = {"status": status, "rows": 0}
            print(f"  {sym:<6} FAIL {status}")
            continue
        df.to_csv(OUT / f"{sym}.csv", index=False)
        manifest[sym] = {"status": "ok", "rows": int(len(df)),
                         "first": str(df["date"].iloc[0].date()), "last": str(df["date"].iloc[-1].date())}
        ok += 1
        if i % 20 == 0:
            print(f"    {i}/{len(syms)} … ({ok} ok)")
        time.sleep(0.35)

    (OUT / "MANIFEST_STOCKS.json").write_text(json.dumps({
        "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "Yahoo chart v8, interval=1d, range=10y, no key",
        "requested": len(syms), "ok": ok, "symbols": manifest,
        "caveats": ["Today's largest companies only: survivorship bias is built in.",
                    "10-year history ceiling; no long-cycle study on single names.",
                    "`close` is the raw print, `adjclose` adjusts for splits/dividends — pick one "
                    "deliberately, never mix within a study."]}, indent=2))
    print(f"\n  stocks: {ok}/{len(syms)} saved -> {OUT}")


if __name__ == "__main__":
    main()
