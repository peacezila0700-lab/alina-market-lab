"""EXP-0002 — power expansion for H01 (rule FROZEN, nothing tuned).

Two changes vs EXP-0001, both of which only add sample, never change the rule:
  1. longer history  : each pair from its earliest available D1 bar (2000-2003) instead of 2016
  2. cross-section   : the same frozen rule on 5 mean-reverting pairs, equal weight

Honest split:
  CLEAN = bars before 2016-11-21  -> never used by any prior analysis in this project
  USED  = 2016-11-21 onwards      -> already consumed by screening / EXP-0001 (reference only)

Statistics: block bootstrap that resamples CALENDAR CLUSTERS (month), not individual trades,
because trades in different pairs overlap in time and are therefore not independent.
"""
import csv, os, sys, json, datetime as dt, collections
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest_engine as be

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "data", "processed")
BASKET = ["EURGBP", "EURCHF", "AUDNZD", "CADCHF", "EURUSD"]
CUT = "2016-11-21"
PIP = 1e-4


def load_full(sym):
    rows = list(csv.DictReader(open(os.path.join(P, f"{sym}_D1_fullclean.csv"))))
    d = [dt.date.fromisoformat(r["ts_utc"][:10]) for r in rows]
    o = np.array([float(r["open"]) for r in rows])
    h = np.array([float(r["high"]) for r in rows])
    l = np.array([float(r["low"]) for r in rows])
    c = np.array([float(r["close"]) for r in rows])
    return d, o, h, l, c


def stats(net):
    net = np.asarray(net, float)
    if len(net) == 0:
        return dict(n=0)
    w, l = net[net > 0].sum(), -net[net < 0].sum()
    return dict(n=int(len(net)), net_exp=round(float(net.mean()), 2),
                total=round(float(net.sum()), 1),
                pf=round(float(w / l), 2) if l > 0 else float("inf"),
                win=round(float((net > 0).mean() * 100), 1),
                sd=round(float(net.std(ddof=1)), 1) if len(net) > 1 else None)


def cluster_bootstrap(net_by_month, iters=5000, seed=13):
    """resample whole months -> handles cross-pair correlation"""
    keys = list(net_by_month.keys())
    if len(keys) < 6:
        return None, None
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(iters):
        pick = rng.choice(len(keys), size=len(keys), replace=True)
        vals = np.concatenate([net_by_month[keys[i]] for i in pick])
        if len(vals):
            means.append(vals.mean())
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def main():
    per_pair, all_trades = {}, []
    for sym in BASKET:
        d, o, h, l, c = load_full(sym)
        ma, z, a = be.build_signals(d, o, h, l, c)
        tr = be.run_strategy(d, o, h, l, c, z, ma, a)
        for t in tr:
            t["symbol"] = sym
        per_pair[sym] = dict(trades=tr, bars=len(c),
                             first=d[0].isoformat(), last=d[-1].isoformat())
        all_trades += tr
        print(f"{sym}: {len(c)} bars {d[0]} -> {d[-1]} | {len(tr)} trades")

    # ---- split clean / used ----
    def bucket(trades, side):
        return [t for t in trades if (t["entry_date"] < CUT) == (side == "CLEAN")]

    out = {"generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "rule": "frozen H01 (z>=2, MA50, sigma 252d, next-open fill, 20d time stop, 3*ATR stop)",
           "cost_pips_per_trade": be.SPREAD + 2 * be.SLIP,
           "split": {"CLEAN": f"< {CUT} (never used before)", "USED": f">= {CUT}"},
           "per_pair": {}, "pooled": {}}

    for sym, info in per_pair.items():
        for side in ("CLEAN", "USED"):
            tr = bucket(info["trades"], side)
            out["per_pair"].setdefault(sym, {})[side] = stats([t["net_pips"] for t in tr])
        out["per_pair"][sym]["bars"] = info["bars"]
        out["per_pair"][sym]["first"] = info["first"]

    for side in ("CLEAN", "USED"):
        tr = [t for t in all_trades if (t["entry_date"] < CUT) == (side == "CLEAN")]
        by_month = collections.defaultdict(list)
        for t in tr:
            by_month[t["entry_date"][:7]].append(t["net_pips"])
        lo, hi = cluster_bootstrap(by_month)
        s = stats([t["net_pips"] for t in tr])
        s.update(ci_lo=None if lo is None else round(lo, 2),
                 ci_hi=None if hi is None else round(hi, 2),
                 months=len(by_month))
        # regime spread across pairs
        per = [np.mean([t["net_pips"] for t in tr if t["symbol"] == sym]) if
               any(t["symbol"] == sym for t in tr) else None for sym in BASKET]
        s["pair_means"] = [None if p is None else round(float(p), 1) for p in per]
        s["pairs_positive"] = int(sum(1 for p in per if p is not None and p > 0))
        out["pooled"][side] = s

        # concurrency: how many other pairs are in a position on the entry date
        conc = []
        for t in tr:
            n = sum(1 for u in tr if u["symbol"] != t["symbol"]
                    and u["entry_date"] <= t["entry_date"] <= u["exit_date"])
            conc.append(n)
        out["pooled"][side]["avg_concurrent_other_pairs"] = round(float(np.mean(conc)), 2) if conc else None

    # ---- random benchmark on the CLEAN window, pooled ----
    rng = np.random.default_rng(23)
    clean_tr = bucket(all_trades, "CLEAN")
    n_t = max(1, len(clean_tr))
    sims = []
    for _ in range(2000):
        sims.append(float(rng.choice([t["net_pips"] for t in clean_tr], size=n_t, replace=True).mean()
                          + rng.normal(0, 1)) if False else 0)
    # honest random benchmark: random entries per pair, same count and hold, same costs
    sims = []
    for _ in range(1000):
        vals = []
        for sym in BASKET:
            d, o, h, l, c = load_full(sym)
            k = len([t for t in clean_tr if t["symbol"] == sym])
            if k == 0:
                continue
            r = np.random.default_rng(int(rng.integers(1e6)))
            idx = r.integers(be.SIG_WIN, len(c) - be.MAX_HOLD - 1, size=k)
            for i in idx:
                e, x = o[i + 1], o[min(i + 1 + be.MAX_HOLD, len(c) - 1)]
                vals.append((e - x) / PIP - (be.SPREAD + 2 * be.SLIP))
        if vals:
            sims.append(float(np.mean(vals)))
    sims = np.array(sims)
    out["random_benchmark_CLEAN"] = dict(sims=int(len(sims)),
                                        mean=round(float(sims.mean()), 2),
                                        p5=round(float(np.percentile(sims, 5)), 2),
                                        p95=round(float(np.percentile(sims, 95)), 2))

    # ---- per-pair trade ledger ----
    art = os.path.join(ROOT, "research", "artifacts")
    os.makedirs(art, exist_ok=True)
    cols = ["symbol", "signal_date", "entry_date", "exit_date", "bars_held",
            "entry_px", "exit_px", "stop_px", "reason", "gross_pips", "cost_pips", "net_pips"]
    with open(os.path.join(art, "EXP-0002_trades.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(all_trades, key=lambda t: t["entry_date"]))
    json.dump(out, open(os.path.join(art, "EXP-0002_summary.json"), "w"), indent=2)

    print("\n=== POOLED ===")
    for side in ("CLEAN", "USED"):
        print(side, json.dumps(out["pooled"][side]))
    print("random benchmark (CLEAN):", out["random_benchmark_CLEAN"])
    print("wrote research/artifacts/EXP-0002_*")


if __name__ == "__main__":
    main()
