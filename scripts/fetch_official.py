"""Free, official, long-history daily FX — no API keys, no payment.

Sources
  ECB Statistical Data Warehouse   EUR/USD, EUR/GBP, EUR/CHF   from 1999-01-04
  Reserve Bank of Australia F11.1  AUD/USD, AUD/NZD, AUD/CAD, AUD/CHF  from 1983

Both are central-bank publications with documented methodology, in contrast to vendor data.
Outputs one CSV per pair: data/official/{PAIR}_D.csv  (date, close)
Plus a cross-check of EUR/USD against the Yahoo series already in the project.
"""
import csv, io, os, urllib.request, datetime as dt
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "official")
os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (research)"}

ECB = {"EURUSD": "USD", "EURGBP": "GBP", "EURCHF": "CHF"}
RBA_COLS = {"AUDUSD": "A$1=USD", "AUDNZD": "A$1=NZD", "AUDCAD": "A$1=CAD",
            "AUDCHF": "A$1=CHF", "AUDEUR": "A$1=EUR"}


def get(url, timeout=60):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout).read()


def fetch_ecb():
    out = {}
    for pair, ccy in ECB.items():
        url = (f"https://data-api.ecb.europa.eu/service/data/EXR/D.{ccy}.EUR.SP00.A"
               f"?format=csvdata&startPeriod=1999-01-01")
        txt = get(url).decode("utf-8", "replace")
        rows = []
        for r in csv.DictReader(io.StringIO(txt)):
            try:
                rows.append((r["TIME_PERIOD"], float(r["OBS_VALUE"])))
            except (KeyError, ValueError):
                continue
        rows.sort()
        out[pair] = rows
        print(f"ECB {pair}: {len(rows)} rows  {rows[0][0]} -> {rows[-1][0]}")
    return out


def fetch_rba():
    txt = get("https://www.rba.gov.au/statistics/tables/csv/f11.1-data.csv").decode("utf-8", "replace")
    lines = txt.splitlines()
    header = next(l for l in lines if l.startswith("Title,")).split(",")
    idx = {name.strip(): i for i, name in enumerate(header)}
    out = {p: [] for p in RBA_COLS}
    fmts = ("%d/%m/%Y", "%d-%b-%Y", "%Y-%m-%d")
    for l in lines:
        parts = l.split(",")
        if len(parts) < len(header):
            continue
        date = None
        for f in fmts:
            try:
                date = dt.datetime.strptime(parts[0].strip().strip('"'), f).date().isoformat()
                break
            except ValueError:
                continue
        if not date:
            continue
        for pair, col in RBA_COLS.items():
            i = idx.get(col)
            if i is None:
                continue
            v = parts[i].strip().strip('"')
            try:
                x = float(v)
            except ValueError:
                continue
            if x > 0:
                out[pair].append((date, x))
    for pair, rows in out.items():
        if rows:
            rows.sort()
            print(f"RBA {pair}: {len(rows)} rows  {rows[0][0]} -> {rows[-1][0]}")
    return {k: v for k, v in out.items() if v}


def crosscheck(pairs):
    """EUR/USD from ECB vs Yahoo (already in the project) — overlapping period"""
    ypath = os.path.join(ROOT, "data", "processed", "EURUSD_D1_fullclean.csv")
    if not os.path.exists(ypath):
        return None
    y = {r["ts_utc"][:10]: float(r["close"]) for r in csv.DictReader(open(ypath))}
    e = dict(pairs["EURUSD"])
    both = [(d, e[d], y[d]) for d in e if d in y]
    if not both:
        return None
    diff = np.array([(a - b) / b * 1e4 / 1e2 for _, a, b in both])   # % difference
    return dict(n=len(both), mean_abs_pct=round(float(np.abs(diff).mean()), 4),
                max_abs_pct=round(float(np.abs(diff).max()), 4))


if __name__ == "__main__":
    pairs = {}
    pairs.update(fetch_ecb())
    pairs.update(fetch_rba())
    for pair, rows in pairs.items():
        path = os.path.join(OUT, f"{pair}_D.csv")
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date", "close"])
            w.writerows([(d, f"{v:.6f}") for d, v in rows])
        print(f"saved {pair}: {len(rows)} rows -> {os.path.relpath(path, ROOT)}")
    cc = crosscheck(pairs)
    if cc:
        print(f"\nCROSS-CHECK EURUSD (ECB vs Yahoo): n={cc['n']} "
              f"mean abs diff={cc['mean_abs_pct']}%  max={cc['max_abs_pct']}%")
