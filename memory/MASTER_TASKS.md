# MASTER TASKS

| ID | Task | Status | Dependency | Acceptance |
|---|---|---|---|---|
| T01 | Stage 0 permission audit | DONE | — | evidence in docs/STAGE0_AUDIT.md |
| T02 | Instrument selection with data | DONE | T01 | plan v1 + screening table |
| T03 | GitHub repo scaffold | DONE | — | remote commit verified |
| T04 | Ingest Dukascopy M1→H1 (1y, 2 symbols) | BLOCKED (429) | T02 | H1 csv + spread columns per symbol |
| T04b | QC + manifest on D1 10y research dataset | DONE | — | reports/QC_D1.md PASS, MANIFEST.json |
| T05 | QC report on M1/H1 (Dukascopy) | BLOCKED (429) | T04 | qc_report_M1.md |
| T06 | Dataset manifest + checksum | TODO | T05 | manifest.json |
| T07 | Descriptive stats (D1, 10y) | DONE | T04b | reports/RESEARCH_D1.md (findings with status) |
| T07b | MT5 history export (EURGBP H1, broker-grade) | TODO — owner action | — | CSV with real spread |
| T08 | Hypothesis register (3–5 falsifiable) | DONE — awaiting owner approval of order | T07 | research/HYPOTHESIS_REGISTER.csv + docs/HYPOTHESIS_NOTES.md |
| T09 | Backtest engine + unit tests + EXP-0001 | DONE — H01 not supported | T08 | reports/EXP_0001.md, 13/13 tests |
| T10 | Walk-forward + OOS validation | NOT RUN — moot: H01 rejected first | T09 | deferred |
| T13 | EXP-0002 basket replication (26y × 5 pairs) | DONE — H01 rejected | T09 | reports/EXP_0002.md |
| T14 | Direction decision after rejection (intraday vs new hypothesis family) | WAITING ON OWNER | T13 | decision in DECISION_LOG |
| T10 | Walk-forward + OOS holdout (locked 6 months) | TODO | T09 | IS/OOS report |
| T11 | Broker cost model | BLOCKED | owner: broker + account type | cost spec documented |
| T12 | MT5 EA (MQL5) | PARKED | T10 pass | demo only, never live |

## Budget rules
- max 12 hypotheses tested before a full project review
- 1 session = 1 finished experiment with handoff
- OOS last 6 months locked until final decision
