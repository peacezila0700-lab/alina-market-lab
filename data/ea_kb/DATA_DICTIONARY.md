# ALINA Global EA Intelligence Knowledge Base — Data Dictionary (v4.0 / Batch 4)

Updated UTC: `2026-11-21T09:55:32Z`

## Design Principles & Unified 15-Field Schema
- **Canonical Language:** English (`Machine Translation` tag applied where CodeBase prose originated in Russian/Chinese/German/Italian).
- **Evidence Grading (1–7):**
  - `1` = Primary Source Code / Local Measured Experiment (`.mq5/.mq4/.mqh/.h/.pine/.py` statically parsed, `1982` files)
  - `2` = Official Docs / Full CodeBase Listing Page / Peer-Inspected Guides (`mql5.com`, `forexpeacearmy.com` `Q-1761`)
  - `3` = Academic Research (`arXiv` preprints)
  - `4` = Multiple Independent Sources
  - `5` = Community Reports / Unreadable Compiled Binaries (`.ex5` attachments verified `HTTP 200`, logic `Unverified`)
  - `6` = Commercial Marketing Claims (`Unverified`)
  - `7` = Speculation (tagged explicitly)
- **Verification Status:** `Confirmed`, `Partially Confirmed`, `Inspected - CodeBase Page`, `Conflicting`, `Unverified`, `Blocked`, `Unknown`.
- **Mandatory 15-Field Schema (100% populated on `ea_master` & `indicators`):**
  `unique_id`, `name`, `source_url`, `developer`, `market_and_timeframe`, `trading_logic`, `entry_exit`, `indicators_and_parameters`, `risk_management`, `dependencies`, `evidence`, `verification_status`, `download_path`, `sha256`, `related_records`.
- **Duplicate & Version Retention:** Exact SHA-256 and 5-gram token shingle duplicates/forks are **NEVER deleted** (`duplicates.csv` + `duplicates` SQLite table + `kg_edges`).

## Storage & AI Retrieval Layers (`data/ea_kb/`)
1. `alina_ea_kb.sqlite` — Relational SQLite DB (`ea_master`, `source_files`, `indicators`, `visual_symbols`, `duplicates`, `developers`, `github_repos`, `kg_edges`, `research_queue`) + **FTS5 full-text search (`kb_fts`)** across `2285` RAG chunks.
2. `source_code_index.csv` — Static analysis index across **`1982`** real files (`217` B1 + `1501` B2 + `222` B3 + `42` B4, `39,160,483` bytes): `.mqh: 1300`, `.mq5: 491`, `.h: 165`, `.mq4: 24`, `.pine: 1`, `.py: 1`.
3. `sources/`, `sources_batch2/`, `sources_batch3/`, & `sources_batch4/` — Verbatim archived source trees.
4. `ea_master.jsonl` & `ea_master.csv` — **`499`** records (`383` Level 1 local source-verified + `99` MQL5 CodeBase pages + `17` closed-source/compiled `.ex5` tagged `Unverified`).
5. `indicators.jsonl` — **`226`** indicator records (`100%` populated 15-field schema).
6. `visual_symbols.jsonl` — **`326`** Wingdings + extracted `DRAW_ARROW`/`PLOT_ARROW`/`OBJ_*` records.
7. `duplicates.csv` — **`1312`** pairwise relationships (`exact_sha256: 400`, `near_duplicate >=0.85: 287`, `fork_or_modified >=0.55: 238`, `shared_code_pattern >=0.35: 387`).
8. `research_queue.jsonl` (`1924` B2 reconciled), `research_queue_batch3.jsonl` (`951` B3 reconciled), `research_queue_batch4.jsonl` (`375` B4 reconciled, `0` pending_batch4), & `research_queue_batch5.jsonl` (`344` B5 external/follow-up staged; plus standalone `scripts/fetch_mql5_non_sandbox.py` for the 201 MQL5 raw archives).
