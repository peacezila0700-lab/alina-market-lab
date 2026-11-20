# CURRENT STATE — 2026-11-20 (session: data pack pivot)

## Focus
Data + code + experiments for a DOWNSTREAM AI. App is frozen (not the deliverable).

## Just shipped
- `data/cot/cot_weekly.csv` — CFTC COT legacy futures-only via Socrata (`6dca-aqww`), 24 contracts,
  35,936 contract-weeks, 1986-01-15 → 2026-11-10. Columns include BOTH `report_date` (Tue as-of) and
  `available_from` (Fri public) so look-ahead is impossible to do by accident.
- `data/cot/cot_features.csv` — noncomm/comm net %OI, 156-week z-score + percentile, 4-week change.
- `data/options/SKEW.csv` — CBOE SKEW 1990 → 2026-11-19 (9,274 rows). Put/call CSVs are DEAD (200 + HTML).
- `scripts/fetch_cot.py`, `scripts/test_cot_extremity.py`, `scripts/build_datapack.py`.
- `pack/ALINA_DATAPACK_v1.1.zip` — 6.2 MB, 181 files, 16 datasets. Uploaded to Drive:
  id `1jW8sRVqFoD1EbH3_N4NZk3XmFuPbXLBe` (v1 older zip trashed). Thai one-pager also on Drive as a Doc.
- `datapack_src/` — source of the knowledge docs (README_FOR_AI, DATA_SOURCES live/dead map,
  PITFALLS, WHAT_FAILED, IDEAS_TO_TEST with priors, GLOSSARY, HOW_TO_BACKTEST, README_TH).

## Result of the new test (H12, exploratory — NOT pre-registered)
59 tests, non-overlapping sampling: **0** observations match the contrarian COT read with |t|>=2
(chance ≈3). Three |t|>=2 hits point WITH the crowd (EURUSD net long → +1.06% over 4w, t=2.99;
GOLD +2.05%/8w, t=1.91). Verdict: no contrarian edge; if anything, positioning momentum.
Two traps fixed while doing it: overlapping forward windows inflate t by ~sqrt(h) (saw t=30 on a
0.05% edge), and the pre-derived `*_D.csv` FX crosses only start 2023 (silently truncated the sample).

## Verified / not verified
- COT + SKEW + ECB + spreads: pulled and parsed successfully (verified).
- EA (`ea/AlinaRiskGovernor.mq5`): lint only, **never compiled** — still ยังไม่ได้ทดสอบ.
- Pack integrity: catalog rows/sha256 generated from the files themselves.

## Next actions (in order)
1. Pre-register + run the pooled panel version of H12 (instrument fixed effects, date-clustered SEs,
   70/30 date split) — the only way a COT claim can become real.
2. Add CBOE put/call via an alternative route (put/call CSVs dead; try scraping the ratios page or
   another free vendor) — options *flow* is the biggest remaining hole.
3. Dealer gamma / open interest by strike: needs a free options chain source; unresolved.
4. Regenerate the pack after each data addition (`python3 scripts/build_datapack.py`) and re-upload.
