#!/usr/bin/env python3
"""
build_hour_profile.py — when is it actually cheap and liquid to trade? Measured, per pair, per hour.

This is the execution-timing layer, built from 23 years of hourly bid/ask (scripts/backfill_duka_h1.py).
It answers three operational questions with numbers instead of folklore:

  1. What is the quoted spread, in pips, at each hour of the UTC day? (cost of acting)
  2. What is the typical hourly range as a multiple of that spread? (movement available per unit of cost)
  3. Which hours have the best "range per cost" — i.e. where a given edge is cheapest to express?

The ratio in (3) is the honest version of "trade the London open": it is a cost/liquidity statement, not
a directional claim. Nothing here is a signal; EXP-0017/0018 showed that hourly directional rules still
lose after these spreads.

Outputs
  data/facts/HOUR_OF_DAY_PROFILE.md   tables + the ranked "best hours" per pair
  data/facts/hour_of_day_profile.csv  machine-readable
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INTRA = ROOT / "data" / "intraday"
FACTS = ROOT / "data" / "facts"
PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "EURGBP", "EURCHF", "XAUUSD"]


def pip(sym):
    return 0.01 if (sym.endswith("JPY") or sym == "XAUUSD") else 0.0001


def main():
    rows = []
    md = ["# HOUR-OF-DAY EXECUTION PROFILE (measured, 2003-2026)", "",
          "Quoted spreads from Dukascopy hourly bid/ask. **These are a floor**: a retail account pays "
          "commission and slippage on top. `range/spread` = median hourly high-low range divided by the "
          "median spread for that hour — how much movement you get per unit of cost.", ""]
    for sym in PAIRS:
        p = INTRA / f"{sym}_H1_bidask.csv"
        if not p.exists():
            continue
        df = pd.read_csv(p, parse_dates=["ts_utc"])
        df = df[df["bid_c"] > 0].copy()
        df["hour"] = df["ts_utc"].dt.hour
        df["rng_pips"] = (df["bid_h"] - df["bid_l"]) / pip(sym)
        g = df.groupby("hour").agg(median_spread_pips=("spread_close_pips", "median"),
                                   median_range_pips=("rng_pips", "median"),
                                   n_bars=("spread_close_pips", "size")).reset_index()
        g["range_over_spread"] = (g["median_range_pips"] / g["median_spread_pips"]).round(2)
        g.insert(0, "pair", sym)
        rows.append(g)

        best = g.sort_values("range_over_spread", ascending=False).head(4)
        worst = g.sort_values("range_over_spread").head(3)
        md += [f"## {sym}", "",
               f"- cheapest hours (spread pips): " +
               ", ".join(f"{int(r.hour):02d}Z {r.median_spread_pips:.2f}" for _, r in
                         g.sort_values("median_spread_pips").head(4).iterrows()),
               f"- best movement-per-cost hours: " +
               ", ".join(f"{int(r.hour):02d}Z ×{r.range_over_spread:.1f}" for _, r in best.iterrows()),
               f"- worst (avoid unless forced): " +
               ", ".join(f"{int(r.hour):02d}Z ×{r.range_over_spread:.1f}" for _, r in worst.iterrows()),
               "", "| hour UTC | median spread (pips) | median range (pips) | range / spread | bars |",
               "|---|---|---|---|---|"]
        for _, r in g.sort_values("hour").iterrows():
            md.append(f"| {int(r.hour):02d} | {r.median_spread_pips:.2f} | {r.median_range_pips:.1f} | "
                      f"{r.range_over_spread:.2f} | {int(r.n_bars)} |")
        md.append("")

    if not rows:
        print("no intraday files found")
        return
    out = pd.concat(rows, ignore_index=True)
    FACTS.mkdir(parents=True, exist_ok=True)
    out.to_csv(FACTS / "hour_of_day_profile.csv", index=False)
    md += ["## How to use this", "",
           "1. If a rule must trade, restrict it to the hours with the highest `range / spread`; EXP-0018 "
           "showed that gating by hour alone does not create an edge, it only reduces the cost of one.",
           "2. The 21-22Z and 00-02Z hours are the rollover window: spreads widen several-fold and the "
           "range shrinks. Any hourly strategy should simply be flat there.",
           "3. XAUUSD's spread is ~39 pips (0.39 USD) — gold is a *daily* instrument at retail cost; "
           "hourly gold ideas need ~80 pips of movement just to break even on a round trip.", ""]
    (FACTS / "HOUR_OF_DAY_PROFILE.md").write_text("\n".join(md))
    print(f"  -> {FACTS/'HOUR_OF_DAY_PROFILE.md'}  ({len(out)} rows)")
    show = out[out.pair == "EURUSD"].sort_values("median_spread_pips").head(3)
    print("  EURUSD cheapest hours:", [(int(r.hour), round(r.median_spread_pips, 2)) for _, r in show.iterrows()])


if __name__ == "__main__":
    main()
