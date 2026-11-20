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

## PROJECT REVIEW #1 (2026-11-20) — hard stop at 6 hypotheses
- EXP-0003 (H1 fade): IS −1.66, VALID +0.97 (CI spans 0), control flips sign → **H05 rejected**
- EXP-0004 (H1 breakout): IS **−2.93, CI [−4.27, −1.54]** → **H06 rejected (significantly negative)**
- Both directions lose after cost ⇒ cost + adverse selection dominate, not tuning
- **Zero validated edges.** Full review: `reports/PROJECT_REVIEW_1.md`
- Recommendation: get MT5 export (real spread/swap) then re-run, or stop with the negative result

## EXP-0002 result (2026-11-20) — H01 REJECTED
- Power expansion without changing the rule: 26y history (2000/2003→2026) × 5 pairs.
- **CLEAN sample (never used before): n=94, +5.81 pips/trade, PF 1.06, CI [−52.55, +67.66], 2/5 pairs positive**
- Random-entry benchmark mean +2.79 (p95 +43.8) → observed result is indistinguishable from luck
- Sign instability across periods: EURGBP −15.3 → +61.6; CADCHF −50.9 → +76.3
- Report: `reports/EXP_0002.md` · H02/H04 deprioritised · H03 not worth a session on a dead base

## EXP-0001 result (2026-11-20)
- **H01: NOT SUPPORTED** — 14 trades in 10 years (min 30 required). IS n=10, +68.3 pips/trade,
  PF 2.29, but 95% CI [-7.45, +164.8] includes 0. Random-entry benchmark p95 = +114 → inside noise.
- Validation (n=3) and OOS (n=1) are untestable. Full report: `reports/EXP_0001.md`
- Binding constraint is now **statistical power**, not data quality or cost.
- Rule was NOT re-tuned (that would burn the only honest test left).

## Waiting on owner — direction decision after H01 rejection
- Option 1: move to intraday (H1/M15) with NEW data — needs a working feed (MT5 export or Dukascopy)
- Option 2: new D1 hypothesis family (e.g. volatility-compression breakout), pre-registered
- Forbidden: retuning H01 on the same data
- No evidence supports moving toward paper trading.

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
