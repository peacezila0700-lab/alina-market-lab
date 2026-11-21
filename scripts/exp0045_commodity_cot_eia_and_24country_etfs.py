#!/usr/bin/env python3
"""
EXP-0045 — 20y Disaggregated Commodity COT + Weekly EIA Inventories & 26y 24-Country ETFs (2000-2026 TR)
1) Tests CFTC Disaggregated Managed Money / Producer Net % OI (strict Friday release +1td) & EIA weekly crude/natgas
   inventories on GLD, SLV, PPLT, USO, UNG, DBA (dividend-adjusted adjclose).
2) Tests 24 Country Equity ETFs (2000-2026 TR) on 12-1 momentum, 21d reversal, and SMA126+VT12 trend.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "research" / "artifacts" / "exp0045_commodity_cot_eia_and_24country_etfs.json"


def perf_ex(tot: np.ndarray, rf: np.ndarray) -> dict:
    tot = tot[np.isfinite(tot)]
    rf = rf[: len(tot)]
    if len(tot) < 60:
        return {"sharpe": 0.0, "cagr_pct": 0.0, "maxdd_pct": 0.0, "calmar": 0.0}
    ex = tot - rf
    sd = float(np.std(ex, ddof=1))
    shp = float(np.mean(ex) / sd * math.sqrt(252.0)) if sd > 0 else 0.0
    eq = np.cumprod(1.0 + tot)
    cagr = (float(eq[-1]) ** (252.0 / len(tot)) - 1.0) * 100.0 if eq[-1] > 0 else -100.0
    mdd = float(np.min(eq / np.maximum.accumulate(eq) - 1.0)) * 100.0
    return {"sharpe": round(shp, 3), "cagr_pct": round(cagr, 2), "maxdd_pct": round(mdd, 2), "calmar": round(cagr / max(abs(mdd), 1e-3), 3)}


def load_tr(sym: str) -> pd.Series:
    df = pd.read_csv(ROOT / "data" / "broad" / f"{sym}.csv")
    df["date"] = pd.to_datetime(df["date"])
    return pd.to_numeric(df.drop_duplicates("date").set_index("date")["adjclose"], errors="coerce").sort_index()


def main() -> None:
    rng = np.random.default_rng(42)
    bil = load_tr("BIL")
    cot_c = pd.read_csv(ROOT / "data" / "cot" / "cot_disagg_commodities.csv.gz")
    cot_c["avail"] = pd.to_datetime(cot_c["available_from"])

    # --- PART 1: COMMODITY COT & EIA ---
    pairs = [("GOLD", "GLD"), ("SILVER", "SLV"), ("PLATINUM", "PPLT"), ("WTI_NYMEX", "USO"), ("NATGAS", "UNG"), ("CORN", "DBA")]
    cot_res = {}
    for comm, etf in pairs:
        px = load_tr(etf)
        idx = px.index.intersection(bil.index)
        idx = idx[idx >= pd.Timestamp("2009-01-01")]
        if len(idx) < 500:
            continue
        r_etf = px.pct_change().reindex(idx).fillna(0.0)
        r_bil = bil.pct_change().reindex(idx).fillna(0.0)

        sub = cot_c[cot_c["commodity"] == comm].sort_values("avail").drop_duplicates("avail").set_index("avail")
        mm = sub["mm_net_pct_oi"].reindex(idx, method="ffill")
        mm_z = (mm - mm.rolling(756).mean()) / mm.rolling(756).std()
        # Contrarian (buy crowded short MM z < -1.0) vs Momentum (buy crowded long MM z > +1.0 vs <0)
        w_mom = (mm_z > 0.0).astype(float).shift(1).fillna(0.0).to_numpy()
        w_cnt = (mm_z < -1.0).astype(float).shift(1).fillna(0.0).to_numpy()
        is_m, oos_m = idx < pd.Timestamp("2018-01-01"), idx >= pd.Timestamp("2018-01-01")
        rb = r_bil.to_numpy()
        re = r_etf.to_numpy()

        def ev(w):
            to = np.abs(np.diff(w, prepend=0.0))
            tot = w * re + (1.0 - w) * rb - to * 5e-4
            return {"is": perf_ex(tot[is_m], rb[is_m]), "oos": perf_ex(tot[oos_m], rb[oos_m]), "all": perf_ex(tot, rb)}

        cot_res[f"{comm}_{etf}"] = {"BuyHold": ev(np.ones(len(idx))), "MM_Mom_zgt0": ev(w_mom), "MM_Contrarian_zlt_m1": ev(w_cnt)}

    # Cross-sectional Managed Money COT across 6 commodities (rebalance weekly, Long Top2 - Short Bot2 z156)
    eia_res = {}
    for fname, etf, lag_d in [("eia_crude_stocks_w.csv", "USO", 5), ("eia_henryhub_w.csv", "UNG", 2)]:
        ep = ROOT / "data" / "collect" / fname
        if not ep.exists():
            continue
        edf = pd.read_csv(ep)
        dcol, vcol = edf.columns[0], edf.columns[1]
        edf[dcol] = pd.to_datetime(edf[dcol], errors="coerce")
        edf["val"] = pd.to_numeric(edf[vcol], errors="coerce")
        edf = edf.dropna(subset=[dcol, "val"]).sort_values(dcol)
        edf["chg"] = edf["val"].diff()
        edf["z52"] = (edf["chg"] - edf["chg"].rolling(52).mean()) / edf["chg"].rolling(52).std()
        # EIA report published Wed/Thu (+6 calendar days conservative after Friday report period)
        edf["avail"] = edf[dcol] + pd.Timedelta(days=lag_d)
        px = load_tr(etf)
        idx = px.index.intersection(bil.index)
        idx = idx[idx >= pd.Timestamp("2010-01-01")]
        es = edf.drop_duplicates("avail").set_index("avail")["z52"].reindex(idx, method="ffill")
        # Drawdown in inventory (z52 < -0.5) = bullish commodity
        w = (es < -0.5).astype(float).shift(1).fillna(0.0).to_numpy()
        to = np.abs(np.diff(w, prepend=0.0))
        re = px.pct_change().reindex(idx).fillna(0.0).to_numpy()
        rb = bil.pct_change().reindex(idx).fillna(0.0).to_numpy()
        tot = w * re + (1.0 - w) * rb - to * 5e-4
        is_m, oos_m = idx < pd.Timestamp("2018-01-01"), idx >= pd.Timestamp("2018-01-01")
        eia_res[etf] = {"BuyHold": perf_ex(re, rb), "EIA_Draw_Bullish_IS": perf_ex(tot[is_m], rb[is_m]), "EIA_Draw_Bullish_OOS": perf_ex(tot[oos_m], rb[oos_m]), "All": perf_ex(tot, rb)}

    # --- PART 2: 24 COUNTRY EQUITY ETFs (2008-2026 COMMON + 2000-2026 LONG PANEL) ---
    countries_19 = ["SPY", "EWA", "EWC", "EWG", "EWH", "EWJ", "EWT", "EWU", "EWW", "EWY", "EWZ", "EZA", "FXI", "EIDO", "EPU", "THD", "TUR", "VNM", "INDA"]
    avail_c = [c for c in countries_19 if (ROOT / "data" / "broad" / f"{c}.csv").exists()]
    px_c = pd.DataFrame({c: load_tr(c) for c in avail_c}).dropna()
    idx_c = px_c.index
    ret_c = px_c.pct_change().fillna(0.0)
    rb_c = bil.pct_change().reindex(idx_c).fillna(0.0).to_numpy()
    # Check start after 252d lookback
    valid_start = idx_c >= idx_c[252]
    idx_v = idx_c[valid_start]
    rb_v = rb_c[valid_start]
    rm_v = ret_c[valid_start].to_numpy()
    is_c, oos_c = idx_v < pd.Timestamp("2019-01-01"), idx_v >= pd.Timestamp("2019-01-01")

    mom252_21 = (px_c.shift(21) / px_c.shift(252) - 1.0)[valid_start]
    rev21 = (-px_c.pct_change(21))[valid_start]
    sma126 = (px_c > px_c.rolling(126).mean()).astype(float)
    rv21_c = (ret_c.rolling(21).std() * math.sqrt(252.0)).clip(lower=0.10)
    w_trend = (sma126 * np.minimum(1.0, 0.12 / rv21_c)).shift(1).fillna(0.0)[valid_start].to_numpy() / len(avail_c)

    reb = list(range(0, len(idx_v) - 1, 21))
    w_ew = np.full((len(idx_v), len(avail_c)), 1.0 / len(avail_c))
    w_m_lo = np.zeros_like(rm_v)
    w_m_ls = np.zeros_like(rm_v)
    w_r_ls = np.zeros_like(rm_v)
    for k, ri in enumerate(reb):
        i0 = ri + 1
        i1 = reb[k + 1] + 1 if k + 1 < len(reb) else len(idx_v)
        ms = mom252_21.iloc[ri]
        top4 = [avail_c.index(c) for c in ms.nlargest(4).index]
        bot4 = [avail_c.index(c) for c in ms.nsmallest(4).index]
        w_m_lo[i0:i1, top4] = 0.25
        w_m_ls[i0:i1, top4] = 0.125
        w_m_ls[i0:i1, bot4] = -0.125

        rs = rev21.iloc[ri]
        t4r = [avail_c.index(c) for c in rs.nlargest(4).index]
        b4r = [avail_c.index(c) for c in rs.nsmallest(4).index]
        w_r_ls[i0:i1, t4r] = 0.125
        w_r_ls[i0:i1, b4r] = -0.125

    country_res = {}
    for sn, wm, is_ls in [
        ("Country_EqualWeight_19", w_ew, False),
        ("Country_Mom12_1_Top4_LO", w_m_lo, False),
        ("Country_Mom12_1_Top4Bot4_LS", w_m_ls, True),
        ("Country_Rev21d_Top4Bot4_LS", w_r_ls, True),
        ("Country_SMA126_VT12_Cash", w_trend, False),
    ]:
        to = np.sum(np.abs(np.diff(wm, axis=0, prepend=0.0)), axis=1)
        cw = np.zeros(len(wm)) if is_ls else np.maximum(0.0, 1.0 - np.sum(wm, axis=1))
        tot = np.sum(wm * rm_v, axis=1) + cw * rb_v - to * 5e-4
        rf_cmp = np.zeros(len(wm)) if is_ls else rb_v
        m_oos = perf_ex(tot[oos_c], rf_cmp[oos_c])
        p_sh = None
        if sn != "Country_EqualWeight_19":
            null = []
            # shuffle columns (ticker permutation) across OOS!
            w_oos = wm[oos_c]; rm_oos = rm_v[oos_c]; rb_oos = rf_cmp[oos_c]; cw_oos = cw[oos_c]
            for _ in range(200):
                perm = rng.permutation(len(avail_c))
                wp = w_oos[:, perm]
                top = np.sum(np.abs(np.diff(wp, axis=0, prepend=0.0)), axis=1)
                totp = np.sum(wp * rm_oos, axis=1) + cw_oos * rb_oos - top * 5e-4
                null.append(perf_ex(totp, rb_oos)["sharpe"])
            p_sh = round(float(np.mean(np.array(null) <= m_oos["sharpe"]) * 100.0), 1)
        country_res[sn] = {"is": perf_ex(tot[is_c], rf_cmp[is_c]), "oos": m_oos, "all": perf_ex(tot, rf_cmp), "perm200_oos_pct": p_sh}

    out = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "EXP-0045",
        "commodity_cot_timing": cot_res,
        "eia_inventories_timing": eia_res,
        "country_19_etfs_common_start": idx_v[0].strftime("%Y-%m-%d"),
        "country_etf_strategies": country_res,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, indent=2))

    print("=== EXP-0045 (1) COMMODITY DISAGG COT TIMING (2009-2026) ===")
    for k, v in cot_res.items():
        print(f"  {k:16s}: BH={v['BuyHold']['all']['sharpe']:+.3f} | MM_Mom OOS={v['MM_Mom_zgt0']['oos']['sharpe']:+.3f} All={v['MM_Mom_zgt0']['all']['sharpe']:+.3f} | MM_Cnt OOS={v['MM_Contrarian_zlt_m1']['oos']['sharpe']:+.3f}")
    print("\n=== EXP-0045 (2) EIA WEEKLY INVENTORIES (USO/UNG) ===")
    print(" ", eia_res)
    print(f"\n=== EXP-0045 (3) {len(avail_c)} COUNTRY ETFs TR ({idx_v[0].strftime('%Y-%m-%d')}..{idx_v[-1].strftime('%Y-%m-%d')}) ===")
    for k, v in country_res.items():
        print(f"  {k:30s}: IS={v['is']['sharpe']:+.3f} OOS={v['oos']['sharpe']:+.3f}({v['perm200_oos_pct']}%) All={v['all']['sharpe']:+.3f}(CAGR={v['all']['cagr_pct']:+.1f}%,DD={v['all']['maxdd_pct']:+.1f}%)")


if __name__ == "__main__":
    main()
