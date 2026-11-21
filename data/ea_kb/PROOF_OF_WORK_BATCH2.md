# PROOF OF WORK — BATCH 2 (ALINA Global EA Intelligence Knowledge Base v2.13)

Generated UTC: `2026-11-21T08:57:12Z`

## 1. Batch 2 Queue Reconciliation (`Q-0001..Q-1924` -> `0` Pending)
- **Total Batch 2 Queue Items Reconciled:** `1924` (`pending = 0`)
- **Status Breakdown:** `{"completed": 1635, "blocked": 15, "deferred": 262, "completed_metadata_only": 12}`
  - `completed` (`1,635`): `1,133` GitHub queue files + `21` GitLab files + `161` P1 dependencies + `75` GitHub repo tree audits + `219` MQL5 CodeBase pages (covering `100%` of `205` unique queued CodeBase IDs, with `89` refreshed verbatim in `R1–R4`) + `25` MQL5 developer profiles (`+2` extras `eleanna74`, `kayruyuta`) + `1` ForexPeaceArmy `Q-1761` EA Scams guide.
  - `completed_metadata_only` (`12`): ForexFactory `.ex5` attachments (`Q-1749..Q-1760`) scraped `HTTP 200` for thread metadata while internal binary logic remains strictly tagged `Unverified` (`Evidence Level 5`).
  - `deferred` (`262`): `260` GitHub unit-test/auxiliary helper `.mqh` files (repo trees fully audited & stored in `github_repos_audit.jsonl`) + `2` P1 deferred dependencies (`batch2_p1_deps.json`).
  - `blocked` (`15`): `14` GitLab raw fetches throttled by unauthenticated `HTTP 429` + `1` MQL5 listing (`code/46563`) withdrawn by author `William210`.
- **Batch 3 Follow-Up Queue (`research_queue_batch3.jsonl`):** `951` tasks (`{"mql5_source_archive": 203, "gitlab_source_retry": 14, "p1_dep_retry": 2, "batch2_new_include_dependency": 719, "batch2_new_icustom_target": 13}`) staged cleanly for non-sandbox archive downloads and newly discovered dependencies.

## 2. Scaled Static Source Code Analysis & Deduplication (`1,718` Files)
- **Total Local Source Files Analyzed:** `1718` (`217` Batch 1 + `1501` Batch 2) totaling **`35,160,400` bytes** (`~33.5 MiB` raw source).
- **File Extensions (`.h` C/MQL header parser added):** `{".mq5": 480, ".h": 12, ".mq4": 24, ".mqh": 1201, ".pine": 1}`
- **Static Source Roles:** `{"Expert Advisor (Trading)": 227, "Indicator": 109, "Library / Header (.h)": 12, "Expert Advisor (Modular / Class-based)": 73, "Unclassified Source": 19, "Library / Header (.mqh)": 1201, "Script": 45, "Utility / Diagnostic EA": 31, "Trade / Risk Manager EA": 1}`
- **Duplicate & Fork Clustering (`duplicates.csv`, ALL copies retained):** `1289` relationships -> `{"exact_sha256": 400, "fork_or_modified": 238, "shared_code_pattern": 366, "near_duplicate": 285}`

## 3. Master KB & Retrieval Layer Counts (`alina_ea_kb.sqlite` + JSONL/CSV)
- **`ea_master`:** `493` (`377` Level 1 local source-verified + `99` MQL5 CodeBase inspected + `17` closed-source/binary `Unverified`)
- **`indicators`:** `223` | **`visual_symbols`:** `325` | **`strategies`:** `377`
- **Unified 15-Field Schema Completeness (`ea_master` & `indicators`):** **`100.0%`** verified non-empty across every record
- **`developers`:** `197` | **`github_repos`:** `75` (3,014 `.mq*` + 656 `.py` files discovered)
- **Knowledge Graph (`kg_edges`):** `4726` triples | **SQLite FTS5 (`kb_fts`):** `2021` searchable RAG chunks
- **Lab Evidence Linked:** `23` Experiments (`EXP-0001..0023`), `2028` Event Calendar rows, `1588` Headline rows, + `FPA Q-1761` 4 scam patterns.

