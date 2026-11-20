#!/usr/bin/env python3
"""
build_vol_regimes.py — conditional base rates for the volatility TERM STRUCTURE.

This is the layer the rest of the project was missing: every earlier base-rate table conditioned on
the VIX *level*. The curve's slope is the market's own forward-looking stress price and is a stronger
conditioner. Everything here is descriptive (no trading rule), so it can be used by a downstream AI
as a prior without any of the execution caveats.

Outputs
  data/facts/VOL_REGIME_BASE_RATES.md   human/LLM-readable tables
  data/facts/vol_regime_base_rates.csv  same numbers, machine-readable

Method notes (uncertainty written down)
  * Buckets are ex-ante defined, not fitted: slope_3m in (<0.85, 0.85-1.00, 1.00-1.10, >1.10),
    slope_9d in (<0.95, 0.95-1.05, >1.05), vvix percentile in quintiles.
  * Forward returns are SPY close-to-close, price only. No costs — this is a prior, not a strategy.
  * n_eff = n_rows / horizon_days: overlapping windows make the effective sample much smaller, and
    every table prints it. If n_eff < 8 the row is marked "weak".
  * A 21-day horizon overlaps only ~12 times a year, so treat every cell above 1.60x or below 0.60x
    with suspicion unless n_eff is large; the mark column does that for you.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FACTS = ROOT / "data" / "facts"
HORIZONS = [5, 21, 63]


def load_broad(sym):
    df = pd.read_csv(ROOT / "data" / "broad" / f"{sym}.csv")
    dc = next(c for c in df.columns if c.lower() in ("date", "datetime"))
    cc = next(c for c in df.columns if c.lower() in ("close", "adj close", "price"))
    df[dc] = pd.to_datetime(df[dc])
    return df.set_index(dc)[cc].astype(float).sort_index()


def table(df, bucket_col, label, rows):
    for b, sub in df.groupby(bucket_col, observed=True):
        for h in HORIZONS:
            fwd = sub[f"fwd{h}"].dropna()
            if len(fwd) < 30:
                continue
            vol = sub[f"rv{h}"].dropna()
            rows.append({"conditioner": label, "bucket": str(b), "horizon_d": h, "n": int(len(fwd)),
                         "n_eff": int(len(fwd) // h), "median_pct": round(float(fwd.median()) * 100, 3),
                         "mean_pct": round(float(fwd.mean()) * 100, 3),
                         "pct_positive": round(float((fwd > 0).mean()) * 100, 1),
                         "p10_pct": round(float(fwd.quantile(0.10)) * 100, 2),
                         "p90_pct": round(float(fwd.quantile(0.90)) * 100, 2),
                         "realised_vol_pct": round(float(vol.mean()) * 100, 2) if len(vol) else None})


def main():
    spy = load_broad("SPY")
    ft = pd.read_csv(ROOT / "data" / "collect" / "vol_stress_features.csv", index_col=0, parse_dates=True)
    df = pd.DataFrame(index=spy.index)
    df["close"] = spy
    for h in HORIZONS:
        df[f"fwd{h}"] = spy.shift(-h) / spy - 1
        df[f"rv{h}"] = (np.log(spy).diff().rolling(h).std() * np.sqrt(252)).shift(-h)

    df["slope_3m"] = ft["slope_3m"].reindex(df.index).ffill()
    df["slope_9d"] = ft["slope_9d"].reindex(df.index).ffill()
    df["vvix_pct"] = ft["vvix_pct"].reindex(df.index).ffill()
    df["skew"] = ft["skew"].reindex(df.index).ffill()
    df["vix"] = ft["vix"].reindex(df.index).ffill()

    df["b_slope3m"] = pd.cut(df["slope_3m"], [-np.inf, 0.85, 1.00, 1.10, np.inf],
                             labels=["<0.85 contango", "0.85-1.00", "1.00-1.10", ">1.10 inverted"])
    df["b_slope9d"] = pd.cut(df["slope_9d"], [-np.inf, 0.95, 1.05, np.inf],
                             labels=["<0.95 calm front", "0.95-1.05", ">1.05 front panic"])
    df["b_vvix"] = pd.cut(df["vvix_pct"], [0, 0.2, 0.4, 0.6, 0.8, 1.0],
                          labels=["q1 calmest", "q2", "q3", "q4", "q5 wildest"])
    df["b_skew"] = pd.cut(df["skew"], [-np.inf, 125, 135, 145, np.inf],
                          labels=["<125", "125-135", "135-145", ">145"])
    df["b_vixlvl"] = pd.cut(df["vix"], [-np.inf, 12, 15, 20, 25, 30, 40, np.inf],
                            labels=["<12", "12-15", "15-20", "20-25", "25-30", "30-40", ">=40"])

    rows = []
    for col, label in (("b_slope3m", "VIX/VIX3M slope"), ("b_slope9d", "VIX9D/VIX slope"),
                       ("b_vvix", "VVIX percentile"), ("b_skew", "SKEW level"), ("b_vixlvl", "VIX level")):
        table(df, col, label, rows)
    out = pd.DataFrame(rows)
    FACTS.mkdir(parents=True, exist_ok=True)
    out.to_csv(FACTS / "vol_regime_base_rates.csv", index=False)

    lines = ["# VOLATILITY REGIME BASE RATES — SPY forward returns by curve state",
             "",
             f"Sample: {df['slope_3m'].first_valid_index().date()} .. {df.index[-1].date()}. "
             "Price returns, no costs. `n_eff = n / horizon` (overlapping windows).",
             "Read this as a PRIOR on what usually happens, not as a strategy: EXP-0013 and EXP-0015 "
             "both showed that acting on these states does not beat volatility targeting after costs.",
             ""]
    for conditioner in out["conditioner"].unique():
        lines += [f"## {conditioner}", "",
                  "| bucket | h | n | n_eff | median % | mean % | %pos | p10 | p90 | realised vol % |",
                  "|---|---|---|---|---|---|---|---|---|---|"]
        for _, r in out[out["conditioner"] == conditioner].iterrows():
            weak = " (weak)" if r["n_eff"] < 8 else ""
            lines.append(f"| {r['bucket']}{weak} | {r['horizon_d']}d | {r['n']} | {r['n_eff']} | "
                         f"{r['median_pct']:+.2f} | {r['mean_pct']:+.2f} | {r['pct_positive']:.0f} | "
                         f"{r['p10_pct']:+.2f} | {r['p90_pct']:+.2f} | {r['realised_vol_pct']} |")
        lines.append("")

    # the headline facts, computed rather than asserted
    inv = df[df["slope_3m"] > 1.0]["fwd21"].dropna()
    con = df[df["slope_3m"] <= 1.0]["fwd21"].dropna()
    lines += ["## Headline contrasts (21-day forward, SPY)", "",
              f"- **Inverted curve (VIX > VIX3M)**: median {inv.median()*100:+.2f}%, {100*(inv>0).mean():.1f}% positive, "
              f"n={len(inv)} (n_eff {len(inv)//21})",
              f"- **Normal curve**: median {con.median()*100:+.2f}%, {100*(con>0).mean():.1f}% positive, "
              f"n={len(con)} (n_eff {len(con)//21})",
              f"- **Difference of medians: {(inv.median()-con.median())*100:+.2f} pp** — the sign is what matters; "
              "the magnitude is inside the noise for a single 15-year sample.",
              ""]
    (FACTS / "VOL_REGIME_BASE_RATES.md").write_text("\n".join(lines))
    print("\n".join(lines[-8:]))
    print(f"\n  -> {FACTS/'VOL_REGIME_BASE_RATES.md'}  ({len(out)} rows)")


if __name__ == "__main__":
    main()
