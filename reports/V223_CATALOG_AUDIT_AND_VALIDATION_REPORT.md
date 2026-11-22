# ALINA Market Lab — `v2.23` Institutional Public Datasets Catalog Audit & Phase-C Validation Report

**Date (UTC):** `2026-11-22` | **Experiments:** `EXP-0049` through `EXP-0054` (plus `EXP-0051b`, `EXP-0054b`, `EXP-0054c`, `EXP-0054d`) | **Hypotheses:** `H56..H64` | **Cumulative Outcome:** `0 / 64` Non-Trend Alpha (`54` experiments total)

---

## 1. Executive Summary
We conducted an end-to-end live audit, selective ingestion, and strictly causal Phase-C validation across **all 18 sources** in `/home/user/uploads/Institutional Quant Public Datasets Catalog.md`:
- **12 genuinely new open-data sources** passed live URL, schema, and coverage verification and were cleanly ingested (`~7.9 MB` compressed across 18 new workspace artifacts, plus `Johnbrick123/sp500-data` `235.85 MB` CRSP-reconciled S&P 500 archive and `gauss314/options-IV-SP500` `3.16M` option chain rows cached in `/var/tmp/alina_raw_cache/`).
- **6 catalog items** were audited and documented as inaccessible, overlapping, or infeasible on resource/coverage grounds (`3ltrashpanda` HTTP `403`, `crypto-options-surface` `2026`-only span, `Dukascopy` HTTP `503` vs existing 22-year local H1 archive, `HistData.com` SSL handshake failure, `Stooq ^SET` rate block, `OpenMedallion` active-only/short history, `EPSOFT` overlapping existing `2004–2026` intraday, `PatentPulse` `211 GB` / `HUPD` `123.9 GB` exceeding 2 GB RAM sandbox).
- **Result across `EXP-0049..0054`:** **ALL 6 experiment batches (`H56..H64`) are `NO_EDGE` (`REJECTED`)** after survivorship-free reconstruction, transaction costs, permutation/circular-shift testing, and a four-stage adversarial falsification audit (`EXP-0054 -> 0054b -> 0054c -> 0054d`).
- **Validated Defensive Core (`EXP-0033` + `EXP-0041` + `EXP-0043`) Unchanged:** Neither on-chain crypto metrics, DeFi flows, CME crypto COT, macro surprises, 55-year equity factors, equity IV surfaces, Thai SET50/TFEX intraday rules, earnings transcripts, SEC XBRL buybacks, SEC `8-K` filings, nor 38-year freight PPI beat or improved our existing two defensive overlays (`Equity VT12% x RiskMeta(23f) -> BIL` and `Crypto SMA50/TrendEns x VT25% -> EFFR`).

---

## 2. Full Catalog Audit Matrix (All 18 Entries)

