# ALINA MARKET LAB

Research-only market intelligence lab. **No live trading. No real money.**

- **Instrument (locked):** EURGBP primary, EURUSD control
- **Approach (locked):** daily-scale mean reversion, H1 execution, limit entries
- **Rule:** every number in any report must come from an artifact produced by code in this repo

## Structure
```
configs/   project configuration (no secrets)
docs/      plan, audits, research notes
scripts/   ingest / qc / research / backtest
data/      gitignored — raw + processed datasets (manifest by checksum)
```

## Do not
- commit credentials, broker exports, or raw data
- report a metric that no script produced
- enable live trading
