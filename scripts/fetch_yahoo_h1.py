"""Fetch H1 history (Yahoo, 730d limit) for the intraday experiment + QC.

This is a NEW sample: no H1 price series has been used for any test in this project yet
(H1 was only used earlier for ATR/spread sizing arithmetic).

QC is printed and written to reports/QC_H1.md. Known vendor limits are recorded, not hidden:
  * 730-day history ceiling
  * no spread column (cost must be assumed -> documented)
  * null bars observed in the daily series as well
"""
import csv, json, os, time, datetime as dt, urllib.request, hashlib
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "data", "processed")
REP = os.path.join(ROOT, "reports")
os.makedirs(P, exist_ok=True); os.makedirs(REP, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0"}
PAIRS = ["EURGBP", "EURUSD"]


def grab(sym):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}=X"
           f"?range=730d&interval=1h")
    d = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=45).read())
    r = d["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    rows = []
    for i, t in enumerate(r["timestamp"]):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        rows.append((t, o, h, l, c))
    return rows


def build(sym):
    raw = grab(sym)
    kept, nulls, occ, weekend = [], 0, 0, 0
    for t, o, h, l, c in raw:
        if None in (o, h, l, c):
            nulls += 1
            continue
        ts = dt.datetime.fromtimestamp(t, dt.timezone.utc)
        if ts.weekday() == 5:
            weekend += 1
            continue
        if abs(o - c) < 1e-12:
            occ += 1
        kept.append((ts, o, h, l, c))
    kept.sort(key=lambda x: x[0])
    path = os.path.join(P, f"{sym}_H1.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["ts_utc", "open", "high", "low", "close"])
        for ts, o, h, l, c in kept:
            w.writerow([ts.strftime("%Y-%m-%d %H:%M:%S"), round(o, 6), round(h, 6),
                        round(l, 6), round(c, 6)])
    gaps = np.diff([ts.timestamp() for ts, *_ in kept]) / 60
    sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
    return dict(symbol=sym, raw=len(raw), kept=len(kept), nulls=nulls,
                saturday=weekend, open_eq_close=occ, occ_pct=round(occ / len(kept) * 100, 1),
                first=str(kept[0][0]), last=str(kept[-1][0]),
                median_step_min=float(np.median(gaps)),
                gaps_gt_3x=int((gaps > 3 * np.median(gaps)).sum()),
                sha256=sha), kept


if __name__ == "__main__":
    out = ["# QC — H1 (Yahoo, 730d)", "",
           f"Generated: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}", "",
           "| check | EURGBP | EURUSD |", "|---|---|---|"]
    stats = []
    for sym in PAIRS:
        s, _ = build(sym)
        stats.append(s)
        print(f"{sym}: kept={s['kept']} nulls={s['nulls']} open==close={s['occ_pct']}% "
              f"median_step={s['median_step_min']:.0f}min gaps>3x={s['gaps_gt_3x']}")
        time.sleep(1)
    a, b = stats
    rows = [("raw bars", "raw", "raw"), ("kept bars", "kept", "kept"),
            ("null bars dropped", "nulls", "nulls"),
            ("Saturday bars dropped", "saturday", "saturday"),
            ("open == close", "occ_pct", "occ_pct"),
            ("first", "first", "first"), ("last", "last", "last"),
            ("median step (min)", "median_step_min", "median_step_min"),
            ("gaps > 3x median", "gaps_gt_3x", "gaps_gt_3x"),
            ("sha256", "sha256", "sha256")]
    for label, ka, kb in rows:
        va, vb = a[ka], b[kb]
        if ka == "sha256":
            va, vb = va[:16], vb[:16]
        out.append(f"| {label} | {va} | {vb} |")
    out += ["", "> **Limitation that matters:** Yahoo H1 carries no spread. Every cost figure in",
            "> the intraday experiment is therefore an assumption (1.3 pips), not a measurement.",
            "> A broker MT5 export would replace it with the real thing."]
    open(os.path.join(REP, "QC_H1.md"), "w").write("\n".join(out))
    json.dump(stats, open(os.path.join(P, "MANIFEST_H1.json"), "w"), indent=2)
    print("wrote reports/QC_H1.md + MANIFEST_H1.json")