| Catalog ID | Dataset & Source | Live Audit Status | Key Caveats / Bugs Caught | Ingestion / Experiment |
|---|---|---|---|---|
| **1.1** | CoinMetrics Community BTC/ETH (`coinmetrics/data`) | **LIVE OK** (`2010–2026-10`) | `SOPR` omitted in Community tier; `CapMVRVCur`, flows, `AdrActCnt` present (`00:00 UTC` -> `+1d` lag) | `data/crypto_onchain/coinmetrics_{btc,eth}.csv.gz` (`EXP-0049`) |
| **1.2** | DeFiLlama Stablecoins & Chain TVL (`llama.fi`) | **LIVE OK** (`2017–2026-11`) | Clean daily USD snapshots; used `+1d` lag | `data/crypto_onchain/defillama_macro.csv.gz` (`EXP-0049`) |
| **1.3** | HuggingFace `3ltrashpanda` & `crypto-options-surface` | **REJECTED / SKIP** | `3ltrashpanda` returned HTTP `403`; `crypto-options-surface` starts `2026` only (too short) | Documented infeasible |
| **1.4** | CFTC Financial Futures COT (`fut_fin_txt_{2018..2026}.zip`) | **LIVE OK** (`2018–2026-11`) | Tuesday snapshot released Friday -> enforced `report_date + 3d` lag | `data/cot/cme_crypto_fin_cot.csv.gz` (`EXP-0049`) |
| **2.1** | Forex Factory Calendar (`Ehsanrs2/Forex_Factory_Calendar`) | **LIVE OK** (`2007–2025-04`) | Must filter out untimed `00:00:00` rows & restrict to UTC `11..19` (`1,911` clean USD clusters) | `data/events/forex_factory_2007_2025.csv.gz` (`EXP-0050`) |
| **2.2** | St. Louis Fed ALFRED (`alfredgraph.csv`) | **LIVE OK** (`200`) | First-print macro surprises already tested cleanly via Forex Factory unrevised actuals + SPF | Audited live; overlaps `2.1`/`2.3` |
| **2.3** | Philly Fed SPF (`MedianLevel.xlsx`) | **LIVE OK** (`1968Q4–2026Q4`) | Quarterly survey release -> causal quarterly alignment | `data/macro/philly_spf_median.csv.gz` (`EXP-0050`) |
| **3.1** | Ken French Daily Factors (`mba.tuck.dartmouth.edu`) | **LIVE OK** (`200`) | Already ingested & tested in `EXP-0046` (`1963–2026`, `15,918d`) | `data/macro/ken_french_ff5_mom_daily.csv.gz` (`EXP-0046`) |
| **3.2** | `Johnbrick123/sp500-data` (`1968–2026-10`) | **LIVE OK** (`99.99%` CRSP!) | **Critical trap:** `members.parquet` drops stale tickers — MUST use `membership_intervals.parquet` `[start, end]`; Yahoo `close` is backward split-adjusted while Tiingo/CRSP/Wiki are unsplit | Cached `prices.parquet` (`235.85 MB`), `EXP-0051`/`0051b`/`0054c`/`0054d` |
| **3.3** | `gauss314/options-IV-SP500` | **LIVE OK** (`2019-10..2023-07`) | `3,161,661` chain rows -> `678,292` daily surface features (`3.8y` span) | Cached `/var/tmp/alina_raw_cache/data_IV_USA.csv` (`EXP-0052`) |
| **3.4** | `oyi77/OpenMedallion` | **REJECTED / SKIP** | Active-only survivorship bias + overlaps `Johnbrick123` / local stocks | Documented skip |
| **4.1** | Stooq `^SET` CSV (`stooq.com`) | **BLOCKED** | Daily IP cap / blocked in sandbox | Covered by `4.2` (`SET50`) |
| **4.2** | SET50 Index & Futures Daily (`SamapanThongmee`) | **LIVE OK** (`2006–2023`) | String dash `"--"` in numeric columns (`pd.to_numeric` required); Futures daily is front-month | `data/thai/set50_{index,futures_daily}_2006_2023.*` (`EXP-0053`) |
| **4.3** | TFEX S50 1-Minute (`assazzin/Tradingview-S50`) | **LIVE OK** (`2016–2025`, `2,428d`) | Must strip contract overlap at roll; large open gaps are genuine market jumps | `data/thai/tfex_s50_15m_2016_2025.csv.gz` (`54,294` bars, `EXP-0053`) |
| **5.1–5.3** | Dukascopy (`503`), `EPSOFT` (overlap), `HistData` (SSL error) | **SKIP / OVERLAP** | Existing `data/intraday/*_H1_bidask.csv.gz` already provides 22-year (`2004–2026`) Dukascopy bid/ask H1 data | Used local H1 archive in `EXP-0050` |
| **6.1** | SEC EDGAR `companyfacts` & `submissions` (`8-K` + Buybacks) | **LIVE OK** (`2012–2026`) | **3 critical traps caught:** (i) `recent`-1000 cap truncated `47` megacaps (`JPM` missing `2013–2024` -> fixed via `808` archive JSONs); (ii) `companyfacts` returns comparative prior `end` dates on same `filed` (`56%` ties); (iii) `360`-firm subset had survivor bias -> expanded to **`796/797` (`99.9%`)** historical `2012–2026` S&P 500 CIKs | `sec_buybacks_sp500_full_pit.csv.gz` (`806` CIKs), `sec_8k_sp500_full_pit.csv.gz` (`133,850` `8-K`s) (`EXP-0054/b/c/d`) |
| **6.2** | S&P 500 Earnings Transcripts (`glopardo`, `20,681` calls) | **LIVE OK** (`2013Q2–2025Q1`) | `_eoq` EPS/PE fields leak beyond `earnings_date` and were strictly excluded | `sp500_earnings_transcript_features_2013_2025.csv.gz` (`EXP-0054/0054b`) |
| **6.3** | USPTO Patents (`HUPD/hupd` `123.9 GB`, `PatentPulse` `211 GB`) | **INFEASIBLE** | Verified `200` on HF API (`18` shards `123.9 GB` / `211 GB`), infeasible in `1.98 GB` RAM / `/tmp` container | Documented infeasible |
| **6.4** | FRED Deep Sea Freight PPI (`PCU483111483111`) & Cass (`FRGSHPUSM649NCIS`, `FRGEXPUSM649NCIS`) | **LIVE OK** (`1988–2026` PPI) | Note `FRGEXPUSM649NCIS` begins `2016-01` (not `1990-01`); enforced `+45d` BLS lag | `data/macro/fred_freight_monthly.csv` (`EXP-0054`) |

