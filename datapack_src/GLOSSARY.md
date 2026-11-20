# GLOSSARY + units (so an AI does not misread a column)

## COT (`data/cot_weekly_cftc`)
- **report_date** — Tuesday as-of date of the positions.
- **available_from** — the Friday the numbers became public (15:30 ET). **Tradeable date.**
- **open_interest** — total contracts outstanding (contracts, not notional).
- **noncomm_*** — non-commercial = funds/CTAs/speculators ("big money").
- **noncomm_net** — long − short (contracts). Positive = net long.
- **noncomm_net_pct_oi** — that net as % of open interest. The comparable-across-time version.
- **comm_*** — commercial = producers/consumers/hedgers. Usually the mirror image of funds.
- **nonrept_net** — small trader net.
- **conc_net_top4_***_pct** — share of OI held by the 4 largest traders on that side (concentration).
- **units** — contract size, e.g. "CONTRACTS OF 100 TROY OUNCES". **Never compare raw contracts
  across contracts**; compare `% of OI` or z-scores.

## Spreads (`data/spreads_measured_dukascopy`)
- Stored as **pips in price units** (ask − bid) and `spread_bp` = spread/price × 10000.
- For a 5-digit FX pair, 0.00012 = 1.2 pips. Round-turn cost ≈ full spread (enter at ask, exit at bid).
- `retail` and `ecn` in `MEASURED_COSTS.json` = different account types of the same venue.

## Returns / risk
- **cagr** — compound annual growth rate, decimal (0.12 = 12%).
- **maxdd** — maximum drawdown, decimal, positive number.
- **sharpe** — annualised, **risk-free = 0**. Bars/year explicit (252 daily, 52 weekly, 12 monthly).
- **calmar** — cagr / maxdd.
- **RUINED** — the equity curve touched zero; all ratios are meaningless.

## Terms
- **TSMOM** — time-series momentum (sign of the past 12-month return).
- **XS reversion** — cross-sectional mean reversion: long the losers, short the winners of the last k days.
- **null / permutation control** — same number of trades, random dates or random asset choice;
  the honest baseline. If the strategy cannot beat it, there is no edge.
- **VRP** — variance risk premium: implied vol minus realised vol. Positive on average, crashes hard.
- **walk-forward** — optimise on a rolling window, trade the next window, never re-use data.
- **hold-out** — data never touched during development. Touch it once, then it is burnt.
