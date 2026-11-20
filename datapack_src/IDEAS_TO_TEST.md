# IDEAS TO TEST — with pre-declared priors

Priors are the honest guess **before** testing, stated so a later result can be judged against them
(a 5% "win" on a 10%-prior idea is noise; a 5% win on a 40%-prior idea is a finding). Scale 0–100.

Ordered by (prior × cheapness). Test cheap ones first.

## Tier 1 — cheap, untested, plausible (prior 25–40%)

| # | Idea | Prior | Why it might work | How to test (cheap) |
|---|---|---|---|---|
| I01 | **COT extreme as contrarian**: when non-commercial net % of OI is in the top/bottom 5% of a 3-year window for a contract, fade over 2–8 weeks | 35 | Crowded speculative positioning is the classic squeeze setup; dataset covers 1986–2026 across 24 contracts, and it is *not* in the price series | `data/cot_weekly_cftc`: percentile-rank `noncomm_net_pct_oi` per instrument over 156 weeks, `shift` by `available_from`, then event study of forward 2/4/8-week returns. Use the 24-instrument panel for cross-sectional pooling (much more power than one market) |
| I02 | **COT commercial/non-commercial divergence** (commercials net long while funds net short, and the gap widens) as a slow long bias | 30 | Commercials are hedgers and are right about *value* over months, wrong about timing | Signal = z-score of `comm_net − noncomm_net` / OI; test monthly rebalance, 24 contracts |
| I03 | **VIX term-structure / SKEW combination** as a risk-off switch for an equity basket (not a standalone trade) | 30 | SKEW measures *tail* demand, VIX measures the middle; both high = real fear; both low = complacent | `vix_cboe_daily` + `skew_cboe_daily`: 2-factor regime, then apply to SP500 daily. Test only as a filter on an existing basket, never standalone |
| I04 | **Measured-spread cross-sectional carry**: rank the 10 FX pairs by measured spread (liquidity) and only trade the cheapest quartile with a mean-reversion rule | 25 | The XS-reversion failure was a cost problem, not a signal problem: ECN +0.07 vs retail −0.08 | `spreads_measured_dukascopy` + `fx_official_ecb_daily`; restrict the universe, re-run h09_xs_reversion.py |

## Tier 2 — needs building, medium cost (prior 15–25%)

| # | Idea | Prior | Note |
|---|---|---|---|
| I05 | **Dealer gamma / options positioning** as a pinning signal near large strikes | 20 | Real edge in the literature, but requires options chain data this pack does not have. CBOE put/call CSVs are dead (see DATA_SOURCES). Would need a new free chain source |
| I06 | **COT regime + trend interaction**: only take trend trades when funds are *adding* (change in noncomm net confirms) | 20 | Cheap to test with the existing panel; risk of double-counting trend, which already failed |
| I07 | **Macro surprise** (actual vs forecast) from the forward-collected calendar | 15 | Needs 2+ years of accumulation before any test is meaningful; the archive starts 2026-11 |
| I08 | **Seasonality/calendar in ags and energy** (crude inventory weeks, grain planting/harvest) | 20 | COT panel + universe CSVs already cover CORN, WHEAT, WTI, NATGAS back to 1986/1990 |
| I09 | **Vol-of-vol / SKEW momentum** as a tail-hedge timing signal | 15 | Very few independent observations; high overfit risk |
| I10 | **Cross-asset lead-lag**: copper/gold ratio, USD vs EM FX, BTC vs NASDAQ with a lag | 15 | Frequently published, therefore likely arbitraged; test with strict cost and a null |

## Tier 3 — expected to fail (prior < 10%) — listed to stop re-proposing them
- MA crossover / MACD / RSI / Bollinger / Ichimoku / SuperTrend standalone. **Already tested, all ≈ 0.**
- Martingale, grid, averaging-down. **5/5 wiped.**
- Attention/news-count as direction. **Tested: no.**
- Short-vol carry as a primary strategy. **Tested: −103.7% worst 12 m.**
- Multi-timeframe confluence filters. **Untested but unsupportable on free data.**

## Protocol for any new test (non-negotiable)
1. Write the hypothesis + prior **before** looking at results (see `results/experiments.jsonl`).
2. Split: 70% in-sample / 30% untouched hold-out, split by **date**, never randomly.
3. Charge measured costs on every turn; report ECN and retail.
4. Run a turnover-matched random control; report it next to the result.
5. Declare the number of trials; if you tried 20 variants, say so.
6. Write the verdict into `results/experiments.jsonl` even when it fails — that is the asset.
