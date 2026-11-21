# Comprehensive Research Analysis: `EXP-0001` through `EXP-0029` & Catalog Comparison

Generated UTC: `2026-11-21T11:58:00Z` | Scope: **Read-Only Empirical Audit (Zero Code Execution / Zero Historical Edits)**  
Authoritative Sources: `research/EXPERIMENT_LOG.csv` (`29` rows), `research/HYPOTHESIS_REGISTER.csv`, `data/ea_kb/alina_ea_kb.sqlite` (`2,100` source files, `499` EAs), `reports/*.md`, `research/artifacts/*.json`, `PROJECT_HEALTH_REPORT.md`.

---

## 1. Complete Empirical Summary (`EXP-0001..0029`)

Across **`29` pre-registered experiments**, **`0` strategies** cleared the lab's OOS + null-control + post-cost survivability bars for directional trading alpha. Two domains demonstrated verified **non-directional** operational utility (volatility/drawdown risk control and execution-cost avoidance).

| Exp Range | Domain & Hypotheses | Sample & Datasets | Core Empirical Outcome | Primary Failure / Survival Mechanism |
|---|---|---|---|---|
| `EXP-0001..0004` | Single-pair FX mean-reversion & breakout (`H01, H05, H06`) | `EURGBP`/`EURUSD` D1 & H1 (`2000–2026`, up to `222` IS trades) | **ALL REJECTED** (`EXP-0002` CLEAN `+5.81p` inside random p95 `+43.8p`; `EXP-0003` IS `-1.66p`; `EXP-0004` IS `-2.93p`) | Random-walk noise on D1; adverse selection + spread cost on H1 market orders. |
| `EXP-0005..0007` | Cross-sectional FX & multi-asset reversion (`H09, H10`) | `P1R_EUR9` ECB (`1999–2026`) + `P2_MULTI12`; Hold-out `2019–2026` | **REJECTED** (`EXP-0006` conditional P1R ECN `+0.402` collapsed to **`+0.126` retail / `+0.158` ECN** on `EXP-0007` hold-out; 3y windows `1/6` positive) | In-sample period selection + `97x/yr` turnover cost drag (`Yahoo FX` vs `ECB` return corr only `0.38`). |
| `EXP-0008` | Variance Risk Premium & VIXY short-vol (`H11a, H11b`) | CBOE `VIX` + `SPY` + `VIXY` (`2000–2026`) | **REJECTED** (`H11a` overlay non-monotone `+0.337`; `H11b` `-100%` short VIXY Sharpe `+0.694` suffered **`-103.7%` rolling 12m** & `-43.1%` single-day wipeout) | Statistical significance without tail survivability (leverage cap `-10%` gives ~`17%` MaxDD). |
| `EXP-0009..0011` | `COT` panel (`H12`), Events (`H13`), Treasury auctions (`H14`) | `35,936` COT rows; `22,799` event rows; `770` auctions | **ALL FAIL** (`COT` OOS `t=-0.56`, `R²=0.0001`; `FOMC` IS `t=2.23` flipped sign OOS `-0.00113`; auctions absorbed day-of) | Markets absorb public scheduled positioning/auctions rapidly; events shift **variance**, not **mean return**. |
| `EXP-0012` | Cross-sectional ETF momentum & reversals (`H15`) | `68` ETFs (`2007–2026`) | **ALL FAIL** (`MOM_12_1` OOS `+0.534` at `78.5th` null pct; `REV_5D` `-0.518` OOS net `5 bp`) | Two early code bugs fixed (fixed ticker permutation null exposed false passes). |
| `EXP-0013..0016` | Market overlays: Breadth, Credit, GEX (`H16–H17`), Vol Term Structure (`H18`), Yield Curve (`H19`) | `SPY`/`TLT`/`IEF`, `DIX/GEX`, CBOE `VIX/VIX3M/VIX9D`, UST curve | **DIRECTIONAL ALPHA FAIL / RISK CONTROL DISCOVERY** (`GEX` = vol targeting in disguise `Δ +0.041` OOS `74th` pct; `Vol Onset` **AUC `0.746` / Brier `+0.168`**, yet active overlay lost `-0.278` OOS vs passive vol targeting; `10y-3m` halved 2022–26 bond DD) | **First verified structural finding:** Macro/vol-term indicators forecast **volatility/drawdown regimes**, not excess directional Sharpe over simple volatility targeting. |
| `EXP-0017..0018` | 5 Hourly FX rules & sparse liquidity gates (`H20, H20b`) | 6 pairs, `~145k` Dukascopy H1 bid/ask bars (`2003–2026`) | **ALL FAIL** (`REV1` gross `+0.188 bp/h` -> net **`-0.154 bp/h`**, Sharpe `-7.83/-5.81`; gating still `-1.90/-0.91`, breakeven requires `3–30x` tighter spreads) | Retail spread/turnover cost wall (`24x/day` turnover). |
| `EXP-0019` | House Congressional PTR disclosures (`H21`) | `6,365` PTR rows (`16` months, `115` stocks) | **FAIL (OPEN SAMPLE)** (`IS 0.0th` pct `-0.69%` vs `OOS 99.5th` pct `+2.60%` — severe half-split sign flip) | Insufficient history (`16` months); demonstrates why single-split reporting lies. |
| `EXP-0020..0021` | Purged WF ML (`Ridge`, `HistGradientBoosting`) on US (`112`) & Thai (`64`) stocks (`H22, H23`) | `112` US + `64` Thai SET (`2016–2026`), `t+1` lag | **FAIL** (`US ML` OOS `+0.31..+0.36` < `99th` bar & LO `+0.96 < EW +1.39`; `Thai ML` hit **`99.5–100.0%` IS** then collapsed to **`-0.29 / -0.37` OOS** at `27 bp` Thai cost) | Textbook ML overfitting trap on daily technical + macro panels; high Thai transaction fees (`16.8 bp` floor). |
| `EXP-0022` & `EXP-0026` | Point-in-Time SEC EDGAR fundamentals (`H24`: `N=62`; `H29`: `N=317` w/ `acceptanceDateTime`) | `62` -> `317` US-GAAP firms (`15,073` PIT rows, `0` leaks) | **PROMISING STRUCTURE / FAIL PROMOTION BAR** (`F_NEG_ACCRUALS`: `N=62` `+0.624/+0.947` [`93.5/92.0%`]; `N=317` IS `+0.943` [`99.0%`] / OOS `+0.525` [`90.0%`], survives `20 bp` `+0.494`, BH FDR `False/False`; `F_CFO_ASSETS` `-0.691`, `F_QUALITY_COMP` `-0.726` collapsed OOS) | Strongest non-price candidate in lab, yet OOS missed `99.0%` Bonferroni bar and carries active-constituent **survivorship bias**. |
| `EXP-0023` | 1H Crypto reversal/mom/breakout/ETH-BTC pair (`H25`) | `9,999` confirmed OKX 1H bars (`2025–2026`) | **FAIL** (`ETH-BTC` gross `+1.60 IS / +2.39 OOS` Sharpe, breakeven `2.6–3.1 bp/side` -> net `-4.43/-5.29` at `10 bp` taker and `-1.51` OOS at `5 bp` maker) | Exchange taker/maker fee wall identical to `EXP-0017`. |
| `EXP-0024..0025` | **Phase C Kill Point:** KB Limit OU (`H26`), Fix Fade (`H27`), Vol/Spread Guard (`H28`) vs H1 Scalp | `23y` Dukascopy H1 (`EURGBP 147,297`, `EURUSD 148,482`) across `4` broker tiers | **REJECT ALL AT KILL POINT** (`EURGBP` limit saved `+0.78p/trade` vs market, yet ALL net `-1.60p`; Guarded `-1.41p` PF `0.90`; H1 Scalp `-3.35p` PF `0.47`; all `4` brokers including Exness Raw negative `-1.06..-5.96p`) | Structural confirmation that retail FX price-only EAs (`H26–H28`) fail over 23 years even with limit fills & cheapest public ECN spreads. **Phase D ML parked.** |
| `EXP-0027` | Macro, CB Rates, Vol Term & Events (`H30`) | `10,186d` CB rates + `VIX` + `OFR FSI` + `GPR` + `COT` (`2009–2026`) | **DIRECTIONAL FAIL / RISK RADAR PASS** (`SPY 5d +0.153`, `EURGBP -0.423`; Vol-Onset **OOS AUC `0.7212`**, `RV21` corr `+0.4271` [level `R²=-0.021`]; Inverted `VIX/VIX3M` SPY vol **`38.12%`** vs `13.56%`; `12%` Vol-Target cut SPY MaxDD `-34.1% -> -16.6%` IS, `-25.4% -> -16.2%` OOS) | Macro/vol features work strictly for **volatility classification & drawdown control**, NOT directional entries. |
| `EXP-0028..0029` | 23y FX Carry (`H31`) & Deribit/OKX Crypto Carry (`H32`) | `23y` FX H1 + CB rates; `25,284h` Deribit + `10,000h` OKX | **NOT ARBITRAGE / FAIL** (`20–21 UTC` spreads `2.4x–4.0x` liquid hours; retail `0.25–0.50p` swap markup kills 23y FX carry `+0.006 / -0.154`; Deribit funding fell `8.29%->3.84%`, Maker/Taker+borrow+basis MtM kills OOS; `OKX-Deribit` 95th `|spread|` `12.89 bps < 24–32 bps` RT) | Funding decay, retail overnight swap markups, basis mark-to-market whipsaws, and exchange execution fees. |

