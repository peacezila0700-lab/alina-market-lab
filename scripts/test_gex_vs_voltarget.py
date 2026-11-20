#!/usr/bin/env python3
"""
EXP-0014 — The GEX overlay that survived EXP-0013's null: is it gamma, or is it just
volatility targeting wearing a gamma hat?

WHY THIS TEST EXISTS
EXP-0013 tested 7 market-state overlays against a circular-shift null. Six died. One, GEXSIGN
(1.5x exposure when dealer gamma is positive, 0.5x when negative), beat 200/200 shifted copies
in-sample (Sharpe 0.676 vs null p99.2 = 0.310) but only reached the 90th percentile out-of-sample.
A 100/100 in-sample hit deserves one sharpening — but the obvious alternative explanation must be
killed first, because it is the most common false positive in this whole field:

    In dealer-negative-gamma regimes, realised volatility is HIGH. An overlay that is long in
    calm periods and light in volatile periods is a *volatility-targeting* rule. Vol targeting
    mechanically raises Sharpe on any asset with vol clustering. GEX may be nothing more than a
    noisier way of writing "reduce size when vol is high".

PRE-REGISTERED DESIGN (written before the result)
-------------------------------------------------
Universe / period : SPY daily, GEX data live 2011-05 .. latest (DECISION: GEX sample only, so all
                    three arms see identical days).
Arm A (gamma)     : w = 1.5 if GEX(t-1) > 0 else 0.5
Arm B (voltarget) : w = clip(0.15 / RV20(t-1), 0, 2) * k   where k makes mean(B) == mean(A) exactly
                    over the full sample (a single scalar, disclosed, applied identically to IS/OOS)
Arm C (hybrid)    : w = B's weight * (1.5 if GEX>0 else 0.5), then mean-normalised the same way
All weights lagged one day; cost 2 bp per unit |Δw|.
Split 70/30 by date.

TEST STATISTIC (the only thing that can pass)
  Δ = Sharpe(A) − Sharpe(B) on the same days.
  Null: circular shifts of ARM A's weight series (200 shifts) -> distribution of Δ under "gamma
  timing carries no information beyond the vol scaling already inside B".
  Percentile of the observed Δ inside that distribution.
  PASS requires: Δ > 0, percentile >= 95 in-sample AND percentile >= 95 out-of-sample.
  (Bonferroni is not needed: this is a single pre-declared hypothesis, H17, and one comparison.)
Any other outcome = FAIL, and H17 closes with the note "GEX effect is vol targeting in disguise".
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "artifacts" / "gex_vs_voltarget.json"
N_SHIFT = 200
COST_BP = 2.0


def load(sym):
    df = pd.read_csv(ROOT / "data" / "broad" / f"{sym}.csv")
    dc = next(c for c in df.columns if c.lower() in ("date", "datetime"))
    cc = next(c for c in df.columns if c.lower() in ("close", "adj close", "price"))
    df[dc] = pd.to_datetime(df[dc])
    return df.set_index(dc)[cc].astype(float).sort_index()


def sharpe(r):
    r = pd.Series(r).dropna()
    return float(r.mean() / r.std() * np.sqrt(252)) if len(r) > 60 and r.std() > 0 else np.nan


def perf(r, w, cost_bp=COST_BP):
    df = pd.DataFrame({"r": r, "w": w}).dropna()
    dw = df["w"].astype(float).diff().abs().fillna(0.0)
    net = df["w"].astype(float) * df["r"] - dw * cost_bp / 1e4
    eq = (1 + net).cumprod()
    return {"sharpe": sharpe(net), "cagr": float(eq.iloc[-1] ** (252 / len(net)) - 1),
            "maxdd": float((eq / eq.cummax() - 1).min()), "n": int(len(net)),
            "mean_w": float(df["w"].mean()), "turnover_yr": float(dw.sum() / (len(net) / 252))}


def main():
    spy = load("SPY")
    g = pd.read_csv(ROOT / "data" / "alt" / "dix_gex.csv")
    gc = next(c for c in g.columns if c.lower() == "gex")
    g["date"] = pd.to_datetime(g["date"])
    gex = g.set_index("date")[gc].astype(float).sort_index()
    gex = gex[~gex.index.duplicated()].reindex(spy.index).ffill(limit=5)

    r = spy.pct_change()
    rv20 = r.rolling(20).std() * np.sqrt(252)

    wA = pd.Series(np.where(gex.shift(1) > 0, 1.5, 0.5), index=spy.index).where(gex.shift(1).notna())
    raw = (0.15 / rv20.shift(1)).clip(0, 2).where(rv20.shift(1).notna())
    k = float(np.nanmean(wA) / np.nanmean(raw))
    wB = raw * k
    wC = (raw * np.where(gex.shift(1) > 0, 1.5, 0.5)).where(gex.shift(1).notna())
    wC = wC * float(np.nanmean(wA) / np.nanmean(wC))

    live = wA.dropna().index
    r, wA, wB, wC = r.reindex(live), wA.reindex(live), wB.reindex(live), wC.reindex(live)
    n = len(live)
    cut = int(n * 0.70)
    i_is, i_oos = live[:cut], live[cut:]

    print(f"  sample {live[0].date()} .. {live[-1].date()}  n={n}  IS={len(i_is)}  OOS={len(i_oos)}")
    print(f"  vol-target scale k = {k:.3f} (mean weights matched: A={np.nanmean(wA):.3f} B={np.nanmean(wB):.3f})")

    out = {}
    for name, w in (("A_gamma", wA), ("B_voltarget", wB), ("C_hybrid", wC)):
        s_is = perf(r.reindex(i_is), w.reindex(i_is))
        s_oos = perf(r.reindex(i_oos), w.reindex(i_oos))
        out[name] = {"is": s_is, "oos": s_oos}
        print(f"  {name:<12} IS Sharpe {s_is['sharpe']:>6.3f} vol {s_is['sharpe'] and 0 or 0}"
              f"OOS Sharpe {s_oos['sharpe']:>6.3f}  maxDD IS {s_is['maxdd']:.1%} OOS {s_oos['maxdd']:.1%}")

    def delta_pct(idx, w_a, w_b, label):
        d_obs = sharpe((w_a.reindex(idx) * r.reindex(idx) - w_a.reindex(idx).astype(float).diff().abs().fillna(0) * COST_BP / 1e4)) \
            - sharpe((w_b.reindex(idx) * r.reindex(idx) - w_b.reindex(idx).astype(float).diff().abs().fillna(0) * COST_BP / 1e4))
        base = sharpe((w_b.reindex(idx) * r.reindex(idx) - w_b.reindex(idx).astype(float).diff().abs().fillna(0) * COST_BP / 1e4))
        v = w_a.reindex(idx).values.astype(float)
        s = pd.Series(v).ffill().bfill().values
        rr = r.reindex(idx).values
        rng = np.random.default_rng(7)
        ds = []
        for _ in range(N_SHIFT):
            ws = pd.Series(np.roll(s, rng.integers(1, len(s))), index=idx)
            dw = ws.diff().abs().fillna(0)
            ds.append(sharpe(ws * rr - dw * COST_BP / 1e4) - base)
        ds = np.array(ds)
        pct = float((ds < d_obs).mean() * 100)
        print(f"  Δ(A−B) {label}: {d_obs:+.3f}  percentile {pct:.1f}  null p95 {np.percentile(ds, 95):+.3f}")
        return d_obs, pct, float(np.percentile(ds, 95))

    d_is, p_is, p95_is = delta_pct(i_is, wA, wB, "IS ")
    d_oos, p_oos, p95_oos = delta_pct(i_oos, wA, wB, "OOS")
    passed = d_is > 0 and p_is >= 95 and p_oos >= 95
    print(f"\n  VERDICT: {'PASS — gamma adds beyond vol targeting (review)' if passed else 'FAIL — GEX is vol targeting in disguise'}")

    payload = {"experiment": "EXP-0014", "hypothesis": "H17",
               "sample": [str(live[0].date()), str(live[-1].date())],
               "arms": out, "scale_k": k,
               "delta_is": d_is, "delta_is_pct": p_is, "delta_is_null_p95": p95_is,
               "delta_oos": d_oos, "delta_oos_pct": p_oos, "delta_oos_null_p95": p95_oos,
               "bar": "Δ>0 and percentile>=95 in IS and OOS",
               "verdict": "PASS" if passed else "FAIL",
               "context": "Follows EXP-0013 where the GEX overlay hit the 100th percentile in-sample "
                          "against 200 circular shifts but only the 90th out-of-sample."}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, default=str))
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()
