#!/usr/bin/env python3
"""
build_technical_indicators.py — one canonical TA stack for every instrument in the pack.

The point is NOT to ship "buy/sell signals" (EXP-0001 already killed 7 classic TA families on 24
instruments against a permutation null). The point is to ship the INDICATOR VALUES themselves in one
consistent, documented, look-ahead-free form, so a downstream model or a screener never has to
recompute them differently for every idea, and so every future backtest uses the same definitions.

Indicators (all computed on the close, all causal):
  sma20/50/200, ema12/26/50, rsi14, macd(12,26,9) line/signal/hist, bb20 upper/mid/lower/width/pctb,
  atr14 (+ atr14 as % of close), adx14, stoch14 %K/%D, obv slope 20, donchian20 hi/lo + position,
  keltner20 (ema20 +- 2*atr), zscore20 of close, return 1/5/21/63d, realised vol 20/63d annualised,
  distance to 52-week high/low, volume z-score 20 (where volume exists).

Uncertainty written down:
  * Volume is missing for most free OHLC files; volume-based fields (obv, vol_z) are left NaN rather
    than faked with 1.0 — a downstream user must be able to tell "no data" from "zero".
  * ETF proxies, not the underlying; adjusted-close handling differs by file, so cross-instrument
    comparisons of absolute returns should use the same file family.
  * adx/stoch use Wilder smoothing implemented here (not TA-Lib) — documented so numbers are
    reproducible; expect small differences from any other library.

Outputs
  data/technicals/latest.csv          one row per instrument, latest bar
  data/technicals/history_wide.csv    close + the most-used 12 fields, wide format by date
  data/technicals/MANIFEST_TECH.json  column dictionary + coverage + sha256-free row counts
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "technicals"


def load_ohlc(path):
    try:
        df = pd.read_csv(path)
    except Exception:                                            # noqa: BLE001
        return None
    dc = next((c for c in df.columns if c.lower() in ("date", "datetime", "ts_utc")), None)
    cc = next((c for c in df.columns if c.lower() in ("close", "adj close", "price", "bid_c")), None)
    if not dc or not cc:
        return None
    df[dc] = pd.to_datetime(df[dc], errors="coerce")
    df = df.dropna(subset=[dc]).sort_values(dc).set_index(dc)
    out = pd.DataFrame({"close": pd.to_numeric(df[cc], errors="coerce")})
    for col, name in (("high", "high"), ("low", "low"), ("volume", "volume"), ("vol", "volume")):
        if col in [c.lower() for c in df.columns] and name not in out:
            src = [c for c in df.columns if c.lower() == col][0]
            out[name] = pd.to_numeric(df[src], errors="coerce")
    if "high" not in out:
        out["high"] = out["close"]
    if "low" not in out:
        out["low"] = out["close"]
    return out.dropna(subset=["close"])


def wilder(s, n):
    return s.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def indicators(df):
    c, h, l, v = df["close"], df["high"], df["low"], df.get("volume")
    o = pd.DataFrame(index=df.index)
    o["close"] = c
    for n in (20, 50, 200):
        o[f"sma{n}"] = c.rolling(n).mean()
    for n in (12, 20, 26, 50):
        o[f"ema{n}"] = c.ewm(span=n, adjust=False, min_periods=n).mean()

    delta = c.diff()
    up = wilder(delta.clip(lower=0), 14)
    dn = wilder(-delta.clip(upper=0), 14)
    rs = up / dn.replace(0, np.nan)
    o["rsi14"] = 100 - 100 / (1 + rs)

    macd = o["ema12"] - o["ema26"]
    o["macd_line"] = macd
    o["macd_signal"] = macd.ewm(span=9, adjust=False, min_periods=9).mean()
    o["macd_hist"] = macd - o["macd_signal"]

    mid = c.rolling(20).mean()
    sd = c.rolling(20).std()
    o["bb_mid"] = mid
    o["bb_upper"] = mid + 2 * sd
    o["bb_lower"] = mid - 2 * sd
    o["bb_width"] = (o["bb_upper"] - o["bb_lower"]) / mid
    o["bb_pctb"] = (c - o["bb_lower"]) / (o["bb_upper"] - o["bb_lower"]).replace(0, np.nan)

    prev_c = c.shift(1)
    tr = pd.concat([h - l, (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
    o["atr14"] = wilder(tr, 14)
    o["atr14_pct"] = o["atr14"] / c * 100

    up_move, dn_move = h.diff(), -l.diff()
    plus_dm = np.where((up_move > dn_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((dn_move > up_move) & (dn_move > 0), dn_move, 0.0)
    atr = wilder(tr, 14)
    pdi = 100 * wilder(pd.Series(plus_dm, index=df.index), 14) / atr.replace(0, np.nan)
    mdi = 100 * wilder(pd.Series(minus_dm, index=df.index), 14) / atr.replace(0, np.nan)
    o["plus_di"], o["minus_di"] = pdi, mdi
    o["adx14"] = wilder(100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan), 14)

    hh, ll = h.rolling(14).max(), l.rolling(14).min()
    o["stoch_k"] = 100 * (c - ll) / (hh - ll).replace(0, np.nan)
    o["stoch_d"] = o["stoch_k"].rolling(3).mean()

    if v is not None and v.notna().sum() > 50:
        obv = (np.sign(c.diff().fillna(0)) * v.fillna(0)).cumsum()
        o["obv_slope20"] = obv.diff(20) / v.rolling(20).mean().replace(0, np.nan)
        o["vol_z20"] = (v - v.rolling(20).mean()) / v.rolling(20).std().replace(0, np.nan)
    else:
        o["obv_slope20"] = np.nan
        o["vol_z20"] = np.nan

    o["donch20_hi"] = h.rolling(20).max()
    o["donch20_lo"] = l.rolling(20).min()
    o["donch20_pos"] = (c - o["donch20_lo"]) / (o["donch20_hi"] - o["donch20_lo"]).replace(0, np.nan)
    o["kelt_upper"] = o["ema20"] + 2 * o["atr14"]
    o["kelt_lower"] = o["ema20"] - 2 * o["atr14"]
    o["zscore20"] = (c - mid) / sd.replace(0, np.nan)

    for n in (1, 5, 21, 63):
        o[f"ret{n}d"] = c.pct_change(n) * 100
    for n in (20, 63):
        o[f"rv{n}"] = c.pct_change().rolling(n).std() * np.sqrt(252) * 100
    o["dist_52w_high_pct"] = (c / c.rolling(252, min_periods=60).max() - 1) * 100
    o["dist_52w_low_pct"] = (c / c.rolling(252, min_periods=60).min() - 1) * 100
    return o


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sources = []
    for folder in ("data/broad", "data/universe", "data/stocks"):
        for p in sorted((ROOT / folder).glob("*.csv")):
            if p.name.startswith(("MANIFEST", "CLEANING")):
                continue
            sources.append(p)

    latest_rows, history = [], {}
    for p in sources:
        ohlc = load_ohlc(p)
        if ohlc is None or len(ohlc) < 210:
            continue
        ind = indicators(ohlc)
        last = ind.iloc[-1]
        row = {"symbol": p.stem, "as_of": str(ind.index[-1].date()), "close": round(float(ohlc["close"].iloc[-1]), 4),
               "rows": int(len(ind))}
        for k, val in last.items():
            if isinstance(val, (int, float, np.floating)) and np.isfinite(val):
                row[k] = round(float(val), 4)
        latest_rows.append(row)
        keep = ["close", "rsi14", "macd_hist", "bb_pctb", "atr14_pct", "adx14", "zscore20",
                "ret21d", "ret63d", "rv63", "dist_52w_high_pct", "donch20_pos"]
        # the wide history file stays ETFs/indices only: 115 single stocks x 12 fields x 2.5k dates would
        # triple it for little research value (stock studies can read data/stocks/*.csv directly).
        if p.parent.name in ("broad", "universe"):
            for k in keep:
                history.setdefault(k, {})[p.stem] = ind[k]

    latest = pd.DataFrame(latest_rows).sort_values("symbol")
    latest.to_csv(OUT / "latest.csv", index=False)

    wide = pd.DataFrame({f"{k}|{sym}": s for k, dd in history.items() for sym, s in dd.items()})
    wide = wide.sort_index()
    # 94 instruments x 12 fields x 8.7k dates is 111 MB as plain CSV -> gzip (the pack reads it the same
    # way, pandas handles .gz transparently).
    wide.round(4).to_csv(OUT / "history_wide.csv.gz", compression="gzip")

    cols = {c: ("price" if c == "close" else
                "momentum" if c.startswith(("rsi", "macd", "ret", "zscore", "donch", "bb_pctb")) else
                "volatility" if c.startswith(("atr", "rv", "bb_width")) else
                "trend" if c.startswith(("sma", "ema", "adx", "di", "kelt", "dist_52w")) else
                "volume" if c.startswith(("obv", "vol_z")) else "other") for c in latest.columns}
    (OUT / "MANIFEST_TECH.json").write_text(json.dumps({
        "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "instruments": int(len(latest)), "columns": cols,
        "notes": ["Every value is computed on the close and is causal; a signal from this table applies "
                  "to the NEXT bar.",
                  "Volume-derived columns (obv_slope20, vol_z20) are NaN where the source file has no "
                  "volume — that is 'no data', not zero.",
                  "Wilder smoothing is implemented manually; expect small differences from other libraries.",
                  "These are indicator values, not signals: EXP-0001 rejected 7 classic TA families on 24 "
                  "instruments against a permutation null."]}, indent=2))
    print(f"  technicals: {len(latest)} instruments, {len(wide.columns)} history series, "
          f"{len(wide)} dates -> {OUT}")
    top = latest[["symbol", "close", "rsi14", "adx14", "ret21d", "dist_52w_high_pct"]].head(6)
    print(top.to_string(index=False))


if __name__ == "__main__":
    main()
