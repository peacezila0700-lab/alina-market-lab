"""Fetch full available daily history (period1=2000-01-01 -> now) for the basket,
then apply the SAME cleaning rules as the canonical pipeline (R1-R4).

Outputs:
  data/processed/{SYM}_D1_full.csv        raw vendor rows
  data/processed/{SYM}_D1_fullclean.csv   canonical rows used by EXP-0002
  data/processed/CLEANING_LOG_FULL.csv    every repair, traceable
"""
import csv, json, os, time, datetime as dt, urllib.request, hashlib

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "data", "processed")
os.makedirs(P, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0"}
BASKET = ["EURGBP", "EURCHF", "AUDNZD", "CADCHF", "EURUSD"]
P1 = 946684800          # 2000-01-01 UTC
log = [["symbol", "date", "rule", "detail"]]


def yahoo(sym, interval="1d"):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}=X"
           f"?period1={P1}&period2={int(time.time())}&interval={interval}")
    d = json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=45).read())
    r = d["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    rows = []
    for i, t in enumerate(r["timestamp"]):
        o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
        if None in (o, h, l, c):
            continue
        rows.append([dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
                     o, h, l, c])
    return rows


def clean(sym, rows):
    have_fri = {dt.date.fromisoformat(r[0][:10]) for r in rows
                if dt.date.fromisoformat(r[0][:10]).weekday() == 4}
    kept, relab, dup, clamp = [], 0, 0, 0
    for r in rows:
        date = dt.date.fromisoformat(r[0][:10])
        o, h, l, c = (float(r[1]), float(r[2]), float(r[3]), float(r[4]))
        if date.weekday() == 6:                       # R1
            fri = date - dt.timedelta(days=2)
            if fri in have_fri:
                dup += 1
                log.append([sym, str(date), "R1_drop_duplicate_sunday", f"close={c:.5f}"])
                continue
            date = fri
            relab += 1
            log.append([sym, str(date), "R1_relabel_sunday_to_friday", f"close={c:.5f}"])
        elif date.weekday() == 5:
            log.append([sym, str(date), "R0_drop_saturday", f"close={c:.5f}"])
            continue
        hi2, lo2 = max(h, o, c), min(l, o, c)
        if (hi2, lo2) != (h, l):                      # R2
            clamp += 1
            log.append([sym, str(date), "R2_clamp_ohlc",
                        f"high {h:.5f}->{hi2:.5f} low {l:.5f}->{lo2:.5f}"])
            h, l = hi2, lo2
        kept.append([f"{date.isoformat()} 00:00:00", round(o, 6), round(h, 6),
                     round(l, 6), round(c, 6)])
    kept.sort(key=lambda x: x[0])
    out, spikes = [], 0
    for i, row in enumerate(kept):                    # R3
        if 0 < i < len(kept) - 1:
            c0, c1, c2 = float(kept[i - 1][4]), float(row[4]), float(kept[i + 1][4])
            if abs(c1 / c0 - 1) > 0.05 and abs(c1 / c2 - 1) > 0.05 and abs(c2 / c0 - 1) < 0.01:
                spikes += 1
                log.append([sym, row[0][:10], "R3_drop_isolated_spike",
                            f"close={c1:.5f} between {c0:.5f} and {c2:.5f}"])
                continue
        out.append(row)
    return out, dict(relabeled=relab, dup_sunday=dup, clamped=clamp, spikes=spikes)


if __name__ == "__main__":
    summary = []
    for sym in BASKET:
        rows = yahoo(sym)
        raw = os.path.join(P, f"{sym}_D1_full.csv")
        with open(raw, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["ts_utc", "open", "high", "low", "close"])
            w.writerows(rows)
        kept, info = clean(sym, rows)
        out = os.path.join(P, f"{sym}_D1_fullclean.csv")
        with open(out, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["ts_utc", "open", "high", "low", "close"])
            w.writerows(kept)
        sha = hashlib.sha256(open(out, "rb").read()).hexdigest()
        summary.append(dict(symbol=sym, raw=len(rows), clean=len(kept),
                            first=kept[0][0][:10], last=kept[-1][0][:10],
                            sha256=sha[:16], **info))
        print(f"{sym}: raw={len(rows):>5} clean={len(kept):>5} "
              f"{kept[0][0][:10]} -> {kept[-1][0][:10]} {info}")
        time.sleep(1)

    with open(os.path.join(P, "CLEANING_LOG_FULL.csv"), "w", newline="") as f:
        csv.writer(f).writerows(log)
    json.dump(summary, open(os.path.join(P, "MANIFEST_FULL.json"), "w"), indent=2)
    print("cleaning log rows:", len(log) - 1)
