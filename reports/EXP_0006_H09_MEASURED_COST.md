# EXP-0006 — H09 re-scored with MEASURED costs (T18 done)

**Read EXP-0005 first (`reports/H09_XS_REVERSION.md`). It stands as the registered test and it was REJECTED.**
This experiment changes **one input only** — the cost vector — and is labelled a re-score, not a pass.

## What was measured, and how

The `.bi5` datafeed host returns HTTP 503, so the measurement uses Dukascopy's public chart API
instead: the same instrument is queried twice per timestamp, once with `offer_side=B` (bid) and once
with `offer_side=A` (ask), then aligned by timestamp. Quoted spread = ask − bid, observed. Free, no
key, no signup, four anchor timestamps × 30,000 hourly bars each covering **2003 → 2025**.

Note the quirk that had to be solved: the path and instrument must be URL-encoded
(`path=chart%2Fjson3`, `instrument=EUR%2FUSD`) or the API answers `_callbacks____error([null])`.

## Measured spread, pips, median of hourly bars per year

| Instrument | 2003 | 2008 | 2012 | 2015 | 2019 | 2022 | 2025 | half-spread % now | vs our old assumption |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| EURUSD | 1.0 | 1.5 | 0.9 | 0.3 | 0.3 | 0.4 | 0.5 | 0.0013% | **10× cheaper** |
| EURJPY | 2.0 | 2.0 | 1.6 | 0.8 | 0.6 | 1.1 | 1.1 | 0.0034% | 3.9× cheaper |
| EURGBP | 1.6 | 2.0 | 1.3 | 0.9 | 0.9 | 1.1 | 0.8 | 0.0050% | 2.6× cheaper |
| EURCHF | 2.0 | 2.5 | 1.7 | 1.7 | 1.0 | 1.4 | 1.2 | 0.0053% | 2.5× cheaper |
| EURCAD | — | 5.5 | 2.5 | 2.2 | 1.9 | 2.5 | 2.4 | 0.0068% | 1.9× cheaper |
| EURSEK | — | 27 | 30 | 32 | 21 | 48 | 48 | 0.0165% | **1.3× MORE expensive** |
| EURNOK | 32 | — | 30 | 37 | 20 | 55 | 50 | 0.0189% | **1.5× MORE expensive** |
| EURAUD | — | 4.5 | 2.1 | 2.1 | 2.0 | 2.5 | 2.7 | 0.0073% | 1.8× cheaper |
| EURNZD | — | 7.0 | 4.5 | 5.0 | 3.1 | 3.8 | 4.3 | 0.0095% | 1.4× cheaper |
| GBPUSD | 2.0 | 2.0 | 1.7 | 1.0 | 1.0 | 1.1 | 0.9 | 0.0039% | 3.4× cheaper |

The single most important number in this project: **EURUSD went from 1.0 pip to 0.3 pips between
2003 and 2013 and has stayed there.** Every decay story in `DECISION_LOG`/`EXPERIMENT_LOG` happens
in that window.

## Three cost regimes, identical rules and criteria (`PREREG_H09.md` A1–A4 unchanged)

| Cost regime | P1R Sharpe | CAGR | maxDD | 2× cost | WF+ | null_pct | A1 | A2 | A3 | A4 | Verdict |
|---|---:|---:|---:|---:|---:|---:|:--:|:--:|:--:|:--:|---|
| assumed 0.013% (EXP-0005) | +0.343 | +2.41% | 27.1% | +0.181 | 77.3% | 100.0 | ❌ | ✅ | ✅ | ❌ | **REJECTED** |
| **measured ECN** | **+0.402** | +2.89% | 23.3% | +0.300 | 77.3% | 100.0 | ✅ | ✅ | ✅ | ✅ | **PASS** |
| **measured + 1 pip retail markup** | **+0.358** | +2.53% | 26.0% | +0.211 | 77.3% | 100.0 | ✅ | ✅ | ✅ | ✅ | **PASS** |

P2 MULTI12 fails under all three regimes (+0.15 Sharpe, WF+ 57%, 2× cost +0.03, maxDD 249% —
an equity curve crossing zero). The pre-registration required **both panels** to pass, so:

> **H09 is NOT formally accepted.** P1R (official ECB data, 27 years, 9 EUR crosses) is now
> "conditionally supported pending a forward test at the owner's broker". P2's failure is not
> explained away — a cross-asset version of the same idea does not work.

## The economics, so nobody mistakes this for a money printer

| Item | Value |
|---|---|
| Annual turnover | **97× notional** (weekly rebalance, ~3 legs each side) |
| Gross return | +3.96%/yr |
| Cost drag (retail regime) | −1.15%/yr |
| Net | +2.53%/yr, vol 7.8%, Sharpe 0.36, maxDD 26%, hit rate 51.2% |
| Correlation to equal-weight buy & hold | **−0.013** (genuinely market-neutral) |
| Best years | 2009 +23.3%, 2016 +14.4%, 2011 +14.2%, 2023 +10.9% |
| Worst years | 2006 −8.7%, 2002 −6.5% |

A 0.36-Sharpe, market-neutral, 97× turnover strategy is a **thin** business: the cost model is 29%
of the gross return, and a retail account that quotes EURUSD at 1.5 pips instead of 1.0 turns this
into nothing.

## Per-leg attribution (descriptive only — see the warning underneath)

| Pair | own Sharpe | reads |
|---|---:|---|
| EURJPY | +0.34 | the engine |
| EURCAD | +0.29 | strong |
| EURCHF | +0.27 | strong |
| EURNZD | +0.13 | positive |
| EURGBP | +0.10 | weak |
| EURAUD | +0.07 | weak |
| EURNOK | +0.04 | **eaten by 44-pip spreads** |
| EURSEK | −0.06 | **eaten by 48-pip spreads** |
| EURUSD | −0.08 | no signal at all |

⚠️ **This table is a trap and is labelled as one.** Dropping SEK/NOK because their P&L is negative
after the fact is exactly the post-hoc selection this project exists to prevent. Acting on it
requires a *fresh* pre-registration where the instrument set is chosen by a rule written down
**before** looking at P&L (e.g. "only pairs whose measured spread is below 0.5 pip"). That is H10,
and it is not run yet.

## Status and what would actually settle it

1. **EXP-0005 stands REJECTED** on assumed costs. This re-score does not overturn it; it replaces a
   guess with a measurement and shows the guess was the reason for the rejection.
2. **Dukascopy is not the owner's broker.** The retail row is measured + 1 pip — a plausible
   standard account, still an assumption. T18 finishes only with the owner's MT5 export.
3. **The only honest confirmation left is forward.** The full 1999–2026 history has now been used
   for the estimate, so no holdout remains. The next step is a paper-traded forward run of the
   exact locked rule (k=2, tercile, weekly, dollar-neutral) from 2026-11-20 with the cost of the
   owner's actual account, recorded weekly. No live trading (standing rule).
4. This is the first result in the project that survived its own null, its own walk-forward and a
   measured cost: **0.36 Sharpe, market-neutral, 97× turnover, thin.** That is what a real,
   small, retail-accessible edge looks like — not a 30% CAGR.

_Artifacts: `research/artifacts/h09_{assumed,ecn,retail}.json`, `data/spreads/*.csv`,
`data/spreads/MEASURED_COSTS.json`, `reports/MEASURED_SPREADS.md`, `reports/H09_XS_REVERSION_{ecn,retail}.md`.
Scripts: `scripts/measure_spreads.py`, `scripts/h09_xs_reversion.py` (`COST_SCENARIO=ecn|retail`)._
