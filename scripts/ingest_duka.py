"""
Alina Market Lab — Dukascopy M1 candles -> H1 canonical bars (concurrent, resumable)

Source: https://datafeed.dukascopy.com/datafeed/{SYM}/{YYYY}/{MM0}/{DD}/{BID|ASK}_candles_min_1.bi5
Record: >5If (offset_sec uint32, open, close, low, high uint32 /1e5, volume float32)

Rules honoured:
- resumable (state file), append-only, ordered output
- weekend/holiday missing recorded as absent (never forward-filled)
- no raw .bi5 kept, H1 aggregated only
"""
import lzma, struct, os, sys, time, datetime as dt, http.client, ssl, threading
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "processed")
STATE = os.path.join(ROOT, "data", "state")
for d in (OUT, STATE):
    os.makedirs(d, exist_ok=True)

SCALE = 1e5
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)", "Accept": "*/*"}
HEADER = ("ts_utc,bid_open,bid_high,bid_low,bid_close,"
          "spread_mean_pips,spread_max_pips,minutes_obs\n")


_CTX = ssl.create_default_context()
_TL = threading.local()


def _conn():
    c = getattr(_TL, "c", None)
    if c is None:
        c = http.client.HTTPSConnection("datafeed.dukascopy.com", timeout=25, context=_CTX)
        _TL.c = c
    return c


def fetch(url, tries=4):
    """persistent connection per thread; url = path only"""
    for i in range(tries):
        try:
            c = _conn()
            c.request("GET", url, headers=UA)
            r = c.getresponse()
            body = r.read()
            if r.status == 200:
                return body
            if r.status == 404:
                return None
            time.sleep(0.4)
        except Exception:
            try:
                _TL.c.close()
            except Exception:
                pass
            _TL.c = None
            time.sleep(0.3 + 0.3 * i)
    return None


def decode(raw):
    if not raw:
        return []
    try:
        data = lzma.LZMADecompressor().decompress(raw)
    except Exception:
        return []
    rows = []
    for i in range(len(data) // 24):
        off, o, c, lo, hi, vol = struct.unpack(">5If", data[i * 24:(i + 1) * 24])
        rows.append((off, o / SCALE, c / SCALE, lo / SCALE, hi / SCALE, vol))
    return rows


def day_worker(sym, day):
    mm0 = day.month - 1
    base = f"/datafeed/{sym}/{day.year}/{mm0:02d}/{day.day:02d}"
    brows = decode(fetch(f"{base}/BID_candles_min_1.bi5"))
    arows = decode(fetch(f"{base}/ASK_candles_min_1.bi5"))
    if not brows:
        return day, []
    bid = {r[0]: (r[1], r[2], r[3], r[4]) for r in brows}
    ask = {r[0]: (r[1], r[2], r[3], r[4]) for r in arows}
    bars, sp = {}, {}
    for off in sorted(bid):
        h = off // 3600
        o, c, lo, hi = bid[off]
        if h not in bars:
            bars[h] = [o, o, lo, hi]
        rec = bars[h]
        rec[1], rec[2], rec[3] = c, min(rec[2], lo), max(rec[3], hi)
        if off in ask:
            sp.setdefault(h, []).append((ask[off][1] - c) * 1e4)
    out = []
    for h in sorted(bars):
        o, c, lo, hi = bars[h]
        s = sp.get(h, [])
        ts = dt.datetime(day.year, day.month, day.day, h, tzinfo=dt.timezone.utc)
        out.append((ts.strftime("%Y-%m-%d %H:%M:%S"), round(o, 6), round(hi, 6),
                    round(lo, 6), round(c, 6),
                    round(sum(s) / len(s), 3) if s else "",
                    round(max(s), 3) if s else "", len(s)))
    return day, out


def run(sym, start, end, workers=8):
    st_path = os.path.join(STATE, f"{sym}_last_done.txt")
    last = open(st_path).read().strip() if os.path.exists(st_path) else ""
    days = []
    d = start
    while d <= end:
        if d.weekday() != 5 and d.isoformat() > last:
            days.append(d)
        d += dt.timedelta(days=1)

    t0 = time.time()
    n_ok = n_miss = 0
    handlers = {}
    chunk = workers * 4

    def writer(day, rows):
        nonlocal n_ok, n_miss
        yr = day.year
        if yr not in handlers:
            path = os.path.join(OUT, f"{sym}_{yr}_H1.csv")
            new = not os.path.exists(path)
            handlers[yr] = open(path, "a", newline="")
            if new:
                handlers[yr].write(HEADER)
        if rows:
            for r in rows:
                handlers[yr].write(",".join(str(x) for x in r) + "\n")
            n_ok += 1
        else:
            n_miss += 1
        handlers[yr].flush()
        open(st_path, "w").write(day.isoformat())

    with ThreadPoolExecutor(max_workers=workers) as ex:
        for i in range(0, len(days), chunk):
            batch = days[i:i + chunk]
            results = list(ex.map(lambda dd: day_worker(sym, dd), batch))
            for day, rows in results:          # keep chronological order
                writer(day, rows)
            done = min(i + chunk, len(days))
            el = time.time() - t0
            rate = done / el if el else 0
            eta = (len(days) - done) / rate / 60 if rate else 0
            print(f"[{sym}] {done}/{len(days)} days | ok={n_ok} empty={n_miss} "
                  f"| {rate:.2f} day/s | ETA {eta:.1f} min", flush=True)
    for f in handlers.values():
        f.close()
    print(f"[{sym}] DONE ok={n_ok} empty={n_miss} in {(time.time()-t0)/60:.1f} min",
          flush=True)


if __name__ == "__main__":
    run(sys.argv[1], dt.date.fromisoformat(sys.argv[2]),
        dt.date.fromisoformat(sys.argv[3]),
        workers=int(sys.argv[4]) if len(sys.argv) > 4 else 8)
