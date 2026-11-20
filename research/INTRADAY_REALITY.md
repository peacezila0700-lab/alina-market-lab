# INTRADAY REALITY — what free data + free latency can actually support

Written after testing every route from this sandbox (2026-11-20). This is the cost/latency ceiling,
stated plainly, so no future session wastes a week building an HFT bot on free data.

## 1. What you can get, verified

| Route | Granularity | History | Has bid/ask? | Verdict |
|---|---|---|---|---|
| Dukascopy freeserv `chart/json3` | 1 MIN / 1 HOUR / 1 DAY | 2003 → 2025 | **YES** (`offer_side=B` and `=A`) | The only free source with real spreads. 1 MIN returned **403** today; 1 HOUR works and returns 30,000 bars per call |
| OKX `history-candles` | 1m / 5m / 1H / 1D | BTC/ETH to ~2020 (1H), deeper on 1D | No (last price) | Deep, stable, key-less. Harvested 1 year of 1H (9,500 bars each) into `data/intraday/` |
| Yahoo `v8/finance/chart` | 1m/5m/15m | **730 days max**, 422 on bad param combos | No | Only for recent equity intraday |
| CME / Binance / Bybit | — | — | — | Blocked from this IP (403/451) |
| Tick data | — | — | — | No free source. Do not plan for it |

## 2. The cost wall (the number that decides everything)

Round-turn cost, measured where possible:

| Instrument | Round-turn cost | What the edge must clear per trade |
|---|---|---|
| EURUSD (ECN) | **0.26 bp** | ~0.5 bp to be interesting |
| EURGBP (ECN) | 0.78 bp | ~1.5 bp |
| EURSEK (ECN) | 3.18 bp | ~6 bp |
| BTC on OKX (10 bp/side taker) | **20 bp** | ~40 bp |

Hourly volatility for context: BTC ≈ 0.47% per hour, ETH ≈ 0.63% per hour.

**Conclusion: an hour-level bot belongs on FX, not crypto.** Crypto hourly vol is large but you must
clear 40 bp per round trip; FX you must clear 0.5 bp. Same signal, 80× different hurdle. This single
number kills most "crypto scalping bot" ideas before any code is written — and it is why the execution
universe is EURUSD/EURGBP/EURCHF/GBPUSD/GOLD.

## 3. Latency reality

- No free feed is real-time: our sources are REST snapshots (OKX/deribit are seconds; Yahoo/Cboe are
  15-min delayed or EOD). A retail MT5 terminal is faster than any of this.
- Therefore the honest intraday design is **hourly-bar, decision-at-bar-close, execution within the
  next bar** — i.e. latency of one bar (~60 min) is irrelevant to the strategy, and no co-location is
  needed. Any strategy that needs sub-second execution is out of scope for zero cost.
- Practical trick that *does* work free: run the decision on bar close, and place a **limit order at a
  passive level** for the next bar — you convert the spread cost from taker to maker. That is the
  single biggest cost lever available to a retail account (EURUSD maker ≈ 0.1 pip).

## 4. What is worth testing at this granularity

1. **Overnight/intraday session split** (Asian range → London breakout) on FX hourly with measured
   bid/ask. Cheap to test, professionally traded, and the cost model is real.
2. **Hour-of-day seasonality in spread** — the spread files we measured show which hours are cheap;
   trading only those hours improves net expectancy without any new signal.
3. **Event-hour venting**: FOMC/CPI hours have wide spreads and gap risk; the event DB can gate them.
4. **Crypto 4H/1D carry** (funding) rather than intraday scalping — funding is paid, not traded
   against the spread.

## 5. What NOT to do

- Do not build anything that needs tick data, queue position, or sub-minute signals: the data does not
  exist for free and the latency cannot be bought at zero cost.
- Do not run intraday backtests on Yahoo 1m (730-day cap, and the sample is one regime).
- Do not trust any hourly backtest that does not include the measured bid/ask by hour — the spread at
  03:00 and at 13:30 is not the same number, and that difference is often the whole P&L.
