# CURRENT STATE

**Updated:** 2026-11-20 (UTC)
**Phase:** Stage 1 (Foundation) → Stage 2 (Data)

## Done (with evidence)
- Stage 0 audit — `docs/STAGE0_AUDIT.md` (Drive write/read/delete tested; GitHub push tested)
- Instrument screening over 11 assets / 10y — `docs/PLAN_v1_INSTRUMENT_DATA.md`
- Dukascopy M1→H1 ingest pipeline — `scripts/ingest_duka.py` (resumable, spread per hour)
- GitHub repo scaffold pushed — commit `adaaced3`
- Sample decode verified: EURGBP 2024-01-02, 1,440 M1 bars, bid+ask

## In progress
- Ingest 1y M1 candles (EURGBP, EURUSD) → H1 with spread stats (background job)

## Blocked
- Cost model needs broker name + account type (owner)
- paper/demo forward test needs a runtime that is not session-scoped

## Not verified yet
- Dukascopy throughput over thousands of files (rate limits observed)
- Validity of Yahoo H1 candle boundaries vs tick source
