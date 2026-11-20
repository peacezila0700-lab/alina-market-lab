"""EXP-0001 backtest engine — H01 rule (frozen), single instrument, single position.

DESIGN RULES (per PROJECT_RULES + docs/HYPOTHESIS_NOTES.md)
  * signal computed only from bars <= t (rolling windows are trailing)
  * fill happens on the NEXT bar's open after the signal bar
  * stop-loss is checked against the next bars' high/low, filled at the stop level
    (conservative: stop is honoured even on gap, at the stop price)
  * exit on MA cross and time stop are executed on the next open
  * all P&L in pips, fixed 1 unit, costs subtracted once per round trip
  * no parameter search: threshold/horizon/stop are the pre-registered values

Cost model (explicit, reported alongside every result):
  spread        : 0.9 pip round trip   (Dukascopy median, measured 2026-11-20)
  slippage      : 0.2 pip per side
  swap/financing: parametrised, default 0.0 pip/night; 0.3 used as a bound
"""
import csv, os, json, datetime as dt
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PIP = 1e-4

# ---- pre-registered parameters (DO NOT TUNE) ----
MA_WIN = 50
SIG_WIN = 252
Z_ENTRY = 2.0
MAX_HOLD = 20
ATR_WIN = 20
STOP_ATR = 3.0
SPREAD = 0.9
SLIP = 0.2
SWAP = 0.0

BLOCKS = {
    "IS":         ("2016-11-21", "2023-12-31"),
    "VALIDATION": ("2024-01-01", "2025-05-31"),
    "OOS_LOCKED": ("2025-06-01", "2026-11-20"),
}


def load(sym="EURGBP"):
    rows = list(csv.DictReader(open(os.path.join(ROOT, "data", "processed", f"{sym}_D1_clean.csv"))))
    d = [dt.date.fromisoformat(r["ts_utc"][:10]) for r in rows]
    o = np.array([float(r["open"]) for r in rows])
    h = np.array([float(r["high"]) for r in rows])
    l = np.array([float(r["low"]) for r in rows])
    c = np.array([float(r["close"]) for r in rows])
    return d, o, h, l, c


def rolling_mean(x, w):
    out = np.full(len(x), np.nan)
    for i in range(w - 1, len(x)):
        out[i] = x[i - w + 1:i + 1].mean()
    return out


def rolling_std(x, w):
    out = np.full(len(x), np.nan)
    for i in range(w - 1, len(x)):
        out[i] = x[i - w + 1:i + 1].std(ddof=1)
    return out


def atr(h, l, c, w=ATR_WIN):
    tr = np.full(len(c), np.nan)
    tr[1:] = np.maximum(h[1:] - l[1:], np.maximum(abs(h[1:] - c[:-1]), abs(l[1:] - c[:-1])))
    return rolling_mean(tr, w)


def build_signals(d, o, h, l, c):
    ma = rolling_mean(c, MA_WIN)
    dev = c - ma
    sd = rolling_std(dev, SIG_WIN)
    z = dev / sd
    return ma, z, atr(h, l, c)


def run_strategy(d, o, h, l, c, z, ma, a, spread=SPREAD, slip=SLIP, swap=SWAP,
                 z_entry=Z_ENTRY, max_hold=MAX_HOLD, stop_atr=STOP_ATR):
    """Returns list of trade dicts. Short-only (H01). One position at a time."""
    trades = []
    i = max(MA_WIN, SIG_WIN, ATR_WIN)          # first bar where all inputs exist
    n = len(c)
    while i < n - 1:
        if np.isnan(z[i]) or np.isnan(a[i]) or z[i] < z_entry:
            i += 1
            continue
        entry_i = i + 1                         # fill on next bar
        entry_px = o[entry_i]
        stop_px = entry_px + stop_atr * a[i]
        exit_i, exit_px, reason = None, None, None
        for j in range(entry_i, min(entry_i + max_hold, n)):
            if h[j] >= stop_px:                 # stop hit (checked before the close exit)
                exit_i, exit_px, reason = j, stop_px, "stop_loss"
                break
            if c[j] < ma[j]:                    # reverted to the mean -> exit next open
                exit_i = j + 1 if j + 1 < n else j
                exit_px = o[exit_i] if j + 1 < n else c[j]
                reason = "ma_cross"
                break
        if exit_i is None:
            exit_i = min(entry_i + max_hold, n - 1)
            exit_px, reason = o[exit_i], "time_stop"
        gross = (entry_px - exit_px) / PIP       # short
        nights = (d[exit_i] - d[entry_i]).days
        cost = spread + 2 * slip + swap * nights
        trades.append({
            "signal_date": d[i].isoformat(), "entry_date": d[entry_i].isoformat(),
            "exit_date": d[exit_i].isoformat(), "bars_held": exit_i - entry_i + 1,
            "entry_px": round(entry_px, 5), "exit_px": round(exit_px, 5),
            "stop_px": round(stop_px, 5), "reason": reason,
            "gross_pips": round(gross, 2), "cost_pips": round(cost, 2),
            "net_pips": round(gross - cost, 2)})
        i = exit_i + 1                          # no overlapping positions
    return trades


