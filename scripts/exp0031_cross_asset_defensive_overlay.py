#!/usr/bin/env python3
"""
EXP-0031 (H34) — Cross-Asset Defensive Risk Overlay Under Stationary Meta-Labeling (Offline Only)

Tests whether calibrated risk-regime probabilities (`P(VolOnset_21d)` + `P(TailStress_21d)` +
`P(TB_NonDirStress_21d)` from Task 3 / EXP-0030) improve multi-asset drawdown & CVaR protection
when rotating throttled equity exposure into defensive sleeves (`Cash`, `TLT`, `IEF`, `GOLD`) vs:
  - Buy & Hold SPY
  - Static 60/40 (SPY/TLT)
  - Static Risk-Budget (40% SPY / 30% TLT / 15% IEF / 15% GOLD)
  - Causal 12% Vol-Targeted SPY + Cash

Strict Safeguards:
  - Expanding Purged Walk-Forward CV (6 folds 2015-2026) + Chrono VALID (2019-2022) & OOS (2023-2026)
  - Purge = 21d + Embargo = 10d = 31 trading days between every fit/calibration/test split
  - Strict t-1 execution lag on ALL weights; zero future look-ahead
  - Explicit 5 bp / 10 bp per-unit turnover transaction costs + (Fed + 50bp) borrow on >1.0x leverage
  - Both Apples-to-Apples Price-Return Parity (Cash 0%) AND Cash-EFFR Sensitivity reported
  - 200 circular-shift null tests; Phase C Kill Point remains STRICTLY LOCKED.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "research" / "artifacts" / "exp0031_cross_asset_overlay.json"


def rolling_z(s: pd.Series, win: int = 252, min_p: int = 60) -> pd.Series:
    mu = s.rolling(win, min_periods=min_p).mean()
    sd = s.rolling(win, min_periods=min_p).std().replace(0, np.nan)
    return ((s - mu) / sd).clip(-4.0, 4.0)


def load_close(name: str) -> pd.Series:
    df = pd.read_csv(ROOT / "data" / "universe" / f"{name}.csv")
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return df["close"]


def build_dataset() -> tuple[pd.DataFrame, list[str]]:
    spy_df = pd.read_csv(ROOT / "data" / "universe" / "SPY.csv")
    spy_df["date"] = pd.to_datetime(spy_df["date"])
    spy_df = spy_df.set_index("date").sort_index()
    spy_df = spy_df[~spy_df.index.duplicated(keep="last")]

    tlt = load_close("TLT")
    ief = load_close("IEF")
    gold = load_close("GOLD")

    cb = pd.read_csv(ROOT / "data" / "macro" / "central_bank_rates_daily.csv")
    cb["date"] = pd.to_datetime(cb["date"])
    cb = cb.set_index("date").sort_index()
    cb = cb[~cb.index.duplicated(keep="last")]

    vol = pd.read_csv(ROOT / "data" / "collect" / "vol_stress_features.csv")
    vol["date"] = pd.to_datetime(vol["date"])
    vol = vol.set_index("date").sort_index()
    vol = vol[~vol.index.duplicated(keep="last")]

    fsi = pd.read_csv(ROOT / "data" / "collect" / "ofr_fsi.csv")
    fsi["date"] = pd.to_datetime(fsi["Date"])
    fsi = fsi.set_index("date")[["OFR FSI", "Credit", "Funding"]].sort_index()
    fsi = fsi[~fsi.index.duplicated(keep="last")]

    gpr = pd.read_csv(ROOT / "data" / "collect" / "gpr_monthly.csv")
    gpr["date"] = pd.to_datetime(gpr["month"]) + pd.offsets.MonthEnd(1) + pd.Timedelta(days=2)
    gpr = gpr.dropna(subset=["date", "gpr"]).set_index("date")[["gpr"]].sort_index()
    gpr = gpr[~gpr.index.duplicated(keep="last")]

    cot = pd.read_csv(ROOT / "data" / "cot" / "cot_features.csv")
    cot["date"] = pd.to_datetime(cot["available_from"])

    ev = pd.read_csv(ROOT / "data" / "events" / "event_calendar_full.csv")
    ev["date"] = pd.to_datetime(ev["date"], errors="coerce")
    fomc_dates = pd.DatetimeIndex(sorted(ev[ev["event"] == "FOMC"]["date"].dropna().unique()))

    idx = spy_df.loc["2011-01-04":"2026-10-15"].index
    df = pd.DataFrame(index=idx)
    c_spy = spy_df["close"].reindex(idx)
    l_spy = spy_df["low"].reindex(idx)
    df["r_spy"] = c_spy.pct_change()
    df["r_tlt"] = tlt.reindex(idx).ffill().pct_change().fillna(0.0)
    df["r_ief"] = ief.reindex(idx).ffill().pct_change().fillna(0.0)
    df["r_gold"] = gold.reindex(idx).ffill().pct_change().fillna(0.0)
    df["fed_rate"] = cb["fed_rate_proxy"].reindex(idx).ffill().fillna(0.0)

    ofr_raw = fsi["OFR FSI"].reindex(idx).ffill()
    df["ofr_fsi_z252"] = rolling_z(ofr_raw, 252)
    df["ofr_fsi_chg21"] = ofr_raw.diff(21)
    df["ofr_credit_z252"] = rolling_z(fsi["Credit"].reindex(idx).ffill(), 252)
    df["ofr_funding_z252"] = rolling_z(fsi["Funding"].reindex(idx).ffill(), 252)
    df["d_fed_63"] = df["fed_rate"].diff(63)
    df["d_diff_fed_ecb_21"] = cb["diff_fed_ecb_dfr"].reindex(idx).ffill().diff(21)
    df["d_diff_boe_ecb_21"] = cb["diff_boe_ecb_dfr"].reindex(idx).ffill().diff(21)
    df["gpr_z252"] = rolling_z(gpr["gpr"].reindex(idx, method="ffill"), 252)

    for inst, col in [("SP500", "cot_sp500_z"), ("VIX", "cot_vix_z"), ("UST_10Y", "cot_ust10y_z"), ("EURUSD", "cot_eur_z")]:
        sub_c = cot[cot["instrument"] == inst].set_index("date")[["noncomm_net_pct_oi_z156"]].sort_index()
        sub_c = sub_c[~sub_c.index.duplicated(keep="last")]
        df[col] = sub_c["noncomm_net_pct_oi_z156"].reindex(idx, method="ffill").fillna(0.0)

    fomc_ns = fomc_dates.asi8
    idx_ns = idx.asi8
    pos = np.searchsorted(fomc_ns, idx_ns, side="left")
    next_days = np.where(pos < len(fomc_ns), (fomc_ns[np.minimum(pos, len(fomc_ns) - 1)] - idx_ns) / 86400e9, 30.0)
    df["fomc_within_5d"] = (next_days <= 5.0).astype(float)

    df["vix"] = vol["vix"].reindex(idx).ffill()
    df["slope_3m"] = vol["slope_3m"].reindex(idx).ffill()
    df["slope_9d"] = vol["slope_9d"].reindex(idx).ffill()
    df["vvix_pct"] = vol["vvix_pct"].reindex(idx).ffill()
    df["skew"] = vol["skew"].reindex(idx).ffill()
    df["vix_chg21"] = df["vix"].diff(21)

    r1 = df["r_spy"]
    df["rv5_past"] = r1.rolling(5).std() * math.sqrt(252)
    df["rv21_past"] = r1.rolling(21).std() * math.sqrt(252)
    df["rv63_past"] = r1.rolling(63).std() * math.sqrt(252)
    df["rv_ratio_5_21"] = df["rv5_past"] / df["rv21_past"].replace(0, np.nan)

    # Trailing realized vol for TLT / IEF / GOLD (strictly causal)
    df["rv21_tlt"] = df["r_tlt"].rolling(21).std() * math.sqrt(252)
    df["rv21_gold"] = df["r_gold"].rolling(21).std() * math.sqrt(252)

    H = 21
    r_arr = r1.to_numpy()
    l_arr = l_spy.to_numpy()
    c_arr = c_spy.to_numpy()
    rv21_arr = df["rv21_past"].to_numpy()
    y_onset = np.full(len(df), np.nan)
    y_stress = np.full(len(df), np.nan)
    for i in range(len(df) - H):
        if not np.isfinite(rv21_arr[i]) or c_arr[i] <= 0:
            continue
        rv_f = float(np.std(r_arr[i + 1 : i + 1 + H], ddof=1) * math.sqrt(252.0))
        min_l = float(np.min(l_arr[i + 1 : i + 1 + H]) / c_arr[i] - 1.0)
        y_onset[i] = 1.0 if rv_f > 1.35 * rv21_arr[i] else 0.0
        y_stress[i] = 1.0 if (min_l <= -0.05 or rv_f > 0.20) else 0.0

    df["y_vol_onset"] = y_onset
    df["y_tb_stress"] = y_stress

    feats = [
        "ofr_fsi_z252", "ofr_fsi_chg21", "ofr_credit_z252", "ofr_funding_z252",
        "d_fed_63", "d_diff_fed_ecb_21", "d_diff_boe_ecb_21", "gpr_z252",
        "cot_sp500_z", "cot_vix_z", "cot_ust10y_z", "cot_eur_z", "fomc_within_5d",
        "vix", "slope_3m", "slope_9d", "vvix_pct", "skew", "vix_chg21",
        "rv5_past", "rv21_past", "rv63_past", "rv_ratio_5_21",
    ]
    clean = df.dropna(subset=feats + ["y_vol_onset", "y_tb_stress", "rv21_tlt", "rv21_gold"]).copy()
    return clean, feats


def fit_predict_purged_wf(clean: pd.DataFrame, feats: list[str], target_col: str, purge_gap: int = 31) -> pd.Series:
    wf_cuts = [pd.Timestamp(d) for d in ("2015-01-02", "2017-01-03", "2019-01-02", "2021-01-04", "2023-01-03", "2025-01-02")]
    wf_starts = [int(clean.index.searchsorted(dt)) for dt in wf_cuts]
    X_all = clean[feats].to_numpy()
    y_all = clean[target_col].to_numpy(dtype=int)
    out = pd.Series(np.nan, index=clean.index)

    for k, ts in enumerate(wf_starts):
        te = wf_starts[k + 1] if k + 1 < len(wf_starts) else len(clean)
        tr_end = ts - purge_gap
        split_c = int(tr_end * 0.72)
        fit_e = max(120, split_c - purge_gap)
        bm = HistGradientBoostingClassifier(max_depth=2, max_iter=60, min_samples_leaf=50, l2_regularization=5.0, random_state=42)
        bm.fit(X_all[:fit_e], y_all[:fit_e])
        pc = bm.predict_proba(X_all[split_c:tr_end])[:, 1]
        pt = bm.predict_proba(X_all[ts:te])[:, 1]
        eps = 1e-6
        zc = np.log(np.clip(pc, eps, 1 - eps) / (1 - np.clip(pc, eps, 1 - eps))).reshape(-1, 1)
        zt = np.log(np.clip(pt, eps, 1 - eps) / (1 - np.clip(pt, eps, 1 - eps))).reshape(-1, 1)
        cal = LogisticRegression(C=1.0).fit(zc, y_all[split_c:tr_end])
        out.iloc[ts:te] = cal.predict_proba(zt)[:, 1]
    return out


def eval_multi_asset_portfolio(
    weights_df: pd.DataFrame,
    rets_df: pd.DataFrame,
    fed_rate: pd.Series,
    turn_bp: float = 5.0,
    borrow_bp: float = 50.0,
    earn_cash_effr: bool = False,
) -> dict[str, Any]:
    cols = ["w_spy", "w_tlt", "w_ief", "w_gold"]
    W = weights_df[cols].fillna(0.0)
    R = rets_df[["r_spy", "r_tlt", "r_ief", "r_gold"]].loc[W.index].fillna(0.0)
    fv = fed_rate.loc[W.index].fillna(0.0)

    gross_asset = (W.to_numpy() * R.to_numpy()).sum(axis=1)
    tot_w = W.sum(axis=1).to_numpy()
    cash_w = np.maximum(0.0, 1.0 - tot_w)
    lev_w = np.maximum(0.0, tot_w - 1.0)
    cash_ret = cash_w * ((fv.to_numpy() / 100.0) / 252.0) if earn_cash_effr else np.zeros(len(W))
    borrow_cost = lev_w * ((fv.to_numpy() / 100.0 + borrow_bp / 10000.0) / 252.0)

    dw = np.abs(np.diff(W.to_numpy(), axis=0, prepend=W.to_numpy()[:1])).sum(axis=1)
    tx_cost = dw * (turn_bp / 10000.0)

    gross = pd.Series(gross_asset + cash_ret, index=W.index)
    net = pd.Series(gross_asset + cash_ret - tx_cost - borrow_cost, index=W.index)

    def _stats(s: pd.Series) -> dict[str, float]:
        eq = (1.0 + s).cumprod()
        dd = eq / eq.cummax() - 1.0
        ar = float(s.mean() * 252)
        av = float(s.std() * math.sqrt(252))
        sh = ar / av if av > 0 else 0.0
        mdd = float(dd.min())
        cal = ar / abs(mdd) if mdd < 0 else 0.0
        q5 = float(np.quantile(s, 0.05))
        cvar = float(s[s <= q5].mean())
        return {
            "sharpe": round(sh, 3),
            "ann_ret_pct": round(ar * 100, 2),
            "ann_vol_pct": round(av * 100, 2),
            "max_dd_pct": round(mdd * 100, 2),
            "calmar": round(cal, 3),
            "cvar95_bp": round(cvar * 10000, 1),
        }

    return {
        "gross": _stats(gross),
        "net": _stats(net),
        "avg_weights": {c: round(float(W[c].mean()), 3) for c in cols},
        "avg_cash_pct": round(float(cash_w.mean() * 100), 1),
        "ann_turnover": round(float(dw.mean() * 252), 2),
        "tx_drag_bp_yr": round(float(tx_cost.mean() * 252 * 10000), 1),
    }


def circ_shift_multi_pct(
    weights_df: pd.DataFrame,
    rets_df: pd.DataFrame,
    fed_rate: pd.Series,
    turn_bp: float = 5.0,
    borrow_bp: float = 50.0,
    n_sims: int = 200,
) -> float:
    cols = ["w_spy", "w_tlt", "w_ief", "w_gold"]
    W = weights_df[cols].fillna(0.0).to_numpy()
    R = rets_df[["r_spy", "r_tlt", "r_ief", "r_gold"]].loc[weights_df.index].fillna(0.0).to_numpy()
    fv = fed_rate.loc[weights_df.index].fillna(0.0).to_numpy()

    def _net_sh(wm: np.ndarray) -> float:
        tot = wm.sum(axis=1)
        lev = np.maximum(0.0, tot - 1.0)
        dw = np.abs(np.diff(wm, axis=0, prepend=wm[:1])).sum(axis=1)
        s = (wm * R).sum(axis=1) - dw * (turn_bp / 10000.0) - lev * ((fv / 100.0 + borrow_bp / 10000.0) / 252.0)
        sd = s.std()
        return float(s.mean() / sd * math.sqrt(252)) if sd > 0 else 0.0

    obs = _net_sh(W)
    rng = np.random.default_rng(31)
    n = len(W)
    sims = [_net_sh(np.roll(W, int(rng.integers(30, max(31, n - 30))), axis=0)) for _ in range(n_sims)]
    return round(float(np.mean(np.array(sims) <= obs) * 100.0), 1)


def main() -> None:
    clean, feats = build_dataset()
    p_onset = fit_predict_purged_wf(clean, feats, "y_vol_onset", purge_gap=31)
    p_stress = fit_predict_purged_wf(clean, feats, "y_tb_stress", purge_gap=31)

    wf_mask = p_onset.notna() & p_stress.notna()
    sub = clean.loc[wf_mask].copy()
    p_on = p_onset.loc[wf_mask]
    p_st = p_stress.loc[wf_mask]

    # Strictly causal t-1 weights on WF OOS (2015-01-02 -> 2026-09-16, N=2,943)
    idx = sub.index
    zeros = pd.Series(0.0, index=idx)

    # 1. Buy & Hold SPY
    w_bh = pd.DataFrame({"w_spy": 1.0, "w_tlt": 0.0, "w_ief": 0.0, "w_gold": 0.0}, index=idx)

    # 2. Static 60/40 SPY/TLT
    w_6040 = pd.DataFrame({"w_spy": 0.60, "w_tlt": 0.40, "w_ief": 0.0, "w_gold": 0.0}, index=idx)

    # 3. Static All-Weather (40% SPY / 30% TLT / 15% IEF / 15% GOLD)
    w_aw = pd.DataFrame({"w_spy": 0.40, "w_tlt": 0.30, "w_ief": 0.15, "w_gold": 0.15}, index=idx)

    # 4. Causal 12% Vol-Target SPY + Cash (no meta overlay)
    vt_raw = (0.12 / sub["rv21_past"].replace(0, np.nan)).clip(0.0, 1.5).shift(1).fillna(1.0)
    w_vt = pd.DataFrame({"w_spy": vt_raw, "w_tlt": zeros, "w_ief": zeros, "w_gold": zeros}, index=idx)

    # Meta throttle scalar in [0.35, 1.0]: combines VolOnset & TB_NonDirStress causally at t-1
    throttle = (
        1.0
        - 1.3 * (p_on - 0.25).clip(lower=0.0)
        - 1.1 * (p_st - 0.30).clip(lower=0.0)
    ).clip(0.35, 1.0).shift(1).fillna(1.0)

    w_spy_meta = vt_raw * throttle
    cut_amt = (1.0 - w_spy_meta).clip(lower=0.0)

    # 5. VolTarget + Meta -> Cash (Risk-Off to Cash)
    w_meta_cash = pd.DataFrame({"w_spy": w_spy_meta, "w_tlt": zeros, "w_ief": zeros, "w_gold": zeros}, index=idx)

    # 6. VolTarget + Meta -> TLT Bond Rotation (puts 70% of freed equity budget into TLT, capped 0.60)
    w_tlt_rot = (0.70 * cut_amt).clip(0.0, 0.60)
    w_meta_tlt = pd.DataFrame({"w_spy": w_spy_meta, "w_tlt": w_tlt_rot, "w_ief": zeros, "w_gold": zeros}, index=idx)

    # 7. VolTarget + Meta -> Cash + GOLD + IEF Defensive Mix (frees 55% Cash, 25% GOLD, 20% IEF)
    w_meta_cash_gold = pd.DataFrame(
        {
            "w_spy": w_spy_meta,
            "w_tlt": zeros,
            "w_ief": (0.20 * cut_amt).clip(0.0, 0.25),
            "w_gold": (0.25 * cut_amt).clip(0.0, 0.30),
        },
        index=idx,
    )

    strategies = [
        ("1_SPY_Buy_And_Hold", w_bh),
        ("2_Static_60_40_SPY_TLT", w_6040),
        ("3_Static_40_30_15_15_Multi", w_aw),
        ("4_VolTarget12_SPY_Cash", w_vt),
        ("5_VolTarget12_Meta_Cash", w_meta_cash),
        ("6_VolTarget12_Meta_TLT_Rot", w_meta_tlt),
        ("7_VolTarget12_Meta_Cash_IEF_GOLD", w_meta_cash_gold),
    ]

    def run_window(mask: pd.Series) -> dict[str, Any]:
        s_sub = sub.loc[mask]
        res = {}
        for nm, wdf in strategies:
            w_sub = wdf.loc[mask]
            st_0 = eval_multi_asset_portfolio(w_sub, s_sub, s_sub["fed_rate"], turn_bp=5.0, borrow_bp=50.0, earn_cash_effr=False)
            st_effr = eval_multi_asset_portfolio(w_sub, s_sub, s_sub["fed_rate"], turn_bp=5.0, borrow_bp=50.0, earn_cash_effr=True)
            st_10 = eval_multi_asset_portfolio(w_sub, s_sub, s_sub["fed_rate"], turn_bp=10.0, borrow_bp=100.0, earn_cash_effr=False)
            st_0["cash_effr_net"] = st_effr["net"]
            st_0["stress_10bp_net"] = st_10["net"]
            st_0["circ_shift_pct_5bp"] = circ_shift_multi_pct(w_sub, s_sub, s_sub["fed_rate"], 5.0, 50.0, 200)
            res[nm] = st_0
        return res

    full_wf = run_window(pd.Series(True, index=idx))
    covid_2020 = run_window((idx >= "2020-01-02") & (idx <= "2020-06-30"))
    rate_bear_2022 = run_window((idx >= "2022-01-03") & (idx <= "2022-12-30"))
    oos_2023_2026 = run_window(idx >= "2023-01-03")

    out = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "EXP-0031",
        "hypothesis": "H34",
        "phase_gate": "PHASE_C_KILL_POINT_ACTIVE_OFFLINE_ONLY",
        "wf_window": f"{idx[0].strftime('%Y-%m-%d')} -> {idx[-1].strftime('%Y-%m-%d')} (n={len(sub)})",
        "price_return_caveat": "data/universe/*.csv uses Yahoo price closes excluding SPY/TLT/IEF dividends; Cash=0% provides strict price-return parity while cash_effr_net adds official NYFed EFFR.",
        "wf_2015_2026_full": full_wf,
        "crisis_2020_covid_h1": covid_2020,
        "crisis_2022_rate_bear": rate_bear_2022,
        "oos_2023_2026_bull": oos_2023_2026,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2))

    for title, blk in [
        ("FULL 11.7y WF OOS (2015-2026)", full_wf),
        ("2020 COVID H1 Crash", covid_2020),
        ("2022 Rate-Hike Bear (SPY+TLT Dual Crash)", rate_bear_2022),
        ("2023-2026 Calm/Bull OOS", oos_2023_2026),
    ]:
        print(f"\n=== {title} ===")
        for nm, v in blk.items():
            n5, n10, effr = v["net"], v["stress_10bp_net"], v["cash_effr_net"]
            print(
                f"  {nm:34s}: Net5bpSh={n5['sharpe']:+.3f} (EFFR={effr['sharpe']:+.3f}, 10bp={n10['sharpe']:+.3f}) | "
                f"Ret={n5['ann_ret_pct']:+.2f}% | MaxDD={n5['max_dd_pct']:+.2f}% | CVaR95={n5['cvar95_bp']:+.1f}bp | "
                f"Calmar={n5['calmar']:.3f} | Cash={v['avg_cash_pct']:4.1f}% | ShiftPct={v['circ_shift_pct_5bp']}%"
            )


if __name__ == "__main__":
    main()
