# QC REPORT — D1 datasets

Generated: 2026-11-20T15:24:19+00:00
Script: `scripts/qc_d1.py` — all numbers below are produced by code.
## Verdict

- **EURGBP_D1_clean.csv**: PASS
- **EURUSD_D1_clean.csv**: PASS


## EURGBP_D1_clean.csv

| check | value |
|---|---|
| rows | 2592 |
| range | 2016-11-21 → 2026-11-20 |
| duplicate dates | 0 |
| weekday slots in span | 2610 |
| missing weekdays (holidays/no-data) | 18 |
| weekend bars present | 0 |
| OHLC logical violations | 0 |
| flat bars (high==low) | 0 |
| non-positive prices | 0 |
| returns beyond 6σ | 2 |
| unchanged closes (stale) | 9 |
| daily log-return sd | 0.00406 |

| year | bars | high/low range % |
|---|---|---|
| 2016 | 30 | 4.0 |
| 2017 | 257 | 11.6 |
| 2018 | 260 | 5.5 |
| 2019 | 260 | 12.6 |
| 2020 | 261 | 14.6 |
| 2021 | 260 | 8.6 |
| 2022 | 258 | 12.6 |
| 2023 | 259 | 5.7 |
| 2024 | 261 | 8.4 |
| 2025 | 256 | 7.7 |
| 2026 | 230 | 5.6 |

### Cross-check vs ECB reference rate (EUR/GBP)

- overlapping days: **2546**
- mean diff: -0.66 pips · mean abs diff: **17.85 pips**
- 95th pct abs diff: 50.68 pips · max: 166.9 pips
- largest deviations:

  - 2020-03-20: +166.9 pips
  - 2019-10-10: -160.5 pips
  - 2022-09-23: +150.9 pips
  - 2022-09-29: -148.3 pips
  - 2020-03-18: -132.9 pips

> ECB fixes ~14:15 CET; Yahoo daily close is UTC-boundary. A few pips of disagreement is expected. A large one is a flag.

## EURUSD_D1_clean.csv

| check | value |
|---|---|
| rows | 2592 |
| range | 2016-11-21 → 2026-11-20 |
| duplicate dates | 0 |
| weekday slots in span | 2610 |
| missing weekdays (holidays/no-data) | 18 |
| weekend bars present | 0 |
| OHLC logical violations | 0 |
| flat bars (high==low) | 0 |
| non-positive prices | 0 |
| returns beyond 6σ | 2 |
| unchanged closes (stale) | 6 |
| daily log-return sd | 0.00449 |

| year | bars | high/low range % |
|---|---|---|
| 2016 | 30 | 4.8 |
| 2017 | 257 | 16.9 |
| 2018 | 260 | 11.9 |
| 2019 | 259 | 6.3 |
| 2020 | 261 | 15.5 |
| 2021 | 260 | 10.4 |
| 2022 | 259 | 20.5 |
| 2023 | 259 | 7.9 |
| 2024 | 261 | 8.4 |
| 2025 | 256 | 16.6 |
| 2026 | 230 | 9.8 |
