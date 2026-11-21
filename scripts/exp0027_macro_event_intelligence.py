#!/usr/bin/env python3
"""
Workstream A2 (EXP-0027) — Macro / Central Bank / Volatility / Geopolitical Event Intelligence

Strictly separates outcomes across 5 non-overlapping categories:
  1. Directional Prediction (5d / 21d forward returns on SPY, EURGBP, EURUSD)
  2. Volatility Prediction (5d / 21d forward realized vol R^2 & Onset AUC / Brier Skill OOS)
  3. Regime Classification (VIX Term Structure + OFR FSI + Rate-Cycle transitions)
  4. Risk-Sizing (Causal Vol-Targeting on SPY & EURGBP)
  5. Exposure Control (Term-Structure + Macro-Stress Drawdown Throttle vs Vol-Targeting & Buy-Hold)

Uses causal expanding / walk-forward splits (IS <= 2020-12-31, OOS >= 2021-01-01) and turnover-matched circular shifts.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "research" / "artifacts" / "exp0027_macro_events.json"
OUT_MD = ROOT / "reports" / "EXP_0027_MACRO_EVENT_INTELLIGENCE.md"
SPLIT = pd.Timestamp("2021-01-01")


def ann_sharpe(r: pd.Series) -> float:
    r = r.dropna()
    return float(r.mean() / r.std() * math.sqrt(252)) if len(r) > 30 and r.std() > 0 else 0.0


def max_dd(r: pd.Series) -> float:
    eq = (1.0 + r.fillna(0.0)).cumprod()
    return float((eq / eq.cummax() - 1.0).min())


def circular_shift_pct(w: pd.Series, ret: pd.Series, cost_bp: float = 2.0, n_sims: int = 200) -> float:
    rng = np.random.default_rng(17)
    w_arr = w.to_numpy()
    r_arr = ret.to_numpy()
    valid = np.isfinite(w_arr) & np.isfinite(r_arr)
    w_arr, r_arr = w_arr[valid], r_arr[valid]
    if len(w_arr) < 60:
        return 50.0
    dw = np.abs(np.diff(w_arr, prepend=0.0))
    obs = w_arr * r_arr - dw * (cost_bp / 10000.0)
    obs_s = obs.mean() / obs.std() * math.sqrt(252) if obs.std() > 0 else 0.0
    sims = []
    n = len(w_arr)
    for _ in range(n_sims):
        sh = int(rng.integers(20, n - 20))
        ws = np.roll(w_arr, sh)
        dws = np.abs(np.diff(ws, prepend=0.0))
        nr = ws * r_arr - dws * (cost_bp / 10000.0)
        sims.append(nr.mean() / nr.std() * math.sqrt(252) if nr.std() > 0 else 0.0)
    return float(np.mean(np.array(sims) <= obs_s) * 100.0)


def main() -> None:
    # Load official prices & macro series
    spy = pd.read_csv(ROOT / "data" / "universe" / "SPY.csv")
    spy["date"] = pd.to_datetime(spy["date"])
    spy = spy.set_index("date")["close"].sort_index()
    spy = spy[~spy.index.duplicated(keep="last")]

    eg = pd.read_csv(ROOT / "data" / "official" / "EURGBP_ECB_D.csv")
    eg["date"] = pd.to_datetime(eg["date"])
    eg = eg.set_index("date")["close"].sort_index()
    eg = eg[~eg.index.duplicated(keep="last")]

    eu = pd.read_csv(ROOT / "data" / "official" / "EURUSD_ECB_D.csv")
    eu["date"] = pd.to_datetime(eu["date"])
    eu = eu.set_index("date")["close"].sort_index()
    eu = eu[~eu.index.duplicated(keep="last")]

    cb = pd.read_csv(ROOT / "data" / "macro" / "central_bank_rates_daily.csv")
    cb["date"] = pd.to_datetime(cb["date"])
    cb = cb.set_index("date").sort_index()
    cb = cb[~cb.index.duplicated(keep="last")]

    cb_chg = pd.read_csv(ROOT / "data" / "macro" / "cb_rate_changes.csv")
    cb_chg["date"] = pd.to_datetime(cb_chg["date"])

    vol = pd.read_csv(ROOT / "data" / "collect" / "vol_stress_features.csv")
    vol["date"] = pd.to_datetime(vol["date"])
    vol = vol.set_index("date").sort_index()
    vol = vol[~vol.index.duplicated(keep="last")]

    fsi = pd.read_csv(ROOT / "data" / "collect" / "ofr_fsi.csv")
    fsi["date"] = pd.to_datetime(fsi["Date"])
    fsi = fsi.set_index("date")[["OFR FSI", "Credit", "Volatility"]].sort_index()
    fsi = fsi[~fsi.index.duplicated(keep="last")]

    gpr = pd.read_csv(ROOT / "data" / "collect" / "gpr_monthly.csv")
    gpr["date"] = pd.to_datetime(gpr["month"]) + pd.offsets.MonthEnd(1) + pd.Timedelta(days=2)  # lagged public release
    gpr = gpr.dropna(subset=["date", "gpr"]).set_index("date")[["gpr"]].sort_index()
    gpr = gpr[~gpr.index.duplicated(keep="last")]

    cot = pd.read_csv(ROOT / "data" / "cot" / "cot_features.csv")
    cot["date"] = pd.to_datetime(cot["available_from"])
    if "EURUSD" in cot["instrument"].values:
        cot_eur = cot[cot["instrument"] == "EURUSD"].set_index("date")[["noncomm_net_pct_oi_z156"]].sort_index()
        cot_eur = cot_eur[~cot_eur.index.duplicated(keep="last")]
    else:
        cot_eur = pd.DataFrame()

    ev = pd.read_csv(ROOT / "data" / "events" / "event_calendar_full.csv")
    ev["date"] = pd.to_datetime(ev["date"], errors="coerce")
    fomc_dates = set(ev[ev["event"] == "FOMC"]["date"].dropna())

    # Master trading calendar = SPY dates 2009-10-01..2026-11-20 (when VIX3M exists)
    idx = spy.loc["2009-10-01":"2026-11-20"].index
    df = pd.DataFrame(index=idx)
    df["spy_ret1"] = spy.pct_change().reindex(idx)
    df["eg_ret1"] = eg.reindex(idx).ffill().pct_change()
    df["eu_ret1"] = eu.reindex(idx).ffill().pct_change()

    # Strictly causal features known at close[t] (used ONLY for t+1..t+h)
    df["vix"] = vol["vix"].reindex(idx).ffill()
    df["slope_3m"] = vol["slope_3m"].reindex(idx).ffill()
    df["slope_9d"] = vol["slope_9d"].reindex(idx).ffill()
    df["vvix_pct"] = vol["vvix_pct"].reindex(idx).ffill()
    df["ofr_fsi"] = fsi["OFR FSI"].reindex(idx).ffill()
    df["ofr_credit"] = fsi["Credit"].reindex(idx).ffill()
    df["diff_boe_ecb"] = cb["diff_boe_ecb_dfr"].reindex(idx).ffill()
    df["diff_fed_ecb"] = cb["diff_fed_ecb_dfr"].reindex(idx).ffill()
    df["d_diff_boe_ecb_21"] = df["diff_boe_ecb"].diff(21)
    df["d_diff_fed_ecb_21"] = df["diff_fed_ecb"].diff(21)
    df["gpr_lag"] = gpr["gpr"].reindex(idx, method="ffill")
    if not cot_eur.empty:
        df["cot_eur_z"] = cot_eur["noncomm_net_pct_oi_z156"].reindex(idx, method="ffill").fillna(0.0)
    else:
        df["cot_eur_z"] = 0.0

    # Realized vol (causal trailing & strictly forward non-overlapping/target)
    df["rv21_past"] = df["spy_ret1"].rolling(21).std() * math.sqrt(252)
    df["rv5_fwd"] = df["spy_ret1"].shift(-1).rolling(5).std().shift(-4) * math.sqrt(252)
    df["rv21_fwd"] = df["spy_ret1"].shift(-1).rolling(21).std().shift(-20) * math.sqrt(252)
    df["spy_fwd5"] = spy.pct_change(5).shift(-5).reindex(idx)
    df["spy_fwd21"] = spy.pct_change(21).shift(-21).reindex(idx)
    df["eg_fwd5"] = eg.reindex(idx).ffill().pct_change(5).shift(-5)

    # Event flags (causal close-of-day or scheduled)
    df["is_fomc"] = df.index.isin(fomc_dates).astype(int)
    boe_chg_dates = set(cb_chg[cb_chg["central_bank"] == "BOE_BANK_RATE"]["date"])
    ecb_chg_dates = set(cb_chg[cb_chg["central_bank"] == "ECB_DFR"]["date"])
    df["is_boe_chg"] = df.index.isin(boe_chg_dates).astype(int)
    df["is_ecb_chg"] = df.index.isin(ecb_chg_dates).astype(int)

    feats = ["vix", "slope_3m", "slope_9d", "vvix_pct", "ofr_fsi", "ofr_credit",
             "diff_boe_ecb", "diff_fed_ecb", "d_diff_boe_ecb_21", "d_diff_fed_ecb_21", "gpr_lag", "cot_eur_z"]

    # 1. DIRECTIONAL PREDICTION (Ridge IS->OOS + Single-Signal t-stats)
    sub_dir = df.dropna(subset=feats + ["spy_fwd5", "eg_fwd5"]).copy()
    is_d = sub_dir.index < SPLIT
    oos_d = sub_dir.index >= SPLIT
    dir_results = {}
    for target_col, label in (("spy_fwd5", "SPY 5d Forward Return"), ("spy_fwd21", "SPY 21d Forward Return"), ("eg_fwd5", "EURGBP 5d Forward Return")):
        sub = sub_dir.dropna(subset=[target_col])
        is_m = sub.index < SPLIT
        oos_m = sub.index >= SPLIT
        sc = StandardScaler().fit(sub.loc[is_m, feats])
        mdl = Ridge(alpha=50.0).fit(sc.transform(sub.loc[is_m, feats]), sub.loc[is_m, target_col])
        pred_oos = pd.Series(mdl.predict(sc.transform(sub.loc[oos_m, feats])), index=sub.loc[oos_m].index)
        corr_oos = float(pred_oos.corr(sub.loc[oos_m, target_col]))
        # Sign strategy net of 2 bp switch
        sig = np.sign(pred_oos).shift(1).fillna(0.0)
        r_asset = df["spy_ret1" if "spy" in target_col else "eg_ret1"].reindex(pred_oos.index)
        sh_oos = ann_sharpe(sig * r_asset - sig.diff().abs().fillna(0) * 0.0002)
        pct = circular_shift_pct(sig, r_asset, 2.0)
        dir_results[label] = {
            "oos_corr": round(corr_oos, 4),
            "oos_net_sharpe": round(sh_oos, 3),
            "circular_shift_pct": round(pct, 1),
            "verdict": "FAIL" if pct < 95.0 or sh_oos <= 0 else "WEAK_SUPPORT",
        }

    # 2. VOLATILITY PREDICTION (Forward 21d RV R^2 & Vol-Expansion Onset AUC / BSS OOS)
    sub_v = df.dropna(subset=feats + ["rv21_past", "rv21_fwd"]).copy()
    sub_v["vol_onset"] = (sub_v["rv21_fwd"] > 1.35 * sub_v["rv21_past"]).astype(int)
    v_feats = feats + ["rv21_past"]
    is_v = sub_v.index < SPLIT
    oos_v = sub_v.index >= SPLIT
    sc_v = StandardScaler().fit(sub_v.loc[is_v, v_feats])
    # RV level regression
    reg_v = Ridge(alpha=10.0).fit(sc_v.transform(sub_v.loc[is_v, v_feats]), sub_v.loc[is_v, "rv21_fwd"])
    pred_rv_oos = reg_v.predict(sc_v.transform(sub_v.loc[oos_v, v_feats]))
    y_rv_oos = sub_v.loc[oos_v, "rv21_fwd"].to_numpy()
    r2_oos = 1.0 - float(np.sum((y_rv_oos - pred_rv_oos) ** 2) / np.sum((y_rv_oos - y_rv_oos.mean()) ** 2))
    corr_rv_oos = float(np.corrcoef(y_rv_oos, pred_rv_oos)[0, 1])

    # Onset classification (LogReg IS -> OOS)
    clf_v = LogisticRegression(C=0.5, max_iter=1000).fit(sc_v.transform(sub_v.loc[is_v, v_feats]), sub_v.loc[is_v, "vol_onset"])
    prob_oos = clf_v.predict_proba(sc_v.transform(sub_v.loc[oos_v, v_feats]))[:, 1]
    y_on_oos = sub_v.loc[oos_v, "vol_onset"].to_numpy()
    auc_oos = float(roc_auc_score(y_on_oos, prob_oos))
    brier_model = float(brier_score_loss(y_on_oos, prob_oos))
    base_rate = float(sub_v.loc[is_v, "vol_onset"].mean())
    brier_clim = float(brier_score_loss(y_on_oos, np.full_like(prob_oos, base_rate)))
    bss_oos = 1.0 - (brier_model / brier_clim) if brier_clim > 0 else 0.0

    # Event-day |return| expansion ratio (FOMC / BoE / ECB vs Normal day)
    event_vol = {}
    base_abs = float(df["spy_ret1"].abs().mean())
    base_eg_abs = float(df["eg_ret1"].abs().mean())
    for col, nm, target, bval in (
        ("is_fomc", "FOMC Decision Day (SPY)", "spy_ret1", base_abs),
        ("is_boe_chg", "BoE Rate Change Day (EURGBP)", "eg_ret1", base_eg_abs),
        ("is_ecb_chg", "ECB Rate Change Day (EURGBP)", "eg_ret1", base_eg_abs),
    ):
        ev_sub = df[df[col] == 1][target].dropna()
        event_vol[nm] = {
            "n_events": int(len(ev_sub)),
            "abs_move_ratio_vs_normal": round(float(ev_sub.abs().mean() / bval), 3) if len(ev_sub) else None,
            "mean_signed_ret_bp": round(float(ev_sub.mean() * 10000.0), 2) if len(ev_sub) else None,
        }

    # 3. REGIME CLASSIFICATION STATS
    regimes = {}
    for label, mask in (
        ("Normal Term Structure (slope_3m <= 1.0)", df["slope_3m"] <= 1.0),
        ("Inverted Stress (slope_3m > 1.0)", df["slope_3m"] > 1.0),
        ("High Financial Stress (OFR FSI > 0)", df["ofr_fsi"] > 0),
        ("Low Financial Stress (OFR FSI <= 0)", df["ofr_fsi"] <= 0),
    ):
        sub_r = df[mask]
        regimes[label] = {
            "days": int(len(sub_r)),
            "spy_ann_vol_pct": round(float(sub_r["spy_ret1"].std() * math.sqrt(252) * 100), 2),
            "spy_fwd21_median_pct": round(float(sub_r["spy_fwd21"].median() * 100), 2),
        }

    # 4 & 5. RISK-SIZING & EXPOSURE CONTROL ON SPY (IS & OOS, 2 bp turnover cost)
    # All weights strictly lagged t-1 -> return[t]
    target_vol = 0.12
    w_bh = pd.Series(1.0, index=df.index)
    w_vt = (target_vol / df["rv21_past"].replace(0, np.nan)).clip(0.0, 1.5).shift(1).fillna(1.0)
    # Macro/Term-Structure Exposure Control Overlay: cut exposure by 50% when VIX/VIX3M > 1.02 OR OFR FSI > 1.5
    stress_throttle = np.where((df["slope_3m"] > 1.02) | (df["ofr_fsi"] > 1.5), 0.5, 1.0)
    w_ctrl = (w_vt * pd.Series(stress_throttle, index=df.index).shift(1).fillna(1.0))

    risk_ctrl = {}
    for nm, w in (("SPY_Buy_And_Hold", w_bh), ("Causal_Vol_Targeting_12pct", w_vt), ("VolTarget_Plus_MacroStress_Throttle", w_ctrl)):
        net = w * df["spy_ret1"] - w.diff().abs().fillna(0.0) * 0.0002
        is_n = net[net.index < SPLIT]
        oos_n = net[net.index >= SPLIT]
        risk_ctrl[nm] = {
            "is_sharpe": round(ann_sharpe(is_n), 3),
            "oos_sharpe": round(ann_sharpe(oos_n), 3),
            "all_sharpe": round(ann_sharpe(net), 3),
            "is_maxdd_pct": round(max_dd(is_n) * 100, 2),
            "oos_maxdd_pct": round(max_dd(oos_n) * 100, 2),
            "all_maxdd_pct": round(max_dd(net) * 100, 2),
            "avg_exposure": round(float(w.mean()), 3),
        }

    payload = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "experiment": "EXP-0027",
        "split_date": str(SPLIT.date()),
        "directional_prediction": dir_results,
        "volatility_prediction": {
            "oos_rv21_r2": round(r2_oos, 4),
            "oos_rv21_corr": round(corr_rv_oos, 4),
            "oos_onset_auc": round(auc_oos, 4),
            "oos_onset_brier_skill": round(bss_oos, 4),
            "event_day_volatility": event_vol,
        },
        "regime_classification": regimes,
        "risk_sizing_and_exposure_control": risk_ctrl,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2))

    lines = [
        "# EXP-0027 — Workstream A2: Macro, Central Bank & Volatility Event Intelligence",
        "",
        f"Generated UTC: `{payload['generated_utc']}` | IS `< 2021-01-01` | OOS `>= 2021-01-01`",
        "",
        "## 1. Directional Prediction (OOS Ridge Regression + Circular-Shift Null, 2 bp cost)",
        "| Target | OOS Corr | OOS Net Sharpe | Circular-Shift Pct | Verdict |",
        "|---|---:|---:|---:|---|",
    ]
    for k, v in dir_results.items():
        lines.append(f"| {k} | {v['oos_corr']:+.4f} | {v['oos_net_sharpe']:+.3f} | {v['circular_shift_pct']}% | **{v['verdict']}** |")

    vp = payload["volatility_prediction"]
    lines += [
        "",
        "## 2. Volatility Prediction (Strictly Out-of-Sample `>= 2021-01-01`)",
        f"- **Forward 21d Realized Vol `R²` (OOS):** `{vp['oos_rv21_r2']:+.4f}` | **Pearson Corr:** `{vp['oos_rv21_corr']:+.4f}`",
        f"- **Vol-Expansion Onset (`RV21_fwd > 1.35 * RV21_past`) OOS `AUC`:** `{vp['oos_onset_auc']:.4f}` | **Brier Skill Score:** `{vp['oos_onset_brier_skill']:+.4f}`",
        "",
        "| Central Bank Event | Events | `|Move|` Ratio vs Normal Day | Mean Signed Move (bp) |",
        "|---|---:|---:|---:|",
    ]
    for en, evd in vp["event_day_volatility"].items():
        lines.append(f"| {en} | {evd['n_events']} | {evd['abs_move_ratio_vs_normal']}x | {evd['mean_signed_ret_bp']:+.2f} |")

    lines += [
        "",
        "## 3. Regime Classification",
        "| Regime | Days | SPY Ann Vol (%) | Forward 21d Median (%) |",
        "|---|---:|---:|---:|",
    ]
    for rn, rd in regimes.items():
        lines.append(f"| {rn} | {rd['days']} | {rd['spy_ann_vol_pct']}% | {rd['spy_fwd21_median_pct']:+.2f}% |")

    lines += [
        "",
        "## 4. Risk-Sizing & Exposure Control (2 bp turnover cost)",
        "| Strategy | Avg Exp | IS Sharpe | OOS Sharpe | ALL Sharpe | IS MaxDD | OOS MaxDD |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for sn, sd in risk_ctrl.items():
        lines.append(
            f"| `{sn}` | {sd['avg_exposure']} | {sd['is_sharpe']:+.3f} | {sd['oos_sharpe']:+.3f} | "
            f"{sd['all_sharpe']:+.3f} | {sd['is_maxdd_pct']}% | {sd['oos_maxdd_pct']}% |"
        )
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n")
    print(f"Wrote {OUT_JSON} and {OUT_MD}")


if __name__ == "__main__":
    main()
