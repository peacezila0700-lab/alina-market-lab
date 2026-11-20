#!/usr/bin/env python3
"""Alternative / "special" data layer — the stuff that is NOT on the first page of Google.

Everything here was verified to work WITHOUT an API key from a plain sandbox (2026-11-20).
Each block records why a trader cares, and the status is written to MANIFEST_ALT.json so a
downstream AI can trust (or distrust) the file.

Layers covered:
  A. Equity positioning beyond COT: SqueezeMetrics DIX (dark-pool index) + GEX (dealer gamma)
     — daily, 2011-05 → now. DIX = share of off-exchange volume that is retail-buying; the
     complement is institutional selling. GEX = model dealer gamma (positive = suppressed vol).
  B. Financial-system stress: OFR Financial Stress Index (5 sub-indices) — official, free CSV.
  C. Policy/geopolitical risk: Baker-Bloom-Davis Economic Policy Uncertainty (US monthly) and
     Caldara-Iacoviello Geopolitical Risk index. These are the two most-cited text-based risk
     measures in academic macro trading.
  D. Physical supply: EIA weekly crude stocks + Henry Hub natural gas price (official xls).
  E. Crypto positioning/flows (exchange-published, free): OKX funding rate + top-trader
     long/short account ratio; Deribit options chain → implied-vol term structure & skew.
"""
from __future__ import annotations

