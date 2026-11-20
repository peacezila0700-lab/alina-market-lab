# WHAT FAILED — evidence, not opinion

Read this before spending a single token on a "new" idea. Tally at the time of writing:
**8 pre-registered experiments, 168 screen tests, 144 free-EA family tests, 0 validated edges.**

## Closed with numbers

| # | Idea | Result | Verdict |
|---|---|---|---|
| EXP-0001 | Long-only trend (10-month TSMOM) on 24 assets | Sharpe ~0.3 net, DD > 40%, fails 2013+ | REJECTED |
| EXP-0002 | Single-asset screen, 7 documented rules × 24 assets | best family flat; 22/24 "profitable" was a look-ahead artefact | REJECTED (bug) |
| EXP-0003 | Same, look-ahead corrected, 300-null permutation | no family beats null | REJECTED |
| EXP-0004 | Donchian breakout portfolio | positive but < null on most configs | REJECTED |
| EXP-0005 | XS mean-reversion G10 (equal-weight, 5-day) at assumed 1.3 pip | Sharpe +2.10 / +1.38 depending on window | PROVISIONAL (costs too optimistic) |
| EXP-0006 | EXP-0005 re-scored with MEASURED spreads | ECN +0.07 Sharpe (~breakeven); retail −0.08 | REJECTED |
| EXP-0007 | HK/TW/JP equity-index momentum, 2016–2021 hold-out | in-sample +0.413 -> hold-out **+0.126** | FAILED |
| EXP-0008 | Variance risk premium (short vol via VIX vs realised) | H11b Sharpe +0.694, worst 12 m **−103.7%** | REJECTED (crash risk) |

## Family sweep over the free-EA ecosystem (144 tests)
Mean Sharpe vs null by family, 24 instruments each:

| Family | Mean Sharpe | Instruments beating null (of 24) |
|---|---|---|
| BOLL_FADE | +0.04 | 1 |
| ICHIMOKU | +0.04 | 2 |
| RSI_FADE | +0.01 | 0 |
| STOCH_FADE | −0.03 | 1 |
| MACD | −0.04 | 1 |
| SUPERTREND | −0.61 | 0 |

6 of 144 beat the null; chance alone predicts 7.2. **No family edge.**

## Also dead / not worth retrying
- **Attention (Wikipedia pageviews) as a directional signal.** It improves next-day *volatility*
  forecasts (MAE better on 6 of 8 assets) but the portfolio Sharpe went 0.64 -> 0.63. Information
  ≠ tradeable edge.
- **Event-window trading around FOMC.** Move clustering exists but is not directional after costs.
- **Multi-timeframe intraday confirmation** (H1/H4 + ADX/GARCH/VWAP/confluence filters): 2-month
  window, all variants ≈ 0. Cannot be validated on free data (Yahoo H1 limited to 730 days,
  Dukascopy tick feed 503).
- **Kalman/OU pairs trading across 8 assets:** Gaussian log-likelihood gain (28.1) did not survive
  cost-per-round-trip; mean half-life 3.2 days is too slow for the spread width available.
- **Martingale/grid EA family:** see PITFALLS #9 — 5 of 5 accounts wiped.

## What this means for the next AI
The failure pattern is consistent: **any signal that survives in-sample dies on (a) measured costs,
(b) a genuine hold-out, or (c) a permutation null.** Design accordingly — pre-register, charge real
costs, hold data out, and compare against a turnover-matched random control. The value left is not
in retesting these; it is in new data sources and in position/flow information (COT, options
skew, dealer gamma) that is not in the price series at all.
