# ALINA Global EA Intelligence Knowledge Base — Data Dictionary (v2.0 / Batch 2)

Updated UTC: `2026-11-21T08:57:12Z`

## Design Principles & Unified 15-Field Schema
- **Canonical Language:** English (`Machine Translation` tag applied where CodeBase prose originated in Russian/Chinese/German/Italian).
- **Evidence Grading (1–7):**
  - `1` = Primary Source Code / Local Measured Experiment (`.mq5/.mq4/.mqh/.h/.pine` statically parsed, `1,718` files)
  - `2` = Official Docs / Full CodeBase Listing Page / Peer-Inspected Guides (`mql5.com`, `forexpeacearmy.com` `Q-1761`)
  - `3` = Academic Research (`arXiv` preprints)
  - `4` = Multiple Independent Sources
  - `5` = Community Reports / Unreadable Compiled Binaries (`.ex5` attachments verified `HTTP 200`, logic `Unverified`)
  - `6` = Commercial Marketing Claims (`Unverified`)
  - `7` = Speculation (tagged explicitly)
- **Verification Status:** `Confirmed`, `Partially Confirmed`, `Inspected - CodeBase Page`, `Conflicting`, `Unverified`, `Blocked`, `Unknown`.
- **Mandatory 15-Field Schema (100% populated on `ea_master` & `indicators`):**
  `unique_id`, `name`, `source_url`, `developer`, `market_and_timeframe`, `trading_logic`, `entry_exit`, `indicators_and_parameters`, `risk_management`, `dependencies`, `evidence`, `verification_status`, `download_path`, `sha256`, `related_records` (plus Batch 1 backward-compatibility columns).
- **Duplicate & Version Retention:** Exact SHA-256 and 5-gram token shingle duplicates/forks are **NEVER deleted** (`duplicates.csv` + `duplicates` SQLite table + `kg_edges`).

## Storage & AI Retrieval Layers (`data/ea_kb/`)
1. `alina_ea_kb.sqlite` — Relational SQLite DB (`ea_master`, `source_files`, `indicators`, `visual_symbols`, `duplicates`, `developers`, `github_repos`, `kg_edges`, `research_queue`) + **FTS5 full-text search (`kb_fts`)** across `2021` RAG chunks.
2. `source_code_index.csv` — Static analysis index across **`1718`** real files (`217` Batch 1 + `1501` Batch 2, `35,160,400` bytes): `.mqh: 1201`, `.mq5: 480`, `.mq4: 24`, `.h: 12`, `.pine: 1`.
3. `sources/` & `sources_batch2/` — Verbatim archived source trees (`sources/` Batch 1 + `sources_batch2/{github,deps,gitlab}/` Batch 2).
4. `ea_master.jsonl` & `ea_master.csv` — **`493`** records (`377` Level 1 local source-verified + `99` Batch 1/2 MQL5 CodeBase pages + `17` closed-source/compiled `.ex5` tagged `Unverified`).
5. `indicators.jsonl` — **`223`** indicator records (`100%` populated 15-field schema).
6. `visual_symbols.jsonl` — **`325`** Wingdings + extracted `DRAW_ARROW`/`PLOT_ARROW`/`OBJ_*` records.
7. `duplicates.csv` — **`1289`** pairwise relationships (`exact_sha256: 400`, `near_duplicate >=0.85: 285`, `fork_or_modified >=0.55: 238`, `shared_code_pattern >=0.35: 366`).
8. `developers.jsonl` & `github_repos_audit.jsonl` — **`197`** developer profiles + **`75`** full GitHub repository tree audits.
9. `batch2_mql5_fetched.json` & `batch2_fpa_q1761.json` — Persisted `fetch_page` artifacts (`212` MQL5 CodeBase records, `27` MQL5 developer profiles, `6` source previews, `Q-1761` ForexPeaceArmy 4 EA scam benchmarks).
10. `research_queue.jsonl` & `research_queue_batch3.jsonl` — All **`1924`** Batch 1/2 tasks reconciled (`pending = 0`); **`951`** follow-up Batch 3 tasks staged cleanly.
11. `knowledge_graph.jsonl` (`4726` triples), `rag_corpus.jsonl` (`2021` docs), `strategies.jsonl` (`377`), `trading_logic.jsonl`, `unclassified.jsonl` (`49`), `risk_management_patterns.jsonl`, `market_behavior_links.jsonl`, `backtest_evidence.jsonl` (`23`), `research_papers.jsonl`, `KB_STATS_BATCH2.json`, `PROOF_OF_WORK_BATCH2.md`.
