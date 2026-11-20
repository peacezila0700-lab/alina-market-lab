#!/usr/bin/env python3
"""BASE RATES — conditional forward-return distributions, estimated from the data in this repo.

Why this file exists: every "principle" a human trader uses ("buy fear", "high gamma suppresses
vol", "stress predicts drawdowns") is really a conditional distribution. Rather than trusting a
blog's number, this script measures them on official series and writes a tidy table a model can
consume directly.

Method (deliberately conservative):
  * Forward returns are SIMPLE returns from close to close, horizon h in trading days.
  * Overlapping windows are used for the point estimates (that is what a "if today looks like X"
    question asks) but the `n_eff` column reports the non-overlapping count so nobody is fooled
    into treating overlapping observations as independent.
  * No costs: this is a distribution of market outcomes, not a strategy.
  * Every factor is bucketed on a TRAILING percentile (or fixed thresholds where the level is
    meaningful), so the table is usable in real time without hindsight.

Outputs: data/facts/base_rates.csv, data/facts/BASE_RATES.md, data/facts/base_rates.json
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "facts")
os.makedirs(OUT, exist_ok=True)
HORIZONS = (5, 21, 63, 252)


def load(rel: str, col: str | None = None) -> pd.Series:
    df = pd.read_csv(os.path.join(ROOT, rel))
    dcol = "date" if "date" in df.columns else df.columns[0]
    c = col or ("close" if "close" in df.columns else df.columns[1])
    s = pd.Series(df[c].values, index=pd.to_datetime(df[dcol], errors="coerce")).astype(float)
    s = s[~s.index.duplicated()].sort_index().dropna()
    return s


def fwd(px: pd.Series, h: int) -> pd.Series:
    return px.shift(-h) / px - 1.0


def stat_block(ret: pd.Series, mask: pd.Series) -> dict:
    x = ret[mask].dropna()
    if len(x) < 30:
        return {}
    return {"n": int(len(x)), "median": round(float(x.median()) * 100, 2),
            "mean": round(float(x.mean()) * 100, 2), "pct_pos": round(float((x > 0).mean()) * 100, 1),
            "p10": round(float(x.quantile(0.10)) * 100, 2), "p90": round(float(x.quantile(0.90)) * 100, 2),
            "worst": round(float(x.min()) * 100, 2)}


def bucketise(s: pd.Series, kind: str) -> pd.Series:
    """kind: 'fixed:<edges>' or 'pct:<n>' trailing percentile buckets."""
    if kind.startswith("pct:"):
        n = int(kind.split(":")[1])
        r = s.rolling(504, min_periods=252).rank(pct=True)
        return pd.cut(r, bins=np.linspace(0, 1, n + 1), labels=[f"q{i + 1}" for i in range(n)],
                      include_lowest=True).astype(str)
    edges = [float(x) for x in kind.split(":")[1].split(",")]
    labels = [f"<{edges[0]:g}"] + [f"{a:g}-{b:g}" for a, b in zip(edges, edges[1:])] + [f">={edges[-1]:g}"]
    return pd.cut(s, bins=[-np.inf] + edges + [np.inf], labels=labels).astype(str)


def main() -> None:
    spy = load("data/universe/SPY.csv")
    vix = load("data/official/VIX_CBOE_D.csv")
    dix = load("data/alt/dix_gex.csv", "DIX")
    gex = load("data/alt/dix_gex.csv", "GEX")
    fsi = load("data/alt/ofr_fsi.csv", "OFR FSI")

    factors = {
        "VIX": (vix, "fixed:12,15,20,25,30,40", "CBOE VIX close"),
        "DIX": (dix, "pct:5", "SqueezeMetrics dark-pool index"),
        "GEX_sign": (np.sign(gex), "fixed:-1,0,1", "dealer gamma sign (SqueezeMetrics model)"),
        "OFR_FSI": (fsi, "fixed:-0.5,0,0.5,1.5", "OFR Financial Stress Index"),
    }

    rows, meta = [], {}
    for name, (s, kind, desc) in factors.items():
        s = s.copy()
        s.index = s.index.normalize()
        b = bucketise(s, kind) if kind.startswith("pct:") else s.pipe(lambda x: bucketise(x, kind))
        if kind.startswith("fixed:-1"):
            b = pd.Series(np.where(s > 0, "positive", np.where(s < 0, "negative", "zero")), index=s.index)
        aligned = b.reindex(spy.index, method="ffill")
        meta[name] = {"description": desc, "coverage": f"{s.index.min().date()}..{s.index.max().date()}"}
        for h in HORIZONS:
            r = fwd(spy, h).reindex(spy.index)
            base = stat_block(r, pd.Series(True, index=spy.index))
            rows.append({"factor": name, "bucket": "ALL (unconditional)", "horizon_d": h, **base,
                         "n_eff": int(base.get("n", 0) / h)})
            for lvl in sorted(aligned.dropna().unique()):
                m = aligned == lvl
                st = stat_block(r, m)
                if st:
                    rows.append({"factor": name, "bucket": str(lvl), "horizon_d": h, **st,
                                 "n_eff": int(st["n"] / h)})

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(OUT, "base_rates.csv"), index=False)
    with open(os.path.join(OUT, "base_rates.json"), "w") as f:
        json.dump({"meta": meta, "generated_rows": len(df), "note":
                   "Forward simple returns in percent. n_eff = non-overlapping count (~n/h): "
                   "use it, not n, when judging significance."}, f, indent=2)

    # human/AI-readable markdown, one section per factor/horizon of 21d and 252d
    lines = ["# BASE RATES — what happened NEXT, given today's reading", "",
             "Measured on this repo's own official data (SPY from Yahoo, VIX from Cboe, DIX/GEX from "
             "SqueezeMetrics, OFR FSI from the Office of Financial Research). Forward returns are simple, "
             "in percent, no costs. `n_eff` = non-overlapping observations — the honest sample size.", ""]
    for name in factors:
        for h in (21, 252):
            sub = df[(df.factor == name) & (df.horizon_d == h)]
            if sub.empty:
                continue
            lines += [f"## {name} → next {h} trading days", "",
                      "| bucket | n | n_eff | median % | mean % | % positive | p10 % | p90 % | worst % |",
                      "|---|---|---|---|---|---|---|---|---|"]
            for _, r in sub.iterrows():
                lines.append(f"| {r.bucket} | {int(r.n)} | {int(r.n_eff)} | {r['median']:+.1f} | {r['mean']:+.1f} | "
                             f"{r.pct_pos:.0f} | {r.p10:+.1f} | {r.p90:+.1f} | {r.worst:+.1f} |")
            lines.append("")
    lines += ["## How to use this without fooling yourself", "",
              "- A bucket with `n_eff` under ~30 is an anecdote. Do not build a rule on it.",
              "- The unconditional row is the benchmark. If the bucket median is not visibly different "
              "*and* the sample is big enough, there is no signal.",
              "- These are conditional distributions of the market, not of a strategy. A strategy also pays "
              "the spread and the timing of entry, which usually eats the difference.",
              "- Multiple buckets × factors × horizons = a lot of looks. Treat the extremes as hypotheses, "
              "then test them with a hold-out, exactly like the other experiments in this repo."]
    with open(os.path.join(OUT, "BASE_RATES.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"wrote {len(df)} rows -> data/facts/base_rates.csv  (+ BASE_RATES.md)")
    print(df[(df.horizon_d == 252) & (df.factor == "VIX")].to_string(index=False))


if __name__ == "__main__":
    main()
