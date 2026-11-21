#!/usr/bin/env python3
"""
EXP-0042 — Overnight (Close->Open) vs Intraday (Open->Close) Drift & Execution Cost Wall (2000-2026)
Tests 26.8 years of daily SPY/QQQ/IWM/TLT/GLD split-adjusted Open vs Close to settle whether
the famous Overnight Equity Anomaly survives realistic MOC/MOO daily turnover costs (0/2/5/10 bp/side).
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TIINGO = ROOT / "data" / "etfs_tiingo"
OUT_JSON = ROOT / "research" / "artifacts" / "exp0042_overnight_vs_intraday_cost_wall.json"


def perf(r: np.ndarray) -> dict:
    r = r[np.isfinite(r)]
    if len(r) < 30:
        return {"sharpe": 0.0, "cagr_pct": 0.0, "maxdd_pct": 0.0}
    sd = float(np.std(r, ddof=1))
    shp = float(np.mean(r) / sd * math.sqrt(252.0)) if sd > 0 else 0.0
    eq = np.cumprod(1.0 + r)
    cagr = (float(eq[-1]) ** (252.0 / len(r)) - 1.0) * 100.0 if eq[-1] > 0 else -100.0
    mdd = float(np.min(eq / np.maximum.accumulate(eq) - 1.0)) * 100.0
    return {"sharpe": round(shp, 3), "cagr_pct": round(cagr, 2), "maxdd_pct": round(mdd, 2)}


def main() -> None:
    res = {}
    for sym in ("SPY", "QQQ", "IWM", "TLT", "GLD"):
        df = pd.read_csv(TIINGO / f"{sym}.csv")
        df["date"] = pd.to_datetime(df["date"])
        df = df.drop_duplicates("date").set_index("date").sort_index()
        # Scale open using adjClose/close adjustment factor (captures splits + dividends accurately)
        adj_fac = pd.to_numeric(df["adjclose"], errors="coerce") / pd.to_numeric(df["close"], errors="coerce")
        adj_c = pd.to_numeric(df["adjclose"], errors="coerce")
        adj_o = pd.to_numeric(df["open"], errors="coerce") * adj_fac
        r_on = (adj_o / adj_c.shift(1) - 1.0).dropna()
        r_id = (adj_c / adj_o - 1.0).reindex(r_on.index).dropna()
        r_cc = adj_c.pct_change().reindex(r_on.index).dropna()
        idx = r_on.index.intersection(r_id.index).intersection(r_cc.index)
        on = r_on.reindex(idx).to_numpy()
        id_ = r_id.reindex(idx).to_numpy()
        cc = r_cc.reindex(idx).to_numpy()

        # Daily round-trip = 2 trades per day (enter close, exit open) -> 2 * cost_bps per day
        res[sym] = {
            "days": int(len(idx)),
            "start": idx[0].strftime("%Y-%m-%d"),
            "BuyHold_0bp": perf(cc),
            "Intraday_0bp": perf(id_),
            "Overnight_0bp": perf(on),
            "Overnight_2bp_side": perf(on - 2.0 * 2e-4),
            "Overnight_5bp_side": perf(on - 2.0 * 5e-4),
            "Overnight_10bp_side": perf(on - 2.0 * 10e-4),
            "Overnight_Gross_Ann_Ret_pct": round(float(np.mean(on) * 252.0 * 100.0), 2),
            "Breakeven_bps_per_side": round(float(np.mean(on) * 10000.0 / 2.0), 2),
        }

    out = {"generated_utc": datetime.now(timezone.utc).isoformat(), "experiment": "EXP-0042", "results": res}
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print("=== EXP-0042 OVERNIGHT VS INTRADAY & COST WALL (2000-2026 TR) ===")
    for s, v in res.items():
        print(f"  {s:4s} ({v['start']}): BH={v['BuyHold_0bp']['sharpe']:+.3f}({v['BuyHold_0bp']['cagr_pct']:+.1f}%) | ID_0bp={v['Intraday_0bp']['sharpe']:+.3f} | ON_0bp={v['Overnight_0bp']['sharpe']:+.3f}({v['Overnight_0bp']['cagr_pct']:+.1f}%) BE={v['Breakeven_bps_per_side']:.2f}bp/side | ON_2bp={v['Overnight_2bp_side']['sharpe']:+.3f} | ON_5bp={v['Overnight_5bp_side']['sharpe']:+.3f}")


if __name__ == "__main__":
    main()
