#!/usr/bin/env python3
"""
EXP-0039 — Multi-Asset Total-Return ETF Rotation (GEM, Faber GTAA, Risk Parity, 26y Sector Mom) & DIX/GEX Study
Evaluates 2000-2026 dividend-adjusted adjClose ETFs + BIL cash ETF + SqueezeMetrics DIX/GEX strictly causally (t-1 lag),
with 5bp/10bp costs, 200 circular shifts, and Risk Meta WF AUC check for DIX/GEX.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
BROAD = ROOT / "data" / "broad"
TIINGO = ROOT / "data" / "etfs_tiingo"
OUT_JSON = ROOT / "research" / "artifacts" / "exp0039_etf_dix_gex_rotation.json"

N_SHIFTS = 200


def load_tr(sym: str) -> pd.Series:
    p = TIINGO / f"{sym}.csv"
    if not p.exists():
        p = BROAD / f"{sym}.csv"
    df = pd.read_csv(p)
    df["date"] = pd.to_datetime(df["date"])
    s = pd.to_numeric(df["adjclose"], errors="coerce").set_axis(df["date"]).dropna().sort_index()
    return s[~s.index.duplicated(keep="last")]


def perf(r: np.ndarray, scale: float = 252.0) -> dict:
    r = r[np.isfinite(r)]
    if len(r) < 30:
        return {"sharpe": 0.0, "cagr_pct": 0.0, "maxdd_pct": 0.0, "calmar": 0.0}
    mu, sd = float(np.mean(r)), float(np.std(r, ddof=1))
    shp = (mu / sd * math.sqrt(scale)) if sd > 0 else 0.0
    eq = np.cumprod(1.0 + r)
    cagr = (float(eq[-1]) ** (scale / len(r)) - 1.0) * 100.0 if eq[-1] > 0 else -100.0
    mdd = float(np.min(eq / np.maximum.accumulate(eq) - 1.0)) * 100.0
    cal = cagr / max(abs(mdd), 1e-3)
    return {"sharpe": round(shp, 3), "cagr_pct": round(cagr, 2), "maxdd_pct": round(mdd, 2), "calmar": round(cal, 3)}


def circ_shift_panel(W: np.ndarray, R: np.ndarray, cost_bps: float, ref_shp: float, rng: np.random.Generator) -> float:
    n = len(R)
    null = []
    min_s = max(21, n // 20)
    for _ in range(N_SHIFTS):
        s = int(rng.integers(min_s, n - min_s))
        Ws = np.roll(W, s, axis=0)
        to = np.sum(np.abs(np.diff(Ws, axis=0, prepend=0.0)), axis=1)
        rn = np.sum(Ws * R, axis=1) - to * (cost_bps / 10000.0)
        sd = float(np.std(rn, ddof=1))
        null.append(float(np.mean(rn) / sd * math.sqrt(252.0)) if sd > 0 else 0.0)
    return round(float(np.mean(np.array(null) <= ref_shp) * 100.0), 1)


def main() -> None:
    rng = np.random.default_rng(42)

    # --- PART 1: SQUEEZEMETRICS DIX & GEX (2011-05 .. 2026-11) ---
    dix = pd.read_csv(ROOT / "data" / "collect" / "dix_gex.csv")
    dix["date"] = pd.to_datetime(dix["date"])
    dix = dix.drop_duplicates("date").set_index("date").sort_index()
    spy_s = load_tr("SPY")
    bil_s = load_tr("BIL")
    idx_d = dix.index.intersection(spy_s.index).intersection(bil_s.index)
    r_spy_d = spy_s.pct_change().reindex(idx_d).fillna(0.0).to_numpy()
    r_bil_d = bil_s.pct_change().reindex(idx_d).fillna(0.0).to_numpy()
    dix_v = pd.to_numeric(dix["dix"].reindex(idx_d), errors="coerce")
    gex_v = pd.to_numeric(dix["gex"].reindex(idx_d), errors="coerce")
    dix_z = ((dix_v - dix_v.rolling(63).mean()) / dix_v.rolling(63).std()).shift(1).fillna(0.0).to_numpy()
    gex_z = ((gex_v - gex_v.rolling(63).mean()) / gex_v.rolling(63).std()).shift(1).fillna(0.0).to_numpy()

    is_d = idx_d < pd.Timestamp("2019-01-01")
    oos_d = idx_d >= pd.Timestamp("2019-01-01")
    dix_res = {}
    for name, w_spy in [
        ("SPY_BuyHold", np.ones(len(idx_d))),
        ("DIX_GT_MA63_vs_BIL", (dix_z > 0.0).astype(float)),
        ("DIX_High_p80_vs_BIL", (dix_z > 0.84).astype(float)),
        ("GEX_Pos_Regime_vs_BIL", (gex_v.shift(1).fillna(0.0).to_numpy() > 0.0).astype(float)),
        ("GEX_Neg_Contrarian_vs_BIL", (gex_z < -1.0).astype(float)),
    ]:
        W = np.column_stack([w_spy, 1.0 - w_spy])
        R = np.column_stack([r_spy_d, r_bil_d])
        to = np.sum(np.abs(np.diff(W, axis=0, prepend=0.0)), axis=1)
        rn = np.sum(W * R, axis=1) - to * 5e-4
        m_all = perf(rn)
        dix_res[name] = {
            "is_11_18": perf(rn[is_d]),
            "oos_19_26": perf(rn[oos_d]),
            "all": m_all,
            "shift_pct_oos": circ_shift_panel(W[oos_d], R[oos_d], 5.0, perf(rn[oos_d])["sharpe"], rng) if name != "SPY_BuyHold" else None,
        }

    # Walk-Forward Risk Meta check with DIX/GEX added (2012-2026)
    vol = pd.read_csv(ROOT / "data" / "collect" / "vol_stress_features.csv")
    vol["date"] = pd.to_datetime(vol["date"])
    vol = vol.set_index("date").sort_index()
    fsi = pd.read_csv(ROOT / "data" / "collect" / "ofr_fsi.csv")
    fsi["date"] = pd.to_datetime(fsi["Date"])
    fsi = fsi.set_index("date").sort_index()
    df_wf = pd.DataFrame(index=idx_d)
    r1 = spy_s.pct_change().reindex(idx_d)
    df_wf["vix"] = vol["vix"].reindex(idx_d).ffill()
    df_wf["slope_3m"] = vol["slope_3m"].reindex(idx_d).ffill()
    df_wf["ofr_fsi"] = fsi["OFR FSI"].reindex(idx_d).ffill()
    df_wf["rv21"] = r1.rolling(21).std() * math.sqrt(252.0)
    df_wf["rv5"] = r1.rolling(5).std() * math.sqrt(252.0)
    df_wf["dix_z63"] = ((dix_v - dix_v.rolling(63).mean()) / dix_v.rolling(63).std())
    df_wf["gex_z63"] = ((gex_v - gex_v.rolling(63).mean()) / gex_v.rolling(63).std())
    spy_raw = pd.read_csv(ROOT / "data" / "universe" / "SPY.csv")
    spy_raw["date"] = pd.to_datetime(spy_raw["date"])
    spy_raw = spy_raw.set_index("date").sort_index()
    c_u = spy_raw["close"].reindex(idx_d).ffill().to_numpy()
    l_u = spy_raw["low"].reindex(idx_d).ffill().to_numpy()
    r_u = spy_raw["close"].reindex(idx_d).ffill().pct_change().to_numpy()
    H, PG = 21, 31
    y_ts = np.full(len(idx_d), np.nan)
    for i in range(len(idx_d) - H):
        if c_u[i] > 0:
            rv_f = float(np.std(r_u[i + 1 : i + 1 + H], ddof=1) * math.sqrt(252.0))
            ml = float(np.min(l_u[i + 1 : i + 1 + H]) / c_u[i] - 1.0)
            y_ts[i] = 1.0 if (rv_f > 0.20 or ml <= -0.05) else 0.0
    df_wf["y_ts"] = y_ts
    dw = df_wf.dropna()
    wf_dix_auc = {}
    for label, fcols in [
        ("Base5", ["vix", "slope_3m", "ofr_fsi", "rv21", "rv5"]),
        ("Base5_Plus_DIX_GEX", ["vix", "slope_3m", "ofr_fsi", "rv21", "rv5", "dix_z63", "gex_z63"]),
    ]:
        preds, ys = [], []
        X, y = dw[fcols].to_numpy(), dw["y_ts"].to_numpy(int)
        for t0 in range(500, len(dw), 21):
            te = t0 - PG
            if te < 200:
                continue
            m = HistGradientBoostingClassifier(max_depth=2, max_iter=50, min_samples_leaf=40, l2_regularization=5.0, random_state=42)
            m.fit(X[:te], y[:te])
            t1 = min(t0 + 21, len(dw))
            preds.extend(m.predict_proba(X[t0:t1])[:, 1])
            ys.extend(y[t0:t1])
        wf_dix_auc[label] = round(float(roc_auc_score(ys, preds)), 4)

    # --- PART 2: GLOBAL MULTI-ASSET ETF ALLOCATION (2008-04 .. 2026-11) ---
    etfs = ["SPY", "ACWI", "QQQ", "IWM", "EEM", "EWJ", "AGG", "IEF", "TLT", "GLD", "DBC", "BIL"]
    px_g = pd.DataFrame({s: load_tr(s) for s in etfs}).dropna()
    ret_g = px_g.pct_change().fillna(0.0)
    idx_g = px_g.index
    start_g = idx_g >= pd.Timestamp("2009-05-01")  # after 252d lookback warmup
    is_g = start_g & (idx_g < pd.Timestamp("2018-01-01"))
    oos_g = idx_g >= pd.Timestamp("2018-01-01")
    R_g = ret_g.to_numpy()
    c2i = {s: i for i, s in enumerate(etfs)}
    reb_days = [i for i in range(252, len(idx_g) - 1, 21) if idx_g[i] >= pd.Timestamp("2009-05-01")]

    # Strategy weights matrices
    W_bh = np.zeros_like(R_g); W_bh[:, c2i["SPY"]] = 1.0
    W_6040 = np.zeros_like(R_g); W_6040[:, c2i["SPY"]] = 0.6; W_6040[:, c2i["AGG"]] = 0.4
    W_gem = np.zeros_like(R_g)
    W_gtaa = np.zeros_like(R_g)
    W_rp = np.zeros_like(R_g)

    sma200 = px_g.rolling(200).mean()
    ret252 = px_g.pct_change(252)
    vol63 = ret_g.rolling(63).std() * math.sqrt(252.0)

    gtaa_assets = ["SPY", "ACWI", "EEM", "AGG", "GLD", "DBC"]
    rp_assets = ["SPY", "ACWI", "TLT", "IEF", "GLD"]
    for k, r_i in enumerate(reb_days):
        i0 = r_i + 1
        i1 = reb_days[k + 1] + 1 if k + 1 < len(reb_days) else len(idx_g)
        # GEM: compare 252d SPY vs BIL; if SPY > BIL pick max(SPY, ACWI, EEM), else AGG
        if ret252.iloc[r_i]["SPY"] > ret252.iloc[r_i]["BIL"]:
            best_eq = max(["SPY", "ACWI", "EEM"], key=lambda a: float(ret252.iloc[r_i][a]))
            W_gem[i0:i1, c2i[best_eq]] = 1.0
        else:
            W_gem[i0:i1, c2i["AGG"]] = 1.0

        # Faber GTAA-6: 1/6 in each asset if px > SMA200 else BIL
        for a in gtaa_assets:
            if px_g.iloc[r_i][a] > sma200.iloc[r_i][a]:
                W_gtaa[i0:i1, c2i[a]] += 1.0 / len(gtaa_assets)
            else:
                W_gtaa[i0:i1, c2i["BIL"]] += 1.0 / len(gtaa_assets)

        # Risk Parity (inverse 63d vol across 5 asset classes, scaled to 10% target vol, cap 1.0x total)
        ivs = {a: 1.0 / max(float(vol63.iloc[r_i][a]), 0.02) for a in rp_assets}
        tot_iv = sum(ivs.values())
        w_raw = {a: ivs[a] / tot_iv for a in rp_assets}
        # estimate basket vol using recent 63d portfolio std
        rp_hist = sum(ret_g[a].iloc[r_i - 62 : r_i + 1] * w_raw[a] for a in rp_assets)
        p_vol = max(float(rp_hist.std() * math.sqrt(252.0)), 0.02)
        lev = min(1.0, 0.10 / p_vol)
        for a in rp_assets:
            W_rp[i0:i1, c2i[a]] = w_raw[a] * lev
        W_rp[i0:i1, c2i["BIL"]] = max(0.0, 1.0 - lev)

    global_res = {}
    for name, W in [("1_SPY_BuyHold", W_bh), ("2_Static_60_40", W_6040), ("3_Antonacci_GEM", W_gem), ("4_Faber_GTAA_6", W_gtaa), ("5_RiskParity_10VT_BIL", W_rp)]:
        to = np.sum(np.abs(np.diff(W, axis=0, prepend=0.0)), axis=1)
        rn5 = np.sum(W * R_g, axis=1) - to * 5e-4
        rn10 = np.sum(W * R_g, axis=1) - to * 10e-4
        m_all = perf(rn5[start_g])
        global_res[name] = {
            "net5bp_is_09_17": perf(rn5[is_g]),
            "net5bp_oos_18_26": perf(rn5[oos_g]),
            "net5bp_all": m_all,
            "net10bp_all": perf(rn10[start_g]),
            "shift_pct_oos": circ_shift_panel(W[oos_g], R_g[oos_g], 5.0, perf(rn5[oos_g])["sharpe"], rng) if name not in ("1_SPY_BuyHold", "2_Static_60_40") else None,
        }

    # --- PART 3: 26-YEAR US SPDR 9-SECTOR MOMENTUM (2001-2026) ---
    secs = ["XLB", "XLE", "XLF", "XLI", "XLK", "XLP", "XLU", "XLV", "XLY"]
    px_s = pd.DataFrame({s: load_tr(s) for s in secs}).dropna()
    ret_s = px_s.pct_change().fillna(0.0)
    idx_s = px_s.index
    start_s = idx_s >= pd.Timestamp("2001-02-01")
    is_s = start_s & (idx_s < pd.Timestamp("2014-01-01"))
    oos_s = idx_s >= pd.Timestamp("2014-01-01")
    R_s = ret_s.to_numpy()
    mom_12_1 = px_s.shift(21) / px_s.shift(252) - 1.0
    reb_s = [i for i in range(252, len(idx_s) - 1, 21) if idx_s[i] >= pd.Timestamp("2001-02-01")]
    W_sec_ls = np.zeros_like(R_s)
    W_sec_lo = np.zeros_like(R_s)
    W_sec_ew = np.full_like(R_s, 1.0 / len(secs))
    for k, r_i in enumerate(reb_s):
        i0 = r_i + 1
        i1 = reb_s[k + 1] + 1 if k + 1 < len(reb_s) else len(idx_s)
        order = np.argsort(mom_12_1.iloc[r_i].to_numpy())
        W_sec_ls[i0:i1, order[-3:]] = 0.5 / 3.0
        W_sec_ls[i0:i1, order[:3]] = -0.5 / 3.0
        W_sec_lo[i0:i1, order[-3:]] = 1.0 / 3.0

    sec_res = {}
    for name, W in [("SPDR_EqualWeight_All9", W_sec_ew), ("SPDR_Mom12_1_Top3_LO", W_sec_lo), ("SPDR_Mom12_1_LS_Top3_Bot3", W_sec_ls)]:
        to = np.sum(np.abs(np.diff(W, axis=0, prepend=0.0)), axis=1)
        rn5 = np.sum(W * R_s, axis=1) - to * 5e-4
        rn10 = np.sum(W * R_s, axis=1) - to * 10e-4
        sec_res[name] = {
            "net5bp_is_01_13": perf(rn5[is_s]),
            "net5bp_oos_14_26": perf(rn5[oos_s]),
            "net5bp_all": perf(rn5[start_s]),
            "net10bp_all": perf(rn10[start_s]),
            "shift_pct_oos": circ_shift_panel(W[oos_s], R_s[oos_s], 5.0, perf(rn5[oos_s])["sharpe"], rng) if name != "SPDR_EqualWeight_All9" else None,
        }

    out = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "EXP-0039",
        "dix_gex_timing": dix_res,
        "dix_gex_wf_tail_auc": wf_dix_auc,
        "global_etf_allocation_2009_2026": global_res,
        "sector_momentum_2001_2026": sec_res,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, indent=2))

    print("=== EXP-0039 (1) DIX / GEX TIMING & WF RISK AUC ===")
    print("  WF TailStress AUC:", wf_dix_auc)
    for k, v in dix_res.items():
        print(f"  {k:28s}: IS={v['is_11_18']['sharpe']:+.3f} OOS={v['oos_19_26']['sharpe']:+.3f}(sh={v['shift_pct_oos']}%) All={v['all']['sharpe']:+.3f} DD={v['all']['maxdd_pct']:+.1f}% Calmar={v['all']['calmar']}")

    print("\n=== EXP-0039 (2) GLOBAL MULTI-ASSET ETF ALLOCATION (2009-2026 TR, NET 5bp) ===")
    for k, v in global_res.items():
        print(f"  {k:24s}: IS={v['net5bp_is_09_17']['sharpe']:+.3f} OOS={v['net5bp_oos_18_26']['sharpe']:+.3f}(sh={v['shift_pct_oos']}%) All={v['net5bp_all']['sharpe']:+.3f} CAGR={v['net5bp_all']['cagr_pct']:+.2f}% DD={v['net5bp_all']['maxdd_pct']:+.1f}% Cal={v['net5bp_all']['calmar']}")

    print("\n=== EXP-0039 (3) 26-YEAR US 9-SECTOR MOMENTUM (2001-2026 TR, NET 5bp) ===")
    for k, v in sec_res.items():
        print(f"  {k:26s}: IS={v['net5bp_is_01_13']['sharpe']:+.3f} OOS={v['net5bp_oos_14_26']['sharpe']:+.3f}(sh={v['shift_pct_oos']}%) All={v['net5bp_all']['sharpe']:+.3f} CAGR={v['net5bp_all']['cagr_pct']:+.2f}% DD={v['net5bp_all']['maxdd_pct']:+.1f}%")


if __name__ == "__main__":
    main()
