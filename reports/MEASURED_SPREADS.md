# MEASURED SPREADS — Dukascopy bid/ask, hourly closes, 2003–2026

Every quoted spread here is **ask minus bid observed in real tick-derived bars**, not an assumption. Half of it is the one-way cost our cost model charges per unit turnover.

Caveat that matters: this is **one ECN venue**. A retail MT5 'standard' account is wider (typically 0.8–1.5 pips on EURUSD); 'raw/ECN + commission' accounts land near these numbers once commission is added back. T18 is complete only when the owner's own export is measured.

## Recent-era spread (median of yearly medians, 2019+)

| Instrument | spread (pips) | half-spread % of notional | vs our H09 assumption 0.013% |
|---|---:|---:|---:|
| EURUSD | 0.3 | 0.00134% | 9.7× cheaper |
| EURJPY | 1.1 | 0.00337% | 3.9× cheaper |
| EURGBP | 0.9 | 0.00501% | 2.6× cheaper |
| EURCHF | 1.0 | 0.00527% | 2.5× cheaper |
| EURCAD | 2.0 | 0.00676% | 1.9× cheaper |
| EURSEK | 36.6 | 0.01647% | 0.8× cheaper |
| EURNOK | 44.1 | 0.01889% | 0.7× cheaper |
| EURAUD | 2.4 | 0.00731% | 1.8× cheaper |
| EURNZD | 3.3 | 0.0095% | 1.4× cheaper |
| GBPUSD | 1.0 | 0.00386% | 3.4× cheaper |

## Spread by year (pips, median of hourly bars)

| Instrument | 2003 | 2004 | 2005 | 2006 | 2007 | 2008 | 2009 | 2010 | 2011 | 2012 | 2013 | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| EURUSD | 1.0 | 1.0 | 1.0 | 1.0 | 1.0 | 1.5 | 1.0 | 1.0 | 1.2 | 0.9 | 0.5 | 0.3 | 0.3 | 0.2 | 0.3 | 0.3 | 0.3 | 0.3 | 0.3 | 0.4 | 0.3 | 0.2 | 0.5 |
| EURJPY | 2.0 | 2.0 | 2.0 | 2.0 | 2.0 | 2.0 | 2.0 | 2.0 | 2.0 | 1.6 | 1.5 | 0.7 | 0.8 | 0.7 | 0.5 | 0.6 | 0.6 | 0.6 | 0.6 | 1.1 | 1.2 | 1.1 | 1.1 |
| EURGBP | 1.6 | 1.6 | 1.6 | 1.6 | 1.5 | 2.0 | 2.0 | 1.5 | 1.9 | 1.3 | 1.3 | 0.8 | 0.9 | 1.0 | 0.9 | 0.9 | 0.9 | 0.9 | 0.8 | 1.1 | 1.0 | 0.8 | 0.8 |
| EURCHF | 2.0 | 2.0 | 2.0 | 2.0 | 2.0 | 2.5 | 2.5 | 2.0 | 2.6 | 1.7 | 1.9 | 1.3 | 1.7 | 1.2 | 1.1 | 1.2 | 1.0 | 1.0 | 1.0 | 1.4 | 1.2 | 1.0 | 1.2 |
| EURCAD | — | 4.6 | 4.0 | 4.0 | 5.0 | 5.5 | 6.0 | 4.0 | 4.2 | 2.5 | 2.4 | 2.2 | 2.2 | 2.1 | 1.7 | 1.8 | 1.9 | 1.8 | 2.0 | 2.5 | 2.0 | 1.8 | 2.4 |
| EURSEK | — | 2.6 | 2.6 | 2.6 | 19.0 | 27.0 | 56.6 | 32.0 | 44.6 | 30.4 | 37.1 | 28.8 | 32.1 | 25.7 | 20.1 | 23.3 | 20.6 | 34.4 | 31.2 | 48.5 | 37.85 | 36.6 | 47.6 |
| EURNOK | — | 32.0 | — | — | — | — | — | 31.0 | 37.0 | 30.4 | 34.6 | 30.4 | 36.85 | 33.2 | 18.8 | 23.4 | 19.9 | 39.5 | 37.6 | 55.05 | 45.15 | 44.1 | 50.2 |
| EURAUD | — | — | 7.0 | 6.0 | 5.0 | 4.5 | 5.0 | 3.4 | 3.3 | 2.1 | 2.2 | 1.6 | 2.1 | 2.1 | 1.6 | 1.9 | 2.0 | 2.1 | 1.9 | 2.5 | 2.6 | 2.4 | 2.7 |
| EURNZD | — | — | — | 7.0 | 6.6 | 7.0 | 6.5 | 7.5 | 7.9 | 4.5 | 4.6 | 3.7 | 5.0 | 4.4 | 3.1 | 3.2 | 3.1 | 3.3 | 3.3 | 3.8 | 3.2 | 3.4 | 4.3 |
| GBPUSD | 2.0 | 2.0 | 2.0 | 2.0 | 2.0 | 2.0 | 2.0 | 2.0 | 2.3 | 1.7 | 1.2 | 1.0 | 1.0 | 1.1 | 0.8 | 0.9 | 1.0 | 1.0 | 0.8 | 1.1 | 1.0 | 0.8 | 0.9 |
