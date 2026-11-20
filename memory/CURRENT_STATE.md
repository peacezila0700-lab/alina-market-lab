# CURRENT STATE

**Updated:** 2026-11-20 (UTC)
**Phase:** Stage 1 (Foundation) → Stage 2 (Data)

## Done (with evidence)
- Stage 0 audit — `docs/STAGE0_AUDIT.md` (Drive write/read/delete tested; GitHub push tested)
- Instrument screening over 11 assets / 10y — `docs/PLAN_v1_INSTRUMENT_DATA.md`
- Dukascopy M1→H1 ingest pipeline — `scripts/ingest_duka.py` (resumable, spread per hour)
- GitHub repo scaffold pushed — commit `adaaced3`
- Sample decode verified: EURGBP 2024-01-02, 1,440 M1 bars, bid+ask

## Done this session (evidence)
- T04b QC + manifest: `reports/QC_D1.md`, `data/processed/MANIFEST.json` — both datasets **PASS**
- Canonical cleaning: `scripts/build_canonical_d1.py` → 2,592 bars each, log `CLEANING_LOG.csv` (720 rows)
- T07 Descriptive research: `reports/RESEARCH_D1.md`, `reports/zscore_buckets.csv`
- Decisions D01–D06: `docs/DECISION_LOG.md`
- T08 Hypothesis register: `research/HYPOTHESIS_REGISTER.csv` (H01–H04 ranked) + pre-registration in `docs/HYPOTHESIS_NOTES.md` + `research/EXPERIMENT_LOG.csv` (EXP-0001 planned)

## Waiting on owner (Gate 5)
- Approve test order H01 -> H02 -> H03 -> H04 before any backtest is written

## In progress / blocked by source
- Ingest M1 candles: **BLOCKED — Dukascopy returns HTTP 429** (rate limit, source-side, verified 5/5 curl)
- v1 script had a silent-data-loss bug → fixed as **QR-001** (`docs/INCIDENT_LOG.md`), job now stops instead of faking days

## Blocked
- Cost model needs broker name + account type (owner)
- paper/demo forward test needs a runtime that is not session-scoped

## Data available right now
- EURGBP + EURUSD **D1 10 years** (Yahoo, 2016-11 → 2026-11) — usable for research/backtest at daily horizon
- ECB EUR/GBP daily reference (verified reachable)
- Dukascopy: 1 verified day of M1 bid+ask (2024-01-02, 1,440 bars, spread median 0.90 pip)

## Not verified yet
- Dukascopy throughput over thousands of files (rate limits observed)
- Validity of Yahoo H1 candle boundaries vs tick source
