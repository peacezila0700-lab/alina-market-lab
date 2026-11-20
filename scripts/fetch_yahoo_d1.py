"""Fetch D1 OHLC for EURGBP / EURUSD from Yahoo chart API -> data/processed/{SYM}_D1.csv
Also fetches ECB EUR/GBP daily reference rate for cross-check.
"""
import json, csv, os, hashlib, datetime as dt, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "processed")
os.makedirs(OUT, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0"}


def get(url, timeout=40):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8")


def yahoo(sym, rng="10y", iv="1d"):
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?range={rng}&interval={iv}"
    d = json.loads(get(url))
    r = d["chart"]["result"][0]
    ts = r["timestamp"]
    q = r["indicators"]["quote"][0]
    rows = []
    for i, t in enumerate(ts):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        v = q["volume"][i]
        if None in (o, h, l, c):
            continue
        rows.append([dt.datetime.fromtimestamp(t, dt.timezone.utc)
                     .strftime("%Y-%m-%d %H:%M:%S"), o, h, l, c, "" if v is None else v])
    return rows, r["meta"]


def main():
    manifest = {"created_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "datasets": []}
    for sym, name in [("EURGBP=X", "EURGBP"), ("EURUSD=X", "EURUSD")]:
        rows, meta = yahoo(sym)
        path = os.path.join(OUT, f"{name}_D1.csv")
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["ts_utc", "open", "high", "low", "close", "volume"])
            w.writerows(rows)
        sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
        manifest["datasets"].append({
            "id": f"{name}_D1", "symbol": sym,
            "source": "yahoo_chart_api", "interval": "1d",
            "rows": len(rows), "first": rows[0][0], "last": rows[-1][0],
            "server_timezone": meta.get("exchangeTimezoneName"),
            "gmtoffset": meta.get("gmtoffset"),
            "sha256": sha, "path": f"data/processed/{name}_D1.csv",
            "limitations": [
                "vendor-provided OHLC, no spread/volume for FX",
                "daily bar boundary timezone ambiguity (UTC vs exchange tz)",
                "not tick-verified against a primary feed (pending Dukascopy)",
            ]})
        print(f"{name}: {len(rows)} rows {rows[0][0][:10]} -> {rows[-1][0][:10]} sha={sha[:12]}")
        time.sleep(1)

    # ECB daily EUR/GBP reference (GBP per 1 EUR)
    try:
        url = ("https://data-api.ecb.europa.eu/service/data/EXR/D.GBP.EUR.SP00.A"
               "?format=csvdata&startPeriod=2016-01-01")
        txt = get(url, timeout=60)
        lines = list(csv.DictReader(txt.splitlines()))
        rows = sorted([[r["TIME_PERIOD"], r["OBS_VALUE"]] for r in lines])
        path = os.path.join(OUT, "ECB_EURGBP_D1.csv")
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date", "eur_gbp_reference"])
            w.writerows(rows)
        manifest["datasets"].append({
            "id": "ECB_EURGBP_D1", "symbol": "EUR/GBP (ECB reference)",
            "source": "ecb_sdw_csvdata", "rows": len(rows),
            "first": rows[0][0], "last": rows[-1][0],
            "sha256": hashlib.sha256(open(path, "rb").read()).hexdigest(),
            "path": "data/processed/ECB_EURGBP_D1.csv",
            "limitations": ["reference rate fixed ~14:15 CET, not a tradable close"]})
        print(f"ECB: {len(rows)} rows {rows[0][0]} -> {rows[-1][0]}")
    except Exception as e:
        print("ECB fetch failed:", e)

    with open(os.path.join(OUT, "MANIFEST.json"), "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print("manifest written")


if __name__ == "__main__":
    main()
