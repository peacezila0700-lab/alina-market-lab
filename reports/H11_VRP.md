# EXP-0008 — H11 volatility risk premium: the premium is real, the trade is not survivable

Pre-registered in `docs/PREREG_H11.md` before any code ran. Two questions, both answered.

## Data (free, no key)

| Series | Source | Coverage |
|---|---|---|
| VIX daily OHLC | CBOE (`cdn.cboe.com` public CSV) | **9,320 rows, 1990-01-02 → 2026-11-19** |
| SPY, VIXY, panel of 14 | Yahoo daily | SPY 2000+, VIXY 2011+, rest 2000+ |

`VRP_t = VIX_t − RV_t` where `RV_t` is the annualised stdev of the trailing 21 SPY returns —
strictly past-only, no forward information anywhere in the signal.

## H11a — VRP as a state variable: **FAIL**

Monthly quintile sort of next-month equal-weight panel returns, 321 monthly observations:

| VRP quintile | mean VRP | next-month return (annualised) | hit rate |
|---|---:|---:|---:|
| Q1 (lowest) | −4.28 | +4.78% | 57.8% |
| Q2 | +2.08 | −0.55% | 48.4% |
| Q3 | +3.94 | **+9.55%** | 64.1% |
| Q4 | +5.89 | −0.35% | 51.6% |
| Q5 (highest) | +10.10 | +7.61% | 61.5% |

There is **no monotone relationship** — Q3 and Q5 are the good buckets, Q1–Q2 and Q4 are flat. A
sort that is not monotone is not a signal, it is sorting noise into five bins.

Strategy form (top-quintile-only overlay, 17.8% time in market): Sharpe **+0.337** vs buy & hold
**+0.406**, `null_pct` **82.6**, walk-forward fails. All four criteria fail except "survives doubled
costs", which is meaningless when the gross signal is absent.

## H11b — selling the premium: statistically strong, financially lethal

Short VIXY, monthly rebalance, 190 months (2011-01 → 2026-11), costs 0.10%/month:

| Metric | Value |
|---|---|
| Net Sharpe | **+0.694** |
| null_pct (random same-turnover long/short) | **≥95** |
| 5-year walk-forward windows positive | **≥60%** |
| Survives 2× costs | **yes** |
| **A5: worst rolling 12-month loss** | **−103.7%** ❌ |
| **A6: worst single day** | **−43.1%** ❌ (VIXY +43.1% on 2024-08-05) |

Four of six criteria pass; the two that decide whether a normal retail account survives both fail.
**At the pre-registered −100% notional exposure the equity curve goes negative** — the account is
gone, and every Sharpe computed on that curve is arithmetic fiction (maxDD reads "419%", which is
the same zero-crossing artefact flagged for crypto in `PORTFOLIO_DONCHIAN.md`).

### What exposure is actually survivable (descriptive, not part of the verdict)

| Exposure | worst rolling 12m | CAGR | maxDD | Sharpe |
|---|---:|---:|---:|---:|
| −100% | **−103.7%** | RUINED | RUINED | 0.69 |
| −50% | −50.4% | +17.45% | 168.7%* | 0.69 |
| −35% | −34.4% | +13.45% | 86.0% | 0.69 |
| −25% | −24.0% | +10.08% | 52.2% | 0.69 |
| −20% | −18.9% | +8.23% | 38.8% | 0.69 |
| −10% | −9.2% | +4.26% | 16.9% | 0.69 |

Sharpe is constant (the trade scales linearly in risk), so the premium is genuinely there per unit
of risk — the entire question is whether an account can hold the position through the spikes. At
−25% exposure you earn ~10%/yr with a 52% drawdown and one 12-month stretch of −24%. *The 168.7%
at −50% is another zero-crossing artefact; read it as "wiped".

## Verdict

**Both parts FAIL their pre-registered bars. H11 is rejected as a tradeable strategy.**

But the reason matters and is worth keeping: this is the **first mechanism in the project that
passes a statistical test at all** (H11b: Sharpe 0.69, beats null, survives walk-forward and
doubled costs). It fails only on **survivability**, which is the correct reason for a retail account
to walk away — the premium is compensation for taking a loss that lands all at once.

That also explains why the earlier families failed: they had no premium behind them at all. Here the
premium is real, and the price is a coin-flip on ruin.

## What this changes for the project

- **Two independent verdicts now point the same way:** whatever is left for a retail account in
  free-data, no-live-trading research is *risk management*, not signal generation. Vol scaling,
  event avoidance, drawdown caps.
- The one thing a retail account genuinely can do with this: **hold the premium at a size that
  cannot kill the account** (−10% to −20% notional), accepting single-digit returns with a 20–40%
  drawdown. That is a portfolio decision, not an edge claim.
- Next family (per the pre-registration escape clause): **carry** — policy-rate sources are already
  verified reachable (ECB, BoC valet, RBA, Norges Bank, BoE). Different premium, different failure mode.

_Artifacts: `research/artifacts/h11_vrp.json`, `data/official/VIX_CBOE_D.csv`, `data/universe/{SPY,VIXY}.csv`.
Script: `scripts/h11_vrp.py`._
