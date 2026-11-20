#!/usr/bin/env python3
"""
event_pack.py — build the context pack for ONE date (or one date range) so a local model can analyse a
specific day/event without loading the whole datapack.

    python3 scripts/event_pack.py 2026-11-20
    python3 scripts/event_pack.py 2026-11-20 --days 5 --out packs/

Output: packs/<date>.json  (~20-40 KB) with, for that day:
  calendar      : every event in the window (FOMC, auctions, OPEX, month-end, NFP rule, VIX onset, shocks)
  market        : per-instrument close, 1/5/21-day returns, realised vol, ATR, distance to key levels
  levels        : pivots / prior-day / value area / swing points nearest the price
  vol_regime    : VIX curve state, slope_3m, slope_9d, VVIX percentile and the measured base rates
  carry         : curve slope (10y-3m, 10y-2y), crypto funding, perp basis if available
  news          : headlines from -3 to +3 days with entity tags
  base_rates    : conditioned forward-return medians for the state that day
  similar_days  : the 12 historical days with the closest vol-curve + trend state, with what happened next
  caveats       : everything that can mislead a reader of this specific day

Design rules (they are why this file is useful):
  * One JSON per day, self-describing, with units and as-of stamps in the payload.
  * `similar_days` is the honest replacement for forecasting: nearest-neighbour states, forward outcomes
    shown including the bad ones. No model, no fitted weights, no look-ahead — neighbours are drawn
    from days strictly before the target date.
  * Nothing here is a recommendation. The local model reads this, then decides; the numbers it needs to
    reason with are all present and none are pre-chewed into a signal.
"""
import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
UNIVERSE = ["SPY", "TLT", "IEF", "GLD", "DXY", "EURUSD", "USDJPY", "GBPUSD", "WTI", "NATGAS",
            "BTC", "ETH", "NASDAQ100", "SP500", "VIXY", "COPPER", "SILVER"]


def _read(rel, datecol=None):
    p = ROOT / rel
    if not p.exists():
        return None
    try:
        if str(p).endswith(".gz"):
            df = pd.read_csv(p)
        else:
            df = pd.read_csv(p)
    except Exception:                                            # noqa: BLE001
        return None
    dc = datecol or next((c for c in df.columns if c.lower() in
                          ("date", "dt", "ts_utc", "datetime", "ts", "observation_date", "date_utc",
                           "published", "harvested_utc")), None)
    if dc is None:
        # some of our files are written with an unnamed index column (vol_stress_features.csv); fall back
        # to the first column if it parses as dates, otherwise give up rather than guess.
        first = df.columns[0]
        try:
            if pd.to_datetime(df[first], errors="coerce").notna().mean() > 0.8:
                dc = first
        except Exception:                                        # noqa: BLE001
            pass
    if dc is None:
        return None
    df[dc] = pd.to_datetime(df[dc], errors="coerce", utc=False)
    df = df.dropna(subset=[dc]).sort_values(dc)
    df = df.set_index(dc)
    # every index in this pack is tz-naive UTC: mixing a tz-aware funding series with a naive calendar
    # date raises "Invalid comparison between dtype=datetime64[ns, UTC] and Timestamp" (seen, fixed).
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_convert("UTC").tz_localize(None)
    return df


def px_series(sym):
    for rel, col in ((f"data/universe/{sym}.csv", None), (f"data/broad/{sym}.csv", None)):
        df = _read(rel)
        if df is not None and len(df) > 100:
            c = next((x for x in df.columns if x.lower() in ("close", "adj close", "price")), None)
            if c:
                return df[c].astype(float)
    return None


