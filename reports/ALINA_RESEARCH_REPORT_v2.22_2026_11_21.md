# ALINA Market Lab — `v2.22` Exhaustive Open-Data Expansion & Validation Report (`EXP-0043..0048`)

Date UTC: `2026-11-21` | Scope: **5 New Free Institutional Data Pillars (`19-coin Crypto + 4.9y Binance OI/L-S`, `FRED Net Liquidity`, `20y Disaggregated COT`, `63y Ken French FF5+Mom`, `54 Bulk SEC Form 13F Zips`) + Untested Local Alt-Data (`SVXY/VXZ`, `EIA`, `19 Country ETFs`, `Wikipedia Attention`, `33y CBOE SKEW`, `S&P 500 Additions`)**

---

## 1. Executive Summary & Cumulative Scorecard (`EXP-0001..0048`)

1. **`EXP-0043` Strengthens & Validates Crypto Daily Trend Across Fallen Altcoins (`15/19` Coins):**
   - Testing `EXP-0041` (`SMA50_VT25` & `TrendEns_VT25`) on a survivorship-resistant **19-coin Binance spot universe (`2017–2026`, `52,926` daily bars)** — deliberately including `-96%` to `-99.7%` fallen cycle majors (`FIL, ICP, EOS, ALGO, LTC, BCH, ETC, XLM`) — proves the edge is **NOT BTC/ETH selection bias**.
   - `SMA50_VT25` beats Buy&Hold excess Sharpe on **`15 / 19` individual coins**, cuts Equal-Weight 19-coin MaxDD from **`-81.8%` to `-19.1%`**, lifts Sharpe **`+0.661 -> +1.176`** (`Calmar 0.320 -> 1.039`, `IS 18–22: +1.337 | OOS 23–26: +0.972`, `30bp/side: +1.015`, **`Shift300 = 99.67%`**), and holds cleanly even with BTC & ETH completely removed (`17 Altcoins`: `+0.648 -> +1.088`, DD `-18.5%`, `Shift300 = 98.67%`).
   - Integrated `19-coin >SMA50` breadth telemetry into `scripts/risk_radar.py` (`compute_crypto_trend_overlay()` — latest `2026-10-31`: **`1/19 (5.3%)` above SMA50**, matching deep winter Cash defense).
2. **All Other Directional / Institutional / Macro / Factor Hypotheses (`EXP-0043b..0048`) FAIL Phase C Survival:**
   - **Cumulative Epistemic Ledger (`48` Experiments, `55` Hypotheses):** **`0 / 47`** directional/factor/timing/alt-data/13F alpha hypotheses survive Phase C OOS, realistic cost, survivorship, and permutation controls. Phase D ML and live/demo EA execution stay **LOCKED (`SIG_NONE / MODE_PAPER`)**.
   - ALINA's two live defensive overlays stay unchanged and hardened: **(1) US Equities `EXP-0033` `VolTarget12% x RiskMeta(23f) -> BIL Cash` (`Sh +0.930, DD -14.74%, Calmar 0.699`)** and **(2) Crypto `EXP-0041/0043` `SMA50/TrendEns + VolTarget25% -> Cash`**.

---

## 2. Five Open-Data Pillars Ingested in `v2.22`

| Pillar | Dataset File | Coverage & Causality | Size |
|---|---|---|---:|
| **1A. Crypto 19-Coin Spot** | `data/crypto_vision/spot_daily_19coins.csv.gz` | `52,926` rows, `19` coins (`2017-08-17..2026-10-31`), dynamic `>=120d` eligibility | `1.5 MB` |
| **1B. Binance UM Futures Metrics** | `data/crypto_vision/binance_um_daily_metrics.csv.gz` | `3,592` days (`BTCUSDT/ETHUSDT`, `2021-12-01..2026-10-31`): OI, Top-Trader L/S, Global L/S, Taker L/S | `141 KB` |
| **2. US Fed Net Liquidity & Breakeven** | `data/macro/fred_liquidity_credit.csv` | `7,798` biz days (`1997..2026-11-21`); `WALCL/WTREGEN` shifted `+2d` to Fri (`net_liquidity_bn = $5,824.4B`). Note: FRED caps `BAMLH0A0HYM2` to trailing 3y (`2023-11..2026-11`). | `497 KB` |
| **3. CFTC Disaggregated COT** | `data/cot/cot_disagg_commodities.csv.gz` | `8,779` weekly rows (`2006..2026`, `1,067` reports across Gold, Silver, Platinum, WTI, NatGas, Corn, Soybeans), `available_from = report_date + 3d` | `382 KB` |
| **4. Ken French FF5 + Momentum** | `data/macro/ken_french_ff5_mom_daily.csv.gz` | `15,918` trading days (`1963-07-01..2026-09-30`): `Mkt_RF, SMB, HML, RMW, CMA, RF, Mom` | `214 KB` |
| **5. SEC Form 13F Bulk (`54` Zips)** | `data/sec/sec_13f_quarterly_holdings.csv.gz` | `18,466` `(period_end, ticker)` rows (`53` quarters `2013q2..2026q3`, `317/320` active + `68/68` delisted matched via OpenFIGI+CUSIP), `available_from = max(FILING_DATE)+1d`, `2023-01-03` `$1K->$1` boundary handled | `649 KB` |

