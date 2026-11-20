# DATA SOURCES — verified live/dead map (probed 2026-11-20)

Every entry was tested from a sandbox with plain `curl`/`urllib`, no API key, no signup unless noted.
Re-use the working patterns verbatim; they took many attempts to find.

## LIVE (verified working, exact pattern)

| Data | Endpoint pattern | Notes |
|---|---|---|
| FX official daily (1999+) | `https://data-api.ecb.europa.eu/service/data/EXR/D.{CCY}.EUR.SP00.A?format=csvdata&startPeriod=1999-01-01` | 7,203 rows each for USD,JPY,GBP,CHF,CAD,SEK,NOK,AUD,NZD. Columns `TIME_PERIOD`,`OBS_VALUE`. **Best free FX source.** |
| COT positioning (1986+) | `https://publicreporting.cftc.gov/resource/6dca-aqww.json?$where=contract_market_name='GOLD'&$limit=50000&$order=report_date_as_yyyy_mm_dd` | Socrata API. Discover names with `$select=contract_market_name,count(*)&$group=contract_market_name`. Legacy futures-only dataset id `6dca-aqww`. |
| COT bulk (alt) | `https://www.cftc.gov/files/dea/history/dea_fut_xls_YYYY.zip` | Legacy BIFF `.xls` inside, ~8 MB/yr — needs `xlrd`; the Socrata route is easier and needs no parsing. |
| VIX history | `https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv` | 9,320 rows from 1990-01-02. Needs `curl -L` (307 redirect). |
| SKEW history | `https://cdn.cboe.com/api/global/us_indices/daily_prices/SKEW_History.csv` | 9,274 rows from 1990. |
| FX bid/ask (measured spread) | `https://freeserv.dukascopy.com/2.0/index.php?path=chart%2Fjson3&instrument=EUR%2FUSD&offer_side=B&interval=1HOUR&splits=true&stocks=true&time_direction=P&timestamp={ms}&jsonp=cb` | **Must URL-encode `chart%2Fjson3` and `EUR%2FUSD`** or you get `_callbacks____error([null])`. Query twice: `offer_side=B` (bid) and `A` (ask) -> spread = ask − bid. 30,000 bars/call, back to 2003. Send `Referer: https://freeserv.dukascopy.com/`. |
| FOMC decision dates | `https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm` + `.../fomchistorical{1994..2026}.htm` | Parse `monetaryYYYYMMDDa.htm` (2011+) and `fomcYYYYMMDD{beige,greenbook,...}` (older). Exclude panels whose heading contains "Conference Call". |
| Economic calendar | `https://nfs.faireconomy.media/ff_calendar_thisweek.json` | **Current week only** — no free history exists. 429s aggressively; back off >= 12 s. |
| Wikipedia attention | `https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/en.wikipedia/all-access/user/{Article}/daily/{YYYYMMDD}/{YYYYMMDD}` | Daily views, 2015+. Free, no key. |
| Yahoo daily OHLCV | `https://query1.finance.yahoo.com/v8/finance/chart/{SYM}?period1=946684800&period2={now}&interval=1d` | Must pass explicit period1/period2 (`range=max` caps ~300 bars). FX history starts 2003–2006 only. |
| MQL5 free EA listings | `https://www.mql5.com/en/code/mt5/experts` + `/page{N}` | HTML listing; parse `/en/code/\d+` links. |
| GitHub repo search | `https://api.github.com/search/repositories?q={query}&sort=stars&per_page=25` | Unauthenticated, 10 req/min. Code search needs a token (401 without). |
| SNB data portal | `https://data.snb.ch/api/cube/{cube}/data/csv/en` | Works, e.g. `zimoma`. |
| Bank of Canada Valet | `https://www.bankofcanada.ca/valet/observations/{SERIES}/csv` | Works (e.g. V39079 = policy rate). |
| RBA tables | `https://www.rba.gov.au/statistics/tables/csv/f1.1-data.csv` | Works, **but truncated window** (f11.1 serves only ~2023+). |
| Norges Bank | `https://data.norges-bank.no/api/data/IR/B.KPRA.SD.R?format=csv` | Works. |
| BoE IADB CSV | `https://www.bankofengland.co.uk/boeapps/database/_iadb-fromshowcolumns.asp?csv.x=yes&Datefrom=01/Jan/2000&Dateto=now&SeriesCodes=IUDBEDR&CSVF=TN&UsingCodes=Y&VPD=Y&VFD=N` | Works when `UsingCodes=Y` and `csv.x=yes`. |
| Bundesbank | `https://api.statistiken.bundesbank.de/rest/download/BBEX3/...` | Returns data (BBEX3 FX). |

