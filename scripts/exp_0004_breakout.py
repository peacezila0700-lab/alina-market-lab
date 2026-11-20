"""EXP-0004 — H06 intraday breakout after volatility compression (rule frozen in docs/PREREG_H06.md)."""
import csv, os, json, collections, datetime as dt
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "data", "processed")
ART = os.path.join(ROOT, "research", "artifacts")
PIP = 1e-4

ATR_WIN, PCT_WIN, PCT_Q = 20, 500, 33
DON_WIN, MA_WIN = 20, 20
STOP_ATR = 1.5
ENTRY_CUTOFF, FLAT_HOUR = 19, 21
COST = 1.3

BLOCKS = {"IS": ("2024-02-05", "2025-12-31"),
          "VALIDATION": ("2026-01-01", "2026-05-31"),
          "OOS_LOCKED": ("2026-06-01", "2026-11-20")}


def load(sym):
    rows = list(csv.DictReader(open(os.path.join(P, f"{sym}_H1.csv"))))
    ts = [dt.datetime.strptime(r["ts_utc"], "%Y-%m-%d %H:%M:%S") for r in rows]
    o = np.array([float(r["open"]) for r in rows]); h = np.array([float(r["high"]) for r in rows])
    l = np.array([float(r["low"]) for r in rows]); c = np.array([float(r["close"]) for r in rows])
    return ts, o, h, l, c


def rm(x, w):
    out = np.full(len(x), np.nan)
    for i in range(w - 1, len(x)):
        out[i] = x[i - w + 1:i + 1].mean()
    return out


def roll_max(x, w):
    out = np.full(len(x), np.nan)
    for i in range(w, len(x)):
        out[i] = x[i - w:i].max()          # excludes bar i (level known before the bar)
    return out


def roll_min(x, w):
    out = np.full(len(x), np.nan)
    for i in range(w, len(x)):
        out[i] = x[i - w:i].min()
    return out


def run(ts, o, h, l, c):
    ma = rm(c, MA_WIN)
    tr = np.full(len(c), np.nan)
    tr[1:] = np.maximum(h[1:] - l[1:], np.maximum(abs(h[1:] - c[:-1]), abs(l[1:] - c[:-1])))
    atr = rm(tr, ATR_WIN)
    hi = roll_max(h, DON_WIN)
    lo = roll_min(l, DON_WIN)
    # compression: ATR at t <= 33rd pct of trailing PCT_WIN ATR values
    compress = np.zeros(len(c), bool)
    for i in range(PCT_WIN + ATR_WIN, len(c)):
        window = atr[i - PCT_WIN:i]
        window = window[~np.isnan(window)]
        if len(window) > 100 and not np.isnan(atr[i]):
            compress[i] = atr[i] <= np.percentile(window, PCT_Q)

    n, trades, i = len(c), [], PCT_WIN + ATR_WIN
    while i < n - 1:
        if (not compress[i] or np.isnan(hi[i]) or np.isnan(atr[i])
                or ts[i].hour >= ENTRY_CUTOFF):
            i += 1
            continue
        side = 1 if c[i] > hi[i] else (-1 if c[i] < lo[i] else 0)
        if side == 0:
            i += 1
            continue
        e = i + 1
        entry = o[e]
        stop = entry - side * STOP_ATR * atr[i]
        exit_i = exit_px = reason = None
        for j in range(e, n):
            # stop first (conservative)
            if (side == 1 and l[j] <= stop) or (side == -1 and h[j] >= stop):
                exit_i, exit_px, reason = j, stop, "stop_loss"
                break
            # MA20 cross against position
            if (side == 1 and c[j] < ma[j]) or (side == -1 and c[j] > ma[j]):
                exit_i = j + 1 if j + 1 < n else j
                exit_px = o[exit_i] if j + 1 < n else c[j]
                reason = "ma_cross"
                break
            if ts[j].hour == FLAT_HOUR:
                exit_i, exit_px, reason = j, c[j], "day_flat"
                break
        if exit_i is None:
            exit_i, exit_px, reason = n - 1, c[-1], "max_hold"
        gross = side * (exit_px - entry) / PIP
        trades.append(dict(side="long" if side == 1 else "short",
                           signal_ts=ts[i].strftime("%Y-%m-%d %H:%M"),
                           entry_ts=ts[e].strftime("%Y-%m-%d %H:%M"),
                           exit_ts=ts[exit_i].strftime("%Y-%m-%d %H:%M"),
                           bars=exit_i - e + 1, entry_px=round(entry, 5),
                           exit_px=round(exit_px, 5), reason=reason,
                           gross_pips=round(gross, 2), cost_pips=COST,
                           net_pips=round(gross - COST, 2),
                           overnight=int(ts[e].date() != ts[exit_i].date())))
        i = exit_i + 1
    return trades


