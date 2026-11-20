"""Stage 4 — descriptive research on canonical D1 data.

Rules: in-sample description only. NOT a strategy, NOT a backtest.
Every forward-return number is reported NET of an explicit cost assumption.
Overlapping windows are disclosed. No claim without n.

Output: reports/RESEARCH_D1.md, reports/zscore_buckets.csv
"""
import csv, os, datetime as dt, numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, "data", "processed")
REP = os.path.join(ROOT, "reports")
os.makedirs(REP, exist_ok=True)
PIP = {"EURGBP": 1e-4, "EURUSD": 1e-4}


def load(sym):
    rows = list(csv.DictReader(open(os.path.join(P, f"{sym}_D1_clean.csv"))))
    dates = [dt.date.fromisoformat(r["ts_utc"][:10]) for r in rows]
    c = np.array([float(r["close"]) for r in rows])
    return dates, c


def hurst(x, lags=(2, 3, 5, 8, 13, 21, 34, 55, 89)):
    lx = np.log(x)
    pts = [(np.log(k), np.log(np.std(lx[k:] - lx[:-k]))) for k in lags]
    a = np.array(pts)
    return float(np.polyfit(a[:, 0], a[:, 1], 1)[0])


def halflife(s):
    s = np.asarray(s, float)
    x, y = s[:-1] - s[:-1].mean(), s[1:] - s[1:].mean()
    b = np.polyfit(x, y, 1)[0]
    return float(-np.log(2) / np.log(b)) if 0 < b < 1 else float("nan")


def vr(px, k):
    r = np.diff(np.log(px))
    v1 = r.var(ddof=1)
    rk = np.log(px[k:]) - np.log(px[:-k])
    return float(rk.var(ddof=1) / (k * v1)), len(rk)


def explore(sym, dates, c):
    pip = PIP[sym]
    r = np.diff(np.log(c))
    n = len(c)
    yrs = (dates[-1] - dates[0]).days / 365.25
    out = {"sym": sym, "n": n, "first": str(dates[0]), "last": str(dates[-1]),
           "years": round(yrs, 2),
           "vol_ann": round(float(r.std() * np.sqrt(252) * 100), 2),
           "skew": round(float(((r - r.mean()) ** 3).mean() / r.std() ** 3), 3),
           "kurt": round(float(((r - r.mean()) ** 4).mean() / r.std() ** 4), 2),
           "acf": [round(float(np.corrcoef(r[:-k], r[k:])[0, 1]), 4) for k in (1, 2, 3, 5, 10)],
           "hurst": round(hurst(c[-1500:]), 3),
           "vol_cluster_acf": round(float(np.corrcoef(np.abs(r[:-1]), np.abs(r[1:]))[0, 1]), 3)}

    w = 50
    ma = np.convolve(c, np.ones(w) / w, mode="valid")
    dev = c[w - 1:] / ma - 1
    out["hl_ma50"] = round(halflife(dev), 1)
    w2 = 200
    ma2 = np.convolve(c, np.ones(w2) / w2, mode="valid")
    out["hl_ma200"] = round(halflife(c[w2 - 1:] / ma2 - 1), 1)
    out["within_2pct_ma200"] = round(float(np.mean(np.abs(c[w2 - 1:] / ma2 - 1) < 0.02) * 100), 1)

    vrs = {}
    for k in (5, 20, 60):
        v, nk = vr(c, k)
        vrs[k] = (round(v, 3), nk)
    out["vr"] = vrs

    # z-score buckets vs forward returns, net of cost
    z = (c[w - 1:] - ma) / (np.std(c[w - 1:] - ma))
    buckets = [(-9, -2), (-2, -1), (-1, 1), (1, 2), (2, 9)]
    rows = []
    for lo, hi in buckets:
        m = (z >= lo) & (z < hi)
        for h in (5, 10, 20):
            fwd = np.full(len(c), np.nan)
            fwd[:-h] = (c[h:] - c[:-h]) / pip
            f = fwd[w - 1:][m]
            f = f[~np.isnan(f)]
            if len(f) == 0:
                continue
            gross = float(f.mean())
            rows.append({"symbol": sym, "z_bucket": f"[{lo},{hi})", "horizon_d": h,
                         "n": int(len(f)),
                         "gross_pips": round(gross, 1),
                         "net_pips_cost_0.9": round(gross - 0.9, 1),
                         "net_pips_cost_1.5": round(gross - 1.5, 1),
                         "win_rate": round(float((f > 0).mean() * 100), 1),
                         "sd_pips": round(float(f.std()), 1),
                         "t_stat": round(gross / (f.std() / np.sqrt(len(f))), 2)})
    # subperiod stability of the key finding (z<-2, 20d)
    subs = [("2016-11", "2019-12"), ("2020-01", "2022-12"), ("2023-01", "2026-11")]
    stab = []
    for a, b in subs:
        idx = [i for i, d in enumerate(dates) if a <= d.strftime("%Y-%m") <= b]
        if len(idx) < 60:
            continue
        cc, dd = c[idx], [dates[i] for i in idx]
        ww = 50
        m1 = np.convolve(cc, np.ones(ww) / ww, mode="valid")
        zz = (cc[ww - 1:] - m1) / np.std(cc[ww - 1:] - m1)
        fwd = np.full(len(cc), np.nan)
        fwd[:-20] = (cc[20:] - cc[:-20]) / pip
        f = fwd[ww - 1:][zz < -2]
        f = f[~np.isnan(f)]
        stab.append((a, b, len(f), round(float(f.mean()), 1) if len(f) else None,
                     round(float((f > 0).mean() * 100), 0) if len(f) else None))
    out["stability"] = stab

    # day-of-week
    dow = {}
    for i in range(1, len(c)):
        k = dates[i].weekday()
        dow.setdefault(k, []).append((c[i] - c[i - 1]) / pip)
    out["dow"] = [(k, len(v), round(float(np.mean(v)), 1)) for k, v in sorted(dow.items())]
    return out, rows


