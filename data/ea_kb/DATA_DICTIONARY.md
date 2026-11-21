# ALINA Global EA Intelligence Knowledge Base — Data Dictionary (v1.0 / Batch 1)

## Design Principles
- **Canonical Language:** English (`Machine Translation` tag applied if prose translated; original titles/URLs/comments preserved in Turkish/Russian/Japanese/Chinese).
- **Evidence Grading (1–7):**
  - `1` = Primary Source Code / Local Measured Experiment (`.mq5/.mq4/.mqh` statically parsed)
  - `2` = Official Documentation (`mql5.com/en/docs/...`)
  - `3` = Independent / Academic Research (`arXiv` preprints)
  - `4` = Multiple Independent Sources
  - `5` = Community / User Reports (Reddit / ForexFactory / MQL5 reviews)
  - `6` = Commercial Marketing Claims (closed-source `.ex5` product pages)
  - `7` = Speculation (tagged explicitly, never presented as fact)
- **Verification Status:** `Confirmed`, `Partially Confirmed`, `Unverified`, `Conflicting`, `Unsupported`, `Unknown`.
- **Duplicate Retention:** Duplicates/forks are NEVER deleted (`duplicates.csv` + `duplicates` SQLite table + `kg_edges`).

## Storage & AI Retrieval Layers (`data/ea_kb/`)
1. `alina_ea_kb.sqlite` — Relational SQLite DB + **FTS5 full-text search virtual table (`kb_fts`)** across `230` RAG chunks.
2. `rag_corpus.jsonl` — Chunked RAG records (`doc_id`, `entity_id`, `kind`, `title`, `source_url`, `evidence_level`, `verification_status`, `text`).
3. `knowledge_graph.jsonl` — `725` typed triples (`EA/SRC/IND <-> Developer / VisualSymbol / Strategy / Indicator / Duplicate`).
4. `ea_master.jsonl` & `ea_master.csv` — Master EA database (`96` records: `90` Level 1 verified source code + `1` Level 2 doc-inspected framework + `5` Level 5–6 commercial/unverified).
5. `source_code_index.csv` — Index of `217` analyzed `.mq5/.mq4/.mqh/.py/.pine` source files (`SHA-256`, bytes, handlers, inputs, indicators, repaint & grid/martingale flags).
6. `sources/` — Verbatim archived source files (`mql5_ea/`, `mql5_ind/`, `github/`, `gitlab/`, `forexfactory/`).
7. `indicators.jsonl` — `63` indicator records (parsed source indicators + `fetch_page`-inspected MQL5 indicators).
8. `visual_symbols.jsonl` — `204` records (official Wingdings table + extracted `DRAW_ARROW`/`PLOT_ARROW`/`OBJ_ARROW`/`DRAW_LINE` buffers & repaint warnings).
9. `strategies.jsonl` & `trading_logic.jsonl` — Decomposed workflow records (`Market Condition -> Setup -> Signal -> Confirmation -> Entry -> SL -> TP -> Position Mgmt`).
10. `developers.jsonl` — `69` developer profiles/links linked to authored systems.
11. `duplicates.csv` — Exact SHA-256 (`3`) + Structural 5-gram Jaccard fork/similarity pairs (`7`).
12. `unclassified.jsonl` — `28` unclassified sources, unknown `iCustom` dependencies, and `.ex5`-only binaries.
13. `research_queue.jsonl` — `1,924` persistent follow-up research tasks for Batch 2+.
14. `market_events_index.json` / `financial_news_index.json` / `backtest_evidence.jsonl` / `research_papers.jsonl` / `risk_management_patterns.jsonl` / `market_behavior_links.jsonl` / `source_websites.json`.