def stats(net):
    net = np.asarray(net, float)
    if not len(net):
        return dict(n=0)
    w, l = net[net > 0].sum(), -net[net < 0].sum()
    eq = np.cumsum(net)
    return dict(n=int(len(net)), net_exp=round(float(net.mean()), 2),
                total=round(float(net.sum()), 1),
                pf=round(float(w / l), 2) if l > 0 else float("inf"),
                win=round(float((net > 0).mean() * 100), 1),
                maxdd=round(float(np.max(np.maximum.accumulate(eq) - eq)), 1))


def cluster_ci(trades, iters=5000, seed=31):
    by_day = collections.defaultdict(list)
    for t in trades:
        by_day[t["entry_ts"][:10]].append(t["net_pips"])
    keys = list(by_day)
    if len(keys) < 8:
        return None, None
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(iters):
        pick = rng.choice(len(keys), size=len(keys), replace=True)
        means.append(np.concatenate([by_day[keys[i]] for i in pick]).mean())
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


if __name__ == "__main__":
    out, all_tr = {}, {}
    for sym in ["EURGBP", "EURUSD"]:
        ts, o, h, l, c = load(sym)
        tr = run(ts, o, h, l, c)
        for t in tr:
            t["symbol"] = sym
        all_tr[sym] = tr
        res = {}
        for b, (a0, b0) in BLOCKS.items():
            sub = [t for t in tr if a0 <= t["entry_ts"][:10] <= b0]
            s = stats([t["net_pips"] for t in sub])
            lo, hi = cluster_ci(sub)
            s["ci_lo"] = None if lo is None else round(lo, 2)
            s["ci_hi"] = None if hi is None else round(hi, 2)
            s["reasons"] = dict(collections.Counter(t["reason"] for t in sub))
            s["sides"] = dict(collections.Counter(t["side"] for t in sub))
            res[b] = s
        out[sym] = res
        print(f"\n{sym}: trades={len(tr)}")
        for b, s in res.items():
            print(f"  {b:11} n={s.get('n',0):>4} exp={s.get('net_exp')} pf={s.get('pf')} "
                  f"win={s.get('win')} ci=[{s.get('ci_lo')},{s.get('ci_hi')}] {s.get('reasons')}")

    # random benchmark matching validation trade count
    ts, o, h, l, c = load("EURGBP")
    nv = max(1, len([t for t in all_tr["EURGBP"]
                     if BLOCKS["VALIDATION"][0] <= t["entry_ts"][:10] <= BLOCKS["VALIDATION"][1]]))
    rng = np.random.default_rng(37)
    ok = [i for i in range(600, len(c) - 10) if ts[i].hour < ENTRY_CUTOFF]
    sims = []
    for _ in range(2000):
        vals = []
        for i in rng.choice(ok, size=nv, replace=False):
            side = rng.choice([-1, 1])
            vals.append(side * (c[min(i + 6, len(c) - 1)] - o[i + 1]) / PIP - COST)
        sims.append(float(np.mean(vals)))
    sims = np.array(sims)
    out["_random_benchmark"] = dict(n_trades=nv, sims=int(len(sims)),
                                    mean=round(float(sims.mean()), 2),
                                    p5=round(float(np.percentile(sims, 5)), 2),
                                    p95=round(float(np.percentile(sims, 95)), 2))
    print("\nrandom benchmark:", out["_random_benchmark"])

    cols = ["symbol", "side", "signal_ts", "entry_ts", "exit_ts", "bars", "entry_px",
            "exit_px", "reason", "gross_pips", "cost_pips", "net_pips", "overnight"]
    with open(os.path.join(ART, "EXP-0004_trades.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for sym in ["EURGBP", "EURUSD"]:
            w.writerows(sorted(all_tr[sym], key=lambda t: t["entry_ts"]))
    json.dump(out, open(os.path.join(ART, "EXP-0004_summary.json"), "w"), indent=2)
    print("\nwrote research/artifacts/EXP-0004_*")
