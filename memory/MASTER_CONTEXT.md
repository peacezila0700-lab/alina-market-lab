# MASTER CONTEXT

| field | value |
|---|---|
| Project | ALINA MARKET LAB |
| Owner | Project Owner |
| Agent | Alina (Arena Agent Mode) |
| Status | Stage 0 PASSED (2026-11-20) · Stage 1 in progress · Stage 2 data ingest running |
| Instrument (LOCKED) | EURGBP primary · EURUSD control |
| Timeframe | D1 research / H1 execution |
| Approach (LOCKED) | daily-scale mean reversion, limit entries, hold 1–5 days |
| Money at risk | **ZERO** — research/backtest only |
| Data authority | Dukascopy (M1 candles, real spread) + ECB reference (sanity) + Yahoo (10y daily) |
| Repo | github.com/peacezila0700-lab/alina-market-lab (private) |

## Verified workspace capabilities (evidence 2026-11-20)
- Drive: upload / read-back / trash — tested with real file, id `1nGX8ZTk...`
- GitHub: push works — 2 commits on remote, verified via API
- Python 3.13: numpy, pandas, scipy, scikit-learn, matplotlib
- No 24/7 runtime → batch mode only, one session = one finished experiment

## Known constraints
- Dukascopy datafeed ≈ 0.17 req/s → 1 year of M1 candles ≈ 70 min per symbol
- EURGBP H1 ATR ≈ 5.9 pips → spread = 15% of ATR ⇒ no H1 scalping
- Broker contract spec still missing (cost model BLOCKED)
