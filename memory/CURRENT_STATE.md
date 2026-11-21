# CURRENT STATE — 2026-11-21 (v2.13: Global EA Intelligence KB Batch 2 Complete + v2.12 baseline)

## Focus
Global Research Agent + Persistent AI/RAG-ready **Private AI Trading Knowledge Base** under `alina_lab/data/ea_kb/` (**Batch 2 complete**: static reverse-engineering of **1,718 downloaded `.mq5/.mq4/.mqh/.h/.pine` files (`35.16 MB`)**, 100% of 205 unique queued MQL5 CodeBase pages + 27 developer profiles + ForexPeaceArmy `Q-1761` + 75 GitHub repo audits + ForexFactory `.ex5` metadata, SQLite+FTS5 DB, 4,726 KG edges, 1,289 duplicate/fork pairs retained, 100% 15-field schema completeness, and `1,924/1,924` Batch 2 queue reconciled with `0` pending). App frozen.

## Drive (live)
- **v2.13 `1sXRKNIXvL5Pxuts2y8-qVG0q0XXjYCGw`** — 56 datasets / 2,410 files / 81.05 MB (`81,050,728` B, MD5 `a36fe8427c3c3cfa04c61daa67c42e26`). **Current.**
- **v2.12 `1iFzwkn17hDD6O8lJeXpqPkHyjxCJcTYG`** — 56 datasets / 890 files / 73.4 MB (`73,418,168` B, preserved untouched alongside v2.13).
- v2.11 (`1biZ1JbdXYH5p3f8NFGIxQ_u2RuPVOVi3`) and older trashed prior to v2.12. Local temp build dirs cleaned after upload.

## Shipped this session (chronological)
15. **Global EA Intelligence Knowledge Base — Batch 2 (`scripts/ea_kb_batch2_*.py`, updated `ea_source_analyzer.py` + `.h` support → `data/ea_kb/`) → v2.13:**
    - Resolved `1,924/1,924` Batch 2 research queue tasks (`0` pending: `1,635` completed, `12` completed metadata-only `.ex5`, `262` deferred, `15` blocked HTTP-429/withdrawn) and staged `951` Batch 3 follow-up tasks (`research_queue_batch3.jsonl`).
    - Staged `1,501` new Batch 2 files (`30.15 MB`) under `sources_batch2/` (`1,368` GitHub, `112` P1 deps, `21` GitLab) + persisted `212` MQL5 CodeBase pages (`100%` of 205 queued IDs, `89` refreshed verbatim), `27` MQL5 developer profiles, and `Q-1761` ForexPeaceArmy scams guide.
    - Analyzed all **1,718** local files statically, built **1,289** SHA-256 + 5-gram shingle duplicate/fork pairs (all retained), populated **100%** of 15 unified fields across **493 EAs** and **223 Indicators**, **325 Visual Symbols**, **197 Developers**, **75 GitHub Repo Audits**, **4,726 Knowledge Graph edges**, and **2,021 FTS5 RAG chunks** (`alina_ea_kb.sqlite` `5.99 MB`).
    - Documented full verified audit in `data/ea_kb/DATA_DICTIONARY.md` and `data/ea_kb/PROOF_OF_WORK_BATCH2.md`.
14. **Global EA Intelligence Knowledge Base — Batch 1 (`scripts/ea_source_analyzer.py`, `ea_kb_crawler.py`, `ea_kb_build.py`, `ea_kb_report.py` → `data/ea_kb/`) → v2.12:**
    - Downloaded & statically reverse-engineered **217 verbatim source files (`5.01 MB`)** across MQL5 CodeBase, GitHub, GitLab (`fxce/mt5-libs` `develop`, `RoffildLibrary`), ForexFactory attachments, and local `AlinaRiskGovernor.mq5`.
    - Built **SQLite+FTS5 (`alina_ea_kb.sqlite`)** + JSONL/CSV layers: **96 EAs** (`90` Level 1 source-verified, `1` Level 2 doc-inspected `NewsBacktest`, `5` Level 5–6 commercial/unverified `.ex5` claims never guessed), **63 Indicators**, **204 Visual Symbol / Wingdings records**, **69 Developers**, **90 Decomposed Strategies**, **10 Exact/Fork/Shared-Code Duplicates** (all preserved), **28 Unclassified/Unknown records**, **725 Knowledge Graph edges**, **230 FTS5 RAG chunks**, and **1,924 persistent `research_queue.jsonl` tasks** for Batch 2+.
    - Full Batch 1 audit & real HTTP/source counts documented in `data/ea_kb/DATA_DICTIONARY.md` and `data/ea_kb/PROOF_OF_WORK_BATCH1.md`.
