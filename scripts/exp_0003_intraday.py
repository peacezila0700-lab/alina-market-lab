"""EXP-0003 — H05 intraday fade, no overnight position (swap = 0 by construction).

Rule is frozen in docs/PREREG_H05.md (committed before this file was run).
Splits, rejection criteria and limitations were declared in advance.
"""
import csv, os, sys, json, collections, datetime as dt
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "data", "processed")
ART = os.path.join(ROOT, "research", "artifacts")
os.makedirs(ART, exist_ok=True)
PIP = 1e-4

# ---- frozen parameters (PREREG_H05) ----
MA_WIN = 20
SD_WIN = 252
Z_ENTRY = 2.0
ATR_WIN = 20
STOP_ATR = 3.0
ENTRY_CUTOFF_HOUR = 19       # no entries at/after 19:00 UTC
FLAT_HOUR = 21               # forced exit at the 21:00 bar close -> no overnight, no swap
MAX_HOLD = 23
COST = 1.3                   # pips per round trip (spread 0.9 + 2 x 0.2 slippage)

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


def rstd(x, w):
    out = np.full(len(x), np.nan)
    for i in range(w - 1, len(x)):
        out[i] = x[i - w + 1:i + 1].std(ddof=1)
    return out


def run(ts, o, h, l, c):
    ma = rm(c, MA_WIN)
    dev = c - ma
    z = dev / rstd(dev, SD_WIN)
    tr = np.full(len(c), np.nan)
    tr[1:] = np.maximum(h[1:] - l[1:], np.maximum(abs(h[1:] - c[:-1]), abs(l[1:] - c[:-1])))
    atr = rm(tr, ATR_WIN)
    n = len(c)
    trades, i = [], max(SD_WIN, ATR_WIN, MA_WIN)
    while i < n - 1:
        if (np.isnan(z[i]) or np.isnan(atr[i]) or z[i] < Z_ENTRY
                or ts[i].hour >= ENTRY_CUTOFF_HOUR):
            i += 1
            continue
        e_i = i + 1
        entry = o[e_i]
        stop = entry + STOP_ATR * atr[i]
        exit_i, exit_px, reason = None, None, None
        for j in range(e_i, min(e_i + MAX_HOLD, n)):
            if h[j] >= stop:
                exit_i, exit_px, reason = j, stop, "stop_loss"
                break
            if c[j] < ma[j]:
                exit_i = j + 1 if j + 1 < n else j
                exit_px = o[exit_i] if j + 1 < n else c[j]
                reason = "ma_cross"
                break
            if ts[j].hour == FLAT_HOUR:                 # forced flat, same day
                exit_i, exit_px, reason = j, c[j], "day_flat"
                break
        if exit_i is None:
            exit_i = min(e_i + MAX_HOLD, n - 1)
            exit_px, reason = c[exit_i], "max_hold"
        gross = (entry - exit_px) / PIP
        trades.append(dict(signal_ts=ts[i].strftime("%Y-%m-%d %H:%M"),
                           entry_ts=ts[e_i].strftime("%Y-%m-%d %H:%M"),
                           exit_ts=ts[exit_i].strftime("%Y-%m-%d %H:%M"),
                           bars=exit_i - e_i + 1, entry_px=round(entry, 5),
                           exit_px=round(exit_px, 5), reason=reason,
                           gross_pips=round(gross, 2), cost_pips=COST,
                           net_pips=round(gross - COST, 2),
                           overnight=int(ts[e_i].date() != ts[exit_i].date())))
        i = exit_i + 1
    return trades


def stats(net):
    net = np.asarray(net, float)
    if not len(net):
        return dict(n=0)
    w, l = net[net > 0].sum(), -net[net < 0].sum()
    eq = np.cumsum(net)
    dd = float(np.max(np.maximum.accumulate(eq) - eq))
    return dict(n=int(len(net)), net_exp=round(float(net.mean()), 2),
                total=round(float(net.sum()), 1),
                pf=round(float(w / l), 2) if l > 0 else float("inf"),
                win=round(float((net > 0).mean() * 100), 1),
                maxdd=round(dd, 1), sd=round(float(net.std(ddof=1)), 1) if len(net) > 1 else None)


def cluster_ci(trades, iters=5000, seed=17):
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
        vals = np.concatenate([by_day[keys[i]] for i in pick])
        means.append(vals.mean())
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def random_benchmark(ts, o, c, n_trades, sims=2000, seed=29):
    """same count, same intraday hold, same cost, random entries inside 00-18 UTC"""
    rng = np.random.default_rng(seed)
    ok = [i for i in range(SD_WIN, len(c) - MAX_HOLD - 1) if ts[i].hour < ENTRY_CUTOFF_HOUR]
    out = []
    for _ in range(sims):
        vals = []
        for i in rng.choice(ok, size=n_trades, replace=False):
            e = o[i + 1]
            x = c[min(i + 1 + 5, len(c) - 1)]     # ~same median hold as the rule
            vals.append((e - x) / PIP - COST)
        out.append(float(np.mean(vals)))
    return np.array(out)


if __name__ == "__main__":
    result = {}
    all_tr = {}
    for sym in ["EURGBP", "EURUSD"]:
        ts, o, h, l, c = load(sym)
        tr = run(ts, o, h, l, c)
        for t in tr:
            t["symbol"] = sym
        all_tr[sym] = (ts, o, c, tr)
        res = {}
        for b, (a0, b0) in BLOCKS.items():
            sub = [t for t in tr if a0 <= t["entry_ts"][:10] <= b0]
            s = stats([t["net_pips"] for t in sub])
            lo, hi = cluster_ci(sub)
            s["ci_lo"] = None if lo is None else round(lo, 2)
            s["ci_hi"] = None if hi is None else round(hi, 2)
            s["reasons"] = dict(collections.Counter(t["reason"] for t in sub))
            s["overnight_trades"] = int(sum(t["overnight"] for t in sub))
            s["avg_bars"] = round(float(np.mean([t["bars"] for t in sub])), 1) if sub else None
            res[b] = s
        result[sym] = res
        print(f"\n{sym}: total trades={len(tr)}")
        for b, s in res.items():
            print(f"  {b:11} n={s.get('n',0):>4} exp={s.get('net_exp')} "
                  f"pf={s.get('pf')} win={s.get('win')} ci=[{s.get('ci_lo')},{s.get('ci_hi')}] "
                  f"reasons={s.get('reasons')}")

    # random benchmark for EURGBP validation-size sample
    ts, o, c, tr = all_tr["EURGBP"]
    nv = max(1, len([t for t in tr if BLOCKS["VALIDATION"][0] <= t["entry_ts"][:10]
                     <= BLOCKS["VALIDATION"][1]]))
    rb = random_benchmark(ts, o, c, nv)
    result["_random_benchmark"] = dict(n_trades=nv, sims=int(len(rb)),
                                       mean=round(float(rb.mean()), 2),
                                       p5=round(float(np.percentile(rb, 5)), 2),
                                       p95=round(float(np.percentile(rb, 95)), 2))
    print("\nrandom benchmark:", result["_random_benchmark"])

    cols = ["symbol", "signal_ts", "entry_ts", "exit_ts", "bars", "entry_px", "exit_px",
            "reason", "gross_pips", "cost_pips", "net_pips", "overnight"]
    with open(os.path.join(ART, "EXP-0003_trades.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for sym in ["EURGBP", "EURUSD"]:
            w.writerows(all_tr[sym][3])
    json.dump(result, open(os.path.join(ART, "EXP-0003_summary.json"), "w"), indent=2)
    print("\nwrote research/artifacts/EXP-0003_*")