## DEAD (do not waste time — re-verified 2026-11-20)

| Source | Failure |
|---|---|
| FRED `fredgraph.csv` | connection timeout (25 s), no body |
| BIS `stats.bis.org` API | 404 on series endpoints |
| GDELT DOC API | hard HTTP 429 even at 1 request / 30 s from this IP |
| CBOE put/call CSVs (`totalpc.csv`, `equitypc.csv`, `indexpc.csv`) | return a 341 KB **HTML 404 page with status 200** — validate content, not status |
| `cdn.cboe.com/.../CPC_History.csv`, `PCRATIO_History.csv` | 403 |
| OECD SDMX | 403 |
| Riksbank SWEA | 204 empty body |
| RBNZ | 403 |
| Stooq | unreachable |
| FXCM candledata | 404 |
| SIFMA securities-industry-data archive | 404 |
| Dukascopy `.bi5` datafeed | HTTP 503 (the freeserv chart API is the reliable route) |
| Yahoo H1 intraday | 730-day ceiling; no spread column |
| GitHub code search API | 401 without token |
| `^SET.BK` (Thai index) | 1 bar only |

## Data-quality traps found the hard way
- **Yahoo FX cannot be trusted for returns.** ECB EURUSD vs Yahoo EURUSD: level correlation 0.998
  but **daily-return correlation 0.38**; GBPUSD 0.52. No lag (−2…+2) fixes it — different snapshot time.
- **Yahoo FX bad prints** up to 13.8% (EURUSD 2008-12-08: 1.4918 vs official 1.2854).
- **RBA f11.1** looks like it covers 1983, but the API serves only ~2023 onward.
- **CBOE CSV URLs** can return HTTP 200 + HTML; always check the first bytes are not `<!DOCTYPE`.
- **CFTC zip** contains a legacy BIFF `.xls` (OLE2 magic `D0CF11E0`), not CSV — `pd.read_csv` fails.

## Volatility term structure and deep history (added 2026-11-20)
| endpoint | what it gives | note |
|---|---|---|
| `cdn.cboe.com/api/global/us_indices/daily_prices/{VIX,VIX1D,VIX9D,VIX3M,VVIX,SKEW}_History.csv` | VIX curve + vol-of-vol + skew | **requires `curl -sL`** (307 redirect) and a browser UA. CSV layouts differ per file: some rows have no comma between date and value, so parse with a regex, not a CSV reader. VIX3M from 2009-09, VIX9D 2011-01, VIX1D 2022-05. |
| `home.treasury.gov/.../daily-treasury-rates.csv/{YYYY}/all?type=daily_treasury_yield_curve&field_tdr_date_value={YYYY}&page&_format=csv` | full yield curve for one calendar year | loop 1990..now (37 requests, ~0s each) → 9,228 rows of deep history. The daily collector alone only appends the latest row. |
| `okx.com/api/v5/public/funding-rate-history?instId=BTC-USDT-SWAP` | funding settlements | **`-SWAP` suffix is mandatory**; the spot id returns code 51000. Depth capped at ~3 months (280 rows). |
| `okx.com/api/v5/market/history-candles?instId=BTC-USDT&bar=1H&limit=100&after=<ts>` | hourly candles | paginate with `after`; ~10,000 bars per symbol is the endpoint ceiling. |
