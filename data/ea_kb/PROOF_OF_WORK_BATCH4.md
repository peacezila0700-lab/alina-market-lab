# PROOF OF WORK — BATCH 4 (ALINA Global EA Intelligence Knowledge Base v2.15)

Generated UTC: `2026-11-21T09:55:32Z`

## 1. Batch 4 Queue Reconciliation (`Q-2876..Q-3250` -> `0` Pending)
- **Total Batch 4 Tasks Reconciled:** `375` (`pending_batch4 = 0`)
- **Status Breakdown:** `{"blocked": 201, "deferred": 24, "completed": 144, "completed_stdlib_builtin": 6}`
- **By Task Kind & Outcome:** `{"mql5_source_archive_followup::blocked": 201, "p1_dep_retry_followup::deferred": 2, "batch2_new_include_dependency_followup::deferred": 18, "batch2_new_icustom_target_followup::deferred": 4, "batch3_new_include_dependency::completed": 144, "batch3_new_include_dependency::completed_stdlib_builtin": 6}`
  - `batch3_new_include_dependency` (**`150/150` = `100.0%` resolved**): `144` matched/downloaded verbatim across `EA31337/EA31337-classes`, `EA31337/EA31337`, `9nix6`, `PopovMP`, `francomascareloai`, `nkanven`, `fxce/mt5-libs`, and `roffild/roffildlibrary` + `6` confirmed C++/OS/MQL stdlib headers (`iomanip`, `locale`, `sstream`, `vector`, `windows.h`, `python.h`).
  - `mql5_source_archive_followup` (`201`): Honestly preserved as `blocked_sandbox_mql5_ip` (`scripts/fetch_mql5_non_sandbox.py` built and ready for single-command external fetch).
  - `external/proprietary follow-ups` (`24`): Honestly staged as `deferred` (`AZ-INVEST/SDK`, private indicators).
- **Batch 5 Follow-Up Queue (`research_queue_batch5.jsonl`):** `344` tasks (`{"mql5_external_archive": 201, "p1_dep_retry_external": 2, "batch2_new_include_dependency_external": 18, "batch2_new_icustom_target_external": 4, "batch4_new_include_dependency": 119}`).

## 2. Scaled Static Source Code Analysis (`1982` Files)
- **Total Local Source Files Analyzed:** `1982` (`217` B1 + `1501` B2 + `222` B3 + `42` B4) totaling **`39,160,483` bytes** (`+204,417` B in Batch 4).
- **File Extensions:** `{".mq5": 491, ".h": 165, ".mq4": 24, ".mqh": 1300, ".pine": 1, ".py": 1}`
- **Duplicate & Fork Clustering:** `1312` relationships -> `{"exact_sha256": 400, "fork_or_modified": 238, "shared_code_pattern": 387, "near_duplicate": 287}`

## 3. Master KB Counts (`alina_ea_kb.sqlite`)
- **`ea_master`:** `499` (`383` local verified) | **`indicators`:** `226` | **`visual_symbols`:** `326` | **`strategies`:** `383`
- **Unified 15-Field Completeness:** **`100.0%`** | **`kg_edges`:** `5029` | **`kb_fts`:** `2285` chunks

