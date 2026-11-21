# COVERAGE MATRIX — the owner's 13 categories, mapped to real files

Written 2026-11-20. Every row was verified by fetching and parsing the actual data, not by assuming a
source exists. "Gap" means the honest answer is *not available for free*; do not re-probe those.

| # | Category (owner's list) | Status | What we actually hold | File(s) | Freshness |
|---|---|---|---|---|---|
| 1 | **Trading Strategy** | covered (as evidence, not as signals) | 18 pre-registered experiments with verdicts, pre-registration text, and the null design for each. 0 validated edges — that is the finding, and it is worth more than a fake one | `research/EXPERIMENT_LOG.csv`, `results/experiments.jsonl`, `artifacts/*.json` | static, updated per experiment |
| 2 | **Technical Analysis / Price Action** | covered | 209 instruments × 40 indicators (RSI, MACD, BB, ATR, ADX, Stoch, Donchian, Keltner, OBV, z-scores, 52w distance, realised vol) + support/resistance with stated rules (pivots, prior D/W, value areas, swing points) | `data/technicals/latest.csv`, `data/technicals/history_wide.csv.gz`, `data/levels/*`, `data/facts/HOUR_OF_DAY_PROFILE.md` | daily |
| 3 | **Fundamental / company analysis** | covered for the top 60 US names | as-filed XBRL: revenue, net income, EPS diluted, assets, liabilities, equity, cash, CFO, long-term debt; net margin, ROE, P/E derived | `data/sec/fundamentals.csv`, `data/sec/MANIFEST_SEC.json` | quarterly (as filed) |
| 4 | **Macroeconomics** (rates, inflation, GDP) | covered | US Treasury curve 1990-2026 (13 tenors), BLS CPI/PAYEMS, EIA crude+gas, EPU + GPR indices, OFR Financial Stress Index, **and a World Bank panel: 22 economies × 9 indicators 1990-2025** | `data/collect/treasury_yield_curve_full.csv`, `data/macro/wb_latest.csv`, `data/macro/wb_panel_long.csv`, `data/alt/*` | daily (US) / annual (world) |
| 5 | **Market news & events** | covered, wider than before | 294 headlines from 15 RSS outlets **plus 1,294 headlines from 425 outlets across 26 queries and 16 country editions** (incl. Thai, Vietnamese, Arabic, Chinese, Japanese), entity-tagged; event DB of 2,028 dated events | `data/news/headlines.csv`, `data/news/headlines_world.csv`, `data/events/event_calendar_full.csv`, `data/events/EVENT_STATS.md` | intraday (RSS), daily (events) |
| 6 | **Historical price data** | covered | 209 instruments daily (68 ETFs, 24 research panel, 115 US stocks, 10y each), 6 FX/metals pairs hourly with bid+ask 2003-2026, BTC/ETH 1H, crypto funding | `data/broad/`, `data/stocks/`, `data/universe/`, `data/intraday/*.csv.gz` | daily / hourly |
| 7 | **Market price API** | covered (free, key-less) | Yahoo chart v8 (daily), Dukascopy freeserv (hourly bid/ask), OKX (crypto 1H + funding), CBOE (VIX complex), Treasury.gov, Nasdaq quote API | see `datapack_src/DATA_SOURCES.md` for the exact URL patterns | as above |
| 8 | **News API** | covered | 15 direct RSS feeds + Google News RSS aggregation by topic and by country edition; per-day numeric pressure series | `data/news/*` | intraday |
| 9 | **Financial statements** | covered (top 60) | see #3; plus filing metadata (form type, filed date, period, accession, primary document) | `data/sec/filings.csv` | as filed |
| 10 | **Economic calendar** | covered | FOMC dates 1990-2026, Treasury auctions (bid-to-cover), OPEX, month/quarter end, NFP rule, VIX-onset, shocks; ForexFactory XML for the current+next week; BLS/BEA/Fed release schedules | `data/events/`, `data/collect/econ_calendar.csv` | daily |
| 11 | **SEC filings** | covered (top 60) | last 25 filings per company including 10-K/10-Q/8-K/**Form 4 (insider)** — the Form 4 rows are stored but **not parsed** into insider transactions yet (explicit gap) | `data/sec/filings.csv` | daily |
| 12 | **Stock screener** | covered | 7,301 NYSE/Nasdaq symbols with market cap, sector, industry, country, last sale, **joined to technicals and to as-filed fundamentals with staleness columns** (`fund_age_days`, `filing_age_days`) | `data/screener/screener_latest.csv`, `data/screener/nasdaq_all.csv` | daily |
| 13 | **Technical indicators** | covered | same as #2, with a column dictionary in `data/technicals/MANIFEST_TECH.json` (category per column: momentum / volatility / trend / volume) | `data/technicals/` | daily |

## Gaps that free data genuinely cannot close
| Gap | Why it matters | What we do instead |
|---|---|---|
| **Options chain with strikes/IV per expiry** | blocks every variance/straddle test, blocks a true VRP study | Deribit crypto chain + CBOE indices only; equity chains need a paid feed |
| **Intraday equity data beyond 730 days** | blocks intraday equity work | hourly FX/metals only (23y, bid+ask measured) |
| **Point-in-time fundamentals (vintages)** | as-filed XBRL is revision-free, so fundamental backtests carry restatement bias | `filed` dates are stored so a lagged version can be built later |
| **Analyst estimates / guidance** | needed for "did it beat expectations" rather than "did EPS rise" | none free; the gap is stated in every fundamental caption |
| **Real-time (sub-second) prices** | latency-sensitive strategies | one-bar execution model documented in `INTRADAY_REALITY.md` |
| **Parsed insider transactions (Form 4)** | a genuinely interesting, free signal | filings are stored; parsing is a concrete next task (see below) |

## The three next tasks this matrix exposes, in value order
1. **Parse Form 4 filings into an insider-buying dataset.** It is free, it is genuinely non-price
   information, and it is the only category in the list we hold raw but have not turned into numbers.
2. **Build a lagged (point-in-time) fundamental panel** using `filed` dates, so a fundamental backtest is
   not silently restated.
3. **Extend the stock panel past 120 names** and use it for the cross-section tests that the 68-ETF panel
   was too small for (the honest null is already written in `PITFALLS.md` #11).