---

## 3. Experiment Outcomes (`EXP-0049` through `EXP-0054`)

### `EXP-0049` — Crypto On-Chain, DeFiLlama, Fear&Greed & CME Crypto COT (`NO_EDGE`)
- **13.4y BTC (`2013–2026`, `10bp` + EFFR):** `SMA50_VT25_Base` achieved **All `+1.713` | OOS `+1.534` | MaxDD `-31.38%` (`Shift300 = 100.0%`)** vs `BuyHold +1.234` (`-84.52%`). Every on-chain/overlay variant degraded or underperformed: `Overlay_MVRVCap2p5 +1.595`, `Overlay_AdrPos +1.550`, `MVRV_Value_LT2p5 +0.878`, `MVRV_Z_Contrarian +0.514`, `ExchOutflow_Pos +0.795`.
- **11y ETH (`2015–2026`):** `SMA50_VT25_Base` **All `+1.480` | OOS `+1.202`** beat `MVRVCap2p5 +1.445`, `AdrPos +1.358`, and `BuyHold +1.247` (`OOS +0.580`).
- **Modern BTC (`2018–2026`) & 19-Coin Basket:** `BTC SMA50_VT25 +1.357` beat `+StablePos (+1.219)`, `+FGCap80 (+1.285)`, and `+CME_AssetMgr (+1.351)`. Across all `19` coins: `SMA50_VT25_Base +1.315` (`OOS +1.297`) beat `+StablePos (+1.294)` and `+FGCap80 (+1.263)`.

### `EXP-0050` — Macro Surprises (`Forex Factory` H1/D1) & Philly Fed SPF (`NO_EDGE`)
- **H1 Intraday Post-Surprise (`2007–2025`, `1,911` timed USD clusters, `0.5bp/side`):** Release bars spike `~2.1x` in `|ret|` (`EURUSD 15.09bp` vs `7.20bp`), proving genuine announcement timing, but **post-release `H1..H24` drift is zero/negative**: `EURUSD H1 z>0.75 +0.41bp (t=+0.62, Sharpe +0.148)`, `XAUUSD -3.44bp (t=-2.33, H24 -12.85bp)`.
- **Daily Macro Surprise EMA (`2008–2025`):** Trailed `BuyHold` on `SPY` (`+0.340/+0.398` vs `+0.578`, OOS `+0.129/+0.323` vs `+0.760`), `TLT` (`-0.180` vs `+0.246`), and `GLD` (`+0.177` vs `+0.511`).
- **Philly Fed SPF (`2000–2026`):** `SPY_SPF_RGDP_Pos +0.441` (`OOS +0.575`) & `SPY_SPF_Disinfl_Bonds +0.471` trailed `SPY_BuyHold +0.488` (`OOS +0.780`); `TLT` variants (`OOS +0.029/-0.004`) matched flat `BuyHold +0.015`.

