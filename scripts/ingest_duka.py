"""
Alina Market Lab — Dukascopy M1 candles -> H1 canonical bars

FIX (2026-11-20, after incident QR-001):
  v1 treated HTTP 429 (rate limit) as "day has no data" and advanced the state file
  => 48 days were marked done with ZERO rows. That is exactly the kind of silent
  data loss PROJECT_RULES forbids. This version:
    * returns an explicit status per fetch: OK / MISSING(404) / RATE_LIMITED / ERROR
    * global token-bucket rate limiter (default 0.8 req/s) respected across threads
    * on RATE_LIMITED: back off long, and NEVER advance the state past that day
    * output row is only written when bars were actually decoded
    * state file = last day fully written in chronological order

Record format: >5If (offset_sec uint32, open, close, low, high uint32 /1e5, volume f32)
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

RATE = float(os.environ.get("DUKA_RPS", "0.8"))     # requests per second (global)
_lock = threading.Lock()
_next_slot = [0.0]


def _throttle():
    with _lock:
        now = time.time()
        slot = max(now, _next_slot[0])
        _next_slot[0] = slot + 1.0 / RATE
        wait = slot - now
    if wait > 0:
        time.sleep(wait)


_CTX = ssl.create_default_context()
_TL = threading.local()


def _conn():
    c = getattr(_TL, "c", None)
    if c is None:
        c = http.client.HTTPSConnection("datafeed.dukascopy.com", timeout=30, context=_CTX)
        _TL.c = c
    return c


def fetch(path):
    """-> (status, bytes|None)"""
    for attempt in range(3):
        _throttle()
        try:
            c = _conn()
            c.request("GET", path, headers=UA)
            r = c.getresponse()
            body = r.read()
            if r.status == 200:
                return "OK", body
            if r.status == 404:
                return "MISSING", None
            if r.status == 429:
                return "RATE_LIMITED", None
            time.sleep(1.5 * (attempt + 1))
        except Exception:
            try:
                _TL.c.close()
            except Exception:
                pass
            _TL.c = None
            time.sleep(1.0 * (attempt + 1))
    return "ERROR", None


def decode(raw):
    if not raw:
        return []
    try:
        data = lzma.LZMADecompressor().decompress(raw)
    except Exception:
        return []
    out = []
    for i in range(len(data) // 24):
        off, o, c, lo, hi, vol = struct.unpack(">5If", data[i * 24:(i + 1) * 24])
        out.append((off, o / SCALE, c / SCALE, lo / SCALE, hi / SCALE, vol))
    return out


def day_worker(sym, day):
    mm0 = day.month - 1
    base = f"/datafeed/{sym}/{day.year}/{mm0:02d}/{day.day:02d}"
    s1, braw = fetch(f"{base}/BID_candles_min_1.bi5")
    s2, araw = fetch(f"{base}/ASK_candles_min_1.bi5")
    if "RATE_LIMITED" in (s1, s2):
        return day, None, "RATE_LIMITED"
    if "ERROR" in (s1, s2):
        return day, None, "ERROR"
    brows, arows = decode(braw), decode(araw)
    if not brows:
        return day, [], "MISSING"
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
    rows = []
    for h in sorted(bars):
        o, c, lo, hi = bars[h]
        s = sp.get(h, [])
        ts = dt.datetime(day.year, day.month, day.day, h, tzinfo=dt.timezone.utc)
        rows.append((ts.strftime("%Y-%m-%d %H:%M:%S"), round(o, 6), round(hi, 6),
                     round(lo, 6), round(c, 6),
                     round(sum(s) / len(s), 3) if s else "",
                     round(max(s), 3) if s else "", len(s)))
    return day, rows, "OK"


def run(sym, start, end, workers=6):
    st = os.path.join(STATE, f"{sym}_last_done.txt")
    last = open(st).read().strip() if os.path.exists(st) else ""
    days, d = [], start
    while d <= end:
        if d.weekday() != 5 and d.isoformat() > last:
            days.append(d)
        d += dt.timedelta(days=1)

    handlers, n_ok, n_miss, t0 = {}, 0, 0, time.time()
    wrote_upto = last

    def flush(day, rows, status):
        nonlocal n_ok, n_miss, wrote_upto
        if status == "OK":
            yr = day.year
            if yr not in handlers:
                path = os.path.join(OUT, f"{sym}_{yr}_H1.csv")
                new = not os.path.exists(path)
                handlers[yr] = open(path, "a", newline="")
                if new:
                    handlers[yr].write(HEADER)
            for r in rows:
                handlers[yr].write(",".join(str(x) for x in r) + "\n")
            handlers[yr].flush()
            n_ok += 1
            wrote_upto = day.isoformat()
            open(st, "w").write(wrote_upto)
        elif status == "MISSING":
            n_miss += 1
            wrote_upto = day.isoformat()
            open(st, "w").write(wrote_upto)
        else:                       # RATE_LIMITED / ERROR -> do NOT advance state
            raise RuntimeError(f"{sym} {day} -> {status}; state kept at {wrote_upto}")

    chunk = workers * 2
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for i in range(0, len(days), chunk):
            batch = days[i:i + chunk]
            results = list(ex.map(lambda dd: day_worker(sym, dd), batch))
            for day, rows, status in results:
                if status in ("RATE_LIMITED", "ERROR"):
                    for f in handlers.values():
                        f.close()
                    print(f"[{sym}] STOPPED at {day} ({status}). "
                          f"state={wrote_upto}. resume later.", flush=True)
                    return False
                flush(day, rows, status)
            done = min(i + chunk, len(days))
            el = time.time() - t0
            print(f"[{sym}] {done}/{len(days)} ok={n_ok} missing={n_miss} "
                  f"| {done/el:.2f} day/s | ETA {(len(days)-done)/(done/el)/60:.1f} min",
                  flush=True)
    for f in handlers.values():
        f.close()
    print(f"[{sym}] DONE ok={n_ok} missing={n_miss} in {(time.time()-t0)/60:.1f} min", flush=True)
    return True


if __name__ == "__main__":
    ok = run(sys.argv[1], dt.date.fromisoformat(sys.argv[2]),
             dt.date.fromisoformat(sys.argv[3]),
             workers=int(sys.argv[4]) if len(sys.argv) > 4 else 6)
    sys.exit(0 if ok else 2)
