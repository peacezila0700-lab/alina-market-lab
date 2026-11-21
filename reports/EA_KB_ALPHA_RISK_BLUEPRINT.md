# EA KB ALPHA, EXECUTION & RISK BLUEPRINT (from 1,982 Real Source Files)

Generated UTC: `2026-11-21T09:48:21Z` | Source DB: `data/ea_kb/alina_ea_kb.sqlite` (`Batch 4 (v2.15)`)

## 1. Empirical Structural Reality Across 383 Local Source-Verified EAs
| Metric | Count | % of 383 Local EAs | Quant Lab Diagnostic Implication |
|---|---:|---:|---|
| Has Hard Stop Loss (`has_sl`) | 191 | 49.9% | 192 EAs trade naked without hard SL |
| Has Take Profit (`has_tp`) | 184 | 48.0% | ~48% specify explicit TP targets |
| **Grid / Martingale Flag** | **14** | **3.7%** | 14 EAs use lot escalation/averaging (4 without any SL) -> tail wipeout risk |
| **Limit / Pending Execution** | **20** | **5.2%** | 94.8% rely on market/unfiltered orders and pay full spread on entry |
| **New-Bar Closed Check** | 220 | 57.4% | 163 EAs evaluate intra-bar ticks -> look-ahead / backtest-live divergence risk |
| **Spread Filter Present** | 61 | 15.9% | 84.1% lack spread caps and trade straight through 20–22 UTC rollover spikes (2.6x on EURGBP) |
| **Daily DD / Equity Guard** | 22 | 5.7% | Required baseline protection in `AlinaRiskGovernor.mq5` |
| **Clean Non-Martingale + SL + Guarded** | **116** | **30.3%** | Engineering gold-standard reference pool (`EA31337`, `FxceLibs`, `AlinaRiskGovernor`, etc.) |

## 2. Most Frequent Strategy Categories & Indicators (`ea_master` local)
- **Top Categories:** `Price Action / General / Unclassified` (155), `Trend/Breakout` (119), `Oscillator/Mean-Reversion` (93), `Risk/Trade Utility` (32), `SMC/ICT` (26), `Grid/Martingale/Basket` (14), `ML/Neural/ONNX` (14), `News/Calendar` (7)
- **Top Built-in Indicators:** `iMA` (76), `iRSI` (71), `iATR` (50), `iMACD` (22), `iADX` (21), `iCustom` (18), `iBands` (13), `iCCI` (12), `iMFI` (12), `iMomentum` (8), `iStochastic` (7), `iSAR` (5), `iFractals` (4), `iOBV` (4), `iStdDev` (3)
- **FTS5 Knowledge Queries (`kb_fts`):** `SpreadFilter OR MaxSpread`=149, `Drawdown OR DailyLoss`=56, `Limit OR Pending`=17, `MeanReversion OR ZScore OR Bollinger`=9, `OnTradeTransaction`=27, `OrderCalcProfit`=3

## 3. Known Retail EA Failure Modes vs ALINA Measured Experiments (`EXP-0001..0023`)
1. **Martingale / Grid / No-SL Tail Illusion (3.7% of local EAs = 14/383 + FPA `Q-1761`):** Smooth equity curves conceal exponential lot growth (FPA `93.02%` relative DD); Lab `5/5` martingale tests failed (`WHAT_FAILED.md`).
2. **Non-Limit Market-Order Cost Wall (94.8% of local EAs lack limit/pending entry):** Directly matches `EXP-0017/0018` (1h FX reversal gross `+0.19 bp/h` wiped out to `-0.15 bp/h` net by spread) and `EXP-0023` (ETH-BTC gross `+1.60..+2.39` Sharpe wiped out by OKX fees).
3. **Rollover Spread & Swap Bleed (`SpreadFilter` missing in 84.1% of local EAs):** Dukascopy real H1 spreads jump **2.6x** on EURGBP at 20–21 UTC (`0.9` -> `2.6` pips) and **3.2x** on EURUSD (`0.5` -> `1.6` pips).
4. **Indicator Repaint & Intra-Bar Peeking:** Static flags detected in `indicators.jsonl`: `Reads_Bar0_FormingBar` (21), `Check_Series_Index_i_minus_1_Direction` (9), `DRAW_ARROW_Missing_Explicit_EMPTY_VALUE` (8), `Visual only.` (2), `Display only.` (2)