### `EXP-0051` + `EXP-0051b` — 55-Year Survivorship-Free PIT S&P 500 (`1971–2026`, `NO_EDGE`)
- **13,845 calendar days, median `485` PIT firms/month, `$5` min price, `10bp/side` + `dtb3`:**
  - Every canonical L/S factor decayed sharply post-2006 (`IS 1972–2005 -> OOS 2006–2026`):
    - `Mom_12_1_LS`: `+1.297 -> +0.122` (`perm200 = 22.5%`)
    - `FIP_LS`: `+1.059 -> +0.027` (`perm200 = 2.0%`)
    - `Rev_21d_LS`: `+0.917 -> -0.092` (`perm200 = 0.5%`)
    - `LowVol_60d_LS`: `+0.636 -> -0.039` (`perm200 = 0.0%`)
    - `Dist52H_LS`: `+0.586 -> -0.074` (`perm200 = 0.0%`)
    - `LowVol_x_Mom_LS`: `+1.124 -> -0.010` (`perm200 = 2.0%`)
  - **S&P 500 Index Additions (`EXP-0051b`):** Historical negative post-add drift (`1996–2013` `21d -2.519% t=-5.28`) **vanished in `2014–2026` (`21d -0.374% t=-0.68`)**.
  - **LowVol60 LO + VolTarget 12% (`EXP-0051b`):** `2014–2026 +0.876` (`DD -12.7%`) only matched single-ETF `SPY_VT12 (+0.857)` and trailed `EXP-0033 (+0.930)` without stock-picking overhead.

### `EXP-0052` — S&P 500 Equity Options IV Surface (`2019-10..2023-07`, `NO_EDGE`)
- Across `678,292` daily underlying IV surface rows (`10bp/side` + `dtb3`):
  - Monthly `21d` & Weekly `5d` L/S factors were negative or failed permutations: `vrp_20_LS` (`-0.117` perm `51.5%` / `-0.136`), `neg_smirk_LS` (`-0.120` / `-0.040`), `otm_itm_skew_LS` (`-0.547` / `-0.157`), `pc_vol_LS` (`-0.285` / `-1.940`), `pc_oi_LS` (`-0.481` / `-0.359`), `iv_hv_ratio_LS` (`-0.393` / `-0.659`), `neg_atm_iv_LS` (`-0.899` / `-0.952`), `call_surge_LS` (`-0.585` / `-0.759`).
  - `vrp_20_LO` collapsed on Weekly OOS (`+0.027`, perm `89.5%`).

### `EXP-0053` — Thai SET50 Daily & TFEX S50 1-Minute Intraday (`NO_EDGE`)
- **Daily SET50 (`2006–2023`, `4,244d`, `5bp/side`):** `SET50_BuyHold +0.255 (OOS +0.122, DD -61.7%)`; `TrendEns_VT12 +0.350 (OOS -0.270)`, `SMA50_VT12 +0.196 (OOS -0.296)`, `BasisZ_Contra_VT12 +0.330` (driven mostly by THB cash hurdle, not equity alpha), `OIMom20_VT12 OOS +0.021`.
- **TFEX S50 1m Intraday (`2016–2025`, `2,428d`):** ALL 7 intraday strategies (`ORB15m, ORB30m, GapFade, GapFollow, AftFollow_Morn0.3, AftFade_Morn0.3, AftFollow_All`) lost money net of **BOTH `5bp` (`-0.773` to `-2.521`) AND `2bp` (`-0.201` to `-0.955`)**.

### `EXP-0054` (`0054b / 0054c / 0054d`) — Adversarial Audit of Transcripts, SEC Buybacks, `8-K` Filings & 38y Freight (`NO_EDGE`)
Initial candidate spikes in `EXP-0054` were subjected to three progressive adversarial falsification rounds, exposing and eliminating every methodological distortion:

