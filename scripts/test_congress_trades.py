#!/usr/bin/env python3
"""
EXP-0019 — Do US congressional trades (House PTR filings) predict anything, once you use the date the
market could actually know?

This is the first test in the project that uses genuinely non-price, non-market information. It exists
because `day-trader-skill` pointed at the House Clerk's PTR archive (review:
research/THIRD_PARTY_REVIEW_day_trader_skill.md) and the data turned out to be parseable for free.

PRE-REGISTERED DESIGN (written before the result)
-------------------------------------------------
Data      : data/congress/congress_trades.csv (6,365 parsed transactions, 102 members, filed 2025-07-24 ..
            2026-11-19) joined to data/stocks/ (115 large caps). 1,186 transactions match a price series
            in 61 tickers: 616 purchases, 566 sales, 4 exchanges (dropped).
Events    : purchase = type 'P'; sale = type 'S' or 'S (partial)'.
Timing    : the event date is `filed_date`, NOT `transaction_date` — the STOCK Act allows a 45-day lag and
            a study that uses transaction_date is trading on information nobody had.
Target    : forward 21-trading-day total return of the stock from the first close at or after filed_date,
            expressed as EXCESS over the equal-weight mean of all 61 covered stocks over the same window
            (so a market-wide selloff cannot masquerade as an effect — this repo has been bitten by that
            before, see test_cot_panel.py).
Tests     : 1) difference in mean excess return: purchases − sales
            2) purchases vs a MATCHED CONTROL: for each purchase event, draw 200 random dates from the
               SAME ticker's own history and compute the same 21-day excess return. The distribution of the
               control mean is the null for "congressional buying dates are ordinary dates for this stock".
            3) the same two checks on the last 30% of events (by filings date).
Costs     : 2 bp per side, charged once per event (a 21-day hold, not a scalping strategy).
Bar       : purchases must beat their matched control at the 95th percentile AND purchases − sales must be
            positive, in BOTH halves. Otherwise FAIL, no exceptions.

KNOWN LIMITATIONS, STATED UP FRONT (they are why a pass here would still be weak evidence):
  * 16 months of filings, one market regime, one direction (a sharp selloff).
  * Only 61 large caps have price history in this workspace: the sample is exactly the stocks everyone
    already watches, where any information advantage is smallest.
  * Amounts are disclosure RANGES, so no position weighting beyond equal weight.
  * Filing is voluntary in timing within 45 days: even a real effect could be an artifact of WHEN people
    choose to disclose (they disclose winners late, losers early) — that artifact would show up as sales
    looking better, which is a useful built-in falsification check.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "artifacts" / "congress_trades.json"
H = 21
COST_BP = 2.0
N_CONTROL = 200


def main():
    tr = pd.read_csv(ROOT / "data" / "congress" / "congress_trades.csv")
    px = {}
    for p in sorted((ROOT / "data" / "stocks").glob("*.csv")):
        df = pd.read_csv(p, parse_dates=["date"])
        px[p.stem] = df.set_index("date")["close"].astype(float).sort_index()
    panel = pd.DataFrame(px).sort_index()
    ret = panel.pct_change()

    tr["filed_date"] = pd.to_datetime(tr["filed_date"], errors="coerce")
    tr = tr[tr["ticker_guess"].isin(panel.columns)].dropna(subset=["filed_date"])
    tr["side"] = np.where(tr["type"] == "P", "buy", np.where(tr["type"].astype(str).str.startswith("S"), "sell", None))
    tr = tr.dropna(subset=["side"]).sort_values("filed_date")
    print(f"  events: {len(tr)} ({int((tr.side=='buy').sum())} buys / {int((tr.side=='sell').sum())} sells) "
          f"in {tr.ticker_guess.nunique()} tickers, {tr.filed_date.min().date()} .. {tr.filed_date.max().date()}")

    def fwd_excess(ticker, when):
        """21-day forward return, excess over the equal-weight panel mean, entered at the next close."""
        idx = panel.index
        pos = idx.searchsorted(when, side="left")
        if pos + H + 1 >= len(idx):
            return np.nan
        entry, exit_ = idx[pos], idx[pos + H]
        r = panel[ticker].loc[exit_] / panel[ticker].loc[entry] - 1 - 2 * COST_BP / 1e4
        bench = (panel.loc[exit_] / panel.loc[entry] - 1).mean()
        return float(r - bench)

    tr["fwd_excess"] = [fwd_excess(t, d) for t, d in zip(tr["ticker_guess"], tr["filed_date"])]
    ev = tr.dropna(subset=["fwd_excess"]).copy()
    print(f"  events with a complete forward window: {len(ev)}")

    buys, sells = ev[ev.side == "buy"], ev[ev.side == "sell"]
    n = len(ev)
    cut = ev["filed_date"].quantile(0.70)
    halves = {"is": ev[ev.filed_date <= cut], "oos": ev[ev.filed_date > cut]}

    rng = np.random.default_rng(20261121)
    results = {}
    for label, sub in halves.items():
        b = sub[sub.side == "buy"]
        s = sub[sub.side == "sell"]
        diff = (b["fwd_excess"].mean() - s["fwd_excess"].mean()) if len(b) and len(s) else np.nan
        # matched control: same tickers, random dates
        obs = b["fwd_excess"].mean() if len(b) else np.nan
        ctrl_means = []
        for _ in range(N_CONTROL):
            vals = []
            for t in b["ticker_guess"]:
                ser = panel[t].dropna()
                if len(ser) < H + 30:
                    continue
                d = ser.index[rng.integers(0, len(ser) - H - 1)]
                v = fwd_excess(t, pd.Timestamp(d))
                if np.isfinite(v):
                    vals.append(v)
            if vals:
                ctrl_means.append(float(np.mean(vals)))
        ctrl = np.array(ctrl_means)
        pct = float((ctrl < obs).mean() * 100) if len(ctrl) else np.nan
        results[label] = {"n_buy": int(len(b)), "n_sell": int(len(s)),
                          "buy_mean_pct": round(float(b["fwd_excess"].mean()) * 100, 3) if len(b) else None,
                          "sell_mean_pct": round(float(s["fwd_excess"].mean()) * 100, 3) if len(s) else None,
                          "buy_minus_sell_pct": round(float(diff) * 100, 3) if np.isfinite(diff) else None,
                          "pct_vs_matched_control": pct,
                          "control_mean_pct": round(float(ctrl.mean()) * 100, 3) if len(ctrl) else None,
                          "control_p95_pct": round(float(np.percentile(ctrl, 95)) * 100, 3) if len(ctrl) else None}
        print(f"  {label.upper():<4} buys {len(b):>3} sells {len(s):>3} | buy {results[label]['buy_mean_pct']:+.2f}% "
              f"sell {results[label]['sell_mean_pct']:+.2f}% | diff {results[label]['buy_minus_sell_pct']:+.2f}pp "
              f"| buy vs control pct {pct:5.1f} (ctrl mean {results[label]['control_mean_pct']:+.2f}%, "
              f"p95 {results[label]['control_p95_pct']:+.2f}%)")

    ok = all(results[h]["pct_vs_matched_control"] is not None
             and results[h]["pct_vs_matched_control"] >= 95
             and (results[h]["buy_minus_sell_pct"] or -1) > 0 for h in ("is", "oos"))
    verdict_text = ("PASS (review)" if ok else
                    "FAIL — congressional filings carry no measurable edge on this 16-month large-cap sample")
    print(f"\n  VERDICT: {verdict_text}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"experiment": "EXP-0019", "hypothesis": "H21",
                               "design": __doc__.split("PRE-REGISTERED DESIGN")[1][:2600],
                               "events": int(len(ev)), "results": results,
                               "bar": "buy vs matched control >=95th pct AND buy-sell>0 in both halves",
                               "verdict": "PASS" if ok else "FAIL",
                               "verdict_note": "FAIL here is about a 16-month sample, not a proof of "
                                               "no effect; the sample must grow before H21 closes."},
                              indent=2, default=str))
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()