---

## 2. Comparison Against Existing ALINA Knowledge Base (`2,100` Files) & Proposed 6-Category Resource Map

### A. What ALINA Already Contains (Confirmed in `data/ea_kb/alina_ea_kb.sqlite`)
1. **`EA31337` (`331` local source files, `kb_fts=332`):** Complete `EA31337-classes` modular strategy/indicator/risk/order/symbol structs already indexed across Batches 1–5 (`Source/C++` `.h`/`.mqh`).
2. **`EarnForex` (`62` local source files, `kb_fts=73`):** `Position Sizer` (`39` files), `Account Protector` (`7` files), `RiskCalculator`, ATR stop/trailing & lot-sizing frameworks already extracted.
3. **`PopovMP / FSB` (`127` files), `SmartMoneyConcepts` (`3` files / `17` EAs), `MQL5 Code Base` (`492` MT5 + `141` MT4 files):** Core indicator/breakout/SMC patterns already audited; **`201` remaining MQL5 links are IP-blocked (`HTTP 403`)** with legal local guide at `scripts/BATCH5_MQL5_COLAB_GUIDE.md`.
4. **Cross-Asset & Non-Price Datasets:** `23y` Dukascopy H1 bid/ask, official ECB daily rates, `317` SEC PIT US-GAAP companies (`16:00 ET` cutoff), `10,186` daily CB policy rates (`ECB`, `BoE`, `NYFed`), `25,284h` Deribit funding/DVOL, `16` news RSS feeds, `CBOE` VIX term structure, `OFR FSI`, `CFTC COT`, and `DIX/GEX`.

