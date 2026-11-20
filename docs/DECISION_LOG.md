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

## D10 — Universe screen invalidated and re-run (QR-002); buy & hold is the bar to beat
- **Date:** 2026-11-20 · **Status:** ACTIVE
- The 168-test multi-asset screen was re-run after fixing the same-bar look-ahead (QR-002).
- Post-fix reality: best Sharfes are **asset betas, not strategies** — BTC buy&hold 0.78,
  GOLD buy&hold 0.64, ETH buy&hold 0.53. Best live rules: BTC TSMOM_12M 0.81 (96th pct null),
  GOLD TSMOM_12M 0.55 (100th), NASDAQ100 TSMOM_12M 0.45 (99th).
- **DONCHIAN_55 no longer "dominates"** — it is mid-pack (BTC 0.52). D09's stop still binds
  for FX; the multi-asset hunt continues but nothing here is tradeable yet.
- New standing rule: a candidate must beat the **equal-weight buy & hold portfolio**
  (CAGR 11.6%, Sharpe 0.70, maxDD 66.9%, 2000–2026) on a cost-charged, lagged basis.

## D11 — Free event layer built: FOMC dates + weekly calendar archive + attention proxy
- **Date:** 2026-11-20 · **Status:** ACTIVE
- Sources that actually worked, all free, no signup: **federalreserve.gov** (205 FOMC decision
  dates 1994-02-04 → 2026-10-28, parsed from file names), **nfs.faireconomy.media** weekly
  calendar JSON (current week only → our own archive starts 2026-11, 125 events),
  **wikimedia pageviews API** (8 assets, 3,976 days each, 2016→).
- Dead: GDELT DOC API (hard HTTP 429 from this IP at 1 req/30s), FRED, BIS, FXCM, Stooq.
- **Event study result (`reports/EVENT_LAYER.md`):** FOMC days carry larger moves — S&P +17.1bp
  (Welch t=2.84), GOLD +17.3bp (2.79), EURUSD +6.2bp (2.45), USDJPY +5.9bp (2.25), BTC +40bp (2.09),
  WTI +13bp (0.94, not significant). The biggest historical shocks (2008-10, 2020-03, 2020-04-21 WTI
  −45%) are **not** on scheduled days.
- **Attention is a diagnostic, not a strategy** (`reports/ATTENTION_SIGNAL.md`): it improves next-day
  |move| MAE on 6/8 assets but R² on only 3/8, and in a vol-targeted portfolio the Sharpe goes
  0.64 → 0.63. Do not trade it.

## D12 — Push workflow made snapshot-proof (`scripts/gh_push.sh`)
- **Date:** 2026-11-20 · **Status:** ACTIVE
- Root cause of the lost remote: the platform excludes `.git/config`, `.git-credentials` and
  `.netrc` from workspace snapshots, so any PAT embedded in the remote URL disappears whenever
  the sandbox is recreated. GitHub never received a request — the token was **not** rejected.
- Fix: token stored at `~/.alina/git_token` (mode 600, this path **is** snapshotted), and
  `scripts/gh_push.sh` rebuilds the remote from it on demand. `--save`, `--check` supported;
  the token is masked out of all output.
- Trade-off accepted by the owner: the token sits in plaintext inside the private workspace in
  exchange for not having to re-paste it every session.
