# HYPOTHESIS REGISTER — notes, ranking and pre-registration

- **Created:** 2026-11-20 · **Stage:** 5 (Hypothesis Factory) · **Register:** `research/HYPOTHESIS_REGISTER.csv`
- **Status:** proposed — awaiting owner approval of test order

## A. Honest disclosure before anything else

These hypotheses were **generated from the same 10-year dataset** that will be used to test them.
That is contamination by construction, and no amount of in-sample elegance fixes it.
Consequences, accepted up front:

1. The in-sample block can only be used to **measure mechanics** (trade counts, cost drag, stop-outs),
   never to claim an edge.
2. The **validation block (2024-01-01 → 2025-05-31)** is the first honest test.
3. The **locked OOS block (2025-06-01 → 2026-11-20)** is touched **once**, at the end, and its result
   is reported whether it is good or bad.
4. If H01 fails on validation, the correct action is **not** to re-tune H01. It is to log
   the failure and move to the next hypothesis.

## B. Ranking (why H01 first)

Score = 0.40·value-of-information + 0.30·data feasibility + 0.15·(6 − impl cost) + 0.15·(6 − false-discovery risk)

| rank | id | score | what it buys |
|---|---|---|---|
| 1 | H01 | 4.25 | the only hypothesis that, if true, is a tradeable rule |
| 2 | H02 | 3.85 | reuses H01's code; tells us whether the long side should exist at all |
| 3 | H03 | 3.30 | a filter on H01 — meaningless until H01 is measured |
| 4 | H04 | 3.30 | 6 variants on one entry rule = highest multiple-testing risk; last |

`EXPERIMENT BUDGET: 4 of 12 hypotheses used. A full project review is triggered at 12.`

## C. The one recommended first experiment — EXP-0001

- **Hypothesis:** H01 · **Rule:** frozen as written in the register (no tuning, no "try 1.8 vs 2.2")
- **Data:** canonical D1 (2,592 bars) + cost = 0.9 pip round trip, swap 0.0 and 0.3 pip/night as bounds
- **Benchmarks (both mandatory):**
  - B0: no-trade (net expectancy = 0)
  - B1: random entries with the same count, holding and cost — the honest "is this better than luck" test
- **Reported per block (IS / validation / OOS separately, never pooled):**
  trade count, net expectancy, profit factor, max drawdown, win rate, average holding,
  cost contribution in pips, exposure, block-bootstrap 95% CI of net expectancy
- **Pass condition:** net expectancy > 0 with CI excluding 0 **in the validation block**, and not
  driven by ≤5 trades, and not contradicted in OOS.
- **Fail condition:** anything else. Failures are logged in `EXPERIMENT_LOG.csv` and kept.

## D. Known weaknesses of this register (write them down while they are still uncomfortable)

1. **Entry-only asymmetry.** H01 tests the short side because the data showed the short side.
   That is selection. H02 exists specifically to price that in.
2. **Few independent events.** z ≥ +2 occurs ~7 times a year. Ten years ≈ 70 entries, and the
   20-day windows overlap, so the effective number of independent episodes is far smaller.
   Any t-statistic computed on overlapping windows is decorative.
3. **Swap is unknown.** The cost model is missing broker financing. If EURGBP shorts pay
   materially, H01's edge can invert. → blocked on broker spec (T11).
4. **Price data is not execution-grade.** Vendor open==close in ~39% of bars; fills are modelled
   from closes with an explicit slippage assumption, not from real fills.
5. **Regime dependence.** 2022 (range 19%) looks nothing like 2023-2026 (5-7%). A rule that only
   works in quiet ranges is a bet on the next regime being quiet. H03 exists to test that.

## E. What would make me recommend abandoning the direction entirely

- H01 and H02 both fail on validation **and** the failure is not explained by cost (i.e. gross is also ≤ 0)
- The effect exists only when costs are assumed below the measured Dukascopy median (0.9 pip)
- The effect is concentrated in 2020-2022 (COVID/energy shock) and absent in calm years

## F. Next action

Owner approves the test order → **T09**: build the backtest engine with unit tests
(next-bar execution, spread, swap, stops, time stops, trade ledger), then run EXP-0001.

## H07 — Scheduled macro events raise realised volatility (SUPPORTED, not tradeable directly)
- FOMC decision windows: mean |move| is higher on all 6 tested assets, Welch t 2.09–2.84 for
  5 of 6. Consistent with the event-risk literature.
- Consequence: event risk is real but the *direction* is unpredictable; the usable form is
  sizing/avoidance around known dates, which needs measured spread (T18) to price.

## H08 — Free public attention predicts next-day volatility (PARTIALLY SUPPORTED, rejected as edge)
- Spearman(attention z, next-day |ret|): BTC 0.164, ETH 0.141, WTI 0.068, USDJPY 0.066,
  GOLD 0.043, EURUSD 0.035, SP500 0.035, COPPER −0.021.
- Beats the realised-vol baseline on MAE in 6/8 assets but not in R² (3/8) and not in portfolio
  Sharpe. Rejected as a signal; retained as a regime/narration layer.

## H09 — cross-sectional + time-series mean reversion (EXP-0005, REJECTED)
- Pre-registered (`PREREG_H09.md`, commit f2ce077) with A1–A4 thresholds before code ran.
- First panel was defective (5 of 8 official FX files held only 977 bars, 2023+) → AMENDMENT1
  replaced it with P1R EUR9 (9 ECB EUR crosses, 7,203 rows each from 1999-01-04).
- **P1R k=2 weekly tercile, dollar-neutral, 1999–2026:** Sharpe **+0.343** (bar 0.35 → FAIL),
  CAGR +2.41%, vol 7.84%, maxDD 27.1%, null_pct **100.0**, WF+ **77.3%**, 2× cost **+0.181**
  (bar 0.20 → FAIL). Closest miss in the project's history.
- **P2 MULTI12:** +0.152, WF+ 57.1%, 2× cost +0.020 → fails three criteria. Not a cross-asset effect.
- **H09b z-fade:** FTSE +0.336 (fails A1 only), GBPUSD +0.085, EURUSD −0.161,
  AUDUSD +0.981 but on **977 bars** → null_pct 99.2 is not evidence at that length.
- **Cost boundary:** clears all four bars at **0.75×** the assumed 0.013% half-spread. The verdict is
  a statement about our cost assumption, not about the market → T18 is now the highest-value task.
- Rolling 5y Sharpe peaked 2009–2016 (+0.5…+0.9), now +0.28–0.35 → same post-2013 decay as every
  other family tested.

## H09b status update / EXP-0006 — measured costs change the verdict for P1R only
- T18 produced REAL spreads (Dukascopy bid/ask, 2003-2025). EURUSD 1.0 pip (2003) -> 0.3 pip (2013+).
- Under measured costs P1R passes A1-A4 (ECN +0.402, retail+1pip +0.358). P2 still fails.
- Pre-registration demanded both panels -> **H09 not accepted**. P1R = "conditionally supported".
- Economics: 97x annual turnover, gross +3.96%, cost -1.15%, net +2.53%, Sharpe 0.36, maxDD 26%,
  corr to buy & hold -0.013. Thin but market-neutral and real by every test we can run in-sample.
- Per-leg: EURJPY/EURCAD/EURCHF carry it; EURSEK/EURNOK net negative (spreads 44-48 pips);
  EURUSD has no signal. Acting on that = post-hoc selection -> must be H10 pre-registered first.
- Only remaining confirmation: forward paper run at the owner's actual broker cost.
