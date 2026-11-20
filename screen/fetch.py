import json, urllib.request, time, os

SYMS = ["EURUSD=X","EURGBP=X","EURCHF=X","AUDNZD=X","GBPUSD=X","USDJPY=X",
        "AUDCAD=X","NZDCAD=X","CADCHF=X","GC=F","SI=F"]
os.makedirs("screen/raw", exist_ok=True)

def grab(sym, rng, iv, out):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range={rng}&interval={iv}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        d = json.load(urllib.request.urlopen(req, timeout=30))
        r = d["chart"]["result"][0]
        json.dump({"sym": sym, "iv": iv, "ts": r["timestamp"], "q": r["indicators"]["quote"][0]},
                  open(out, "w"))
        return len(r["timestamp"])
    except Exception as e:
        return f"ERR {e}"

for s in SYMS:
    f = f"screen/raw/{s.replace('=','_')}_d.json"
    n = grab(s, "10y", "1d", f)
    print(f"{s:10} daily10y -> {n}", flush=True)
    time.sleep(1)