## 4. Live Batch 4 Source Samples (`batch='batch4'`)
| SRC ID | File | Role | Lines | Author | Local Path |
|---|---|---|---|---|---|
| SRC-1943 | `Include__AZ-INVEST__SDK__TradingChecks.mqh` | Library / Header (.mqh) | 932 | 9nix6 | `data/ea_kb/sources_batch4/github/9nix6__Median-and-Turbo-Renko-indicator-bundle/Include__AZ-INVEST__SDK__TradingChecks.mqh` |
| SRC-1958 | `Chart.struct.tf.h` | Library / Header (.h) | 356 | EA31337 | `data/ea_kb/sources_batch4/github/EA31337__EA31337-classes/Chart.struct.tf.h` |
| SRC-1966 | `Pattern.enum.h` | Library / Header (.h) | 325 | EA31337 | `data/ea_kb/sources_batch4/github/EA31337__EA31337-classes/Pattern.enum.h` |
| SRC-1957 | `Chart.struct.static.h` | Library / Header (.h) | 300 | EA31337 | `data/ea_kb/sources_batch4/github/EA31337__EA31337-classes/Chart.struct.static.h` |
| SRC-1961 | `Indicator__IndicatorCandle.h` | Library / Header (.h) | 267 | EA31337 | `data/ea_kb/sources_batch4/github/EA31337__EA31337-classes/Indicator__IndicatorCandle.h` |
| SRC-1980 | `Forexsb.com__IndicatorManager.mqh` | Library / Header (.mqh) | 244 | PopovMP | `data/ea_kb/sources_batch4/github/PopovMP__FSB_Expert_Advisor_Code/Forexsb.com__IndicatorManager.mqh` |
| SRC-1942 | `Include__AZ-INVEST__SDK__RenkoCustomChartSettings.mqh` | Library / Header (.mqh) | 204 | 9nix6 | `data/ea_kb/sources_batch4/github/9nix6__Median-and-Turbo-Renko-indicator-bundle/Include__AZ-INVEST__SDK__RenkoCustomChartSettings.mqh` |
| SRC-1972 | `Task__TaskAction.struct.h` | Library / Header (.h) | 196 | EA31337 | `data/ea_kb/sources_batch4/github/EA31337__EA31337-classes/Task__TaskAction.struct.h` |
| SRC-1956 | `Buffer__BufferTick.h` | Library / Header (.h) | 169 | EA31337 | `data/ea_kb/sources_batch4/github/EA31337__EA31337-classes/Buffer__BufferTick.h` |
| SRC-1944 | `Include__IncOnRingBuffer__carrayring.mqh` | Library / Header (.mqh) | 153 | 9nix6 | `data/ea_kb/sources_batch4/github/9nix6__Median-and-Turbo-Renko-indicator-bundle/Include__IncOnRingBuffer__carrayring.mqh` |
| SRC-1970 | `Strategy.struct.pricestop.h` | Library / Header (.h) | 146 | EA31337 | `data/ea_kb/sources_batch4/github/EA31337__EA31337-classes/Strategy.struct.pricestop.h` |
| SRC-1971 | `Task__Task.struct.h` | Library / Header (.h) | 145 | EA31337 | `data/ea_kb/sources_batch4/github/EA31337__EA31337-classes/Task__Task.struct.h` |

### Resolved Batch 4 Include Tasks (`batch3_new_include_dependency`)
| Task | Target | Status | Outcome |
|---|---|---|---|
| Q-3101 | `AZ-INVEST/SDK/RenkoCustomChartSettings.mqh` | `completed` | github_tree_downloaded -> data/ea_kb/sources_batch4/github/9nix6__Median-and-Turbo-Renko-indicator-bundle/Incl |
| Q-3102 | `AZ-INVEST/SDK/Normailze.mqh` | `completed` | github_tree_downloaded -> data/ea_kb/sources_batch4/github/9nix6__Median-and-Turbo-Renko-indicator-bundle/Incl |
| Q-3103 | `AZ-INVEST/SDK/TradingChecks.mqh` | `completed` | github_tree_downloaded -> data/ea_kb/sources_batch4/github/9nix6__Median-and-Turbo-Renko-indicator-bundle/Incl |
| Q-3104 | `IncOnRingBuffer/carrayring.mqh` | `completed` | github_tree_downloaded -> data/ea_kb/sources_batch4/github/9nix6__Median-and-Turbo-Renko-indicator-bundle/Incl |
| Q-3105 | `rider/defines.h` | `completed` | github_tree_downloaded -> data/ea_kb/sources_batch4/github/EA31337__EA31337/src__include__common__rider__defin |
| Q-3106 | `advanced/defines.h` | `completed` | github_tree_downloaded -> data/ea_kb/sources_batch4/github/EA31337__EA31337/src__include__common__advanced__de |
| Q-3107 | `lite/defines.h` | `completed` | github_tree_downloaded -> data/ea_kb/sources_batch4/github/EA31337__EA31337/src__include__common__lite__define |
| Q-3108 | `elite/defines.h` | `completed` | github_tree_downloaded -> data/ea_kb/sources_batch4/github/EA31337__EA31337/src__include__common__elite__defin |
| Q-3109 | `common/elite/inputs.mqh` | `completed` | github_tree_dedup_existing_sha256 -> data/ea_kb/sources/github/EA31337__EA31337/src__include__common__elite__i |
| Q-3110 | `common/rider/inputs.mqh` | `completed` | github_tree_dedup_existing_sha256 -> data/ea_kb/sources_batch2/github/EA31337__EA31337/src__include__common__r |
