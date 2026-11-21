# PROOF OF WORK — BATCH 3 (ALINA Global EA Intelligence Knowledge Base v2.14)

Generated UTC: `2026-11-21T09:35:18Z`

## 1. Batch 3 Queue Reconciliation (`Q-1925..Q-2875` -> `0` Pending)
- **Total Batch 3 Tasks Reconciled:** `951` (`pending_batch3 = 0`)
- **Status Breakdown:** `{"blocked": 201, "completed": 716, "deferred": 24, "completed_stdlib_builtin": 10}`
- **By Task Kind & Outcome:** `{"mql5_source_archive::blocked": 201, "mql5_source_archive::completed": 2, "gitlab_source_retry::completed": 14, "p1_dep_retry::deferred": 2, "batch2_new_include_dependency::completed": 694, "batch2_new_include_dependency::deferred": 18, "batch2_new_include_dependency::completed_stdlib_builtin": 7, "batch2_new_icustom_target::completed": 6, "batch2_new_icustom_target::deferred": 4, "batch2_new_icustom_target::completed_stdlib_builtin": 3}`
  - `gitlab_source_retry` (**`14/14` = `100%` resolved**): Bypassed GitLab per-file HTTP 429 limits cleanly via GitLab REST API v4 full repository archives (`fxce/mt5-libs` 30 files, `Roffild/RoffildLibrary` 43 files; `HTTP 200`), resolving all 14 queued tasks plus 4 GitLab includes, `Roffild/ToIndicator`, and `18` unique extra GitLab library files.
  - `batch2_new_include_dependency` (**`701/719` = `97.5%` resolved**): `694` matched/downloaded verbatim from audited GitHub/GitLab trees (including `EA31337/EA31337-classes` submodule & `MegaJoctan/MALE5` 278-star repo) + `7` confirmed MetaQuotes standard library headers (`completed_stdlib_builtin`); `18` genuinely deferred (`9` proprietary `AZ-INVEST/SDK` headers + `9` non-repo external dependencies).
  - `batch2_new_icustom_target` (**`9/13` resolved**): `6` downloaded/resolved from repo/GitLab trees + `3` confirmed MT4/MT5 built-ins (`Heiken Ashi`, `Examples/Heiken_Ashi`, `Examples/ZigZag`); `4` proprietary/external targets deferred.
  - `mql5_source_archive` (`203`): `2` matched verbatim local files (`completed`); `201` honestly preserved as `blocked` (`blocked_sandbox_mql5_ip` — MQL5 drops raw `.zip/.mq5` TCP connections on sandbox IP and `fetch_page` HTML-to-Markdown strips `<...>` operators/includes, so uncorrupted raw archive fetch remains queued for non-sandbox execution while CodeBase metadata/logic is already persisted in `batch2_mql5_fetched.json`).
- **Batch 4 Follow-Up Queue (`research_queue_batch4.jsonl`):** `375` tasks (`{"mql5_source_archive_followup": 201, "p1_dep_retry_followup": 2, "batch2_new_include_dependency_followup": 18, "batch2_new_icustom_target_followup": 4, "batch3_new_include_dependency": 150}`) staged cleanly.

## 2. Scaled Static Source Code Analysis & Deduplication (`1,940` Files)
- **Total Local Source Files Analyzed:** `1940` (`217` Batch 1 + `1501` Batch 2 + `222` Batch 3) totaling **`38,956,066` bytes** (`~37.15 MiB` raw source; `+3,795,666` B in Batch 3).
- **File Extensions:** `{".mq5": 491, ".h": 131, ".mq4": 24, ".mqh": 1292, ".pine": 1, ".py": 1}`
- **Static Source Roles:** `{"Expert Advisor (Trading)": 227, "Indicator": 112, "Library / Header (.h)": 131, "Expert Advisor (Modular / Class-based)": 75, "Unclassified Source": 22, "Library / Header (.mqh)": 1292, "Script": 49, "Utility / Diagnostic EA": 31, "Trade / Risk Manager EA": 1}`
- **Duplicate & Fork Clustering (`duplicates.csv`, ALL copies retained):** `1311` relationships -> `{"exact_sha256": 400, "fork_or_modified": 238, "shared_code_pattern": 386, "near_duplicate": 287}`