---

## 3. Experiment Results (`EXP-0043..0048`)

### `EXP-0043` — 19-Coin Survivorship-Free Crypto Trend & 4.9y Binance OI / L-S Crowding
- **19-Coin Basket (`2018-06..2026-10`, `10bp/side`, Ex-EFFR):**
  - `EqualWeight BuyHold`: Sharpe **`+0.661`**, CAGR `+26.1%`, MaxDD **`-81.8%`**, Calmar `0.320` (`IS +0.714 | OOS23-26 +0.597`)
  - **`EqualWeight SMA50_VT25`:** Sharpe **`+1.176`**, CAGR `+19.9%`, MaxDD **`-19.1%`**, Calmar **`1.039`** (`IS +1.337 | OOS23-26 +0.972 | 30bp +1.015 | Shift300 = 99.67%`) — **PASS**
  - **`EqualWeight TrendEns_VT25`:** Sharpe **`+1.106`**, CAGR `+17.8%`, MaxDD **`-16.9%`**, Calmar **`1.055`** (`Shift300 = 99.0%`) — **PASS**
  - **17 Non-BTC/ETH Altcoins Only:** `BuyHold +0.648 (DD -83.1%)` $\rightarrow$ **`SMA50_VT25 +1.088 (DD -18.5%, Calmar 0.985, IS +1.265, OOS +0.862, Shift300 = 98.67%)`** — **PASS**
- **Fallen-Giant Individual Proof (`SMA50_VT25` vs `BuyHold`):** `FIL` (`-0.099` / `-99.7%` $\rightarrow$ **`+0.477` / `-31.1%`**), `ICP` (`-0.167` / `-96.7%` $\rightarrow$ **`+0.298` / `-26.1%`**), `EOS` (`+0.211` / `-97.2%` $\rightarrow$ **`+0.471` / `-23.9%`**), `ADA` (`+0.546` / `-95.2%` $\rightarrow$ `TrendEns +0.891` / `-25.4%`), `AVAX` (`+0.464` / `-95.6%` $\rightarrow$ `TrendEns +0.948` / `-23.4%`).
- **Rejected Arms (`FAIL`):**
  - Cross-Sectional Crypto Momentum (`XS_Mom21_LS`: `IS +0.500 -> OOS -0.239`; `XS_Mom60_LS`: `IS +0.960 -> OOS -0.151`).
  - Binance Futures `OI / Top-Trader L-S / Retail L-S / Taker Flow` (`2021-12..2026-10`, `n=1,796d`): all Spearman ICs near zero (`-0.014..+0.022`); every crowding filter degraded `TrendEns_VT25` OOS (`BTC +0.368 -> +0.241 / +0.194 / -0.788`; `ETH +0.408 -> +0.292 / -1.076 / -0.589`).

