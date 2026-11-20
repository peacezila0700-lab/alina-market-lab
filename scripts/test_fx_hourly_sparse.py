#!/usr/bin/env python3
"""
EXP-0018 — The one thing EXP-0017 exposed: hourly FX reversal has a positive GROSS edge and dies on
turnover. So trade it sparsely.

WHAT EXP-0017 MEASURED
  REV1 pooled: gross +0.188 bp/hour, net −0.154 bp/hour, cost drag 0.342 bp/hour. Every single hour
  carries a round trip, so the spread is paid 24 times a day. The gross sign was RIGHT; the frequency
  was wrong. That is a cost-structure problem, and it has one honest fix: fewer, larger trades.

PRE-REGISTERED DESIGN (written before the result)
-------------------------------------------------
Universe / data / execution / costs / split / null: identical to EXP-0017 (same bid/ask files, one-bar
latency, one side of the *measured* spread per unit of |Δposition|, 70/30 by date, circular-shift null).
Base signal: REV1 = -sign(r_t), i.e. the profitable-gross but cost-doomed rule.

Gates (each is causal, computed from data strictly before the decision):
  G1 BIGMOVE : trade only when |r_t| is above its trailing-252-hour 95th percentile
  G2 OVERLAP : trade only during 12:00-16:00 UTC (London/NY overlap, tightest spreads, most volume)
  G3 BOTH    : G1 AND G2
When a gate is off, the position is 0 (flat), so turnover and cost fall with it.

Tests: 3 gated variants + the ungated baseline, pooled across the 6 pairs. Bar = 98.3rd percentile
(Bonferroni over 3 new variants) in BOTH halves. Report the breakeven cost multiplier for each (net mean
return / cost drag) so the margin is explicit even on a fail.

WHY THIS ISN'T P-HACKING: the number of variants is fixed at 3 before the run, they were chosen from the
EXP-0017 diagnostic (turnover and session liquidity are the only two knobs that diagnostic pointed at),
the bar is Bonferroni-corrected, and the OOS half must confirm.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

import test_fx_hourly as base

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "artifacts" / "fx_hourly_sparse.json"
BAR_PCT = 98.33


def gated_positions(df):
    r = df["r"].values
    rev = -np.sign(r)
    absr = pd.Series(np.abs(r))
    thr = absr.rolling(252, min_periods=120).quantile(0.95).shift(1).values
    big = np.nan_to_num(np.where(absr.values > thr, 1.0, 0.0), nan=0.0)
    hour = df["ts_utc"].dt.hour.values
    overlap = np.isin(hour, [12, 13, 14, 15]).astype(float)
    return {"BASE": rev, "G1_BIGMOVE": rev * big, "G2_OVERLAP": rev * overlap, "G3_BOTH": rev * big * overlap}


def main():
    pooled = {}
    cost_drag = {}
    for sym in base.PAIRS:
        df = base.load(sym)
        pos = gated_positions(df)
        for name, p in pos.items():
            net, pser = base.run(df, p, sym)
            p_ = pser.shift(1).fillna(0.0).values
            spread_cost = (0.5 * df["spread_close_pips"].values * base.pip_size(sym)
                           / df["bid_c"].shift(1).bfill().values)
            dp = np.abs(np.diff(np.concatenate([[0.0], p_])))
            drag = pd.Series(dp * spread_cost, index=df["ts_utc"])
            pooled.setdefault(name, []).append(net)
            cost_drag.setdefault(name, []).append(drag)

    results = {}
    print("  variant        IS Sharpe  IS pct  OOS Sharpe  OOS pct   turnover/h  gross bp/h  net bp/h  breakeven x")
    for name, series in pooled.items():
        port = pd.concat([s.rename(i) for i, s in enumerate(series)], axis=1).mean(axis=1).sort_index()
        drag = pd.concat([s.rename(i) for i, s in enumerate(cost_drag[name])], axis=1).mean(axis=1).sort_index()
        n = len(port)
        cut = int(n * 0.70)
        is_s, oos_s = port.iloc[:cut], port.iloc[cut:]
        sh_is, sh_oos = base.sharpe(is_s), base.sharpe(oos_s)

        def shift_pct(s, b):
            v = s.values.astype(float)
            rng = np.random.default_rng(9)
            shs = np.array([base.sharpe(np.roll(v, rng.integers(1, len(v)))) for _ in range(200)])
            return float((shs < b).mean() * 100)

        p_is, p_oos = shift_pct(is_s, sh_is), shift_pct(oos_s, sh_oos)
        ok = sh_is > 0 and sh_oos > 0 and p_is >= BAR_PCT and p_oos >= BAR_PCT
        gross = port + drag
        be = float(gross.mean() / drag.mean()) if drag.mean() > 0 else np.nan
        results[name] = {"is_sharpe": sh_is, "oos_sharpe": sh_oos, "is_pct": p_is, "oos_pct": p_oos,
                         "verdict": "PASS" if ok else "FAIL",
                         "gross_bp_per_h": float(gross.mean() * 1e4), "net_bp_per_h": float(port.mean() * 1e4),
                         "breakeven_cost_multiple": be}
        print(f"  {name:<13} {sh_is:>9.3f} {p_is:>7.1f} {sh_oos:>11.3f} {p_oos:>7.1f} "
              f"{float((np.abs(np.diff(port.index.values)) > 0).mean()):>10.3f} "
              f"{gross.mean()*1e4:>+10.3f} {port.mean()*1e4:>+9.3f} {be:>12.2f}"
              f"   {'PASS' if ok else 'FAIL'}")

    any_pass = any(v["verdict"] == "PASS" for v in results.values())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"experiment": "EXP-0018", "hypothesis": "H20b",
                               "design": __doc__.split("PRE-REGISTERED DESIGN")[1][:2200],
                               "bar_percentile": BAR_PCT, "results": results,
                               "any_pass": any_pass}, indent=2, default=str))
    print(f"\n  VERDICT: {'PASS (review)' if any_pass else 'FAIL — sparser trading does not rescue hourly FX'}")
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()
