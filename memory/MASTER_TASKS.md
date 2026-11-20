# MASTER TASKS

| ID | Task | Status | Dependency | Acceptance |
|---|---|---|---|---|
| T01 | Stage 0 permission audit | DONE | — | evidence in docs/STAGE0_AUDIT.md |
| T02 | Instrument selection with data | DONE | T01 | plan v1 + screening table |
| T03 | GitHub repo scaffold | DONE | — | remote commit verified |
| T04 | Ingest Dukascopy M1→H1 (1y, 2 symbols) | BLOCKED (429) | T02 | H1 csv + spread columns per symbol |
| T04b | QC + manifest on D1 10y research dataset (Yahoo) | TODO (next) | — | qc_report + manifest |
| T05 | QC report (dupes, gaps, flat bars, OHLC, cross-check ECB) | TODO | T04 | qc_report.md + pass/fail per check |
| T06 | Dataset manifest + checksum | TODO | T05 | manifest.json |
| T07 | Descriptive stats (D1, 10y): half-life, regimes, stability | TODO | T05 | research note with status per finding |
| T08 | Hypothesis register (3–5 falsifiable) | TODO | T07 | HYPOTHESIS_REGISTER.csv |
| T09 | Baseline #1 mean-reversion + backtest engine + unit tests | TODO | T08 | trade ledger + net expectancy after cost |
| T10 | Walk-forward + OOS holdout (locked 6 months) | TODO | T09 | IS/OOS report |
| T11 | Broker cost model | BLOCKED | owner: broker + account type | cost spec documented |
| T12 | MT5 EA (MQL5) | PARKED | T10 pass | demo only, never live |

## Budget rules
- max 12 hypotheses tested before a full project review
- 1 session = 1 finished experiment with handoff
- OOS last 6 months locked until final decision