| Pillar | Initial (`exp0054` / `0054b`) Appearance | Exact Distortion Exposed | True Clean Audit Result (`exp0054b / c / d`) | Verdict |
|---|---|---|---|---|
| **S&P 500 Earnings Transcripts** (`20,681` calls, `496` firms) | `yoy_tone` `21d +0.823% (t=+4.31)` | Intra-quarter `quantile(0.8)` lookahead + clustered earnings dates | **Causal Calendar-Time L/S (`10bp`):** `net_tone_21d` All **`+0.057`** (`OOS -0.187`), `yoy_tone_21d` All **`+0.108`** (`IS -0.098`) | **`NO_EDGE`** |
| **SEC XBRL Buyback Yield** (`2013–2026`) | `PIT_SP500_SecNeut +0.880` (`OOS +1.119`) | (1) `360`-firm `2026` mega-cap survivor tilt (`EW +1.108`); (2) `56%` duplicate prior-year comparative `end` ties on same `filed` date; (3) Yahoo backward split-adjusted `close` × unadjusted XBRL `shares` across `265` splits (`AAPL/NVDA/AMZN` overstated `4x–40x` pre-split) | **100% PIT S&P 500 (`796/797` mapped, `806` CIKs, `unsplit_close`, SIC sector neutral):** `ZERO_FILL_SecNeut_10bp` **`-0.000`** (`IS -0.404 / OOS +0.275`); `ZERO_FILL_EW_10bp` **`+0.207`** (`20bp` **`-0.316`**); `bb_to_assets` **`+0.010`**; `net_share_red_yoy` **`+0.034`** | **`NO_EDGE`** |
| **SEC `8-K` Filings** (`Item 5.02`, `1.01`, `2.02`, `8.01`) | `CalShort 5.02 OOS +3.376`, `63d -0.949% (t=-4.96)` | `submissions/recent` `1,000`-row cap hid `2012–2025` `8-K`s for `47` mega-cap issuers (`JPM, BAC, GS, MS, C, GOOGL, CRM`) while keeping distressed/delisted filings | **Zero-Truncation (`808` archive JSONs, `133,850` `8-K`s, `94,866` strictly PIT S&P 500, flat `~1,700` `5.02`/yr):** `Item 5.02` (`n=17,846`) `5d -0.056% (t=-1.80)`, `21d -0.071% (t=-1.20)`, `63d -0.050% (t=-0.47)`; `CalShort 42d` All **`+0.312`** (`IS -1.026`) | **`NO_EDGE`** |
| **BLS Deep Sea Freight PPI** (`1988–2026`, `+45d` lag) | — | Tested directly with `+45d` BLS publication lag | Trailed `BuyHold` on `SPY` (`+0.084/+0.181` vs `+0.488`, OOS `+0.311` vs `+0.780`) and `GLD` (`+0.351/+0.424` vs `+0.584`) | **`NO_EDGE`** |

---

## 4. Production & Governance State (`v2.23`)
- **Tests:** **`39 / 39 pytest` PASSED** (`tests/test_backtest_engine.py`, `tests/test_eurgbp_pipeline.py`, `tests/test_governor.py`, `tests/test_workstreams.py` including `test_exp0049_to_0054_v223_catalog_validation`).
- **Daily Risk Radar (`9/9 FRESH`, `overall=HIGH`, `alerts=4`):** Live `2026-11-20/22` state shows `VIX=35.89` (`Slope3M=1.160` inverted), `Equity VolTarget12% x Meta(23f) = 44.6% Equity / 55.4% Cash Buffer`, and `BTC $59,084 < SMA50 $77,116 -> 0.0% BTC / 100.0% Cash` (`19-coin >SMA50 breadth = 1/19 = 5.3%`).
- **Execution Safety:** Phase D ML alpha, live trading, and demo trading remain **LOCKED** (`SIG_NONE` / `MODE_PAPER`).
