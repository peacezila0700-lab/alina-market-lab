# EVENT LAYER — do scheduled events and public attention explain the big moves?

- FOMC decision dates on file: **205** (1994-02-04 -> 2026-10-28), parsed from the Fed's own file names
- Attention = daily English Wikipedia pageviews per asset (free, no key), used as a dated 'how loud was the news' proxy — it measures attention, **not** sentiment or causality
- Economic calendar archive: only *this week* is served by the free feed, so our own archive starts 2026-11 (no historical backfill is available for free)

## 1. Do FOMC decision days move the market harder?

| Asset | FOMC days matched | mean abs move on FOMC days | on other days | diff | Welch t |
|---|---:|---:|---:|---:|---:|
| SP500 | 312 | 0.965% | 0.794% | +17.12 bp | 2.84 |
| GOLD | 302 | 0.963% | 0.79% | +17.29 bp | 2.79 |
| EURUSD | 260 | 0.488% | 0.426% | +6.19 bp | 2.45 |
| USDJPY | 308 | 0.509% | 0.45% | +5.89 bp | 2.25 |
| BTC | 208 | 2.647% | 2.244% | +40.35 bp | 2.09 |
| WTI | 302 | 1.936% | 1.803% | +13.29 bp | 0.94 |

Welch t above ~2 is a real difference; below ~1.5 is noise. Sample starts in 2000, so the calendar coverage (1994+) is not the limit — history is.

## 2. Does public attention lead moves?

| Asset | days | corr(attention z, same-day abs move) | corr(attention z, **next-day** abs move) | next-day abs move, hot decile | cold |
|---|---:|---:|---:|---:|---:|
| SP500 | 2485 | 0.198 | 0.141 | 1.126% | 0.702% |
| GOLD | 2487 | 0.12 | 0.081 | 1.015% | 0.721% |
| EURUSD | 2571 | 0.005 | 0.003 | 0.335% | 0.334% |
| USDJPY | 2571 | 0.069 | 0.081 | 0.505% | 0.376% |
| BTC | 3611 | 0.25 | 0.175 | 3.452% | 2.208% |
| WTI | 2486 | 0.313 | 0.21 | 3.214% | 1.738% |

Same-day correlation should be positive by construction (big moves make news). **The next-day column is the only one that could be worth money** — if attention today raised tomorrow's expected move, that is a volatility signal.

## 3. Biggest single-day moves

- **SP500**: 2008-10-13 +11.6%, 2008-10-15 -9.0%, 2008-10-28 +10.8%, 2020-03-12 -9.5%, 2020-03-13 +9.3%
- **GOLD**: 2001-09-14 +6.8%, 2006-06-13 -7.3%, 2008-09-17 +9.0%, 2009-03-19 +7.8%, 2013-04-15 -9.3%
- **EURUSD**: 2008-01-08 +6.0%, 2008-02-08 +7.5%, 2008-02-11 -6.9%, 2008-09-08 -6.0%, 2008-10-07 +10.1%
- **USDJPY**: 2008-04-07 +5.6%, 2008-04-08 -5.9%, 2008-05-08 -5.0%, 2008-10-07 +8.5%, 2008-10-08 -9.6%
- **BTC**: 2015-01-14 -21.1%, 2017-07-20 +23.9%, 2017-09-14 -18.7%, 2017-12-06 +19.9%, 2017-12-07 +25.2%
- **WTI**: 2020-03-09 -24.6%, 2020-03-18 -24.4%, 2020-03-19 +23.8%, 2020-04-02 +24.7%, 2020-04-21 -45.2%

`*` = inside an FOMC decision window. Notice how *few* of the extremes carry the star: the biggest shocks are almost never the scheduled ones.


_Generated 2026-11-20 16:48 UTC by `scripts/explain_moves.py`. Artifacts: `research/artifacts/event_study.json`, `data/events/`._
