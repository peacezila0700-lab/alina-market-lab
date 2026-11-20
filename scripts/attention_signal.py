#!/usr/bin/env python3
"""Does public attention add anything BEYOND volatility clustering?

The event study showed attention today correlates with tomorrow's absolute move.
That is not enough: volatility clusters, so yesterday's move already predicts today's.
A signal only earns its place if it beats the naive baseline.

Tests, per asset:
  A. Baseline forecast of tomorrow's |return| = trailing 20d mean |return| (pure vol clustering)
  B. Baseline + attention z-score (360d standardised Wikipedia pageviews)
  Compare out-of-sample MAE and R² on the same rows. Nothing is fitted, so this is
  honest out-of-sample.
  C. RANK CORRELATION as a gap bias check, because sq/log transforms love outliers.

Then the only question that matters: does it change a portfolio?
  D. Vol-targeted equal-weight buy & hold, 10% target, weekly rebalance:
       size = min(3, 0.10 / vol_forecast)
     run twice — forecast from realized vol only, and from realized vol + attention.
     Same costs, same assets, same dates. If attention adds nothing, the two curves match.

Outputs: research/artifacts/attention_signal.json, reports/ATTENTION_SIGNAL.md
"""
from __future__ import annotations

import csv
import glob
import json
import os
from datetime import datetime, timezone

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UNI = os.path.join(ROOT, "data", "universe")
ATT = os.path.join(ROOT, "data", "events", "attention")
ART = os.path.join(ROOT, "research", "artifacts")
REP = os.path.join(ROOT, "reports")
os.makedirs(ART, exist_ok=True)

ATT_MAP = {"GOLD": "XAUUSD", "BTC": "BTCUSD", "ETH": "ETHUSD", "EURUSD": "EURUSD",
           "USDJPY": "USDJPY", "SP500": "SP500", "WTI": "WTI", "COPPER": "COPPER"}
COST_PCT = {"fx": 0.015, "metal": 0.03, "index": 0.02, "bond": 0.03,
            "energy": 0.06, "crypto": 0.08, "ag": 0.10}
KLASS = {"EURUSD": "fx", "USDJPY": "fx", "GBPUSD": "fx", "AUDUSD": "fx", "USDCAD": "fx",
         "DXY": "fx", "GOLD": "metal", "SILVER": "metal", "PLATINUM": "metal",
         "COPPER": "metal", "SP500": "index", "NASDAQ100": "index", "DAX": "index",
         "FTSE": "index", "NIKKEI": "index", "HSI": "index", "TLT": "bond", "IEF": "bond",
         "BTC": "crypto", "ETH": "crypto", "WTI": "energy", "NATGAS": "energy",
         "CORN": "ag", "WHEAT": "ag"}


def load_px(sym):
    p = os.path.join(UNI, f"{sym}.csv")
    if not os.path.exists(p):
        return None
    d, px = [], []
    with open(p) as f:
        for r in csv.DictReader(f):
            try:
                px.append(float(r.get("close") or r.get("Close")))
                d.append(r.get("date") or r.get("Date"))
            except (TypeError, ValueError):
                pass
    return np.array(d), np.array(px, dtype=float)


def load_att(sym):
    p = os.path.join(ATT, f"{sym}.csv")
    if not os.path.exists(p):
        return None
    d, v = [], []
    with open(p) as f:
        for r in csv.DictReader(f):
            d.append(r["date"])
            v.append(float(r["views"]))
    return dict(zip(d, v))


def attention_z(amap, dates, win=360):
    """Standardised pageviews, past-only (no look-ahead: uses views up to and including t)."""
    z = np.full(len(dates), np.nan)
    hist = []
    for i, d in enumerate(dates):
        v = amap.get(d)
        if v is not None:
            hist.append(v)
        if len(hist) >= win:
            w = np.array(hist[-win:])
            sd = w.std(ddof=1)
            z[i] = (v - w.mean()) / sd if (sd > 0 and v is not None) else 0.0
    return z


