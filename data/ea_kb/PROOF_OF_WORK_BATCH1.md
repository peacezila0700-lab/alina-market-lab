# PROOF OF WORK — BATCH 1 (Global EA Research & Intelligence System)

Generated UTC: `2026-11-21T08:16:09Z`

## 1. Search Engines, Platforms & Queries Executed
- **Platforms/Sources Queried:** DuckDuckGo/Web Search (multi-query global web_search), MQL5 CodeBase (en/ru/ja/zh), MQL5 Market, MQL5 Official Reference Docs, GitHub REST API & Raw Content, GitLab REST API v4 & Raw Content, ForexFactory Forums & Attachments, Reddit (r/algotrading, r/Forex), TradingView / Pine-to-MT5 GitHub ecosystem, YouTube (tutorials linked to MQL5 CodeBase), arXiv / ResearchGate, ForexPeaceArmy, Myfxbook
- **Web Search Queries Executed (9 multi-platform/multilingual queries):**
  1. `site:mql5.com "Market" popular Expert Advisors Grid Scalping Trend Night Scalper Prop Firm reviews limitations`
  2. `"Expert Advisor" OR "MQL5" open source framework GitHub GitLab SMC ICT Smart Money Machine Learning ONNX MetaTrader 5`
  3. `arXiv SSRN "MetaTrader" OR "technical trading rules" OR "algorithmic trading" transaction costs overfitting decay 2024 2025 2026`
  4. `site:gitlab.com "MetaTrader 5" OR "MQL5" "Expert Advisor" OR ".mq5"`
  5. `site:reddit.com/r/algotrading OR site:reddit.com/r/Forex "MT5" "Expert Advisor" OR "EA" open source backtest real results`
  6. `site:forexfactory.com "MT5" "Expert Advisor" ".mq5" OR "mql5" trading systems source code`
  7. `site:mql5.com/ru/code/mt5/experts OR site:mql5.com/ja/code/mt5/experts OR site:mql5.com/zh/code/mt5/experts`
  8. `site:tradingview.com OR site:youtube.com "MT5 Expert Advisor" OR "MQL5" source code strategy backtest github`
  9. `"Pine Script" to "MQL5"` + `site:github.com "MQL5" "DRAW_ARROW" OR "PLOT_ARROW" OR "Wingdings"` + `site:mql5.com/en/docs` + `site:myfxbook.com OR site:forexpeacearmy.com`

## 2. Websites Read vs Blocked / Rate-Limited (Verified HTTP Logs)
- **Crawler HTTP Requests Attempted (Batch 1 script + supplements):** `258` initial + `13` GitLab `develop` + `69` GitHub extra indicator/cross-platform fetches
- **Websites/Endpoints Successfully Read (`200 OK`):** `219` (main crawler) + `82` (GitLab/GitHub supplements) + `19` (`fetch_page` full reads on MQL5 Indicators, Market, Docs, GitHub, GitLab, FF)
- **Websites Blocked / Rate-Limited / Failed (logged honestly, not counted as read):**
  - `MQL5 CodeBase` rapid `urllib` requests after item ~46: `HTTP 403 Forbidden` / connection reset on `24` indicator pages + `3` docs + `3` RU/JA/ZH pages + `2` Market pages (recovered 7 indicators, 3 market pages & 3 docs separately via `fetch_page`; remainder queued).
  - `ForexPeaceArmy` (`forexpeacearmy.com`): `HTTP 403 Forbidden` directly (queued; search snippets preserved at Level 5).
  - `GitLab fxce/mt5-libs` initial `master` branch guess gave `404` on 6 files -> fixed dynamically to `default_branch='develop'` and downloaded `12` `.mq5/.mqh` files `200 OK`.

## 3. Verified Extraction & Knowledge Base Counts
- **Source Code Files Downloaded & Statically Analyzed (`Level 1 Confirmed`):** `217` files (`5.01 MB` verbatim `.mq5/.mq4/.mqh/.py/.pine`)
  - Breakdown by Role: `{"Expert Advisor (Trading)": 59, "Indicator": 56, "Expert Advisor (Modular / Class-based)": 21, "Unclassified Source": 8, "Library / Header (.mqh)": 52, "Script": 11, "Utility / Diagnostic EA": 9, "Trade / Risk Manager EA": 1}`
