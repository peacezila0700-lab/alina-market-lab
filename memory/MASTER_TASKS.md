# MASTER TASKS

| ID | Task | Status | Dependency | Acceptance |
|---|---|---|---|---|
| T01..T08 | Stage 0 audit, instrument lock, D1 QC & initial hypotheses (`H01`–`H25`) | DONE | — | `reports/QC_D1.md`, `EXP-0001..0023` |
| T18 | Re-score / test FX with measured Dukascopy bid/ask + public broker matrix | DONE | `D13` | `configs/broker_cost_models.json`, `EXP-0024/0025` |
| T19 | EA KB Batch 4 (`v2.15`): resolve 150 transitive `#include` + 24 non-MQL5 + standalone MQL5 script + SQLite rebuild | DONE | Batch 3 | `KB_STATS_BATCH4.json`, `PROOF_OF_WORK_BATCH4.md`, `fetch_mql5_non_sandbox.py` |
| T20 | EA KB Alpha & Risk Blueprint extraction across 1,982 files / 383 local source-verified EAs | DONE | T19 | `reports/EA_KB_ALPHA_RISK_BLUEPRINT.md`, `H26`–`H28` |
| T21 | Phase A Governance lock (`D13`, `PROJECT_RULES.md`) + `configs/broker_cost_models.json` | DONE | — | `docs/DECISION_LOG.md`, `memory/PROJECT_RULES.md` |
| T22 | Phase B H1 Bid/Ask Data QC + Live `.bi5` M1 -> H1 Parity Check (`EURGBP` & `EURUSD` 23y) | DONE | T21 | `reports/QC_H1_BIDASK.md`, `research/artifacts/qc_h1_bidask.json` |
| T23 | Phase C Unit-Tested 23y Backtests (`EXP-0024` `H26/H27`, `EXP-0025` `H28` + H1 Scalp + 4 Brokers + OOS Locked) | DONE — REJECTED | T20, T22 | `17/17` unit tests PASS, `reports/EXP_0024_PHASE_C.md` |
| T24 | Non-sandbox MQL5 archive harvest (`201` blocked archives -> Batch 5 `344` queue) | READY (Owner non-sandbox run) | — | Run `python3 scripts/fetch_mql5_non_sandbox.py` outside sandbox |
| T25 | Phase D ML Signal/Filter + MQL5 Demo EA (`AlinaRiskGovernor.mq5`) | PARKED (Kill Point) | Validated Phase C `OOS > 0` | Remains `SIG_NONE` / `MODE_PAPER` until a hypothesis clears OOS > 0 |
| T26 | Expand PIT SEC filings beyond 62 US large caps or new non-price alpha (`H21` PTR accumulation) | BACKLOG | Collector growth | Re-test only when power/sample threshold clears |

## Budget & Governance Rules
- `memory/PROJECT_RULES.md` enforced: strict causality (`signal[t] -> fill >= t+1`), no tuning on locked OOS, kill ML/live if OOS <= 0.
- `AlinaRiskGovernor.mq5` stays `SIG_NONE` and `MODE_PAPER`.
