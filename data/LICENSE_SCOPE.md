# ALINA Market Lab — Data Provenance & License Scope (`Personal Research in Cloud`)

Last Updated: `2026-11-21`

> **CRITICAL RULE:** Do NOT redistribute or republish raw vendor exports marked `[PERSONAL_RESEARCH_ONLY]` on public repositories, external websites, or commercial products. Never commit `.env` or API keys (`TIINGO_API_KEY`, `EODHD_API_KEY`) to git or Drive bundles.

## 1. Commercial-Safe / Public Domain / Permissive Feeds (`[COMMERCIAL_SAFE]`)
| Directory / Files | Source | Coverage | Notes |
|---|---|---|---|
| `data/macro/central_bank_rates_daily.csv`, `data/macro/fred_rates_full.csv` | NYFed EFFR, FRED (`DFF`, `SOFR`, `DGS2`, `DGS10`, `DGS30`, `DTB3`, `ECBESTR`, `IUDSOIA`), ECB, BoE | `1954–2026-11-20` (`effr` 100% populated) | Public domain / official central bank data |
| `data/collect/treasury_auctions*.csv*`, `data/collect/ofr_fsi.csv`, `data/collect/gpr_monthly.csv` | US Treasury FiscalData (`1979–2026`), OFR FSI, Caldara-Iacoviello GPR | `1979–2026-11` | Zero-key official/academic feeds |
| `data/events/event_calendar_full.csv`, `data/events/central_bank_2027_official.csv` | Fed FOMC, ECB, BoE, BoJ official 2027 schedules + US Treasury auctions | `1994–2027-12-31` | Verified official central bank pages |
| `data/sec/` (`pit_fundamentals_expanded.csv`, `pit_fundamentals_delisted.csv`, `insider_form4_2025_2026q1.csv.gz`) | SEC EDGAR (`submissions`, `companyfacts`, Form 3/4/5) | `317` active + `27` delisted (`leaks=0`); `133,957` Form 4 open-market P/S (`2025q1–2026q1`) | Public US government filings |
| `data/cot/cot_weekly.csv`, `data/cot/cot_features.csv` | CFTC Socrata (`6dca-aqww`) | `35,815` rows (`0` duplicates) | Public US CFTC data |
| `data/congress/congress_trades.csv` | US House/Senate periodic disclosures | `6,365` rows (`audit_flag` added) | Public disclosures |
| `data/equities/sp500_ticker_start_end.csv`, `sp500_historical_components.csv`, `finra_short_interest_latest5k.csv.gz` | `fja05680/sp500` (MIT), FINRA API | `1996–2026-08-18` (`1,262` S&P tickers) | Permissive MIT / FINRA public |
| `data/ea_kb/alina_ea_kb.sqlite`, `sources_batch*` | GitHub OSI-licensed repos (Batches 1–6 audit) | `2,174` files (`553` EAs) | Batch 6 `74` files verified OSI; Batches 1–5 legacy provenance audited in `KB_STATS_BATCH6.json` |

## 2. Personal Research Only (`[PERSONAL_RESEARCH_ONLY]`)
| Directory / Files | Source & Tier | Coverage | Restriction |
|---|---|---|---|
| `data/tiingo/supported_tickers.csv.gz` | Tiingo Starter (`$0`) | `109,368` tickers (`19,119` US delisted stocks) | Personal research only; non-commercial |
| `data/etfs_tiingo/*.csv`, `data/broad/{TLT,SPY,IEF,...}.csv` | Tiingo Daily API (`$0` Starter) | `15` core ETFs (`2000–2026-11-20`), `adjClose` + `divCash` + `splitFactor` | Personal research only; no redistribution |
| `data/stocks_delisted_tiingo/*.csv` | Tiingo Daily API (`$0` Starter) | `30` delisted/bankrupt/M&A US tickers (`2010–2026`) | Personal research only; no redistribution |
| `data/thai/EODHD_*_INDX.csv`, `data/thai/eodhd_*.csv` | EODHD Free (`$0`, `20/day`) | `SET.INDX`, `SET50.INDX`, `SET100.INDX` (`241` bars, `1y` free cap); `874` `.BK` symbols | Personal research only; 1-year EOD cap on Free plan |
| `data/crypto_vision/*.csv.gz` | `data.binance.vision` | `BTCUSDT`, `ETHUSDT`, `SOLUSDT` 1h Spot/Perp/Funding (`2019-09–2026-10`, `0` gaps on perp) | CC BY-NC-SA 4.0 (Non-commercial only) |
| `data/microstructure/deribit_*_1h.csv.gz` | Deribit Public API | Funding/Perp (`2024–2026-11-21`, `0` gaps) + DVOL (`2021-03–2026-11-21`, `49,632` bars) | Personal research; commercial API requires license |
| `data/universe/`, `data/stocks/`, `data/sec/prices_pit/`, `data/collect/vol_stress_features.csv` | Yahoo Finance / CBOE CSV | Active daily OHLCV / VIX suite | Personal research only; not for commercial resale |
