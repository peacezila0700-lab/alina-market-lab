#!/usr/bin/env python3
"""Test the families that free EA sites actually give away, on the same 24-asset universe.

Why: `data/free_eas/CATALOG.csv` shows what the free ecosystem offers (332 sources harvested
from MQL5 Code Base + GitHub). This script re-implements the *logic families* those products
belong to — RSI fade, Bollinger fade, Ichimoku, MACD, Stochastic, Supertrend, grid/martingale —
and runs them through the SAME cost-charged, lagged, null-controlled engine as everything else.

We cannot compile MQL5 here, so this tests the ideas, not the individual products. That is the
honest comparison: if a family has no edge before the vendor's marketing, no product in it can.

P&L is NOT re-implemented (QR-002): `pnl_of`, `metrics`, `null_percentile` are imported from
scripts/screen_universe.py.

Grid/martingale gets its own explicit simulator, because it is a sizing scheme rather than a
signal, and its risk profile (blowup) is the thing being measured.
"""
from __future__ import annotations

import csv
import importlib.util
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "research", "artifacts")
REP = os.path.join(ROOT, "reports")
UNI = os.path.join(ROOT, "data", "universe")

spec = importlib.util.spec_from_file_location("su", os.path.join(ROOT, "scripts", "screen_universe.py"))
su = importlib.util.module_from_spec(spec)
sys.modules["su"] = su
spec.loader.exec_module(su)


def ema(x: np.ndarray, n: int) -> np.ndarray:
    a = 2.0 / (n + 1.0)
    out = np.full(len(x), np.nan)
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = a * x[i] + (1 - a) * out[i - 1]
    return out


def rsi(x: np.ndarray, n: int = 14) -> np.ndarray:
    d = np.diff(x, prepend=x[0])
    up, dn = np.where(d > 0, d, 0.0), np.where(d < 0, -d, 0.0)
    au = np.full(len(x), np.nan)
    ad = np.full(len(x), np.nan)
    au[n] = up[1:n + 1].mean()
    ad[n] = dn[1:n + 1].mean()
    for i in range(n + 1, len(x)):
        au[i] = (au[i - 1] * (n - 1) + up[i]) / n
        ad[i] = (ad[i - 1] * (n - 1) + dn[i]) / n
    rs = np.where(ad > 0, au / ad, 100.0)
    return 100 - 100 / (1 + rs)


def atr(px: np.ndarray, n: int = 10) -> np.ndarray:
    d = np.abs(np.diff(px, prepend=px[0]))
    out = np.full(len(px), np.nan)
    out[n] = d[1:n + 1].mean()
    for i in range(n + 1, len(px)):
        out[i] = (out[i - 1] * (n - 1) + d[i]) / n
    return out


def rule_positions(name: str, px: np.ndarray) -> np.ndarray:
    n = len(px)
    pos = np.zeros(n)
    if name == "RSI_FADE":
        r = rsi(px)
        cur = 0.0
        for i in range(15, n):
            if np.isnan(r[i]):
                continue
            if cur == 0.0:
                cur = 1.0 if r[i] < 30 else (-1.0 if r[i] > 70 else 0.0)
            elif cur > 0 and r[i] > 50:
                cur = 0.0
            elif cur < 0 and r[i] < 50:
                cur = 0.0
            pos[i] = cur
    elif name == "BOLL_FADE":
        w = 20
        for i in range(w, n):
            m = px[i - w:i].mean()
            sd = px[i - w:i].std(ddof=1)
            if sd <= 0:
                continue
            z = (px[i] - m) / sd
            cur = pos[i - 1] if i else 0.0
            if cur == 0.0:
                cur = 1.0 if z < -2 else (-1.0 if z > 2 else 0.0)
            elif (cur > 0 and z >= 0) or (cur < 0 and z <= 0):
                cur = 0.0
            pos[i] = cur
    elif name == "ICHIMOKU":
        t = np.array([np.mean(px[max(0, i - 8):i + 1]) if i >= 8 else np.nan for i in range(n)])
        k = np.array([np.mean(px[max(0, i - 25):i + 1]) if i >= 25 else np.nan for i in range(n)])
        for i in range(26, n):
            if np.isnan(t[i]) or np.isnan(k[i]):
                continue
            pos[i] = 1.0 if t[i] > k[i] else -1.0
    elif name == "MACD":
        f, s_, sig = ema(px, 12), ema(px, 26), None
        macd = f - s_
        sig = ema(macd, 9)
        for i in range(30, n):
            if np.isnan(macd[i]) or np.isnan(sig[i]):
                continue
            pos[i] = 1.0 if macd[i] > sig[i] else -1.0
    elif name == "STOCH_FADE":
        w = 14
        cur = 0.0
        for i in range(w, n):
            hh, ll = px[i - w:i].max(), px[i - w:i].min()
            if hh <= ll:
                continue
            kk = (px[i] - ll) / (hh - ll) * 100
            if cur == 0.0:
                cur = 1.0 if kk < 20 else (-1.0 if kk > 80 else 0.0)
            elif cur > 0 and kk > 50:
                cur = 0.0
            elif cur < 0 and kk < 50:
                cur = 0.0
            pos[i] = cur
    elif name == "SUPERTREND":
        a = atr(px, 10)
        for i in range(11, n):
            if np.isnan(a[i]):
                continue
            pos[i] = 1.0 if px[i] > px[i - 1] + 0.0 and px[i] > np.mean(px[max(0, i - 10):i]) else -1.0
    else:
        raise ValueError(name)
    return pos


