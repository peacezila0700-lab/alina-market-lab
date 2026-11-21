#!/usr/bin/env python3
"""
Workstream D — Daily Risk Radar (`scripts/risk_radar.py`)
EXPLICIT SCOPE: RISK MONITORING TOOL ONLY — NOT A SIGNAL GENERATOR OR PROOF OF EDGE.

Monitors:
  1. VIX & Implied Vol Term Structure (`vol_stress_features.csv`)
  2. Systemic Financial Stress (`ofr_fsi.csv`)
  3. Equity Realized Volatility & Technical Stress (`SPY.csv`, `technicals/latest.csv`)
  4. Support / Resistance Proximity (`levels/levels_latest.csv`)
  5. 7-Day Forward Event Calendar (`events/event_calendar_full.csv`, `econ_calendar.csv`)
  6. Macro Central Bank Policy Differentials (`macro/central_bank_rates_daily.csv`)
  7. News Feed Health & Stress Keyword Density (`news/feed_status.json`, `news/headlines.csv`)
  8. Crypto Funding & Perp Basis Monitor (`microstructure/deribit_BTC_funding_1h.csv.gz`, `collect/okx_BTCUSDT_funding_deep.csv`)
  9. US Equity RegSHO Market Short Volume & Form 4 Context (`equities/finra_regsho_market_daily.csv`, `sec/insider_form4_2018_2026q1.csv.gz`)

Every panel reports:
  - `data_source`
  - `last_updated`
  - `freshness_status` (`FRESH`, `STALE_WARNING`, `CRITICAL_STALE`, `MISSING_OR_ERROR`)
  - `risk_classification` (`LOW`, `MODERATE`, `ELEVATED`, `HIGH`)
  - `alert_thresholds`
  - `missing_data_warning`

Outputs:
  - `data/risk_radar/latest.json`
  - `data/risk_radar/history.jsonl` (append-only historical log, deduplicated per `run_date`)
  - `reports/RISK_RADAR_SPEC_AND_LATEST.md`
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "risk_radar"
OUT_JSON = OUT_DIR / "latest.json"
OUT_HIST = OUT_DIR / "history.jsonl"
OUT_MD = ROOT / "reports" / "RISK_RADAR_SPEC_AND_LATEST.md"

DISCLAIMER = (
    "RISK MONITORING TOOL ONLY — Not a buy/sell signal generator or proof of trading edge. "
    "Phase C Kill Point remains active (0 validated directional edges across 31 experiments)."
)

STRESS_KEYWORDS = ("crisis", "default", "emergency", "tariff", "war", "crash", "halt", "recession", "shock", "panic")


def _rolling_z(s: pd.Series, win: int = 252, min_p: int = 60) -> pd.Series:
    mu = s.rolling(win, min_periods=min_p).mean()
    sd = s.rolling(win, min_periods=min_p).std().replace(0, np.nan)
    return ((s - mu) / sd).clip(-4.0, 4.0)


def compute_calibrated_risk_meta() -> dict:
    """
    Task 3 + EXP-0030/0031 Stationary Risk Meta-Labeling Panel (Monitoring & Sizing Only).
    Trains expanding purged HGBC + Platt models strictly up to T - 31d (21d purge + 10d embargo)
    and outputs today's calibrated probabilities + causal defensive sizing reference.
    """
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression

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

    idx = spy.loc["2011-01-04":].index
    df = pd.DataFrame(index=idx)
    c, l = spy["close"].reindex(idx), spy["low"].reindex(idx)
    r1 = c.pct_change()
    fed = cb["fed_rate_proxy"].reindex(idx).ffill().fillna(0.0)
    ofr_raw = fsi["OFR FSI"].reindex(idx).ffill()
    df["ofr_fsi_z252"] = _rolling_z(ofr_raw, 252)
    df["ofr_fsi_chg21"] = ofr_raw.diff(21)
    df["ofr_credit_z252"] = _rolling_z(fsi["Credit"].reindex(idx).ffill(), 252)
    df["ofr_funding_z252"] = _rolling_z(fsi["Funding"].reindex(idx).ffill(), 252)
    df["d_fed_63"] = fed.diff(63)
    df["d_diff_fed_ecb_21"] = cb["diff_fed_ecb_dfr"].reindex(idx).ffill().diff(21)
    df["d_diff_boe_ecb_21"] = cb["diff_boe_ecb_dfr"].reindex(idx).ffill().diff(21)
    df["gpr_z252"] = _rolling_z(gpr["gpr"].reindex(idx, method="ffill"), 252)

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

    df["rv5_past"] = r1.rolling(5).std() * math.sqrt(252)
    df["rv21_past"] = r1.rolling(21).std() * math.sqrt(252)
    df["rv63_past"] = r1.rolling(63).std() * math.sqrt(252)
    df["rv_ratio_5_21"] = df["rv5_past"] / df["rv21_past"].replace(0, np.nan)

    feats = [
        "ofr_fsi_z252", "ofr_fsi_chg21", "ofr_credit_z252", "ofr_funding_z252",
        "d_fed_63", "d_diff_fed_ecb_21", "d_diff_boe_ecb_21", "gpr_z252",
        "cot_sp500_z", "cot_vix_z", "cot_ust10y_z", "cot_eur_z", "fomc_within_5d",
        "vix", "slope_3m", "slope_9d", "vvix_pct", "skew", "vix_chg21",
        "rv5_past", "rv21_past", "rv63_past", "rv_ratio_5_21",
    ]

    H = 21
    EMB = 10
    PURGE_GAP = H + EMB
    r_arr, l_arr, c_arr, rv_arr = r1.to_numpy(), l.to_numpy(), c.to_numpy(), df["rv21_past"].to_numpy()
    y_on = np.full(len(df), np.nan)
    y_ts = np.full(len(df), np.nan)
    y_tb = np.full(len(df), np.nan)
    for i in range(len(df) - H):
        if not np.isfinite(rv_arr[i]) or c_arr[i] <= 0:
            continue
        rv_f = float(np.std(r_arr[i + 1 : i + 1 + H], ddof=1) * math.sqrt(252.0))
        min_l = float(np.min(l_arr[i + 1 : i + 1 + H]) / c_arr[i] - 1.0)
        y_on[i] = 1.0 if rv_f > 1.35 * rv_arr[i] else 0.0
        y_ts[i] = 1.0 if (rv_f > 0.20 or min_l <= -0.05) else 0.0
        y_tb[i] = 1.0 if (min_l <= -0.05 or rv_f > 0.20) else 0.0

    df["y_vol_onset"] = y_on
    df["y_tail_stress"] = y_ts
    df["y_tb_nondir"] = y_tb

    feat_clean = df.dropna(subset=feats)
    x_live = feat_clean[feats].iloc[[-1]].to_numpy()
    live_row = feat_clean.iloc[-1]
    as_of_date = feat_clean.index[-1].strftime("%Y-%m-%d")

    train_df = feat_clean.dropna(subset=["y_vol_onset", "y_tail_stress", "y_tb_nondir"])
    tr_end = len(train_df) - PURGE_GAP
    split_c = int(tr_end * 0.72)
    fit_e = max(120, split_c - PURGE_GAP)
    X_tr = train_df[feats].to_numpy()

    probs = {}
    for col, key in [
        ("y_vol_onset", "p_vol_onset_21d"),
        ("y_tail_stress", "p_tail_stress_21d"),
        ("y_tb_nondir", "p_tb_nondir_stress_21d"),
    ]:
        y_tr = train_df[col].to_numpy(dtype=int)
        bm = HistGradientBoostingClassifier(max_depth=2, max_iter=60, min_samples_leaf=50, l2_regularization=5.0, random_state=42)
        bm.fit(X_tr[:fit_e], y_tr[:fit_e])
        pc = bm.predict_proba(X_tr[split_c:tr_end])[:, 1]
        pl = bm.predict_proba(x_live)[:, 1]
        eps = 1e-6
        zc = np.log(np.clip(pc, eps, 1 - eps) / (1 - np.clip(pc, eps, 1 - eps))).reshape(-1, 1)
        zl = np.log(np.clip(pl, eps, 1 - eps) / (1 - np.clip(pl, eps, 1 - eps))).reshape(-1, 1)
        cal = LogisticRegression(C=1.0).fit(zc, y_tr[split_c:tr_end])
        probs[key] = round(float(cal.predict_proba(zl)[0, 1]), 4)

    rv21_now = float(live_row["rv21_past"])
    vt_exp = float(np.clip(0.12 / max(rv21_now, 1e-4), 0.0, 1.5))
    throttle = float(
        np.clip(
            1.0 - 1.3 * max(0.0, probs["p_vol_onset_21d"] - 0.25) - 1.1 * max(0.0, probs["p_tb_nondir_stress_21d"] - 0.30),
            0.35,
            1.0,
        )
    )
    meta_exp = vt_exp * throttle
    cash_buf = max(0.0, 1.0 - meta_exp)

    return {
        "scope": "MONITORING_AND_OFFLINE_SIZING_ONLY_NOT_DIRECTIONAL_SIGNAL",
        "as_of_date": as_of_date,
        "train_cutoff_date": train_df.index[tr_end - 1].strftime("%Y-%m-%d"),
        "purge_plus_embargo_days": PURGE_GAP,
        "calibrated_probabilities": probs,
        "stationary_drivers": {
            "ofr_fsi_z252": round(float(live_row["ofr_fsi_z252"]), 3),
            "gpr_z252": round(float(live_row["gpr_z252"]), 3),
            "d_fed_63": round(float(live_row["d_fed_63"]), 3),
            "vix": round(float(live_row["vix"]), 2),
            "slope_3m": round(float(live_row["slope_3m"]), 3),
            "rv21_past_pct": round(rv21_now * 100.0, 2),
        },
        "defensive_sizing_reference": {
            "vol_target_12pct_exposure_pct": round(vt_exp * 100.0, 1),
            "meta_throttle_scalar": round(throttle, 3),
            "meta_cash_equity_exposure_pct": round(meta_exp * 100.0, 1),
            "cash_buffer_pct": round(cash_buf * 100.0, 1),
            "exp0031_note": "Park throttled equity weight in Cash/Short-Bills (NOT blind TLT rotation when d_fed_63 > 0).",
        },
    }


def compute_fx_execution_guard() -> dict:
    """EXP-0030 Track B FX execution-cost & liquidity-shock guard summary (EURGBP H1 Dukascopy)."""
    eg = pd.read_csv(ROOT / "data" / "intraday" / "EURGBP_H1_bidask.csv.gz")
    eg["dt"] = pd.to_datetime(eg["ts_utc"], utc=True)
    eg = eg.sort_values("dt").reset_index(drop=True)
    sp = eg["spread_close_pips"].clip(lower=0.0)
    sp_z72 = _rolling_z(sp, 72, 24)
    last_dt = eg["dt"].iloc[-1]
    last_sp = float(sp.iloc[-1])
    last_z = float(sp_z72.iloc[-1])
    hr = int(last_dt.hour)
    in_rollover_hazard = hr in (16, 17, 18, 19, 20, 21, 22, 23)
    return {
        "pair": "EURGBP_H1_Dukascopy",
        "last_bar_utc": last_dt.isoformat(),
        "latest_hour_utc": hr,
        "latest_spread_pips": round(last_sp, 2),
        "spread_z72": round(last_z, 2) if np.isfinite(last_z) else None,
        "rollover_hazard_window_utc": "16:00-23:00 UTC (6h horizon touches 21-22 UTC rollover)",
        "last_bar_in_rollover_hazard": in_rollover_hazard,
        "exp0030_gate_benchmark": "70pct VALID MetaGate cuts 6h shock 34.9% -> 16.1% & drag 2.21p -> 1.85p (net stays -2.10p < 0; Phase C locked).",
    }


def _freshness(last_date_str: str | None, ref_dt: datetime, warn_days: int = 4, crit_days: int = 10) -> tuple[str, int | None]:
    if not last_date_str:
        return "MISSING_OR_ERROR", None
    dt = pd.to_datetime(last_date_str, utc=True, errors="coerce")
    if pd.isna(dt):
        return "MISSING_OR_ERROR", None
    age = int(max(0, (ref_dt - dt.to_pydatetime()).days))
    if age <= warn_days:
        return "FRESH", age
    if age <= crit_days:
        return "STALE_WARNING", age
    return "CRITICAL_STALE", age


def _rank_risk(val: float | None, elev: float, high: float, reverse: bool = False) -> str:
    if val is None or not np.isfinite(val):
        return "UNKNOWN"
    if not reverse:
        if val >= high:
            return "HIGH"
        if val >= elev:
            return "ELEVATED"
        return "LOW"
    else:
        if val <= high:
            return "HIGH"
        if val <= elev:
            return "ELEVATED"
        return "LOW"


def compute_crypto_trend_overlay() -> dict:
    """
    EXP-0041: Strictly causal Daily Crypto Trend Regime + VolTarget 25% Monitor (BTC-USD).
    Long-only trend-regime defense / sizing overlay (not market-neutral alpha).
    """
    btc = pd.read_csv(ROOT / "data" / "universe" / "BTC.csv")
    btc["date"] = pd.to_datetime(btc["date"], errors="coerce")
    btc = btc.dropna(subset=["date", "close"]).drop_duplicates("date").sort_values("date").set_index("date")
    c = pd.to_numeric(btc["close"], errors="coerce").dropna()
    r = c.pct_change().fillna(0.0)
    sma50 = float(c.rolling(50).mean().iloc[-1])
    last_c = float(c.iloc[-1])
    votes = [float(last_c > float(c.rolling(lb).mean().iloc[-1])) for lb in (20, 40, 60, 90, 120)]
    trend_ens = float(sum(votes) / 5.0)
    rv21 = max(0.15, float(r.rolling(21).std().iloc[-1] * math.sqrt(365.0)))
    vt25_scalar = min(1.0, 0.25 / rv21)
    target_w_ens = round(trend_ens * vt25_scalar * 100.0, 1)
    target_w_sma50 = round((1.0 if last_c > sma50 else 0.0) * vt25_scalar * 100.0, 1)
    return {
        "as_of_date": c.index[-1].strftime("%Y-%m-%d"),
        "btc_close": round(last_c, 2),
        "btc_sma50": round(sma50, 2),
        "above_sma50": bool(last_c > sma50),
        "trend_ens_vote_20_40_60_90_120": round(trend_ens, 2),
        "rv21_ann_pct": round(rv21 * 100.0, 2),
        "vt25_scalar": round(vt25_scalar, 3),
        "suggested_btc_ens_vt25_pct": target_w_ens,
        "suggested_btc_sma50_vt25_pct": target_w_sma50,
        "suggested_cash_pct": round(100.0 - target_w_ens, 1),
        "exp0041_note": "EXP-0041 (2015-2026 BTC 11.5y EFFR excess): SMA50_VT25 Sh +1.665 DD -33.5% (Shift=99.9%); TrendEns_VT25 Sh +1.590 DD -27.8% (Shift=99.9%). Monitoring/defense reference only.",
    }


def build_risk_radar() -> dict:
    now = datetime.now(timezone.utc)
    run_date = now.strftime("%Y-%m-%d")
    alerts: list[dict] = []
    missing_warnings: list[str] = []
    panels: dict[str, dict] = {}

    # 1. VIX & Term Structure
    try:
        p = ROOT / "data" / "collect" / "vol_stress_features.csv"
        df = pd.read_csv(p)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"]).sort_values("date")
        last = df.iloc[-1]
        ld = last["date"].strftime("%Y-%m-%d")
        fr, age = _freshness(ld, now)
        vix = float(last["vix"])
        s3 = float(last["slope_3m"])
        s9 = float(last["slope_9d"])
        vv = float(last["vvix_pct"])
        rc = "HIGH" if (vix >= 30 or s3 > 1.05) else ("ELEVATED" if (vix >= 22 or s3 > 1.00 or vv >= 0.90) else "LOW")
        if s3 > 1.0:
            alerts.append({"panel": "vol_term_structure", "severity": rc, "msg": f"VIX/VIX3M inverted at {s3:.3f} (>1.00)"})
        if vv >= 0.90:
            alerts.append({"panel": "vol_term_structure", "severity": "ELEVATED", "msg": f"VVIX percentile elevated at {vv:.2f} (>=0.90)"})
        panels["vol_term_structure"] = {
            "data_source": "data/collect/vol_stress_features.csv (CBOE VIX/VIX3M/VIX9D/VVIX)",
            "last_updated": ld,
            "age_days": age,
            "freshness_status": fr,
            "risk_classification": rc,
            "alert_thresholds": {"vix_elev": 22.0, "vix_high": 30.0, "slope_3m_inversion": 1.00, "vvix_pct_elev": 0.90},
            "metrics": {"vix": round(vix, 2), "slope_3m": round(s3, 3), "slope_9d": round(s9, 3), "vvix_pct": round(vv, 3)},
            "missing_data_warning": None if fr == "FRESH" else f"Vol term structure stale ({age}d old)",
        }
    except Exception as e:
        panels["vol_term_structure"] = {"data_source": "data/collect/vol_stress_features.csv", "freshness_status": "MISSING_OR_ERROR", "risk_classification": "UNKNOWN", "missing_data_warning": str(e)}
        missing_warnings.append(f"vol_term_structure error: {e}")

    # 2. OFR Financial Stress Index
    try:
        p = ROOT / "data" / "collect" / "ofr_fsi.csv"
        df = pd.read_csv(p)
        df["dt"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["dt"]).sort_values("dt")
        last = df.iloc[-1]
        ld = last["dt"].strftime("%Y-%m-%d")
        fr, age = _freshness(ld, now, warn_days=5, crit_days=14)
        fsi = float(last["OFR FSI"])
        cr = float(last["Credit"])
        rc = _rank_risk(fsi, 0.0, 2.0)
        if rc in ("ELEVATED", "HIGH"):
            alerts.append({"panel": "ofr_fsi", "severity": rc, "msg": f"OFR FSI positive at {fsi:+.2f} (>0 stress threshold)"})
        panels["ofr_fsi"] = {
            "data_source": "data/collect/ofr_fsi.csv (US Treasury OFR)",
            "last_updated": ld,
            "age_days": age,
            "freshness_status": fr,
            "risk_classification": rc,
            "alert_thresholds": {"fsi_elevated": 0.0, "fsi_high": 2.0},
            "metrics": {"ofr_fsi": round(fsi, 3), "credit": round(cr, 3), "volatility_sub": round(float(last["Volatility"]), 3)},
            "missing_data_warning": None if fr == "FRESH" else f"OFR FSI lagging ({age}d old)",
        }
    except Exception as e:
        panels["ofr_fsi"] = {"data_source": "data/collect/ofr_fsi.csv", "freshness_status": "MISSING_OR_ERROR", "risk_classification": "UNKNOWN", "missing_data_warning": str(e)}
        missing_warnings.append(f"ofr_fsi error: {e}")

    # 3. Equity Realized Vol & Technical Stress (SPY)
    try:
        p = ROOT / "data" / "universe" / "SPY.csv"
        df = pd.read_csv(p)
        df["dt"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["dt"]).sort_values("dt")
        ld = df["dt"].iloc[-1].strftime("%Y-%m-%d")
        fr, age = _freshness(ld, now)
        r = df["close"].pct_change()
        rv20 = float(r.tail(20).std() * math.sqrt(252) * 100.0)
        rv63 = float(r.tail(63).std() * math.sqrt(252) * 100.0)
        hi252 = float(df["close"].tail(252).max())
        dd52 = float((df["close"].iloc[-1] / hi252 - 1.0) * 100.0)
        rc = "HIGH" if (rv20 >= 28 or dd52 <= -15) else ("ELEVATED" if (rv20 >= 18 or dd52 <= -8) else "LOW")
        if rc != "LOW":
            alerts.append({"panel": "equity_vol_dd", "severity": rc, "msg": f"SPY RV20={rv20:.1f}%, 52w DD={dd52:.1f}%"})
        panels["equity_vol_dd"] = {
            "data_source": "data/universe/SPY.csv (Yahoo Finance Daily)",
            "last_updated": ld,
            "age_days": age,
            "freshness_status": fr,
            "risk_classification": rc,
            "alert_thresholds": {"rv20_elev": 18.0, "rv20_high": 28.0, "dd52_elev": -8.0, "dd52_high": -15.0},
            "metrics": {"spy_close": round(float(df["close"].iloc[-1]), 2), "rv20_pct": round(rv20, 2), "rv63_pct": round(rv63, 2), "dd_52w_pct": round(dd52, 2)},
            "missing_data_warning": None if fr == "FRESH" else f"SPY data stale ({age}d)",
        }
    except Exception as e:
        panels["equity_vol_dd"] = {"data_source": "data/universe/SPY.csv", "freshness_status": "MISSING_OR_ERROR", "risk_classification": "UNKNOWN", "missing_data_warning": str(e)}
        missing_warnings.append(f"equity_vol_dd error: {e}")

    # 4. Support / Resistance Proximity (levels_latest.csv)
    try:
        p = ROOT / "data" / "levels" / "levels_latest.csv"
        df = pd.read_csv(p)
        ld = str(df["as_of"].iloc[0])[:10]
        fr, age = _freshness(ld, now, warn_days=5, crit_days=14)
        sub = df[df["instrument"].isin(["SPY", "QQQ", "EURUSD", "EURGBP", "BTC", "GOLD"])]
        prox = []
        near_crit = False
        for _, row in sub.iterrows():
            atr = float(row["atr14"]) if float(row["atr14"]) > 0 else 1.0
            c = float(row["close"])
            s1, r1 = float(row["pivot_s1"]), float(row["pivot_r1"])
            dist_s1_atr = round((c - s1) / atr, 2)
            dist_r1_atr = round((r1 - c) / atr, 2)
            if abs(dist_s1_atr) < 0.35 or abs(dist_r1_atr) < 0.35:
                near_crit = True
            prox.append({"instrument": row["instrument"], "close": round(c, 4), "s1": round(s1, 4), "r1": round(r1, 4), "dist_s1_atr": dist_s1_atr, "dist_r1_atr": dist_r1_atr})
        rc = "MODERATE" if near_crit else "LOW"
        panels["support_resistance"] = {
            "data_source": "data/levels/levels_latest.csv",
            "last_updated": ld,
            "age_days": age,
            "freshness_status": fr,
            "risk_classification": rc,
            "alert_thresholds": {"near_pivot_atr": 0.35},
            "metrics": {"instruments": prox},
            "missing_data_warning": None if fr == "FRESH" else f"Levels snapshot is {age}d old (regenerate build_levels)",
        }
    except Exception as e:
        panels["support_resistance"] = {"data_source": "data/levels/levels_latest.csv", "freshness_status": "MISSING_OR_ERROR", "risk_classification": "UNKNOWN", "missing_data_warning": str(e)}
        missing_warnings.append(f"support_resistance error: {e}")

    # 5. 7-Day Event Calendar
    try:
        ev = pd.read_csv(ROOT / "data" / "events" / "event_calendar_full.csv")
        ev["dt"] = pd.to_datetime(ev["date"], errors="coerce")
        today_pd = pd.Timestamp(now.date())
        win = ev[(ev["dt"] >= today_pd) & (ev["dt"] <= today_pd + pd.Timedelta(days=7))].sort_values("dt")
        # Also include data/collect/econ_calendar.csv latest snapshot info
        ev_list = [{"date": r["dt"].strftime("%Y-%m-%d"), "event": str(r["event"]), "detail": str(r["detail"])} for _, r in win.iterrows()]
        has_fomc = any("FOMC" in e["event"].upper() for e in ev_list)
        rc = "ELEVATED" if has_fomc else ("MODERATE" if len(ev_list) > 0 else "LOW")
        if has_fomc:
            alerts.append({"panel": "calendar_7d", "severity": "ELEVATED", "msg": "FOMC decision within next 7 days (historically 1.19x SPY abs move)"})
        panels["calendar_7d"] = {
            "data_source": "data/events/event_calendar_full.csv",
            "last_updated": run_date,
            "age_days": 0,
            "freshness_status": "FRESH",
            "risk_classification": rc,
            "alert_thresholds": {"fomc_7d": True},
            "metrics": {"upcoming_7d_count": len(ev_list), "events": ev_list[:10]},
            "missing_data_warning": None if ev["dt"].max() >= pd.Timestamp("2027-12-01") else "Note: ECB/BoE 2027 dates require annual calendar extension after Dec 2026.",
        }
    except Exception as e:
        panels["calendar_7d"] = {"data_source": "data/events/event_calendar_full.csv", "freshness_status": "MISSING_OR_ERROR", "risk_classification": "UNKNOWN", "missing_data_warning": str(e)}
        missing_warnings.append(f"calendar_7d error: {e}")

    # 6. Macro Central Bank Differentials
    try:
        cb = pd.read_csv(ROOT / "data" / "macro" / "central_bank_rates_daily.csv")
        cb["dt"] = pd.to_datetime(cb["date"], errors="coerce")
        cb = cb.dropna(subset=["dt"]).sort_values("dt")
        last = cb.iloc[-1]
        ld = last["dt"].strftime("%Y-%m-%d")
        fr, age = _freshness(ld, now)
        panels["macro_rates"] = {
            "data_source": "data/macro/central_bank_rates_daily.csv (ECB + BoE + NYFed EFFR)",
            "last_updated": ld,
            "age_days": age,
            "freshness_status": fr,
            "risk_classification": "LOW",
            "alert_thresholds": {"abs_spread_wide_pct": 2.0},
            "metrics": {
                "ecb_dfr": round(float(last["ecb_dfr"]), 3),
                "boe_rate": round(float(last["boe_rate"]), 3),
                "fed_rate_proxy": round(float(last["fed_rate_proxy"]), 3),
                "diff_boe_ecb_dfr": round(float(last["diff_boe_ecb_dfr"]), 3),
                "diff_fed_ecb_dfr": round(float(last["diff_fed_ecb_dfr"]), 3),
            },
            "missing_data_warning": None if fr == "FRESH" else f"CB rates stale ({age}d)",
        }
    except Exception as e:
        panels["macro_rates"] = {"data_source": "data/macro/central_bank_rates_daily.csv", "freshness_status": "MISSING_OR_ERROR", "risk_classification": "UNKNOWN", "missing_data_warning": str(e)}
        missing_warnings.append(f"macro_rates error: {e}")

    # 7. News Feed Health & Stress Keywords
    try:
        fs = json.loads((ROOT / "data" / "news" / "feed_status.json").read_text())
        hl = pd.read_csv(ROOT / "data" / "news" / "headlines.csv")
        feeds = fs.get("feeds", {})
        ok_cnt = sum(1 for v in feeds.values() if str(v).startswith("OK"))
        tot_cnt = len(feeds)
        stamp_val = fs.get("stamp") or fs.get("fetched_utc") or ""
        ld = str(stamp_val)[:10]
        fr, age = _freshness(stamp_val, now, warn_days=2, crit_days=5)
        titles = hl["title"].astype(str).tolist()
        stress_hits = [t for t in titles if any(kw in t.lower() for kw in STRESS_KEYWORDS)]
        rc = "ELEVATED" if (ok_cnt < tot_cnt or len(stress_hits) >= 25) else ("MODERATE" if len(stress_hits) >= 12 else "LOW")
        if ok_cnt < tot_cnt:
            missing_warnings.append(f"News feed partial degradation: {ok_cnt}/{tot_cnt} OK")
        panels["news_stress"] = {
            "data_source": "data/news/feed_status.json + headlines.csv (16 RSS feeds)",
            "last_updated": str(stamp_val)[:19],
            "age_days": age,
            "freshness_status": fr,
            "risk_classification": rc,
            "alert_thresholds": {"min_feeds_ok": tot_cnt, "stress_headlines_elev": 25},
            "metrics": {"feeds_ok": ok_cnt, "feeds_total": tot_cnt, "unique_headlines": len(hl), "stress_keyword_hits": len(stress_hits)},
            "missing_data_warning": None if ok_cnt == tot_cnt else f"Only {ok_cnt}/{tot_cnt} RSS feeds succeeded",
        }
    except Exception as e:
        panels["news_stress"] = {"data_source": "data/news/feed_status.json", "freshness_status": "MISSING_OR_ERROR", "risk_classification": "UNKNOWN", "missing_data_warning": str(e)}
        missing_warnings.append(f"news_stress error: {e}")

    # 8. Crypto Funding & Basis Monitor
    try:
        der = pd.read_csv(ROOT / "data" / "microstructure" / "deribit_BTC_funding_1h.csv.gz")
        der["dt"] = pd.to_datetime(der["ts"], format="ISO8601", utc=True)
        der = der.sort_values("dt")
        ld = der["dt"].iloc[-1].strftime("%Y-%m-%d")
        fr, age = _freshness(der["dt"].iloc[-1].isoformat(), now, warn_days=2, crit_days=7)
        der_24h_apr = float(der["interest_1h"].tail(24).mean() * 8760.0 * 100.0)
        okx_f = pd.read_csv(ROOT / "data" / "collect" / "okx_BTCUSDT_funding_deep.csv")
        okx_last_apr = float(okx_f["fundingRate"].tail(3).mean() * 3 * 365 * 100.0) if not okx_f.empty else None
        rc = "ELEVATED" if (abs(der_24h_apr) >= 25.0) else "LOW"
        has_cv = (ROOT / "data" / "crypto_vision" / "binance_BTCUSDT_um_funding.csv.gz").exists()
        panels["crypto_funding_basis"] = {
            "data_source": "data/microstructure/deribit_BTC_funding_1h.csv.gz + data/crypto_vision/ + okx_BTCUSDT_funding_deep.csv",
            "last_updated": ld,
            "age_days": age,
            "freshness_status": fr,
            "risk_classification": rc,
            "alert_thresholds": {"abs_funding_apr_elev": 25.0},
            "metrics": {
                "deribit_btc_24h_apr_pct": round(der_24h_apr, 2),
                "deribit_btc_index": round(float(der["index_price"].iloc[-1]), 2),
                "okx_btc_24h_apr_pct": round(okx_last_apr, 2) if okx_last_apr is not None else None,
            },
            "missing_data_warning": (
                None if has_cv else "OKX public funding API limited to ~93d; Binance (HTTP 451) & Bybit (HTTP 403) blocked in sandbox."
            ),
        }
    except Exception as e:
        panels["crypto_funding_basis"] = {"data_source": "data/microstructure/", "freshness_status": "MISSING_OR_ERROR", "risk_classification": "UNKNOWN", "missing_data_warning": str(e)}
        missing_warnings.append(f"crypto_funding_basis error: {e}")

    # 9. US Equity RegSHO Market Short Volume & Insider Context (Monitoring Only - EXP-0035)
    try:
        reg_p = ROOT / "data" / "equities" / "finra_regsho_market_daily.csv"
        reg_m = pd.read_csv(reg_p)
        reg_m["dt"] = pd.to_datetime(reg_m["date"], errors="coerce")
        reg_m = reg_m.dropna(subset=["dt"]).sort_values("dt")
        ld = reg_m["dt"].iloc[-1].strftime("%Y-%m-%d")
        fr, age = _freshness(ld, now)
        sr = pd.to_numeric(reg_m["mkt_short_ratio"], errors="coerce")
        sr_last = float(sr.iloc[-1])
        sr_ma5 = float(sr.tail(5).mean())
        sr_ma60 = float(sr.tail(60).mean())
        sr_sd60 = float(sr.tail(60).std())
        sr_z60 = float((sr_last - sr_ma60) / sr_sd60) if sr_sd60 > 0 else 0.0
        sr_surge = float(sr_ma5 - sr_ma60)
        rc = "ELEVATED" if abs(sr_z60) >= 2.5 else ("MODERATE" if abs(sr_z60) >= 1.75 else "LOW")
        if rc != "LOW":
            alerts.append({"panel": "equity_short_insider_breadth", "severity": rc, "msg": f"FINRA RegSHO mkt short ratio={sr_last:.3f} (z60={sr_z60:+.2f})"})
        panels["equity_short_insider_breadth"] = {
            "data_source": "data/equities/finra_regsho_market_daily.csv (FINRA RegSHO CNMS, monitoring context only; EXP-0035)",
            "last_updated": ld,
            "age_days": age,
            "freshness_status": fr,
            "risk_classification": rc,
            "alert_thresholds": {"abs_regsho_z60_mod": 1.75, "abs_regsho_z60_elev": 2.50},
            "metrics": {
                "regsho_mkt_short_ratio": round(sr_last, 4),
                "regsho_ma5": round(sr_ma5, 4),
                "regsho_surge_5v60": round(sr_surge, 4),
                "regsho_z60": round(sr_z60, 2),
                "n_nms_symbols": int(reg_m["n_symbols"].iloc[-1]),
                "sec_form4_archive_range": "2018q1..2026q1 (quarterly DERA; context only)",
            },
            "missing_data_warning": None if fr == "FRESH" else f"FINRA RegSHO stale ({age}d old)",
        }
    except Exception as e:
        panels["equity_short_insider_breadth"] = {"data_source": "data/equities/finra_regsho_market_daily.csv", "freshness_status": "MISSING_OR_ERROR", "risk_classification": "UNKNOWN", "missing_data_warning": str(e)}
        missing_warnings.append(f"equity_short_insider_breadth error: {e}")

    # Freshness SLA audit across all panels
    stale_panels = [k for k, v in panels.items() if v.get("freshness_status") in ("STALE_WARNING", "CRITICAL_STALE", "MISSING_OR_ERROR")]
    for sp in stale_panels:
        missing_warnings.append(f"{sp}: freshness={panels[sp].get('freshness_status')} (age={panels[sp].get('age_days')}d)")

    # Overall Risk Classification
    ranks = {"LOW": 0, "MODERATE": 1, "ELEVATED": 2, "HIGH": 3, "UNKNOWN": 1}
    max_r = max((ranks.get(v.get("risk_classification", "LOW"), 0) for v in panels.values()), default=0)
    inv_r = {0: "LOW", 1: "MODERATE", 2: "ELEVATED", 3: "HIGH"}
    overall_risk = inv_r[max_r]

    try:
        risk_meta = compute_calibrated_risk_meta()
    except Exception as e:
        risk_meta = {"error": str(e)}
        missing_warnings.append(f"risk_meta_model error: {e}")

    try:
        fx_guard = compute_fx_execution_guard()
    except Exception as e:
        fx_guard = {"error": str(e)}
        missing_warnings.append(f"fx_execution_guard error: {e}")

    try:
        crypto_overlay = compute_crypto_trend_overlay()
    except Exception as e:
        crypto_overlay = {"error": str(e)}
        missing_warnings.append(f"crypto_trend_overlay error: {e}")

    payload = {
        "generated_utc": now.isoformat(timespec="seconds"),
        "run_date": run_date,
        "disclaimer": DISCLAIMER,
        "overall_risk_classification": overall_risk,
        "fresh_panels": len(panels) - len(stale_panels),
        "total_panels": len(panels),
        "stale_or_missing_panels": stale_panels,
        "active_alerts": alerts,
        "missing_data_warnings": list(dict.fromkeys(missing_warnings)),
        "panels": panels,
        "risk_meta_model": risk_meta,
        "fx_execution_guard": fx_guard,
        "crypto_trend_overlay": crypto_overlay,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2))

    # Append deduplicated snapshot to history.jsonl
    hist_lines = []
    if OUT_HIST.exists():
        for l in OUT_HIST.read_text().splitlines():
            if not l.strip():
                continue
            try:
                rec = json.loads(l)
                if rec.get("run_date") != run_date:
                    hist_lines.append(json.dumps(rec))
            except Exception:
                continue
    compact = {
        "run_date": run_date,
        "generated_utc": payload["generated_utc"],
        "overall_risk_classification": overall_risk,
        "fresh_panels": payload["fresh_panels"],
        "total_panels": payload["total_panels"],
        "alerts_count": len(alerts),
        "vix": panels.get("vol_term_structure", {}).get("metrics", {}).get("vix"),
        "slope_3m": panels.get("vol_term_structure", {}).get("metrics", {}).get("slope_3m"),
        "ofr_fsi": panels.get("ofr_fsi", {}).get("metrics", {}).get("ofr_fsi"),
        "spy_rv20": panels.get("equity_vol_dd", {}).get("metrics", {}).get("rv20_pct"),
        "p_vol_onset_21d": risk_meta.get("calibrated_probabilities", {}).get("p_vol_onset_21d"),
        "p_tail_stress_21d": risk_meta.get("calibrated_probabilities", {}).get("p_tail_stress_21d"),
    }
    hist_lines.append(json.dumps(compact))
    OUT_HIST.write_text("\n".join(hist_lines) + "\n")

    # Markdown Specification & Latest Reading
    lines = [
        "# Daily Risk Radar — Specification & Latest Reading",
        "",
        f"> **{DISCLAIMER}**",
        "",
        f"Generated UTC: `{payload['generated_utc']}` | Overall Risk Classification: **`{overall_risk}`** | Fresh Panels: `{payload['fresh_panels']}/{payload['total_panels']}`",
        "",
        "## 1. Panel Status, Data Sources, Freshness & Thresholds",
        "| Panel | Last Updated | Age (d) | Freshness | Risk Class | Key Metrics | Warning |",
        "|---|---|---:|---|---|---|---|",
    ]
    for k, v in panels.items():
        m_str = json.dumps(v.get("metrics", {}))[:95]
        w_str = v.get("missing_data_warning") or "none"
        lines.append(
            f"| `{k}` | `{v.get('last_updated', '?')}` | {v.get('age_days', '?')} | `{v.get('freshness_status')}` | "
            f"**{v.get('risk_classification')}** | `{m_str}` | {w_str} |"
        )
    if "calibrated_probabilities" in risk_meta:
        cp = risk_meta["calibrated_probabilities"]
        ds = risk_meta["defensive_sizing_reference"]
        sd = risk_meta["stationary_drivers"]
        lines += [
            "",
            "## 2. Calibrated Risk Meta-Labeling (`Task 3 + EXP-0030/0031`, Offline Sizing & Monitor Only)",
            f"- **As-Of Date:** `{risk_meta['as_of_date']}` | **Causal Train Cutoff (`-31d` Purge+Embargo):** `{risk_meta['train_cutoff_date']}`",
            f"- **Calibrated Probabilities (`HGBC + Platt`):** `P(VolOnset_21d) = {cp['p_vol_onset_21d']:.4f}` | `P(TailStress_21d) = {cp['p_tail_stress_21d']:.4f}` | `P(TB_NonDirStress_21d) = {cp['p_tb_nondir_stress_21d']:.4f}`",
            f"- **Stationary Macro/Vol State:** `OFR_FSI_z252={sd['ofr_fsi_z252']}`, `GPR_z252={sd['gpr_z252']}`, `d_Fed_63d={sd['d_fed_63']}`, `VIX={sd['vix']}`, `Slope3M={sd['slope_3m']}`, `RV21={sd['rv21_past_pct']}%`",
            f"- **Defensive Sizing Reference (`EXP-0031`):** `VolTarget12%={ds['vol_target_12pct_exposure_pct']}%` × `MetaThrottle={ds['meta_throttle_scalar']}` -> **`Equity={ds['meta_cash_equity_exposure_pct']}%` / `Cash Buffer={ds['cash_buffer_pct']}%`**",
        ]
    if "latest_spread_pips" in fx_guard:
        lines += [
            "",
            "## 3. FX Intraday Rollover & Cost-Shock Guard (`EXP-0030 Track B`)",
            f"- **`EURGBP H1` Last Bar:** `{fx_guard['last_bar_utc']}` | Spread `{fx_guard['latest_spread_pips']} pips` (`z72={fx_guard['spread_z72']}`) | In 6h Rollover Hazard (`16–23 UTC`): `{fx_guard['last_bar_in_rollover_hazard']}`",
        ]
    if "btc_close" in crypto_overlay:
        lines += [
            "",
            "## 4. Crypto Daily Trend Regime & VolTarget25% Monitor (`EXP-0041`, Monitoring Reference)",
            f"- **`BTC-USD` As-Of `{crypto_overlay['as_of_date']}`:** Close `${crypto_overlay['btc_close']:,.2f}` | `SMA(50)=${crypto_overlay['btc_sma50']:,.2f}` (`Above={crypto_overlay['above_sma50']}`) | `TrendEns(20,40,60,90,120)={crypto_overlay['trend_ens_vote_20_40_60_90_120']:.2f}` | `RV21={crypto_overlay['rv21_ann_pct']}%`",
            f"- **Vol-Targeted Reference (`VT25%`):** `TrendEns x VT25 = {crypto_overlay['suggested_btc_ens_vt25_pct']}%` (`SMA50 x VT25 = {crypto_overlay['suggested_btc_sma50_vt25_pct']}%`) | Cash/EFFR `{crypto_overlay['suggested_cash_pct']}%`",
        ]
    lines += ["", "## 5. Active Risk Alerts"]
    if alerts:
        for a in alerts:
            lines.append(f"- **[{a['severity']}] `{a['panel']}`:** {a['msg']}")
    else:
        lines.append("- None triggered.")
    lines += ["", "## 6. Missing Data / Staleness Warnings"]
    if payload["missing_data_warnings"]:
        for w in payload["missing_data_warnings"]:
            lines.append(f"- {w}")
    else:
        lines.append("- None.")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n")
    print(f"RISK RADAR OK: overall={overall_risk} | fresh={payload['fresh_panels']}/{payload['total_panels']} | alerts={len(alerts)}")
    return payload


if __name__ == "__main__":
    build_risk_radar()
