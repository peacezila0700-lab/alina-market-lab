# ALINA Market Lab — Project Status

Last Updated UTC: `2026-11-21T11:40:00Z` | Active Phase: **Phase C Kill Point (Research, Data Collection, Statistical Analysis & Risk Monitoring Only)**

## 1. Executive Summary & Epistemic Ledger
- **Verified Fact:** Across `29` logged empirical experiments (`EXP-0001..0029`), **`0` directional trading strategies** clear our pre-registered OOS + permutation/bootstrap + realistic transaction-cost survival bars. Phase D Machine Learning, Live Trading, and Demo Trading remain **STRICTLY PARKED**.
- **Verified Fact:** All `15` system health dimensions were empirically audited (`PROJECT_HEALTH_REPORT.md`); blocking engineering defects (`PROB-001` missing `data/universe/`, `PROB-002` date schema / `Unnamed: 0` CSVs, `PROB-003` MarketWatch RSS HTTP 400) were fixed and verified (`16/16` RSS feeds OK, `26/27` daily collector OK, `26` universe CSVs restored, `8/8` Risk Radar panels `FRESH`).
- **Experimental Result:**
  - **Workstream A1 (`EXP-0026`):** Expanded strict Point-in-Time SEC fundamentals from `62` to **`317` US-GAAP companies** (`15,073` snapshots, `16:00 ET acceptanceDateTime` cutoff, `0` leaks). Sloan Negative Accruals (`F_NEG_ACCRUALS`) achieved **IS `+0.943` (`99.0%`) -> OOS `+0.525` (`90.0%`)**, remaining positive at `20 bp` cost (`+0.494`) and in both Large (`+0.442`) and Mid (`+0.541`) caps — yet **FAILED** strict Bonferroni `99.0%` OOS bar and BH FDR (`False/False`).
  - **Workstream A2 (`EXP-0027`):** Macro/CB differentials + Vol Term Structure + OFR FSI **FAILED** OOS directional prediction (`SPY 5d +0.153`, `EURGBP 5d -0.423`), **SUCCEEDED** at volatility-onset ranking (`OOS AUC = 0.7212`, `RV21 corr = +0.4271`), regime separation (`38.12%` inverted vs `13.56%` normal), event-vol measurement (`BoE 1.573x`, `FOMC 1.187x`), and causal drawdown reduction (`SPY IS MaxDD -34.10% -> -16.57%`, `OOS -25.36% -> -16.18%`).
  - **Workstream B (`EXP-0028`, `EXP-0029`):** Retail FX spot carry (`EURGBP`, `EURUSD` over 23 years) failed once `0.25–0.50` pip/night retail swap markups were applied (`+0.006` / `-0.154` ALL Sharpe), while H1 rollover spread timing proved `20–21 UTC` spreads are `2.4x–4.0x` wider than London/NY overlap. Deribit 1H funding cash-and-carry (`25,284` hours, `2024–2026`) & OKX-Deribit basis (`10,000` hours) failed post-cost tradability under Maker/Taker fees + borrow + basis-MtM risk (`OKX-Deribit` 95th `|spread|` `12.89 bps` < `24–32 bps` RT).
  - **Workstream C (EA KB Batch 5):** Backed up SQLite, acquired `118/119` GitHub dependencies + `1` stdlib (`100%` of open GitHub `#include` queue), updated `alina_ea_kb.sqlite` to **`2,100` local source files** (`0` missing paths, `1,322` duplicate relations, `PRAGMA integrity_check == ok`), extracted `5` archetypes across the full corpus, and generated a reproducible local/Colab manual guide for the `201` IP-blocked MQL5 archives.
  - **Workstream D (Daily Risk Radar):** Hardened `scripts/risk_radar.py` + `dashboard/alina_today.html` + `telegram_bot.py` (`/risk`) + `notify_telegram.py` + `.github/workflows/daily_pipeline.yml` as an explicit **Risk Monitoring Tool** (`8/8` panels `FRESH`, `Overall Risk: HIGH` on `2026-11-21` due to `VIX=35.89`, `VIX/VIX3M=1.160`, `VVIX=0.996`).

## 2. Workstream Go / No-Go Scorecard
| Workstream | Objective | Status | Decision / Gate |
|---|---|---|---|
| **A1 — SEC PIT 300+** | Retest `F_NEG_ACCRUALS` on `300–500` US firms with `acceptanceDateTime` | **DONE** (`N=317`) | **NO-GO LIVE / KEEP RESEARCH MONITOR ONLY** (`+0.525` OOS failed `99%` bar + survivor bias) |
| **A2 — Macro/Event Vol** | Separate directional alpha vs vol/regime/sizing value | **DONE** (`2009–26`) | **GO FOR RISK MONITOR / NO-GO DIRECTIONAL** (`AUC 0.721`, `MaxDD -51%` sizing) |
| **B — Microstructure/Carry** | Audit 23y FX carry + 2.9y Deribit/OKX post-cost carry/basis | **DONE** (`EXP-0028/29`) | **NO-GO / REJECT ARBITRAGE CLAIM** (retail carry & cross-venue fail post-cost) |
| **C — EA KB Batch 5** | Acquire GitHub deps, protect DB, audit 5 archetypes, guide MQL5 | **DONE** (`2,100` files) | **GO COMPLETE** (`118` files + `1` stdlib; `201` MQL5 legally deferred to PC/Colab) |
| **D — Daily Risk Radar** | Harden automated phone/GitHub risk monitor + SLAs + alerts | **DONE** (`8/8 FRESH`) | **GO LIVE MONITORING** (Requires user setting `TELEGRAM_BOT_TOKEN` secret in GitHub) |

## 3. Epistemic Classification Summary
- **Verified Fact:** `2,100` KB files exist on disk (`integrity_check == ok`), `317` SEC companies have `0` PIT date leaks, `25,284` hourly Deribit rows downloaded, `16/16` RSS feeds pass, `dashboard/alina_today.html` is 11 KB self-contained offline HTML.
- **Experimental Result:** All numerical Sharpes, AUCs, MaxDDs, spread ratios, and percentile ranks in `EXP-0026..0029` come directly from deterministic scripts under `scripts/`.
- **Hypothesis:** `H29`–`H32` pre-registered hypotheses are now empirically resolved (only risk-sizing/volatility/execution-window rules survived; all directional & carry/arbitrage hypotheses rejected at retail costs).
- **Unverified Claim:** Any external claim of MQL5 commercial EA profitability inside the `201` blocked archives remains unverified until legally acquired via user PC/Colab and verified against real broker costs.
- **Missing Evidence:** Delisted SEC tickers (survivorship bias in `EXP-0026`), historical retail FX broker swap tables (`EXP-0028` bounded via `[0..0.50]` pip/night haircut), OKX funding >93d, Binance/Bybit futures feeds (sandbox HTTP 451/403), `treasury_auctions` (FiscalData HTTP 404).
- **Conflicting Evidence:** `EXP-0027` OOS Vol-Expansion **AUC = `0.7212`** (strong rank separation) conflicts with raw RV level **`R² = -0.021`** / **`BSS = -0.157`** (IS-to-OOS variance calibration drift), proving rank/regime alerts are reliable while static linear probability thresholds require rolling calibration.
