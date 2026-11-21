#!/usr/bin/env python3
"""
fetch_thai_panel.py — SET (Thailand) daily panel, free and key-less.

Why: the pack was 100% US assets. If the system is going to run from a phone in Bangkok, the local market
has to be in it, otherwise every answer has to be translated through a US proxy.

Verified route (2026-11-21): Yahoo chart v8 with the `.BK` suffix works for individual SET names
(PTT.BK returns 2,427 daily bars back to 2016-11). The SET *index* itself (^SET, ^SET.BK) returns a single
bar, so no index history is available from this source — the panel therefore builds its OWN equal-weight
index (`SET_EW`), which is honest as long as its construction is stated (see the manifest).

Uncertainty written down:
  * Yahoo `.BK` prices are in THB, unadjusted for the local dividend culture (SET yields ~3%), so
    total-return studies need the dividends separately — this panel is price-only.
  * The ticker list is hand-written from the liquid SET50/SET100 names. Names that were delisted, renamed
    or never listed simply return 404 and are recorded as such; there is no survivorship correction,
    because the list is a snapshot of today's liquid names.
  * Yahoo's Thai coverage has gaps around holidays that differ from US holidays; the calendar here is
    whatever Yahoo returns, which is correct for the SET but means the panel cannot be aligned naively
    with US data.
  * Foreign-board / DR / ETF listings (e.g. THD in the US panel) are different instruments — not merged.

Outputs
  data/thai/{SYMBOL}.csv            date, open, high, low, close, volume (THB)
  data/thai/SET_EW.csv              equal-weight index built from the constituents that traded that day
  data/thai/MANIFEST_THAI.json      per-symbol status, rows, date range, index construction
"""
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "thai"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

# Liquid SET names (SET50/SET100 core). Wrong or delisted tickers simply 404 and are reported.
TICKERS = [
    "ADVANC", "AOT", "AWC", "BAM", "BBL", "BDMS", "BEM", "BGRIM", "BH", "BJC", "BLA", "CBG", "COM7",
    "CPALL", "CPF", "CPN", "CRC", "DELTA", "DOHOME", "EA", "EGCO", "ERW", "GLOBAL", "GPSC", "GULF",
    "HMPRO", "INTUCH", "IRPC", "IVL", "JMT", "KBANK", "KCE", "KKP", "KTB", "KTC", "LH", "MEGA",
    "MINT", "MTC", "OR", "OSP", "PLANB", "PTT", "PTTEP", "PTTGC", "RATCH", "SAWAD", "SCB", "SCC",
    "SCGP", "SISB", "SPRC", "STA", "TASCO", "TCAP", "THG", "TIDLOR", "TISCO", "TOP", "TRUE", "TU",
    "TVO", "TTB", "VGI", "WHA",
]


def chart(sym, rng="10y", tries=3):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}.BK"
           f"?range={rng}&interval=1d&includeAdjustedClose=true")
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=45) as r:
                j = json.loads(r.read().decode("utf-8", "replace"))
            res = (j.get("chart") or {}).get("result") or []
            if not res:
                return None, "no result"
            res = res[0]
            ts = res.get("timestamp") or []
            q = ((res.get("indicators") or {}).get("quote") or [{}])[0]
            if not ts:
                return None, "no timestamps"
            df = pd.DataFrame({"date": pd.to_datetime(ts, unit="s", utc=True).tz_convert(None).normalize(),
                               "open": q.get("open"), "high": q.get("high"), "low": q.get("low"),
                               "close": q.get("close"), "volume": q.get("volume")})
            return df.dropna(subset=["close"]).reset_index(drop=True), "ok"
        except Exception as e:                                    # noqa: BLE001
            if a == tries - 1:
                return None, f"{type(e).__name__}: {e}"[:80]
            time.sleep(2 + 2 * a)
    return None, "unknown"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest, closes = {}, {}
    for i, t in enumerate(TICKERS, 1):
        df, status = chart(t)
        if df is None or len(df) < 250:
            manifest[t] = {"status": status, "rows": 0 if df is None else int(len(df))}
            print(f"  {t:<8} SKIP {status}")
            continue
        df.to_csv(OUT / f"{t}.csv", index=False)
        manifest[t] = {"status": "ok", "rows": int(len(df)),
                       "first": str(df["date"].iloc[0].date()), "last": str(df["date"].iloc[-1].date())}
        closes[t] = df.set_index("date")["close"]
        if i % 15 == 0:
            print(f"    {i}/{len(TICKERS)} …")
        time.sleep(0.35)

    if closes:
        px = pd.DataFrame(closes).sort_index()
        rets = px.pct_change()
        ew = (1 + rets.mean(axis=1).fillna(0)).cumprod() * 100.0
        ew.name = "SET_EW"
        ew.to_frame().to_csv(OUT / "SET_EW.csv")
        print(f"\n  SET_EW built from {len(closes)} names: {px.index[0].date()} .. {px.index[-1].date()} "
              f"({len(ew)} sessions)")
    (OUT / "MANIFEST_THAI.json").write_text(json.dumps({
        "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "Yahoo chart v8 with the .BK suffix; SET index history is NOT available (^SET returns 1 bar)",
        "requested": len(TICKERS), "ok": sum(1 for v in manifest.values() if v["status"] == "ok"),
        "index_construction": "SET_EW = equal-weight daily-rebalanced index of the constituents that "
                              "traded, base 100 = first common date. Cap-weighted SET50/SET are not "
                              "reproducible without the official membership and float data.",
        "caveats": ["Price-only, THB, no dividend adjustment (SET yields ~3%).",
                    "Ticker list is today's liquid names: survivorship applies.",
                    "Thai and US trading calendars differ; align on dates, never on row numbers."],
        "symbols": manifest}, indent=2))
    print(f"  -> {OUT/'MANIFEST_THAI.json'}")


if __name__ == "__main__":
    main()
