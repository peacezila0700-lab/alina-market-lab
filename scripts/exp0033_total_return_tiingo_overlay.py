#!/usr/bin/env python3
"""
EXP-0033 — EXP-0031 Cross-Asset Defensive Overlay under Tiingo Total-Return (`adjClose` incl. Dividends)
& Real Tradeable Cash ETF (`BIL`) + Backfilled NYFed EFFR (`FRED DFF`).

Compares Price-Return baseline (`data/universe/`) vs Total-Return (`data/etfs_tiingo/` `adjclose`)
with true geometric CAGR, Day-0 turnover cost, and Act/360 cash yield parity.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "scripts"))
import exp0031_cross_asset_defensive_overlay as e31

OUT_JSON = ROOT / "research" / "artifacts" / "exp0033_total_return_tiingo_overlay.json"


def load_tiingo_adj(sym: str) -> pd.Series:
    df = pd.read_csv(ROOT / "data" / "etfs_tiingo" / f"{sym}.csv")
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    df = df[~df.index.duplicated(keep="last")]
    return pd.to_numeric(df["adjclose"], errors="coerce")


def eval_total_return(
    weights_df: pd.DataFrame,
    rets_df: pd.DataFrame,
    r_cash: pd.Series,
    fed_rate: pd.Series,
    turn_bp: float = 5.0,
    borrow_bp: float = 50.0,
) -> dict:
    cols = ["w_spy", "w_tlt", "w_ief", "w_gold"]
    W = weights_df[cols].fillna(0.0)
    R = rets_df[["r_spy", "r_tlt", "r_ief", "r_gold"]].loc[W.index].fillna(0.0)
    rc = r_cash.loc[W.index].fillna(0.0).to_numpy()
    fv = fed_rate.loc[W.index].fillna(0.0).to_numpy()

    tot_w = W.sum(axis=1).to_numpy()
    cash_w = np.maximum(0.0, 1.0 - tot_w)
    lev_w = np.maximum(0.0, tot_w - 1.0)
    gross_asset = (W.to_numpy() * R.to_numpy()).sum(axis=1)
    cash_ret = cash_w * rc
    borrow_cost = lev_w * ((fv / 100.0 + borrow_bp / 10000.0) / 360.0) * (360.0 / 252.0)

    # Include Day-0 initial entry cost cleanly
    dw = np.abs(np.diff(W.to_numpy(), axis=0, prepend=np.zeros((1, W.shape[1])))).sum(axis=1)
    tx_cost = dw * (turn_bp / 10000.0)

    net = pd.Series(gross_asset + cash_ret - tx_cost - borrow_cost, index=W.index)
    eq = (1.0 + net).cumprod()
    yrs = len(net) / 252.0
    cagr = float(eq.iloc[-1] ** (1.0 / yrs) - 1.0) if yrs > 0 else 0.0
    ar = float(net.mean() * 252)
    av = float(net.std() * math.sqrt(252))
    sh = ar / av if av > 0 else 0.0
    mdd = float((eq / eq.cummax() - 1.0).min())
    cal = cagr / abs(mdd) if mdd < 0 else 0.0
    q5 = float(np.quantile(net, 0.05))
    cvar = float(net[net <= q5].mean())
    return {
        "sharpe": round(sh, 3),
        "cagr_pct": round(cagr * 100, 2),
        "ann_ret_pct": round(ar * 100, 2),
        "ann_vol_pct": round(av * 100, 2),
        "max_dd_pct": round(mdd * 100, 2),
        "calmar_cagr": round(cal, 3),
        "cvar95_bp": round(cvar * 10000, 1),
    }


def main() -> None:
    clean, feats = e31.build_dataset()
    p_onset = e31.fit_predict_purged_wf(clean, feats, "y_vol_onset", purge_gap=31)
    p_stress = e31.fit_predict_purged_wf(clean, feats, "y_tb_stress", purge_gap=31)
    wf_mask = p_onset.notna() & p_stress.notna()
    sub = clean.loc[wf_mask].copy()
    idx = sub.index

    # Replace price-only returns with Tiingo total-return `adjclose` returns!
    rets_tr = pd.DataFrame({
        "r_spy": load_tiingo_adj("SPY").reindex(idx).ffill().pct_change().fillna(0.0),
        "r_tlt": load_tiingo_adj("TLT").reindex(idx).ffill().pct_change().fillna(0.0),
        "r_ief": load_tiingo_adj("IEF").reindex(idx).ffill().pct_change().fillna(0.0),
        "r_gold": load_tiingo_adj("GLD").reindex(idx).ffill().pct_change().fillna(0.0),
    }, index=idx)
    r_bil = load_tiingo_adj("BIL").reindex(idx).ffill().pct_change().fillna(0.0)
    r_effr = (sub["fed_rate"] / 100.0) / 360.0 * (360.0 / 252.0)

    p_on, p_st = p_onset.loc[wf_mask], p_stress.loc[wf_mask]
    zeros = pd.Series(0.0, index=idx)
    vt_raw = (0.12 / sub["rv21_past"].replace(0, np.nan)).clip(0.0, 1.5).shift(1).fillna(1.0)
    throttle = (1.0 - 1.3 * (p_on - 0.25).clip(lower=0.0) - 1.1 * (p_st - 0.30).clip(lower=0.0)).clip(0.35, 1.0).shift(1).fillna(1.0)
    w_spy_meta = vt_raw * throttle
    cut_amt = (1.0 - w_spy_meta).clip(lower=0.0)

    strats = [
        ("1_SPY_Buy_And_Hold", pd.DataFrame({"w_spy": 1.0, "w_tlt": 0.0, "w_ief": 0.0, "w_gold": 0.0}, index=idx)),
        ("2_Static_60_40_SPY_TLT", pd.DataFrame({"w_spy": 0.60, "w_tlt": 0.40, "w_ief": 0.0, "w_gold": 0.0}, index=idx)),
        ("4_VolTarget12_SPY_Cash", pd.DataFrame({"w_spy": vt_raw, "w_tlt": zeros, "w_ief": zeros, "w_gold": zeros}, index=idx)),
        ("5_VolTarget12_Meta_Cash", pd.DataFrame({"w_spy": w_spy_meta, "w_tlt": zeros, "w_ief": zeros, "w_gold": zeros}, index=idx)),
        ("6_VolTarget12_Meta_TLT_Rot", pd.DataFrame({"w_spy": w_spy_meta, "w_tlt": (0.70 * cut_amt).clip(0.0, 0.60), "w_ief": zeros, "w_gold": zeros}, index=idx)),
        ("7_VolTarget12_Meta_Cash_IEF_GLD", pd.DataFrame({"w_spy": w_spy_meta, "w_tlt": zeros, "w_ief": (0.20 * cut_amt).clip(0.0, 0.25), "w_gold": (0.25 * cut_amt).clip(0.0, 0.30)}, index=idx)),
    ]

    res = {}
    print(f"=== EXP-0033 TIINGO TOTAL RETURN (adjClose incl. divs) [{idx[0].date()}..{idx[-1].date()}, n={len(idx)}] ===")
    for nm, wdf in strats:
        st_0 = eval_total_return(wdf, rets_tr, zeros, sub["fed_rate"])
        st_bil = eval_total_return(wdf, rets_tr, r_bil, sub["fed_rate"])
        st_effr = eval_total_return(wdf, rets_tr, r_effr, sub["fed_rate"])
        res[nm] = {"cash_0pct": st_0, "cash_bil_etf": st_bil, "cash_effr": st_effr}
        print(f"  {nm:32s}: TR(0%Cash) Sh={st_0['sharpe']:+.3f} CAGR={st_0['cagr_pct']:+.2f}% DD={st_0['max_dd_pct']:+.2f}% | "
              f"BIL_ETF Sh={st_bil['sharpe']:+.3f} CAGR={st_bil['cagr_pct']:+.2f}% Calmar={st_bil['calmar_cagr']:.3f} | "
              f"EFFR Sh={st_effr['sharpe']:+.3f}")

    OUT_JSON.write_text(json.dumps({
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "EXP-0033",
        "window": f"{idx[0].strftime('%Y-%m-%d')}..{idx[-1].strftime('%Y-%m-%d')} (n={len(idx)})",
        "total_return_results": res,
    }, indent=2))


if __name__ == "__main__":
    main()
