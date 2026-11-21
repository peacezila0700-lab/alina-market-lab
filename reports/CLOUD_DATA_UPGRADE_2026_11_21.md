# ALINA Market Lab — Cloud Data Upgrade & Integrity Report (`v2.19`)

**Date:** `2026-11-21` | **Mode:** `Personal Research in Cloud` (`No KYC`, `Telegram Deferred`, `Phase C Kill Point LOCKED`)

## 1. Executive Summary
Following the read-only Data Audit (`v2.18`), ALINA executed its **Phase-1 Cloud Data Upgrade** using only verified Zero-Key public feeds plus the user's **Tiingo Starter (`$0`)** and **EODHD Free (`$0`)** API keys (**Databento rejected/skipped due to KYC; Telegram deferred per user**). Every dataset passed strict OHLC, monotonicity, split/dividend, and point-in-time (PIT) timestamp verification (`35/35 pytest` passing in `1.46s`).

Two new empirical experiments (**`EXP-0032`**, **`EXP-0033`**) quantified the real-world impact of these upgrades:
1. **`EXP-0032` (Survivorship Bias Empirical Proof):** Adding `+27` real delisted/bankrupt/M&A US firms (`SIVBQ`, `BBBYQ`, `RADCQ`, `WEWKQ`, `NKLA`, `SAVEQ`, `TWTR`, `ATVI`, `WBA`, `DISH`, etc.) with zero-leak SEC XBRL PIT snapshots (`1,030` rows, `0` leaks) to the `317` active SEC firms **dropped `F_NEG_ACCRUALS` 10bp L/S Sharpe by `-0.150` (`+0.729 -> +0.579`) and lowered OOS permutation percentile from `92.5% -> 75.0%`**, proving active-only testing overstated performance by ~`26%`.
2. **`EXP-0033` (Tiingo Total-Return & `BIL` Cash Parity):** Re-running `EXP-0031` (`2015-01-02..2026-09-16`, `n=2,943`) on dividend-inclusive Tiingo `adjClose` plus tradeable T-Bill ETF `BIL` (with Day-0 cost & geometric CAGR) confirmed **`5_VolTarget12_Meta_Cash` (`Sharpe +0.930`, `CAGR +10.11%`, `MaxDD -14.74%`, `Calmar 0.699`)** beats `SPY Buy & Hold` (`Calmar 0.404`, `MaxDD -33.70%`) and decisively outperforms blind `TLT` rotation (`MaxDD -27.00%`, `Calmar 0.336`).

---

