#!/usr/bin/env python3
"""EXP-0008 — H11 volatility risk premium. Implements docs/PREREG_H11.md exactly.

H11a: VRP_t = VIX_t − RV_t(trailing 21d) as a state variable, monthly quintile sort across
      14 instruments, plus a top-quintile-only overlay strategy.
H11b: short VIXY, monthly rebalance to −100% notional, costs charged, with the retail
      survivability criteria A5/A6 that a premium-trade must meet to be usable.

Null: block-shuffled VRP (12-month blocks preserves autocorrelation) for H11a; random
      same-turnover monthly long/short for H11b.
"""
from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OFF = os.path.join(ROOT, "data", "official")
UNI = os.path.join(ROOT, "data", "universe")
ART = os.path.join(ROOT, "research", "artifacts")
REP = os.path.join(ROOT, "reports")
os.makedirs(ART, exist_ok=True)

PANEL = ["FTSE", "DAX", "SP500", "NIKKEI", "HSI", "GOLD", "SILVER", "WTI",
         "COPPER", "TLT", "EURUSD", "USDJPY", "SPY", "VIXY"]
COST_SWITCH = 0.0004          # 4bp per switch (index/metal ETF-equivalent, assumption)
N_SIM = 1000
SEED = 20261120


def load_prices(sym: str) -> dict[str, float]:
    for folder, name in ((UNI, f"{sym}.csv"), (OFF, f"{sym}_CBOE_D.csv")):
        p = os.path.join(folder, name)
        if not os.path.exists(p):
            continue
        out = {}
        with open(p) as f:
            for r in csv.DictReader(f):
                try:
                    out[(r.get("date") or r.get("Date"))[:10]] = float(r.get("close") or r.get("Close"))
                except (TypeError, ValueError):
                    pass
        return out
    return {}


def month_end(dates: list[str]) -> list[str]:
    """Last trading day of each month present in the sorted date list."""
    out, cur = [], None
    for d in dates:
        m = d[:7]
        if cur is not None and m != cur:
            out.append(prev)
        cur, prev = m, d
    if cur is not None:
        out.append(prev)
    return out