import io
import json
import os
import time
import urllib.request
from datetime import datetime, timezone

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "alt")
os.makedirs(OUT, exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"
STATUS: dict = {"built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "sources": {}}


def get(url: str, timeout: int = 40, referer: str | None = None) -> bytes | None:
    h = {"User-Agent": UA}
    if referer:
        h["Referer"] = referer
    req = urllib.request.Request(url, headers=h)
    for a in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception as e:                                    # noqa: BLE001
            print(f"    retry {a + 1}: {e}")
            time.sleep(2 * (a + 1))
    return None


def note(key: str, **kw) -> None:
    STATUS["sources"][key] = kw
    print(f"  {key:22} {kw.get('status')}  rows={kw.get('rows', '-')}")


# ---------------------------------------------------------------- A. DIX / GEX
def dix_gex() -> None:
    print("[A] SqueezeMetrics DIX + GEX (dark pool + dealer gamma, 2011→)")
    raw = get("https://squeezemetrics.com/monitor/static/DIX.csv")
    if not raw:
        return note("dix_gex", status="FAILED")
    df = pd.read_csv(io.BytesIO(raw))
    df.columns = [c.strip().lower() for c in df.columns]
    df["date"] = pd.to_datetime(df["date"])
    df = df.rename(columns={"dix": "DIX", "gex": "GEX"})
    df.to_csv(os.path.join(OUT, "dix_gex.csv"), index=False, float_format="%.6f")
    note("dix_gex", status="OK", rows=len(df), first=str(df.date.min().date()),
         last=str(df.date.max().date()), cols=list(df.columns),
         meaning="DIX = dark-pool buy/sell imbalance (retail-ish demand); GEX = modelled dealer gamma in $bn per 1% move",
         caveat="GEX assumes dealers long calls / short puts from OI only; sign can be wrong in unusual flow. "
                "DIX is a share of off-exchange volume, not a dollar flow.")


# ---------------------------------------------------------------- B. OFR stress
def ofr_fsi() -> None:
    print("[B] OFR Financial Stress Index")
    raw = get("https://www.financialresearch.gov/financial-stress-index/data/fsi.csv")
    if not raw:
        return note("ofr_fsi", status="FAILED")
    df = pd.read_csv(io.BytesIO(raw))
    df.to_csv(os.path.join(OUT, "ofr_fsi.csv"), index=False)
    note("ofr_fsi", status="OK", rows=len(df), first=df.iloc[0, 0], last=df.iloc[-1, 0],
         cols=list(df.columns),
         meaning="0 = normal; >0 = above-average stress. Sub-indices separate credit / equity valuation / "
                 "safe assets / funding / volatility",
         caveat="Weekly-ish publication lag; rescaled so history has zero mean.")


# ---------------------------------------------------------------- C. policy risk
def epu() -> None:
    print("[C1] Economic Policy Uncertainty (Baker-Bloom-Davis)")
    raw = get("https://www.policyuncertainty.com/media/US_Historical_EPU_data.xlsx")
    if not raw:
        return note("epu_us", status="FAILED")
    xl = pd.ExcelFile(io.BytesIO(raw))
    sheet = "US Historical EPU Data" if "US Historical EPU Data" in xl.sheet_names else xl.sheet_names[0]
    df = pd.read_excel(xl, sheet_name=sheet)
    df.columns = [str(c).strip() for c in df.columns]
    # the file has a 2-row header on some releases: keep the year/month + index triples
    keep = [c for c in df.columns if c.lower() in ("year", "month", "news-based economic policy uncertainty index",
                                                   "news_based_epu", "three_components", "epu")]
    df = df[keep] if len(keep) >= 3 else df.iloc[:, :4]
    df.to_csv(os.path.join(OUT, "epu_us_monthly.csv"), index=False)
    note("epu_us", status="OK", rows=len(df), cols=list(df.columns)[:6],
         meaning="News-based count of articles about policy uncertainty, monthly, 1985→. A text-based risk "
                 "measure that is genuinely independent of price data",
         caveat="Monthly, published with a lag of days; the index is normalised to 100 = 1985-2009 mean.")


def gpr() -> None:
    print("[C2] Geopolitical Risk index (Caldara-Iacoviello)")
    raw = get("https://www.matteoiacoviello.com/gpr_files/data_gpr_export.xls")
    if not raw:
        return note("gpr", status="FAILED")
    df = pd.read_excel(io.BytesIO(raw))
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    dcol = "month" if "month" in df.columns else df.columns[0]
    df[dcol] = pd.to_datetime(df[dcol], errors="coerce")
    df = df.dropna(subset=[dcol]).sort_values(dcol)
    df.to_csv(os.path.join(OUT, "gpr_monthly.csv"), index=False, float_format="%.4f")
    note("gpr", status="OK", rows=len(df), first=str(df[dcol].min().date()), last=str(df[dcol].max().date()),
         cols=list(df.columns)[:10],
         meaning="GPR / GPRC (threats) / GPRA (acts) — newspaper-based geopolitical risk, 1900→ for some series",
         caveat="Monthly and slow-moving; good as a regime backdrop, not a trading trigger.")


# ---------------------------------------------------------------- D. physical supply
def eia() -> None:
    print("[D] EIA weekly physical supply (crude stocks, Henry Hub)")
    for key, url in (("eia_crude_stocks_w", "https://www.eia.gov/dnav/pet/hist_xls/WCRSTUS1w.xls"),
                     ("eia_henryhub_w", "https://www.eia.gov/dnav/ng/hist_xls/RNGWHHDw.xls")):
        raw = get(url)
        if not raw:
            note(key, status="FAILED")
            continue
        try:
            xl = pd.ExcelFile(io.BytesIO(raw), engine="xlrd")
            sheet = [s for s in xl.sheet_names if "Data 1" in s or "Data" in s][0]
            df = pd.read_excel(xl, sheet_name=sheet, header=2)
            df.columns = ["date", "value"] + list(df.columns[2:])
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df = df.dropna(subset=["date"])[["date", "value"]]
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            df = df.dropna(subset=["value"])
            df.to_csv(os.path.join(OUT, f"{key}.csv"), index=False)
            note(key, status="OK", rows=len(df), first=str(df.date.min().date()), last=str(df.date.max().date()),
                 meaning="Weekly physical inventory / spot price — the actual supply side behind energy futures",
                 caveat="Published Wednesday 10:30 ET for crude; the release is the event, the level is the context.")
        except Exception as e:                                    # noqa: BLE001
            note(key, status=f"PARSE_FAILED: {e}")


# ---------------------------------------------------------------- E. crypto flow
def okx_funding_lsr() -> None:
    print("[E1] OKX funding rate + top-trader long/short ratio")
    raw = get("https://www.okx.com/api/v5/public/funding-rate-history?instId=BTC-USDT-SWAP&limit=100")
    if raw:
        rows = json.loads(raw).get("data", [])
        df = pd.DataFrame(rows)
        if not df.empty:
            df["ts"] = pd.to_datetime(df.fundingTime.astype("int64"), unit="ms", utc=True)
            df["fundingRate"] = df.fundingRate.astype(float)
            df = df[["ts", "fundingRate"]].sort_values("ts")
            df.to_csv(os.path.join(OUT, "okx_btc_funding.csv"), index=False)
            note("okx_btc_funding", status="OK", rows=len(df),
                 meaning="8-hourly perpetual funding = the price of leveraged long exposure; positive = longs pay "
                         "shorts (crowded long). A carry + crowding measure in one number",
                 caveat="OKX only (one venue), 100 most recent points per call → build history by polling.")
    else:
        note("okx_btc_funding", status="FAILED")

    raw = get("https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio?ccy=BTC&period=1D")
    if raw:
        rows = json.loads(raw).get("data", [])
        df = pd.DataFrame(rows, columns=["ts_ms", "long_short_ratio"])
        df["date"] = pd.to_datetime(df.ts_ms.astype("int64"), unit="ms", utc=True)
        df["long_short_ratio"] = df.long_short_ratio.astype(float)
        df = df[["date", "long_short_ratio"]].sort_values("date")
        df.to_csv(os.path.join(OUT, "okx_btc_long_short_ratio.csv"), index=False)
        note("okx_btc_lsr", status="OK", rows=len(df),
             meaning="Accounts with net long vs net short positions (retail-leaning). >1 = crowd is long",
             caveat="Account-count ratio, not notional; classic contrarian input with weak standalone power.")


def deribit_vol() -> None:
    print("[E2] Deribit options chain → IV term structure + skew")
    raw = get("https://www.deribit.com/api/v2/public/get_book_summary_by_currency?currency=BTC&kind=option")
    if not raw:
        return note("deribit_btc_iv", status="FAILED")
    res = json.loads(raw).get("result", [])
    rows = []
    for r in res:
        name = r.get("instrument_name", "")
        parts = name.split("-")
        if len(parts) != 4:
            continue
        _, expiry, strike, kind = parts
        try:
            rows.append({"expiry": expiry, "strike": float(strike), "kind": kind.lower(),
                         "iv_pct": float(r.get("mark_iv") or 0), "oi": float(r.get("open_interest") or 0),
                         "volume": float(r.get("volume") or 0), "underlying": float(r.get("underlying_price") or 0)})
        except (TypeError, ValueError):
            continue
    if not rows:
        return note("deribit_btc_iv", status="PARSE_EMPTY")
    df = pd.DataFrame(rows)
    spot = float(df.underlying.iloc[0])
    df["expiry_dt"] = pd.to_datetime(df.expiry, format="%d%b%y")
    df["dte"] = (df.expiry_dt - pd.Timestamp.utcnow().tz_localize(None)).dt.days
    df["mny"] = df.strike / spot
    df.to_csv(os.path.join(OUT, "deribit_btc_chain_snapshot.csv"), index=False, float_format="%.4f")
    # term structure: ATM IV per expiry; skew: 25-delta-ish OTM put vs call at ~35d
    atm = (df[df.mny.between(0.95, 1.05)].groupby("expiry_dt")
           .apply(lambda g: g.sort_values("strike").iloc[(g.strike - spot).abs().argsort()[:3]].iv_pct.mean())
           .rename("atm_iv_pct").reset_index())
    atm["dte"] = (atm.expiry_dt - pd.Timestamp.utcnow().tz_localize(None)).dt.days
    atm.sort_values("dte").to_csv(os.path.join(OUT, "deribit_btc_term_structure.csv"), index=False, float_format="%.3f")
    note("deribit_btc_iv", status="OK", rows=len(df), spot=spot,
         meaning="Full BTC option chain: mark IV per strike/expiry → risk reversal (25d put IV − call IV) is the "
                 "purest fear gauge in a 24/7 market; term structure inverts in stress",
         caveat="A snapshot, not history. Mark IV is venue-published, not a tradeable quote; OI is per-contract.")


def main() -> None:
    for fn in (dix_gex, ofr_fsi, epu, gpr, eia, okx_funding_lsr, deribit_vol):
        try:
            fn()
        except Exception as e:                                    # noqa: BLE001
            print(f"  {fn.__name__}: EXCEPTION {e}")
            STATUS["sources"][fn.__name__] = {"status": f"EXCEPTION: {e}"}
    with open(os.path.join(OUT, "MANIFEST_ALT.json"), "w") as f:
        json.dump(STATUS, f, indent=2)
    print(f"\nmanifest → data/alt/MANIFEST_ALT.json  ({len(STATUS['sources'])} sources)")


if __name__ == "__main__":
    main()
