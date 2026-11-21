# CURRENT STATE — 2026-11-21 (v2.15: EA KB Batch 4 + Blueprint + 23y Phase B/C Complete)

## Focus
Completed **all three tracks** requested by the owner:
1. **Track 1 — Global EA Intelligence KB Batch 4 (`v2.15`):** Rebuilt `alina_ea_kb.sqlite` across **1,982 static local files (`39,160,483` B)**, resolved **375/375 Batch 4 tasks (`0` pending)** (`150/150` transitive `#include` targets across GitLab/GitHub + `6` MT5 stdlib built-ins + `24` deferred external SDK headers + `201` IP-blocked MQL5 archives exported to standalone `scripts/fetch_mql5_non_sandbox.py`), staged `344` Batch 5 tasks, preserved `1,312` duplicate/fork pairs, `5,029` KG edges, `2,285` FTS5 RAG chunks, `100.0%` 15-field parity, and `25` linked experiments.
2. **Track 2 — EA KB Alpha & Risk Blueprint (`reports/EA_KB_ALPHA_RISK_BLUEPRINT.md`):** Audited all `383` local source-verified EAs (`49.9%` SL, `48.0%` TP, `57.4%` new-bar gate, `15.9%` spread filter, `5.2%` limit/pending orders, `5.7%` equity/DD guard, `30.3%` clean non-martingale + SL + guard) and formalized `H26`–`H28`.
3. **Track 3 — `ALINA_PLAN_v1` Phases A–C + Kill Point (`EXP-0024` & `EXP-0025`):**
   - Locked `D13` (`EURGBP` primary + `EURUSD` control, public broker cost tiers including Exness Raw/Standard, IC Markets Raw, Dukascopy measured + swap `[0, 0.35]`) and wrote `memory/PROJECT_RULES.md`.
   - Passed Phase B QC on 23-year `EURGBP_H1_bidask.csv.gz` (`147,297` bars, median spread `1.0` pip, live `.bi5` M1 `2026-11-18` matched digit-for-digit) & `EURUSD_H1_bidask.csv.gz` (`148,482` bars, median `0.5` pip).
   - Passed `17/17` unit tests (`test_backtest_engine.py` + `test_eurgbp_pipeline.py`).
   - Executed `EXP-0024` & `EXP-0025`: passive limit entry saved `+0.78` pips/trade vs market on 23y EURGBP (`-1.60` vs `-2.38`), `H28_H1_SCALP_BASELINE` collapsed (`-3.35` EURGBP / `-5.86` EURUSD), and **all tested rules remained net negative across 23y IS/VALID/OOS and all 4 broker models** -> **Phase C Kill Point enforced (`Phase D ML & Demo/Live EA PARKED`)**.

## Drive (live target on sync)
- **v2.15 `ALINA_DATAPACK_v2.15.zip`** — built, verified, uploaded to Drive; `v2.12` preserved untouched.
- Workspace kept clean after syncing via `/home/user/CLOUD_SYNC_POINTER.md`.

## Tally
25 pre-registered experiments, 168 screen tests, 144 free-EA family tests, 59 COT tests -> **0 validated directional edges**.
Every trap is documented in `PITFALLS.md`; every rejected hypothesis is documented in `WHAT_FAILED.md` & `research/HYPOTHESIS_REGISTER.csv`.
