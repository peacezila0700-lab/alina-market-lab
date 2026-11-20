# DECISION LOG

## D01 — Instrument: EURGBP primary, EURUSD control
- **Date:** 2026-11-20 · **Status:** LOCKED by owner
- **Evidence:** screening of 11 instruments / 10y — EURGBP Hurst 0.358, half-life 13.7d,
  65.7% of days within ±2% of 200dMA, VR(5)=0.882 → VR(60)=0.516 vs EURUSD Hurst 0.500
- **Rejected:** XAU/XAG (vol 17–35%), EURCHF (SNB 2015 gap risk), AUDNZD (ADF t=-0.84, no cointegration)
- **Reversal:** requires ≥5 years OOS evidence that another instrument has a stronger, cost-surviving effect

## D02 — Approach: daily-scale mean reversion, not H1 scalping
- **Date:** 2026-11-20 · **Status:** LOCKED (forced by cost arithmetic)
- **Evidence:** EURGBP ATR(H1) 5.9 pips; Dukascopy spread median 0.90 pip = 15% of ATR per side
- **Rule:** expected move per trade must be ≥ 3× round-trip cost; entering with limit orders

## D03 — Canonical D1 source is vendor data with documented repairs, not "raw"
- **Date:** 2026-11-20 · **Status:** ACTIVE (provisional)
- **Rules:** R1 relabel Sunday→Friday when Friday missing (294/522 weeks; |r| Thu→Sun 32.1 pips
  ≈ Thu→Fri 35.5 pips); R1b drop duplicate Sunday stub (10); R2 clamp OHLC (44); R3 drop isolated
  bad print (1: EURGBP 0.97900 on 2022-10-07); R4 never forward-fill
- **Impact:** kurtosis 173.6 → 8.3; two fabricated ±11% moves removed
- **Log:** `data/processed/CLEANING_LOG.csv` (720 rows), every row traceable

## D04 — Research numbers are in-sample only, overlapping windows disclosed
- **Date:** 2026-11-20 · **Status:** PERMANENT RULE
- z-score bucket cells use overlapping h-day windows → t-stats are optimistic;
  effective independent episodes are few (e.g. z<-2 20d: n=49 over 10 years ≈ 2–3 episodes/yr)

## D05 — Dukascopy bulk ingest: BLOCKED, not abandoned
- **Date:** 2026-11-20 · **Status:** BLOCKED (source rate limit, HTTP 429 intermittent)
- 2 successes then persistent 429s; polite 0.8 req/s still blocked
- **Fallback order:** (1) owner's MT5 history export, (2) retry Dukascopy when unblocked,
  (3) Yahoo H1 730d for cross-checks only

## D06 — Price data from Yahoo is NOT execution-grade
- open==close in ~39% of bars; Friday session mislabeled Sunday in 294/522 weeks
- → closes usable for research; OHLC/spread NOT usable for backtest execution assumptions

## D07 — H01 rejected; D1 z-score direction closed
- **Date:** 2026-11-20 · **Status:** CLOSED (not to be retuned)
- **Evidence:** EXP-0001 (n=14, CI spans 0, random benchmark p95 = +114 vs observed +68) and
  EXP-0002 (n=94 clean trades over 26 years × 5 pairs, +5.81 pips/trade, PF 1.06,
  CI [−52.55, +67.66], 2/5 pairs positive, random mean +2.79)
- **What stays true:** the descriptive range behaviour (Hurst 0.36, VR60 0.52, 66% within ±2% of MA200)
- **What is rejected:** that a z ≥ +2σ short with MA-cross/time-stop exits monetises it after costs
- **Forbidden:** any retune of threshold/horizon/stop on the same data
- **Consequence:** both the OOS block and the CLEAN block are consumed → any further test needs
  untouched data (intraday) or a structurally different hypothesis family

## D08 — Intraday arena chosen for future tests; both mechanism families rejected
- **Date:** 2026-11-20 · **Status:** ACTIVE
- Intraday (H1) chosen because financing is zero by construction (see FEASIBILITY_MATH) and
  it yields ~79 trades/year vs 1.4 for D1 → statistically answerable in weeks.
- EXP-0003 (fade, H05) rejected: IS −1.66 pips, validation CI spans 0, control flips sign.
- EXP-0004 (breakout, H06) rejected: IS −2.93 pips, CI [−4.27, −1.54], negative in all blocks.
- Consequence: no retuning of H05/H06. Any further test requires measured broker costs (T18).

## D09 — Hard stop at 6 of 12 hypotheses
- **Date:** 2026-11-20 · **Status:** ACTIVE
- Triggered PROJECT REVIEW #1. No further experiments are authorised until the cost model is
  measured (owner MT5 export) or the owner explicitly chooses a different arena.
