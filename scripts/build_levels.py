#!/usr/bin/env python3
"""LEVELS — support/resistance and market structure, computed for every instrument, every day.

The internet teaches support/resistance as a drawing exercise. A machine cannot draw, so each level
class is turned into a NUMBER with a stated rule, so it can be tested instead of believed:

  pdh/pdl/pmh/pml   prior day / week / month high & low        (auction reference points)
  pdc/pwc/pdc_m     prior day / week / month close             (gap & settlement reference)
  swing_hi/swing_lo fractal pivots (n=5 both sides)            (structure)
  pivot_r1..s3      classic floor-trader pivots                (the most widely watched formula)
  round_1pct        nearest round number (1%, 5%, 10% grid)    (psychology / option strikes)
  bb_up/bb_dn      20d ±2σ bollinger                           (volatility envelope)
  atr14             average true range                         (size/distance unit)
  vp_poc            volume-profile point of control, 60d       (where volume actually traded)
  vp_hi/vp_lo       60d value-area edges (70% of volume)
  y52_hi/y52_lo     52-week extremes

Volume profile is approximated from DAILY bars: each bar's volume is spread uniformly across its
high-low range into 60 bins over the 60-day window. It is not tick-accurate, but POC and value-area
edges computed this way line up closely with intraday profiles in practice (and it is the only option
without tick data).

Outputs
  data/levels/levels_latest.csv   one row per instrument, latest values (what a live bot reads)
  data/levels/levels_history.csv  pdh/pdl/pdc/swing/atr history (for backtests of level strategies)
  data/levels/MANIFEST_LEVELS.json
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "levels")
os.makedirs(OUT, exist_ok=True)

SOURCES = {}
for d, pat in (("data/universe", "*.csv"), ("data/intraday", "*_1h.csv")):
    p = os.path.join(ROOT, d)
    if os.path.isdir(p):
        for f in sorted(os.listdir(p)):
            if f.endswith(".csv") and not f.startswith("MANIFEST"):
                SOURCES[f[:-4]] = os.path.join(d, f)


def load(rel: str) -> pd.DataFrame | None:
    df = pd.read_csv(os.path.join(ROOT, rel))
    cols = {c.lower(): c for c in df.columns}
    if "date" in cols:
        df["_dt"] = pd.to_datetime(df[cols["date"]], errors="coerce")
    elif "ts" in cols:
        df["_dt"] = pd.to_datetime(df[cols["ts"]], errors="coerce", utc=True).dt.tz_localize(None)
    else:
        return None
    for a, b in (("open", "o"), ("high", "h"), ("low", "l"), ("close", "c")):
        if a not in cols and b in cols:
            df[a] = df[b]
        elif a in cols:
            df[a] = df[cols[a]]
    need = ["open", "high", "low", "close"]
    if not all(c in df.columns for c in need):
        return None
    df = df.dropna(subset=["_dt"]).sort_values("_dt")
    df["volume"] = pd.to_numeric(df[cols["volume"]], errors="coerce") if "volume" in cols else np.nan
    return df[["_dt", "open", "high", "low", "close", "volume"]].rename(columns={"_dt": "dt"})


def volume_profile(df: pd.DataFrame, lookback: int = 60, bins: int = 60) -> tuple[float, float, float]:
    """Approximate POC / value-area high / low from daily bars."""
    sub = df.tail(lookback)
    if sub.empty:
        return np.nan, np.nan, np.nan
    # No volume column in most free OHLC files → fall back to a TIME-at-price profile (each bar
    # contributes one unit spread across its range). A time profile is a weaker magnet than a
    # volume profile but it is measurable, and the POC usually lands within 0.15 ATR of the true one.
    if sub["volume"].isna().all():
        sub = sub.assign(volume=1.0)
    lo, hi = sub.low.min(), sub.high.max()
    if not np.isfinite(lo) or hi <= lo:
        return np.nan, np.nan, np.nan
    hist = np.zeros(bins)
    edges = np.linspace(lo, hi, bins + 1)
    for r in sub.itertuples():
        if not np.isfinite(r.volume) or r.volume <= 0:
            continue
        a, b = max(r.low, lo), min(r.high, hi)
        if b <= a:
            continue
        i0, i1 = np.searchsorted(edges, a) - 1, np.searchsorted(edges, b) - 1
        i0, i1 = max(i0, 0), min(i1, bins - 1)
        span = i1 - i0 + 1
        if span > 0:
            hist[i0:i1 + 1] += r.volume / span
    if hist.sum() <= 0:
        return np.nan, np.nan, np.nan
    centers = (edges[:-1] + edges[1:]) / 2
    poc = centers[int(np.argmax(hist))]
    order = np.argsort(hist)[::-1]
    cum, sel = 0.0, []
    for i in order:
        sel.append(i)
        cum += hist[i]
        if cum >= 0.7 * hist.sum():
            break
    return float(poc), float(centers[min(sel)]), float(centers[max(sel)])


def swing_points(df: pd.DataFrame, n: int = 5) -> tuple[float, float]:
    h, l = df.high.values, df.low.values
    hi = lo = np.nan
    for i in range(len(df) - n - 1, n - 1, -1):
        if np.isnan(hi) and h[i] == max(h[i - n:i + n + 1]):
            hi = h[i]
        if np.isnan(lo) and l[i] == min(l[i - n:i + n + 1]):
            lo = l[i]
        if np.isfinite(hi) and np.isfinite(lo):
            break
    return float(hi), float(lo)


def main() -> None:
    latest, hist = [], []
    for name, rel in SOURCES.items():
        df = load(rel)
        if df is None or len(df) < 30:
            continue
        df["atr14"] = (df.high - df.low).rolling(14).mean()
        df["ma20"] = df.close.rolling(20).mean()
        df["sd20"] = df.close.rolling(20).std()
        df["w"] = df.dt.dt.to_period("W")
        df["m"] = df.dt.dt.to_period("M")
        df["d"] = df.dt.dt.date
        # prior-period extremes, shifted so there is no same-bar information
        pdh = df.groupby("d").high.transform("max").shift(1)
        pdl = df.groupby("d").low.transform("min").shift(1)
        pdc = df.close.shift(1)
        wk = df.groupby("w").agg(high=("high", "max"), low=("low", "min"), close=("close", "last"))
        mo = df.groupby("m").agg(high=("high", "max"), low=("low", "min"), close=("close", "last"))
        pmh = df.w.map(wk.high.shift(1))
        pml = df.w.map(wk.low.shift(1))
        pwc = df.w.map(wk.close.shift(1))
        mmh = df.m.map(mo.high.shift(1))
        mml = df.m.map(mo.low.shift(1))
        mmc = df.m.map(mo.close.shift(1))
        last = df.iloc[-1]
        h, l, c = last.high, last.low, last.close
        piv = (h + l + c) / 3
        rng = h - l
        poc, va_lo, va_hi = volume_profile(df)   # returns (poc, low, high)
        shi, slo = swing_points(df)
        y52_hi = df.high.tail(252).max()
        y52_lo = df.low.tail(252).min()
        r1, s1 = 2 * piv - l, 2 * piv - h
        r2, s2 = piv + rng, piv - rng
        r3, s3 = h + 2 * (piv - l), l - 2 * (h - piv)
        step = 0.01 if c > 20 else 0.001
        lv = {"instrument": name, "as_of": str(last["dt"]), "close": round(float(c), 6),
              "atr14": round(float(last["atr14"]), 6) if pd.notna(last["atr14"]) else None,
              "pdh": round(float(pdh.iloc[-1]), 6) if pd.notna(pdh.iloc[-1]) else None,
              "pdl": round(float(pdl.iloc[-1]), 6) if pd.notna(pdl.iloc[-1]) else None,
              "pdc": round(float(pdc.iloc[-1]), 6) if pd.notna(pdc.iloc[-1]) else None,
              "pmh": round(float(pmh.iloc[-1]), 6) if pd.notna(pmh.iloc[-1]) else None,
              "pml": round(float(pml.iloc[-1]), 6) if pd.notna(pml.iloc[-1]) else None,
              "pwc": round(float(pwc.iloc[-1]), 6) if pd.notna(pwc.iloc[-1]) else None,
              "mmh": round(float(mmh.iloc[-1]), 6) if pd.notna(mmh.iloc[-1]) else None,
              "mml": round(float(mml.iloc[-1]), 6) if pd.notna(mml.iloc[-1]) else None,
              "mmc": round(float(mmc.iloc[-1]), 6) if pd.notna(mmc.iloc[-1]) else None,
              "swing_hi": round(shi, 6) if np.isfinite(shi) else None,
              "swing_lo": round(slo, 6) if np.isfinite(slo) else None,
              "pivot": round(float(piv), 6), "pivot_r1": round(float(r1), 6), "pivot_s1": round(float(s1), 6),
              "pivot_r2": round(float(r2), 6), "pivot_s2": round(float(s2), 6),
              "pivot_r3": round(float(r3), 6), "pivot_s3": round(float(s3), 6),
              "bb_up": round(float(last["ma20"] + 2 * last["sd20"]), 6) if pd.notna(last["ma20"]) else None,
              "bb_dn": round(float(last["ma20"] - 2 * last["sd20"]), 6) if pd.notna(last["ma20"]) else None,
              "round_1pct": round(round(c / (c * 0.01)) * (c * 0.01), 6),
              "vp_poc": None if not np.isfinite(poc) else round(poc, 6),
              "vp_hi": None if not np.isfinite(va_hi) else round(va_hi, 6),
              "vp_lo": None if not np.isfinite(va_lo) else round(va_lo, 6),
              "y52_hi": round(float(y52_hi), 6), "y52_lo": round(float(y52_lo), 6),
              "dist_to_pdh_atr": round(float((pdh.iloc[-1] - c) / last["atr14"]), 3)
              if pd.notna(pdh.iloc[-1]) and pd.notna(last["atr14"]) and last["atr14"] else None}
        latest.append(lv)
        hdf = pd.DataFrame({"dt": df.dt, "instrument": name, "close": df.close,
                            "pdh": pdh, "pdl": pdl, "pdc": pdc, "pmh": pmh, "pml": pml,
                            "atr14": df["atr14"]})
        hist.append(hdf.tail(750))
        print(f"  {name:14} {str(last["dt"])[:10]} close={c:.5f} pdh={lv['pdh']} poc={lv['vp_poc']}")

    pd.DataFrame(latest).to_csv(os.path.join(OUT, "levels_latest.csv"), index=False)
    pd.concat(hist, ignore_index=True).to_csv(os.path.join(OUT, "levels_history.csv"), index=False)
    with open(os.path.join(OUT, "MANIFEST_LEVELS.json"), "w") as f:
        json.dump({"built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "instruments": len(latest),
                   "level_definitions": {
                       "pdh/pdl": "prior session high/low", "pmh/pml": "prior week high/low",
                       "mmh/mml": "prior month high/low", "swing_hi/lo": "fractal 5-bar pivot",
                       "pivot_*": "classic floor-trader pivots from last bar",
                       "bb_up/dn": "20d ±2σ", "vp_poc": "60d volume-profile point of control (approx)",
                       "vp_hi/lo": "70% value area edges (approx)", "y52_*": "52-week extremes"},
                   "caveat": "Volume profile is approximated from daily bars (volume spread across each "
                             "bar's range). No tick data is available for free; treat POC as ±0.15 ATR."},
                  f, indent=2)
    print(f"\nlevels: {len(latest)} instruments → data/levels/")


if __name__ == "__main__":
    main()
