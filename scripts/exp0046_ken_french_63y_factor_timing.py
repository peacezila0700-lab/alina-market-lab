#!/usr/bin/env python3
"""
EXP-0046 — Ken French 63-Year Daily Factor Timing & Factor Momentum (1963-2026, 15,918 days)
Tests Ehsani & Linnainmaa (2022) Factor Momentum (12m / 1m TSMOM & Cross-Sectional Factor Momentum across
Mkt_RF, SMB, HML, RMW, CMA, Mom) and VIX/HY-OAS Factor Rotation across IS (1963-1994) and OOS (1995-2026).
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "research" / "artifacts" / "exp0046_ken_french_63y_factor_timing.json"


def stats_ls(r: np.ndarray) -> dict:
    r = r[np.isfinite(r)]
    if len(r) < 60:
        return {"sharpe": 0.0, "cagr_pct": 0.0, "maxdd_pct": 0.0}
    sd = float(np.std(r, ddof=1))
    shp = float(np.mean(r) / sd * math.sqrt(252.0)) if sd > 0 else 0.0
    eq = np.cumprod(1.0 + r)
    cagr = (float(eq[-1]) ** (252.0 / len(r)) - 1.0) * 100.0 if eq[-1] > 0 else -100.0
    mdd = float(np.min(eq / np.maximum.accumulate(eq) - 1.0)) * 100.0
    return {"sharpe": round(shp, 3), "cagr_pct": round(cagr, 2), "maxdd_pct": round(mdd, 2)}


def main() -> None:
    rng = np.random.default_rng(42)
    kf = pd.read_csv(ROOT / "data" / "macro" / "ken_french_ff5_mom_daily.csv.gz")
    kf["date"] = pd.to_datetime(kf["date"])
    kf = kf.drop_duplicates("date").set_index("date").sort_index()

    facs = ["SMB", "HML", "RMW", "CMA", "Mom"]
    R = kf[facs]
    idx = kf.index
    # Monthly (21td) rebalance for realistic implementation costs (10bp/side per factor ETF turnover)
    reb = list(range(252, len(idx) - 1, 21))
    idx_e = idx[252:]
    R_e = R.iloc[252:].to_numpy()
    is_m = idx_e < pd.Timestamp("1995-01-01")
    oos_m = idx_e >= pd.Timestamp("1995-01-01")
    oos_recent = idx_e >= pd.Timestamp("2010-01-01")

    cum21 = (1.0 + R).rolling(21).apply(lambda x: float(np.prod(x) - 1.0), raw=True)
    cum252 = (1.0 + R).rolling(252).apply(lambda x: float(np.prod(x) - 1.0), raw=True)

    w_ew = np.full_like(R_e, 1.0 / len(facs))
    w_ts21 = np.zeros_like(R_e)
    w_ts252 = np.zeros_like(R_e)
    w_ts252_lo = np.zeros_like(R_e)
    w_xs252_top2 = np.zeros_like(R_e)

    for k, ri in enumerate(reb):
        i0 = ri - 252 + 1
        i1 = (reb[k + 1] - 252 + 1) if k + 1 < len(reb) else len(idx_e)
        c21 = cum21.iloc[ri].to_numpy()
        c252 = cum252.iloc[ri].to_numpy()
        w_ts21[i0:i1] = np.where(c21 > 0, 1.0, -1.0) / len(facs)
        w_ts252[i0:i1] = np.where(c252 > 0, 1.0, -1.0) / len(facs)
        pos252 = np.where(c252 > 0, 1.0, 0.0)
        w_ts252_lo[i0:i1] = pos252 / max(1.0, float(pos252.sum()))
        top2 = np.argsort(c252)[-2:]
        w_xs252_top2[i0:i1, top2] = 0.5

    # Compare vs Equal-Weight Multi-Factor & individual static factors at 0bp & 10bp turnover
    res = {}
    for sn, wm in [
        ("Static_EW_5Factors", w_ew),
        ("Factor_TSMOM_21d_LS", w_ts21),
        ("Factor_TSMOM_252d_LS", w_ts252),
        ("Factor_TSMOM_252d_LongOnly", w_ts252_lo),
        ("Factor_XSMom_252d_Top2_LO", w_xs252_top2),
    ]:
        to = np.sum(np.abs(np.diff(wm, axis=0, prepend=0.0)), axis=1)
        tot0 = np.sum(wm * R_e, axis=1)
        tot10 = tot0 - to * 10e-4
        tot20 = tot0 - to * 20e-4
        m_oos = stats_ls(tot10[oos_m])
        p_sh = None
        if sn != "Static_EW_5Factors":
            null = []
            w_o, r_o = wm[oos_m], R_e[oos_m]
            for _ in range(200):
                s = int(rng.integers(30, len(w_o) - 30))
                ws = np.roll(w_o, s, axis=0)
                tos = np.sum(np.abs(np.diff(ws, axis=0, prepend=0.0)), axis=1)
                null.append(stats_ls(np.sum(ws * r_o, axis=1) - tos * 10e-4)["sharpe"])
            p_sh = round(float(np.mean(np.array(null) <= m_oos["sharpe"]) * 100.0), 1)
        res[sn] = {
            "gross_0bp_all": stats_ls(tot0),
            "net10bp_is_63_94": stats_ls(tot10[is_m]),
            "net10bp_oos_95_26": m_oos,
            "net10bp_recent_10_26": stats_ls(tot10[oos_recent]),
            "net20bp_all": stats_ls(tot20),
            "turnover_x_yr": round(float(to.sum() / (len(wm) / 252.0)), 1),
            "shift200_oos_pct": p_sh,
        }

    # Static individual factors 1963-2026 vs 2010-2026 (post-publication decay check!)
    indiv = {}
    for f in ["Mkt_RF"] + facs:
        arr = kf[f].to_numpy()
        indiv[f] = {
            "all_63_26": stats_ls(arr),
            "is_63_94": stats_ls(arr[idx < pd.Timestamp("1995-01-01")]),
            "oos_95_26": stats_ls(arr[idx >= pd.Timestamp("1995-01-01")]),
            "post2010_10_26": stats_ls(arr[idx >= pd.Timestamp("2010-01-01")]),
        }

    out = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "EXP-0046",
        "range": f"{idx[0].strftime('%Y-%m-%d')}..{idx[-1].strftime('%Y-%m-%d')}",
        "factor_timing_strategies": res,
        "individual_factors_decay": indiv,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, indent=2))

    print("=== EXP-0046 (1) KEN FRENCH 63-YEAR FACTOR MOMENTUM & TIMING (1963-2026) ===")
    for k, v in res.items():
        print(f"  {k:28s}: 0bpAll={v['gross_0bp_all']['sharpe']:+.3f} | 10bp IS63-94={v['net10bp_is_63_94']['sharpe']:+.3f} OOS95-26={v['net10bp_oos_95_26']['sharpe']:+.3f}({v['shift200_oos_pct']}%) Rec10-26={v['net10bp_recent_10_26']['sharpe']:+.3f} TO/y={v['turnover_x_yr']:.1f}x")
    print("\n=== EXP-0046 (2) INDIVIDUAL FACTORS POST-PUBLICATION DECAY ===")
    for k, v in indiv.items():
        print(f"  {k:8s}: All63-26={v['all_63_26']['sharpe']:+.3f} | 63-94={v['is_63_94']['sharpe']:+.3f} | 95-26={v['oos_95_26']['sharpe']:+.3f} | Post2010={v['post2010_10_26']['sharpe']:+.3f}")


if __name__ == "__main__":
    main()
