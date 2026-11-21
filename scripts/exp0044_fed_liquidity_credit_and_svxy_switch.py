#!/usr/bin/env python3
"""
EXP-0044 — US Fed Net Liquidity (WALCL - TGA - RRP) + HY Credit OAS + VIX ETP Term-Structure Switch
1) Tests Net Liquidity & High-Yield OAS as causal SPY / BTC timing AND as an ablation on ALINA's 23-feature Risk Meta WF model.
2) Tests causal VIX/VIX3M Term-Structure Regime Switch across SVXY / VXZ / VIXY / BIL (2011-2026 TR, incl. Feb 2018 Volmageddon).
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
OUT_JSON = ROOT / "research" / "artifacts" / "exp0044_fed_liquidity_credit_and_svxy_switch.json"


def perf_ex(tot: np.ndarray, rf: np.ndarray, scale: float = 252.0) -> dict:
    tot = tot[np.isfinite(tot)]
    rf = rf[: len(tot)]
    if len(tot) < 60:
        return {"sharpe": 0.0, "cagr_pct": 0.0, "maxdd_pct": 0.0, "calmar": 0.0}
    ex = tot - rf
    sd = float(np.std(ex, ddof=1))
    shp = float(np.mean(ex) / sd * math.sqrt(scale)) if sd > 0 else 0.0
    eq = np.cumprod(1.0 + tot)
    cagr = (float(eq[-1]) ** (scale / len(tot)) - 1.0) * 100.0 if eq[-1] > 0 else -100.0
    mdd = float(np.min(eq / np.maximum.accumulate(eq) - 1.0)) * 100.0
    return {"sharpe": round(shp, 3), "cagr_pct": round(cagr, 2), "maxdd_pct": round(mdd, 2), "calmar": round(cagr / max(abs(mdd), 1e-3), 3)}


def shift_pct(w: np.ndarray, r_ex: np.ndarray, cbps: float, ref: float, rng: np.random.Generator, scale: float = 252.0, n: int = 200) -> float:
    null = []
    for _ in range(n):
        s = int(rng.integers(20, len(w) - 20))
        ws = np.roll(w, s)
        to = np.abs(np.diff(ws, prepend=0.0))
        ex = ws * r_ex - to * (cbps / 10000.0)
        sd = float(np.std(ex, ddof=1))
        null.append(float(np.mean(ex) / sd * math.sqrt(scale)) if sd > 0 else 0.0)
    return round(float(np.mean(np.array(null) <= ref) * 100.0), 1)


def load_broad_tr(sym: str) -> pd.Series:
    df = pd.read_csv(ROOT / "data" / "broad" / f"{sym}.csv")
    df["date"] = pd.to_datetime(df["date"])
    return pd.to_numeric(df.drop_duplicates("date").set_index("date")["adjclose"], errors="coerce").sort_index()


def main() -> None:
    rng = np.random.default_rng(42)
    liq = pd.read_csv(ROOT / "data" / "macro" / "fred_liquidity_credit.csv")
    liq["date"] = pd.to_datetime(liq["date"])
    liq = liq.drop_duplicates("date").set_index("date").sort_index()

    spy = pd.read_csv(ROOT / "data" / "etfs_tiingo" / "SPY.csv")
    spy["date"] = pd.to_datetime(spy["date"])
    spy = spy.drop_duplicates("date").set_index("date").sort_index()["adjclose"]

    bil = pd.read_csv(ROOT / "data" / "etfs_tiingo" / "BIL.csv")
    bil["date"] = pd.to_datetime(bil["date"])
    bil = bil.drop_duplicates("date").set_index("date").sort_index()["adjclose"]

    btc = pd.read_csv(ROOT / "data" / "universe" / "BTC.csv")
    btc["date"] = pd.to_datetime(btc["date"])
    btc = btc.drop_duplicates("date").set_index("date").sort_index()["close"]

    # --- PART 1: NET LIQUIDITY & HY OAS TIMING ON SPY (2008-2026) & BTC (2015-2026) ---
    idx_s = spy.loc["2008-01-01":].index.intersection(bil.index)
    r_spy = spy.pct_change().reindex(idx_s).fillna(0.0)
    r_bil = bil.pct_change().reindex(idx_s).fillna(0.0)
    nl_s = liq["net_liquidity_bn"].reindex(idx_s).ffill()
    hy_s = liq["BAMLH0A0HYM2"].reindex(idx_s).ffill()

    nl_chg63 = nl_s.diff(63)
    hy_z252 = (hy_s - hy_s.rolling(252).mean()) / hy_s.rolling(252).std()
    hy_chg21 = hy_s.diff(21)

    spy_timing = {}
    is_s = idx_s < pd.Timestamp("2017-01-01")
    oos_s = idx_s >= pd.Timestamp("2017-01-01")
    for name, w_ser in [
        ("SPY_BuyHold", pd.Series(1.0, index=idx_s)),
        ("SPY_if_NetLiq63_Pos_else_BIL", (nl_chg63 > 0).astype(float).shift(1)),
        ("SPY_if_HY_OAS_NotWidening_else_BIL", (hy_chg21 < 0.25).astype(float).shift(1)),
        ("SPY_if_NetLiq_OR_HY_Calm_else_BIL", ((nl_chg63 > 0) | (hy_z252 < 1.0)).astype(float).shift(1)),
    ]:
        w = w_ser.fillna(0.0).to_numpy()
        to = np.abs(np.diff(w, prepend=0.0))
        tot = w * r_spy.to_numpy() + (1.0 - w) * r_bil.to_numpy() - to * 5e-4
        m_oos = perf_ex(tot[oos_s], r_bil.to_numpy()[oos_s])
        p_sh = None if name == "SPY_BuyHold" else shift_pct(w[oos_s], (r_spy - r_bil).to_numpy()[oos_s], 5.0, m_oos["sharpe"], rng)
        spy_timing[name] = {"is_08_16": perf_ex(tot[is_s], r_bil.to_numpy()[is_s]), "oos_17_26": m_oos, "all": perf_ex(tot, r_bil.to_numpy()), "shift_oos_pct": p_sh}

    # BTC 2015-2026 vs Net Liquidity
    cb = pd.read_csv(ROOT / "data" / "macro" / "central_bank_rates_daily.csv")
    cb["date"] = pd.to_datetime(cb["date"])
    cb = cb.drop_duplicates("date").set_index("date").sort_index()
    idx_b = btc.loc["2015-06-01":].index
    r_btc = btc.pct_change().reindex(idx_b).fillna(0.0)
    rf_btc = (cb["effr"].reindex(idx_b).ffill().fillna(0.0) / 100.0 / 365.0).fillna(0.0)
    nl_b = liq["net_liquidity_bn"].reindex(idx_b).ffill()
    hy_b = liq["BAMLH0A0HYM2"].reindex(idx_b).ffill()
    is_b, oos_b = idx_b < pd.Timestamp("2021-01-01"), idx_b >= pd.Timestamp("2021-01-01")
    btc_timing = {}
    for name, w_ser in [
        ("BTC_BuyHold", pd.Series(1.0, index=idx_b)),
        ("BTC_if_NetLiq90d_Pos_else_Cash", (nl_b.diff(90) > 0).astype(float).shift(1)),
        ("BTC_if_HY_Calm_else_Cash", (hy_b.diff(30) < 0.25).astype(float).shift(1)),
    ]:
        w = w_ser.fillna(0.0).to_numpy()
        to = np.abs(np.diff(w, prepend=0.0))
        tot = w * r_btc.to_numpy() + (1.0 - w) * rf_btc.to_numpy() - to * 10e-4
        m_oos = perf_ex(tot[oos_b], rf_btc.to_numpy()[oos_b], 365.0)
        p_sh = None if name == "BTC_BuyHold" else shift_pct(w[oos_b], (r_btc - rf_btc).to_numpy()[oos_b], 10.0, m_oos["sharpe"], rng, 365.0)
        btc_timing[name] = {"is_15_20": perf_ex(tot[is_b], rf_btc.to_numpy()[is_b], 365.0), "oos_21_26": m_oos, "all": perf_ex(tot, rf_btc.to_numpy(), 365.0), "shift_oos_pct": p_sh}

    # --- PART 2: FULL 23-FEATURE RISK META vs +4 NET-LIQ/CREDIT FEATURES (WF 2014-2026) ---
    from scripts.risk_radar import _rolling_z
    spy_u = pd.read_csv(ROOT / "data" / "universe" / "SPY.csv")
    spy_u["date"] = pd.to_datetime(spy_u["date"])
    spy_u = spy_u.drop_duplicates("date").set_index("date").sort_index()
    vol = pd.read_csv(ROOT / "data" / "collect" / "vol_stress_features.csv")
    vol["date"] = pd.to_datetime(vol["date"])
    vol = vol.drop_duplicates("date").set_index("date").sort_index()
    fsi = pd.read_csv(ROOT / "data" / "collect" / "ofr_fsi.csv")
    fsi["date"] = pd.to_datetime(fsi["Date"])
    fsi = fsi.drop_duplicates("date").set_index("date").sort_index()
    gpr = pd.read_csv(ROOT / "data" / "collect" / "gpr_monthly.csv")
    gpr["date"] = pd.to_datetime(gpr["month"]) + pd.offsets.MonthEnd(1) + pd.Timedelta(days=2)
    gpr = gpr.dropna(subset=["date", "gpr"]).drop_duplicates("date").set_index("date")[["gpr"]].sort_index()
    cot = pd.read_csv(ROOT / "data" / "cot" / "cot_features.csv")
    cot["date"] = pd.to_datetime(cot["available_from"])
    ev = pd.read_csv(ROOT / "data" / "events" / "event_calendar_full.csv")
    ev["date"] = pd.to_datetime(ev["date"], errors="coerce")
    fomc_dates = pd.DatetimeIndex(sorted(ev[ev["event"] == "FOMC"]["date"].dropna().unique()))

    idx_m = spy_u.loc["2011-05-02":].index
    df = pd.DataFrame(index=idx_m)
    c_s, l_s = spy_u["close"].reindex(idx_m), spy_u["low"].reindex(idx_m)
    r1 = c_s.pct_change()
    fed = cb["fed_rate_proxy"].reindex(idx_m).ffill().fillna(0.0)
    ofr_raw = fsi["OFR FSI"].reindex(idx_m).ffill()
    df["ofr_fsi_z252"] = _rolling_z(ofr_raw, 252)
    df["ofr_fsi_chg21"] = ofr_raw.diff(21)
    df["ofr_credit_z252"] = _rolling_z(fsi["Credit"].reindex(idx_m).ffill(), 252)
    df["ofr_funding_z252"] = _rolling_z(fsi["Funding"].reindex(idx_m).ffill(), 252)
    df["d_fed_63"] = fed.diff(63)
    df["d_diff_fed_ecb_21"] = cb["diff_fed_ecb_dfr"].reindex(idx_m).ffill().diff(21)
    df["d_diff_boe_ecb_21"] = cb["diff_boe_ecb_dfr"].reindex(idx_m).ffill().diff(21)
    df["gpr_z252"] = _rolling_z(gpr["gpr"].reindex(idx_m, method="ffill"), 252)
    for inst, col in [("SP500", "cot_sp500_z"), ("VIX", "cot_vix_z"), ("UST_10Y", "cot_ust10y_z"), ("EURUSD", "cot_eur_z")]:
        sub_c = cot[cot["instrument"] == inst].set_index("date")[["noncomm_net_pct_oi_z156"]].sort_index()
        sub_c = sub_c[~sub_c.index.duplicated(keep="last")]
        df[col] = sub_c["noncomm_net_pct_oi_z156"].reindex(idx_m, method="ffill").fillna(0.0)
    fomc_ns = fomc_dates.asi8
    idx_ns = idx_m.asi8
    pos = np.searchsorted(fomc_ns, idx_ns, side="left")
    df["fomc_within_5d"] = (np.where(pos < len(fomc_ns), (fomc_ns[np.minimum(pos, len(fomc_ns) - 1)] - idx_ns) / 86400e9, 30.0) <= 5.0).astype(float)
    df["vix"] = vol["vix"].reindex(idx_m).ffill()
    df["slope_3m"] = vol["slope_3m"].reindex(idx_m).ffill()
    df["slope_9d"] = vol["slope_9d"].reindex(idx_m).ffill()
    df["vvix_pct"] = vol["vvix_pct"].reindex(idx_m).ffill()
    df["skew"] = vol["skew"].reindex(idx_m).ffill()
    df["vix_chg21"] = df["vix"].diff(21)
    df["rv5_past"] = r1.rolling(5).std() * math.sqrt(252.0)
    df["rv21_past"] = r1.rolling(21).std() * math.sqrt(252.0)
    df["rv63_past"] = r1.rolling(63).std() * math.sqrt(252.0)
    df["rv_ratio_5_21"] = df["rv5_past"] / df["rv21_past"].replace(0, np.nan)

    # New liquidity + inflation breakeven + yield curve features (ALL full 2003-2026 history, 0 NaNs post-2011!)
    fr = pd.read_csv(ROOT / "data" / "macro" / "fred_rates_full.csv")
    fr["date"] = pd.to_datetime(fr["date"])
    fr = fr.drop_duplicates("date").set_index("date").sort_index()
    nl_m = liq["net_liquidity_bn"].reindex(idx_m).ffill()
    t10yie_m = liq["T10YIE"].reindex(idx_m).ffill().shift(1)
    yc10_2_m = (pd.to_numeric(fr["dgs10"], errors="coerce") - pd.to_numeric(fr["dgs2"], errors="coerce")).reindex(idx_m).ffill().shift(1)
    df["net_liq_chg21"] = nl_m.diff(21)
    df["net_liq_z252"] = _rolling_z(nl_m, 252)
    df["t10yie_chg21"] = t10yie_m.diff(21)
    df["yc10_2_chg21"] = yc10_2_m.diff(21)

    H, PG = 21, 31
    ra, la, ca, rva = r1.to_numpy(), l_s.to_numpy(), c_s.to_numpy(), df["rv21_past"].to_numpy()
    y_on, y_ts = np.full(len(df), np.nan), np.full(len(df), np.nan)
    for i in range(len(df) - H):
        if np.isfinite(rva[i]) and ca[i] > 0:
            rv_f = float(np.std(ra[i + 1 : i + 1 + H], ddof=1) * math.sqrt(252.0))
            ml = float(np.min(la[i + 1 : i + 1 + H]) / ca[i] - 1.0)
            y_on[i] = 1.0 if rv_f > 1.35 * rva[i] else 0.0
            y_ts[i] = 1.0 if (rv_f > 0.20 or ml <= -0.05) else 0.0
    df["y_on"], df["y_ts"] = y_on, y_ts
    feats23 = [
        "ofr_fsi_z252", "ofr_fsi_chg21", "ofr_credit_z252", "ofr_funding_z252", "d_fed_63",
        "d_diff_fed_ecb_21", "d_diff_boe_ecb_21", "gpr_z252", "cot_sp500_z", "cot_vix_z",
        "cot_ust10y_z", "cot_eur_z", "fomc_within_5d", "vix", "slope_3m", "slope_9d",
        "vvix_pct", "skew", "vix_chg21", "rv5_past", "rv21_past", "rv63_past", "rv_ratio_5_21",
    ]
    feats25 = feats23 + ["net_liq_chg21", "net_liq_z252"]
    feats27 = feats25 + ["t10yie_chg21", "yc10_2_chg21"]
    dw = df.dropna(subset=feats27 + ["y_on", "y_ts"])
    wf_auc = {"sample": f"{dw.index[0].strftime('%Y-%m-%d')}..{dw.index[-1].strftime('%Y-%m-%d')}", "n_rows": int(len(dw))}
    for tgt in ("y_on", "y_ts"):
        wf_auc[tgt] = {}
        for lbl, fc in [("Base23", feats23), ("Plus2_NetLiq", feats25), ("Plus4_NetLiq_T10YIE_Curve", feats27)]:
            X, y = dw[fc].to_numpy(), dw[tgt].to_numpy(int)
            preds, ys = [], []
            for t0 in range(600, len(dw), 21):
                te = t0 - PG
                m = HistGradientBoostingClassifier(max_depth=2, max_iter=60, min_samples_leaf=50, l2_regularization=5.0, random_state=42).fit(X[:te], y[:te])
                t1 = min(t0 + 21, len(dw))
                preds.extend(m.predict_proba(X[t0:t1])[:, 1])
                ys.extend(y[t0:t1])
            wf_auc[tgt][lbl] = round(float(roc_auc_score(ys, preds)), 4)

    # Also test EXP-0033 VolTarget12% x MetaCash portfolio Sharpe/MaxDD/Calmar on Base23 vs Plus2_NetLiq vs Plus4!
    r_spy_m = spy.pct_change().reindex(dw.index).fillna(0.0).to_numpy()
    r_bil_m = bil.pct_change().reindex(dw.index).fillna(0.0).to_numpy()
    rv21_m = np.clip(dw["rv21_past"].to_numpy(), 0.05, None)
    vt12_w = np.minimum(1.0, 0.12 / rv21_m)
    wf_port = {}
    for lbl, fc in [("Base23", feats23), ("Plus2_NetLiq", feats25), ("Plus4_NetLiq_T10YIE_Curve", feats27)]:
        X_on, y_on_a = dw[fc].to_numpy(), dw["y_on"].to_numpy(int)
        X_ts, y_ts_a = dw[fc].to_numpy(), dw["y_ts"].to_numpy(int)
        w_p = np.zeros(len(dw))
        for t0 in range(600, len(dw), 21):
            te = t0 - PG
            m1 = HistGradientBoostingClassifier(max_depth=2, max_iter=60, min_samples_leaf=50, l2_regularization=5.0, random_state=42).fit(X_on[:te], y_on_a[:te])
            m2 = HistGradientBoostingClassifier(max_depth=2, max_iter=60, min_samples_leaf=50, l2_regularization=5.0, random_state=42).fit(X_ts[:te], y_ts_a[:te])
            t1 = min(t0 + 21, len(dw))
            p1 = m1.predict_proba(X_on[t0:t1])[:, 1]
            p2 = m2.predict_proba(X_ts[t0:t1])[:, 1]
            risk = np.clip(1.0 - 0.50 * p2 - 0.25 * p1, 0.20, 1.0)
            w_p[t0:t1] = vt12_w[t0:t1] * risk
        w_exec = np.roll(w_p, 1); w_exec[0] = 0.0
        sl = slice(601, len(dw))
        we = w_exec[sl]
        to = np.abs(np.diff(we, prepend=0.0))
        tot = we * r_spy_m[sl] + (1.0 - we) * r_bil_m[sl] - to * 5e-4
        wf_port[lbl] = perf_ex(tot, r_bil_m[sl])
    wf_auc["vt12_meta_cash_portfolio"] = wf_port

    # --- PART 3: VIX TERM-STRUCTURE ETP SWITCH (SVXY / VXZ / BIL, 2012-2026 incl. Volmageddon Feb 2018!) ---
    svxy = load_broad_tr("SVXY")
    vxz = load_broad_tr("VXZ")
    idx_v = svxy.index.intersection(vxz.index).intersection(bil.index).intersection(vol.index)
    idx_v = idx_v[idx_v >= pd.Timestamp("2012-01-01")]
    px_v = pd.DataFrame({"SVXY": svxy, "VXZ": vxz, "BIL": bil, "SPY": spy}).reindex(idx_v).dropna()
    ret_v = px_v.pct_change().fillna(0.0)
    slope = vol["slope_3m"].reindex(px_v.index).ffill()
    idx_vv = px_v.index
    is_v, oos_v = idx_vv < pd.Timestamp("2019-01-01"), idx_vv >= pd.Timestamp("2019-01-01")
    rv_svxy = (ret_v["SVXY"].rolling(21).std() * math.sqrt(252.0)).clip(lower=0.15)

    vix_res = {}
    # Strategies (strict t-1 causal lag, 10bp turnover)
    w_svxy_bh = np.column_stack([np.ones(len(idx_vv)), np.zeros(len(idx_vv)), np.zeros(len(idx_vv))])
    sig_cont = (slope < 0.90).shift(1).fillna(False).to_numpy()
    sig_back = (slope > 1.00).shift(1).fillna(False).to_numpy()
    w_sw_bil = np.column_stack([sig_cont.astype(float), np.zeros(len(idx_vv)), (~sig_cont).astype(float)])
    w_sw_vxz = np.column_stack([sig_cont.astype(float), sig_back.astype(float), (~(sig_cont | sig_back)).astype(float)])
    vt_scale = np.minimum(1.0, 0.15 / rv_svxy).shift(1).fillna(0.0).to_numpy()
    w_sw_vt = np.column_stack([sig_cont.astype(float) * vt_scale, np.zeros(len(idx_vv)), 1.0 - sig_cont.astype(float) * vt_scale])

    rm_v = ret_v[["SVXY", "VXZ", "BIL"]].to_numpy()
    rb_v = ret_v["BIL"].to_numpy()
    for name, wmat in [
        ("SVXY_BuyHold", w_svxy_bh),
        ("Switch_SVXY_lt090_else_BIL", w_sw_bil),
        ("Switch_SVXY_lt090_VXZ_gt100_else_BIL", w_sw_vxz),
        ("Switch_SVXY_lt090_VT15_else_BIL", w_sw_vt),
    ]:
        to = np.sum(np.abs(np.diff(wmat, axis=0, prepend=0.0)), axis=1)
        tot = np.sum(wmat * rm_v, axis=1) - to * 10e-4
        m_oos = perf_ex(tot[oos_v], rb_v[oos_v])
        p_sh = None
        if name != "SVXY_BuyHold":
            # circular shift on SVXY timing
            r_ex_m = (ret_v["SVXY"] - ret_v["BIL"]).to_numpy()[oos_v]
            w_s = wmat[oos_v, 0]
            p_sh = shift_pct(w_s, r_ex_m, 10.0, m_oos["sharpe"], rng)
        vix_res[name] = {
            "is_12_18_incl_volmageddon": perf_ex(tot[is_v], rb_v[is_v]),
            "oos_19_26": m_oos,
            "all": perf_ex(tot, rb_v),
            "shift_oos_pct": p_sh,
        }

    out = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "EXP-0044",
        "spy_net_liquidity_hy_timing": spy_timing,
        "btc_net_liquidity_hy_timing": btc_timing,
        "risk_meta_23f_vs_27f_netliq_hy_auc": wf_auc,
        "vix_etp_term_switch_2012_2026": vix_res,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, indent=2))

    print("=== EXP-0044 (1) FED NET LIQUIDITY & HY OAS TIMING ===")
    for k, v in spy_timing.items():
        print(f"  {k:38s}: IS={v['is_08_16']['sharpe']:+.3f} OOS={v['oos_17_26']['sharpe']:+.3f}({v['shift_oos_pct']}%) All={v['all']['sharpe']:+.3f} DD={v['all']['maxdd_pct']:+.1f}%")
    for k, v in btc_timing.items():
        print(f"  {k:38s}: IS={v['is_15_20']['sharpe']:+.3f} OOS={v['oos_21_26']['sharpe']:+.3f}({v['shift_oos_pct']}%) All={v['all']['sharpe']:+.3f} DD={v['all']['maxdd_pct']:+.1f}%")
    print("\n=== EXP-0044 (2) 23f RISK META vs +4 NET-LIQ/HY WF AUC (2014-2026) ===")
    print(" ", wf_auc)
    print("\n=== EXP-0044 (3) VIX TERM-STRUCTURE ETP SWITCH (2012-2026 INCL. VOLMAGEDDON) ===")
    for k, v in vix_res.items():
        print(f"  {k:38s}: IS={v['is_12_18_incl_volmageddon']['sharpe']:+.3f}(DD={v['is_12_18_incl_volmageddon']['maxdd_pct']:+.1f}%) OOS={v['oos_19_26']['sharpe']:+.3f}({v['shift_oos_pct']}%) All={v['all']['sharpe']:+.3f} DD={v['all']['maxdd_pct']:+.1f}%")


if __name__ == "__main__":
    main()