### B. What Is Redundant or Contradicts Empirical Evidence (Do NOT Chase)
1. **Dumping `130–450` OHLCV Indicators/Alphas (`Alpha101`, `Alpha158`, `Pandas-TA df.ta.strategy("All")`, `TA-Lib`) into LightGBM:**
   - Directly refuted by `EXP-0020` (`US 112` stocks + ML), `EXP-0021` (`Thai 64` SET + ML: `100th` pct IS -> `-0.37` OOS), and `EXP-0012` (`68` ETFs). WorldQuant/Qlib alphas rely on huge institutional stock breadth (`500–3,000+` stocks) at institutional execution fees (`1–2 bp`), NOT single-instrument FX or `27 bp/side` Thai retail fees.
2. **Converting `10–30` Negative-Expectancy EAs (`Freqtrade` / `NostalgiaForInfinity` / `MQL5` / `PineScript`) into `Signal_EA1..30` to Predict Direction:**
   - `EXP-0024` & `EXP-0025` proved across `23` years and `4` public brokers that classic retail price-only EA rules have negative net expectancy (`-1.06` to `-5.96` pips/trade). **Meta-Labeling cannot create directional alpha from negative-expectancy price signals + OHLCV lag features** without overfitting (violates Phase C Kill Point).
3. **Re-mining `MQL5` / `Forex Factory` / `Forex Station` Commercial Claims Without Execution Proof:**
   - Unverified Win Rates (`94.8%` of local KB EAs skip limit entries; `84.1%` omit spread filters; `50.1%` lack hard SL; `21` indicators read forming bar `0` causing repainting).