### `EXP-0044` — US Fed Net Liquidity, Full-Sample Risk Meta Ablation & VIX Term ETP Switch (`FAIL`)
- **Fed Net Liquidity (`WALCL - TGA - RRP`) Timing:** `SPY_if_NetLiq63_Pos` `OOS +0.587` vs `SPY BuyHold +0.675` (`74.0%` shift); `BTC_if_NetLiq90d_Pos` `OOS +0.439` vs `BTC BuyHold +0.442` (`72.0%` shift).
- **Full `3,830`-Day Risk Meta WF Ablation (`2011-08..2026-10` — after detecting & removing FRED's 3-year redistribution cap on `BAMLH0A0HYM2` which otherwise silently truncated WF to 671 rows!):**
  - `Base23`: `VolOnset AUC = 0.7656`, `TailStress AUC = 0.6461`, `VT12 x MetaCash Sharpe 0.784, MaxDD -12.17%, Calmar 0.747`.
  - `Plus2_NetLiq`: `VolOnset 0.7591` (**worse**), `TailStress 0.6311` (**worse**), `Calmar 0.756`. `Base23` stays untouched.
- **VIX Term-Structure ETP Switch (`SVXY / VXZ / BIL`, `2012–2026` TR incl. Feb 2018 Volmageddon):**
  - `Switch_SVXY_lt090_else_BIL`: `IS -1.381 | OOS -0.299 (0.0% shift!) | All -0.405 (DD -50.2%)`.
  - `Switch_SVXY_lt090_VXZ_gt100_else_BIL`: `IS +0.386 | OOS -0.101 (6.5% shift) | All -0.044 (DD -59.7%)`.

### `EXP-0045` — 20y Disaggregated Commodity COT + EIA Inventories & 19 Country ETFs (`FAIL`)
- **Commodity Disaggregated COT (`2009–2026` vs `GLD, SLV, PPLT, USO, UNG, DBA`):** No rule beat `BuyHold` consistently (`GLD MM_Mom +0.240 < BH +0.440`, `SLV +0.043 < +0.332`, `UNG -0.122`).
- **EIA Weekly Inventories:** Both failed (`USO All -0.114`, `UNG All -0.194`).
- **19 Country Equity ETFs TR (`2013–2026`):** `EqualWeight +0.287`; `Mom12-1 L/S All -0.142`; `Rev21d L/S All +0.090`; `SMA126_VT12 All +0.072`; `Mom12-1 Top4 LO` had negative IS (`-0.088 -> OOS +0.573`).

### `EXP-0046` — Ken French 63.2-Year Daily Factors & Factor Momentum (`1963–2026`, `FAIL`)
- **Post-Publication Academic Factor Decay (`IS 1963–94` $\rightarrow$ `OOS 1995–2026` $\rightarrow$ `Post-2010`):**
  - `SMB`: `+0.361 -> +0.040 ->` **`-0.100`** | `HML`: `+0.907 -> +0.172 ->` **`-0.062`** | `CMA`: `+0.845 -> +0.272 ->` **`+0.033`** | `RMW`: `+0.658 -> +0.420 -> +0.168` | `Mom`: `+1.206 -> +0.337 -> +0.284`.
  - `Static_EW_5Factors`: `+1.758 -> +0.526 ->` **`+0.177`**.
- **Factor Momentum (`10bp/side` ETF implementation):** `TSMOM_21d` (`Post2010 -0.052`, `10.7x/yr` turnover), `TSMOM_252d` (`+0.147`), `TSMOM_252d_LO` (`+0.147`), and `XSMom_Top2` (`+0.091`) **ALL trailed Static EW (`+0.177`) post-2010**.

### `EXP-0047` — SEC Form 13F (`54` Zips, `53` Quarters, `386` Active+Delisted Firms, `FAIL`)
- **Forensic Fix (`SIVBQ +8,362%`, `FRCB +700%`, `RADCQ +1,900%`, `CHK +2,571%`):** Unfiltered delisted series contain `< $1` zombie OTC bid-ask bounces after bankruptcy; enforcing institutional investability (`close >= $5.00 & volume >= 25,000` at rebalance) restored true `EqualWeight_Universe` benchmark (`IS +1.013 | OOS22-26 +0.715 | All +0.874, CAGR +18.9%, DD -37.5%`).
- **Results (`2017-03..2026-11`, `available_from = max(FILING_DATE)+1d`):** ALL `10` SEC 13F L/S & Top-25 LO strategies (`Breadth_1Q`, `Breadth_4Q`, `Anti-HHI`, `Put/Call Filers`, `Put/Call Shares`) **failed 95% ticker permutations (`25.5%..90.5%`)**, with L/S Sharpes between `-0.380` and `+0.276`.

### `EXP-0048` — Wikipedia Attention, 33y CBOE SKEW & S&P 500 Additions (`FAIL`)
- **Wikipedia Attention (`2016–2026`, `6` assets):** `IC7 = -0.03..+0.06`; both contrarian (`z > 2`) and FOMO (`z > 0.5`) trailed Buy&Hold OOS across all 6 assets.
- **33y CBOE SKEW (`1993–2026`):** Cash gating on `SKEW z > 1.5` or `> 145` degraded SPY OOS (`+0.421 / +0.484` vs `SPY +0.652`).
- **S&P 500 Additions (`2019–2026`, `n=31`, `t+1`):** `5d -0.543% (t=-0.63)`, `21d +0.758% (t=+0.41)`, `63d +8.49% (t=+1.20)`.

---

## 4. Verification & Deployment State
- `scripts/risk_radar.py`, `scripts/build_dashboard.py`, and `tests/test_workstreams.py` updated (`38/38` tests passing).
- `AlinaRiskGovernor.mq5` stays locked at `SIG_NONE` / `MODE_PAPER`; Phase D ML remains **PARKED**.
