#!/usr/bin/env python3
"""CFTC Commitments of Traders — who is actually long and short (the "big money" layer).

Source: CFTC Public Reporting Environment (Socrata), dataset 6dca-aqww = Legacy, Futures Only.
Free, no key, weekly since 1986, published Friday for Tuesday's positions.

Why this matters for a trading AI: price tells you *what* happened, COT tells you *who* did it.
Commercials (producers/consumers) vs non-commercials (funds/speculators) vs non-reportable
(small traders). Extreme positioning is the classic contrarian input; whether it works is a
separate question that must be tested (see knowledge/IDEAS_TO_TEST.md).

Published-lag note (critical, prevents look-ahead): positions are as of Tuesday close but are
only public on Friday ~15:30 ET. Any backtest must use `available_from` (the Friday), never the
`report_date`. Both columns are written out so a consumer cannot accidentally cheat.

Outputs:
  data/cot/cot_weekly.csv     one row per contract-week (compact columns + derived)
  data/cot/MANIFEST_COT.json  provenance + row counts + lag rule
"""
from __future__ import annotations

import csv
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "cot")
os.makedirs(OUT, exist_ok=True)
BASE = "https://publicreporting.cftc.gov/resource/6dca-aqww.json"
UA = "Mozilla/5.0 (compatible; alina-market-lab research)"

# contract name -> our instrument label
CONTRACTS = {
    "EURO FX": "EURUSD", "BRITISH POUND": "GBPUSD", "JAPANESE YEN": "USDJPY",
    "SWISS FRANC": "USDCHF", "CANADIAN DOLLAR": "USDCAD", "AUSTRALIAN DOLLAR": "AUDUSD",
    "NZ DOLLAR": "NZDUSD", "MEXICAN PESO": "USDMXN",
    "S&P 500 Consolidated": "SP500", "NASDAQ-100 Consolidated": "NASDAQ100",
    "VIX FUTURES": "VIX",
    "GOLD": "GOLD", "SILVER": "SILVER", "COPPER- #1": "COPPER", "PLATINUM": "PLATINUM",
    "CRUDE OIL, LIGHT SWEET-WTI": "WTI", "WTI FINANCIAL CRUDE OIL": "WTI_FINANCIAL",
    "NAT GAS NYME": "NATGAS",
    "CORN": "CORN", "WHEAT-SRW": "WHEAT",
    "UST BOND": "UST_BOND", "UST 10Y NOTE": "UST_10Y",
    "BITCOIN": "BTC", "ETHER CASH SETTLED": "ETH",
}
FIELDS = [
    "report_date_as_yyyy_mm_dd", "contract_market_name", "market_and_exchange_names",
    "open_interest_all", "noncomm_positions_long_all", "noncomm_positions_short_all",
    "noncomm_postions_spread_all", "comm_positions_long_all", "comm_positions_short_all",
    "nonrept_positions_long_all", "nonrept_positions_short_all",
    "traders_tot_all", "traders_noncomm_long_all", "traders_noncomm_short_all",
    "conc_net_le_4_tdr_long_all", "conc_net_le_4_tdr_short_all",
    "commodity_group_name", "commodity_subgroup_name", "contract_units",
]


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def fetch(contract: str) -> list[dict]:
    q = {
        "$select": ",".join(FIELDS),
        "$where": f"contract_market_name='{contract}'",
        "$order": "report_date_as_yyyy_mm_dd",
        "$limit": "50000",
    }
    url = BASE + "?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read())
        except Exception as e:                                    # noqa: BLE001
            print(f"    retry {attempt + 1}: {e}")
            time.sleep(3 * (attempt + 1))
    return []


def available_from(report: date) -> str:
    """COT is published the Friday after the Tuesday as-of date (15:30 ET)."""
    d = report
    while d.weekday() != 4:                # next Friday
        d += timedelta(days=1)
    return d.isoformat()


def main() -> None:
    rows: list[dict] = []
    manifest = {"source": BASE, "dataset": "Legacy Futures Only (6dca-aqww)",
                "fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "lag_rule": "positions as of Tuesday; public Friday 15:30 ET -> use available_from",
                "contracts": {}}
    for contract, label in CONTRACTS.items():
        data = fetch(contract)
        if not data:
            print(f"  {contract}: NOTHING")
            manifest["contracts"][contract] = {"rows": 0, "label": label}
            continue
        per = 0
        for r in data:
            rep = (r.get("report_date_as_yyyy_mm_dd") or "")[:10]
            if not rep:
                continue
            oi = num(r.get("open_interest_all"))
            ncl, ncs = num(r.get("noncomm_positions_long_all")), num(r.get("noncomm_positions_short_all"))
            cl, cs = num(r.get("comm_positions_long_all")), num(r.get("comm_positions_short_all"))
            rl, rs = num(r.get("nonrept_positions_long_all")), num(r.get("nonrept_positions_short_all"))
            nc_net = (ncl - ncs) if (ncl is not None and ncs is not None) else None
            cm_net = (cl - cs) if (cl is not None and cs is not None) else None
            nr_net = (rl - rs) if (rl is not None and rs is not None) else None
            rows.append({
                "report_date": rep,
                "available_from": available_from(date.fromisoformat(rep)),
                "instrument": label, "contract": contract,
                "open_interest": oi,
                "noncomm_long": ncl, "noncomm_short": ncs,
                "noncomm_net": nc_net,
                "noncomm_net_pct_oi": round(nc_net / oi * 100, 3) if (nc_net is not None and oi) else None,
                "comm_long": cl, "comm_short": cs, "comm_net": cm_net,
                "nonrept_net": nr_net,
                "traders_total": num(r.get("traders_tot_all")),
                "conc_net_top4_long_pct": num(r.get("conc_net_le_4_tdr_long_all")),
                "conc_net_top4_short_pct": num(r.get("conc_net_le_4_tdr_short_all")),
                "group": r.get("commodity_group_name"), "subgroup": r.get("commodity_subgroup_name"),
                "units": r.get("contract_units"),
            })
            per += 1
        manifest["contracts"][contract] = {"rows": per, "label": label,
                                           "first": min((x["report_date"] for x in rows[-per:]), default=None),
                                           "last": max((x["report_date"] for x in rows[-per:]), default=None)}
        print(f"  {label:14} ({contract}): {per} weeks  {manifest['contracts'][contract]['first']}..{manifest['contracts'][contract]['last']}")
        time.sleep(0.4)

    rows.sort(key=lambda r: (r["instrument"], r["report_date"]))
    path = os.path.join(OUT, "cot_weekly.csv")
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    manifest["total_rows"] = len(rows)
    manifest["instruments"] = sorted({r["instrument"] for r in rows})
    with open(os.path.join(OUT, "MANIFEST_COT.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nwrote {path}: {len(rows)} rows, {len(manifest['instruments'])} instruments")


if __name__ == "__main__":
    main()
