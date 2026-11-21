#!/usr/bin/env python3
"""
ingest_v222_pillars_1_to_4.py — Fetch 4 untouched open-data pillars (Zero-KYC, public endpoints):
  1A) Binance Vision 19-coin spot daily history (2017-08..2026-10, incl. fallen majors EOS/FIL/ALGO/ICP)
  1B) Binance Vision UM Futures daily metrics (OI, Top-Trader L/S, Global L/S, Taker L/S 2021-12..2026-10)
  2)  FRED Net Liquidity (WALCL, WTREGEN, RRPONTSYD) + HY OAS (BAMLH0A0HYM2) + Breakeven (T10YIE)
  3)  CFTC Disaggregated Commodity COT (2006..2026) with strict Friday-release causal availability
  4)  Ken French Daily 5-Factors + Momentum (1963..2026-09)
"""
from __future__ import annotations

import concurrent.futures
import io
import json
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
UA = {"User-Agent": "AlinaMarketLab/2.22 research@alina-lab.local"}


def fetch_bytes(url: str, timeout: int = 20) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception:
        return None


def ingest_crypto_19_spot() -> Path:
    syms = [
        "BTCUSDT", "ETHUSDT", "BNBUSDT", "XRPUSDT", "ADAUSDT", "SOLUSDT",
        "DOGEUSDT", "LINKUSDT", "AVAXUSDT", "TRXUSDT", "UNIUSDT", "LTCUSDT",
        "BCHUSDT", "ETCUSDT", "XLMUSDT", "EOSUSDT", "FILUSDT", "ALGOUSDT", "ICPUSDT",
    ]
    months = [f"{y:04d}-{m:02d}" for y in range(2017, 2027) for m in range(1, 13)
              if (y, m) >= (2017, 8) and (y, m) <= (2026, 10)]

    tasks = [(s, ym) for s in syms for ym in months]

    def one(t: tuple[str, str]) -> list[tuple]:
        s, ym = t
        u = f"https://data.binance.vision/data/spot/monthly/klines/{s}/1d/{s}-1d-{ym}.zip"
        b = fetch_bytes(u, timeout=10)
        if not b:
            return []
        try:
            z = zipfile.ZipFile(io.BytesIO(b))
            lines = z.read(z.namelist()[0]).decode("utf-8", errors="ignore").splitlines()
            out = []
            for ln in lines:
                parts = ln.split(",")
                if len(parts) < 8 or not parts[0].isdigit():
                    continue
                ts = int(parts[0])
                if ts > 10**14:
                    ts //= 1000
                dt = datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc).strftime("%Y-%m-%d")
                out.append((dt, s, float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4]), float(parts[5]), float(parts[7])))
            return out
        except Exception:
            return []

    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=24) as ex:
        for res in ex.map(one, tasks):
            rows.extend(res)

    df = pd.DataFrame(rows, columns=["date", "symbol", "open", "high", "low", "close", "volume", "quote_volume"])
    df = df.drop_duplicates(["date", "symbol"]).sort_values(["symbol", "date"])
    out_p = ROOT / "data" / "crypto_vision" / "spot_daily_19coins.csv.gz"
    out_p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_p, index=False, compression="gzip")
    print(f"[1A] Crypto 19-coin spot daily: {len(df):,} rows, {df['symbol'].nunique()} coins, {df['date'].min()}..{df['date'].max()}")
    return out_p


def ingest_crypto_daily_metrics() -> Path:
    syms = ["BTCUSDT", "ETHUSDT"]
    dates = pd.date_range("2021-12-01", "2026-10-31", freq="1D").strftime("%Y-%m-%d").tolist()
    tasks = [(s, d) for s in syms for d in dates]

    def one(t: tuple[str, str]) -> tuple | None:
        s, d = t
        u = f"https://data.binance.vision/data/futures/um/daily/metrics/{s}/{s}-metrics-{d}.zip"
        b = fetch_bytes(u, timeout=10)
        if not b:
            return None
        try:
            z = zipfile.ZipFile(io.BytesIO(b))
            df = pd.read_csv(io.BytesIO(z.read(z.namelist()[0])))
            if df.empty:
                return None
            last = df.iloc[-1]
            return (
                d,
                s,
                float(last["sum_open_interest"]),
                float(last["sum_open_interest_value"]),
                float(last["count_toptrader_long_short_ratio"]),
                float(last["sum_toptrader_long_short_ratio"]),
                float(last["count_long_short_ratio"]),
                float(df["sum_taker_long_short_vol_ratio"].mean()),
            )
        except Exception:
            return None

    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=32) as ex:
        for res in ex.map(one, tasks):
            if res is not None:
                rows.append(res)

    df = pd.DataFrame(rows, columns=[
        "date", "symbol", "oi_contracts", "oi_usd",
        "toptrader_ls_count_ratio", "toptrader_ls_pos_ratio",
        "global_ls_count_ratio", "taker_ls_vol_ratio_mean",
    ]).drop_duplicates(["date", "symbol"]).sort_values(["symbol", "date"])
    out_p = ROOT / "data" / "crypto_vision" / "binance_um_daily_metrics.csv.gz"
    df.to_csv(out_p, index=False, compression="gzip")
    print(f"[1B] Binance UM daily metrics: {len(df):,} rows, {df['symbol'].value_counts().to_dict()}, {df['date'].min()}..{df['date'].max()}")
    return out_p