- **EA Master Database Total:** `96` (`90` source-verified Level 1 + `6` Doc/Commercial/Unverified Level 2–6)
- **Indicators Master Database:** `63` (`56` raw source files + `7` `fetch_page` inspected MQL5 CodeBase indicators)
- **Visual Symbol & Wingdings Library:** `204` records (Wingdings reference + extracted `DRAW_ARROW`/`PLOT_ARROW`/`DRAW_LINE`/`OBJ_*`)
- **Decomposed Strategies:** `90` | **Developers Indexed:** `69`
- **Duplicate / Fork / Similarity Pairs Found (all preserved):** `{"fork_or_modified": 3, "shared_code_pattern": 4, "exact_sha256": 3}`
- **Unclassified / Unknown / Binary-Only Records Preserved:** `28`
- **Knowledge Graph Edges:** `725` | **RAG FTS5 Chunks Indexed:** `230`
- **Research Queue Tasks Remaining for Batch 2+:** `1924` (`{"mql5_ea_page": 84, "developer_profile": 25, "mql5_related": 83, "mql5_ind_page": 53, "github_repo": 75, "github_source_file": 1393, "gitlab_source_file": 35, "compiled_binary_unreadable": 12, "blocked_403_manual_or_search": 1, "custom_include_dependency": 158, "custom_indicator_icustom": 5}`)

## 4. Sample Verified Records (No Hallucination)
### Level 1 Source-Verified EAs
| ID | Name | Role | Indicators | SL | Grid/Mart Flag | Source URL |
|---|---|---|---|---|---|---|
| EA-0001 | GOLD_Grid_Confidence_V7_32_stabil.mq5 | Expert Advisor (Trading) | ["iMA", "iRSI", "iATR", "iADX"] | True | True | https://www.forexfactory.com/attachment/file/5213923?d=1780388517 |
| EA-0002 | GridOracle_V4.12.mq5 | Expert Advisor (Trading) | ["iMA", "iRSI", "iATR", "iStdDev"] | False | True | https://www.forexfactory.com/attachment/file/5196745?d=1777794860 |
| EA-0015 | Moenabiel/memo-smt-ea :: MQL5/Experts/MEMO/MEMO_ | Expert Advisor (Modular / Class-based) | [] | True | False | https://raw.githubusercontent.com/Moenabiel/memo-smt-ea/main/MQL5/Experts/MEMO/MEMO_XAU_XAG_SMT_EA.mq5 |
| EA-0046 | London Breakout EA: simple and transparent/Londo | Expert Advisor (Trading) | ["iATR"] | True | False | https://www.mql5.com/en/code/download/78293/LondonBreakoutEA.mq5 |
| EA-0048 | H4 Breakout Retest EA for Gold (XAUUSD) - expert | Expert Advisor (Trading) | [] | True | False | https://www.mql5.com/en/code/download/78537/H4BreakoutRetest_XAU.mq5 |
| EA-0050 | Algo: EMA Trend Cross on Closed Bars — XAUUSD M3 | Expert Advisor (Trading) | ["iMA"] | True | False | https://www.mql5.com/en/code/download/78968/MSP_FreeEA_Alpha_1_1.mq5 |
| EA-0081 | Basket Guard - closes a basket of positions at l | Expert Advisor (Trading) | [] | False | False | https://www.mql5.com/en/code/download/79773/BasketGuard.mq5 |

### Commercial / Closed-Source / Doc-Only EAs (Strictly Tagged Unverified / Claims)
| ID | Name | Developer | Evidence Level | Status | URL |
|---|---|---|---|---|---|
| EA-COM-0092 | Prop Firm Gold EA | Jimmy Peter Eriksson | Level 5 | Unverified | https://www.mql5.com/en/market/product/153540 |
| EA-COM-0093 | My AI Gold | Vitalii Kosov | Level 6 | Unverified | https://www.mql5.com/en/market/product/194000 |
| EA-COM-0094 | The Gold Reaper MT5 | Profalgo Limited (strueli) | Level 6 | Unverified | https://www.mql5.com/en/market/product/111357 |
| EA-COM-0095 | Night Scalper MT5 (snippet/search only) | Unknown (search snippet) | Level 6 | Unverified | https://www.mql5.com/en/market/product/44236 |
| EA-COM-0096 | Dark Venus EA (Reddit community report only) | External / Commercial (unverified) | Level 5 | Conflicting | https://www.reddit.com/r/algotrading/comments/zxdvjm/is_money_management_all_that_matters_to_be/ |
| EA-DOC-0091 | Calendar-Based Backtesting: Event-Driven Trading EA (NewsBacktest) | Mullerp04 | Level 2 | Partially Confirmed | https://www.mql5.com/en/code/55630 |