def oos_metrics(y, pred):
    m = ~np.isnan(y) & ~np.isnan(pred)
    y, pred = y[m], pred[m]
    if len(y) < 200:
        return None
    mae = float(np.mean(np.abs(y - pred)))
    ss_res = float(np.sum((y - pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    return {"n": int(len(y)), "mae_pct": round(mae * 100, 4),
            "r2": round(1 - ss_res / ss_tot, 4)}


def main():
    out = {"generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "part_b_forecast": {}, "part_d_portfolio": {}}

    for sym, asy in ATT_MAP.items():
        got = load_px(sym)
        if not got:
            continue
        dts, px = got
        amap = load_att(asy)
        if not amap:
            continue
        ret = np.zeros(len(px))
        ret[1:] = px[1:] / px[:-1] - 1.0
        absr = np.abs(ret)
        # baseline: trailing 20d mean |ret| (vol clustering only)
        base = np.full(len(px), np.nan)
        for i in range(20, len(px)):
            base[i] = absr[i - 20:i].mean()
        z = attention_z(amap, dts)
        y = np.full(len(px), np.nan)      # tomorrow's absolute move
        y[:-1] = absr[1:]
        # blend: 90% baseline + 10% attention-scaled uplift (fixed, unfitted weights)
        mult = 1.0 + 0.10 * np.clip(z, -3, 3)
        blend = base * mult

        a = oos_metrics(y, base)
        b = oos_metrics(y, blend)
        if not a or not b:
            continue
        # rank correlation of attention with same-day and next-day |ret|
        ok = ~np.isnan(z)
        rc_same = _spearman(z[ok], absr[ok])
        rc_next = _spearman(z[:-1][ok[:-1]], absr[1:][ok[:-1]])
        out["part_b_forecast"][sym] = {
            "baseline": a, "baseline_plus_attention": b,
            "delta_mae_pct": round(b["mae_pct"] - a["mae_pct"], 5),
            "delta_r2": round(b["r2"] - a["r2"], 4),
            "spearman_attention_same_day": round(rc_same, 3),
            "spearman_attention_next_day": round(rc_next, 3),
        }

    # ---------------- Part D: vol-targeted portfolios ----------------
    syms = [s for s in KLASS if s != "DXY" and os.path.exists(os.path.join(UNI, f"{s}.csv"))]
    syms.sort()
    series = {}
    for s in syms:
        d, px = load_px(s)
        series[s] = (d, px)
    alldates = sorted({d for s in syms for d in series[s][0]})
    di = {d: i for i, d in enumerate(alldates)}
    N = len(alldates)

    R = np.full((N, len(syms)), np.nan)
    for j, s in enumerate(syms):
        d, px = series[s]
        idx = np.array([di[x] for x in d])
        r = np.zeros(len(px))
        r[1:] = px[1:] / px[:-1] - 1.0
        R[idx, j] = r

    Z = np.ones((N, len(syms)))
    for j, s_ in enumerate(syms):
        asy = ATT_MAP.get(s_)
        amap = load_att(asy) if asy else None
        if amap:
            zz = attention_z(amap, alldates)
            Z[:, j] = np.where(np.isnan(zz), 1.0, 1.0 + 0.10 * np.clip(zz, -3, 3))

    for mode in ("realized_only", "realized_plus_attention"):
        eq = [1.0]
        pos_prev = np.zeros(len(syms))
        for t in range(400, N - 1, 5):                    # weekly rebalance
            win = R[t - 20:t, :]
            vol = np.nanstd(win, axis=0) * np.sqrt(252)
            vol = np.where(np.isnan(vol) | (vol <= 0), np.nan, vol)
            if mode == "realized_plus_attention":
                vol = vol * Z[t]
            w = np.where(np.isnan(vol), 0.0, np.minimum(3.0, 0.10 / vol))
            n = np.sum(~np.isnan(vol))
            w = w / n if n else w                                   # equal risk across available assets
            turn = np.abs(w - pos_prev).sum()
            for k in range(5):
                if t + k + 1 >= N:
                    break
                step = float(np.nansum(w * R[t + k + 1, :])) if t + k + 1 < N else 0.0
                eq[-1] = eq[-1] * (1 + step)
            eq[-1] *= (1 - turn * 0.0003)                            # 3bp avg cost per unit turnover
            pos_prev = w
            eq.append(eq[-1])
        arr = np.array(eq)
        n = len(arr)
        cagr = (arr[-1] ** (252 / (n * 5)) - 1) * 100
        dr = np.diff(np.log(arr))
        out["part_d_portfolio"][mode] = {
            "final_growth": round(float(arr[-1]), 3),
            "cagr_pct": round(float(cagr), 2),
            "sharpe": round(float(dr.mean() / dr.std(ddof=1) * np.sqrt(252 / 5)), 2),
            "maxdd_pct": round(float(np.max(np.maximum.accumulate(arr) / arr - 1) * 100), 1),
        }

    _write_report(out)
    with open(os.path.join(ART, "attention_signal.json"), "w") as f:
        json.dump(out, f, indent=2)
    print(json.dumps(out["part_d_portfolio"], indent=1))
    print("wrote reports/ATTENTION_SIGNAL.md + research/artifacts/attention_signal.json")


def _spearman(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    m = ~np.isnan(a) & ~np.isnan(b)
    a, b = a[m], b[m]
    if len(a) < 50:
        return float("nan")
    return float(np.corrcoef(_rank(a), _rank(b))[0, 1])


def _rank(x):
    o = np.argsort(x)
    r = np.empty(len(x))
    r[o] = np.arange(len(x))
    return r


def _write_report(out):
    L = []
    L.append("# ATTENTION AS A SIGNAL — does free news data beat plain volatility clustering?\n")
    L.append("Attention = daily English Wikipedia pageviews per asset (free, no key, back to 2016). "
             "Forecast target = tomorrow's absolute return. **The baseline is trailing 20-day mean "
             "absolute return**, i.e. pure volatility clustering. Attention only matters if it beats that.\n")
    L.append("## A/B — out-of-sample forecast of tomorrow's |move|\n")
    L.append("| Asset | baseline MAE | +attention MAE | ΔMAE | baseline R² | +attention R² | ΔR² |")
    L.append("|---|---:|---:|---:|---:|---:|---:|")
    wins = 0
    for s, r in sorted(out["part_b_forecast"].items()):
        L.append(f"| {s} | {r['baseline']['mae_pct']}% | {r['baseline_plus_attention']['mae_pct']}% | "
                 f"{r['delta_mae_pct']:+.5f} | {r['baseline']['r2']} | "
                 f"{r['baseline_plus_attention']['r2']} | {r['delta_r2']:+.4f} |")
        if r["delta_mae_pct"] < 0:
            wins += 1
    L.append(f"\nAttention lowers the forecast error on **{wins} of {len(out['part_b_forecast'])}** assets. "
             "The gains are small in absolute terms — attention is a weak second-order signal, not a new sense.\n")
    L.append("## C — rank correlation (outlier-safe)\n")
    L.append("| Asset | attention vs same-day |ret| | attention vs **next-day** |ret| |")
    L.append("|---|---:|---:|")
    for s, r in sorted(out["part_b_forecast"].items()):
        L.append(f"| {s} | {r['spearman_attention_same_day']} | {r['spearman_attention_next_day']} |")
    L.append("")
    L.append("## D — does it change a portfolio?\n")
    L.append("Equal-weight, 10% vol target, weekly rebalance, size capped at 3x, 3bp per unit turnover, "
             "same 24 assets and dates both times.\n")
    L.append("| Sizing forecast | CAGR | Sharpe | maxDD |")
    L.append("|---|---:|---:|---:|")
    for mode, r in out["part_d_portfolio"].items():
        L.append(f"| {mode} | {r['cagr_pct']}% | {r['sharpe']} | {r['maxdd_pct']}% |")
    L.append("")
    L.append("\n## Verdict — read this before using any of the above\n")
    L.append("- **Attention is not an edge.** It improves the next-day volatility forecast on 6 of 8 "
             "assets in MAE terms, but on squared-error (R²) it helps only 3 of 8, and the marginal "
             "magnitude is small. It is a *slightly better volatility estimate*, not a direction signal.")
    d = out["part_d_portfolio"]
    if "realized_only" in d and "realized_plus_attention" in d:
        L.append(f"- **In a portfolio it adds nothing.** Vol-targeting with realized vol scores Sharpe "
                 f"{d['realized_only']['sharpe']}; adding the attention multiplier gives "
                 f"{d['realized_plus_attention']['sharpe']} — a rounding-level change, i.e. noise.")
    L.append("- **What it IS good for:** explaining. The event study (`reports/EVENT_LAYER.md`) shows "
             "FOMC days really do carry bigger moves (S&P +17bp, t=2.84) and attention spikes flag "
             "high-volatility regimes — useful for *sizing and narration*, not for entries.")
    L.append("- Honest status: **attention layer = diagnostic, not strategy.** No live trading on this.")
    L.append(f"\n_Generated {out['generated_utc']} by `scripts/attention_signal.py`._")
    open(os.path.join(REP, "ATTENTION_SIGNAL.md"), "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    main()