## 3. Master KB & Retrieval Layer Counts (`alina_ea_kb.sqlite` + JSONL/CSV)
- **`ea_master`:** `499` (`383` Level 1 local source-verified + `99` MQL5 CodeBase inspected + `17` closed-source/binary `Unverified`)
- **`indicators`:** `226` | **`visual_symbols`:** `326` | **`strategies`:** `383`
- **Unified 15-Field Schema Completeness (`ea_master` & `indicators`):** **`100.0%`** verified non-empty across every record
- **`developers`:** `197` | **`github_repos`:** `75` (+ 19 Batch 3 tree audits in `batch3_resolutions.json`)
- **Knowledge Graph (`kg_edges`):** `4986` triples | **SQLite FTS5 (`kb_fts`):** `2243` searchable RAG chunks
- **Lab Evidence Linked:** `23` Experiments (`EXP-0001..0023`), `2028` Event Calendar rows, `1588` Headline rows.

## 4. Live Verified Batch 3 Samples (`alina_ea_kb.sqlite`)
### Largest Newly Downloaded Batch 3 Source Files (`source_files` where `batch='batch3'`)
| SRC ID | File | Role | Lines | Author | Local Path |
|---|---|---|---|---|---|
| SRC-1873 | `MQL5__Include__Math__Alglib__linalg.mqh` | Library / Header (.mqh) | 37629 | francomascareloai | `data/ea_kb/sources_batch3/deps/github/francomascareloai__EA_SCALPER_XAUUSD/MQL5__Include__Math__Alglib__linalg.mqh` |
| SRC-1872 | `MQL5__Include__Math__Alglib__alglibinternal.mqh` | Library / Header (.mqh) | 15934 | francomascareloai | `data/ea_kb/sources_batch3/deps/github/francomascareloai__EA_SCALPER_XAUUSD/MQL5__Include__Math__Alglib__alglibinternal.mqh` |
| SRC-1725 | `Include__AZ-INVEST__SDK__TradeFunctions.mqh` | Library / Header (.mqh) | 1165 | 9nix6 | `data/ea_kb/sources_batch3/deps/github/9nix6__Median-and-Turbo-Renko-indicator-bundle/Include__AZ-INVEST__SDK__TradeFunctions.mqh` |
| SRC-1856 | `Forexsb.com__StrategyTrader.mqh` | Library / Header (.mqh) | 1117 | PopovMP | `data/ea_kb/sources_batch3/deps/github/PopovMP__FSB_Expert_Advisor_Code/Forexsb.com__StrategyTrader.mqh` |
| SRC-1869 | `Include__TradeSniperEngine.mqh` | Library / Header (.mqh) | 1076 | SenaDev007 | `data/ea_kb/sources_batch3/deps/github/SenaDev007__A2Sniper/Include__TradeSniperEngine.mqh` |
| SRC-1801 | `Order.struct.h` | Library / Header (.h) | 1046 | EA31337 | `data/ea_kb/sources_batch3/deps/github/EA31337__EA31337-classes/Order.struct.h` |
| SRC-1862 | `Include__PositionStateMachine.mqh` | Library / Header (.mqh) | 1032 | SenaDev007 | `data/ea_kb/sources_batch3/deps/github/SenaDev007__A2Sniper/Include__PositionStateMachine.mqh` |
| SRC-1803 | `Pattern.struct.h` | Library / Header (.h) | 994 | EA31337 | `data/ea_kb/sources_batch3/deps/github/EA31337__EA31337-classes/Pattern.struct.h` |
| SRC-1861 | `Include__OrderBookEngine.mqh` | Library / Header (.mqh) | 949 | SenaDev007 | `data/ea_kb/sources_batch3/deps/github/SenaDev007__A2Sniper/Include__OrderBookEngine.mqh` |
| SRC-1860 | `Include__OrderBlockEngine.mqh` | Library / Header (.mqh) | 887 | SenaDev007 | `data/ea_kb/sources_batch3/deps/github/SenaDev007__A2Sniper/Include__OrderBlockEngine.mqh` |
| SRC-1920 | `Include__FxceLibs__Trade__Trade.mqh` | Library / Header (.mqh) | 857 | fxce | `data/ea_kb/sources_batch3/gitlab/fxce__mt5-libs/Include__FxceLibs__Trade__Trade.mqh` |
| SRC-1867 | `Include__StrategicReversalEngine.mqh` | Library / Header (.mqh) | 841 | SenaDev007 | `data/ea_kb/sources_batch3/deps/github/SenaDev007__A2Sniper/Include__StrategicReversalEngine.mqh` |

