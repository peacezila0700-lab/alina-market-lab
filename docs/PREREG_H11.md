# PRE-REGISTRATION — H11: volatility risk premium (a mechanism family never tested here)

**Written before the test was coded or run.** Date: 2026-11-20. Status: LOCKED once EXP-0008 is
appended to `research/EXPERIMENT_LOG.csv`.

## Why this family, and why now

Every test so far (trend, breakout, cross-sectional reversion, single-asset fade) is a **price
pattern** claim. All of them failed out-of-sample. H11 tests a different source of return:
**being paid to carry risk that other people want to shed.** Specifically, implied volatility is
persistently above subsequently realised volatility, and the difference (the variance risk premium)
is documented in the literature (Carr & Wu 2009; Bollerslev, Tauchen & Zhou 2009). It is a
risk-transfer premium, not a pattern — and it is the only major family this project has not touched.

Data is free and complete: CBOE publishes the full VIX history (9,321 rows from 1990-01-02), and
retail-tradeable volatility ETPs (VIXY from 2011, UVXY from 2011) exist precisely so a retail
account can hold the other side.

## Two separate questions (both must be answered; they are not the same trade)

### H11a — is the VRP a usable *state variable*?

- `VRP_t = VIX_t − RV_t`, where `RV_t` = annualised standard deviation of daily SPY returns over the
  **trailing** 21 trading days (trailing only; no forward information anywhere).
- Panel: the 12 liquid instruments of `P2_MULTI12` (FTSE, DAX, SP500, NIKKEI, HSI, GOLD, SILVER,
  WTI, COPPER, TLT, EURUSD, USDJPY) plus SPY and VIXY = 14.
- Test: monthly buckets (month-end signal, next-month return). Sort months into quintiles by `VRP_t`
  and compare mean next-month returns across quintiles, pooled over assets.
- Strategy form: hold the equal-weight panel when `VRP_t` is in the top quintile of its own trailing
  5-year history, hold cash otherwise. Monthly rebalance, cost charged per switch.

### H11b — is *selling* the premium survivable at retail?

- Instrument: **VIXY** (ProShares VIX short-term futures ETP, retail-tradeable, 2011-01 → 2026-11).
- Rule: hold **short VIXY**, rebalanced monthly to constant notional exposure of −100% of equity.
- Costs: 0.08%/month financing+borrow (assumption, disclosed), plus 0.02% per rebalance.
- This is the actual trade the premium pays for, so it must be tested, not just described.

## Walk-forward and null

- Same protocol as every prior experiment: rolling 5-year windows stepped 1 year.
- Null for H11a: **1000 shuffles of the VRP series** (destroying the VRP↔return link while keeping
  its distribution and autocorrelation via block-shuffling in 12-month blocks), recomputing the
  quintile spread each time.
- Null for H11b: 1000 random monthly long/short series with the same turnover — establishes whether
  the premium is distinguishable from leverage/luck.

## Accept / reject criteria

| # | Criterion | Threshold | Applies to |
|---|---|---|---|
| A1 | Net Sharpe (cost charged) | **> 0.35** | both |
| A2 | Beats its null | **null_pct ≥ 95** | both |
| A3 | Rolling 5y windows positive | **≥ 60%** | both |
| A4 | Survives doubled costs | **Sharpe > 0.20** | both |
| **A5** | **Retail survivability: worst rolling 12-month loss** | **< 35% of equity** | H11b only |
| **A6** | **No single day worse than −20%** | hard limit | H11b only |

A5/A6 are registered because a premium that pays 8%/yr and vaporises 80% in a week is not an edge
for a normal retail account — it is a lottery ticket with the sign flipped. The project's standing
rule is a normal retail broker account, not a fund that can absorb a vol spike.

## What each outcome means

- **H11a passes, H11b fails**: the VRP is real information about forward returns but the direct
  short-vol trade is unsurvivable → usable only as a *sizing/risk* input, same status as the
  attention layer (diagnostic).
- **Both pass**: first tradeable candidate in the project; next step is a forward paper run and a
  measured borrow/financing cost from the owner's broker.
- **Both fail**: the project states that even a documented risk premium does not survive retail
  costs and retail survivability constraints, and the next family to test is carry (needs central
  bank policy rates — sources already verified reachable: ECB, BoC valet, RBA, Norges, BoE, SNB).

## Known limitations stated in advance

- VIXY is an ETN structure that suffers roll decay; a short position benefits from that decay, which
  makes the historical number look better than a sustainable premium. Disclosed, not adjusted away.
- Yahoo price data for US ETPs is adjusted for splits/dividends only, not borrow costs.
- Monthly data gives ~180 observations for H11b (2011–2026): wide error bars. A pass is
  "consistent", not "proven" — the same standard applied to H10.

_Registered 2026-11-20. Nothing in this file may be edited after EXP-0008 runs._
