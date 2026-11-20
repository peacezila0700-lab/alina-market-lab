#!/usr/bin/env python3
"""
EXP-0016 — Bond carry / roll-down: does the shape of the Treasury curve pay for duration exposure?

WHY THIS IS A DIFFERENT KIND OF BET
Every test so far looked for DIRECTION from price-derived state (breadth, gamma, events, positioning).
This one tests a CARRY mechanism instead: a bond's expected return over a short horizon is roughly its
yield plus the price gain from rolling down a steep curve, so a steep curve should pay duration holders
and a flat/inverted one should not. That is the mechanism documented in the term-structure literature
(Fama-Bliss 1987; Cochrane-Piazzesi 2005) and it does not require forecasting anything.

PRE-REGISTERED DESIGN (written before the result)
-------------------------------------------------
Data      : Treasury daily yield curve 1990-2026 (backfilled by scripts/backfill_history.py) and the
            ETF prices available here: TLT (20y+, from 2002-07-30) and IEF (7-10y, from 2002-07-30).
            Price-only returns; no dividends (TLT/IEF distribute monthly), so every level is pessimistic
            by roughly the coupon — this biases the SIGNAL comparison, not the sign of the result.
Signals   : S1 = 10Y − 3M (level slope), S2 = 10Y − 2Y (curve slope). Both taken at t-1.
Rule      : w in {0, 1, 2} from terciles of S over the trailing 3 years (756 trading days, causal,
            expanding seed of 2 years). Mean exposure ≈ 1, so no free leverage.
Costs     : 2 bp per unit |Δw| per day (ETF commission + spread; a tercile rule trades rarely).
Split     : 70/30 by date.
Benchmarks (both must be beaten — PITFALLS #13 exists because this step is usually skipped):
            BH  = constant weight equal to the arm's mean exposure
            VT  = volatility targeting, w = clip(0.10/RV20(t-1), 0, 2) scaled to the same mean
Null      : circular shifts of the arm's weight series (200), giving the distribution of Sharpe under
            "the carry rule carries no timing information but keeps its turnover".

PASS BAR: the arm's net Sharpe must exceed the 98.75th percentile of the shift null (Bonferroni for
4 tests) in-sample AND out-of-sample, AND exceed the vol-targeting arm out-of-sample.
Anything else is FAIL and H19 closes.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "artifacts" / "bond_carry.json"
COST_BP = 2.0
N_SHIFT = 200
BAR_PCT = 98.75


def load_etf(sym):
    df = pd.read_csv(ROOT / "data" / "universe" / f"{sym}.csv")
    dc = next(c for c in df.columns if c.lower() == "date")
    cc = next(c for c in df.columns if c.lower() == "close")
    df[dc] = pd.to_datetime(df[dc])
    return df.set_index(dc)[cc].astype(float).sort_index()


def sharpe(r):
    r = pd.Series(r).dropna()
    return float(r.mean() / r.std() * np.sqrt(252)) if len(r) > 60 and r.std() > 0 else np.nan


def perf(r, w):
    df = pd.DataFrame({"r": r, "w": w}).dropna()
    dw = df["w"].astype(float).diff().abs().fillna(0.0)
    net = df["w"].astype(float) * df["r"] - dw * COST_BP / 1e4
    eq = (1 + net).cumprod()
    return {"sharpe": sharpe(net), "cagr": float(eq.iloc[-1] ** (252 / len(net)) - 1),
            "maxdd": float((eq / eq.cummax() - 1).min()), "n": int(len(net)),
            "mean_w": float(df["w"].mean()), "vol": float(net.std() * np.sqrt(252))}


def main():
    yc = pd.read_csv(ROOT / "data" / "collect" / "treasury_yield_curve_full.csv", parse_dates=["Date"]).set_index("Date")
    cols = {c.strip(): c for c in yc.columns}
    yc = yc.sort_index()
    s1 = yc[cols["10 Yr"]] - yc[cols["3 Mo"]]
    s2 = yc[cols["10 Yr"]] - yc[cols["2 Yr"]]
    print(f"  curve {yc.index[0].date()} .. {yc.index[-1].date()}  {len(yc)} days")

    results = {}
    for etf in ("TLT", "IEF"):
        px = load_etf(etf)
        r = px.pct_change()
        idx = r.index.intersection(s1.index)  # bond ETF sample, signal available
        r = r.reindex(idx)
        rv = r.rolling(20).std() * np.sqrt(252)
        for sname, sig in (("10y-3m", s1), ("10y-2y", s2)):
            s = sig.reindex(idx).ffill()
            lo = s.rolling(756, min_periods=504).quantile(1 / 3)
            hi = s.rolling(756, min_periods=504).quantile(2 / 3)
            w = pd.Series(np.where(s >= hi, 2.0, np.where(s <= lo, 0.0, 1.0)), index=idx)
            w = w.where(lo.notna())
            w = w.shift(1)                      # decide at the close, earn the next day
            w = (w / np.nanmean(w)).clip(0, 2)  # mean exposure 1
            live = w.dropna().index
            n = len(live)
            i_is, i_oos = live[: int(n * 0.70)], live[int(n * 0.70):]

            arm = {"is": perf(r.reindex(i_is), w.reindex(i_is)), "oos": perf(r.reindex(i_oos), w.reindex(i_oos))}
            bh = {"is": perf(r.reindex(i_is), pd.Series(1.0, index=i_is)),
                  "oos": perf(r.reindex(i_oos), pd.Series(1.0, index=i_oos))}
            k = float(arm["is"]["mean_w"])
            wv = (0.10 / rv.shift(1)).clip(0, 2) * k
            vt = {"is": perf(r.reindex(i_is), wv.reindex(i_is)), "oos": perf(r.reindex(i_oos), wv.reindex(i_oos))}

            def null(idx_, w_, base_sharpe):
                s_ = w_.reindex(idx_).ffill().bfill().values.astype(float)
                rr = r.reindex(idx_).values
                rng = np.random.default_rng(3)
                shs = []
                for _ in range(N_SHIFT):
                    wsp = pd.Series(np.roll(s_, rng.integers(1, len(s_))), index=idx_)
                    shs.append(sharpe(wsp * rr - wsp.diff().abs().fillna(0) * COST_BP / 1e4))
                return float((np.array(shs) < base_sharpe).mean() * 100), float(np.percentile(shs, BAR_PCT))

            p_is, q_is = null(i_is, w, arm["is"]["sharpe"])
            p_oos, q_oos = null(i_oos, w, arm["oos"]["sharpe"])
            passed = (p_is >= BAR_PCT and p_oos >= BAR_PCT
                      and arm["oos"]["sharpe"] > vt["oos"]["sharpe"])
            results[f"{etf}_{sname}"] = {"arm": arm, "buy_hold": bh, "voltarget": vt,
                                         "pct_is": p_is, "pct_oos": p_oos,
                                         "null_bar_is": q_is, "null_bar_oos": q_oos,
                                         "verdict": "PASS" if passed else "FAIL"}
            print(f"\n  {etf} / {sname}   n={n}  IS {i_is[0].date()}..{i_is[-1].date()}  OOS {i_oos[0].date()}..")
            print(f"    carry arm   IS Sharpe {arm['is']['sharpe']:>6.3f}  OOS {arm['oos']['sharpe']:>6.3f}  "
                  f"CAGR {arm['oos']['cagr']:+.2%}  maxDD OOS {arm['oos']['maxdd']:.1%}")
            print(f"    buy & hold  IS Sharpe {bh['is']['sharpe']:>6.3f}  OOS {bh['oos']['sharpe']:>6.3f}")
            print(f"    vol target  IS Sharpe {vt['is']['sharpe']:>6.3f}  OOS {vt['oos']['sharpe']:>6.3f}")
            print(f"    shift null  IS pct {p_is:5.1f} (bar {q_is:+.3f})   OOS pct {p_oos:5.1f} (bar {q_oos:+.3f})"
                  f"   -> {'PASS' if passed else 'FAIL'}")

    any_pass = any(v["verdict"] == "PASS" for v in results.values())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"experiment": "EXP-0016", "hypothesis": "H19",
                               "design": __doc__.split("PRE-REGISTERED DESIGN")[1][:2400],
                               "bar_percentile": BAR_PCT, "results": results,
                               "any_pass": any_pass}, indent=2, default=str))
    print(f"\n  VERDICT: {'PASS (review)' if any_pass else 'FAIL — curve slope does not pay for duration'}")
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()