### New Batch 3 Local Source-Verified EAs/Scripts (`ea_master`)
| EA ID | Name | Developer | Market / TF | Status | Local Path |
|---|---|---|---|---|---|
| EA-0378 | Include__FxceLibs__Notification__TelegramD | fxce | Any symbol / chart timeframe (no | Confirmed | `data/ea_kb/sources_batch3/gitlab/fxce__mt5-libs/Include__FxceLibs__Notification__TelegramDLL__Examples__TelegramRecon.mq5` |
| EA-0379 | Include__FxceLibs__Notification__Telegram_ | fxce | Any symbol / chart timeframe (no | Confirmed | `data/ea_kb/sources_batch3/gitlab/fxce__mt5-libs/Include__FxceLibs__Notification__Telegram__Examples__TelegramRecon.mq5` |
| EA-0380 | Scripts__Roffild__UnitTests__ArrayList_Uni | roffild | Any symbol / chart timeframe (no | Confirmed | `data/ea_kb/sources_batch3/gitlab/roffild__roffildlibrary/Scripts__Roffild__UnitTests__ArrayList_UnitTest.mq5` |
| EA-0381 | Scripts__Roffild__UnitTests__Log4MQL_UnitT | roffild | Any symbol / chart timeframe (no | Confirmed | `data/ea_kb/sources_batch3/gitlab/roffild__roffildlibrary/Scripts__Roffild__UnitTests__Log4MQL_UnitTest.mq5` |
| EA-0382 | Scripts__Roffild__UnitTests__MLPDataFile_U | roffild | Any symbol / chart timeframe (no | Confirmed | `data/ea_kb/sources_batch3/gitlab/roffild__roffildlibrary/Scripts__Roffild__UnitTests__MLPDataFile_UnitTest.mq5` |
| EA-0383 | Scripts__Roffild__UnitTests__Serialization | roffild | Any symbol / chart timeframe (no | Confirmed | `data/ea_kb/sources_batch3/gitlab/roffild__roffildlibrary/Scripts__Roffild__UnitTests__Serialization_UnitTest.mq5` |

### Resolved GitLab Retry Tasks (`research_queue` `gitlab_source_retry`)
| Task | Status | Outcome / Local Path |
|---|---|---|
| Q-2128 | `completed` | gitlab_archive_api -> data/ea_kb/sources/gitlab/fxce__mt5-libs/Include__FxceLibs__Notification__Telegram__CustomMessage. |
| Q-2129 | `completed` | gitlab_archive_api -> data/ea_kb/sources/gitlab/fxce__mt5-libs/Include__FxceLibs__Notification__Telegram__CustomChat.mqh |
| Q-2130 | `completed` | gitlab_archive_api -> data/ea_kb/sources/gitlab/fxce__mt5-libs/Include__FxceLibs__Common__CandleSticks__CandleSticksInfo |
| Q-2131 | `completed` | gitlab_archive_api -> data/ea_kb/sources/gitlab/fxce__mt5-libs/Include__FxceLibs__Notification__Telegram__CustomMessage. |
| Q-2132 | `completed` | gitlab_archive_api -> data/ea_kb/sources_batch3/gitlab/fxce__mt5-libs/Include__FxceLibs__Notification__Telegram__NotifyT |
| Q-2133 | `completed` | gitlab_archive_api -> data/ea_kb/sources_batch3/gitlab/fxce__mt5-libs/Include__FxceLibs__Notification__Telegram__NotifyT |
| Q-2134 | `completed` | gitlab_archive_api -> data/ea_kb/sources_batch3/gitlab/fxce__mt5-libs/Include__FxceLibs__Notification__TelegramDLL__Noti |
| Q-2135 | `completed` | gitlab_archive_api -> data/ea_kb/sources_batch3/gitlab/roffild__roffildlibrary/Include__Roffild__OrderSql.mqh |
