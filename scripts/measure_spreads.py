#!/usr/bin/env python3
"""T18 — MEASURE the spread instead of assuming it.

Source: Dukascopy public chart API (`freeserv.dukascopy.com/2.0/index.php`), queried twice per
instrument — once with `offer_side=B` (bid) and once with `offer_side=A` (ask). Aligning the two
by timestamp gives a real quoted spread per bar. Free, no key, no signup, history back to 2003.

Requires the URL-encoded form (`path=chart%2Fjson3`, `instrument=EUR%2FUSD`) — the un-encoded
variant returns `_callbacks____error([null])`. The .bi5 datafeed host is currently 503 and is not
used.

Output:
  data/spreads/{SYM}_hourly.csv   year, bars, median_spread_pips, mean_spread_pips, price_median
  data/spreads/MEASURED_COSTS.json  per-instrument half-spread in % of notional (the cost model unit)
  reports/MEASURED_SPREADS.md
"""
from __future__ import annotations

import csv
import json
import os
import re
import statistics
import time
import urllib.request
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "spreads")
REP = os.path.join(ROOT, "reports")
os.makedirs(OUT, exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122 Safari/537.36"

JPY_PAIRS = {"USDJPY", "EURJPY", "GBPJPY", "AUDJPY", "CHFJPY"}
INSTRUMENTS = ["EURUSD", "EURJPY", "EURGBP", "EURCHF", "EURCAD",
               "EURSEK", "EURNOK", "EURAUD", "EURNZD", "GBPUSD"]

# 30,000 hourly bars per call ≈ 4.5 years; four anchor timestamps cover 2003 → now
ANCHORS = [1750000000000, 1600000000000, 1450000000000, 1300000000000, 1150000000000]


def _bytes_to_json(txt: str):
    m = re.search(r"cb\((.*)\)\s*;?\s*$", txt, re.S)
    return json.loads(m.group(1)) if m else None


def bars(sym: str, side: str, ts: int) -> list:
    inst = sym[:3] + "%2F" + sym[3:]
    url = ("https://freeserv.dukascopy.com/2.0/index.php?path=chart%2Fjson3"
           f"&instrument={inst}&offer_side={side}&interval=1HOUR&splits=true&stocks=true"
           f"&time_direction=P&timestamp={ts}&jsonp=cb")
    req = urllib.request.Request(url, headers={"User-Agent": UA,
                                               "Referer": "https://freeserv.dukascopy.com/"})
    for attempt in range(3):
        try:
            return _bytes_to_json(urllib.request.urlopen(req, timeout=40).read().decode()) or []
        except Exception:                                        # noqa: BLE001
            time.sleep(2 + 3 * attempt)
    return []


def pip_size(sym: str) -> float:
    return 0.01 if sym in JPY_PAIRS else 0.0001


def measure(sym: str) -> list[dict]:
    """Per calendar year: median quoted spread in pips, from aligned bid/ask hourly closes."""
    spreads: dict[int, list[float]] = {}
    prices: dict[int, list[float]] = {}
    for ts in ANCHORS:
        b = bars(sym, "B", ts)
        time.sleep(0.4)
        a = bars(sym, "A", ts)
        time.sleep(0.4)
        if not a or not b:
            continue
        amap = {row[0]: row[1] for row in a}          # timestamp -> ask close
        for row in b:
            t, bid_close = row[0], row[1]
            ask_close = amap.get(t)
            if not ask_close or not bid_close or ask_close < bid_close:
                continue
            year = datetime.utcfromtimestamp(t / 1000).year
            spreads.setdefault(year, []).append((ask_close - bid_close) / pip_size(sym))
            prices.setdefault(year, []).append((ask_close + bid_close) / 2)
    rows = []
    for y in sorted(spreads):
        s = spreads[y]
        if len(s) < 200:
            continue
        rows.append({"year": y, "bars": len(s),
                     "median_spread_pips": round(statistics.median(s), 3),
                     "mean_spread_pips": round(statistics.fmean(s), 3),
                     "price_median": round(statistics.median(prices[y]), 5)})
    return rows


def main() -> None:
    costs: dict[str, dict] = {}
    md = ["# MEASURED SPREADS — Dukascopy bid/ask, hourly closes, 2003–2026\n",
          "Every quoted spread here is **ask minus bid observed in real tick-derived bars**, not an "
          "assumption. Half of it is the one-way cost our cost model charges per unit turnover.\n",
          "Caveat that matters: this is **one ECN venue**. A retail MT5 'standard' account is wider "
          "(typically 0.8–1.5 pips on EURUSD); 'raw/ECN + commission' accounts land near these "
          "numbers once commission is added back. T18 is complete only when the owner's own export "
          "is measured.\n"]

    for sym in INSTRUMENTS:
        rows = measure(sym)
        if not rows:
            print(f"  {sym}: no data")
            continue
        p = os.path.join(OUT, f"{sym}_hourly.csv")
        with open(p, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)

        # recent-era cost (2019+) expressed as half-spread % of notional
        recent = [r for r in rows if r["year"] >= 2019]
        if not recent:
            recent = rows[-3:]
        half_pct = statistics.median(
            [(r["median_spread_pips"] * pip_size(sym) / r["price_median"]) / 2 for r in recent]) * 100
        allmed = statistics.median([r["median_spread_pips"] for r in recent])
        costs[sym] = {
            "median_spread_pips_2019plus": round(allmed, 3),
            "half_spread_pct_of_notional": round(half_pct, 5),
            "years_covered": [r["year"] for r in rows],
            "spread_by_year_pips": {r["year"]: r["median_spread_pips"] for r in rows},
        }
        print(f"  {sym}: {rows[0]['year']}–{rows[-1]['year']}, recent median {allmed:.2f} pips, "
              f"half-spread {half_pct:.4f}% of notional")

    with open(os.path.join(OUT, "MEASURED_COSTS.json"), "w") as f:
        json.dump({"generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "source": "freeserv.dukascopy.com chart/json3, offer_side B vs A",
                   "costs": costs}, f, indent=2)

    md.append("## Recent-era spread (median of yearly medians, 2019+)\n")
    md.append("| Instrument | spread (pips) | half-spread % of notional | vs our H09 assumption 0.013% |")
    md.append("|---|---:|---:|---:|")
    for s, c in costs.items():
        ratio = 0.013 / c["half_spread_pct_of_notional"] if c["half_spread_pct_of_notional"] else 0
        md.append(f"| {s} | {c['median_spread_pips_2019plus']} | {c['half_spread_pct_of_notional']}% | "
                  f"{ratio:.1f}× cheaper |")
    md.append("\n## Spread by year (pips, median of hourly bars)\n")
    years = sorted({y for c in costs.values() for y in c["spread_by_year_pips"]})
    md.append("| Instrument | " + " | ".join(str(y) for y in years) + " |")
    md.append("|---|" + "---:|" * len(years))
    for s, c in costs.items():
        md.append(f"| {s} | " + " | ".join(str(c["spread_by_year_pips"].get(y, "—"))
                                           for y in years) + " |")
    with open(os.path.join(REP, "MEASURED_SPREADS.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    print("wrote reports/MEASURED_SPREADS.md + data/spreads/MEASURED_COSTS.json")


if __name__ == "__main__":
    main()