1. News (294/15 feeds), levels (28 instr), 68-ETF panel, daily brief → v2.0/2.1
2. EXP-0010..0012 (events, auctions, cross-section) → all FAIL
3. EXP-0013/0014 (breadth overlays, gamma vs vol targeting) → FAIL
4. CBOE term structure + VOL_REGIME_BASE_RATES + Treasury 1990-2026 backfill (9,228 rows) + OKX deep;
   EXP-0015 (onset: AUC 0.746 but loses to vol targeting) / EXP-0016 (bond carry) → FAIL → v2.2
5. **Dukascopy hourly bid+ask, 6 pairs, 2003-2026, ~145k bars each** + HOUR_OF_DAY_PROFILE;
   EXP-0017 (5 hourly rules, net Sharpe −0.4..−10.8) / EXP-0018 (gating, breakeven multiple 0.03-0.29)
   → FAIL → v2.3
6. **Coverage build-out (v2.5)** — the owner's 13 categories: `build_technical_indicators.py`
   (209 instruments × 40 indicators), `fetch_stock_panel.py` (115 US stocks), `fetch_sec_fundamentals.py`
   (top 60: SEC XBRL as-filed + 10-K/10-Q/8-K/Form 4 filings), `build_screener.py` (7,301 symbols joined,
   staleness columns), `fetch_news_world.py` (1,294 headlines / 425 outlets / 16 country editions),
   `fetch_worldbank.py` (22 economies × 9 indicators 1990-2025), `research/COVERAGE_MATRIX.md`.
7. **`scripts/build_insider.py`** — Form 4 XML parsed from EDGAR: 1,652 transactions, 347 insiders,
   35 purchases vs 969 sales. Sample too small for a study yet (only 4 purchases have price history);
   the daily collector must accumulate filings. Field-level staleness (`filed`) is the leak rule.
8. **Third-party review + congress data (v2.7)** — read the `day-trader-skill` source (MIT): keep its
   opening-range-breakout definition and clock discipline; reject its Time Machine (no costs at all — a
   GROSS distribution next to a real account is the most expensive beginner mistake in day trading).
   Ported the House Clerk route: `scripts/fetch_congress_trades.py` → 6,365 parsed PTR transactions +
   3,207-filing index 2019-2026. EXP-0019 failed with a textbook sign flip (IS 0.0th pct, OOS 99.5th).
9. **Zero-budget build path (v2.8)** — `fetch_thai_panel.py` (64 SET names, 10y, SET_EW index because
   ^SET has no free history), `build_dashboard.py` (10 KB self-contained phone page), and
   `research/BUILD_PLAN_ZERO_BUDGET.md` (corrects the popular Dify+Colab+Unsloth plan).
10. **Training kit (v2.9)** — `training/build_dataset.py` → 213 instruction pairs; `training/finetune_qwen3_kaggle.py`
    (UNTESTED, no GPU here). Local Ollama path superseded by user's mobile-only constraint (see v2.10).