### Visual Symbols Extracted From Source Code
| Sym ID | Item | Type | Code | Meaning | Repaint Audit Warning |
|---|---|---|---|---|---|
| SYM-SRC-0018-03 | CThompson18/MQL5 :: SilverTrendIndicator | DRAW_ARROW | `234` | Down Arrow (Standard Sell Arrow) | DRAW_ARROW_Missing_Explicit_EMPTY_VALUE |
| SYM-SRC-0018-04 | CThompson18/MQL5 :: SilverTrendIndicator | DRAW_ARROW | `233` | Up Arrow (Standard Buy Arrow) | DRAW_ARROW_Missing_Explicit_EMPTY_VALUE |
| SYM-SRC-0019-03 | CThompson18/MQL5 :: indicatorarrows.mq4 | DRAW_ARROW | `233` | Up Arrow (Standard Buy Arrow) | No static repaint flag detected |
| SYM-SRC-0019-04 | CThompson18/MQL5 :: indicatorarrows.mq4 | DRAW_ARROW | `234` | Down Arrow (Standard Sell Arrow) | No static repaint flag detected |
| SYM-SRC-0036-04 | EarnForex/MarketProfile :: MarketProfile | OBJ_ARROW | `code` | Dynamic/Input Variable | No static repaint flag detected |
| SYM-SRC-0037-04 | EarnForex/MarketProfile :: MarketProfile | DRAW_ARROW | `167` | Small Filled Square | Reads_Bar0_FormingBar |
| SYM-SRC-0037-05 | EarnForex/MarketProfile :: MarketProfile | DRAW_ARROW | `167` | Small Filled Square | Reads_Bar0_FormingBar |
| SYM-SRC-0037-06 | EarnForex/MarketProfile :: MarketProfile | DRAW_ARROW | `167` | Small Filled Square | Reads_Bar0_FormingBar |

### Duplicate & Fork Relationships Detected (All Retained)
| Dup ID | File A | File B | Relation | Jaccard Similarity |
|---|---|---|---|---|
| DUP-0004 | `data/ea_kb/sources/github/amfitrite__Gold-Tester/mql5__Doji_Ride_Indicator.mq5` | `data/ea_kb/sources/github/amfitrite__Gold-Tester/mt5__Doji_Ride_Indicator.mq5` | exact_sha256 | 1.0 |
| DUP-0005 | `data/ea_kb/sources/github/amfitrite__Gold-Tester/mql5__ICT_IFVG_Indicator.mq5` | `data/ea_kb/sources/github/amfitrite__Gold-Tester/mt5__ICT_IFVG_Indicator.mq5` | exact_sha256 | 1.0 |
| DUP-0006 | `data/ea_kb/sources/github/amfitrite__Gold-Tester/mql5__VWAP_Bounce_Indicator.mq5` | `data/ea_kb/sources/github/amfitrite__Gold-Tester/mt5__VWAP_Bounce_Indicator.mq5` | exact_sha256 | 1.0 |
| DUP-0010 | `data/ea_kb/sources/github/modnoting__mql5/Experts__Advisors__ExpertMAMA.mq5` | `data/ea_kb/sources/github/modnoting__mql5/Experts__Advisors__ExpertMAPSAR.mq5` | fork_or_modified | 0.7106 |
| DUP-0007 | `data/ea_kb/sources/github/haza79__MT5-Smart-Money-Concept-Indicator/SMC__BalanceOfPower.mq5` | `data/ea_kb/sources/github/haza79__MT5-Smart-Money-Concept-Indicator/SMC__BuyerSellerPressure.mq5` | fork_or_modified | 0.5796 |
| DUP-0001 | `data/ea_kb/sources/github/9nix6__Median-and-Turbo-Renko-indicator-bundle/Indicators__MedianRenko__ADX.mq5` | `data/ea_kb/sources/github/novts__MetaTrader-5-Creating-Trading-Robots-and-Indicators-with-/Indicator_Properties__ADX.mq5` | fork_or_modified | 0.5748 |
| DUP-0009 | `data/ea_kb/sources/github/modnoting__mql5/Experts__Advisors__ExpertMACD.mq5` | `data/ea_kb/sources/github/modnoting__mql5/Experts__Advisors__ExpertMAPSAR.mq5` | shared_code_pattern | 0.5067 |
| DUP-0002 | `data/ea_kb/sources/github/EarnForex__MTF_MA/MTF_MA.mq4` | `data/ea_kb/sources/github/EarnForex__MTF_MA/MTF_MA.mq5` | shared_code_pattern | 0.5046 |
| DUP-0008 | `data/ea_kb/sources/github/modnoting__mql5/Experts__Advisors__ExpertMACD.mq5` | `data/ea_kb/sources/github/modnoting__mql5/Experts__Advisors__ExpertMAMA.mq5` | shared_code_pattern | 0.4746 |
| DUP-0003 | `data/ea_kb/sources/github/GeneralTradingSarl__Smart-Money-Concepts/parity__SMC_ParityRun.mq5` | `data/ea_kb/sources/github/GeneralTradingSarl__Smart-Money-Concepts/parity__SMC_RealtimeRun.mq5` | shared_code_pattern | 0.385 |
