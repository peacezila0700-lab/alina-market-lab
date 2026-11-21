#!/usr/bin/env python3
"""
Task 3 Empirical Audit — Risk / Volatility Meta-Labeling Framework (v2: Raw vs Stationary Macro + Calibration + Utility)

Starts from EXP-0027 (AUC=0.7212, BSS=-0.1571 — explicitly treated as UNCONFIRMED)
and empirically evaluates:
  1. Why EXP-0027 failed calibration (non-stationary interest-rate levels + unpurged boundary + uncalibrated LogReg)
  2. Leakage Audit: Unpurged vs Purged Walk-Forward + Embargo (H=21d, purge=21d, embargo=10d)
  3. Feature Ablation with Causal Stationary Non-Price Macro vs Vol Term Structure vs HAR Realized-Vol Baseline
  4. Class Imbalance (PR-AUC vs base rate) & Probability Calibration (Raw vs Platt Sigmoid vs Isotonic, ECE, BSS)
  5. Cross-Period Regime Stability (6 WF folds 2015-2026) & 200+ Block-Shift Null Permutation Tests
  6. Out-of-sample Causal Sizing / Exposure Utility (Gross & Net @ 2bp & 5bp) vs Buy&Hold, VolTarget, & Heuristic

Strictly non-directional risk/volatility targets only (no directional price prediction).
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
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "research" / "artifacts" / "task3_risk_meta_framework_audit.json"
H_DAYS = 21
EMBARGO_DAYS = 10


def rolling_z(s: pd.Series, win: int = 252) -> pd.Series:
    mu = s.rolling(win, min_periods=60).mean()
    sd = s.rolling(win, min_periods=60).std().replace(0, np.nan)
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


def calc_metrics(y_true: np.ndarray, y_prob: np.ndarray, base_rate_train: float) -> dict[str, Any]:
    y_true = np.asarray(y_true, dtype=int)
    y_prob = np.clip(np.asarray(y_prob, dtype=float), 1e-6, 1.0 - 1e-6)
    pos_rate = float(y_true.mean())
    auc = float(roc_auc_score(y_true, y_prob)) if len(np.unique(y_true)) > 1 else float("nan")
    pr_auc = float(average_precision_score(y_true, y_prob)) if len(np.unique(y_true)) > 1 else float("nan")
    brier = float(brier_score_loss(y_true, y_prob))
    brier_clim = float(brier_score_loss(y_true, np.full_like(y_prob, base_rate_train)))
    bss = 1.0 - (brier / brier_clim) if brier_clim > 0 else 0.0
    ece = ece_score(y_true, y_prob, n_bins=10)
    return {
        "n": int(len(y_true)),
        "pos_rate": round(pos_rate, 4),
        "roc_auc": round(auc, 4),
        "pr_auc": round(pr_auc, 4),
        "pr_lift": round(pr_auc / pos_rate, 3) if pos_rate > 0 else None,
        "brier": round(brier, 4),
        "brier_clim": round(brier_clim, 4),
        "bss": round(bss, 4),
        "ece": round(ece, 4),
        "mean_pred": round(float(y_prob.mean()), 4),
    }


def load_causal_dataset() -> pd.DataFrame:
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
    fsi = fsi.set_index("date")[["OFR FSI", "Credit", "Equity valuation", "Safe assets", "Funding", "Volatility"]].sort_index()
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
    close = spy["close"].reindex(idx)
    ret1 = close.pct_change()
    df["spy_ret1"] = ret1
    df["spy_close"] = close

    # Raw Macro Levels (EXP-0027 legacy)
    df["ofr_fsi"] = fsi["OFR FSI"].reindex(idx).ffill()
    df["ofr_credit"] = fsi["Credit"].reindex(idx).ffill()
    df["ofr_funding"] = fsi["Funding"].reindex(idx).ffill()
    df["ofr_safe"] = fsi["Safe assets"].reindex(idx).ffill()
    df["fed_rate"] = cb["fed_rate_proxy"].reindex(idx).ffill()
    df["ecb_dfr"] = cb["ecb_dfr"].reindex(idx).ffill()
    df["diff_fed_ecb"] = cb["diff_fed_ecb_dfr"].reindex(idx).ffill()
    df["diff_boe_ecb"] = cb["diff_boe_ecb_dfr"].reindex(idx).ffill()
    df["gpr_lag"] = gpr["gpr"].reindex(idx, method="ffill")

    # Stationarized Causal Macro / Credit / Rates / Positioning Features (252d rolling Z & diffs)
    df["ofr_fsi_z252"] = rolling_z(df["ofr_fsi"], 252)
    df["ofr_fsi_chg21"] = df["ofr_fsi"].diff(21)
    df["ofr_credit_z252"] = rolling_z(df["ofr_credit"], 252)
    df["ofr_funding_z252"] = rolling_z(df["ofr_funding"], 252)
    df["d_fed_63"] = df["fed_rate"].diff(63)
    df["d_diff_fed_ecb_21"] = df["diff_fed_ecb"].diff(21)
    df["d_diff_boe_ecb_21"] = df["diff_boe_ecb"].diff(21)
    df["gpr_z252"] = rolling_z(df["gpr_lag"], 252)

    for inst, colname in [("SP500", "cot_sp500_z"), ("VIX", "cot_vix_z"), ("UST_10Y", "cot_ust10y_z"), ("EURUSD", "cot_eur_z")]:
        sub = cot[cot["instrument"] == inst].set_index("date")[["noncomm_net_pct_oi_z156"]].sort_index()
        sub = sub[~sub.index.duplicated(keep="last")]
        df[colname] = sub["noncomm_net_pct_oi_z156"].reindex(idx, method="ffill").fillna(0.0)

    fomc_ns = fomc_dates.asi8
    idx_ns = idx.asi8
    pos = np.searchsorted(fomc_ns, idx_ns, side="left")
    next_days = np.where(pos < len(fomc_ns), (fomc_ns[np.minimum(pos, len(fomc_ns) - 1)] - idx_ns) / 86400e9, 30.0)
    df["fomc_within_5d"] = (next_days <= 5.0).astype(float)

    # Option-Implied Vol Term Structure & Tail Skew
    df["vix"] = vol["vix"].reindex(idx).ffill()
    df["slope_3m"] = vol["slope_3m"].reindex(idx).ffill()
    df["slope_9d"] = vol["slope_9d"].reindex(idx).ffill()
    df["vvix_pct"] = vol["vvix_pct"].reindex(idx).ffill()
    df["skew"] = vol["skew"].reindex(idx).ffill()
    df["vix_chg21"] = df["vix"].diff(21)

    # Realized Vol Persistence Baseline (HAR)
    df["rv5_past"] = ret1.rolling(5).std() * math.sqrt(252)
    df["rv21_past"] = ret1.rolling(21).std() * math.sqrt(252)
    df["rv63_past"] = ret1.rolling(63).std() * math.sqrt(252)
    df["rv_ratio_5_21"] = df["rv5_past"] / df["rv21_past"].replace(0, np.nan)

    # Strictly Forward Targets [t+1 .. t+21]
    df["rv21_fwd"] = ret1.shift(-1).rolling(H_DAYS).std().shift(-(H_DAYS - 1)) * math.sqrt(252)
    c_arr = close.to_numpy()
    fwd_dd = np.full(len(c_arr), np.nan)
    for i in range(len(c_arr) - H_DAYS):
        path = c_arr[i + 1 : i + 1 + H_DAYS] / c_arr[i] - 1.0
        fwd_dd[i] = float(np.min(path))
    df["fwd21_max_adverse"] = fwd_dd

    df["target_vol_onset"] = (df["rv21_fwd"] > 1.35 * df["rv21_past"]).astype(float)
    df["target_tail_stress"] = ((df["rv21_fwd"] > 0.20) | (df["fwd21_max_adverse"] <= -0.05)).astype(float)
    return df


def purged_walk_forward_splits(n: int, fold_starts: list[int], purge: int):
    for k, test_start in enumerate(fold_starts):
        test_end = fold_starts[k + 1] if k + 1 < len(fold_starts) else n
        train_end = max(0, test_start - purge)
        yield np.arange(0, train_end), np.arange(test_start, test_end), test_start - train_end


def fit_predict_causal(X_tr: np.ndarray, y_tr: np.ndarray, X_te: np.ndarray, kind: str) -> np.ndarray:
    if kind == "logreg_uncal":
        m = make_pipeline(StandardScaler(), LogisticRegression(C=0.5, max_iter=1000))
        m.fit(X_tr, y_tr)
        return m.predict_proba(X_te)[:, 1]
    if kind == "logreg_balanced":
        m = make_pipeline(StandardScaler(), LogisticRegression(C=0.2, class_weight="balanced", max_iter=1000))
        m.fit(X_tr, y_tr)
        return m.predict_proba(X_te)[:, 1]

    # Chronological inner calibration split with 21d purge + 10d embargo
    n_tr = len(X_tr)
    split_cal = int(n_tr * 0.72)
    fit_end = max(120, split_cal - (H_DAYS + EMBARGO_DAYS))
    if kind.startswith("hgbc"):
        base = HistGradientBoostingClassifier(
            max_depth=2, max_iter=60, min_samples_leaf=50, l2_regularization=5.0, random_state=42
        )
    else:
        base = make_pipeline(StandardScaler(), LogisticRegression(C=0.2, max_iter=1000))

    base.fit(X_tr[:fit_end], y_tr[:fit_end])
    if kind == "hgbc_raw":
        base.fit(X_tr, y_tr)
        return base.predict_proba(X_te)[:, 1]

    p_cal = base.predict_proba(X_tr[split_cal:])[:, 1]
    p_te = base.predict_proba(X_te)[:, 1]
    if kind.endswith("_platt"):
        eps = 1e-6
        z_cal = np.log(np.clip(p_cal, eps, 1 - eps) / (1 - np.clip(p_cal, eps, 1 - eps))).reshape(-1, 1)
        z_te = np.log(np.clip(p_te, eps, 1 - eps) / (1 - np.clip(p_te, eps, 1 - eps))).reshape(-1, 1)
        cal = LogisticRegression(C=1.0).fit(z_cal, y_tr[split_cal:])
        return cal.predict_proba(z_te)[:, 1]
    else:
        iso = IsotonicRegression(out_of_bounds="clip").fit(p_cal, y_tr[split_cal:])
        return iso.predict(p_te)


def portfolio_stats(weights: pd.Series, returns: pd.Series, cost_bp: float) -> dict[str, Any]:
    df = pd.concat([weights.rename("w"), returns.rename("r")], axis=1).dropna()
    w, r = df["w"], df["r"]
    dw = w.diff().abs().fillna(0.0)
    gross = w * r
    net = gross - dw * (cost_bp / 10000.0)
    eq = (1.0 + net).cumprod()
    dd = eq / eq.cummax() - 1.0
    ann_ret = float(net.mean() * 252)
    ann_vol = float(net.std() * math.sqrt(252))
    sharpe = ann_ret / ann_vol if ann_vol > 0 else 0.0
    down = net[net < 0]
    sortino = ann_ret / float(down.std() * math.sqrt(252)) if len(down) > 5 and down.std() > 0 else 0.0
    mdd = float(dd.min())
    calmar = ann_ret / abs(mdd) if mdd < 0 else 0.0
    q5 = float(np.quantile(net, 0.05))
    cvar95 = float(net[net <= q5].mean())
    ulcer = float(np.sqrt(np.mean((dd * 100.0) ** 2)))
    return {
        "gross_sharpe": round(float(gross.mean() / gross.std() * math.sqrt(252)), 3) if gross.std() > 0 else 0.0,
        "net_sharpe": round(sharpe, 3),
        "sortino": round(sortino, 3),
        "calmar": round(calmar, 3),
        "ann_ret_pct": round(ann_ret * 100, 2),
        "ann_vol_pct": round(ann_vol * 100, 2),
        "max_dd_pct": round(mdd * 100, 2),
        "cvar95_daily_bp": round(cvar95 * 10000, 1),
        "ulcer_index": round(ulcer, 2),
        "avg_exposure": round(float(w.mean()), 3),
        "ann_turnover": round(float(dw.mean() * 252), 2),
    }


def circular_shift_sharpe_pct(weights: pd.Series, returns: pd.Series, cost_bp: float, n_sims: int = 200) -> float:
    rng = np.random.default_rng(42)
    df = pd.concat([weights.rename("w"), returns.rename("r")], axis=1).dropna()
    w, r = df["w"].to_numpy(), df["r"].to_numpy()
    dw = np.abs(np.diff(w, prepend=w[0]))
    obs_net = w * r - dw * (cost_bp / 10000.0)
    obs_sh = obs_net.mean() / obs_net.std() * math.sqrt(252) if obs_net.std() > 0 else 0.0
    sims = []
    n = len(w)
    for _ in range(n_sims):
        sh = int(rng.integers(30, n - 30))
        ws = np.roll(w, sh)
        dws = np.abs(np.diff(ws, prepend=ws[0]))
        net = ws * r - dws * (cost_bp / 10000.0)
        sims.append(net.mean() / net.std() * math.sqrt(252) if net.std() > 0 else 0.0)
    return round(float(np.mean(np.array(sims) <= obs_sh) * 100.0), 1)


def main() -> None:
    df = load_causal_dataset()
    raw_macro_feats = ["ofr_fsi", "ofr_credit", "ofr_funding", "ofr_safe", "fed_rate", "ecb_dfr", "diff_fed_ecb", "diff_boe_ecb", "gpr_lag"]
    stat_macro_feats = [
        "ofr_fsi_z252", "ofr_fsi_chg21", "ofr_credit_z252", "ofr_funding_z252",
        "d_fed_63", "d_diff_fed_ecb_21", "d_diff_boe_ecb_21", "gpr_z252",
        "cot_sp500_z", "cot_vix_z", "cot_ust10y_z", "cot_eur_z", "fomc_within_5d",
    ]
    vol_term_feats = ["vix", "slope_3m", "slope_9d", "vvix_pct", "skew", "vix_chg21"]
    har_feats = ["rv5_past", "rv21_past", "rv63_past", "rv_ratio_5_21"]
    stat_all_feats = stat_macro_feats + vol_term_feats + har_feats

    need_cols = list(dict.fromkeys(raw_macro_feats + stat_all_feats + ["target_vol_onset", "target_tail_stress"]))
    sub = df.dropna(subset=need_cols).copy()

    cut_dates = [pd.Timestamp(d) for d in ("2015-01-02", "2017-01-03", "2019-01-02", "2021-01-04", "2023-01-03", "2025-01-02")]
    fold_starts = [int(sub.index.searchsorted(dt)) for dt in cut_dates]

    # 1. EXP-0027 Non-Stationary Raw-Levels Defect vs Stationary Macro (2021 Boundary, Unpurged vs Purged)
    split_2021 = int(sub.index.searchsorted(pd.Timestamp("2021-01-04")))
    boundary_audit = {}
    for target in ("target_vol_onset", "target_tail_stress"):
        y = sub[target].to_numpy(dtype=int)
        X_raw = sub[raw_macro_feats + vol_term_feats + har_feats].to_numpy()
        X_stat = sub[stat_all_feats].to_numpy()
        tr_end = split_2021 - (H_DAYS + EMBARGO_DAYS)
        p_raw_unp = fit_predict_causal(X_raw[:split_2021], y[:split_2021], X_raw[split_2021:], "logreg_uncal")
        p_raw_prg = fit_predict_causal(X_raw[:tr_end], y[:tr_end], X_raw[split_2021:], "logreg_uncal")
        p_stat_prg = fit_predict_causal(X_stat[:tr_end], y[:tr_end], X_stat[split_2021:], "logreg_platt")
        boundary_audit[target] = {
            "raw_macro_unpurged": calc_metrics(y[split_2021:], p_raw_unp, float(y[:split_2021].mean())),
            "raw_macro_purged_embargo": calc_metrics(y[split_2021:], p_raw_prg, float(y[:tr_end].mean())),
            "stationary_macro_platt_purged": calc_metrics(y[split_2021:], p_stat_prg, float(y[:tr_end].mean())),
        }

    # 2. Calibration & Model Family Audit on Stationary Feature Set (6 WF Folds 2015-2026)
    cal_audit = {}
    oos_probs: dict[str, pd.Series] = {}
    X = sub[stat_all_feats].to_numpy()
    for target in ("target_vol_onset", "target_tail_stress"):
        cal_audit[target] = {}
        y = sub[target].to_numpy(dtype=int)
        for kind in ("logreg_uncal", "logreg_balanced", "logreg_platt", "logreg_isotonic", "hgbc_raw", "hgbc_platt"):
            ps, ys, brs, idxs, fms = [], [], [], [], []
            for tr_idx, te_idx, _ in purged_walk_forward_splits(len(sub), fold_starts, H_DAYS + EMBARGO_DAYS):
                p_te = fit_predict_causal(X[tr_idx], y[tr_idx], X[te_idx], kind)
                br = float(y[tr_idx].mean())
                fm = calc_metrics(y[te_idx], p_te, br)
                fm["fold"] = f"{sub.index[te_idx[0]].strftime('%Y-%m')}..{sub.index[te_idx[-1]].strftime('%Y-%m')}"
                fms.append(fm)
                ps.append(p_te); ys.append(y[te_idx]); idxs.extend(sub.index[te_idx]); brs.extend([br]*len(te_idx))
            agg = calc_metrics(np.concatenate(ys), np.concatenate(ps), float(np.mean(brs)))
            agg["fold_aucs"] = [f["roc_auc"] for f in fms]
            agg["fold_bsss"] = [f["bss"] for f in fms]
            agg["folds"] = fms
            cal_audit[target][kind] = agg
            oos_probs[f"{target}::{kind}"] = pd.Series(np.concatenate(ps), index=pd.DatetimeIndex(idxs))

    # 3. Feature Group Ablation (Stationary Macro vs VolTerm vs HAR Baseline) using logreg_platt & hgbc_platt
    ablation = {}
    feature_sets = {
        "1_Stationary_Macro_COT_GPR_ONLY": stat_macro_feats,
        "2_Vol_Term_Structure_ONLY": vol_term_feats,
        "3_HAR_RealizedVol_Baseline": har_feats,
        "4_StatMacro_Plus_VolTerm": stat_macro_feats + vol_term_feats,
        "5_Full_Combined": stat_all_feats,
    }
    for target in ("target_vol_onset", "target_tail_stress"):
        ablation[target] = {}
        y = sub[target].to_numpy(dtype=int)
        for fs_name, fs_cols in feature_sets.items():
            ablation[target][fs_name] = {}
            Xf = sub[fs_cols].to_numpy()
            for kind in ("logreg_platt", "hgbc_platt"):
                ps, ys, brs, idxs = [], [], [], []
                for tr_idx, te_idx, _ in purged_walk_forward_splits(len(sub), fold_starts, H_DAYS + EMBARGO_DAYS):
                    p_te = fit_predict_causal(Xf[tr_idx], y[tr_idx], Xf[te_idx], kind)
                    ps.append(p_te); ys.append(y[te_idx]); brs.extend([float(y[tr_idx].mean())]*len(te_idx)); idxs.extend(sub.index[te_idx])
                ablation[target][fs_name][kind] = calc_metrics(np.concatenate(ys), np.concatenate(ps), float(np.mean(brs)))
                if fs_name == "4_StatMacro_Plus_VolTerm" and kind == "logreg_platt":
                    oos_probs[f"{target}::statmacro_volterm_platt"] = pd.Series(np.concatenate(ps), index=pd.DatetimeIndex(idxs))

    # 4. Null Model Permutation Tests (200 circular label shifts)
    null_tests = {}
    for target in ("target_vol_onset", "target_tail_stress"):
        for kind in ("logreg_platt", "hgbc_platt"):
            key = f"{target}::{kind}"
            p_s = oos_probs[key]
            y_oos = sub[target].loc[p_s.index].to_numpy(dtype=int)
            p_arr = p_s.to_numpy()
            obs_auc = float(roc_auc_score(y_oos, p_arr))
            rng = np.random.default_rng(123)
            null_aucs = [float(roc_auc_score(np.roll(y_oos, int(rng.integers(30, len(y_oos) - 30))), p_arr)) for _ in range(200)]
            null_tests[key] = {
                "obs_wf_oos_auc": round(obs_auc, 4),
                "null_mean_auc": round(float(np.mean(null_aucs)), 4),
                "null_p99_auc": round(float(np.quantile(null_aucs, 0.99)), 4),
                "perm_p_value": round(float(np.mean(np.array(null_aucs) >= obs_auc)), 4),
            }

    # 5. Causal Exposure / Sizing Utility on Strictly OOS Walk-Forward Window (2015-2026)
    wf_idx = oos_probs["target_tail_stress::logreg_platt"].index
    r_spy = sub["spy_ret1"].reindex(wf_idx)
    rv21 = sub["rv21_past"].reindex(wf_idx)
    slope3m = sub["slope_3m"].reindex(wf_idx)
    fsi_s = sub["ofr_fsi"].reindex(wf_idx)

    w_bh = pd.Series(1.0, index=wf_idx)
    w_vt = (0.12 / rv21.replace(0, np.nan)).clip(0.0, 1.5).shift(1).fillna(1.0)
    w_heur = w_vt * pd.Series(np.where((slope3m > 1.02) | (fsi_s > 1.5), 0.5, 1.0), index=wf_idx).shift(1).fillna(1.0)

    p_stress_lr = oos_probs["target_tail_stress::logreg_platt"].reindex(wf_idx)
    p_stress_hg = oos_probs["target_tail_stress::hgbc_platt"].reindex(wf_idx)
    p_onset_hg = oos_probs["target_vol_onset::hgbc_platt"].reindex(wf_idx)

    # Smooth proportional exposure reduction when calibrated P(tail_stress) > 0.35
    w_meta_lr = w_vt * (1.0 - 1.2 * (p_stress_lr - 0.35).clip(lower=0.0)).clip(0.35, 1.0).shift(1).fillna(1.0)
    w_meta_hg = w_vt * (1.0 - 1.2 * (p_stress_hg - 0.35).clip(lower=0.0)).clip(0.35, 1.0).shift(1).fillna(1.0)
    # Vol-Onset preemptive scale-down before realized vol spike catches up
    w_onset_hg = w_vt * (1.0 - 0.8 * (p_onset_hg - 0.35).clip(lower=0.0)).clip(0.50, 1.0).shift(1).fillna(1.0)
    # Standalone Meta-Label sizing (no HAR vol target)
    w_meta_standalone = (1.0 - 1.2 * (p_stress_lr - 0.35).clip(lower=0.0)).clip(0.35, 1.0).shift(1).fillna(1.0)

    sizing_utility = {}
    for name, w in [
        ("1_SPY_Buy_And_Hold", w_bh),
        ("2_Causal_VolTarget_12pct_Baseline", w_vt),
        ("3_EXP0027_Heuristic_Throttle", w_heur),
        ("4_MetaTailStress_LogReg_Standalone", w_meta_standalone),
        ("5_VolTarget_Plus_MetaTailStress_LogReg", w_meta_lr),
        ("6_VolTarget_Plus_MetaTailStress_HGBC", w_meta_hg),
        ("7_VolTarget_Plus_MetaVolOnset_HGBC", w_onset_hg),
    ]:
        st2 = portfolio_stats(w, r_spy, 2.0)
        st5 = portfolio_stats(w, r_spy, 5.0)
        st2["net_sharpe_5bp"] = st5["net_sharpe"]
        st2["circular_shift_pct_2bp"] = circular_shift_sharpe_pct(w, r_spy, 2.0, 200)
        sizing_utility[name] = st2

    out = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "sample_range": f"{sub.index[0].strftime('%Y-%m-%d')} -> {sub.index[-1].strftime('%Y-%m-%d')}",
        "total_clean_rows": int(len(sub)),
        "wf_oos_range": f"{wf_idx[0].strftime('%Y-%m-%d')} -> {wf_idx[-1].strftime('%Y-%m-%d')}",
        "wf_oos_rows": int(len(wf_idx)),
        "purge_days": H_DAYS,
        "embargo_days": EMBARGO_DAYS,
        "boundary_raw_vs_stationary_2021": boundary_audit,
        "calibration_audit_stationary": cal_audit,
        "feature_ablation_stationary": ablation,
        "null_permutation_tests": null_tests,
        "causal_sizing_utility_wf_oos": sizing_utility,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print("=== 2021 Boundary: Raw Macro Levels (EXP-0027 bug) vs Stationary Macro ===")
    for t, d in boundary_audit.items():
        print(f"-- {t} --")
        for k, v in d.items():
            print(f"  {k:32s}: AUC={v['roc_auc']} | BSS={v['bss']} | ECE={v['ece']} | mean_pred={v['mean_pred']}")
    print("\n=== Stationary Calibration Audit (6 WF Folds 2015-2026) ===")
    for t, m in cal_audit.items():
        print(f"-- {t} --")
        for k, v in m.items():
            print(f"  {k:16s}: AUC={v['roc_auc']} | PR_AUC={v['pr_auc']} (lift={v['pr_lift']}x) | BSS={v['bss']:+.4f} | ECE={v['ece']:.4f} | fold_AUCs={v['fold_aucs']}")
    print("\n=== Stationary Feature Ablation ===")
    for t, fs_map in ablation.items():
        print(f"-- {t} --")
        for fs, m_map in fs_map.items():
            for mk, v in m_map.items():
                print(f"  {fs:34s} ({mk:12s}): AUC={v['roc_auc']} | PR_AUC={v['pr_auc']} ({v['pr_lift']}x) | BSS={v['bss']:+.4f} | ECE={v['ece']:.4f}")
    print("\n=== Null Permutation Tests ===")
    print(json.dumps(null_tests, indent=2))
    print("\n=== Causal Sizing Utility (WF OOS 2015-2026) ===")
    for k, v in sizing_utility.items():
        print(f"  {k:40s}: GrossSh={v['gross_sharpe']:+.3f} NetSh2bp={v['net_sharpe']:+.3f} (5bp={v['net_sharpe_5bp']:+.3f}) | Calmar={v['calmar']:.3f} | MaxDD={v['max_dd_pct']:+.2f}% | CVaR95={v['cvar95_daily_bp']:+.1f}bp | Exp={v['avg_exposure']:.3f} | ShiftPct={v['circular_shift_pct_2bp']}%")


if __name__ == "__main__":
    main()
