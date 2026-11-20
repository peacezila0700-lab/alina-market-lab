"""Screen 24 instruments x 5 documented rules, with an honest multiple-testing control.

Why the control matters: 120 tests will always produce a flattering best. For every
instrument/rule pair we therefore also run 300 RANDOM position series with the SAME number
of position changes, and report the percentile rank of the real rule against that null.
A rule that is not near the top of its own null distribution is noise no matter how pretty
its Sharpe looks.
"""
import csv, json, os, sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data", "universe")
REP = os.path.join(ROOT, "reports")
ART = os.path.join(ROOT, "research", "artifacts")
os.makedirs(ART, exist_ok=True)
SPLIT = "2013-01-01"


def load(name):
    rows = list(csv.DictReader(open(os.path.join(D, f"{name}.csv"))))
    dates = [r["date"] for r in rows]
    px = np.array([float(r["close"]) for r in rows])
    return dates, px


def sma(x, w):
    out = np.full(len(x), np.nan)
    c = np.cumsum(np.insert(x, 0, 0.0))
    out[w - 1:] = (c[w:] - c[:-w]) / w
    return out


def pos_rule(rule, px, dates):
    n = len(px)
    if rule in ("TSMOM_12M", "TSMOM_6M"):
        w = 252 if rule.endswith("12M") else 126
        sig = np.zeros(n)
        sig[w:] = np.where(px[w:] > px[:-w], 1.0, -1.0)
        pos = np.zeros(n)
        last = None
        cur = 0.0
        for i, d in enumerate(dates):
            m = d[:7]
            if m != last:
                cur = sig[i - 1] if i else 0.0
                last = m
            pos[i] = cur
        return pos
    if rule == "MA_50_200":
        f, s = sma(px, 50), sma(px, 200)
        return np.where(np.isnan(f - s), 0.0, np.where(f > s, 1.0, -1.0))
    if rule == "MA_20_100":
        f, s = sma(px, 20), sma(px, 100)
        return np.where(np.isnan(f - s), 0.0, np.where(f > s, 1.0, -1.0))
    if rule == "DONCHIAN_55":
        pos = np.zeros(n)
        for i in range(55, n):
            hi = px[i - 55:i].max()
            lo = px[i - 55:i].min()
            pos[i] = 1.0 if px[i] > hi else (-1.0 if px[i] < lo else pos[i - 1])
        return pos
    if rule == "Z_FADE":
        ma = sma(px, 50)
        dev = px - ma
        sd = np.full(n, np.nan)
        for i in range(252, n):
            sd[i] = dev[i - 252:i].std(ddof=1)
        z = dev / sd
        pos = np.zeros(n)
        i = 260
        while i < n - 21:
            if not np.isnan(z[i]) and z[i] >= 2.0:
                pos[i + 1:i + 21] = -1.0
                i += 21
            else:
                i += 1
        return pos
    if rule == "BUY_HOLD":
        return np.ones(n)
    raise ValueError(rule)


def pnl_of(px, pos, cost_pct):
    """FIXED: the position decided at close t-1 earns the return from t-1 to t."""
    ret = np.zeros(len(px))
    ret[1:] = px[1:] / px[:-1] - 1
    lag = np.r_[0.0, pos[:-1]]
    turn = np.zeros(len(px))
    turn[1:] = np.abs(np.diff(pos))
    return lag * ret - turn * (cost_pct / 100.0)


def sharpe(x):
    if len(x) < 250 or x.std(ddof=1) == 0:
        return np.nan
    return float(x.mean() / x.std(ddof=1) * np.sqrt(252))


def metrics(pnl, dates):
    eq = np.cumprod(1 + pnl)
    yrs = len(pnl) / 252
    return dict(cagr=round(float(eq[-1] ** (1 / yrs) - 1) * 100, 2),
                sharpe=round(sharpe(pnl), 2),
                maxdd=round(float(np.max(np.maximum.accumulate(eq) / eq - 1)) * 100, 1))


def null_percentile(px, pos, cost_pct, dates, sims=300, seed=7):
    """random positions with the SAME number of position changes"""
    n_changes = max(1, int(np.abs(np.diff(pos)).sum() // 2))
    rng = np.random.default_rng(seed)
    obs = sharpe(pnl_of(px, pos, cost_pct))
    if np.isnan(obs):
        return None
    null = []
    for _ in range(sims):
        rp = rng.choice([-1.0, 0.0, 1.0], size=len(px), p=[0.45, 0.10, 0.45])
        # thin the random series so turnover matches
        idx = np.sort(rng.choice(len(px), size=min(len(px), n_changes * 2), replace=False))
        keep = np.zeros(len(px))
        keep[idx] = rp[idx]
        rp = np.repeat(keep[idx], np.diff(np.r_[idx, len(px)]))[:len(px)]
        if len(rp) < len(px):
            rp = np.r_[rp, np.full(len(px) - len(rp), rp[-1] if len(rp) else 0.0)]
        null.append(sharpe(pnl_of(px, rp, cost_pct)))
    null = np.array([x for x in null if not np.isnan(x)])
    if len(null) < 20:
        return None
    return dict(pct=round(float((null < obs).mean() * 100), 0), null_mean=round(float(null.mean()), 2),
                null_p95=round(float(np.percentile(null, 95)), 2))


RULES = ["TSMOM_12M", "TSMOM_6M", "MA_50_200", "MA_20_100", "DONCHIAN_55", "Z_FADE", "BUY_HOLD"]

if __name__ == "__main__":
    man = {m["name"]: m for m in json.load(open(os.path.join(D, "MANIFEST_UNIVERSE.json")))}
    rows = []
    for name, meta in man.items():
        dates, px = load(name)
        pre = np.array([d < SPLIT for d in dates])
        for rule in RULES:
            pos = pos_rule(rule, px, dates)
            pnl = pnl_of(px, pos, meta["cost_pct"])
            m = metrics(pnl, dates)
            m.update(rule=rule, name=name, klass=meta["klass"], bars=len(px),
                     first=dates[0], cost=meta["cost_pct"],
                     sharpe_pre=round(sharpe(pnl[pre]), 2) if pre.sum() > 300 else None,
                     sharpe_post=round(sharpe(pnl[~pre]), 2) if (~pre).sum() > 300 else None)
            if rule != "BUY_HOLD":
                nl = null_percentile(px, pos, meta["cost_pct"], dates)
                m["null_pct"] = nl["pct"] if nl else None
                m["null_p95"] = nl.get("null_p95") if nl else None
            else:
                m["null_pct"] = m["null_p95"] = None
            rows.append(m)
        best = max([r for r in rows if r["name"] == name], key=lambda r: r["sharpe"])
        print(f"{name:11} best={best['rule']:12} Sharpe={best['sharpe']:>5} "
              f"CAGR={best['cagr']:>7}% null_pct={best['null_pct']}")

    rows.sort(key=lambda r: -r["sharpe"])
    with open(os.path.join(ART, "universe_screen.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    json.dump(rows, open(os.path.join(ART, "universe_screen.json"), "w"), indent=2)
    print(f"\n{len(rows)} tests written")
    print("TOP 12 by Sharpe:")
    for r in rows[:12]:
        print(f"  {r['name']:11} {r['rule']:12} Sharpe {r['sharpe']:>5} CAGR {r['cagr']:>7}% "
              f"DD {r['maxdd']:>6}% null_pct {r['null_pct']} pre {r['sharpe_pre']} post {r['sharpe_post']}")
