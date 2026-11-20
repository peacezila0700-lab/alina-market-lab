# EXP-0007 — H10 hold-out test: **FAILED**

Pre-registered in `docs/PREREG_H10.md` **before any hold-out number was computed.**
Universe was chosen by a liquidity rule using **2003–2018 spreads only** — zero reference to
returns — then tested on **2019-01-01 → 2026-11-20** only.

## Universe (chosen ex ante, cheapest half of the 10 measured instruments)

{EURUSD, GBPUSD, EURCHF, EURJPY, EURGBP} — 0.0036% to 0.0099% median half-spread, 2003–2018.
Excluded by rule: EURAUD, EURCAD, EURSEK, EURNZD, EURNOK (all above 0.010%).

## Results

| Panel | Regime | Sharpe | CAGR | maxDD | 2× cost | 3y windows positive | null_pct | A1 | A2 | A3 | A4 | Verdict |
|---|---|---:|---:|---:|---:|---:|---:|:--:|:--:|:--:|:--:|---|
| **PRIMARY (5 liquid)** | **retail (verdict)** | **+0.126** | +0.40% | 28.2% | +0.069 | **16.7%** | 93.3 | ❌ | ❌ | ❌ | ❌ | **FAIL** |
| PRIMARY (5 liquid) | ecn | +0.158 | +0.52% | 26.4% | +0.133 | 16.7% | 95.7 | ❌ | ✅ | ❌ | ❌ | **FAIL** |
| SECONDARY (all 9 EUR crosses) | retail | +0.202 | — | — | — | 20.8% | — | ❌ | — | ❌ | — | FAIL |

Against the pre-registered bars: A1 needs >0.35 (got 0.126), A3 needs ≥60% of 3-year windows
positive (got 16.7% — **one window out of six**), A4 needs >0.20 at doubled cost (got 0.069).

Null_pct 93.3 means the real strategy did not even clearly beat random long/short selection with
the same turnover over this window.

## What this means

1. **The thread closes.** `PREREG_H10.md` said a fail means the cross-sectional reversion thread
   ends the project's involvement with it. That is now the case. No retuning, no "but with 7 pairs
   instead of 5", no moving to a different k.
2. **EXP-0006's "conditionally supported" is now resolved — negatively.** The pooled 1999–2026
   number (+0.36 retail) was carried by 1999–2018. On fresh data the same rule, the same criteria
   and *better* instrument selection produce 0.126. That is the cleanest in-sample/out-of-sample
   gap the project has recorded, and it is exactly why the hold-out was registered.
3. **The 2019–2026 regime** — post-2013 spread compression plus faster arbitrage — kills slow
   weekly FX reversion at retail cost. Three independent tests now agree: FX trend rules ≈0
   (27y ECB), cross-sectional reversion fails out-of-sample, single-asset z-fade fails A1.
4. **Honest tally of the whole project:** 7 documented rule families × 24 assets, 27 years of
   official FX data, 5 pre-registered experiments, 14/14 engine tests, a random null on every
   test — and **zero validated edges**. One bug was caught (QR-002) that had produced a fake
   +30% CAGR. The repository is, so far, a well-documented account of what does *not* work at
   retail cost, which is worth more than a backtest that flatters itself.

## Incidental data finding (QR-003)

GBPUSD had to be built as a cross (`EURUSD / EURGBP`) from the two official ECB series. Verifying
it exposed something worse about the shortcut channel:

| Check | Result |
|---|---|
| Cross vs Yahoo GBPUSD, **level** correlation | 0.9995 (cross is correct) |
| Cross vs Yahoo GBPUSD, **daily return** correlation | 0.52 |
| ECB EURUSD vs Yahoo EURUSD, daily return correlation | **0.38** |
| Lag −2…+2 on returns | no lag fixes it (0.52 → 0.32 at ±1) |

Levels agree, daily returns do not. Yahoo FX is stamped at a different daily snapshot than the ECB
14:15 CET fix, so its returns are **not** usable as a substitute for official fixes — stronger
language than the earlier "shape only" note. Any earlier Yahoo-FX-based result in this repo
(`P2_MULTI12`, the FX rows of `universe_screen`) carries this caveat; none of them is a live finding.

_Artifacts: `research/artifacts/h10_holdout.json`, `data/official/GBPUSD_ECB_D.csv` (7,141 rows,
cross-derived). Script: `scripts/h10_holdout.py`._
