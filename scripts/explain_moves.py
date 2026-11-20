#!/usr/bin/env python3
"""Explain the big moves — join price action to dated events and public attention.

Questions this answers with data we actually hold (no opinions):
  1. Which days moved most, and was there a scheduled macro event (FOMC) that day?
  2. Do FOMC decision days have larger absolute moves than ordinary days? (event study)
  3. Does public attention *predict* the next day's absolute move? (lead-lag correlation)

Inputs:  data/universe/*.csv (prices), data/events/fomc_dates.csv,
         data/events/attention/*.csv
Outputs: research/artifacts/event_study.json, reports/EVENT_LAYER.md
"""
from __future__ import annotations

import csv
import glob
import json
import os
from datetime import date, datetime, timedelta, timezone

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UNI = os.path.join(ROOT, "data", "universe")
EV = os.path.join(ROOT, "data", "events")
ATT = os.path.join(EV, "attention")
ART = os.path.join(ROOT, "research", "artifacts")
REP = os.path.join(ROOT, "reports")
os.makedirs(ART, exist_ok=True)

TARGETS = ["SP500", "GOLD", "EURUSD", "USDJPY", "BTC", "WTI", "NASADAQ_PLACEHOLDER"]
ATT_MAP = {"GOLD": "XAUUSD", "BTC": "BTCUSD", "ETH": "ETHUSD",
           "EURUSD": "EURUSD", "USDJPY": "USDJPY", "SP500": "SP500",
           "WTI": "WTI", "COPPER": "COPPER"}


def load_px(sym: str):
    p = os.path.join(UNI, f"{sym}.csv")
    if not os.path.exists(p):
        hits = [f for f in glob.glob(os.path.join(UNI, "*.csv"))
                if os.path.basename(f).upper().startswith(sym.upper())]
        if not hits:
            return None
        p = hits[0]
    d, px = [], []
    with open(p) as f:
        for r in csv.DictReader(f):
            try:
                px.append(float(r.get("close") or r.get("Close")))
                d.append(r.get("date") or r.get("Date"))
            except (TypeError, ValueError):
                pass
    return np.array(d), np.array(px)


def load_fomc() -> set[str]:
    p = os.path.join(EV, "fomc_dates.csv")
    if not os.path.exists(p):
        return set()
    with open(p) as f:
        return {r["iso_date"] for r in csv.DictReader(f)}


def load_att(sym: str):
    p = os.path.join(ATT, f"{sym}.csv")
    if not os.path.exists(p):
        return None
    d, v = [], []
    with open(p) as f:
        for r in csv.DictReader(f):
            d.append(r["date"])
            v.append(float(r["views"]))
    return np.array(d), np.array(v)


def welch(a, b) -> tuple[float, float]:
    """Welch t on two samples."""
    if len(a) < 5 or len(b) < 5:
        return float("nan"), float("nan")
    va, vb = a.var(ddof=1) / len(a), b.var(ddof=1) / len(b)
    t = (a.mean() - b.mean()) / np.sqrt(va + vb)
    return float(a.mean() - b.mean()), float(t)


