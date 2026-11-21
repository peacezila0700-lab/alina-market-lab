#!/usr/bin/env python3
"""
fetch_worldbank.py — the macro panel: GDP, inflation, unemployment, rates, debt, current account
for 22 economies, annual, 1990 -> latest. Free, key-less, one endpoint.

Why: the pack's macro layer was US-only (Treasury curve, BLS, EIA, EPU, GPR) plus an OFR stress index.
Anything cross-country ("which economy is deteriorating fastest", "does the carry trade work when the
funding country's inflation is high") needs a comparable panel. World Bank is the only free source that
gives one for every country with the same definitions.

Endpoint: https://api.worldbank.org/v2/country/{ISO3}/indicator/{IND}?format=json&per_page=200
  -> [ {meta}, [ {date: "2024", value: 123.4}, ... ] ]   (newest first)

Indicators
  NY.GDP.MKTP.KD.ZG  GDP growth (annual %, constant prices)
  NY.GDP.MKTP.CD     GDP (current US$)
  FP.CPI.TOTL.ZG     inflation, consumer prices (annual %)
  SL.UEM.TOTL.ZS     unemployment (% of labour force, ILO modelled)
  GC.DOD.TOTL.GD.ZS  central government debt (% of GDP)
  BN.CAB.XOKA.GD.ZS  current account balance (% of GDP)
  FR.INR.LEND        lending interest rate (%)
  SP.POP.TOTL        population
  NE.EXP.GNFS.ZS     exports (% of GDP)

Uncertainty written down:
  * World Bank data lag 1-2 years and are revised; `date` is the reference year, not the publication
    date, so nothing here is point-in-time. Use it as a slow prior, never as a trading input.
  * Missing values are common in the newest year (published in arrears) and for small economies.
  * Definitions differ from national statistics offices (ILO-modelled unemployment, for example).

Outputs
  data/macro/wb_panel_long.csv    iso3, country, indicator, year, value
  data/macro/wb_latest.csv        latest non-null value per country x indicator
  data/macro/MANIFEST_WB.json     coverage + coverage_by_indicator
"""
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "macro"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
COUNTRIES = {
    "USA": "United States", "GBR": "United Kingdom", "DEU": "Germany", "FRA": "France",
    "JPN": "Japan", "CHN": "China", "IND": "India", "BRA": "Brazil", "RUS": "Russia",
    "THA": "Thailand", "VNM": "Vietnam", "IDN": "Indonesia", "TUR": "Turkey", "MEX": "Mexico",
    "SAU": "Saudi Arabia", "ZAF": "South Africa", "KOR": "South Korea", "AUS": "Australia",
    "CAN": "Canada", "CHE": "Switzerland", "SGP": "Singapore", "NGA": "Nigeria",
}
INDICATORS = {
    "NY.GDP.MKTP.KD.ZG": "gdp_growth_pct",
    "NY.GDP.MKTP.CD": "gdp_usd",
    "FP.CPI.TOTL.ZG": "inflation_cpi_pct",
    "SL.UEM.TOTL.ZS": "unemployment_pct",
    "GC.DOD.TOTL.GD.ZS": "govt_debt_pct_gdp",
    "BN.CAB.XOKA.GD.ZS": "current_account_pct_gdp",
    "FR.INR.LEND": "lending_rate_pct",
    "SP.POP.TOTL": "population",
    "NE.EXP.GNFS.ZS": "exports_pct_gdp",
}


def get(url, tries=3, timeout=60):
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except Exception:                                        # noqa: BLE001
            if a == tries - 1:
                return None
            time.sleep(2 + 2 * a)
    return None


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows, status = [], {}
    for iso, name in COUNTRIES.items():
        ok = 0
        for ind, label in INDICATORS.items():
            url = (f"https://api.worldbank.org/v2/country/{iso}/indicator/{ind}"
                   f"?format=json&per_page=200&date=1990:2026")
            j = get(url)
            if not j or len(j) < 2 or not j[1]:
                continue
            for rec in j[1]:
                if rec.get("value") is None:
                    continue
                rows.append({"iso3": iso, "country": name, "indicator": label,
                             "year": int(rec["date"]), "value": float(rec["value"])})
                ok += 1
            time.sleep(0.15)
        status[iso] = ok
        print(f"  {iso} {name:<16} {ok:>4} observations")

    df = pd.DataFrame(rows)
    if df.empty:
        print("  no data")
        return
    df = df.sort_values(["country", "indicator", "year"])
    df.to_csv(OUT / "wb_panel_long.csv", index=False)
    latest = (df.sort_values("year").groupby(["iso3", "country", "indicator"])
                .tail(1).reset_index(drop=True))
    latest["data_year"] = latest["year"]
    latest.to_csv(OUT / "wb_latest.csv", index=False)
    cov = df.groupby("indicator")["iso3"].nunique().to_dict()
    (OUT / "MANIFEST_WB.json").write_text(json.dumps({
        "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "api.worldbank.org/v2 (World Bank Open Data, no key)",
        "countries": list(COUNTRIES), "rows": int(len(df)),
        "year_range": [int(df.year.min()), int(df.year.max())],
        "countries_covered_per_indicator": cov,
        "caveats": ["Data lag 1-2 years and are revised: not point-in-time, use as a slow prior.",
                    "ILO-modelled unemployment and national variations mean cross-country comparability "
                    "is approximate.",
                    "Newest-year values are often missing (published in arrears)."]}, indent=2))
    print(f"\n  world bank: {len(df)} rows, {df.iso3.nunique()} countries, {df.year.min()}-{df.year.max()}")
    print(f"  coverage by indicator: {cov}")
    print(f"  -> {OUT/'wb_latest.csv'}")


if __name__ == "__main__":
    main()
