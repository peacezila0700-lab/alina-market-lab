"""Portfolio test of the Donchian breakout (the only family that survived the universe screen).

Design decisions, stated up front:
  * one rule: DONCHIAN 55 (Turtle convention). 30 and 100 are reported as SENSITIVITY only;
    the portfolio is built on 55 and the choice is never revisited to improve the number.
  * long/short, equal risk weight across instruments that have data on that day
  * cost = per-class % of notional, charged on position changes (from the universe manifest)
  * no leverage, no position sizing model beyond equal weight (that is a separate question)

Outputs reports/PORTFOLIO_DONCHIAN.md + artifacts.
"""
import csv, json, os
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data", "universe")
ART = os.path.join(ROOT, "research", "artifacts")
os.makedirs(ART, exist_ok=True)


def load_all():
    man = {m["name"]: m for m in json.load(open(os.path.join(D, "MANIFEST_UNIVERSE.json")))}
    data = {}
    for name, meta in man.items():
        rows = list(csv.DictReader(open(os.path.join(D, f"{name}.csv"))))
        data[name] = (np.array([r["date"] for r in rows]),
                      np.array([float(r["close"]) for r in rows]), meta["cost_pct"])
    return data


def donchian_pos(px, w):
    n = len(px)
    pos = np.zeros(n)
    for i in range(w, n):
        hi = px[i - w:i].max()
        lo = px[i - w:i].min()
        pos[i] = 1.0 if px[i] > hi else (-1.0 if px[i] < lo else pos[i - 1])
    return pos


def pnl_series(px, pos, cost_pct):
    """FIXED: position from close t-1 earns the t-1 -> t return (no same-bar look-ahead)."""
    ret = np.zeros(len(px))
    ret[1:] = px[1:] / px[:-1] - 1
    lag = np.r_[0.0, pos[:-1]]
    turn = np.zeros(len(px))
    turn[1:] = np.abs(np.diff(pos))
    return lag * ret - turn * (cost_pct / 100.0)


def stats(p, label=""):
    p = np.asarray(p)
    eq = np.cumprod(1 + p)
    yrs = len(p) / 252
    dd = float(np.max(np.maximum.accumulate(eq) / eq - 1))
    return dict(label=label, years=round(yrs, 1),
                cagr=round(float(eq[-1] ** (1 / yrs) - 1) * 100, 2),
                vol=round(float(p.std(ddof=1) * np.sqrt(252)) * 100, 1),
                sharpe=round(float(p.mean() / p.std(ddof=1) * np.sqrt(252)), 2),
                maxdd=round(dd * 100, 1),
                worst_yr=round(min(((np.cumprod(1 + p)[np.array([d[:4] for d in dates_grid]) == y][-1] /
                                     np.cumprod(1 + p)[np.array([d[:4] for d in dates_grid]) == y][0] - 1)
                                    for y in sorted(set(d[:4] for d in dates_grid)))) * 100, 1))


if __name__ == "__main__":
    data = load_all()
    dates_grid = sorted(set(d for name in data for d in data[name][0]))
    idx = {d: i for i, d in enumerate(dates_grid)}
    weights_used = []
    results = {}
    port = {}
    for w in (30, 55, 100):
        contrib = []
        for name, (dates, px, cost) in data.items():
            pos = donchian_pos(px, w)
            pnl = pnl_series(px, pos, cost)
            full = np.full(len(dates_grid), np.nan)
            full[[idx[d] for d in dates]] = pnl
            contrib.append(full)
        M = np.array(contrib)                       # instruments x days
        active = ~np.isnan(M)
        port_pnl = np.where(active, M, 0).sum(axis=0) / np.maximum(active.sum(axis=0), 1)
        port_pnl = port_pnl[np.maximum(active.sum(axis=0), 1) > 0]
        use_dates = [d for d, a in zip(dates_grid, active.sum(axis=0)) if a > 0]
        globals()["dates_grid"] = use_dates
        results[f"DONCH_{w}"] = stats(port_pnl, f"DONCH_{w} portfolio")
        if w == 55:
            port = dict(pnl=port_pnl, dates=use_dates, matrix=M, active=active)
            weights_used = active.sum(axis=0)

    # buy & hold benchmark: equal weight long-only
    bh = []
    for name, (dates, px, cost) in data.items():
        ret = np.zeros(len(px)); ret[1:] = px[1:] / px[:-1] - 1
        full = np.full(len(dates_grid), np.nan)
        full[[idx[d] for d in dates]] = ret
        bh.append(full)
    B = np.array(bh)
    act = ~np.isnan(B)
    bh_pnl = np.where(act, B, 0).sum(axis=0) / np.maximum(act.sum(axis=0), 1)
    bh_pnl = bh_pnl[np.maximum(act.sum(axis=0), 1) > 0]
    results["BUY_HOLD_EW"] = stats(bh_pnl, "Equal-weight buy & hold")

    # yearly returns of the 55 portfolio
    p = port["pnl"]
    dts = port["dates"]
    eq = np.cumprod(1 + p)
    yearly = {}
    for y in sorted(set(d[:4] for d in dts)):
        m = np.array([d[:4] == y for d in dts])
        if m.sum() < 20:
            continue
        yearly[y] = round(float(eq[m][-1] / (eq[m][0] / (1 + p[m][0])) - 1) * 100, 1)

    print("\n=== portfolio comparison ===")
    for k, v in results.items():
        print(f"  {v['label']:28} CAGR {v['cagr']:>6}%  vol {v['vol']:>5}%  "
              f"Sharpe {v['sharpe']:>5}  maxDD {v['maxdd']:>6}%")
    print("\ninstruments active at end:", int(weights_used[-1]),
          "| average active:", round(float(np.mean(weights_used)), 1))
    print("\nyearly returns (DONCH_55):")
    for y, v in yearly.items():
        print(f"  {y}: {v:>7}%")

    json.dump(dict(results=results, yearly=yearly,
                   avg_active=round(float(np.mean(weights_used)), 1)),
              open(os.path.join(ART, "portfolio_donchian.json"), "w"), indent=2)
    print("\nwrote research/artifacts/portfolio_donchian.json")