## 4. Key Empirical & Negative Findings Captured in Batch 2 (Preventing Survivorship / Publication Bias)
- **ForexPeaceArmy (`Q-1761`):** Documented 4 EA scam patterns — lot-doubling martingale masking `93.02%` relative DD behind `31.11%` equity graphs & `200–1,000` lots; `277–1,287` day loser holding; `0–3s` latency-arbitrage feed scalpers; missing `SL=0` wipeouts.
- **Explicit Negative / Disconfirmed MQL5 CodeBase Results:**
  - `78778` (`SupertrendScalper`, `saadbig02`): XAUUSD M5 **failed after realistic spread + slippage**.
  - `79585` (`PrevDay_FirstTouch`, `saadbig02`): `2010–2026` XAUUSD `3,637` PDH/PDL touches won `~50%` breakout and fading performed worse.
  - `79797` (`Gold_Session_Liquidity_Free_MT5`, `fxliner`): Author discloses previous tests failed to show consistent profitability.
  - `79730` (`SqueezeScanner`, `SGupta30`): XAUUSD H4 BB/Keltner squeeze needed `>=3.0 ATR` stops (`<=2.5 ATR` broke edge).
  - `78981` (`SpreadClock`): Deriv XAUUSD `7.6M` ticks averaged `15` pts normal vs `28–35` pts (`2.3x`) at rollover.
  - `79760` (`SwapCostPanel`): Overnight swap consumed `15–18%` of gross BTC profit.
  - `78891` (`AwesomeOscillatorPullback`): Claimed `+209% / PF 1.29` mined from `1.2M` optimization runs (severe multiple-testing risk); `68082` (`DataTraderH4Breakout`) tested unprofitable on EURUSD; `78454` (`SMC_StructureFVG_EA`) & `78308` (`Gold_Fractal_Breakout_EA`) explicitly flagged non-profitable; `57272` (`Triangular_Arbitrage`) critiqued by `fxsaber` for `~60ms` tester lag distortion; `79684` (`NyTime.mqh`) resolves MT5 Strategy Tester `TimeGMT() == server time` bug.

