# PROJECT REVIEW #1 — hard stop at six hypotheses

**Date:** 2026-11-20 · **Trigger:** hypothesis budget 6 of 12 used, and both mechanism families
now fail with adequate sample · **Prepared by:** Alina

---

## 1. Executive summary in five lines

1. The range behaviour of EURGBP is **real** and measured on 26 years (Hurst 0.358, VR60 0.516).
2. **Four structurally different rules failed to monetise it**: D1 fade, 26y × 5-pair replication,
   H1 intraday fade, H1 intraday breakout.
3. The failures are **not tuning problems**: the D1 result was indistinguishable from random,
   and the H1 breakout was *significantly negative* (CI [−4.27, −1.54]).
4. **Both directions lose after costs** (−1.7 fade, −2.9 chase vs 1.3 pips round trip).
   That is the fingerprint of cost + adverse selection, not of a missing filter.
5. Nothing here justifies paper trading, let alone live trading. **Zero validated edge.**

## 2. Evidence table

| exp | sample | rule | trades | result | verdict |
|---|---|---|---|---|---|
| EXP-0001 | D1 10y | fade z≥2 | 14 | +68 pips, CI [−7.5, +164.8] | inconclusive (power) |
| EXP-0002 | D1 26y × 5 pairs | same, frozen | 94 clean | +5.81, PF 1.06, CI [−52.6, +67.7] | rejected (random band, sign flips) |
| EXP-0003 | H1 2y | intraday fade | 158 | IS −1.66, VALID +0.97 (CI spans 0) | rejected (3/4 criteria) |
| EXP-0004 | H1 2y | breakout, compression | 311 | IS **−2.93, CI [−4.27, −1.54]** | rejected (significantly negative) |

## 3. What is permanently established (assets, not opinions)

- **Data governance**: 4,186 logged repairs; Sunday→Friday relabel discovered and quantified;
  bad print at EURGBP 0.97900 (2022-10-07) removed and documented; SHA-256 manifest per dataset.
- **Engine integrity**: next-bar fills, truncation test for look-ahead, cost applied once,
  ledger reconciliation — 13 unit tests, all passing.
- **Method**: pre-registration committed *before* each run; block/day-cluster bootstrap;
  random-entry benchmark; block-split reporting; failures kept in the log, never deleted.
- **Cost arithmetic**: financing dominates spread at multi-day holds
  (break-even win rate 53.2% → 72.0%). Therefore any future design should be intraday.
- **Power arithmetic**: intraday gives ~79 trades/year on one pair vs 1.4 trades/year on D1.

## 4. What is blocked

| blocker | consequence |
|---|---|
| No measured H1 spread | every cost figure is an assumption; a 0.7-pip error is ~50% of the observed edge |
| No swap/financing spec | long-hold strategies cannot be priced at all |
| Yahoo H1 ceiling 730d | 2–3 regimes only; a pass would still be weak evidence |
| Dukascopy bulk feed rate-limited | free 20y tick source is unreachable from this sandbox |

**One file from the owner (MT5 History Center export) removes three of these four blockers.**

## 5. Recommended options (owner decision)

| | option | what it buys | risk |
|---|---|---|---|
| **A** | Get the MT5 export, then re-run EXP-0003/0004 with the **real** spread | turns assumptions into measurements; may flip or confirm | low |
| **B** | Stop here; keep the negative results as the deliverable | saves time; the answer "no edge found under these conditions" is itself useful | none |
| **C** | Change arena: different market (indices/gold) or much longer horizon (weekly/monthly) | escapes the 1.3-pip/5.9-pip geometry that killed H1 | needs new data; more work |
| **D** | Keep mining H1 with new thresholds/filters | — | **forbidden** — would burn credibility without new information |

**My recommendation: A, and if A is not possible this week, then B.**
Not C yet — because C inherits the same unmeasured-cost problem.
Not D ever.

## 6. Honest statement about what this project has and has not achieved

It has **not** produced a trading strategy. It has produced something that most retail
quant projects never produce: **a trustworthy "no"**, with the machinery to test the next
idea in one session instead of one month.

If the owner wants a profitable system, the next bottleneck is not modelling skill —
it is **data quality and cost measurement**. Everything else is already built.

## 7. Budget status

- Hypotheses tested: 6 of 12 · Experiments logged: 4 · Failed/aborted runs retained: all
- Money spent: **0** · Services subscribed: **0** · Live orders ever sent: **0**
