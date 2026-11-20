import json, urllib.request, time, numpy as np

def yh(sym, rng="730d", iv="1h"):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range={rng}&interval={iv}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    d = json.load(urllib.request.urlopen(req, timeout=30))
    r = d["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    c = np.array([np.nan if x is None else x for x in q["close"]], float)
    hi = np.array([np.nan if x is None else x for x in q["high"]], float)
    lo = np.array([np.nan if x is None else x for x in q["low"]], float)
    return np.array(r["timestamp"]), c, hi, lo

PIP = {"EURGBP=X":1e-4, "EURCHF=X":1e-4, "AUDNZD=X":1e-4, "EURUSD=X":1e-4}

print(f"{'sym':10} {'bars':>6} {'null':>5} {'ATR_H1(pips)':>13} {'MAE_halflife(h)':>16} {'ann_vol%':>9}")
for s in ["EURGBP=X", "EURCHF=X", "AUDNZD=X", "EURUSD=X"]:
    ts, c, hi, lo = yh(s)
    m = ~np.isnan(c)
    c, hi, lo = c[m], hi[m], lo[m]
    pip = PIP[s]
    tr = np.maximum(hi[1:]-lo[1:], np.maximum(abs(hi[1:]-c[:-1]), abs(lo[1:]-c[:-1])))
    atr = np.median(tr) / pip
    # mean reversion: deviation from 20-bar MA, AR(1) in hours
    w = 20
    ma = np.convolve(c, np.ones(w)/w, mode="valid")
    dev = c[w-1:]/ma - 1
    x, y = dev[:-1], dev[1:]
    beta = np.polyfit(x-x.mean(), y-y.mean(), 1)[0]
    hl = -np.log(2)/np.log(beta) if 0 < beta < 1 else np.nan
    r = np.diff(np.log(c))
    vol = r.std()*np.sqrt(24*260)*100
    print(f"{s:10} {len(c):>6} {int((~m).sum()):>5} {atr:>13.1f} {hl:>16.1f} {vol:>9.2f}")
    time.sleep(1)

print("\n=== official / alternative sources probe ===")
def probe(name, url, head=120):
    try:
        req = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=25) as r:
            body = r.read(head).decode("utf-8", "replace").replace("\n", " | ")
        print(f"[OK]   {name}: {body[:110]}")
    except Exception as e:
        print(f"[FAIL] {name}: {e}")

probe("ECB SDW EUR/GBP daily", "https://data-api.ecb.europa.eu/service/data/EXR/D.GBP.EUR.SP00.A?format=csvdata&lastNObservations=2")
time.sleep(1)
probe("FRED DEXUSUK csv", "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DEXUSUK")
time.sleep(1)
probe("Dukascopy tick EURGBP", "https://datafeed.dukascopy.com/datafeed/EURGBP/2025/00/02/00h_ticks.bi5")
time.sleep(2)
probe("Dukascopy instrument meta", "https://datafeed.dukascopy.com/datafeed/EURGBP/metadata.json")