## 2. Upgraded Datasets & Audit Defect Closures
| Gap / Item | Before (`v2.18`) | After (`v2.19`) | Source & License Scope |
|---|---|---|---|
| **Missing `TLT.csv` & post-close `broad/`** | `data/broad/TLT.csv` absent; `2026-11-20` `SPY=697.76` stale intraday print | `data/broad/TLT.csv` (`6,121` bars `2002-07-26..2026-11-20`) + `15` core ETFs in `data/etfs_tiingo/` (`adjClose`, `divCash`, `splitFactor`); `SPY` verified post-close `689.81` (`151.4M` vol) | Tiingo Daily (`[PERSONAL_RESEARCH_ONLY]`) |
| **US Delisted Universe & SEC PIT** | `0` delisted firms; `data/sec/prices_pit/` missing locally | `data/tiingo/supported_tickers.csv.gz` (`109,368` tickers incl. `19,119` delisted US stocks); `30` delisted stocks (`data/stocks_delisted_tiingo/`) + `27` SEC PIT (`1,030` rows, `0` leaks) + `320/320` active `prices_pit/` restored | Tiingo (`[PERSONAL_RESEARCH_ONLY]`) + SEC EDGAR (`[COMMERCIAL_SAFE]`) |
| **Historical S&P 500 & Insider Form 4** | Active Nasdaq screener only; no Form 4 bulk | `data/equities/sp500_ticker_start_end.csv` (`1,262` names) + `sp500_historical_components.csv` (`2,720` snapshots `1996..2026-08-18`) + `insider_form4_2025_2026q1.csv.gz` (`133,957` open-market P/S tx across `4,429` tickers) + `FINRA` short interest (`5,000` sample) | `fja05680/sp500` (MIT), SEC Form 3/4/5, FINRA (`[COMMERCIAL_SAFE]`) |
| **Thai SET Benchmark** | Yahoo `^SET.BK` broken (`1` bar) | `SET.INDX` (`last=1453.28`), `SET50.INDX` (`993.9`), `SET100.INDX` (`2136.71`), `241` bars `[2025-11-21..2026-11-20]` + `874` `.BK` symbol list (`1y` EOD free cap verified) | EODHD Free (`[PERSONAL_RESEARCH_ONLY]`) |
| **Macro EFFR & Treasury Auctions** | `effr` `61.5%` blank pre-`2016-03-01`; `treasury_auctions.csv` `200` rows | `central_bank_rates_daily.csv` `effr` `10,186/10,186` (`0` nulls) via `FRED DFF` (`1954–2026`) + `fred_rates_full.csv` (`SOFR, DGS2/10/30, DTB3, ESTR, SONIA`); `treasury_auctions.csv` expanded to `11,154` rows (`1979–2026`) | FRED & FiscalData (`[COMMERCIAL_SAFE]`) |
| **2027 Central Bank Calendars** | Calendar stopped `2026-12-31` | Official `2027` schedules added for **FOMC (`8`), ECB (`8`), BOE (`8`), BOJ (`8`)** + `NFP_approx/OPEX/MONTH_END/QUARTER_END` (`max_date=2027-12-31`, `2,293` rows) | Fed, ECB, BoE, BoJ (`[COMMERCIAL_SAFE]`) |
| **Crypto `2020–2023` & Deribit Gaps** | `2020–2023` missing; `deribit_*_funding_1h` had `36` 2h gaps | `data/crypto_vision/`: `BTCUSDT, ETHUSDT, SOLUSDT` 1h Spot/Perp/Funding (`2019-09..2026-10`, `59,904` perp bars, `0` gaps); Deribit `funding_1h` `25,320` rows (**`0` gaps**) + `DVOL 1h` (`49,632` rows `2021-03..2026-11`) | Binance Vision (`CC BY-NC-SA 4.0`) + Deribit (`[PERSONAL_RESEARCH_ONLY]`) |
| **Schema & Anomaly Cleanups** | `121` COT dup pairs; `H09-H11` shifted; `2` neg FX spreads; `congress` future tx unflagged | `cot_features.csv` & `cot_weekly.csv` deduplicated (`35,815` rows, `0` dups); `HYPOTHESIS_REGISTER.csv` aligned (`28x25`); `EURUSD/USDJPY H1` neg spreads=`0`; `congress_trades.csv` flagged (`audit_flag`); `CCZ` bond note warned in `MANIFEST_STOCKS.json` | Internal hygiene (`35/35 pytest` verified) |

---

## 3. API Quota Accounting & Remaining Limits
- **Tiingo Starter (`$0`, `50 req/hr`, `500 symbols/mo`, `1,000 req/day`):**
  - Used **`45 / 500` unique symbols this month** (`15` Core ETFs + `30` Delisted US Stocks; `supported_tickers.zip` = `0` symbol quota).
  - Remaining monthly quota: **`455 / 500` symbols** (available for batch-pulling additional delisted S&P 500 stocks or the `228` SEC PIT firms).
- **EODHD Free (`$0`, `20 calls/day`, `1-year` historical EOD cap confirmed):**
  - Verified live via `/api/user`: **`8 / 20` requests used today** (`12 / 20` remaining).
  - Confirmed that EODHD Free truncates historical EOD CSVs to **trailing 1 year** (`"Data is limited by one year as you have free subscription"`). Multi-decade `.BK` history requires either EODHD All-World (`$19.99/mo` personal) or SETSMART/local broker exports.

## 4. Risk Radar Snapshot (`2026-11-21`, `8/8 FRESH`)
- **Classification:** `HIGH` (`VIX=35.89`, `VIX/VIX3M=1.160`, `VVIX pct=0.996`, `SPY RV20=26.3%`, `52w DD=-11.5%`).
- **Calibrated Risk Meta-Model (`as_of 2026-11-20`):** `P(VolOnset_21d)=7.27%`, `P(TailStress_21d)=34.40%`, `P(TB_NonDirStress_21d)=34.40%` -> Offline Defensive Reference: `44.6%` Equity / `55.4%` Cash Buffer (`Phase C Kill Point LOCKED`).