def metrics(trades, total_days):
    if not trades:
        return dict(n=0, net_exp=np.nan, pf=np.nan, maxdd=np.nan, win=np.nan,
                    avg_hold=np.nan, cost=np.nan, exposure=np.nan, gross_exp=np.nan,
                    ci_lo=np.nan, ci_hi=np.nan)
    net = np.array([t["net_pips"] for t in trades])
    gross = np.array([t["gross_pips"] for t in trades])
    eq = np.cumsum(net)
    dd = float(np.max(np.maximum.accumulate(eq) - eq)) if len(eq) else np.nan
    w, l = net[net > 0].sum(), -net[net < 0].sum()
    lo, hi = block_bootstrap_ci(net)
    return dict(n=len(trades), net_exp=round(float(net.mean()), 2),
                gross_exp=round(float(gross.mean()), 2),
                pf=round(float(w / l), 2) if l > 0 else np.inf,
                maxdd=round(dd, 1), win=round(float((net > 0).mean() * 100), 1),
                avg_hold=round(float(np.mean([t["bars_held"] for t in trades])), 1),
                cost=round(float(np.mean([t["cost_pips"] for t in trades])), 2),
                exposure=round(float(sum(t["bars_held"] for t in trades) / total_days * 100), 1),
                ci_lo=round(lo, 2), ci_hi=round(hi, 2), total=round(float(net.sum()), 1))


def block_bootstrap_ci(net, block=4, iters=5000, seed=7):
    rng = np.random.default_rng(seed)
    n = len(net)
    if n < 3:
        return np.nan, np.nan
    nb = max(1, n // block)
    means = []
    for _ in range(iters):
        starts = rng.integers(0, n, nb)
        samp = np.concatenate([net[s:s + block] for s in starts if s + block <= n] or [net])
        means.append(samp.mean())
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def random_benchmark(d, o, h, l, c, ma, n_trades, max_hold, n_sims=2000, seed=11):
    rng = np.random.default_rng(seed)
    lo = max(MA_WIN, SIG_WIN, ATR_WIN)
    valid = np.arange(lo, len(c) - max_hold - 1)
    out = []
    for _ in range(n_sims):
        picks = rng.choice(valid, size=n_trades, replace=False)
        nets = []
        for p in picks:
            e = o[p + 1]
            x = o[min(p + 1 + max_hold, len(c) - 1)]
            nets.append((e - x) / PIP - (SPREAD + 2 * SLIP))
        out.append(float(np.mean(nets)))
    return np.array(out)


def split_trades(trades):
    res = {}
    for name, (a, b) in BLOCKS.items():
        res[name] = [t for t in trades if a <= t["entry_date"] <= b]
    return res


if __name__ == "__main__":
    d, o, h, l, c = load("EURGBP")
    ma, z, a = build_signals(d, o, h, l, c)
    trades = run_strategy(d, o, h, l, c, z, ma, a)
    sp = split_trades(trades)
    os.makedirs(os.path.join(ROOT, "research", "artifacts"), exist_ok=True)
    out = os.path.join(ROOT, "research", "artifacts", "EXP-0001_trades.csv")
    with open(out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(trades[0].keys()))
        w.writeheader()
        w.writerows(trades)
    summary = {}
    for name, (a0, b0) in BLOCKS.items():
        days = sum(1 for x in d if a0 <= x.isoformat() <= b0)
        summary[name] = metrics(sp[name], days)
    summary["ALL"] = metrics(trades, len(d))
    # random-entry benchmark on the validation block count
    rnd = random_benchmark(d, o, h, l, c, ma, max(1, len(sp["VALIDATION"]) or 10), MAX_HOLD)
    summary["_random_benchmark"] = {"sims": int(len(rnd)),
                                   "mean": round(float(rnd.mean()), 2),
                                   "p5": round(float(np.percentile(rnd, 5)), 2),
                                   "p95": round(float(np.percentile(rnd, 95)), 2)}
    print(json.dumps(summary, indent=2, default=str))
    json.dump(summary, open(os.path.join(ROOT, "research", "artifacts", "EXP-0001_summary.json"), "w"),
              indent=2, default=str)
    print("wrote", out)