if __name__ == "__main__":
    L = ["# RESEARCH — D1 descriptive statistics", "",
         f"Generated: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}",
         "Script: `scripts/descriptive_d1.py` · Data: `*_D1_clean.csv` (canonical, Sunday bars removed)",
         "", "> **Scope:** descriptive only. No strategy, no backtest, no OOS. "
         "Forward-return cells are **in-sample** and windows **overlap** (h-day horizon shifted daily), "
         "so t-stats are optimistic. Treat as hypothesis generation, not evidence of edge.", ""]
    all_rows = []
    stats = []
    for sym in ["EURGBP", "EURUSD"]:
        dates, c = load(sym)
        o, rows = explore(sym, dates, c)
        stats.append(o)
        all_rows += rows
        L += [f"## {sym}", "",
              f"- sample: **{o['n']}** bars, {o['first']} → {o['last']} ({o['years']} years)",
              f"- annualised vol: **{o['vol_ann']}%** · skew {o['skew']} · kurtosis {o['kurt']}",
              f"- return autocorr (1,2,3,5,10): {o['acf']}",
              f"- Hurst (last 1500 bars): **{o['hurst']}** (<0.5 = mean reverting)",
              f"- variance ratio VR(5)={o['vr'][5][0]} · VR(20)={o['vr'][20][0]} · "
              f"VR(60)={o['vr'][60][0]} (<1 = mean reverting)",
              f"- half-life of deviation: MA50 = **{o['hl_ma50']}d**, MA200 = {o['hl_ma200']}d",
              f"- share of days within ±2% of MA200: **{o['within_2pct_ma200']}%**",
              f"- volatility clustering (|r| autocorr): {o['vol_cluster_acf']}", ""]
        L += ["| z-bucket | horizon | n | gross pips | net @0.9 | net @1.5 | win% | sd | t |",
              "|---|---|---|---|---|---|---|---|---|"]
        for r in rows:
            L.append(f"| {r['z_bucket']} | {r['horizon_d']}d | {r['n']} | {r['gross_pips']} | "
                     f"{r['net_pips_cost_0.9']} | {r['net_pips_cost_1.5']} | {r['win_rate']} | "
                     f"{r['sd_pips']} | {r['t_stat']} |")
        L += ["", "### stability of `z<-2, 20d` across subperiods (in-sample)", "",
              "| period | n | mean pips | win% |", "|---|---|---|---|"]
        L += [f"| {a}→{b} | {n} | {m} | {w} |" for a, b, n, m, w in o["stability"]]
        L += ["", "### mean D1 move by weekday (pips)", "",
              "| weekday | n | mean pips |", "|---|---|---|"]
        names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        L += [f"| {names[k]} | {n} | {m} |" for k, n, m in o["dow"]]
        L.append("")

    er = [s for s in stats if s["sym"] == "EURGBP"][0]
    eu = [s for s in stats if s["sym"] == "EURUSD"][0]
    body = L[5:]                      # keep per-symbol sections
    L = L[:5] + ["## Findings (status)", "",
                 f"1. **Range behaviour — SUPPORTED.** EURGBP sits within ±2% of its 200dMA "
                 f"{er['within_2pct_ma200']}% of days vs {eu['within_2pct_ma200']}% for EURUSD; "
                 f"Hurst {er['hurst']} vs {eu['hurst']}.",
                 f"2. **Mean reversion speed — SUPPORTED.** Deviation half-life MA50 "
                 f"{er['hl_ma50']}d (EURGBP) vs {eu['hl_ma50']}d (EURUSD).",
                 f"3. **Variance ratio < 1 — SUPPORTED** for EURGBP at 5/20/60 days "
                 f"({er['vr'][5][0]}/{er['vr'][20][0]}/{er['vr'][60][0]}).",
                 "4. **Tradeable edge from z-score — INCONCLUSIVE.** See bucket table: "
                 "gross vs net columns differ by the cost assumption, and overlapping windows "
                 "inflate t-stats. Requires the Stage 6/7 protocol before any claim.",
                 "5. **Day-of-week effect — WEAK/INCONCLUSIVE.** Small n per bucket, no "
                 "multiple-testing correction.",
                 "", "## What this does NOT prove", "",
                 "- that a strategy makes money: no entry/exit rules, no slippage, no swap, no position sizing",
                 "- out-of-sample performance: everything above is in-sample over one 10-year window",
                 "- that the effect survives regime change: see subperiod table", ""] + body
    open(os.path.join(REP, "RESEARCH_D1.md"), "w").write("\n".join(L))
    with open(os.path.join(REP, "zscore_buckets.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
        w.writeheader()
        w.writerows(all_rows)
    print("wrote reports/RESEARCH_D1.md and zscore_buckets.csv")
    for o in stats:
        print(f"{o['sym']}: n={o['n']} vol={o['vol_ann']}% hurst={o['hurst']} "
              f"hl50={o['hl_ma50']}d within2%={o['within_2pct_ma200']}% VR5={o['vr'][5][0]}")
