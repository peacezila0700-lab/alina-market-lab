#!/usr/bin/env python3
"""BROAD PANEL — a wide cross-section, so the research book has statistical power.

The 24-instrument panel was chosen for tradability. A research panel should be chosen for *variety*:
sectors, countries, credit tiers, commodities, crypto proxies. With ~60 series you can run
cross-sectional tests (rank X, hold Y) that are impossible on 5 instruments, and you can ask
"is this effect in the sector, the country, or the asset class?"

All series are daily Yahoo chart JSON (verified working, no key). Each file keeps date/open/high/
low/close/adjclose and the row count is recorded in MANIFEST_BROAD.json so gaps are visible.

Groups are labelled so a downstream model can condition on them without reading a dictionary.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from datetime import datetime, timezone

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "broad")
os.makedirs(OUT, exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"

PANEL = {
    # US sectors (the cleanest rotation instrument set)
    "XLK": "sector_tech", "XLF": "sector_fin", "XLE": "sector_energy", "XLV": "sector_health",
    "XLI": "sector_industrials", "XLP": "sector_staples", "XLY": "sector_discretionary",
    "XLU": "sector_utilities", "XLB": "sector_materials", "XLRE": "sector_reit",
    "XLC": "sector_comms",
    # country equity
    "EWJ": "country_japan", "EWG": "country_germany", "EWU": "country_uk", "EWC": "country_canada",
    "EWA": "country_australia", "EWZ": "country_brazil", "EWT": "country_taiwan",
    "EWY": "country_korea", "EWH": "country_hk", "INDA": "country_india", "FXI": "country_china",
    "EWW": "country_mexico", "THD": "country_thailand", "EIDO": "country_indonesia",
    "VNM": "country_vietnam", "EPU": "country_peru",
    # credit & rates
    "LQD": "credit_ig", "HYG": "credit_hy", "JNK": "credit_hy2", "SHY": "rates_1_3y",
    "IEF": "rates_7_10y", "TLH": "rates_10_20y", "TIP": "rates_tips", "BIL": "cash",
    "EMB": "credit_em", "MBB": "mbs",
    # commodities
    "GLD": "metal_gold", "SLV": "metal_silver", "CPER": "metal_copper", "PPLT": "metal_platinum",
    "USO": "energy_oil", "UNG": "energy_gas", "DBA": "agri_basket", "DBC": "commodity_basket",
    "URA": "energy_uranium", "LIT": "metal_lithium",
    # fx proxies & dollar
    "UUP": "fx_dollar", "FXE": "fx_euro", "FXY": "fx_yen", "FXB": "fx_pound",
    "FXA": "fx_aussie", "FXF": "fx_swiss", "FXM": "fx_mexico",
    # vol & tail
    "VIXY": "vol_short_term", "VXZ": "vol_mid_term", "SVXY": "vol_inverse",
    # crypto proxies and country risk
    "IBIT": "crypto_btc_proxy", "ETHE": "crypto_eth_proxy", "MSTR": "crypto_levered",
    "TUR": "country_turkey", "EZA": "country_southafrica", "ARGT": "country_argentin",
    # benchmarks
    "SPY": "benchmark_us", "QQQ": "benchmark_nasdaq", "IWM": "benchmark_smallcap",
    "DIA": "benchmark_dow", "ACWI": "benchmark_world", "EEM": "benchmark_em",
}


def fetch(sym: str) -> pd.DataFrame | None:
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
           f"?period1=946684800&period2={int(time.time())}&interval=1d&events=div%2Csplits")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=25) as r:
            j = json.loads(r.read())
        res = j["chart"]["result"][0]
        ts = res["timestamp"]
        q = res["indicators"]["quote"][0]
        df = pd.DataFrame({"date": pd.to_datetime(ts, unit="s").date, "open": q["open"], "high": q["high"],
                           "low": q["low"], "close": q["close"], "volume": q.get("volume")})
        if "adjclose" in res["indicators"]:
            df["adjclose"] = res["indicators"]["adjclose"][0]["adjclose"]
        return df.dropna(subset=["close"])
    except Exception as e:                                        # noqa: BLE001
        print(f"  {sym}: {e}")
        return None


def main() -> None:
    man = {"built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "source": "Yahoo chart v8, interval=1d, no key", "symbols": {}}
    ok = 0
    for sym, group in PANEL.items():
        df = fetch(sym)
        if df is None or len(df) < 200:
            man["symbols"][sym] = {"group": group, "rows": 0, "status": "FAILED"}
            continue
        df.to_csv(os.path.join(OUT, f"{sym}.csv"), index=False)
        man["symbols"][sym] = {"group": group, "rows": int(len(df)),
                               "first": str(df.date.iloc[0]), "last": str(df.date.iloc[-1])}
        ok += 1
        print(f"  {sym:6} {group:22} {len(df):5} rows  {df.date.iloc[0]} → {df.date.iloc[-1]}")
        time.sleep(0.15)
    man["ok"] = ok
    man["total"] = len(PANEL)
    with open(os.path.join(OUT, "MANIFEST_BROAD.json"), "w") as f:
        json.dump(man, f, indent=2)
    print(f"\n{ok}/{len(PANEL)} symbols → data/broad/")


if __name__ == "__main__":
    main()
