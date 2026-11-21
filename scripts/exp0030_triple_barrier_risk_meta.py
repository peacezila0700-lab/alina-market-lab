#!/usr/bin/env python3
"""
EXP-0030 (H33) — Offline Risk & Volatility Meta-Labeling with Path-Dependent Triple-Barrier Method

Strictly offline research under active Phase C Kill Point:
  - NO directional price-return alpha search
  - NO hyperparameter tuning to chase positive outcomes
  - NEVER unlocks Phase D ML or Live/Demo trading

Two Complementary Empirical Tracks:
  Track A: SPY Daily Triple-Barrier Risk/Drawdown Meta-Labeling (2011-04..2026-09)
    - Strictly chronological IS (2011-2018) / VALID (2019-2022) / OOS (2023-2026) with Purge=21d + Embargo=10d
    - Plus 5-fold Purged Expanding Walk-Forward CV (2015-2026)
    - Evaluates BOTH:
        (A1) TB_VolNorm: volatility-scaled first-passage barrier (-2.0*sigma_21d vs +2.5*sigma_21d, H=21d)
        (A2) TB_CapitalDD5: fixed capital drawdown barrier (-5.0% drawdown vs +5.0% recovery, H=21d)
    - Explicit Costs: Spread (2bp) + Commission (1bp) + Slippage (2bp) = 5bp/unit turnover (and 10bp stress)
      + Financing/Swap borrow cost on leverage max(0, w-1) at (FedRate + 50bp)/252
    - 200 Circular-Shift Null Permutations + HAR & Buy&Hold & VolTarget Baselines

  Track B: EURGBP H1 23-Year Bid/Ask Intraday Triple-Barrier Risk/Cost-Shock Audit (2003-08..2026-11)
    - Strictly chronological IS (2003-2015) / VALID (2016-2020) / OOS (2021-2026) with Purge=24h + Embargo=12h
    - Properly 24h-scaled volatility sigma_24h = ATR24 * sqrt(24)
    - Real Dukascopy Bid/Ask spreads + Commission (0.70 pip RT) + Slippage (0.30 pip RT)
      + BoE-ECB Swap (3x Wed) + 0.25 pip/night retail markup
    - Evaluates whether Triple-Barrier Risk Gating improves intraday execution survival & cost drag
      vs Always-Execute and Rollover-Only filter, while testing if net FX expectancy stays <= 0.
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
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "research" / "artifacts" / "exp0030_triple_barrier.json"


def rolling_z(s: pd.Series, win: int = 252, min_p: int = 60) -> pd.Series:
    mu = s.rolling(win, min_periods=min_p).mean()
    sd = s.rolling(win, min_periods=min_p).std().replace(0, np.nan)
    return ((s - mu) / sd).clip(-4.0, 4.0)


def ece_score(y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(y_true)
    for i in range(n_bins):
        lo, hi = bins[i], bins[i + 1]
        mask = (y_prob >= lo) & (y_prob <= hi) if i == n_bins - 1 else (y_prob >= lo) & (y_prob < hi)
        if mask.sum() > 0:
            ece += (mask.sum() / n) * abs(float(y_true[mask].mean()) - float(y_prob[mask].mean()))
    return float(ece)


def clf_metrics(y_true: np.ndarray, y_prob: np.ndarray, base_rate: float) -> dict[str, Any]:
    y_true = np.asarray(y_true, dtype=int)
    y_prob = np.clip(np.asarray(y_prob, dtype=float), 1e-6, 1.0 - 1e-6)
    pos = float(y_true.mean())
    auc = float(roc_auc_score(y_true, y_prob)) if len(np.unique(y_true)) > 1 else float("nan")
    pr = float(average_precision_score(y_true, y_prob)) if len(np.unique(y_true)) > 1 else float("nan")
    brier = float(brier_score_loss(y_true, y_prob))
    b_clim = float(brier_score_loss(y_true, np.full_like(y_prob, base_rate)))
    bss = 1.0 - (brier / b_clim) if b_clim > 0 else 0.0
    return {
        "n": int(len(y_true)),
        "pos_rate": round(pos, 4),
        "roc_auc": round(auc, 4),
        "pr_auc": round(pr, 4),
        "pr_lift": round(pr / pos, 3) if pos > 0 else None,
        "brier": round(brier, 4),
        "bss": round(bss, 4),
        "ece": round(ece_score(y_true, y_prob), 4),
        "mean_pred": round(float(y_prob.mean()), 4),
    }


def perm_test_auc(y_true: np.ndarray, y_prob: np.ndarray, n_sims: int = 200, seed: int = 30) -> dict[str, Any]:
    obs = float(roc_auc_score(y_true, y_prob))
    rng = np.random.default_rng(seed)
    n = len(y_true)
    sims = [float(roc_auc_score(np.roll(y_true, int(rng.integers(30, max(31, n - 30)))), y_prob)) for _ in range(n_sims)]
    arr = np.asarray(sims)
    return {
        "obs_auc": round(obs, 4),
        "null_mean_auc": round(float(arr.mean()), 4),
        "null_p99_auc": round(float(np.quantile(arr, 0.99)), 4),
        "perm_p_value": round(float(np.mean(arr >= obs)), 4),
        "n_perms": n_sims,
    }


def portfolio_stats_full(
    w: pd.Series, ret: pd.Series, fed_rate: pd.Series, turn_cost_bp: float, borrow_spread_bp: float
) -> dict[str, Any]:
    df = pd.concat([w.rename("w"), ret.rename("r"), fed_rate.rename("fed")], axis=1).dropna()
    wv, rv, fv = df["w"], df["r"], df["fed"]
    dw = wv.diff().abs().fillna(0.0)
    gross = wv * rv
    tx_cost = dw * (turn_cost_bp / 10000.0)
    lev = (wv - 1.0).clip(lower=0.0)
    borrow_cost = lev * ((fv / 100.0 + borrow_spread_bp / 10000.0) / 252.0)
    net = gross - tx_cost - borrow_cost

    def _summarize(s: pd.Series) -> dict[str, float]:
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
        "gross": _summarize(gross),
        "net": _summarize(net),
        "avg_exposure": round(float(wv.mean()), 3),
        "ann_turnover": round(float(dw.mean() * 252), 2),
        "tx_drag_bp_yr": round(float(tx_cost.mean() * 252 * 10000), 1),
        "swap_borrow_drag_bp_yr": round(float(borrow_cost.mean() * 252 * 10000), 1),
    }


def circ_shift_sharpe_pct(
    w: pd.Series, ret: pd.Series, fed_rate: pd.Series, turn_cost_bp: float, borrow_spread_bp: float, n_sims: int = 200
) -> float:
    df = pd.concat([w.rename("w"), ret.rename("r"), fed_rate.rename("fed")], axis=1).dropna()
    wv, rv, fv = df["w"].to_numpy(), df["r"].to_numpy(), df["fed"].to_numpy()
    dw = np.abs(np.diff(wv, prepend=wv[0]))
    obs = wv * rv - dw * (turn_cost_bp / 10000.0) - np.maximum(0.0, wv - 1.0) * ((fv / 100.0 + borrow_spread_bp / 10000.0) / 252.0)
    obs_sh = obs.mean() / obs.std() * math.sqrt(252) if obs.std() > 0 else 0.0
    rng = np.random.default_rng(30)
    n = len(wv)
    sims = []
    for _ in range(n_sims):
        sh = int(rng.integers(30, max(31, n - 30)))
        ws = np.roll(wv, sh)
        dws = np.abs(np.diff(ws, prepend=ws[0]))
        ns = ws * rv - dws * (turn_cost_bp / 10000.0) - np.maximum(0.0, ws - 1.0) * ((fv / 100.0 + borrow_spread_bp / 10000.0) / 252.0)
        sims.append(ns.mean() / ns.std() * math.sqrt(252) if ns.std() > 0 else 0.0)
    return round(float(np.mean(np.array(sims) <= obs_sh) * 100.0), 1)


def run_track_a_spy_triple_barrier() -> dict[str, Any]:
    H = 21
    EMB = 10
    PURGE_GAP = H + EMB  # 31 trading days

    spy = pd.read_csv(ROOT / "data" / "universe" / "SPY.csv")
    spy["date"] = pd.to_datetime(spy["date"])
    spy = spy.set_index("date").sort_index()
    spy = spy[~spy.index.duplicated(keep="last")]

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

    idx = spy.loc["2011-01-04":"2026-10-15"].index
    df = pd.DataFrame(index=idx)
    c, h, l = spy["close"].reindex(idx), spy["high"].reindex(idx), spy["low"].reindex(idx)
    ret1 = c.pct_change()
    df["ret1"] = ret1
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

    df["rv5_past"] = ret1.rolling(5).std() * math.sqrt(252)
    df["rv21_past"] = ret1.rolling(21).std() * math.sqrt(252)
    df["rv63_past"] = ret1.rolling(63).std() * math.sqrt(252)
    df["rv_ratio_5_21"] = df["rv5_past"] / df["rv21_past"].replace(0, np.nan)

    # Compute THREE Triple-Barrier Risk Meta-Labels strictly on [t+1..t+21]:
    # (A1) y_tb_volnorm: directional race (-2.0*sigma_21d hit before +2.5*sigma_21d)
    # (A2) y_tb_dd5: directional race (-5.0% hit before +5.0%)
    # (A3) y_tb_nondir_stress: pure non-directional risk-barrier breach (-5.0% drawdown touched OR 21d RV > 20%)
    c_arr, h_arr, l_arr = c.to_numpy(), h.to_numpy(), l.to_numpy()
    sig_ann = df["rv21_past"].to_numpy()
    r_arr = ret1.to_numpy()
    y_volnorm = np.full(len(df), np.nan)
    y_dd5 = np.full(len(df), np.nan)
    y_nondir = np.full(len(df), np.nan)

    for i in range(len(df) - H):
        if not np.isfinite(sig_ann[i]) or sig_ann[i] <= 0 or c_arr[i] <= 0:
            continue
        vol_h = sig_ann[i] * math.sqrt(H / 252.0)
        b_dn, b_up = -max(0.030, 2.0 * vol_h), +max(0.035, 2.5 * vol_h)
        lbl_vn = 0
        for k in range(1, H + 1):
            if l_arr[i + k] / c_arr[i] - 1.0 <= b_dn:
                lbl_vn = 1
                break
            if h_arr[i + k] / c_arr[i] - 1.0 >= b_up:
                lbl_vn = 0
                break
        y_volnorm[i] = float(lbl_vn)

        lbl_dd5 = 0
        hit_dn5 = False
        for k in range(1, H + 1):
            if l_arr[i + k] / c_arr[i] - 1.0 <= -0.05:
                hit_dn5 = True
                if lbl_dd5 == 0:
                    lbl_dd5 = 1
                break
            if h_arr[i + k] / c_arr[i] - 1.0 >= +0.05:
                lbl_dd5 = 0
                break
        y_dd5[i] = float(lbl_dd5)

        min_low_21 = float(np.min(l_arr[i + 1 : i + 1 + H]) / c_arr[i] - 1.0)
        rv_fwd_21 = float(np.std(r_arr[i + 1 : i + 1 + H], ddof=1) * math.sqrt(252.0))
        y_nondir[i] = 1.0 if (min_low_21 <= -0.05 or rv_fwd_21 > 0.20) else 0.0

    df["y_tb_volnorm"] = y_volnorm
    df["y_tb_dd5"] = y_dd5
    df["y_tb_nondir_stress"] = y_nondir

    macro_vol_feats = [
        "ofr_fsi_z252", "ofr_fsi_chg21", "ofr_credit_z252", "ofr_funding_z252",
        "d_fed_63", "d_diff_fed_ecb_21", "d_diff_boe_ecb_21", "gpr_z252",
        "cot_sp500_z", "cot_vix_z", "cot_ust10y_z", "cot_eur_z", "fomc_within_5d",
        "vix", "slope_3m", "slope_9d", "vvix_pct", "skew", "vix_chg21",
    ]
    har_feats = ["rv5_past", "rv21_past", "rv63_past", "rv_ratio_5_21"]
    all_feats = macro_vol_feats + har_feats

    clean = df.dropna(subset=all_feats + ["y_tb_volnorm", "y_tb_dd5", "y_tb_nondir_stress"]).copy()

    valid_start_dt = pd.Timestamp("2019-01-02")
    oos_start_dt = pd.Timestamp("2023-01-03")
    pos_val = int(clean.index.searchsorted(valid_start_dt))
    pos_oos = int(clean.index.searchsorted(oos_start_dt))

    is_df = clean.iloc[: pos_val - PURGE_GAP]
    val_df = clean.iloc[pos_val : pos_oos - PURGE_GAP]
    oos_df = clean.iloc[pos_oos:]

    gap_is_val = int(clean.index.get_loc(val_df.index[0]) - clean.index.get_loc(is_df.index[-1]))
    gap_val_oos = int(clean.index.get_loc(oos_df.index[0]) - clean.index.get_loc(val_df.index[-1]))
    assert gap_is_val >= PURGE_GAP and gap_val_oos >= PURGE_GAP

    def eval_target(tcol: str) -> dict[str, Any]:
        yi = is_df[tcol].to_numpy(dtype=int)
        yv = val_df[tcol].to_numpy(dtype=int)
        yo = oos_df[tcol].to_numpy(dtype=int)

        res_models = {}
        probs_store = {}
        for name, cols, mtype in [
            ("HGBC_Platt_Combined", all_feats, "hgbc"),
            ("LogReg_Platt_Combined", all_feats, "logreg"),
            ("HGBC_Platt_MacroVol_NoPrice", macro_vol_feats, "hgbc"),
            ("HAR_Persistence_Baseline", har_feats, "logreg"),
        ]:
            Xi, Xv, Xo = is_df[cols].to_numpy(), val_df[cols].to_numpy(), oos_df[cols].to_numpy()
            if mtype == "hgbc":
                base = HistGradientBoostingClassifier(max_depth=2, max_iter=60, min_samples_leaf=50, l2_regularization=5.0, random_state=42)
            else:
                base = make_pipeline(StandardScaler(), LogisticRegression(C=0.2, max_iter=1000))
            base.fit(Xi, yi)
            pi_r = base.predict_proba(Xi)[:, 1]
            pv_r = base.predict_proba(Xv)[:, 1]
            po_r = base.predict_proba(Xo)[:, 1]
            eps = 1e-6
            zv = np.log(np.clip(pv_r, eps, 1 - eps) / (1 - np.clip(pv_r, eps, 1 - eps))).reshape(-1, 1)
            zo = np.log(np.clip(po_r, eps, 1 - eps) / (1 - np.clip(po_r, eps, 1 - eps))).reshape(-1, 1)
            cal = LogisticRegression(C=1.0).fit(zv, yv)
            pv_c, po_c = cal.predict_proba(zv)[:, 1], cal.predict_proba(zo)[:, 1]
            res_models[name] = {
                "is_raw": clf_metrics(yi, pi_r, float(yi.mean())),
                "valid_raw": clf_metrics(yv, pv_r, float(yi.mean())),
                "valid_platt": clf_metrics(yv, pv_c, float(yv.mean())),
                "oos_raw": clf_metrics(yo, po_r, float(yi.mean())),
                "oos_platt": clf_metrics(yo, po_c, float(yv.mean())),
                "oos_null_perm_200": perm_test_auc(yo, po_c, 200, 30),
            }
            probs_store[name] = (pd.Series(pv_c, index=val_df.index), pd.Series(po_c, index=oos_df.index))

        # 5-Fold Purged Expanding Walk-Forward CV (2015-2026)
        wf_cuts = [pd.Timestamp(d) for d in ("2015-01-02", "2017-01-03", "2019-01-02", "2021-01-04", "2023-01-03", "2025-01-02")]
        wf_starts = [int(clean.index.searchsorted(dt)) for dt in wf_cuts]
        X_all, y_all = clean[all_feats].to_numpy(), clean[tcol].to_numpy(dtype=int)
        wf_p, wf_y, wf_br = [], [], []
        for k, ts in enumerate(wf_starts):
            te = wf_starts[k + 1] if k + 1 < len(wf_starts) else len(clean)
            tr_end = ts - PURGE_GAP
            split_c = int(tr_end * 0.72)
            fit_e = max(120, split_c - PURGE_GAP)
            bm = HistGradientBoostingClassifier(max_depth=2, max_iter=60, min_samples_leaf=50, l2_regularization=5.0, random_state=42)
            bm.fit(X_all[:fit_e], y_all[:fit_e])
            pc = bm.predict_proba(X_all[split_c:tr_end])[:, 1]
            pt = bm.predict_proba(X_all[ts:te])[:, 1]
            eps = 1e-6
            zc = np.log(np.clip(pc, eps, 1 - eps) / (1 - np.clip(pc, eps, 1 - eps))).reshape(-1, 1)
            zt = np.log(np.clip(pt, eps, 1 - eps) / (1 - np.clip(pt, eps, 1 - eps))).reshape(-1, 1)
            cal = LogisticRegression(C=1.0).fit(zc, y_all[split_c:tr_end])
            wf_p.append(cal.predict_proba(zt)[:, 1])
            wf_y.append(y_all[ts:te])
            wf_br.extend([float(y_all[:tr_end].mean())] * (te - ts))
        wf_p_arr, wf_y_arr = np.concatenate(wf_p), np.concatenate(wf_y)
        return {
            "models": res_models,
            "purged_wf_5fold_hgbc": clf_metrics(wf_y_arr, wf_p_arr, float(np.mean(wf_br))),
            "purged_wf_null_200": perm_test_auc(wf_y_arr, wf_p_arr, 200, 31),
            "probs": probs_store,
        }

    res_vn = eval_target("y_tb_volnorm")
    res_dd5 = eval_target("y_tb_dd5")
    res_nondir = eval_target("y_tb_nondir_stress")

    # Multi-seed shuffled canary leakage test (mean across 5 seeds -> expected ~0.50)
    canary_aucs = []
    for sd in range(995, 1000):
        rng = np.random.default_rng(sd)
        canary = HistGradientBoostingClassifier(max_depth=2, max_iter=60, min_samples_leaf=50, l2_regularization=5.0, random_state=42)
        canary.fit(is_df[all_feats].to_numpy(), rng.permutation(is_df["y_tb_nondir_stress"].to_numpy(dtype=int)))
        canary_aucs.append(float(roc_auc_score(oos_df["y_tb_nondir_stress"].to_numpy(dtype=int), canary.predict_proba(oos_df[all_feats].to_numpy())[:, 1])))
    canary_auc = round(float(np.mean(canary_aucs)), 4)

    # Gross vs Net Portfolio Utility on VALID (2019-2022) & OOS (2023-2026)
    def eval_portfolio(sub_df: pd.DataFrame, p_dd5: pd.Series, p_vn: pd.Series, p_nd: pd.Series) -> dict[str, Any]:
        idx_s = sub_df.index
        r_s, fed_s, rv_s = sub_df["ret1"], sub_df["fed_rate"], sub_df["rv21_past"]
        w_bh = pd.Series(1.0, index=idx_s)
        w_vt = (0.12 / rv_s.replace(0, np.nan)).clip(0.0, 1.5).shift(1).fillna(1.0)
        w_dd5_only = (1.0 - 1.5 * (p_dd5 - 0.20).clip(lower=0.0)).clip(0.35, 1.0).shift(1).fillna(1.0)
        w_vt_dd5 = w_vt * w_dd5_only
        w_vt_vn = w_vt * (1.0 - 1.5 * (p_vn - 0.20).clip(lower=0.0)).clip(0.35, 1.0).shift(1).fillna(1.0)
        w_vt_nd = w_vt * (1.0 - 1.2 * (p_nd - 0.30).clip(lower=0.0)).clip(0.35, 1.0).shift(1).fillna(1.0)

        out_p = {}
        for nm, w in [
            ("1_Buy_And_Hold", w_bh),
            ("2_Causal_VolTarget_12pct_Baseline", w_vt),
            ("3_TB_DD5_MetaOnly_HGBC", w_dd5_only),
            ("4_VolTarget_Plus_TB_VolNorm_HGBC", w_vt_vn),
            ("5_VolTarget_Plus_TB_CapitalDD5_HGBC", w_vt_dd5),
            ("6_VolTarget_Plus_TB_NonDirStress_HGBC", w_vt_nd),
        ]:
            st = portfolio_stats_full(w, r_s, fed_s, 5.0, 50.0)
            st["stress_10bp_net"] = portfolio_stats_full(w, r_s, fed_s, 10.0, 100.0)["net"]
            st["circ_shift_pct_net5bp"] = circ_shift_sharpe_pct(w, r_s, fed_s, 5.0, 50.0, 200)
            out_p[nm] = st
        return out_p

    valid_port = eval_portfolio(
        val_df,
        res_dd5["probs"]["HGBC_Platt_Combined"][0],
        res_vn["probs"]["HGBC_Platt_Combined"][0],
        res_nondir["probs"]["HGBC_Platt_Combined"][0],
    )
    oos_port = eval_portfolio(
        oos_df,
        res_dd5["probs"]["HGBC_Platt_Combined"][1],
        res_vn["probs"]["HGBC_Platt_Combined"][1],
        res_nondir["probs"]["HGBC_Platt_Combined"][1],
    )

    return {
        "sample_window": f"{clean.index[0].strftime('%Y-%m-%d')} -> {clean.index[-1].strftime('%Y-%m-%d')}",
        "splits": {
            "IS": f"{is_df.index[0].strftime('%Y-%m-%d')} -> {is_df.index[-1].strftime('%Y-%m-%d')} (n={len(is_df)})",
            "VALID": f"{val_df.index[0].strftime('%Y-%m-%d')} -> {val_df.index[-1].strftime('%Y-%m-%d')} (n={len(val_df)})",
            "OOS": f"{oos_df.index[0].strftime('%Y-%m-%d')} -> {oos_df.index[-1].strftime('%Y-%m-%d')} (n={len(oos_df)})",
            "purge_plus_embargo_days": PURGE_GAP,
            "verified_gaps": {"is_to_valid": gap_is_val, "valid_to_oos": gap_val_oos},
        },
        "leakage_audit": {
            "purged_gap_assertion_passed": True,
            "shuffled_label_canary_oos_auc_5seed_mean": canary_auc,
            "canary_expected_near_0_50": abs(canary_auc - 0.50) < 0.08,
        },
        "target_a1_tb_volnorm": {k: v for k, v in res_vn.items() if k != "probs"},
        "target_a2_tb_capital_dd5": {k: v for k, v in res_dd5.items() if k != "probs"},
        "target_a3_tb_nondir_stress": {k: v for k, v in res_nondir.items() if k != "probs"},
        "valid_portfolio_2019_2022": valid_port,
        "oos_portfolio_2023_2026_gross_vs_net": oos_port,
    }


def run_track_b_eurgbp_h1_triple_barrier() -> dict[str, Any]:
    H = 6
    EMB = 6
    PURGE_GAP = H + EMB  # 12 H1 bars

    eg = pd.read_csv(ROOT / "data" / "intraday" / "EURGBP_H1_bidask.csv.gz")
    eg["dt"] = pd.to_datetime(eg["ts_utc"], utc=True)
    eg = eg.sort_values("dt").reset_index(drop=True)
    eg["spread_pips"] = eg["spread_close_pips"].clip(lower=0.0)
    eg["mid_o"] = 0.5 * (eg["bid_o"] + eg["ask_o"])
    eg["mid_h"] = 0.5 * (eg["bid_h"] + eg["ask_h"])
    eg["mid_l"] = 0.5 * (eg["bid_l"] + eg["ask_l"])
    eg["mid_c"] = 0.5 * (eg["bid_c"] + eg["ask_c"])
    eg["date"] = eg["dt"].dt.tz_convert(None).dt.normalize()
    eg["hour"] = eg["dt"].dt.hour
    eg["dow"] = eg["dt"].dt.dayofweek

    tr = np.maximum(
        eg["mid_h"] - eg["mid_l"],
        np.maximum((eg["mid_h"] - eg["mid_c"].shift(1)).abs(), (eg["mid_l"] - eg["mid_c"].shift(1)).abs()),
    )
    eg["atr24"] = tr.rolling(24).mean()
    eg["atr6"] = tr.rolling(6).mean()
    eg["atr_ratio"] = eg["atr6"] / eg["atr24"].replace(0, np.nan)
    eg["sigma_6h_pips"] = eg["atr24"] * math.sqrt(H) * 10000.0
    eg["spread_z72"] = rolling_z(eg["spread_pips"], 72, 24)
    eg["sin_hr"] = np.sin(2.0 * math.pi * eg["hour"] / 24.0)
    eg["cos_hr"] = np.cos(2.0 * math.pi * eg["hour"] / 24.0)
    eg["is_rollover"] = eg["hour"].isin([20, 21, 22, 23]).astype(float)

    cb = pd.read_csv(ROOT / "data" / "macro" / "central_bank_rates_daily.csv")
    cb["date"] = pd.to_datetime(cb["date"])
    cb = cb.set_index("date").sort_index()
    cb["diff_boe_ecb_lag1"] = cb["diff_boe_ecb_dfr"].shift(1)
    cb["d_diff_boe_ecb_lag1"] = cb["diff_boe_ecb_dfr"].diff(21).shift(1)

    fsi = pd.read_csv(ROOT / "data" / "collect" / "ofr_fsi.csv")
    fsi["date"] = pd.to_datetime(fsi["Date"])
    fsi = fsi.set_index("date").sort_index()
    fsi["ofr_fsi_z252_lag1"] = rolling_z(fsi["OFR FSI"], 252).shift(1)

    eg = eg.merge(cb[["diff_boe_ecb_lag1", "d_diff_boe_ecb_lag1"]], on="date", how="left")
    eg = eg.merge(fsi[["ofr_fsi_z252_lag1"]], on="date", how="left")
    eg[["diff_boe_ecb_lag1", "d_diff_boe_ecb_lag1", "ofr_fsi_z252_lag1"]] = eg[
        ["diff_boe_ecb_lag1", "d_diff_boe_ecb_lag1", "ofr_fsi_z252_lag1"]
    ].ffill()

    mid_c, mid_h, mid_l = eg["mid_c"].to_numpy(), eg["mid_h"].to_numpy(), eg["mid_l"].to_numpy()
    sp, atr = eg["spread_pips"].to_numpy(), eg["atr24"].to_numpy()
    bid_o, ask_o, bid_c, ask_c = eg["bid_o"].to_numpy(), eg["ask_o"].to_numpy(), eg["bid_c"].to_numpy(), eg["ask_c"].to_numpy()
    bid_h, bid_l = eg["bid_h"].to_numpy(), eg["bid_l"].to_numpy()
    hr_arr, dow_arr, diff_arr = eg["hour"].to_numpy(), eg["dow"].to_numpy(), eg["diff_boe_ecb_lag1"].to_numpy()

    n = len(eg)
    y_fx_shock = np.full(n, np.nan)
    gross_pips = np.full(n, np.nan)
    net_pips = np.full(n, np.nan)

    COMM_PIPS_RT = 0.70
    SLIP_PIPS_RT = 0.30
    RETAIL_SWAP_MARKUP_PIP_NIGHT = 0.25
    SQRT_H = math.sqrt(H)

    for i in range(72, n - H - 2):
        a = atr[i]
        if not np.isfinite(a) or a <= 0:
            continue
        sig_h = a * SQRT_H
        # 6h intraday session Triple-Barrier risk shock:
        # spread spike >= 3.0 pips OR 6h excursion >= 1.50 * sigma_6h
        max_sp = float(np.max(sp[i + 1 : i + 1 + H]))
        max_exc = float(max(np.max(mid_h[i + 1 : i + 1 + H]) - mid_c[i], mid_c[i] - np.min(mid_l[i + 1 : i + 1 + H])))
        y_fx_shock[i] = 1.0 if (max_sp >= 3.0 or max_exc >= 1.50 * sig_h) else 0.0

        # Non-directional execution survival benchmark: symmetric bracket SL = TP = 1.0 * sigma_6h, H = 6h
        entry_mid = 0.5 * (bid_o[i + 1] + ask_o[i + 1])
        entry_ask = ask_o[i + 1]
        sl_lvl = entry_mid - 1.0 * sig_h
        tp_lvl = entry_mid + 1.0 * sig_h
        exit_mid = 0.5 * (bid_c[i + H] + ask_c[i + H])
        exit_bid = bid_c[i + H]
        for k in range(1, H + 1):
            if bid_l[i + k] <= sl_lvl:
                exit_mid, exit_bid = sl_lvl, sl_lvl
                break
            if bid_h[i + k] >= tp_lvl:
                exit_mid, exit_bid = tp_lvl, tp_lvl
                break
        g_pips = (exit_mid - entry_mid) * 10000.0
        exact_ba_pips = (exit_bid - entry_ask) * 10000.0
        crossed_rollover = any(int(hr_arr[i + k]) == 22 for k in range(1, H + 1))
        wd_mult = (3.0 if dow_arr[i] == 2 else 1.0) if crossed_rollover else 0.0
        policy_swap_pips = (-(diff_arr[i] / 100.0) / 365.0 * entry_mid * 10000.0) * wd_mult
        swap_net_pips = policy_swap_pips - RETAIL_SWAP_MARKUP_PIP_NIGHT * wd_mult
        gross_pips[i] = g_pips
        net_pips[i] = exact_ba_pips - COMM_PIPS_RT - SLIP_PIPS_RT + swap_net_pips

    eg["y_fx_shock"] = y_fx_shock
    eg["gross_pips_sym"] = gross_pips
    eg["net_pips_sym"] = net_pips

    fx_feats = [
        "sin_hr", "cos_hr", "is_rollover", "dow", "spread_pips", "spread_z72",
        "sigma_6h_pips", "atr_ratio", "ofr_fsi_z252_lag1", "diff_boe_ecb_lag1", "d_diff_boe_ecb_lag1",
    ]
    clean = eg.dropna(subset=fx_feats + ["y_fx_shock", "net_pips_sym"]).reset_index(drop=True)

    val_idx = int(clean["dt"].searchsorted(pd.Timestamp("2016-01-04", tz="UTC")))
    oos_idx = int(clean["dt"].searchsorted(pd.Timestamp("2021-01-04", tz="UTC")))
    is_df = clean.iloc[: val_idx - PURGE_GAP]
    val_df = clean.iloc[val_idx : oos_idx - PURGE_GAP]
    oos_df = clean.iloc[oos_idx:]

    Xi, yi = is_df[fx_feats].to_numpy(), is_df["y_fx_shock"].to_numpy(dtype=int)
    Xv, yv = val_df[fx_feats].to_numpy(), val_df["y_fx_shock"].to_numpy(dtype=int)
    Xo, yo = oos_df[fx_feats].to_numpy(), oos_df["y_fx_shock"].to_numpy(dtype=int)

    mdl = HistGradientBoostingClassifier(max_depth=3, max_iter=60, min_samples_leaf=200, l2_regularization=5.0, random_state=42)
    mdl.fit(Xi, yi)
    pv_raw, po_raw = mdl.predict_proba(Xv)[:, 1], mdl.predict_proba(Xo)[:, 1]
    eps = 1e-6
    zv = np.log(np.clip(pv_raw, eps, 1 - eps) / (1 - np.clip(pv_raw, eps, 1 - eps))).reshape(-1, 1)
    zo = np.log(np.clip(po_raw, eps, 1 - eps) / (1 - np.clip(po_raw, eps, 1 - eps))).reshape(-1, 1)
    cal = LogisticRegression(C=1.0).fit(zv, yv)
    pv_cal, po_cal = cal.predict_proba(zv)[:, 1], cal.predict_proba(zo)[:, 1]

    base_lr = make_pipeline(StandardScaler(), LogisticRegression(C=0.5, max_iter=500))
    base_lr.fit(is_df[["is_rollover", "spread_pips", "sigma_6h_pips"]].to_numpy(), yi)
    po_base = base_lr.predict_proba(oos_df[["is_rollover", "spread_pips", "sigma_6h_pips"]].to_numpy())[:, 1]

    # Deterministic Clock-Only vs State-Only (No Clock) ablation to expose diurnal rollover schedule effect
    clock_cols = ["sin_hr", "cos_hr", "is_rollover", "dow"]
    state_cols = ["spread_pips", "spread_z72", "sigma_6h_pips", "atr_ratio", "ofr_fsi_z252_lag1", "diff_boe_ecb_lag1", "d_diff_boe_ecb_lag1"]
    mdl_clock = HistGradientBoostingClassifier(max_depth=3, max_iter=60, min_samples_leaf=200, l2_regularization=5.0, random_state=42)
    mdl_clock.fit(is_df[clock_cols].to_numpy(), yi)
    po_clock = mdl_clock.predict_proba(oos_df[clock_cols].to_numpy())[:, 1]

    mdl_state = HistGradientBoostingClassifier(max_depth=3, max_iter=60, min_samples_leaf=200, l2_regularization=5.0, random_state=42)
    mdl_state.fit(is_df[state_cols].to_numpy(), yi)
    pv_st, po_st = mdl_state.predict_proba(val_df[state_cols].to_numpy())[:, 1], mdl_state.predict_proba(oos_df[state_cols].to_numpy())[:, 1]
    zv_s = np.log(np.clip(pv_st, eps, 1 - eps) / (1 - np.clip(pv_st, eps, 1 - eps))).reshape(-1, 1)
    zo_s = np.log(np.clip(po_st, eps, 1 - eps) / (1 - np.clip(po_st, eps, 1 - eps))).reshape(-1, 1)
    cal_s = LogisticRegression(C=1.0).fit(zv_s, yv)
    po_state_cal = cal_s.predict_proba(zo_s)[:, 1]

    # Non-overlapping 6h sampled execution survival audit on OOS
    oos_step = oos_df.iloc[::H].copy()
    po_step = po_cal[::H]
    thresh = float(np.quantile(pv_cal, 0.70))

    def _trade_summary(mask: np.ndarray) -> dict[str, Any]:
        sub = oos_step[mask]
        g, nt = sub["gross_pips_sym"], sub["net_pips_sym"]
        return {
            "n_trades": int(len(sub)),
            "shock_rate": round(float(sub["y_fx_shock"].mean()), 4),
            "gross_mean_pips": round(float(g.mean()), 3),
            "net_mean_pips": round(float(nt.mean()), 3),
            "cost_drag_pips": round(float(g.mean() - nt.mean()), 3),
        }

    return {
        "pair": "EURGBP_H1_Dukascopy",
        "horizon_hours": H,
        "total_clean_bars": int(len(clean)),
        "splits": {
            "IS": f"{is_df['dt'].iloc[0].strftime('%Y-%m-%d')} -> {is_df['dt'].iloc[-1].strftime('%Y-%m-%d')} (n={len(is_df)})",
            "VALID": f"{val_df['dt'].iloc[0].strftime('%Y-%m-%d')} -> {val_df['dt'].iloc[-1].strftime('%Y-%m-%d')} (n={len(val_df)})",
            "OOS": f"{oos_df['dt'].iloc[0].strftime('%Y-%m-%d')} -> {oos_df['dt'].iloc[-1].strftime('%Y-%m-%d')} (n={len(oos_df)})",
            "purge_plus_embargo_bars": PURGE_GAP,
        },
        "risk_shock_classification": {
            "valid_raw": clf_metrics(yv, pv_raw, float(yi.mean())),
            "valid_platt": clf_metrics(yv, pv_cal, float(yv.mean())),
            "oos_platt": clf_metrics(yo, po_cal, float(yv.mean())),
            "oos_clock_only_ablation": clf_metrics(yo, po_clock, float(yi.mean())),
            "oos_state_only_noclock_platt": clf_metrics(yo, po_state_cal, float(yv.mean())),
            "oos_state_only_null_perm_200_nonoverlap": perm_test_auc(yo[::H], po_state_cal[::H], 200, 33),
            "oos_simple_baseline": clf_metrics(yo, po_base, float(yi.mean())),
            "oos_null_perm_200_nonoverlap": perm_test_auc(yo[::H], po_cal[::H], 200, 32),
        },
        "execution_cost_survival_oos_6h_nonoverlap": {
            "Always_Execute_Unfiltered": _trade_summary(np.ones(len(oos_step), dtype=bool)),
            "Avoid_Rollover_20_23_UTC": _trade_summary(oos_step["is_rollover"].to_numpy() == 0.0),
            "MetaLabel_Risk_Gated_70pct_VALID": _trade_summary(po_step <= thresh),
            "High_Risk_Blocked_Cohort": _trade_summary(po_step > thresh),
        },
        "cost_model": {
            "bid_ask": "Measured Dukascopy H1 Bid/Ask quotes",
            "commission_rt_pips": COMM_PIPS_RT,
            "slippage_rt_pips": SLIP_PIPS_RT,
            "swap": "BoE-ECB daily policy differential (3x Wed) - 0.25 pip/night retail markup",
        },
    }


def main() -> None:
    track_a = run_track_a_spy_triple_barrier()
    track_b = run_track_b_eurgbp_h1_triple_barrier()
    out = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "EXP-0030",
        "hypothesis": "H33",
        "phase_gate": "PHASE_C_KILL_POINT_ACTIVE_OFFLINE_ONLY",
        "track_a_spy_daily_triple_barrier": track_a,
        "track_b_eurgbp_h1_triple_barrier": track_b,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print("=== TRACK A: SPY Daily Triple-Barrier (IS / VALID / OOS + 5-Fold WF) ===")
    print("Splits:", track_a["splits"])
    print("Leakage Audit:", track_a["leakage_audit"])
    for lbl, blk in [
        ("TB_VolNorm (-2s/+2.5s)", track_a["target_a1_tb_volnorm"]),
        ("TB_CapitalDD5 (-5%/+5%)", track_a["target_a2_tb_capital_dd5"]),
        ("TB_NonDirStress (-5% OR RV>20%)", track_a["target_a3_tb_nondir_stress"]),
    ]:
        print(f"-- {lbl} --")
        for mname, mv in blk["models"].items():
            print(f"  {mname:30s}: OOS AUC={mv['oos_platt']['roc_auc']} | PR={mv['oos_platt']['pr_auc']} ({mv['oos_platt']['pr_lift']}x) | BSS={mv['oos_platt']['bss']:+.4f} | ECE={mv['oos_platt']['ece']:.4f} | perm_p={mv['oos_null_perm_200']['perm_p_value']}")
        print(f"  5-Fold Purged WF HGBC       : {blk['purged_wf_5fold_hgbc']} | perm_p={blk['purged_wf_null_200']['perm_p_value']} (p99={blk['purged_wf_null_200']['null_p99_auc']})")
    print("-- VALID Portfolio (2019-2022 COVID/Bear) --")
    for k, v in track_a["valid_portfolio_2019_2022"].items():
        print(f"  {k:38s}: GrossSh={v['gross']['sharpe']:+.3f} NetSh5bp={v['net']['sharpe']:+.3f} | MaxDD={v['net']['max_dd_pct']:+.2f}% | CVaR95={v['net']['cvar95_bp']:+.1f}bp")
    print("-- OOS Portfolio (2023-2026 Bull) --")
    for k, v in track_a["oos_portfolio_2023_2026_gross_vs_net"].items():
        print(f"  {k:38s}: GrossSh={v['gross']['sharpe']:+.3f} NetSh5bp={v['net']['sharpe']:+.3f} Stress10bp={v['stress_10bp_net']['sharpe']:+.3f} | MaxDD={v['net']['max_dd_pct']:+.2f}% | CVaR95={v['net']['cvar95_bp']:+.1f}bp | ShiftPct={v['circ_shift_pct_net5bp']}%")

    print("\n=== TRACK B: EURGBP H1 23y Bid/Ask Triple-Barrier ===")
    print("Splits:", track_b["splits"])
    print("OOS Shock Classification:", track_b["risk_shock_classification"]["oos_platt"], "| Baseline:", track_b["risk_shock_classification"]["oos_simple_baseline"]["roc_auc"], "| Null:", track_b["risk_shock_classification"]["oos_null_perm_200_nonoverlap"])
    print("  Clock-Only Ablation   :", track_b["risk_shock_classification"]["oos_clock_only_ablation"])
    print("  State-Only (No Clock) :", track_b["risk_shock_classification"]["oos_state_only_noclock_platt"], "| Null:", track_b["risk_shock_classification"]["oos_state_only_null_perm_200_nonoverlap"])
    for k, v in track_b["execution_cost_survival_oos_6h_nonoverlap"].items():
        print(f"  {k:36s}: n={v['n_trades']:4d} | shock={v['shock_rate']:.3f} | gross={v['gross_mean_pips']:+.3f}p | net={v['net_mean_pips']:+.3f}p | drag={v['cost_drag_pips']:.3f}p")


if __name__ == "__main__":
    main()
