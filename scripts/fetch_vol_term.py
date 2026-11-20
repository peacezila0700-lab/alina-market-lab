#!/usr/bin/env python3
"""
fetch_vol_term.py — pull the CBOE volatility TERM STRUCTURE (free, key-less) and build the
derived stress features that nearly every serious volatility study uses.

Why this matters for the whole project: every "regime" test so far used the VIX *level*, which is
a single point on a curve. The curve's SLOPE is the actual information carrier:
  * VIX/VIX3M > 1  = inverted term structure = traders paying up for immediate protection
  * VIX9D/VIX > 1  = the stress is HERE and NOW, not a distant worry
  * VVIX high      = the options market itself is unstable (hedging demand is volatile)
An inversion is the market's own probability estimate of a near-term shock; it is the best free
onset detector available and it was missing from the pack.

Sources (all verified 200 with `curl -sL` and a browser UA):
  https://cdn.cboe.com/api/global/us_indices/daily_prices/{VIX,VIX1D,VIX9D,VIX3M,VVIX,SKEW}_History.csv
Note: the files have inconsistent CSV layouts (some rows have no comma between date and value, and
the header names differ), so the parser is regex-based rather than csv-based. Do not "fix" it into
csv.DictReader — it will silently drop half the rows.
"""
import io
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
COLLECT = ROOT / "data" / "collect"
BASE = "https://cdn.cboe.com/api/global/us_indices/daily_prices/{sym}_History.csv"
SYMS = ["VIX", "VIX1D", "VIX9D", "VIX3M", "VVIX", "SKEW"]
DATE_RE = re.compile(r"(\d{2}/\d{2}/\d{4})")


def get(sym):
    url = BASE.format(sym=sym)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
    with urllib.request.urlopen(req, timeout=45) as r:
        raw = r.read().decode("utf-8", "replace")
    rows = []
    for line in raw.splitlines()[1:]:
        m = DATE_RE.search(line)
        if not m:
            continue
        # the close is the LAST numeric token on the line
        nums = re.findall(r"-?\d+\.\d+", line)
        if not nums:
            continue
        rows.append((datetime.strptime(m.group(1), "%m/%d/%Y").date(), float(nums[-1])))
    s = pd.Series(dict(rows), name=sym)
    s.index = pd.to_datetime(s.index)
    return s.sort_index()


def main():
    frames = {}
    status = {}
    for sym in SYMS:
        try:
            s = get(sym)
            frames[sym] = s
            status[sym] = f"OK {len(s)} rows {s.index[0].date()}..{s.index[-1].date()}"
        except Exception as e:  # noqa: BLE001
            status[sym] = f"FAIL {type(e).__name__}: {e}"
        print(f"  {sym:<6} {status[sym]}")

    df = pd.DataFrame(frames).sort_index()
    COLLECT.mkdir(parents=True, exist_ok=True)
    df.to_csv(COLLECT / "vol_term_structure.csv")
    print(f"\n  wrote {COLLECT/'vol_term_structure.csv'}  {df.shape[0]} rows x {df.shape[1]} cols")

    # derived features (all causal, computed on the close)
    d = pd.DataFrame(index=df.index)
    d["vix"] = df["VIX"]
    d["slope_3m"] = df["VIX"] / df["VIX3M"]            # >1 inverted (stress now)
    d["slope_9d"] = df["VIX9D"] / df["VIX"]            # >1 front-end panic
    d["vvix"] = df["VVIX"]
    d["vvix_pct"] = d["vvix"].rolling(252, min_periods=120).rank(pct=True)
    d["skew"] = df["SKEW"]
    d["inverted_3m"] = (d["slope_3m"] > 1.0).astype(float)
    d["inv_flip_on"] = ((d["inverted_3m"] == 1) & (d["inverted_3m"].shift(1) == 0)).astype(float)
    feats = COLLECT / "vol_stress_features.csv"
    d.to_csv(feats)
    flips = int(d["inv_flip_on"].sum())
    print(f"  derived -> {feats.name}: {flips} term-structure inversion onsets since {d['slope_3m'].first_valid_index().date()}")
    print(f"  today: slope_3m {d['slope_3m'].dropna().iloc[-1]:.3f}, slope_9d {d['slope_9d'].dropna().iloc[-1]:.3f}, "
          f"vvix_pct {d['vvix_pct'].dropna().iloc[-1]:.2f}")

    (ROOT / "data" / "collect" / "vol_term_status.json").write_text(
        json.dumps({"fetched_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "status": status, "rows": int(df.shape[0])}, indent=2))


if __name__ == "__main__":
    main()
