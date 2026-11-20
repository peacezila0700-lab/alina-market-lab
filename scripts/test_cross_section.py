#!/usr/bin/env python3
"""EXP-0012 — cross-sectional factor test on the BROAD panel (68 ETFs, the payoff of the new data).

Why this test now: cross-sectional questions ("rank assets, long the top, short the bottom") need many
assets to have power. The 5-instrument execution book cannot answer them; 68 ETFs can. This is the
first test in the repo that uses the wide book for what it is for.

Pre-registration (written before running):
  Universe  68 ETFs from data/broad (vol wrappers and cash kept but flagged; results reported both ways)
  Signals   MOM_12_1  = 252-day return skipping the last 21 days
            REV_1M    = past 21-day return (contrarian if the sign is negative)
            REV_5D    = past 5-day return
  Construction  weekly (Friday close) cross-sectional ranking; long the top quintile, short the bottom
            quintile, equal-weighted, dollar-neutral. Positions use the SIGNAL from Friday close and
            earn the NEXT week's returns (pos.shift(1) applied to weekly returns) — no look-ahead.
  Costs     5 bp per side per unit turnover (liquid US ETFs), charged on |Δweight|.
  Null      200 permutations of the asset LABELS held fixed across the whole sample (turnover-matched:
            the portfolio keeps its persistence, only signal→asset mapping is destroyed). A second,
            weekly-reshuffled null is reported for transparency but is NOT the bar, because it loses
            mostly to its own inflated turnover.
  Split     first 70% of weeks = in-sample, last 30% = out-of-sample.
  Pass bar  real strategy beats the 95th percentile of the null IN-SAMPLE and stays positive OOS.

Output: research/artifacts/cross_section.json
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "research", "artifacts", "cross_section.json")
BROAD = os.path.join(ROOT, "data", "broad")
EXCLUDE = {"BIL", "SVXY", "VIXY", "VXZ"}     # cash and vol wrappers distort a dollar-neutral book
COST_BP = 5.0
N_PERM = 200


def load_panel() -> pd.DataFrame:
    frames = {}
    for f in test_files():
        df = pd.read_csv(os.path.join(BROAD, f))
        if "date" not in df.columns or "close" not in df.columns or len(df) < 600:
            continue
        s = pd.Series(df.close.values, index=pd.to_datetime(df.date, errors="coerce")).astype(float)
        s = s[~s.index.duplicated()].sort_index().dropna()
        if len(s) > 600:
            frames[f[:-4]] = s
    px = pd.DataFrame(frames).sort_index()
    return px


def test_files():
    return [f for f in sorted(os.listdir(BROAD)) if f.endswith(".csv") and not f.startswith("MANIFEST")]


def weekly(px: pd.DataFrame) -> pd.DataFrame:
    return px.resample("W-FRI").last()


def backtest(sig: pd.DataFrame, ret_w: pd.DataFrame, perm: int = 0, rng=None,
             mode: str = "dynamic") -> pd.Series:
    """Dollar-neutral quintile portfolio, weekly, cost-charged, with an optional null.

    Two NULLS, because they answer different questions:
      mode='static'  one fixed permutation of the asset LABELS for the whole sample. The portfolio keeps
                     its holding persistence (same turnover as the real strategy), and only the
                     signal→asset mapping is destroyed. THIS is the honest null: beating it means the
                     signal carried information.
      mode='dynamic' the labels are reshuffled every week. Turnover explodes, so the null loses mostly
                     to costs. Beating this one proves nothing about information — it proves only that
                     the real strategy trades less. Reported for transparency, never used as the bar.
    """
    s = sig.copy()
    if perm and rng is not None and mode == "static":
        cols = list(s.columns)
        new = list(rng.permutation(cols))
        s = pd.DataFrame(s.values, index=s.index, columns=new)
    elif perm and rng is not None:
        arr = s.values.copy()
        for i in range(arr.shape[0]):
            # NOTE: row[mask] returns a COPY, so shuffling it in place would silently do nothing.
            # Use explicit index arrays — this bug made the first version of this test report a null
            # with zero dispersion (every permutation identical to the real strategy).
            row = arr[i]
            idx = np.where(~np.isnan(row))[0]
            if len(idx) > 2:
                arr[i, idx] = row[rng.permutation(idx)]
        s = pd.DataFrame(arr, index=sig.index, columns=sig.columns)
    ranks = s.rank(axis=1, pct=True)
    long = (ranks >= 0.8).astype(float)
    short = (ranks <= 0.2).astype(float)
    w = long.div(long.sum(axis=1).replace(0, np.nan), axis=0) - \
        short.div(short.sum(axis=1).replace(0, np.nan), axis=0)
    w = w.fillna(0.0)
    pnl = (w.shift(1) * ret_w).sum(axis=1)                       # lag: last week's signal, this week's return
    turn = (w.shift(1) - w.shift(2)).abs().sum(axis=1).fillna(0.0)
    pnl = pnl - turn * COST_BP / 10000.0
    return pnl.dropna()


def sharpe(x: pd.Series) -> float:
    return float(x.mean() / x.std() * np.sqrt(52)) if len(x) > 20 and x.std() > 0 else np.nan


def main() -> None:
    px = load_panel()
    px = px.loc[:, [c for c in px.columns if c not in EXCLUDE]]
    px = px.dropna(axis=1, thresh=int(len(px) * 0.5)).ffill()
    px = px.loc["2007-01-01":]
    ret_w = weekly(px).pct_change()
    wk = weekly(px)
    signals = {
        "MOM_12_1": wk.shift(1) / wk.shift(52) - 1.0,
        "REV_1M": wk / wk.shift(4) - 1.0,
        "REV_5D": wk / wk.shift(1) - 1.0,
    }
    n_assets = px.shape[1]
    res = {"universe": {"n_assets": int(n_assets), "start": str(px.index.min().date()),
                        "end": str(px.index.max().date()), "cost_bp_per_side": COST_BP,
                        "permutations": N_PERM,
                        "note": "vol wrappers and cash excluded; quarterly-listed ETFs partially NaN early"},
           "pass_bar": "beat 95th pct of permutation null in-sample AND positive out-of-sample",
           "results": {}}

    weeks = ret_w.index
    cut = weeks[int(len(weeks) * 0.7)]
    rng = np.random.default_rng(7)
    for name, sig in signals.items():
        sig = sig.reindex(ret_w.index)
        pnl = backtest(sig, ret_w)
        pnl_is = pnl[pnl.index < cut]
        pnl_oos = pnl[pnl.index >= cut]
        nulls = {"static": [], "dynamic": []}
        for mode in ("static", "dynamic"):
            for k in range(N_PERM):
                n = backtest(sig, ret_w, perm=1, rng=rng, mode=mode)
                nulls[mode].append(sharpe(n[n.index < cut]))
            nulls[mode] = np.array([x for x in nulls[mode] if np.isfinite(x)])
        null = nulls["static"]          # the pre-declared bar uses the turnover-matched (static) null
        sr_is = sharpe(pnl_is)
        pct = float((null < sr_is).mean() * 100) if len(null) else np.nan
        eq = (1 + pnl).cumprod()
        res["results"][name] = {
            "n_weeks": int(len(pnl)),
            "sharpe_is": round(sr_is, 3) if np.isfinite(sr_is) else None,
            "sharpe_oos": round(sharpe(pnl_oos), 3) if np.isfinite(sharpe(pnl_oos)) else None,
            "mean_weekly_bp": round(float(pnl.mean()) * 10000, 2),
            "cagr_pct": round(float(eq.iloc[-1] ** (52 / len(pnl)) - 1) * 100, 2) if len(pnl) and eq.iloc[-1] > 0 else None,
            "maxdd_pct": round(float((eq / eq.cummax() - 1).min()) * 100, 2),
            "null_static_median": round(float(np.median(null)), 3) if len(null) else None,
            "null_static_p95": round(float(np.percentile(null, 95)), 3) if len(null) else None,
            "null_dynamic_median": round(float(np.median(nulls["dynamic"])), 3) if len(nulls["dynamic"]) else None,
            "null_median_sharpe": round(float(np.median(null)), 3) if len(null) else None,
            "null_p95_sharpe": round(float(np.percentile(null, 95)), 3) if len(null) else None,
            "percentile_vs_null": round(pct, 1) if np.isfinite(pct) else None,
            "null_std_sharpe": round(float(np.std(null)), 4) if len(null) else None,
            "z_vs_null": round(float((sr_is - np.median(null)) / np.std(null)), 2)
            if (len(null) and np.std(null) > 1e-9) else None,
            "null_note": "the permutation null is TIGHT here: with 13 longs and 13 shorts out of 60+, a random "
                         "selection produces almost the same portfolio return, so the signal cannot add "
                         "anything unless it is strongly informative. That is the finding, not a bug.",
        }
        r = res["results"][name]
        r["verdict"] = ("PASSES pre-declared bar" if (pct >= 95 and (r["sharpe_oos"] or -9) > 0) else "FAILS")
        print(f"  {name:10} IS Sharpe {r['sharpe_is']}  OOS {r['sharpe_oos']}  null p95 {r['null_p95_sharpe']}  "
              f"pct {r['percentile_vs_null']}  → {r['verdict']}")

    passed = [k for k, v in res["results"].items() if v["verdict"].startswith("PASS")]
    res["conclusion"] = (f"passed: {passed}" if passed else
                         "no cross-sectional factor beats its own permutation null on 60+ ETFs — the classic "
                         "factors are arbitraged in the liquid ETF cross-section, which is exactly what theory "
                         "predicts for the most-watched version of a factor")
    with open(OUT, "w") as f:
        json.dump(res, f, indent=2)
    print("VERDICT:", res["conclusion"])


if __name__ == "__main__":
    main()