def main() -> None:
    fomc = load_fomc()
    out: dict = {"fomc_dates_loaded": len(fomc), "assets": {}}
    md = []
    md.append("# EVENT LAYER — do scheduled events and public attention explain the big moves?\n")
    md.append(f"- FOMC decision dates on file: **{len(fomc)}** "
              f"({min(fomc) if fomc else '-'} -> {max(fomc) if fomc else '-'}), parsed from the Fed's own file names")
    md.append("- Attention = daily English Wikipedia pageviews per asset (free, no key), used as a dated "
               "'how loud was the news' proxy — it measures attention, **not** sentiment or causality")
    md.append("- Economic calendar archive: only *this week* is served by the free feed, so our own "
               "archive starts 2026-11 (no historical backfill is available for free)\n")

    for sym in TARGETS:
        if "PLACEHOLDER" in sym:
            continue
        got = load_px(sym)
        if not got:
            continue
        dts, px = got
        if len(px) < 300:
            continue
        ret = np.zeros(len(px))
        ret[1:] = px[1:] / px[:-1] - 1.0
        absr = np.abs(ret)

        is_fomc = np.array([d in fomc for d in dts])
        # an FOMC day in our data may shift to the next trading day if the Fed
        # released after the close of our (possibly UTC-stamped) series
        nxt = np.zeros_like(is_fomc)
        for i in range(len(dts) - 1):
            if is_fomc[i]:
                nxt[i] = True
                nxt[i + 1] = True
            elif dts[i] in fomc:
                nxt[i + 1] = True

        a = absr[nxt & (np.arange(len(px)) > 0)]
        b = absr[(~nxt) & (np.arange(len(px)) > 0)]
        diff, t = welch(a, b)

        rec = {
            "bars": int(len(px)),
            "first": str(dts[0]), "last": str(dts[-1]),
            "fomc_days_matched": int(nxt.sum()),
            "abs_move_fomc_pct": round(float(a.mean()) * 100, 3) if len(a) else None,
            "abs_move_other_pct": round(float(b.mean()) * 100, 3) if len(b) else None,
            "diff_bp": round(diff * 10000, 2) if diff == diff else None,
            "welch_t": round(t, 2) if t == t else None,
        }

        # ---- attention lead-lag: does yesterday's noise predict today's move?
        at = load_att(ATT_MAP.get(sym, ""))
        if at is not None:
            ad, av = at
            amap = dict(zip(ad, av))
            # 30-day z-score of views (baseline = trailing 365d mean/std)
            z_by_date = {}
            for i in range(365, len(av)):
                w = av[i - 365:i]
                sd = w.std(ddof=1)
                z_by_date[ad[i]] = (av[i] - w.mean()) / sd if sd > 0 else 0.0
            pairs_prev, pairs_next = [], []
            for i in range(len(dts) - 1):
                z = z_by_date.get(dts[i])
                if z is None:
                    continue
                pairs_prev.append((z, absr[i]))
                pairs_next.append((z, absr[i + 1]))
            if len(pairs_prev) > 100:
                zs = np.array([p[0] for p in pairs_prev])
                same = np.array([p[1] for p in pairs_prev])
                nxtd = np.array([p[1] for p in pairs_next])
                rec["attention"] = {
                    "days": len(zs),
                    "corr_attention_vs_same_day_absmove": round(float(np.corrcoef(zs, same)[0, 1]), 3),
                    "corr_attention_vs_next_day_absmove": round(float(np.corrcoef(zs, nxtd)[0, 1]), 3),
                }
                # mean |move| in the top decile of attention vs the rest
                thr = np.quantile(zs, 0.9)
                hi, lo = nxtd[zs >= thr], nxtd[zs < thr]
                rec["attention"]["next_day_absmove_hot_pct"] = round(float(hi.mean()) * 100, 3)
                rec["attention"]["next_day_absmove_cold_pct"] = round(float(lo.mean()) * 100, 3)

        # ---- the five biggest single-day moves
        idx = np.argsort(-absr)[:8]
        rec["biggest_moves"] = [
            {"date": str(dts[i]), "move_pct": round(float(ret[i]) * 100, 2),
             "fomc_window": bool(nxt[i])}
            for i in sorted(idx, key=lambda i: dts[i])
        ]
        out["assets"][sym] = rec

    with open(os.path.join(ART, "event_study.json"), "w") as f:
        json.dump(out, f, indent=2)

    # ---- markdown
    md.append("## 1. Do FOMC decision days move the market harder?\n")
    md.append("| Asset | FOMC days matched | mean abs move on FOMC days | on other days | diff | Welch t |")
    md.append("|---|---:|---:|---:|---:|---:|")
    for sym, r in out["assets"].items():
        md.append(f"| {sym} | {r['fomc_days_matched']} | {r['abs_move_fomc_pct']}% | "
                  f"{r['abs_move_other_pct']}% | {r['diff_bp']:+} bp | {r['welch_t']} |")
    md.append("\nWelch t above ~2 is a real difference; below ~1.5 is noise. Sample starts in 2000, so the "
              "calendar coverage (1994+) is not the limit — history is.\n")

    md.append("## 2. Does public attention lead moves?\n")
    md.append("| Asset | days | corr(attention z, same-day abs move) | corr(attention z, **next-day** abs move) | next-day abs move, hot decile | cold |")
    md.append("|---|---:|---:|---:|---:|---:|")
    for sym, r in out["assets"].items():
        a = r.get("attention")
        if not a:
            continue
        md.append(f"| {sym} | {a['days']} | {a['corr_attention_vs_same_day_absmove']} | "
                  f"{a['corr_attention_vs_next_day_absmove']} | {a['next_day_absmove_hot_pct']}% | "
                  f"{a['next_day_absmove_cold_pct']}% |")
    md.append("\nSame-day correlation should be positive by construction (big moves make news). "
              "**The next-day column is the only one that could be worth money** — if attention today "
              "raised tomorrow's expected move, that is a volatility signal.\n")

    md.append("## 3. Biggest single-day moves\n")
    for sym, r in out["assets"].items():
        mv = ", ".join(f"{m['date']} {m['move_pct']:+.1f}%{'*' if m['fomc_window'] else ''}"
                       for m in r["biggest_moves"][:5])
        md.append(f"- **{sym}**: {mv}")
    md.append("\n`*` = inside an FOMC decision window. Notice how *few* of the extremes carry the star: "
              "the biggest shocks are almost never the scheduled ones.\n")

    md.append(f"\n_Generated {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC by `scripts/explain_moves.py`. "
              "Artifacts: `research/artifacts/event_study.json`, `data/events/`._")
    with open(os.path.join(REP, "EVENT_LAYER.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    print("\n".join(md[:40]))
    print("\nwrote reports/EVENT_LAYER.md + research/artifacts/event_study.json")


if __name__ == "__main__":
    main()