def nearest(level, price):
    if level is None or price is None or not np.isfinite(level) or not np.isfinite(price):
        return None
    return round(float((price - level) / price * 100), 3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("date", help="YYYY-MM-DD (the day to analyse)")
    ap.add_argument("--days", type=int, default=3, help="half-window for news around the date")
    ap.add_argument("--out", default="packs")
    args = ap.parse_args()
    day = pd.Timestamp(args.date).normalize()
    outdir = ROOT / args.out
    outdir.mkdir(parents=True, exist_ok=True)

    pack = {"date": args.date, "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "how_to_read": "units are stated per field; percent values are in percent, prices in quote units",
            "caveats": [
                "All market series are daily closes; a decision on this date can only use data up to the "
                "prior close (see leak_rule per dataset in catalog.json).",
                "similar_days uses days strictly BEFORE the target date, so it is not look-ahead, but the "
                "neighbour count is small (12) — read the spread of outcomes, not the average.",
                "No field here is a recommendation; base rates are priors measured on overlapping windows "
                "with the stated n_effective."]}

    # ---- calendar
    ev = _read("data/events/event_calendar_full.csv")
    if ev is not None:
        win = ev[(ev.index >= day - pd.Timedelta(days=args.days)) & (ev.index <= day + pd.Timedelta(days=args.days))]
        pack["calendar"] = {"window_days": args.days,
                            "events": [{k: (str(v)[:60] if not isinstance(v, (int, float, np.floating))
                                            else round(float(v), 4)) for k, v in row.items() if pd.notna(v)}
                                       for row in win.reset_index().to_dict("records")]}
    # ---- market snapshot
    mkt = {}
    for sym in UNIVERSE:
        s = px_series(sym)
        if s is None or len(s) < 30:
            continue
        s = s[s.index <= day]
        if len(s) < 30:
            continue
        r = s.pct_change()
        c = float(s.iloc[-1])
        atr = float((s.diff().abs()).rolling(14).mean().iloc[-1]) if len(s) > 20 else None
        mkt[sym] = {
            "close": round(c, 4),
            "ret_1d_pct": round(float(r.iloc[-1]) * 100, 3),
            "ret_5d_pct": round(float(s.iloc[-1] / s.iloc[-6] - 1) * 100, 3) if len(s) > 6 else None,
            "ret_21d_pct": round(float(s.iloc[-1] / s.iloc[-22] - 1) * 100, 3) if len(s) > 22 else None,
            "rv20_ann_pct": round(float(r.tail(20).std() * np.sqrt(252) * 100), 2),
            "atr14": round(atr, 4) if atr else None,
            "vs_ma50_pct": round(float(c / s.tail(50).mean() - 1) * 100, 2) if len(s) >= 50 else None,
            "vs_ma200_pct": round(float(c / s.tail(200).mean() - 1) * 100, 2) if len(s) >= 200 else None,
        }
    pack["market"] = mkt

    # ---- levels for the same day (nearest few)
    lv = _read("data/levels/levels_history.csv")
    if lv is not None:
        sub = lv[lv.index <= day]
        if len(sub):
            lastdt = sub.index.max()
            row = sub[sub.index == lastdt]
            pack["levels"] = {"as_of": str(lastdt.date()),
                              "rows": [{k: (float(v) if isinstance(v, (int, float, np.floating)) else str(v))
                                        for k, v in r.items() if pd.notna(v)} for r in row.to_dict("records")][:30]}

    # ---- vol regime + measured base rates
    vt = _read("data/collect/vol_stress_features.csv")
    if vt is not None:
        sub = vt[vt.index <= day]
        if len(sub):
            last = sub.iloc[-1]
            pack["vol_regime"] = {k: (round(float(last[k]), 4) if pd.notna(last[k]) else None)
                                  for k in ("vix", "slope_3m", "slope_9d", "vvix", "vvix_pct", "skew", "inverted_3m")
                                  if k in last.index}
            pack["vol_regime"]["reading"] = (
                "inverted curve: stress is now, not later" if (last.get("slope_3m") or 0) > 1
                else "normal curve: near-term stress priced below 3-month")
    # base-rates files have no date column, so they cannot go through _read() (which requires one)
    brp = ROOT / "data/facts/vol_regime_base_rates.csv"
    br = pd.read_csv(brp) if brp.exists() else None
    if br is not None and "vol_regime" in pack:
        slope = pack["vol_regime"].get("slope_3m")
        if slope is not None:
            bucket = ("<0.85 contango" if slope < 0.85 else "0.85-1.00" if slope < 1.0
                      else "1.00-1.10" if slope < 1.10 else ">1.10 inverted")
            sel = br[(br["conditioner"] == "VIX/VIX3M slope") & (br["bucket"] == bucket)]
            pack["base_rates"] = {"condition": f"VIX/VIX3M slope = {slope:.3f} ({bucket})",
                                  "rows": [{k: (float(v) if isinstance(v, (int, float, np.floating)) else str(v))
                                            for k, v in r.items()} for r in sel.to_dict("records")]}

    # ---- carry
    yc = _read("data/collect/treasury_yield_curve_full.csv")
    carry = {}
    if yc is not None:
        sub = yc[yc.index <= day]
        if len(sub):
            cols = {c.strip(): c for c in sub.columns}
            try:
                last = sub.iloc[-1]
                carry["ust_3m"] = round(float(last[cols["3 Mo"]]), 3)
                carry["ust_2y"] = round(float(last[cols["2 Yr"]]), 3)
                carry["ust_10y"] = round(float(last[cols["10 Yr"]]), 3)
                carry["slope_10y_3m"] = round(carry["ust_10y"] - carry["ust_3m"], 3)
                carry["slope_10y_2y"] = round(carry["ust_10y"] - carry["ust_2y"], 3)
            except Exception:                                    # noqa: BLE001
                pass
    fund = _read("data/collect/okx_BTCUSDT_funding_deep.csv")
    if fund is not None and len(fund):
        sub = fund[fund.index <= day + pd.Timedelta(days=1)]
        if len(sub):
            fr = pd.to_numeric(sub["fundingRate"], errors="coerce").dropna()
            if len(fr):
                carry["btc_funding_per_8h_pct"] = round(float(fr.iloc[-1]) * 100, 5)
                carry["btc_funding_annualised_pct"] = round(float(fr.tail(21).mean()) * 3 * 365 * 100, 2)
    if carry:
        pack["carry"] = carry

    # ---- news
    nh = _read("data/news/headlines.csv")
    if nh is not None:
        win = nh[(nh.index >= day - pd.Timedelta(days=args.days)) & (nh.index <= day + pd.Timedelta(days=args.days))]
        pack["news"] = {"window_days": args.days, "count": int(len(win)),
                        "headlines": [{k: str(v)[:180] for k, v in r.items() if pd.notna(v)}
                                      for r in win.tail(60).to_dict("records")]}

    # ---- similar days (nearest neighbour on vol-curve + trend state), strictly before the target
    spy = px_series("SPY")
    if spy is not None and vt is not None:
        df = pd.DataFrame({"spy": spy})
        df["rv20"] = df["spy"].pct_change().rolling(20).std() * np.sqrt(252)
        df["ma50_gap"] = df["spy"] / df["spy"].rolling(50).mean() - 1
        df["ma200_gap"] = df["spy"] / df["spy"].rolling(200).mean() - 1
        df = df.join(vt[["slope_3m", "vvix_pct"]], how="left").ffill()
        feats = ["rv20", "slope_3m", "vvix_pct", "ma50_gap", "ma200_gap"]
        d = df.dropna(subset=feats)
        past = d[d.index < day]
        if len(past) > 300 and day <= d.index.max() + pd.Timedelta(days=7):
            target = d[d.index <= day]
            if len(target):
                t = target.iloc[-1]
                z = (past[feats] - past[feats].mean()) / past[feats].std()
                zt = (t[feats] - past[feats].mean()) / past[feats].std()
                dist = ((z - zt) ** 2).sum(axis=1).pow(0.5).sort_values()
                sims = []
                for dt_ in dist.index[:12]:
                    i = d.index.get_loc(dt_)
                    if i + 21 >= len(d):
                        continue
                    fwd21 = float(d["spy"].iloc[i + 21] / d["spy"].iloc[i] - 1) * 100
                    fwd5 = float(d["spy"].iloc[i + 5] / d["spy"].iloc[i] - 1) * 100
                    sims.append({"date": str(dt_.date()), "distance": round(float(dist[dt_]), 2),
                                 "fwd5d_pct": round(fwd5, 2), "fwd21d_pct": round(fwd21, 2)})
                if sims:
                    f21 = [s["fwd21d_pct"] for s in sims]
                    pack["similar_days"] = {"method": "nearest 12 days on z-scored (rv20, slope_3m, vvix_pct, "
                                                      "ma50 gap, ma200 gap), drawn only from days before the target",
                                            "neighbours": sims,
                                            "fwd21_summary": {"median_pct": round(float(np.median(f21)), 2),
                                                              "min_pct": round(float(np.min(f21)), 2),
                                                              "max_pct": round(float(np.max(f21)), 2),
                                                              "pct_positive": round(float(np.mean([x > 0 for x in f21])) * 100, 0),
                                                              "n": len(f21)}}

    path = outdir / f"{args.date}.json"
    path.write_text(json.dumps(pack, indent=1, default=str))
    kb = path.stat().st_size / 1024
    print(f"  event pack -> {path}  ({kb:.0f} KB)")
    for k in ("calendar", "market", "levels", "vol_regime", "carry", "news", "similar_days", "base_rates"):
        if k in pack:
            n = len(pack[k]) if isinstance(pack[k], (list, dict)) else 1
            print(f"    {k:<13} present ({len(pack[k])} entries)" if isinstance(pack[k], (list, dict)) else f"    {k:<13} present")
        else:
            print(f"    {k:<13} MISSING")


if __name__ == "__main__":
    main()
