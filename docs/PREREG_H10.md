# PRE-REGISTRATION — H10: the surviving reversion rule on a TRUE HOLD-OUT

**Written before any hold-out number was computed.** Date: 2026-11-20. Status: LOCKED once
EXP-0007 is appended to `research/EXPERIMENT_LOG.csv`.

## The problem this solves

EXP-0006 left one real result and one fatal weakness:

- P1R (9 EUR crosses, 1999–2026, measured costs) **passed all four pre-registered criteria**.
- But 1999–2026 has now been used to *discover* the effect. There is no untouched data left in that
  panel, so its Sharpe of 0.36–0.40 is an **in-sample** number no matter how many nulls it beats.

Also published, with a warning: the P&L is carried by EURJPY/EURCAD/EURCHF while EURSEK/EURNOK are
negative after their 44–48 pip spreads, and EURUSD shows no signal at all. Acting on that
attribution would be post-hoc selection — unless the instrument set is chosen by a rule that is
written down **before** returns are examined.

H10 does exactly that: **choose instruments by liquidity only, then test on years never used.**

## Universe selection rule (uses spread only, never returns)

From `data/spreads/*_hourly.csv`, compute each instrument's **median half-spread as % of notional
over 2003–2018 only** (all pre-holdout). Keep the **cheapest half** of the 10 measured instruments.

Computed result (verified before this file was written):

| Instrument | median half-spread 2003–2018 | kept |
|---|---:|---|
| EURUSD | 0.00362% | ✅ |
| GBPUSD | 0.00523% | ✅ |
| EURCHF | 0.00648% | ✅ |
| EURJPY | 0.00664% | ✅ |
| EURGBP | 0.00990% | ✅ |
| EURAUD | 0.01032% | ❌ |
| EURCAD | 0.01338% | ❌ |
| EURSEK | 0.01432% | ❌ |
| EURNZD | 0.01486% | ❌ |
| EURNOK | 0.01956% | ❌ |

**Universe = {EURUSD, GBPUSD, EURCHF, EURJPY, EURGBP}** — exactly 5 instruments, chosen with zero
reference to returns.

## Test period

**2019-01-01 → 2026-11-20 only.** No pre-2019 P&L is computed in the primary test. The pre-2019
spread data is used solely for selection and forecasting costs.

## Rule (locked)

- Weekly, Friday close. Signal = trailing **k = 2 weeks** return, cross-sectional rank.
- With 5 instruments: **long the bottom 2, short the top 2**, equal weight (½ each), dollar-neutral.
  (Stated explicitly because 5 does not divide by 3 — this is a size rule, not a tuned parameter.)
- Hold exactly one week; positions lagged one bar (QR-002 discipline, regression test required).
- Costs charged on every position change, using **measured** half-spreads for these 5 pairs:
  - `retail` regime = measured median spread 2019+ plus a 1.0 pip markup (the **verdict regime**)
  - `ecn` regime = measured only (reported for context)

## Criteria (all four required) — adjusted for the shorter hold-out

| # | Criterion | Threshold |
|---|---|---|
| A1 | Net Sharpe, 2019–2026, retail costs | **> 0.35** |
| A2 | Beats 1000-sim random-selection null | **null_pct ≥ 95** |
| A3 | Rolling **3-year** windows stepped 1 year (≈5 windows) positive | **≥ 60%** |
| A4 | Survives doubled retail costs | **> 0.20** |

A3 uses 3-year windows instead of 5 because the hold-out is 7.8 years long — that change is declared
here, before running, not after seeing results.

## Secondary (context only, cannot rescue H10)

All 9 EUR crosses on the same hold-out, tercile legs, same costs and criteria. Reported for
completeness; the primary verdict rests on the 5-pair liquidity-selected panel.

## Honest statement of power

7.8 years ≈ 407 weeks. With a true Sharpe of 0.35 the standard error of the estimated Sharpe is
roughly `sqrt(1/7.8) ≈ 0.36`, so **the confidence interval around any result here will span zero.**
A pass therefore means "consistent with the effect, not contradicted by fresh data", not "proven".
A fail is genuinely informative: it would say the 1999–2018 result does not carry into the regime
we would actually trade.

## What happens on each outcome

- **Pass**: P1R moves from "conditionally supported" to "supported on fresh data at estimated retail
  cost". Next step is a forward paper run; still no live trading.
- **Fail**: the cross-sectional reversion thread closes. The project then states plainly that its
  only surviving candidate failed its own out-of-sample test, and turns to a mechanism family never
  yet tested here (H11: volatility risk premium / carry), with no re-use of the reversion data.

_Registered 2026-11-20. Nothing in this file may be edited after EXP-0007 is run._
