"""Probe free, official, long-history FX data sources (no API keys, no payment).

Goal: replace Yahoo's 730-day / 26-year ceilings with central-bank series that go back
decades and are documented. Only public CSV/JSON endpoints are tested.
"""
import io, json, urllib.request, urllib.error, time

UA = {"User-Agent": "Mozilla/5.0 (research; contact: local)"}

SOURCES = [
    ("FRED DEXUSEU (USD per EUR, daily)", "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXUSEU"),
    ("FRED DEXUSUK (USD per GBP, daily)", "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXUSUK"),
    ("ECB SDW EUR/USD daily", "https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?format=csvdata&startPeriod=1999-01-01"),
    ("ECB SDW EUR/GBP daily", "https://data-api.ecb.europa.eu/service/data/EXR/D.GBP.EUR.SP00.A?format=csvdata&startPeriod=1999-01-01"),
    ("ECB SDW EUR/CHF daily", "https://data-api.ecb.europa.eu/service/data/EXR/D.CHF.EUR.SP00.A?format=csvdata&startPeriod=1999-01-01"),
    ("SNB data portal (cube devkum)", "https://data.snb.ch/api/cube/devkum/data/csv/en"),
    ("Bundesbank EUR/GBP daily", "https://api.statistiken.bundesbank.de/rest/download/BBEX3/D.GBP.EUR.BB.AC.000?format=csv&lang=en"),
    ("Bank of Canada EUR/CAD (valet)", "https://www.bankofcanada.ca/valet/observations/FXEURCAD/csv"),
    ("Bank of Canada AUD/CAD (valet)", "https://www.bankofcanada.ca/valet/observations/FXAUDCAD/csv"),
    ("RBA FXRDD (AUD bilateral)", "https://www.rba.gov.au/statistics/tables/csv/f11.1-data.csv"),
    ("BoE IUAMNPY (sterling ERI)", "https://www.bankofengland.co.uk/boeapps/iadb/fromshowcolumns.asp?csv.x=yes&Datefrom=01/Jan/1990&Dateto=now&SeriesCodes=XUDLER"),
    ("BIS USD/EUR monthly", "https://stats.bis.org/api/v1/data/WS_XRU/D.USD.EUR.A?format=csv"),
    ("FXCM H1 EURUSD 2024", "https://candledata.fxcorporate.com/H1/EURUSD/2024.csv.gz"),
    ("FXCM m1 EURUSD 2024 week1", "https://candledata.fxcorporate.com/m1/EURUSD/2024/1.csv.gz"),
    ("Dukascopy M1 EURGBP 1h file", "https://datafeed.dukascopy.com/datafeed/EURGBP/2026/10/02/BID_candles_min_1.bi5"),
]

for name, url in SOURCES:
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=25) as r:
            body = r.read(4000)
            code = r.status
        head = body.decode("utf-8", "replace").splitlines()[:3]
        head = " | ".join(h[:120] for h in head)
        print(f"[OK {code}] {name}  ({len(body)}b, {time.time()-t0:.1f}s)\n        {head[:220]}")
    except urllib.error.HTTPError as e:
        print(f"[HTTP {e.code}] {name}  ({time.time()-t0:.1f}s)")
    except Exception as e:
        print(f"[FAIL] {name}  {type(e).__name__}: {str(e)[:90]}  ({time.time()-t0:.1f}s)")
    time.sleep(0.6)
