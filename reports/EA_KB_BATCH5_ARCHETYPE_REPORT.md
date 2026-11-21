# EA KB Batch 5 — Rebuild, Duplicate Lineage & Structural Archetype Audit

Generated UTC: `2026-11-21T11:35:12+00:00` | SQLite `PRAGMA integrity_check`: **`ok`**

## 1. Corpus Totals & Batch 5 Reconciliation
- **Total Verified Local Source Files:** `2,100` (`+118` new Batch 5 GitHub headers; `missing_local_paths = 0`)
- **By Batch:** `{'batch1': 217, 'batch2': 1501, 'batch3': 222, 'batch4': 42, 'batch5': 118}`
- **`ea_master`:** `499` | **`indicators`:** `226` | **`duplicates`:** `1,322` (`{'exact_sha256': 410, 'fork_or_modified': 238, 'near_duplicate': 287, 'shared_code_pattern': 387}`)
- **Batch 5 Queue (`344` items):** `118` GitHub headers downloaded + indexed, `1` C++ stdlib (`<limits>`), `24` external vendor SDKs deferred cleanly, `201` MQL5 `.zip`/archive items kept `blocked` (never bypassed; reproducible Colab/PC guide in `scripts/BATCH5_MQL5_COLAB_GUIDE.md`).

## 2. Five-Archetype Source-Level Extraction Across `2,100` Source Files
| Archetype / Capability | Source Files Matching | Top Exemplars |
|---|---:|---|
| `multi_currency` | 126 | `MQL4__Experts__Account Protector__Account Protector.mqh` (60), `Forexsb.com__ActionTrade4.mqh` (47), `mq4__MtApi.mq4` (34), `MQL4__Experts__Position Sizer__Position Sizer.mqh` (32), `MT5_EurUsd_v02x.mq5` (28) |
| `basket_trading` | 37 | `ea-research__xaubot-mq5__Include__XAUBot_PositionManager.mqh` (28), `Trade Manager__Trade Manager.mq5` (27), `Basket_Close_Manager.mq5` (23), `EA Snippets__Breakout__Breakout5-2-2.mq5` (13), `EA Snippets__Breakout__Breakout5-2.mq5` (13) |
| `hedging` | 278 | `MQL5__Include__OrderIterator.mqh` (25), `MQL5__Experts__Position Sizer__PortfolioRisk.mqh` (24), `MQL5__Include__EA_SCALPER__Risk__CRecoveryManager.mqh` (16), `MQL5__Indicators__RiskCalculator.mq5` (15), `MQL5__Include__Math__Fuzzy__fuzzyrule.mqh` (11) |
| `vol_breakout` | 204 | `MQL5__Include__EA_SCALPER__Strategy__CTrendFollowStrategy.mqh` (29), `indicators__bollinger_bands_distance_calculator.mq5` (24), `MQL5__Experts__SmartPropAI_Template.mq5` (18), `indicators__bollinger_bands.mq5` (15), `MQL5__Experts__EA_SCALPER_XAUUSD.mq5` (14) |
| `icustom_usage` | 99 | `IndicatorBase.h` (26), `mq4__MtApi.mq4` (12), `mq5__MtApi5.mq5` (12), `Library__IndicatorLibrary.mq5` (6), `Indicators__Indi_HeikenAshi.mqh` (5) |

## 3. Top `#include`, `iCustom`, and External `.dll` Dependencies
- **Top `#include` headers:** `Trade\Trade.mqh` (200), `Forexsb.com/Enumerations.mqh` (111), `Forexsb.com/Indicator.mqh` (109), `Object.mqh` (70), `Math.mqh` (63), `Trade/Trade.mqh` (62), `../Indicator/IndicatorTickOrCandleSource.h` (58), `Trade\SymbolInfo.mqh` (57), `Arrays\List.mqh` (46), `Trade\PositionInfo.mqh` (43)
- **Top `iCustom()` indicator calls:** `Development\\Breakout\\BreakoutBarsTrend_v2` (10), `Custom\\MovingAverageCross` (4), `Heiken Ashi` (3), `dantrend` (2), `smc_test\\SMC_Test_` (2), `Examples\\Custom Moving Average` (2), `Development\\Currency Index\\CurrencyStrength` (2), `Custom\\AdMa` (1), `Custom\\DonchianChannel` (1), `ATR_Trailing_Stop` (1)
- **External `.dll` imports:** `kernel32.dll` (28), `user32.dll` (10), `advapi32.dll` (8), `AdoSuite.dll` (7), `Wininet.dll` (3), `wininet.dll` (2), `kernelbase.dll` (2), `gdi32.dll` (2), `Opengl32.dll` (2), `MTConnector.dll` (1)