def martingale_sim(px: np.ndarray, base=0.01, mult=2.0, levels=6, tp_atr=1.0, cost_pct=0.02):
    """Counter-trend grid with lot doubling — the single most common free-EA scheme.

    Starts a position against the move after every 1-ATR step; profit target is 1-ATR from the
    volume-weighted entry. Equity is in units of account risk where base lot = 1% of equity.
    Position size grows 2x per level; a single surviving run past `levels` is a full wipe.
    """
    n = len(px)
    a = atr(px, 14)
    equity, worst_dd, wiped_at = 1.0, 0.0, None
    i = 20
    while i < n - 1:
        if np.isnan(a[i]) or a[i] <= 0:
            i += 1
            continue
        direction = -np.sign(px[i + 1] - px[i]) or 1.0      # fade the last move
        step = a[i]
        lots, vwap, lev = 0.0, 0.0, 0
        entry_i = i
        size = base
        pnl = 0.0
        j = i + 1
        while j < n:
            pnl += direction * (px[j] / px[j - 1] - 1.0) * size
            cost = abs(px[j] - px[j - 1]) / px[j] * 0  # costs charged below per fill
            adverse = (px[j] - px[entry_i]) * direction
            if adverse < -step * (lev + 1) and lev < levels:
                lev += 1
                size *= mult
                lots += size
                vwap = (vwap * (lots - size) + px[j] * size) / lots if lots else px[j]
                pnl -= size * cost_pct / 100.0
            if lots > 0 and pnl > 0.5 * size * step / px[j]:
                pnl -= lots * cost_pct / 100.0
                break
            if lev >= levels and adverse < -step * (levels + 1):
                pnl = -lots * 1.0        # margin gone: lose the whole stacked exposure
                wiped_at = j
                break
            j += 1
        equity += pnl * 0.01
        worst_dd = max(worst_dd, 1 - equity / max(equity, 1e-9) if equity <= 0 else 0.0)
        if equity <= 0.05 and wiped_at is None:
            wiped_at = j
        if equity <= 0.05:
            break
        i = j + 1
    return {"final_equity": round(float(equity), 3), "wiped": wiped_at is not None,
            "wiped_date_index": int(wiped_at) if wiped_at else None}


FAMILIES = ["RSI_FADE", "BOLL_FADE", "ICHIMOKU", "MACD", "STOCH_FADE", "SUPERTREND"]


def main() -> None:
    files = sorted(f[:-4] for f in os.listdir(UNI) if f.endswith(".csv")
                   and f not in ("SPY.csv", "VIXY.csv"))
    rows = []
    print(f"universe: {len(files)} instruments")
    for sym in files:
        got = su.load(sym)
        if not got:
            continue
        dates, px = got
        if len(px) < 600:
            continue
        cost = su.COST_PCT.get(su.KLASS.get(sym, ""), su.COST_PCT_DEFAULT) \
            if hasattr(su, "COST_PCT_DEFAULT") else 0.03
        # screen_universe carries the cost inside its own loader; fall back to the manifest value
        cost = getattr(su, "COSTS", {}).get(sym, cost)
        for fam in FAMILIES:
            pos = rule_positions(fam, px)
            if np.abs(pos).sum() < 10:
                continue
            pnl = su.pnl_of(px, pos, cost)
            m = su.metrics(pnl, dates)
            nl = su.null_percentile(px, pos, cost, dates, sims=200)
            rows.append({"instrument": sym, "family": fam, "source_eco": "free EA ecosystem",
                         **m, "null_pct": (nl or {}).get("pct"),
                         "null_p95": (nl or {}).get("null_p95"),
                         "bars": int(len(px))})
        print(f"  {sym}: {len(FAMILIES)} families tested")

    # martingale/grid separately, on a few instruments
    mart = []
    for sym in ["EURUSD", "SP500", "GOLD", "BTC", "NIKKEI"]:
        got = su.load(sym)
        if not got:
            continue
        _, px = got
        r = martingale_sim(px)
        mart.append({"instrument": sym, **r})
        print(f"  martingale {sym}: final equity {r['final_equity']} wiped={r['wiped']}")

    os.makedirs(ART, exist_ok=True)
    with open(os.path.join(ART, "free_ea_families.json"), "w") as f:
        json.dump({"families": rows, "martingale": mart}, f, indent=2)
    with open(os.path.join(ART, "free_ea_families.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    # per-family summary
    print("\n=== per family (median across instruments) ===")
    summ = []
    for fam in FAMILIES:
        sub = [r for r in rows if r["family"] == fam]
        if not sub:
            continue
        sh = np.array([r["sharpe"] for r in sub])
        npc = np.array([r["null_pct"] for r in sub if r["null_pct"] is not None])
        s = {"family": fam, "n": len(sub),
             "median_sharpe": round(float(np.median(sh)), 2),
             "best_sharpe": round(float(sh.max()), 2),
             "pct_positive": round(float((sh > 0).mean() * 100), 1),
             "median_null_pct": round(float(np.median(npc)), 0) if len(npc) else None,
             "pass_null95": int((npc >= 95).sum()) if len(npc) else 0}
        summ.append(s)
        print(f"  {fam:12} n={s['n']:3} median Sharpe {s['median_sharpe']:+.2f} "
              f"best {s['best_sharpe']:+.2f} positive {s['pct_positive']:5.1f}% "
              f"null>=95: {s['pass_null95']}/{s['n']}")
    with open(os.path.join(ART, "free_ea_families_summary.json"), "w") as f:
        json.dump({"summary": summ, "martingale": mart}, f, indent=2)
    print("wrote artifacts")


if __name__ == "__main__":
    main()
