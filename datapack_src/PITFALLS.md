# PITFALLS — the bugs that made this project see fake edges

Written because an AI inheriting this repo will make the same mistakes. Each item cost real time
and produced at least one false positive.

## 1. Look-ahead via unlagged positions (the big one)
`pnl[t] = pos[t] * ret[t]` where `ret[t] = close[t]/close[t-1]-1` means you trade at `close[t]`
using information that only exists at `close[t]`, then collect the move into `close[t]`.
Effect measured here: an EMA-cross screen showed **CAGR 30.0%, Sharpe 1.72, 22/24 instruments
profitable**. With `pos[t-1]` the same code gave CAGR 4.0%, 10/24 profitable. The rule is:

```
ret[t]      = close[t]/close[t-1] - 1
pos[t]      = f(info up to and including close[t])
pnl[t]      = pos[t-1] * ret[t] - cost * |pos[t-1] - pos[t-2]|
```

A position that flips at the close can only earn the *next* bar.

## 2. Diagnosing look-ahead incorrectly
A cheap detector: if a 1-bar lag barely changes the result, the look-ahead was not the problem.
Here, lagging changed CAGR from 30% to 4% — ratio > 5x is a strong tell.

## 3. Wrong cost assumption (verdict-flipping)
- Assumed 1.3 pip round-turn on all FX. Reality (measured, ECN): EURUSD 0.3 pips, EURSEK **48 pips**.
- Consequence: XS mean-reversion on G10 looked like a **Sharpe 1.38, +22.5%** opportunity at the
  assumed cost; at retail costs it was **−0.08 Sharpe**; at ECN costs it was **+0.07, ~breakeven**.
- Lesson: cost is not a constant, it is a per-instrument, per-hour measurement. Always run the
  verdict at *two* cost levels (ECN and retail) and report both.

## 4. Zero-crossing equity curves corrupt metrics
When an equal-weight basket's equity crosses zero, `cagr` and `maxdd` become `nan` or absurd
(>100%, or 1e6 %). Always clip/mark `RUINED` instead of reporting the ratio.

## 5. Month-end bucketing
Grouping by `year-month` looks fine until the last group has 3 days: the compounded monthly return
is then not comparable. Check `len(months)` vs the date span before trusting an equity curve.

## 6. Reusing a tested sample as a "new" test
EXP-0006 re-scored EXP-0005 with better costs. That is a cost-model correction, **not** independent
confirmation. Hold-out data must be genuinely unseen (EXP-0007 used 2016–2021 held out and the
prior in-sample result failed: +0.413 → +0.126 Sharpe).

## 7. Survivorship / listing bias in the free-EA and ETF universes
The 332 free EAs are what is *listed today*; dead products were delisted. Do not compute
"average EA performance" from that list. Same for ETFs: `VIXY` exists, `VXX` on Yahoo only from 2018.

## 8. COT date confusion
`report_date` = Tuesday as-of. Public release = Friday 15:30 ET. Using Tuesday in a daily backtest
gives 3 extra days of hindsight per week — it looks great and is 100% fake.

## 9. Martingale looks brilliant until it doesn't
A grid/martingale (fade 1 ATR, double, 6 levels, TP 0.5 ATR) produced **positive equity curves for
months** and a 97%+ win rate. Final equity: EURUSD 0.825, SP500 0.938, GOLD 0.938, BTC 0.976,
NIKKEI 0.951 — **5 of 5 wiped**. If a strategy's win rate is >90%, you are long tail risk.

## 10. "Statistical significance" from many trials
168 screen tests × 14 metrics = thousands of numbers. At 5% you expect ~8 false positives. This
project's rule: report how many of N instruments beat the null vs how many were expected by chance
(6 of 144 observed vs 7.2 expected = nothing found).
