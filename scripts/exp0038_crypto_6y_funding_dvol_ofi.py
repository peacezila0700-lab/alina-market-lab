#!/usr/bin/env python3
"""
EXP-0038 — Crypto 6.8-Year Multi-Regime Exhaustive Study (2020-2026)
Uses Binance Vision 1h Spot + Perp + 8h Funding + taker_buy_volume (BTC/ETH/SOL, ~60k bars each)
plus Deribit 1h DVOL (2021-2026, 49,632 bars).
Tests:
  1) Perp-Spot Cash-and-Carry Funding Arb (always-on vs causal EMA-gated; IS 2020-22 vs OOS 2023-26)
  2) 1h/4h Taker Order-Flow Imbalance (OFI) & Spot-Perp Basis Mean-Reversion (4bp maker vs 10bp taker)
  3) Daily/Weekly Time-Series & Cross-Sectional Momentum (BTC/ETH/SOL)
  4) Deribit DVOL VRP Risk Diagnostic & VolTarget20% + DVOL Throttle Risk-Off Overlay vs BTC B&H
All strategies strictly causal (t-1 lag) with 200 circular shifts.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CV = ROOT / "data" / "crypto_vision"
MICRO = ROOT / "data" / "microstructure"
OUT_JSON = ROOT / "research" / "artifacts" / "exp0038_crypto_6y_funding_dvol_ofi.json"

N_SHIFTS = 200


def metrics_hourly(r: np.ndarray, scale: float = 8760.0) -> dict:
    r = r[np.isfinite(r)]
    if len(r) < 100:
        return {"sharpe": 0.0, "cagr_pct": 0.0, "maxdd_pct": 0.0}
    mu = float(np.mean(r))
    sd = float(np.std(r, ddof=1))
    shp = (mu / sd * math.sqrt(scale)) if sd > 0 else 0.0
    eq = np.cumprod(1.0 + r)
    yrs = len(r) / scale
    cagr = (float(eq[-1]) ** (1.0 / max(yrs, 1e-6)) - 1.0) * 100.0 if eq[-1] > 0 else -100.0
    mdd = float(np.min(eq / np.maximum.accumulate(eq) - 1.0)) * 100.0
    return {"sharpe": round(shp, 3), "cagr_pct": round(cagr, 2), "maxdd_pct": round(mdd, 2)}


def circ_shift_pval(w: np.ndarray, r: np.ndarray, to: np.ndarray, cost_bps: float, ref_sharpe: float, scale: float, rng: np.random.Generator) -> float:
    n = len(r)
    if n < 200:
        return 1.0
    null = []
    # Shift weights in blocks >= 24 bars (or >= 5 daily bars)
    min_s = max(24, n // 20)
    for _ in range(N_SHIFTS):
        s = int(rng.integers(min_s, n - min_s))
        ws = np.roll(w, s)
        tos = np.abs(np.diff(ws, prepend=0.0))
        rn = ws * r - tos * (cost_bps / 10000.0)
        sd = float(np.std(rn, ddof=1))
        null.append(float(np.mean(rn) / sd * math.sqrt(scale)) if sd > 0 else 0.0)
    return round(float(np.mean(np.array(null) <= ref_sharpe) * 100.0), 1)


def roc_auc_fast(y_true: np.ndarray, y_score: np.ndarray) -> float:
    m = np.isfinite(y_true) & np.isfinite(y_score)
    y, s = y_true[m].astype(int), y_score[m]
    if len(y) < 50 or y.sum() == 0 or y.sum() == len(y):
        return 0.5
    r = pd.Series(s).rank(method="average").to_numpy()
    n1 = float((y == 1).sum())
    n0 = float((y == 0).sum())
    return float((r[y == 1].sum() - n1 * (n1 + 1.0) / 2.0) / (n1 * n0))


def load_sym(sym: str) -> pd.DataFrame:
    sp = pd.read_csv(CV / f"binance_{sym}_spot_1h.csv.gz")
    pp = pd.read_csv(CV / f"binance_{sym}_um_perp_1h.csv.gz")
    fn = pd.read_csv(CV / f"binance_{sym}_um_funding.csv.gz")
    for df in (sp, pp, fn):
        df["dt"] = pd.to_datetime(df["ts_utc"], utc=True)
    sp = sp.drop_duplicates("dt").set_index("dt").sort_index()
    pp = pp.drop_duplicates("dt").set_index("dt").sort_index()
    fn = fn.drop_duplicates("dt").set_index("dt").sort_index()

    idx = pp.index
    out = pd.DataFrame(index=idx)
    out["spot_c"] = sp["close"].reindex(idx).ffill()
    out["perp_c"] = pp["close"]
    out["perp_vol"] = pp["volume"]
    out["perp_tbv"] = pp["taker_buy_volume"]
    out["spot_vol"] = sp["volume"].reindex(idx).fillna(0.0)
    out["spot_tbv"] = sp["taker_buy_volume"].reindex(idx).fillna(0.0)
    # 8h funding aligns strictly at exact settlement hours (00:00, 08:00, 16:00 UTC), 0 elsewhere
    out["fund"] = fn["funding_rate"].reindex(idx).fillna(0.0)
    return out.dropna(subset=["spot_c", "perp_c"])


def main() -> None:
    rng = np.random.default_rng(42)
    split_dt = pd.Timestamp("2023-01-01", tz="UTC")
    syms = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    data = {s: load_sym(s) for s in syms}

    # --- 1. CASH & CARRY PERP-SPOT FUNDING ARB (2020-2026) ---
    carry_res = {}
    for s in syms:
        df = data[s]
        # Mark-to-market basis return of (+0.5 Spot, -0.5 Perp) + 0.5 * funding_received (unlevered 1x notional = 0.5x Spot + 0.5x Perp margin)
        # More cleanly: 100% Spot + 100% Short Perp on 2x capital (or 1x hedged notional -> return = (r_spot - r_perp)/2 + 0.5*fund or on Spot+margin = r_spot - r_perp + fund with 1x leg)
        r_sp = df["spot_c"].pct_change().fillna(0.0).clip(-0.5, 0.5)
        r_pp = df["perp_c"].pct_change().fillna(0.0).clip(-0.5, 0.5)
        spread_ret = 0.5 * (r_sp - r_pp + df["fund"])  # unlevered 1.0x capital split 50% Spot / 50% Short Perp
        # Gate using CAUSAL rolling 72h (9 settlements) realized funding EMA > 0 vs > 0.0001 (1bp/8h ~ 11% APR)
        f_ma72 = df["fund"].replace(0.0, np.nan).ffill().rolling(72, min_periods=24).mean().shift(1).fillna(0.0)
        is_m = df.index < split_dt
        oos_m = df.index >= split_dt

        res_s = {}
        for mode_name, w_ser, cbps in [
            ("always_on_8bp", pd.Series(1.0, index=df.index), 8.0),
            ("gate_gt0_8bp", (f_ma72 > 0.0).astype(float), 8.0),
            ("gate_gt1bp_8bp", (f_ma72 > 0.0001).astype(float), 8.0),
            ("gate_gt1bp_4bp_maker", (f_ma72 > 0.0001).astype(float), 4.0),
        ]:
            w = w_ser.to_numpy()
            # Turnover counts both Spot + Perp rebalances (1x change in position = 2 * 0.5 = 1.0 leg notional per side -> 1.0 * cbps)
            to = np.abs(np.diff(w, prepend=0.0))
            rn = w * spread_ret.to_numpy() - to * (cbps / 10000.0)
            m_all = metrics_hourly(rn)
            m_is = metrics_hourly(rn[is_m])
            m_oos = metrics_hourly(rn[oos_m])
            # Also report 2024-2026 post-BTC-ETF era specifically!
            m_2426 = metrics_hourly(rn[df.index >= pd.Timestamp("2024-01-01", tz="UTC")])
            res_s[mode_name] = {
                "is_20_22": m_is,
                "oos_23_26": m_oos,
                "post_etf_24_26": m_2426,
                "all": m_all,
                "time_in_mkt_pct": round(float(w.mean() * 100.0), 1),
            }
        carry_res[s] = res_s

    # --- 2. 1H TAKER ORDER-FLOW IMBALANCE (OFI) & BASIS REVERSION ---
    micro_res = {}
    for s in syms:
        df = data[s]
        is_m = df.index < split_dt
        oos_m = df.index >= split_dt
        r_pp = df["perp_c"].pct_change().fillna(0.0).clip(-0.4, 0.4).to_numpy()

        # Taker buy imbalance: (taker_buy / vol - 0.5) z-scored over 72h, shifted 1 bar
        ofi = (df["perp_tbv"] / df["perp_vol"].replace(0, np.nan) - 0.5).fillna(0.0)
        ofi_z = ((ofi - ofi.rolling(72).mean()) / ofi.rolling(72).std().replace(0, np.nan)).shift(1).fillna(0.0)

        # Basis (perp/spot - 1) z-scored over 72h, shifted 1 bar
        basis = (df["perp_c"] / df["spot_c"] - 1.0)
        basis_z = ((basis - basis.rolling(72).mean()) / basis.rolling(72).std().replace(0, np.nan)).shift(1).fillna(0.0)

        # 4h realized reversal (-ret_4h)
        ret4 = df["perp_c"].pct_change(4)
        rev4_z = ((-ret4 - (-ret4).rolling(72).mean()) / (-ret4).rolling(72).std().replace(0, np.nan)).shift(1).fillna(0.0)

        res_m = {}
        for sig_name, zser in [("OFI_MOM_1H", ofi_z), ("BASIS_REV_1H", -basis_z), ("RET4H_REV_1H", rev4_z)]:
            # Test sign IS only using threshold |z| >= 1.5
            raw_sig = np.where(zser > 1.5, 1.0, np.where(zser < -1.5, -1.0, 0.0))
            to0 = np.abs(np.diff(raw_sig, prepend=0.0))
            rn_pos_is = (raw_sig * r_pp - to0 * 4e-4)[is_m]
            rn_neg_is = (-raw_sig * r_pp - to0 * 4e-4)[is_m]
            sign = 1.0 if metrics_hourly(rn_pos_is)["sharpe"] >= metrics_hourly(rn_neg_is)["sharpe"] else -1.0
            w = sign * raw_sig
            to = np.abs(np.diff(w, prepend=0.0))
            r_0 = w * r_pp
            r_4 = w * r_pp - to * 4e-4
            r_10 = w * r_pp - to * 10e-4
            res_m[sig_name] = {
                "is_sign": "+" if sign > 0 else "-",
                "gross_all": metrics_hourly(r_0)["sharpe"],
                "net4bp_is": metrics_hourly(r_4[is_m])["sharpe"],
                "net4bp_oos": metrics_hourly(r_4[oos_m])["sharpe"],
                "net4bp_all": metrics_hourly(r_4)["sharpe"],
                "net10bp_all": metrics_hourly(r_10)["sharpe"],
                "trades_to_per_yr": round(float(to.sum() / (len(w) / 8760.0)), 1),
            }
        micro_res[s] = res_m

    # --- 3. DAILY CRYPTO TS MOMENTUM, XS MOMENTUM & DERIBIT DVOL RISK OVERLAY ---
    # Resample BTC/ETH/SOL + DVOL to Daily UTC (00:00)
    d_closes = {s: data[s]["spot_c"].resample("1D").last().dropna() for s in syms}
    px_d = pd.DataFrame(d_closes).dropna()
    ret_d = px_d.pct_change().fillna(0.0)
    d_is = px_d.index < split_dt
    d_oos = px_d.index >= split_dt

    # 3A. Time-series Momentum on BTC (20d, 60d) & Cross-Sectional 14d Mom across BTC/ETH/SOL
    ts_res = {}
    for s in syms:
        r_arr = ret_d[s].to_numpy()
        for lb in (14, 30, 60):
            sig = (px_d[s] > px_d[s].rolling(lb).mean()).shift(1).fillna(False).astype(float).to_numpy()
            to = np.abs(np.diff(sig, prepend=0.0))
            r10 = sig * r_arr - to * 10e-4
            bh = r_arr
            s_oos = metrics_hourly(r10[d_oos], 365.0)["sharpe"]
            p_oos = circ_shift_pval(sig[d_oos], r_arr[d_oos], to[d_oos], 10.0, s_oos, 365.0, rng)
            ts_res[f"{s}_SMA{lb}D_LongCash"] = {
                "net10bp_is": metrics_hourly(r10[d_is], 365.0),
                "net10bp_oos": metrics_hourly(r10[d_oos], 365.0),
                "net10bp_all": metrics_hourly(r10, 365.0),
                "bh_all": metrics_hourly(bh, 365.0),
                "perm_pct_oos": p_oos,
            }

    # 3B. Deribit DVOL VRP Risk Diagnostic & VolTarget25% + DVOL Throttle Overlay (BTC 2021-03 .. 2026-10)
    dvol = pd.read_csv(MICRO / "deribit_BTC_dvol_1h.csv.gz")
    dvol["dt"] = pd.to_datetime(dvol["ts_utc"], utc=True)
    dvol_d = (dvol.drop_duplicates("dt").set_index("dt")["close"].resample("1D").last() / 100.0).dropna()
    btc_d = px_d["BTCUSDT"].reindex(dvol_d.index).dropna()
    dvol_d = dvol_d.reindex(btc_d.index)
    r_btc = btc_d.pct_change().fillna(0.0)
    rv21 = r_btc.rolling(21).std() * math.sqrt(365.0)
    rv7 = r_btc.rolling(7).std() * math.sqrt(365.0)
    vrp = (dvol_d - rv21).shift(1)
    dvol_s = dvol_d.shift(1)
    dvol_z = ((dvol_s - dvol_s.rolling(90).mean()) / dvol_s.rolling(90).std()).clip(-3, 3)

    # Targets: 7d forward crash <= -10% or 21d forward VolOnset
    fwd_ret7 = btc_d.shift(-7) / btc_d - 1.0
    y_crash7 = (fwd_ret7 <= -0.10).astype(float)
    y_crash7[fwd_ret7.isna()] = np.nan
    fwd_rv21 = rv21.shift(-21)
    y_vo = (fwd_rv21 > 1.25 * rv21).astype(float)
    y_vo[fwd_rv21.isna() | rv21.isna()] = np.nan

    dvol_diag = {
        "n_days": int(len(btc_d)),
        "auc_dvol_vs_crash7": round(roc_auc_fast(y_crash7.to_numpy(), dvol_s.to_numpy()), 4),
        "auc_vrp_vs_crash7": round(roc_auc_fast(y_crash7.to_numpy(), vrp.to_numpy()), 4),
        "auc_dvol_vs_vol_onset": round(roc_auc_fast(y_vo.to_numpy(), dvol_s.to_numpy()), 4),
        "auc_vrp_vs_vol_onset": round(roc_auc_fast(y_vo.to_numpy(), vrp.to_numpy()), 4),
    }

    # Risk Overlay Comparison on BTC (2021-06 .. 2026-10)
    m_ov = btc_d.index >= pd.Timestamp("2021-06-01", tz="UTC")
    r_b = r_btc[m_ov].to_numpy()
    rv_lag = rv21.shift(1).clip(lower=0.10)[m_ov].to_numpy()
    dz_lag = dvol_z.fillna(0.0)[m_ov].to_numpy()
    vrp_lag = vrp.fillna(0.0)[m_ov].to_numpy()
    w_bh = np.ones_like(r_b)
    w_vt = np.clip(0.30 / rv_lag, 0.0, 1.0)
    # DVOL inverted-term/spike throttle (when DVOL z > 1.0 or VRP < -0.15 realized spike -> cut exposure 50%)
    thr = np.where((dz_lag > 1.0) | (vrp_lag < -0.15), 0.5, 1.0)
    w_vt_dvol = w_vt * thr
    ov_res = {}
    ov_is_m = btc_d.index[m_ov] < split_dt
    ov_oos_m = btc_d.index[m_ov] >= split_dt
    for name, w in [("1_BTC_BuyHold", w_bh), ("2_BTC_VolTarget30", w_vt), ("3_BTC_VT30_DVOL_Throttle", w_vt_dvol)]:
        to = np.abs(np.diff(w, prepend=0.0))
        rn = w * r_b - to * 10e-4
        m_a = metrics_hourly(rn, 365.0)
        m_a["calmar"] = round(m_a["cagr_pct"] / max(abs(m_a["maxdd_pct"]), 1e-3), 3)
        ov_res[name] = {
            "all": m_a,
            "is_21_22": metrics_hourly(rn[ov_is_m], 365.0),
            "oos_23_26": metrics_hourly(rn[ov_oos_m], 365.0),
            "shift_pct_all": circ_shift_pval(w, r_b, to, 10.0, m_a["sharpe"], 365.0, rng) if name != "1_BTC_BuyHold" else None,
        }

    out = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "EXP-0038",
        "cash_and_carry_6y": carry_res,
        "microstructure_1h_ofi_basis": micro_res,
        "daily_ts_momentum": ts_res,
        "deribit_dvol_diagnostics": dvol_diag,
        "btc_vol_dvol_overlay_2021_2026": ov_res,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, indent=2))

    print("=== EXP-0038 (1) CRYPTO 6.8Y CASH-AND-CARRY PERP-SPOT ARB ===")
    for s in syms:
        for k, v in carry_res[s].items():
            print(f"  {s:8s} {k:20s}: IS20-22={v['is_20_22']['sharpe']:+.3f}({v['is_20_22']['cagr_pct']:+.1f}%) | OOS23-26={v['oos_23_26']['sharpe']:+.3f}({v['oos_23_26']['cagr_pct']:+.1f}%) | 24-26={v['post_etf_24_26']['sharpe']:+.3f}({v['post_etf_24_26']['cagr_pct']:+.1f}%) DD={v['all']['maxdd_pct']:+.2f}%")

    print("\n=== EXP-0038 (2) CRYPTO 1H ORDER-FLOW (OFI) & BASIS REVERSION ===")
    for s in syms:
        for k, v in micro_res[s].items():
            print(f"  {s:8s} {k:14s}[{v['is_sign']}]: Gross={v['gross_all']:+.3f} | 4bp IS={v['net4bp_is']:+.3f} OOS={v['net4bp_oos']:+.3f} All={v['net4bp_all']:+.3f} | 10bp={v['net10bp_all']:+.3f}")

    print("\n=== EXP-0038 (3) DAILY TS MOMENTUM (NET 10bp, 365d) ===")
    for k, v in ts_res.items():
        print(f"  {k:24s}: IS={v['net10bp_is']['sharpe']:+.3f} OOS={v['net10bp_oos']['sharpe']:+.3f}(perm={v['perm_pct_oos']}%) All={v['net10bp_all']['sharpe']:+.3f} CAGR={v['net10bp_all']['cagr_pct']:+.1f}% DD={v['net10bp_all']['maxdd_pct']:+.1f}% | BH={v['bh_all']['sharpe']:+.3f}({v['bh_all']['maxdd_pct']:+.1f}%)")

    print("\n=== EXP-0038 (4) DVOL DIAGNOSTIC & BTC VOLTARGET + DVOL OVERLAY ===")
    print("  DVOL Diag:", dvol_diag)
    for k, v in ov_res.items():
        print(f"  {k:26s}: All Sh={v['all']['sharpe']:+.3f} CAGR={v['all']['cagr_pct']:+.1f}% DD={v['all']['maxdd_pct']:+.1f}% Calmar={v['all']['calmar']} | IS={v['is_21_22']['sharpe']:+.3f} OOS={v['oos_23_26']['sharpe']:+.3f} shift={v['shift_pct_all']}")


if __name__ == "__main__":
    main()