def ingest_fred_liquidity_credit() -> Path:
    series_ids = ["WALCL", "WTREGEN", "RRPONTSYD", "BAMLH0A0HYM2", "T10YIE"]
    frames = {}
    for sid in series_ids:
        b = fetch_bytes(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}", timeout=20)
        assert b is not None, f"Failed FRED {sid}"
        df = pd.read_csv(io.BytesIO(b))
        dcol, vcol = df.columns[0], df.columns[1]
        df[dcol] = pd.to_datetime(df[dcol], errors="coerce")
        df[sid] = pd.to_numeric(df[vcol], errors="coerce")
        df = df.dropna(subset=[dcol]).set_index(dcol)[[sid]]
        # Strictly causal release calendar:
        # WALCL & WTREGEN are Wednesday snapshots released Thursday 16:30 ET -> available next trading day (Friday = +2 calendar days)
        if sid in ("WALCL", "WTREGEN"):
            df.index = df.index + pd.Timedelta(days=2)
        frames[sid] = df

    idx = pd.date_range("1997-01-01", "2026-11-21", freq="B")
    out = pd.DataFrame(index=idx)
    for sid, df in frames.items():
        # Units: WALCL (Millions USD), WTREGEN (Millions USD -> note check scale!), RRPONTSYD (Billions USD)
        s = df[sid].reindex(idx).ffill()
        out[sid] = s

    # Verify WTREGEN scale dynamically (FRED WTREGEN switched/stored in Millions or Billions: median post-2020 TGA ~$500B)
    wt_med = float(out.loc["2020-01-01":, "WTREGEN"].median())
    wt_in_bn = out["WTREGEN"] / 1000.0 if wt_med > 50000 else out["WTREGEN"]
    walcl_bn = out["WALCL"] / 1000.0
    rrp_bn = out["RRPONTSYD"].fillna(0.0)
    out["walcl_bn"] = walcl_bn
    out["wtregen_bn"] = wt_in_bn
    out["rrp_bn"] = rrp_bn
    out["net_liquidity_bn"] = walcl_bn - wt_in_bn - rrp_bn
    out.index.name = "date"
    out_p = ROOT / "data" / "macro" / "fred_liquidity_credit.csv"
    out.reset_index().to_csv(out_p, index=False)
    print(f"[2] FRED Net Liquidity & HY OAS: {len(out):,} business days | WTREGEN raw med={wt_med:.1f} -> NetLiq latest=${out['net_liquidity_bn'].dropna().iloc[-1]:.1f}B, HY_OAS latest={out['BAMLH0A0HYM2'].dropna().iloc[-1]:.2f}%")
    return out_p