11. **PIT SEC + ML Signal Tests + Mobile Ops (v2.10):**
    - Fixed `fetch_sec_fundamentals.py` (ASC 606 tag-switch cutoff on 17 tickers + CAT NI tag; `--top 80` → 102,170 rows, 63 US-GAAP filers, 0 stale NI).
    - `scripts/build_pit_fundamentals.py` → `data/sec/pit_fundamentals.csv` (3,794 rows, 63 tickers, 4,618 comparative restatement series blocked from backdating).
    - **EXP-0020 (`scripts/test_ml_us_stocks.py`, H22):** Purged walk-forward Ridge/HGB on 112 US stocks + macro/DIX-GEX + PIT SEC → **FAIL** (L/S OOS −0.115..+0.360, 76–89th pct vs 99th bar; LO OOS +0.63..+0.96 < EW +1.39).
    - **EXP-0021 (`scripts/test_thai_set.py`, H23):** First experiment on 64 Thai SET stocks (27 bp/side retail cost = 16.8 bp Cash Balance fee+VAT + ~10 bp spread) → **FAIL** (ML Ridge/HGB hit 100th/99.5th pct IS then flipped −0.37/−0.29 OOS; 5d reversal −2.37/−1.70 Sharpe).
    - `scripts/ask.py` (Gemini/Groq/OpenRouter/Ollama, dry-run tested ~9k tokens), `scripts/notify_telegram.py` (dry-run tested), `.github/workflows/daily_pipeline.yml`, `build_dashboard.py` +SET64 summary, `research/MOBILE_SIGNAL_ARCHITECTURE_2026.md`.
12. **EXP-0022 / EXP-0023 + Two-Way Telegram Bridge (v2.11):**
    - **EXP-0022 (`scripts/test_pit_fundamentals.py`, H24):** Standalone 63d test on `pit_fundamentals.csv` (62 US GAAP large caps). Sloan accruals (`F_NEG_ACCRUALS`) positive in both IS (+0.624, 93.5th pct) and OOS (+0.947, 92.0th pct; LO OOS +2.015 vs EW +1.830), underpowered for 98.75th pct bar at N=62 → **FAIL**.
    - **EXP-0023 (`scripts/test_crypto_1h.py`, H25):** OKX 1H BTC/ETH 9,999 confirmed bars (`2025-10..2026-11`). `CR_PAIR_ETH_BTC` gross Sharpe +1.604/+2.389 (BE +2.62/+3.06 bp/side) destroyed by 5–10 bp/side fees (−4.43/−5.29 at 10 bp; −1.51 at 5 bp) → **FAIL**.
    - `scripts/telegram_bot.py` (`/status`, `/set`, `/levels SYMBOL`, free-text Gemini/Groq routing; dry-run tested) + `.github/workflows/telegram_qa.yml` + PWA tags on `dashboard/alina_today.html`.
13. **`scripts/event_pack.py`** — one self-describing ~35 KB JSON per day.

## Tally
23 experiments, 168 screen, 144 family, 59 COT, 0 validated edges. Every failure is in
`WHAT_FAILED.md` with the reason; every trap is in `PITFALLS.md` (#1-#19).

## The three sentences that carry the whole project
**Variance is forecastable, direction is not.** State variables cut drawdown (gamma −27% vs −51%, bond
carry halves 2022-26 losses) but never add mean return per unit of exposure, and the one real hourly FX
edge (+0.19 bp/hour gross reversal) is smaller than the 0.34 bp/hour spread it must cross.

## Measured highlights (do not re-derive)
- FOMC day |SPY move| is only **1.09×** a random day (TLT 1.15×) — the meeting matters far less
  than the narrative suggests. NFP (rule) hits bonds harder: TLT 1.33×.
- OPEX day SPY mean −0.170%, only **42.6% positive**; month-end −0.045% / 45.1% positive.
- Treasury auction days are *calmer* than average (SPY |move| 0.88×).
- VIX first crossing 30: SPY same-day median +0.60%, forward 5d mean +1.03%.
- SHOCK (>2.5σ) days: d5 mean −0.02% but median +0.437% — the mean is dragged by 2008/2020.

## Verified / not verified
- Free intraday: OKX 1H/1m crypto candles work with deep history (BTC/ETH to ~2020). Dukascopy
  **1MIN is now 403** (1HOUR still OK). Yahoo 5m restricted (422). No free real-time feed → an
  hour-level bot is only realistic on crypto, or on FX with hourly bars and pessimistic latency.
- EA still never compiled. Governor logic unit-tested 21/21.

## Next
1. Wire the collector to a daily schedule (cron) — the store is the moat.
2. Event-conditional signal tests (the event DB exists now; nothing has been tested against it).
3. Auction demand (bid-to-cover z) → forward bond/equity returns; data is in hand.
