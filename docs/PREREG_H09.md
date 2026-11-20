# PRE-REGISTRATION — H09: cross-sectional mean reversion

**Written before any code was run or any backtest number was looked at.**
Filed by: Alina Research Agent · Date: 2026-11-20 · Status: LOCKED once the first
result is appended to `research/EXPERIMENT_LOG.csv` as EXP-0005.

## Why this hypothesis exists

The corrected multi-asset screen (post QR-002, `reports/PORTFOLIO_DONCHIAN.md`) left exactly
one thread with independent corroboration: **mean reversion**, not trend.

- `Z_FADE` beat each asset's own buy & hold on AUDUSD (+0.26 Sharpe), GBPUSD (+0.23) and FTSE (+0.13).
- On the 27-year ECB data, `RANGE_FADE` was the only rule that **improved after 2013**
  (Sharpe +0.03 → +0.13) while every trend family decayed.
- These are three independent looks at the same underlying behaviour.

Until now everything was tested **one instrument at a time**. That wastes the cross-section:
reversion is a *relative* claim — when one currency/asset has run hot and its neighbour has not,
the spread between them should close. A time-series fade only sees its own history. This test
asks the question the way the literature does (Lehmann 1990; Lo & MacKinlay 1990;
Balvers, Wu & Gilliland 2000; Menkhoff et al. 2012 on FX mean reversion).

## Hypothesis

**H09a (primary, cross-sectional).** Ranking a fixed panel of instruments by their trailing
return and going **long the recent losers / short the recent winners** (dollar-neutral, weekly
hold) earns a positive return **net of cost**, and that return is not explainable by the null
of a random long/short selection with the same turnover.

**H09b (secondary, time-series).** The single-asset z-score fade (`Z_FADE`: fade a move of more
than 2σ from the 20-day mean, exit at the mean) is positive net of cost on the reversion cluster
identified above. This is the same mechanism tested in the panel form; if H09a fails and H09b
passes, the effect is idiosyncratic, not systematic.

## Panels (fixed now, not tunable later)

| Panel | Instruments | Source | Start |
|---|---|---|---|
| **P1 "FX8"** | EURUSD, EURGBP, EURCHF, AUDUSD, AUDNZD, AUDCAD, AUDCHF, AUDEUR | ECB / RBA official daily (`data/official/`) | 1999 |
| **P2 "MULTI12"** | FTSE, DAX, SP500, NIKKEI, HSI, GOLD, SILVER, WTI, COPPER, TLT, EURUSD, USDJPY | Yahoo daily (`data/universe/`) — shape only, never absolute levels | 2000 |

Yahoo FX is capped at 2003–2006 start and carries bad prints up to 13.8%, so P2's FX legs are
included for the cross-section only; P1 remains the clean FX record. Both panels are reported
separately and **must both pass** for H09a to be accepted (a rule that only works on Yahoo's
dirty FX data is not a finding).

## Rules (locked)

- Frequency: **weekly**, Friday close. Signals from complete weeks only.
- Signal: past `k`-week return of each instrument, cross-sectionally ranked each week.
- Position: **long the bottom third, short the top third**, equal weight inside each leg,
  dollar-neutral (sum of weights = 0), gross exposure 1.0 per leg. Hold exactly one week.
- `k = 2` weeks is the **primary**. `k ∈ {1, 4, 12}` are **exploratory only** and reported with a
  Bonferroni note (4 primary-family tests → require p < 0.0125 for any of them to count).
- Benchmark: same panel, equal-weight buy & hold (the D10 bar), plus a cash line.
- H09b: `Z_FADE` exactly as implemented in `screen_universe.py` (20-day mean, 2σ band, exit at
  mean), unchanged, lagged one bar per QR-002.

## Costs (charged, not assumed away)

Per unit of turnover, half-spread each side, by class:
fx 0.013%, index 0.02%, metal 0.03%, energy 0.06%, bond 0.03%, crypto n/a here.
Turnover is `sum(|w_t − w_{t−1}|)` measured **after** the one-week lag, so no cost-free entry.

## Walk-forward protocol

Rolling **5-year windows stepped 1 year** across the full sample (≈23 windows for P1).
No parameter is fitted inside any window — the rule has no free parameters, so walk-forward
here measures **stability over time**, not optimised generalisation. That is stated plainly
because it is a weaker claim than "optimised out-of-sample".

## Null control

1000 simulations per test. Each simulation re-draws the weekly long/short **selection at random**
while matching the real strategy's number of legs and its turnover, then charges the same costs.
`null_pct` = percentile of the real net Sharpe inside that distribution.

## Accept / reject criteria (all four required for H09a)

| # | Criterion | Threshold |
|---|---|---|
| A1 | Net Sharpe, full sample, cost charged | **> 0.35** |
| A2 | Beats random-selection null | **null_pct ≥ 95** |
| A3 | Stability across rolling 5y windows | **net Sharpe > 0 in ≥ 60%** of windows |
| A4 | Survives doubled costs | **net Sharpe > 0.20** at 2× cost |

H09b uses the same four criteria on its single-asset cluster.

**If any criterion fails → REJECTED. No retuning of `k`, no changing the tercile, no dropping a
panel, no re-splitting the sample after seeing results.** A rejection is a result and gets published
as one (this project already has four rejected experiments; a fifth is not a crisis).

## What a PASS would and would not mean

- A pass means: a small, dollar-neutral, cost-charged reversion premium exists in these panels.
  It would still be **untradeable at retail** until T18 measured spreads land, because the
  threshold is 0.35 Sharpe and assumed costs are within a factor of ~2 of the truth.
- A pass does **not** mean it is worth money at size. With 8–12 instruments and weekly rebalancing,
  capacity is tiny and the cost assumption dominates the result.
- A fail means the thread is closed: the project then reports, honestly, that after 27 years of
  official FX data, 24 assets, 7 documented rules and a cross-sectional test, **no retail-accessible
  edge has been found**, and lists what would be needed to look further.

_Registered 2026-11-20. Artifacts this will produce: `research/artifacts/h09_xs_reversion.json`,
`reports/H09_XS_REVERSION.md`, EXP-0005 row in `research/EXPERIMENT_LOG.csv`._