### C. What Is Missing & Genuinely High-Value From the 6-Category Catalog (Targeted Expansion)
1. **Risk Management, Portfolio Control & Execution Architecture (Task 2 — Batch 6 Targets):**
   - **`Quantopian / Zipline` (`Pairs Trading`, `Kalman Filter`, `Portfolio Risk`, `RiskMetrics`):** Missing (`0` files in KB). Valuable for dynamic hedge-ratio estimation, spread variance modeling, and portfolio covariance constraints.
   - **`Freqtrade` (`Protections`: `MaxDrawdown`, `StoplossGuard`, `CooldownPeriod`, `custom_stoploss`):** Missing (`0` files in KB). Valuable for automated risk circuit breakers and trade-level lifecycle management.
   - **`Jesse AI` (`example-strategies`):** Missing (`0` files in KB). Clean Python separation of entry vs `go_long/short` risk sizing & `update_position()` stop/exit rules.
   - **`Spotware cTrader Algo Samples` (`C# cBots`):** Missing (`0` source files). Structured event-driven execution, trailing stops, and async position guards.
   - **Additional `EarnForex` Risk Utilities:** Check GitHub org for open-source risk/execution modules not yet duplicated in Batches 1–5.
2. **Non-Price & Volatility / Risk Modeling (`Kaggle Optiver Realized Volatility` concepts, `EXP-0027` calibration):**
   - Pure volatility/risk-regime modeling (`AUC 0.7212`, `MaxDD -51%`) is empirically supported; probability calibration (`Isotonic/Platt`) and **delisted SEC CIK integration** remain key research gaps.

---

## 3. Audit of the 5 Core Methodological Risks Across `EXP-0001..0029`