def ingest_cftc_disagg_commodities() -> Path:
    targets = {
        "GOLD": "GOLD - COMMODITY EXCHANGE INC.",
        "SILVER": "SILVER - COMMODITY EXCHANGE INC.",
        "COPPER": "COPPER- #1 - COMMODITY EXCHANGE INC.",
        "PLATINUM": "PLATINUM - NEW YORK MERCANTILE EXCHANGE",
        "WTI_CRUDE": "WTI FINANCIAL CRUDE OIL - NEW YORK MERCANTILE EXCHANGE",
        "CRUDE_ICE": "CRUDE OIL, LIGHT SWEET-WTI - ICE FUTURES EUROPE",
        "CRUDE_NYMEX": "CRUDE OIL, LIGHT SWEET - NEW YORK MERCANTILE EXCHANGE",
        "NATGAS_NYME": "NATURAL GAS - NEW YORK MERCANTILE EXCHANGE",
        "NATGAS_LD1": "NAT GAS NYME",
        "CORN": "CORN - CHICAGO BOARD OF TRADE",
        "SOYBEANS": "SOYBEANS - CHICAGO BOARD OF TRADE",
    }
    frames = []
    tags = ["hist_2006_2016"] + [str(y) for y in range(2017, 2027)]
    for yr in tags:
        u = f"https://www.cftc.gov/files/dea/history/fut_disagg_txt_{yr}.zip"
        b = fetch_bytes(u, timeout=30)
        if not b:
            continue
        z = zipfile.ZipFile(io.BytesIO(b))
        df = pd.read_csv(io.BytesIO(z.read(z.namelist()[0])), low_memory=False)
        dcol = "Report_Date_as_YYYY-MM-DD" if "Report_Date_as_YYYY-MM-DD" in df.columns else "Report_Date_as_MM_DD_YYYY"
        mkt = df["Market_and_Exchange_Names"].astype(str).str.strip()
        # Flexible prefix matching to capture renamed NYMEX Crude / NatGas across 2006-2026
        sub = df[
            mkt.isin(targets.values())
            | mkt.str.startswith("CRUDE OIL, LIGHT SWEET - NEW YORK MERCANTILE EXCHANGE")
            | mkt.str.startswith("WTI-PHYSICAL - NEW YORK MERCANTILE EXCHANGE")
            | mkt.str.startswith("HENRY HUB - NEW YORK MERCANTILE EXCHANGE")
            | mkt.str.startswith("HENRY HUB LAST DAY FIN")
        ].copy()
        if sub.empty:
            continue
        keep = pd.DataFrame({
            "report_date": pd.to_datetime(sub[dcol], errors="coerce"),
            "market": sub["Market_and_Exchange_Names"].astype(str).str.strip(),
            "oi": pd.to_numeric(sub["Open_Interest_All"], errors="coerce"),
            "pm_long": pd.to_numeric(sub["Prod_Merc_Positions_Long_All"], errors="coerce"),
            "pm_short": pd.to_numeric(sub["Prod_Merc_Positions_Short_All"], errors="coerce"),
            "mm_long": pd.to_numeric(sub["M_Money_Positions_Long_All"], errors="coerce"),
            "mm_short": pd.to_numeric(sub["M_Money_Positions_Short_All"], errors="coerce"),
        })
        frames.append(keep)

    all_df = pd.concat(frames, ignore_index=True).dropna(subset=["report_date", "oi"])
    # Map canonical commodity key
    def map_comm(m: str) -> str:
        if "GOLD" in m and "MICRO" not in m: return "GOLD"
        if "SILVER" in m: return "SILVER"
        if "COPPER" in m: return "COPPER"
        if "PLATINUM" in m: return "PLATINUM"
        if "WTI-PHYSICAL" in m or "CRUDE OIL, LIGHT SWEET - NEW YORK" in m: return "WTI_NYMEX"
        if "WTI FINANCIAL" in m: return "WTI_FIN"
        if "CRUDE OIL, LIGHT SWEET-WTI - ICE" in m: return "WTI_ICE"
        if "NATURAL GAS - NEW YORK" in m or "HENRY HUB" in m: return "NATGAS"
        if "CORN" in m: return "CORN"
        if "SOYBEANS" in m: return "SOYBEANS"
        return m

    all_df["commodity"] = all_df["market"].map(map_comm)
    all_df = all_df[all_df["oi"] > 0].copy()
    all_df["mm_net_pct_oi"] = (all_df["mm_long"] - all_df["mm_short"]) / all_df["oi"]
    all_df["pm_net_pct_oi"] = (all_df["pm_long"] - all_df["pm_short"]) / all_df["oi"]
    # Tuesday report released Friday 15:30 ET -> causal availability starts Friday close (+3 calendar days; trade Monday open)
    all_df["available_from"] = (all_df["report_date"] + pd.Timedelta(days=3)).dt.strftime("%Y-%m-%d")
    all_df["report_date"] = all_df["report_date"].dt.strftime("%Y-%m-%d")
    all_df = all_df.drop_duplicates(["commodity", "report_date"]).sort_values(["commodity", "report_date"])
    out_p = ROOT / "data" / "cot" / "cot_disagg_commodities.csv.gz"
    all_df.to_csv(out_p, index=False, compression="gzip")
    print(f"[3] CFTC Disagg Commodities: {len(all_df):,} rows, {all_df['commodity'].value_counts().to_dict()}")
    return out_p


def ingest_ken_french() -> Path:
    def parse_kf_daily(url: str, expected_cols: list[str]) -> pd.DataFrame:
        b = fetch_bytes(url, timeout=20)
        assert b is not None, f"Failed {url}"
        z = zipfile.ZipFile(io.BytesIO(b))
        lines = z.read(z.namelist()[0]).decode("utf-8", errors="ignore").splitlines()
        rows = []
        for ln in lines:
            s = ln.strip()
            if len(s) >= 10 and s[:8].isdigit() and "," in s:
                parts = [p.strip() for p in s.split(",")]
                if len(parts) == len(expected_cols) + 1:
                    rows.append([parts[0]] + [float(x) / 100.0 for x in parts[1:]])
        df = pd.DataFrame(rows, columns=["date"] + expected_cols)
        df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")
        return df.set_index("date").sort_index()

    ff5 = parse_kf_daily(
        "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_daily_CSV.zip",
        ["Mkt_RF", "SMB", "HML", "RMW", "CMA", "RF"],
    )
    mom = parse_kf_daily(
        "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_daily_CSV.zip",
        ["Mom"],
    )
    kf = ff5.join(mom, how="inner")
    out_p = ROOT / "data" / "macro" / "ken_french_ff5_mom_daily.csv.gz"
    kf.reset_index().to_csv(out_p, index=False, compression="gzip")
    print(f"[4] Ken French FF5+Mom daily: {len(kf):,} days ({kf.index[0].strftime('%Y-%m-%d')}..{kf.index[-1].strftime('%Y-%m-%d')})")
    return out_p


def main() -> None:
    ingest_crypto_19_spot()
    ingest_crypto_daily_metrics()
    ingest_fred_liquidity_credit()
    ingest_cftc_disagg_commodities()
    ingest_ken_french()


if __name__ == "__main__":
    main()