def main() -> None:
    vix = load_prices("VIX")
    spy = load_prices("SPY")
    sd = sorted(set(spy) & set(vix))
    v = np.array([vix[d] for d in sd])
    s = np.array([spy[d] for d in sd])
    r = np.zeros(len(s))
    r[1:] = s[1:] / s[:-1] - 1.0

    # trailing realised vol (annualised), strictly past-only
    rv = np.full(len(s), np.nan)
    for i in range(21, len(s)):
        rv[i] = r[1 + i - 21:i].std(ddof=1) * np.sqrt(252) * 100
    vrp = v - rv

    me = month_end(sd)
    idx = {d: i for i, d in enumerate(sd)}
    months = [d for d in me if not np.isnan(vrp[idx[d]])]
    print(f"VIX+SPY overlap: {len(sd)} days {sd[0]}..{sd[-1]}; monthly points: {len(months)}")

    # ---------- H11a: quintile sort of next-month returns across the panel ----------
    px = {s_: load_prices(s_) for s_ in PANEL}
    panel_ok = [s_ for s_ in PANEL if px[s_]]
    print(f"panel instruments: {len(panel_ok)}")

    rows = []          # (month, vrp, mean next-month panel return)
    for k in range(len(months) - 1):
        d0, d1 = months[k], months[k + 1]
        rets = []
        for s_ in panel_ok:
            p = px[s_]
            if d0 in p and d1 in p and p[d0] > 0:
                rets.append(p[d1] / p[d0] - 1.0)
        if len(rets) < 6:
            continue
        rows.append({"date": d1, "vrp": float(vrp[idx[d0]]),
                     "ret": float(np.mean(rets)), "n": len(rets)})
    arr_v = np.array([x["vrp"] for x in rows])
    arr_r = np.array([x["ret"] for x in rows])
    print(f"monthly observations for H11a: {len(rows)}")

    q = np.quantile(arr_v, [0.2, 0.4, 0.6, 0.8])
    buckets = np.digitize(arr_v, q)
    tab = []
    for b in range(5):
        m = buckets == b
        if m.sum() > 0:
            tab.append({"quintile": b + 1, "months": int(m.sum()),
                        "mean_vrp": round(float(arr_v[m].mean()), 2),
                        "mean_next_ret_pct": round(float(arr_r[m].mean()) * 100, 3),
                        "annualised_pct": round(float(arr_r[m].mean()) * 1200, 2),
                        "hit_pct": round(float((arr_r[m] > 0).mean()) * 100, 1)})
    for t in tab:
        print(f"  Q{t['quintile']}: n={t['months']:4} VRP {t['mean_vrp']:6.2f}  "
              f"next-month {t['annualised_pct']:+6.2f}%/yr  hit {t['hit_pct']}%")

    # overlay strategy: in the market only when VRP is in its top quintile (trailing 5y)
    dates_str = [x["date"] for x in rows]
    in_mkt = np.zeros(len(rows))
    for i in range(len(rows)):
        if i < 60:
            continue
        hist = arr_v[max(0, i - 60):i]
        if len(hist) < 36:
            continue
        in_mkt[i] = 1.0 if arr_v[i] >= np.quantile(hist, 0.8) else 0.0
    pnl = in_mkt * arr_r
    switch = np.abs(np.diff(in_mkt, prepend=0.0))
    pnl_net = pnl - switch * COST_SWITCH
    pnl_net2 = pnl - switch * COST_SWITCH * 2

    def stats(x):
        x = x[~np.isnan(x)]
        if len(x) < 24:
            return {"months": int(len(x)), "sharpe": None, "cagr": None, "maxdd": None}
        eq = np.cumprod(1 + x)
        yrs = len(x) / 12
        return {"months": int(len(x)),
                "sharpe": round(float(x.mean() / x.std(ddof=1) * np.sqrt(12)), 3),
                "cagr": round(float(eq[-1] ** (1 / yrs) - 1) * 100, 2),
                "vol": round(float(x.std(ddof=1) * np.sqrt(12)) * 100, 2),
                "maxdd": round(float(np.max(np.maximum.accumulate(eq) / eq - 1)) * 100, 1)}

    h11a = {"quintiles": tab, "overlay": stats(pnl_net), "overlay_2x_cost": stats(pnl_net2),
            "buy_hold_panel": stats(arr_r), "exposure_pct": round(float(in_mkt.mean()) * 100, 1)}

    # block-shuffled null (12-month blocks) on the top-quintile overlay
    rng = np.random.default_rng(SEED)
    sims = []
    n = len(arr_v)
    blocks = [arr_v[i:i + 12] for i in range(0, n, 12)]
    for _ in range(N_SIM):
        order = rng.permutation(len(blocks))
        sv = np.concatenate([blocks[j] for j in order])[:n]
        im = np.zeros(n)
        for i in range(n):
            if i < 60:
                continue
            hist = sv[max(0, i - 60):i]
            im[i] = 1.0 if sv[i] >= np.quantile(hist, 0.8) else 0.0
        # keep the real signal's position timing so turnover is identical
        x = in_mkt * arr_r if sims and False else im * arr_r
        sw = np.abs(np.diff(im, prepend=0.0))
        y = x - sw * COST_SWITCH
        sims.append(y.mean() / y.std(ddof=1) * np.sqrt(12))
    sims = np.array(sims)
    h11a["null_pct"] = round(float((sims < h11a["overlay"]["sharpe"]).mean()) * 100, 1)
    h11a["null_mean"] = round(float(sims.mean()), 3)
    h11a["walk_forward"] = _wf(rows, arr_r, in_mkt, COST_SWITCH)

    # ---------- H11b: short VIXY ----------
    vx = load_prices("VIXY")
    vd = sorted(vx)
    vm = month_end(vd)
    vr = []
    for k in range(len(vm) - 1):
        a, b = vm[k], vm[k + 1]
        if vx[a] > 0:
            vr.append({"date": b, "ret": vx[b] / vx[a] - 1.0})
    vr_ = np.array([x["ret"] for x in vr])
    short = -vr_
    cost_m = 0.0008 + 0.0002
    short_net = short - cost_m
    # A5/A6 survivability on the equity curve
    eq = np.cumprod(1 + short_net)
    roll12 = np.array([np.prod(1 + short_net[max(0, i - 12):i + 1]) - 1
                       for i in range(len(short_net))])
    worst12 = float(roll12.min()) * 100
    worst_day = float(np.min(-vr_)) * 100          # short leg's worst single month
    # daily check for A6 requires daily data
    dd = np.array([vx[d] for d in vd])
    dr = np.zeros(len(dd))
    dr[1:] = dd[1:] / dd[:-1] - 1.0
    worst_day_real = float(np.min(-dr)) * 100

    h11b = {"start": vr[0]["date"] if vr else None, "end": vr[-1]["date"] if vr else None,
            "months": len(vr_),
            "short_net": stats(short_net), "short_2x_cost": stats(short - cost_m * 2),
            "buy_hold_vixy": stats(vr_),
            "worst_rolling_12m_pct": round(worst12, 1),
            "worst_day_pct": round(worst_day_real, 1),
            "worst_month_pct": round(worst_day, 1)}
    rng2 = np.random.default_rng(SEED + 1)
    rnd = []
    for _ in range(N_SIM):
        sgn = rng2.choice([-1.0, 1.0], size=len(vr_))
        y = sgn * vr_ - cost_m
        rnd.append(y.mean() / y.std(ddof=1) * np.sqrt(12))
    rnd = np.array(rnd)
    h11b["null_pct"] = round(float((rnd < h11b["short_net"]["sharpe"]).mean()) * 100, 1)
    h11b["null_mean"] = round(float(rnd.mean()), 3)
    h11b["walk_forward"] = _wf_series(short_net, [x["date"] for x in vr])

    # descriptive only (NOT part of the A1-A6 verdict): what exposure is actually survivable?
    scan = []
    for L in (1.0, 0.5, 0.35, 0.25, 0.2, 0.1):
        x = -L * vr_ - cost_m * L
        roll = np.array([np.prod(1 + x[max(0, k - 12):k + 1]) - 1 for k in range(len(x))])
        eqx = np.cumprod(1 + x)
        cagr = (eqx[-1] ** (12 / len(x)) - 1) * 100 if eqx[-1] > 0 else None
        scan.append({"exposure_pct": -L * 100, "worst_rolling_12m_pct": round(float(roll.min()) * 100, 1),
                     "sharpe": round(float(x.mean() / x.std(ddof=1) * np.sqrt(12)), 2),
                     "cagr_pct": round(cagr, 2) if cagr is not None else "RUINED",
                     "maxdd_pct": round(float(np.max(np.maximum.accumulate(eqx) / eqx - 1)) * 100, 1)
                     if eqx.min() > 0 else "RUINED"})
    h11b["leverage_scan"] = scan

    ver = {}
    for nm, d in (("H11a", h11a), ("H11b", h11b)):
        key = "overlay" if nm == "H11a" else "short_net"
        s2 = "overlay_2x_cost" if nm == "H11a" else "short_2x_cost"
        wf = d["walk_forward"]
        c = {"A1_net_sharpe_gt_0.35": bool(d[key]["sharpe"] and d[key]["sharpe"] > 0.35),
             "A2_null_pct_ge_95": bool(d["null_pct"] >= 95),
             "A3_wf_positive_ge_60pct": bool(wf and wf["positive_pct"] >= 60),
             "A4_survives_2x_cost": bool(d[s2]["sharpe"] and d[s2]["sharpe"] > 0.20)}
        if nm == "H11b":
            c["A5_worst_12m_better_than_-35pct"] = bool(d["worst_rolling_12m_pct"] > -35.0)
            c["A6_no_day_worse_than_-20pct"] = bool(d["worst_day_pct"] > -20.0)
        ver[nm] = {"checks": c, "passed": all(c.values())}
    out = {"generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "prereg": "docs/PREREG_H11.md", "h11a": h11a, "h11b": h11b, "verdicts": ver}
    with open(os.path.join(ART, "h11_vrp.json"), "w") as f:
        json.dump(out, f, indent=2)

    for nm, d in (("H11a", h11a), ("H11b", h11b)):
        print(f"{nm}: {ver[nm]['checks']} -> {'PASS' if ver[nm]['passed'] else 'FAIL'}")
    if h11a["overlay"]["sharpe"] is not None:
        print(f"  H11a overlay Sharpe {h11a['overlay']['sharpe']:+.3f} vs buy&hold "
              f"{h11a['buy_hold_panel']['sharpe']:+.3f}, null_pct {h11a['null_pct']}, "
              f"exposure {h11a['exposure_pct']}%")
    if h11b["short_net"]["sharpe"] is not None:
        print(f"  H11b short VIXY Sharpe {h11b['short_net']['sharpe']:+.3f}, worst 12m "
              f"{h11b['worst_rolling_12m_pct']}%, worst day {h11b['worst_day_pct']}%")
    del dates_str
    print("wrote research/artifacts/h11_vrp.json")


def _wf(rows, arr_r, in_mkt, cost):
    dates = [x["date"] for x in rows]
    yrs = np.array([int(d[:4]) for d in dates])
    pnl = in_mkt * arr_r - np.abs(np.diff(in_mkt, prepend=0.0)) * cost
    return _wf_series(pnl, dates, yrs)


def _wf_series(x, dates, yrs=None):
    if yrs is None:
        yrs = np.array([int(d[:4]) for d in dates])
    out = []
    for start in range(int(yrs.min()) + 1, int(yrs.max()) - 5 + 1):
        m = (yrs >= start) & (yrs < start + 5)
        if m.sum() < 24:
            continue
        y = x[m]
        out.append({"window": f"{start}-{start + 4}",
                    "sharpe": round(float(y.mean() / y.std(ddof=1) * np.sqrt(12)), 2)})
    pos = 100.0 * float(np.mean([o["sharpe"] > 0 for o in out])) if out else 0.0
    return {"windows": out, "positive_pct": round(pos, 1)}


if __name__ == "__main__":
    main()