| Risk Class | Concrete Historical Instances Found & Audited | Current Control Status | Residual Vulnerability |
|---|---|---|---|
| **1. Overfitting** | `EXP-0021` (`TH_ML_RIDGE_21D`: `100.0%` IS -> `-0.368` OOS); `EXP-0010` (`FOMC` IS `t=2.23` -> flipped `-0.00113` OOS); `EXP-0019` (`IS 0.0%` -> `OOS 99.5%`) | **Mitigated** by chronological IS/VALID/OOS locking + non-retune Kill Point policy | High if brute-force `150–450` collinear OHLCV features are introduced without feature budget limits |
| **2. Data Leakage / Look-Ahead** | Caught & fixed in: `EXP-0015` (early `1.98` Sharpe bug from same-bar weight + coincident label — `PITFALLS #15`); `COT` (`Tuesday report_date` vs `Friday available_from`); `EXP-0026` (`ROP` 2015 future-dated XBRL `period_end` typo); `EXP-0020/21` (purged `s+H+2 <= t`) | **Enforced** (`0` leaks verified in `pit_fundamentals_expanded.csv`; strict `t+1` execution) | Requires continuous automated assertions (`tests/test_workstreams.py`) on every new horizon label (e.g. Triple-Barrier exit timestamps!) |
| **3. Survivorship Bias** | `EXP-0020` (`112` US current stocks), `EXP-0021` (`64` Thai SET active stocks), `EXP-0026` (`317` active Nasdaq top market-cap US-GAAP firms) | **Disclosed openly**, NOT hidden | **Unresolved** for equity cross-sections (`EXP-0026` `F_NEG_ACCRUALS` needs historical delisted SEC firms + delisting returns) |
| **4. Multiple Testing** | `EXP-0012` (weekly reshuffling bug fixed -> fixed-label ticker permutation); `EXP-0004` (`6` horizon sweep); `EXP-0026` (`5` SEC factors -> Bonferroni `99.0th` + BH FDR) | **Strong** (`200–2,000` fixed permutations / circular shifts + Bonferroni / BH FDR) | Must scale Bonferroni / Deflated Sharpe strictly when testing any new `EXP-0030` thresholds |
| **5. Trading Costs & Execution Realism** | `EXP-0007` (`Yahoo` vs `ECB` `0.38` return corr); `EXP-0017/18` (`Dukascopy` H1 spread `24x/d`); `EXP-0021` (`27 bp` Thai cost); `EXP-0023` (`5–10 bp` OKX); `EXP-0024/25` (`4` brokers + swap); `EXP-0028` (`2.4x–4.0x` rollover spread + `0.25–0.50p` swap markup); `EXP-0029` (`14–32 bp` RT + `5–8%` borrow) | **Very Strong** — real measured bid/ask, broker tiers, fees, borrow, and slippage enforced | Historical retail FX swap curves & Binance/Bybit APIs (`451`/`403`) remain bounded/unavailable |

---

## 4. Epistemic Classification Matrix

- **Verified Facts:**
  - `0/29` directional strategies passed pre-registered promotion bars.
  - `20:00–21:00 UTC` FX spreads expand `2.4x` (`EURGBP`) to `4.0x` (`EURUSD`) vs London/NY overlap.
  - Inverted `VIX/VIX3M > 1.0` separates `38.12%` vs `13.56%` SPY realized volatility (`2009–2026`).
  - `2,100` EA KB source files exist on disk (`integrity_check == ok`); `EA31337` (`331`), `EarnForex` (`62`), and `PopovMP` (`127`) are already heavily indexed.
- **Experimental Results:**
  - `EXP-0026` `F_NEG_ACCRUALS` (`N=317`): IS `+0.943`, OOS `+0.525` (`90.0%` pct, `20 bp` OOS `+0.494`).
  - `EXP-0027` Vol-Onset OOS `AUC = 0.7212`, `12%` causal Vol-Targeting SPY MaxDD `-34.10% -> -16.57%` IS / `-25.36% -> -16.18%` OOS.
  - `EXP-0024/25` 23y `EURGBP` H26/H28 net expectancy `-1.41` to `-3.35` pips/trade across all 4 broker cost models.
- **Hypotheses (Active / Open for Strictly Scoped Research):**
  - Can calibrated **Non-Price + Macro Meta-Labeling** improve **volatility/downside risk classification & exposure sizing** (`Task 3`) without chasing price-only directional alpha?
  - Does **Triple-Barrier Meta-Labeling** with strict **Purged Walk-Forward CV + Embargo + Full Transaction Costs + Null Permutations** hold up on non-price base rules (`Task 4 / EXP-0030`)?
- **Unverified Claims & Missing Evidence:**
  - Unacquired `201` MQL5 code-base files (`HTTP 403`), commercial `PineScript`/`Freqtrade`/`NostalgiaForInfinity` profit claims, historical retail FX swap tables, and delisted SEC firm mortality impact on `F_NEG_ACCRUALS`.