## 5. Live Verified Database Samples (`alina_ea_kb.sqlite`)
### Sample Batch 2 GitHub/GitLab Local Source-Verified EAs (`ea_master`)
| EA ID | Name | Developer | Market / TF | Status | Local Path |
|---|---|---|---|---|---|
| EA-0102 | MT5 to Telegram | 6alaile | Any symbol / chart timeframe (no | Confirmed | `data/ea_kb/sources_batch2/github/6alaile__MetaTrader5-to-Telegram/MT5 to Telegram.mq5` |
| EA-0103 | Experts__2MA_Cross | 9nix6 | Any symbol / chart timeframe (no | Confirmed | `data/ea_kb/sources_batch2/github/9nix6__Median-and-Turbo-Renko-indicator-bundle/Experts__2MA_Cross.mq5` |
| EA-0104 | Experts__ExampleEA | 9nix6 | Any symbol / chart timeframe (no | Confirmed | `data/ea_kb/sources_batch2/github/9nix6__Median-and-Turbo-Renko-indicator-bundle/Experts__ExampleEA.mq5` |
| EA-0105 | Experts__ExampleEA2 | 9nix6 | Any symbol / chart timeframe (no | Confirmed | `data/ea_kb/sources_batch2/github/9nix6__Median-and-Turbo-Renko-indicator-bundle/Experts__ExampleEA2.mq5` |
| EA-0106 | Experts__ExampleEA3 | 9nix6 | Any symbol / chart timeframe (no | Confirmed | `data/ea_kb/sources_batch2/github/9nix6__Median-and-Turbo-Renko-indicator-bundle/Experts__ExampleEA3.mq5` |
| EA-0107 | Experts__PriceMA_Cross | 9nix6 | Any symbol / chart timeframe (no | Confirmed | `data/ea_kb/sources_batch2/github/9nix6__Median-and-Turbo-Renko-indicator-bundle/Experts__PriceMA_Cross.mq5` |
| EA-0108 | Experts__Renko_EA | 9nix6 | Any symbol / chart timeframe (no | Confirmed | `data/ea_kb/sources_batch2/github/9nix6__Median-and-Turbo-Renko-indicator-bundle/Experts__Renko_EA.mq5` |
| EA-0109 | BB-Trend-Trader__BB Trend Trader | Desmath3 | Any symbol / chart timeframe (no | Confirmed | `data/ea_kb/sources_batch2/github/Desmath3__MT5-EA-Project/BB-Trend-Trader__BB Trend Trader.mq5` |

### Sample Conflicting / Disconfirmed / Blocked CodeBase Items
| EA ID | Name | Developer | Empirical Evidence / Note | URL |
|---|---|---|---|---|
| EA-B2-0387 | Awesome Oscillator Pullback | Cristhian Alexander Gaibor Cuasquer | DISCONFIRMED/SELECTION-BIAS FLAG: Author claims +209% / PF 1.29 selected from 1.2M mined optimization candidat | https://www.mql5.com/en/code/78891 |
| EA-B2-0389 | Supertrend Scalper EA | Saad Ferdi | NEGATIVE EMPIRICAL EVIDENCE: Author explicitly tested XAUUSD M5 and reported the strategy FAILED after realist | https://www.mql5.com/en/code/78778 |
| EA-B2-0407 | SMC_StructureFVG_EA | CodeBase Contributor | EXPLICIT NEGATIVE EVIDENCE: Author explicitly states on CodeBase page this is 'not a profitable system' (exper | https://www.mql5.com/en/code/78454 |
| EA-B2-0412 | Gold_Fractal_Breakout_EA | CodeBase Contributor | NEGATIVE/UNVERIFIED EVIDENCE: Author explicitly notes no empirical edge evidence provided. | https://www.mql5.com/en/code/78308 |
| EA-B2-0428 | DataTraderH4Breakout | CodeBase Contributor | DISCONFIRMED BY AUTHOR/TEST: Viral 1M+ view YouTube strategy tested UNPROFITABLE on EURUSD. | https://www.mql5.com/en/code/68082 |
| EA-B2-0430 | BEC_Combined_BE_Trail | CodeBase Contributor | CONFLICTING / BUGS REPORTED: User comments explicitly report UI panel overflow and wrong 2-digit XAUUSD pip sc | https://www.mql5.com/en/code/71657 |
| EA-B2-0436 | Daily_Price_Action_EA | CodeBase Contributor | CONFLICTING / CODE ERRORS: Community comments explicitly flag code errors in published implementation. | https://www.mql5.com/en/code/68704 |
| EA-B2-0438 | Triangular_Arbitrage | CodeBase Contributor | CONFLICTING / TESTER ARTIFACT: Renowned MQL5 architect fxsaber explicitly critiques Strategy Tester ~60ms exec | https://www.mql5.com/en/code/57272 |
| EA-B2-0445 | GDS_Renko_Momentum_Demo_EA_v0_12 | GDS | BACKTEST + EXPLICIT AUTHOR CAVEAT: 220 real-tick test showed PF 1.67 / 28.64% WR, and author explicitly warns  | https://www.mql5.com/en/code/77200 |
| EA-B2-0451 | Sniper_Gold_Hybrid_Recovery_EA | CodeBase Contributor | CONFLICTING EVIDENCE: Conflicting backtest reports and recovery-averaging blowup sensitivity. | https://www.mql5.com/en/code/76605 |

### Top Audited GitHub Repositories (`github_repos`)
| Task | Repository | Stars | MQL Files | Python Files | License |
|---|---|---|---|---|---|
| Q-0246 | `EA31337/EA31337-Libre` | 272 | 2 | 0 | GPL-3.0 |
| Q-0247 | `elrizwiraswara/nyao_scalper_mt5` | 258 | 2 | 1 | BSD-3-Clause |
| Q-0248 | `Joaopeuko/Mql5-Python-Integration` | 217 | 0 | 35 | MIT |
| Q-0249 | `landim32/LadinoBot` | 206 | 18 | 0 | GPL-3.0 |
| Q-0250 | `EarnForex/MarketProfile` | 205 | 2 | 0 | Apache-2.0 |
| Q-0251 | `ejtraderLabs/Metatrader5-Docker` | 168 | 458 | 0 | Unspecified |
| Q-0252 | `jimtin/algorithmic_trading_bot` | 165 | 0 | 30 | Unspecified |
| Q-0253 | `Ichinga-Samuel/aiomql` | 154 | 0 | 302 | MIT |
| Q-0254 | `tahsintasnuva/voice-notes-pipeline` | 153 | 0 | 0 | MIT |
| Q-0255 | `devcartel/pymt5` | 148 | 0 | 8 | MIT |

### Sample Duplicate & Fork Clusters Detected (`duplicates`)
| Dup ID | Relation | Similarity | File A | File B |
|---|---|---|---|---|
| DUP-0001 | `exact_sha256` | `1.0` | `data/ea_kb/sources/github/amfitrite__Gold-Tester/mql5__Doji_Ride_Indicator.mq5` | `data/ea_kb/sources/github/amfitrite__Gold-Tester/mt5__Doji_Ride_Indicator.mq5` |
| DUP-0002 | `exact_sha256` | `1.0` | `data/ea_kb/sources/github/amfitrite__Gold-Tester/mql5__ICT_IFVG_Indicator.mq5` | `data/ea_kb/sources/github/amfitrite__Gold-Tester/mt5__ICT_IFVG_Indicator.mq5` |
| DUP-0003 | `exact_sha256` | `1.0` | `data/ea_kb/sources/github/amfitrite__Gold-Tester/mql5__VWAP_Bounce_Indicator.mq5` | `data/ea_kb/sources/github/amfitrite__Gold-Tester/mt5__VWAP_Bounce_Indicator.mq5` |
| DUP-0004 | `exact_sha256` | `1.0` | `data/ea_kb/sources/github/geraked__metatrader5/Indicators__Boxline.mq5` | `data/ea_kb/sources_batch2/github/geraked__metatrader5/Indicators__Boxline.mq5` |
| DUP-0005 | `exact_sha256` | `1.0` | `data/ea_kb/sources/github/geraked__metatrader5/Indicators__ChandelierExit.mq5` | `data/ea_kb/sources_batch2/github/geraked__metatrader5/Indicators__ChandelierExit.mq5` |
| DUP-0006 | `exact_sha256` | `1.0` | `data/ea_kb/sources/github/geraked__metatrader5/Indicators__Grid.mq5` | `data/ea_kb/sources_batch2/github/geraked__metatrader5/Indicators__Grid.mq5` |
| DUP-0007 | `exact_sha256` | `1.0` | `data/ea_kb/sources/github/geraked__metatrader5/Indicators__OrderBlock.mq5` | `data/ea_kb/sources_batch2/github/geraked__metatrader5/Indicators__OrderBlock.mq5` |
| DUP-0008 | `exact_sha256` | `1.0` | `data/ea_kb/sources/github/geraked__metatrader5/Indicators__UTBot.mq5` | `data/ea_kb/sources_batch2/github/geraked__metatrader5/Indicators__UTBot.mq5` |
| DUP-0009 | `exact_sha256` | `1.0` | `data/ea_kb/sources/github/geraked__metatrader5/Indicators__ZLSMA.mq5` | `data/ea_kb/sources_batch2/github/geraked__metatrader5/Indicators__ZLSMA.mq5` |
| DUP-0010 | `exact_sha256` | `1.0` | `data/ea_kb/sources/github/vdemydiuk__mtapi/mq4__hash.mqh` | `data/ea_kb/sources_batch2/github/vdemydiuk__mtapi/mq5__hash.mqh` |
