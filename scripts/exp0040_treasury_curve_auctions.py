#!/usr/bin/env python3
"""
EXP-0040 — US Treasury Yield-Curve Slope, Bond Trend & Auction Demand Study (2002-2026)
Uses Tiingo total-return TLT/IEF/SHY/BIL ETFs + FRED daily rates (DGS10, DGS2, DTB3)
plus FiscalData 10Y/30Y Treasury auctions (11,154 rows) with strict t-1 / issue_date+1td causality.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TIINGO = ROOT / "data" / "etfs_tiingo"
OUT_JSON = ROOT / "research" / "artifacts" / "exp0040_treasury_curve_auctions.json"

N_SHIFTS = 200


def load_tr(sym: str) -> pd.Series:
    df = pd.read_csv(TIINGO / f"{sym}.csv")
    df["date"] = pd.to_datetime(df["date"])
    s = pd.to_numeric(df["adjclose"], errors="coerce").set_axis(df["date"]).dropna().sort_index()
    return s[~s.index.duplicated(keep="last")]


def perf(r: np.ndarray) -> dict:
    r = r[np.isfinite(r)]
    if len(r) < 30:
        return {"sharpe": 0.0, "cagr_pct": 0.0, "maxdd_pct": 0.0, "calmar": 0.0}
    mu, sd = float(np.mean(r)), float(np.std(r, ddof=1))
    shp = (mu / sd * math.sqrt(252.0)) if sd > 0 else 0.0
    eq = np.cumprod(1.0 + r)
    cagr = (float(eq[-1]) ** (252.0 / len(r)) - 1.0) * 100.0 if eq[-1] > 0 else -100.0
    mdd = float(np.min(eq / np.maximum.accumulate(eq) - 1.0)) * 100.0
    return {"sharpe": round(shp, 3), "cagr_pct": round(cagr, 2), "maxdd_pct": round(mdd, 2), "calmar": round(cagr / max(abs(mdd), 1e-3), 3)}


def circ_shift_pair(w_bond: np.ndarray, r_bond: np.ndarray, r_cash: np.ndarray, cost_bps: float, ref_shp: float, rng: np.random.Generator) -> float:
    n = len(r_bond)
    null = []
    min_s = max(21, n // 20)
    for _ in range(N_SHIFTS):
        s = int(rng.integers(min_s, n - min_s))
        wb = np.roll(w_bond, s)
        to = np.abs(np.diff(wb, prepend=0.0)) * 2.0
        rn = wb * r_bond + (1.0 - wb) * r_cash - to * (cost_bps / 10000.0)
        sd = float(np.std(rn, ddof=1))
        null.append(float(np.mean(rn) / sd * math.sqrt(252.0)) if sd > 0 else 0.0)
    return round(float(np.mean(np.array(null) <= ref_shp) * 100.0), 1)


def main() -> None:
    rng = np.random.default_rng(42)
    tlt = load_tr("TLT")
    ief = load_tr("IEF")
    bil = load_tr("BIL")
    fr = pd.read_csv(ROOT / "data" / "macro" / "fred_rates_full.csv")
    fr["date"] = pd.to_datetime(fr["date"])
    fr = fr.drop_duplicates("date").set_index("date").sort_index()

    idx = tlt.index.intersection(ief.index).intersection(bil.index).intersection(fr.index)
    idx = idx[idx >= pd.Timestamp("2007-06-01")]
    r_tlt = tlt.pct_change().reindex(idx).fillna(0.0).to_numpy()
    r_ief = ief.pct_change().reindex(idx).fillna(0.0).to_numpy()
    r_bil = bil.pct_change().reindex(idx).fillna(0.0).to_numpy()

    dgs10 = pd.to_numeric(fr["dgs10"], errors="coerce").reindex(idx).ffill()
    dgs2 = pd.to_numeric(fr["dgs2"], errors="coerce").reindex(idx).ffill()
    dtb3 = pd.to_numeric(fr["dtb3"], errors="coerce").reindex(idx).ffill()

    # Strict t-1 lag for all curve and trend signals
    slope_10_3m = (dgs10 - dtb3).shift(1)
    slope_10_2y = (dgs10 - dgs2).shift(1)
    tlt_sma126 = (tlt.reindex(idx) > tlt.reindex(idx).rolling(126).mean()).shift(1).fillna(False)
    ief_sma126 = (ief.reindex(idx) > ief.reindex(idx).rolling(126).mean()).shift(1).fillna(False)

    start_m = idx >= pd.Timestamp("2008-01-01")
    is_m = start_m & (idx < pd.Timestamp("2017-01-01"))
    oos_m = idx >= pd.Timestamp("2017-01-01")

    curve_res = {}
    for name, w_ser, r_b in [
        ("1_TLT_BuyHold", pd.Series(1.0, index=idx), r_tlt),
        ("2_IEF_BuyHold", pd.Series(1.0, index=idx), r_ief),
        ("3_BIL_BuyHold", pd.Series(0.0, index=idx), r_tlt),
        ("4_TLT_if_10y3m_Pos_else_BIL", (slope_10_3m > 0.0).astype(float), r_tlt),
        ("5_TLT_if_10y2y_Pos_else_BIL", (slope_10_2y > 0.0).astype(float), r_tlt),
        ("6_TLT_if_SMA126_else_BIL", tlt_sma126.astype(float), r_tlt),
        ("7_TLT_Slope10y3m_AND_SMA126", ((slope_10_3m > 0.0) & tlt_sma126).astype(float), r_tlt),
        ("8_IEF_Slope10y3m_AND_SMA126", ((slope_10_3m > 0.0) & ief_sma126).astype(float), r_ief),
    ]:
        wb = w_ser.fillna(0.0).to_numpy()
        to = np.abs(np.diff(wb, prepend=0.0)) * 2.0
        rn = wb * r_b + (1.0 - wb) * r_bil - to * 5e-4
        # Also compute EXCESS return over BIL (risk-free T-Bills!) so Sharpe isn't inflated by risk-free rate!
        ex = rn - r_bil
        m_all = perf(rn[start_m])
        m_ex_all = perf(ex[start_m])
        m_ex_oos = perf(ex[oos_m])
        curve_res[name] = {
            "total_all": m_all,
            "excess_vs_bil_is": perf(ex[is_m]),
            "excess_vs_bil_oos": m_ex_oos,
            "excess_vs_bil_all": m_ex_all,
            "shift_pct_oos": circ_shift_pair(wb[oos_m], r_b[oos_m] - r_bil[oos_m], np.zeros_like(r_bil[oos_m]), 5.0, m_ex_oos["sharpe"], rng)
            if name not in ("1_TLT_BuyHold", "2_IEF_BuyHold", "3_BIL_BuyHold") else None,
            "time_in_bond_pct": round(float(wb[start_m].mean() * 100.0), 1),
        }

    # Part 2: Treasury 10Y / 30Y Auction Demand Event Study (record_date/auction_date + 1td -> fwd 5d/21d TLT excess over BIL)
    ta = pd.read_csv(ROOT / "data" / "collect" / "treasury_auctions_full.csv.gz", low_memory=False)
    ta["rec_dt"] = pd.to_datetime(ta.get("record_date"), errors="coerce")
    ta["btc"] = pd.to_numeric(ta.get("bid_to_cover_ratio"), errors="coerce")
    ta["hy"] = pd.to_numeric(ta.get("high_yield"), errors="coerce")
    ta["ay"] = pd.to_numeric(ta.get("avg_med_yield"), errors="coerce")
    ta["tail_bp"] = (ta["hy"] - ta["ay"]) * 100.0
    sub = ta[ta["security_type"].isin(["Note", "Bond"]) & ta["security_term"].astype(str).str.contains("10-Year|30-Year|9-Year|29-Year", na=False)].copy()
    sub = sub.dropna(subset=["rec_dt", "btc"]).sort_values("rec_dt")

    tlt_dates = tlt.index.to_numpy()
    bil_aligned = bil.reindex(tlt.index).ffill()
    ev_rows = []
    for _, row in sub.iterrows():
        rdt = np.datetime64(row["rec_dt"])
        pos = int(np.searchsorted(tlt_dates, rdt, side="right"))  # strictly AFTER auction record date
        if pos < 1 or pos + 21 >= len(tlt_dates):
            continue
        dt_e = tlt.index[pos]
        if dt_e < pd.Timestamp("2007-06-01"):
            continue
        r5 = float(tlt.iloc[pos + 5] / tlt.iloc[pos] - 1.0) - float(bil_aligned.iloc[pos + 5] / bil_aligned.iloc[pos] - 1.0)
        r21 = float(tlt.iloc[pos + 21] / tlt.iloc[pos] - 1.0) - float(bil_aligned.iloc[pos + 21] / bil_aligned.iloc[pos] - 1.0)
        ev_rows.append({"date": dt_e, "btc": float(row["btc"]), "tail_bp": float(row["tail_bp"]) if np.isfinite(row["tail_bp"]) else np.nan, "ex_5d": r5, "ex_21d": r21})

    ev_df = pd.DataFrame(ev_rows).drop_duplicates("date")
    auc_diag = {"n_auctions": int(len(ev_df))}
    if len(ev_df) >= 30:
        med_btc = ev_df["btc"].median()
        hi = ev_df[ev_df["btc"] >= med_btc]
        lo = ev_df[ev_df["btc"] < med_btc]
        auc_diag["corr_btc_ex5d"] = round(float(ev_df["btc"].corr(ev_df["ex_5d"])), 4)
        auc_diag["corr_btc_ex21d"] = round(float(ev_df["btc"].corr(ev_df["ex_21d"])), 4)
        auc_diag["hi_btc_ex21d_pct"] = round(float(hi["ex_21d"].mean() * 100.0), 3)
        auc_diag["lo_btc_ex21d_pct"] = round(float(lo["ex_21d"].mean() * 100.0), 3)
        sub_t = ev_df.dropna(subset=["tail_bp"])
        auc_diag["n_with_tail"] = int(len(sub_t))
        auc_diag["corr_tail_ex5d"] = round(float(sub_t["tail_bp"].corr(sub_t["ex_5d"])), 4) if len(sub_t) > 20 else None

    out = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "EXP-0040",
        "curve_duration_timing": curve_res,
        "treasury_auction_10y_30y": auc_diag,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, indent=2))

    print("=== EXP-0040 (1) TREASURY YIELD CURVE & BOND TREND TIMING (EXCESS OVER BIL, 2008-2026) ===")
    for k, v in curve_res.items():
        ta_m = v["total_all"]
        ex_a = v["excess_vs_bil_all"]
        ex_i = v["excess_vs_bil_is"]
        ex_o = v["excess_vs_bil_oos"]
        print(f"  {k:30s} [{v['time_in_bond_pct']:4.1f}%]: Tot CAGR={ta_m['cagr_pct']:+.2f}% DD={ta_m['maxdd_pct']:+.1f}% | ExBIL IS={ex_i['sharpe']:+.3f} OOS={ex_o['sharpe']:+.3f}(sh={v['shift_pct_oos']}%) All={ex_a['sharpe']:+.3f}")
    print("\n=== EXP-0040 (2) TREASURY 10Y/30Y AUCTION DEMAND ===")
    print(" ", auc_diag)


if __name__ == "__main__":
    main()
