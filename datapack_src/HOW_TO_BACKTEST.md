# HOW TO BACKTEST HERE — the exact engine rules this repo settled on

Copy these; they are the distilled result of 8 experiments and 3 self-inflicted incidents.

## The loop
```python
# prices: pandas Series indexed by date, aligned across the universe
ret  = px.pct_change()
pos  = signal.shift(1)                       # <-- the one line that decides if you are lying
turn = pos.diff().abs().fillna(pos.abs())    # turnover per bar
cost = turn * cost_frac                     # cost_frac = spread/price, per instrument
pnl  = pos * ret - cost

cagr   = equity[-1] ** (bars_per_year / len(equity)) - 1
sharpe = pnl.mean() / pnl.std() * sqrt(bars_per_year)
maxdd  = (equity / equity.cummax() - 1).min()
```

## Costs
- FX: use `data/spreads_measured_dukascopy/MEASURED_COSTS.json`, key `ecn` and `retail`.
  Never use one global pip constant across pairs.
- Equities/ETFs: 1 bp + slippage, or 2 bp if you want to be safe.
- Crypto: 10 bp per side minimum (the 24h market is cheap in fees, expensive in spread).
- Report the verdict at both ECN and retail cost — the spread between the two verdicts *is* the
  robustness measure.

## Null controls (mandatory)
1. **Random-position null**: same number of long/short flips, random dates, 300 permutations.
   Record the strategy's percentile. < 95th = nothing.
2. **Buy & hold** on the same instrument, same period, same costs.
3. **Cash** (0.0 Sharpe). Any long-only strategy in a rising market must beat cash meaningfully.

## Sample discipline
- Date split, never random: first 70% development, last 30% hold-out. Touch the hold-out once.
- If you tune any parameter, the hold-out is gone; you need new data or a new idea.
- Count your trials and write the count down (multiple-testing correction is otherwise impossible).

## What "success" looks like here
Not a Sharpe. Success is: positive net of measured costs, beats the permutation null at the 95th
percentile, survives a genuine hold-out, has a plausible economic story for *who is on the other
side and why they would keep losing*, and does not depend on a parameter plateau edge.

## Thresholds used in this repo (and why they are conservative)
- Sharpe > 1.0 net of retail costs AND > 0.7 at hold-out → "promising", still not live.
- Worst rolling 12-month return better than −25% → survivable.
- > 500 trades → statistical content; < 100 trades → anecdote.

## Deployment reality check (free, from this repo)
An MT5 EA was written (`code/ea/AlinaRiskGovernor.mq5`) with: paper mode default, no signal default,
3% daily loss stop, 20% permanent drawdown latch, 2% risk sized off 1.5×ATR, spread guard, one
position max, martingale blocked by construction *and* by a lint rule. **It has never been compiled
or run on a live terminal** — the account that could do it was deleted. Treat it as a template, not
a tested product.
