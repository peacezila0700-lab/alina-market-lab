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

## Update 2026-11-20 (late) — QR-002 look-ahead found; event layer built
- **QR-002:** multi-asset screen + portfolio used a same-bar position (`pos[i]*ret[i]`). Fixed to
  `pos[i-1]`. Previous "Donchian beats everything" result was the bug: DONCH_30 portfolio Sharpe
  1.72 → **0.37**, vs equal-weight buy & hold **0.70**. Regression test added (14/14 pass).
  `compare_strategies.py` had the same defect; re-run, conclusion unchanged (FX ≈ 0 net of cost).
- Corrected screen: best rules are mostly below their own buy & hold; the only repeatable thread is
  **mean-reversion** (Z_FADE on AUDUSD +0.26, GBPUSD +0.23, FTSE +0.13; MA_20_100 on TLT +0.19, DXY +0.11).
- Event layer (free): 205 FOMC dates 1994-2026, weekly calendar archive (forward-only),
  8 assets × 3,976 days of Wikipedia attention. FOMC days move markets more (t up to 2.84);
  attention is a diagnostic, not an edge (portfolio Sharpe 0.64 → 0.63).
- **Blocker:** `.git/config` is excluded from workspace snapshots, so the remote+token were wiped.
  Two commits (9a1961c, 609a5a4) are local only. Needs the owner to paste the PAT again.
- **Next:** pre-registered mean-reversion test (A1) on the FX/FTSE/AUDUSD/GBPUSD cluster with
  walk-forward + null control; then T18 measured spreads.

## Update 2026-11-20 (later) — EXP-0005 / H09 executed and REJECTED (close miss)
- Pre-registered (f2ce077) → amendment 1 (defective P1 panel) → ran → rejected. EXP-0005 logged.
- P1R EUR9 (ECB 9 crosses, 1999-2026) weekly tercile reversion: Sharpe +0.343 vs bar 0.35,
  null_pct 100.0, WF+ 77.3%, 2x-cost +0.181 vs bar 0.20. **Closest miss yet, still a reject.**
- Sensitivity: passes all four at 0.75x assumed cost. **T18 (measured spreads) now decides everything.**
- H09b: FTSE +0.336 (A1 fail), AUDUSD +0.981 on 977 bars (not evidence), EURUSD negative.
- `data/official/EUR{USD,JPY,GBP,CHF,CAD,SEK,NOK,AUD,NZD}_ECB_D.csv` now hold 7,203 rows each (1999+).
- Push still blocked: 5 commits local (f2ce077, amendment, h09 run, docs). Need PAT.

## Update 2026-11-20 (T18 done) — spreads MEASURED, H09 P1R conditionally supported
- `scripts/measure_spreads.py`: Dukascopy bid/ask via chart API (URL-encoded!). .bi5 host is 503.
  10 instruments, 2003-2025 hourly. EURUSD spread 1.0 -> 0.3 pips (the whole decay story).
- EXP-0005 remains REJECTED (assumed cost). EXP-0006 = same rules, measured cost:
  P1R ECN Sharpe +0.402 / retail +0.358, all four criteria PASS; P2 fails => H09 not formally accepted.
- Economics: 97x turnover/yr, gross +3.96%, cost -1.15%, net +2.53%, Sharpe 0.36, maxDD 26%,
  corr(buy&hold) -0.013. Real by our tests but thin.
- Per-leg: EURJPY/CAD/CHF carry it; SEK/NOK negative after spread; EURUSD no signal (no retuning!).
- NEXT: (a) H10 pre-registration with instrument set chosen by a spread rule written in advance;
  (b) forward paper run of locked P1R rule from 2026-11-20; (c) still want the owner MT5 export.
- Artifacts fixed: `research/artifacts/h09_{assumed,ecn,retail}.json` (an earlier run had overwritten
  the assumed file; recovered from commit 41d541a).

## Update 2026-11-20 (H10 hold-out) — reversion thread CLOSED, zero validated edges
- PREREG_H10 committed before running: 5 cheapest EUR pairs by 2003-2018 spread, tested 2019-2026 only.
- Result: retail Sharpe **+0.126** (bar 0.35), 2x cost +0.069, 3y windows positive **16.7%** (1/6),
  null_pct 93.3 => FAIL A1-A4. Secondary 9-pair +0.202 fails too. EXP-0007 REJECTED.
- => EXP-0006 "conditionally supported" resolved NEGATIVELY. Cross-sectional reversion closes.
- QR-003: Yahoo FX daily returns correlate 0.38-0.52 with ECB fixes (levels 0.99) -> never use them.
- Project tally: 5 pre-registered experiments, 168-test screen, 27y official FX, null on every test,
  **zero validated edges**; one fake edge found and killed (QR-002).
- NEXT (per PREREG_H10 escape clause): H11 = volatility risk premium / carry — a mechanism family
  never tested here; must not reuse reversion data or rules.

## Update 2026-11-20 (H11 VRP) — premium is real, retail trade is not survivable
- PREREG_H11 committed before code. Data: CBOE VIX 9,320 rows (1990+), SPY/VIXY from Yahoo.
- H11a (VRP as state variable): non-monotone quintiles, overlay +0.337 vs B&H +0.406, null 82.6 => FAIL.
- H11b (short VIXY 2011-2026): Sharpe +0.694, null >=95, WF >=60%, survives 2x cost => PASSES A1-A4;
  FAILS A5/A6 (worst 12m -103.7%, worst day -43.1%). Equity goes negative at -100% notional.
- Leverage scan: -20% notional = +8.2%/yr, maxDD 38.8%; -10% = +4.3%/yr, maxDD 16.9%.
- => First mechanism to pass a statistical test in this project; rejected on survivability.
- NEXT: carry (policy-rate sources verified: ECB 200, BoC valet 200, RBA 200, Norges 200, BoE CSV 200,
  SNB 200). Dead: OECD SDMX 403, Riksbank SWEA 204, RBNZ 403. CBOE 307->follow with -L.
