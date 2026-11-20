#!/usr/bin/env python3
"""EXP-0007 — H10 hold-out test. Implements docs/PREREG_H10.md exactly.

Imports the tested P&L machinery from h09_xs_reversion.py rather than re-implementing it
(the QR-002 lesson: never write a second P&L path).

Primary panel: {EURUSD, GBPUSD, EURCHF, EURJPY, EURGBP} — cheapest half of the measured
universe using 2003-2018 spreads ONLY.
Hold-out: 2019-01-01 .. 2026-11-20. Nothing before 2019 is used for P&L.
Rule: k=2 weekly, long bottom 2 / short top 2, dollar-neutral, 1-week hold, lagged positions.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "research", "artifacts")
REP = os.path.join(ROOT, "reports")

spec = importlib.util.spec_from_file_location(
    "h09", os.path.join(ROOT, "scripts", "h09_xs_reversion.py"))
h09 = importlib.util.module_from_spec(spec)
sys.modules["h09"] = h09
spec.loader.exec_module(h09)

PRIMARY = ["EURUSD", "GBPUSD", "EURCHF", "EURJPY", "EURGBP"]
SECONDARY = ["EURUSD", "EURJPY", "EURGBP", "EURCHF", "EURCAD",
             "EURSEK", "EURNOK", "EURAUD", "EURNZD"]
HOLDOUT_START = 2019
K = 2


def weights_nleg(R: np.ndarray, k: int, nleg: int) -> np.ndarray:
    """Long bottom nleg / short top nleg, dollar-neutral, position at t uses data ≤ t-1."""
    n, m = R.shape
    W = np.zeros((n, m))
    cum = np.full((n, m), np.nan)
    for t in range(k, n):
        cum[t] = np.nansum(R[t - k:t], axis=0)
    cum = np.where(np.isnan(R), np.nan, cum)
    for t in range(k + 1, n):
        s = cum[t - 1]
        live = ~np.isnan(s)
        if live.sum() < nleg * 2:
            continue
        cols = np.flatnonzero(live)
        order = np.argsort(s[live])
        W[t, cols[order[:nleg]]] = 1.0 / nleg
        W[t, cols[order[-nleg:]]] = -1.0 / nleg
    return W


def run(name: str, syms: list[str], regime: str) -> dict:
    h09.SYMS = syms
    old = h09.SCENARIO
    h09.SCENARIO = regime
    h09.COST_VEC = None if regime == "assumed" else h09.measured_cost_vector(syms, regime)
    h09.SCENARIO = old
    weeks, R = h09.build_panel(syms, "P1")
    keep = np.array([w[0] >= HOLDOUT_START for w in weeks])
    R = R.copy()
    R[~keep] = np.nan                      # hold-out only: nothing pre-2019 contributes
    nleg = 2 if len(syms) == 5 else max(2, len(syms) // 3)
    W = weights_nleg(R, K, nleg)
    pnl = h09.pnr(R, W)
    base = h09.stats(pnl)
    dbl = h09.stats(h09.pnr(R, W, cost_mult=2.0))
    wf = h09.walk_forward(pnl, weeks, years=3, step=1)
    wf_pos = round(100.0 * float(np.mean([b["sharpe"] > 0 for b in wf])), 1) if wf else 0.0
    nul = h09.null_sim(R, W, n_sim=1000)
    null_pct = round(float((nul < base["sharpe"]).mean()) * 100, 1)
    return {"panel": name, "instruments": syms, "regime": regime, "weeks_used": base["weeks"],
            "full": base, "double_cost": dbl, "walk_forward": wf, "wf_positive_pct": wf_pos,
            "null_mean": round(float(nul.mean()), 3), "null_pct": null_pct}


def verdict(r: dict) -> dict:
    c = {
        "A1_net_sharpe_gt_0.35": bool(r["full"]["sharpe"] > 0.35),
        "A2_null_pct_ge_95": bool(r["null_pct"] >= 95),
        "A3_wf_positive_ge_60pct": bool(r["wf_positive_pct"] >= 60),
        "A4_survives_2x_cost": bool(r["double_cost"]["sharpe"] > 0.20),
    }
    return {"checks": c, "passed": all(c.values())}


def main() -> None:
    out = {"prereg": "docs/PREREG_H10.md", "holdout": f"{HOLDOUT_START}-01-01 .. 2026-11-20",
           "primary": {}, "secondary": {}}
    for regime in ("retail", "ecn"):
        r = run("PRIMARY_LIQUID5", PRIMARY, regime)
        r["verdict"] = verdict(r)
        out["primary"][regime] = r
        f_ = r["full"]
        print(f"  PRIMARY {regime:6}: Sharpe {f_['sharpe']:+.3f} CAGR {f_['cagr']:+.2f}% "
              f"DD {f_['maxdd']:.0f}% 2x {r['double_cost']['sharpe']:+.3f} "
              f"WF+ {r['wf_positive_pct']}% null {r['null_pct']} -> "
              f"{'PASS' if r['verdict']['passed'] else 'FAIL'}")
    for regime in ("retail",):
        r = run("SECONDARY_EUR9", SECONDARY, regime)
        r["verdict"] = verdict(r)
        out["secondary"][regime] = r
        print(f"  SECONDARY {regime}: Sharpe {r['full']['sharpe']:+.3f} WF+ {r['wf_positive_pct']}%")

    with open(os.path.join(ART, "h10_holdout.json"), "w") as f:
        json.dump(out, f, indent=2)
    print("wrote research/artifacts/h10_holdout.json")


if __name__ == "__main__":
    main()
