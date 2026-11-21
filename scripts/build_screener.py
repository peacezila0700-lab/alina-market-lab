#!/usr/bin/env python3
"""
build_screener.py — put the three layers on one row and call it a screener.

A screener is only useful if it joins:
  identity      symbol, name, sector, industry, country, market cap          (Nasdaq)
  technicals    RSI, ADX, trend vs MAs, distance from 52w extremes, vol     (data/technicals)
  fundamentals  latest revenue, net income, EPS, equity from XBRL           (data/sec)
  filings       the last 10-K/10-Q filing date, so staleness is visible     (data/sec)

That join is done here, once, with explicit staleness columns, because every screener built ad hoc ends
up with silently stale fundamentals — the most common way a retail screen lies to you.

Uncertainty written down:
  * Fundamentals are as-filed XBRL, available only for the top-market-cap names we crawled (60 today).
    `fund_asof` and `fund_age_days` are printed so a stale row can be spotted and discarded.
  * Market cap and sector come from an unofficial Nasdaq endpoint and are a snapshot, not history.
  * The screener carries VALUES, not ranks-as-advice: no composite score is computed, because a score
    would be an untested strategy pretending to be a filter (see WHAT_FAILED.md).

Outputs
  data/screener/screener_latest.csv   one row per symbol, all layers joined
  data/screener/MANIFEST_SCREENER.json counts, join coverage, staleness summary
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "screener"


def main():
    scr = pd.read_csv(OUT / "nasdaq_all.csv")
    tech = pd.read_csv(ROOT / "data" / "technicals" / "latest.csv")
    fund = pd.read_csv(ROOT / "data" / "sec" / "fundamentals.csv")
    fil = pd.read_csv(ROOT / "data" / "sec" / "filings.csv")

    # ---- latest annual fundamental per company (form 10-K, most recent period)
    # fp == "FY" is essential: a 10-K file also carries the Q4 rows of the SAME tag, and taking the last
    # period_end without that filter mixes quarterly revenue with annual net income (MSFT showed a 2.14
    # "net margin" before this filter — a 214% margin, which is impossible).
    ann = fund[(fund.form == "10-K") & (fund.fp.astype(str) == "FY")].copy()
    ann["period_end"] = pd.to_datetime(ann["period_end"], errors="coerce")
    ann["filed"] = pd.to_datetime(ann["filed"], errors="coerce")
    wide = (ann.sort_values("period_end")
              .groupby(["ticker", "field"])
              .tail(1)
              .pivot_table(index="ticker", columns="field", values="value", aggfunc="last"))
    wide.columns = [f"fy_{c}" for c in wide.columns]
    asof = ann.groupby("ticker")["period_end"].max().rename("fund_period_end")
    filed = ann.groupby("ticker")["filed"].max().rename("fund_filed")

    # ---- filings freshness
    fil["filed"] = pd.to_datetime(fil["filed"], errors="coerce")
    last_10 = (fil[fil.form.isin(["10-K", "10-Q"])].groupby("ticker")["filed"].max()
               .rename("last_periodic_filing"))

    df = scr.rename(columns={"symbol": "symbol"})
    df["symbol"] = df["symbol"].astype(str).str.strip()
    df = df.merge(tech, left_on="symbol", right_on="symbol", how="left", suffixes=("", "_tech"))
    # single-stock technicals, if the stock panel has been fetched
    stk = ROOT / "data" / "stocks" / "MANIFEST_STOCKS.json"
    if stk.exists():
        import json as _json
        have = {k for k, v in _json.loads(stk.read_text())["symbols"].items() if v.get("status") == "ok"}
        df["has_price_history"] = df["symbol"].isin(have)

    fx = wide.join(asof).join(filed).join(last_10).reset_index().rename(columns={"ticker": "symbol"})
    df = df.merge(fx, on="symbol", how="left")

    today = pd.Timestamp(datetime.now(timezone.utc).date())
    df["fund_age_days"] = (today - pd.to_datetime(df.get("fund_filed"), errors="coerce")).dt.days
    df["filing_age_days"] = (today - pd.to_datetime(df.get("last_periodic_filing"), errors="coerce")).dt.days

    # derived, clearly-labelled ratios (no scoring)
    for a, b, name in (("fy_net_income", "fy_revenue", "net_margin"),
                       ("fy_net_income", "fy_equity", "roe"),
                       ("market_cap", "fy_net_income", "pe_from_xbrl")):
        if a in df and b in df:
            with np.errstate(divide="ignore", invalid="ignore"):
                df[name] = np.where(df[b].notna() & (df[b] != 0), df[a] / df[b], np.nan)
    if "pe_from_xbrl" in df:
        df.loc[(df["pe_from_xbrl"] <= 0) | (df["pe_from_xbrl"] > 500), "pe_from_xbrl"] = np.nan

    df = df.sort_values("market_cap", ascending=False)
    df.to_csv(OUT / "screener_latest.csv", index=False)

    joined_fund = int(df["fy_revenue"].notna().sum()) if "fy_revenue" in df else 0
    joined_tech = int(df["rsi14"].notna().sum()) if "rsi14" in df else 0
    med_age = float(pd.to_numeric(df["fund_age_days"], errors="coerce").median()) if "fund_age_days" in df else None
    (OUT / "MANIFEST_SCREENER.json").write_text(json.dumps({
        "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rows": int(len(df)), "symbols_with_technicals": joined_tech,
        "symbols_with_fundamentals": joined_fund,
        "median_fundamental_age_days": med_age,
        "sectors": int(df["sector"].nunique()) if "sector" in df else 0,
        "columns": list(df.columns),
        "caveats": ["Fundamentals cover only the top-market-cap names crawled from SEC XBRL (60).",
                    "No composite score is provided on purpose: an untested score is a strategy in disguise.",
                    "Market cap/sector are a Nasdaq snapshot, not history.",
                    "Always check fund_age_days before acting on a fundamental field."]}, indent=2))
    print(f"  screener: {len(df)} symbols | technicals {joined_tech} | fundamentals {joined_fund} | "
          f"median fundamental age {med_age} days")
    cols = [c for c in ("symbol", "name", "sector", "market_cap", "rsi14", "adx14", "ret21d",
                        "fy_revenue", "net_margin", "pe_from_xbrl", "fund_age_days") if c in df]
    print(df[cols].head(8).to_string(index=False))


if __name__ == "__main__":
    main()
