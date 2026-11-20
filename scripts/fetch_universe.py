"""Fetch a broad multi-asset universe from free Yahoo endpoints (full history).

No keys, no payment. Each instrument gets its own CSV + a manifest row with coverage,
because coverage differences decide which comparisons are even legal.
"""
import csv, json, os, time, datetime as dt, urllib.request, hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "universe")
os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0"}
P1 = 946684800          # 2000-01-01

UNIVERSE = {
    # FX / dollar
    "DXY": ("DX-Y.NYB", "fx"), "EURUSD": ("EURUSD=X", "fx"), "USDJPY": ("USDJPY=X", "fx"),
    "GBPUSD": ("GBPUSD=X", "fx"), "AUDUSD": ("AUDUSD=X", "fx"), "USDCAD": ("USDCAD=X", "fx"),
    # metals
    "GOLD": ("GC=F", "metal"), "SILVER": ("SI=F", "metal"), "COPPER": ("HG=F", "metal"),
    "PLATINUM": ("PL=F", "metal"),
    # energy
    "WTI": ("CL=F", "energy"), "NATGAS": ("NG=F", "energy"),
    # equity indices
    "SP500": ("^GSPC", "index"), "NASDAQ100": ("^NDX", "index"),
    "DAX": ("^GDAXI", "index"), "NIKKEI": ("^N225", "index"),
    "HSI": ("^HSI", "index"), "FTSE": ("^FTSE", "index"), "SET_TH": ("^SET.BK", "index"),
    # bonds / rates
    "TLT": ("TLT", "bond"), "IEF": ("IEF", "bond"),
    # crypto
    "BTC": ("BTC-USD", "crypto"), "ETH": ("ETH-USD", "crypto"),
    # ag
    "CORN": ("ZC=F", "ag"), "WHEAT": ("ZW=F", "ag"),
}

# cost per round trip as % of notional (documented assumption per class, NOT measured)
COST_PCT = {"fx": 0.015, "metal": 0.03, "energy": 0.06, "index": 0.02,
            "bond": 0.03, "crypto": 0.08, "ag": 0.10}


def fetch(sym, interval="1d"):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
           f"?period1={P1}&period2={int(time.time())}&interval={interval}")
    d = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=45).read())
    r = d["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    rows = []
    for i, t in enumerate(r["timestamp"]):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c) or c <= 0:
            continue
        rows.append((dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d"),
                     o, h, l, c))
    return rows


if __name__ == "__main__":
    manifest = []
    for name, (sym, klass) in UNIVERSE.items():
        try:
            rows = fetch(sym)
        except Exception as e:
            print(f"[FAIL] {name} ({sym}): {type(e).__name__}")
            time.sleep(1.5)
            continue
        if len(rows) < 250:
            print(f"[SKIP] {name}: only {len(rows)} bars")
            continue
        path = os.path.join(OUT, f"{name}.csv")
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date", "open", "high", "low", "close"])
            for r in rows:
                w.writerow([r[0], round(r[1], 6), round(r[2], 6), round(r[3], 6), round(r[4], 6)])
        manifest.append(dict(name=name, symbol=sym, klass=klass, rows=len(rows),
                             first=rows[0][0], last=rows[-1][0],
                             cost_pct=COST_PCT[klass],
                             sha256=hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]))
        print(f"[OK] {name:11} {klass:7} {len(rows):>6} bars  {rows[0][0]} -> {rows[-1][0]}")
        time.sleep(0.8)
    json.dump(manifest, open(os.path.join(OUT, "MANIFEST_UNIVERSE.json"), "w"), indent=2)
    print(f"\nsaved {len(manifest)} instruments")