## 4. Top Clean Guarded Reference Implementations in KB
| EA ID | Name | Developer | Indicators | Risk Controls | Path |
|---|---|---|---|---|---|
| EA-0003 | `Imbalance.mq5` | ForexFactory Contrib | Price/Custom | HardSL; TP; TrailingStop; RiskPctSizing; Sess | `data/ea_kb/sources/forexfactory/Imbalance.mq5` |
| EA-0004 | `MT5_EurUsd_v02x.mq5` | ForexFactory Contrib | Price/Custom | HardSL; TP; TrailingStop; RiskPctSizing; Sess | `data/ea_kb/sources/forexfactory/MT5_EurUsd_v02x.mq5` |
| EA-0005 | `OrderBlock_Schematic_1.mq5` | ForexFactory Contrib | Price/Custom | HardSL; TP; TrailingStop; RiskPctSizing; Sess | `data/ea_kb/sources/forexfactory/OrderBlock_Schematic_1.mq5` |
| EA-0006 | `OrderBlock_Schematic_2.mq5` | ForexFactory Contrib | Price/Custom | HardSL; TP; TrailingStop; RiskPctSizing; Sess | `data/ea_kb/sources/forexfactory/OrderBlock_Schematic_2.mq5` |
| EA-0007 | `OrderBlock_Schematic_3.mq5` | ForexFactory Contrib | Price/Custom | HardSL; TP; TrailingStop; RiskPctSizing; Sess | `data/ea_kb/sources/forexfactory/OrderBlock_Schematic_3.mq5` |
| EA-0008 | `Trade Manager.mq5` | ForexFactory Contrib | Price/Custom | HardSL; TP; TrailingStop; RiskPctSizing; Sess | `data/ea_kb/sources/forexfactory/Trade_Manager.mq5` |
| EA-0012 | `EarnForex/PositionSizer :: MQL4/Expe` | EarnForex | Price/Custom | HardSL; TP; TrailingStop; BreakEven; RiskPctS | `data/ea_kb/sources/github/EarnForex__PositionSizer/MQL4__Experts__Position_Sizer__Position_Sizer.mq4` |
| EA-0013 | `EarnForex/PositionSizer :: MQL5/Expe` | EarnForex | Price/Custom | HardSL; TP; TrailingStop; BreakEven; RiskPctS | `data/ea_kb/sources/github/EarnForex__PositionSizer/MQL5__Experts__Position_Sizer__Position_Sizer.mq5` |
| EA-0017 | `KVignesh122/MT5-SMC-trading-bot :: E` | KVignesh122 | iATR,iADX | HardSL; TP; RiskPctSizing; SpreadFilter; Sess | `data/ea_kb/sources/github/KVignesh122__MT5-SMC-trading-bot/EA_Script.mq5` |
| EA-0018 | `Moenabiel/memo-smt-ea :: MQL5/Expert` | Moenabiel | Price/Custom | HardSL; TP; TrailingStop; BreakEven; RiskPctS | `data/ea_kb/sources/github/Moenabiel__memo-smt-ea/MQL5__Experts__MEMO__MEMO_XAU_XAG_SMT_EA.mq5` |
| EA-0021 | `SiyabongaDlamini/SmartMoney.MQ5 :: S` | SiyabongaDlamini | Price/Custom | HardSL; TP; TrailingStop; BreakEven; RiskPctS | `data/ea_kb/sources/github/SiyabongaDlamini__SmartMoney.MQ5/SmartMoney_MTF_EA_v2.mq5` |
| EA-0022 | `e49nana/Algorithmic-trading :: tradf` | e49nana | iATR | HardSL; TP; BreakEven; SpreadFilter; SessionF | `data/ea_kb/sources/github/e49nana__Algorithmic-trading/tradfi__ASQ_CommandDesk_v1.00.mq5` |

## 5. Falsifiable Hypotheses Extracted for Track 3 (`EXP-0024` Suite)
Never retuning closed `H01`/`H05`/`H06`/`H09`/`H20`. Instead testing **3 structural upgrades** on **23-year Dukascopy EURGBP & EURUSD real bid/ask H1 (`2003-2026`, final 6 months locked OOS)**:
1. **`H26` (Limit-Order Multi-Day OU Mean-Reversion):** Enter ONLY via passive limit orders (verified against actual H1 `ask_l` / `bid_h` on bars strictly `> signal_bar`) at stretched 4H/Daily OU Z-scores, targeting `15–40 pips` (`>= 3x` round-trip spread) with ATR stop and time stop — directly testing Decision `D02` that was NEVER tested with real bid/ask H1 limit fills!
2. **`H27` (Session-Liquidity Fix Reversion vs Intraday Drift):** Passive limit/market fade timed around European close / post-NY fix with explicit **rollover-hour spread filter (`20-22 UTC` blocked)** (`SpreadFilter` + `SessionFilter`).
3. **`H28` (Volatility-Compression Regime Filter + Hard Risk Governor):** Apply `H26` ONLY when trailing 252-day ATR volatility is compressed/normal (blocking 2008/2022 breakout regimes like `AlinaRiskGovernor` + `EA31337` regime gates) across **4 broker cost tiers** (`Dukascopy Measured`, `IC Markets Raw ECN`, `Exness Raw`, `Exness Standard`) plus overnight swap sensitivity bounds.
