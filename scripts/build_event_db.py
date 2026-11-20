#!/usr/bin/env python3
"""B1 — EVENT DATABASE + REACTION STATISTICS: what actually happens around catalysts.

Three event families, deliberately kept separate because their date confidence differs:

  1. HARD-SCHEDULED, exact & official
     - FOMC decisions            (parsed from the Fed's own file names, 1994→2026)
     - Treasury auctions          (Treasury Fiscal Data API: date + bid-to-cover + high yield)
     - Monthly/quarterly options expiry (3rd Friday) and month-end/quarter-end (calendar rules)
  2. RULE-DERIVED, ~90-95% exact, flagged `date_confidence=med`
     - NFP = first Friday of the month (BLS targets it; holiday weeks occasionally shift it)
     - CPI is NOT included: BLS blocks this sandbox and a wrong date destroys an event study.
  3. DATA-DERIVED (state-triggered, i.e. "the crisis / drama" family)
     - VIX first crossing above 30 after a spell below 30   (regime-onset)
     - |SPY daily return| > 2.5σ of a 63-day trailing σ     (shock / squeeze days)

Every number produced here is measured on this repo's own price files. The event date is always
KNOWN IN ADVANCE for families 1–2 (they are scheduled), so an event window is not look-ahead; for
family 3 the trigger is only known at that day's close, so forward windows start at the NEXT close.

Outputs
  data/events/event_calendar_full.csv   one row per event
  data/events/event_stats.csv           tidy reaction statistics
  data/events/EVENT_STATS.md            human/AI-readable summary
  data/events/MANIFEST_EVENTS_FULL.json provenance + counts
"""
from __future__ import annotations

import io
import json
import os
import urllib.request
from datetime import datetime, timezone

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "events")
os.makedirs(OUT, exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"

ASSETS = {"SPY": "data/universe/SPY.csv", "TLT": "data/universe/TLT.csv",
          "GLD": "data/universe/GOLD.csv", "DXY": "data/universe/DXY.csv",
          "BTC": "data/universe/BTC.csv", "EURUSD": "data/official/EURUSD_ECB_D.csv"}
WINDOWS = {"d0": 0, "d1": 1, "d5": 5, "d20": 20}


def load_px(rel: str) -> pd.Series:
    df = pd.read_csv(os.path.join(ROOT, rel))
    d = "date" if "date" in df.columns else df.columns[0]
    c = "close" if "close" in df.columns else df.columns[1]
    s = pd.Series(df[c].values, index=pd.to_datetime(df[d], errors="coerce")).astype(float)
    return s[~s.index.duplicated()].sort_index().dropna()


def fetch_auctions() -> pd.DataFrame:
    """Treasury coupon auctions 2010→ with demand metrics. Manual page loop: the API's `links.next`
    URL breaks urllib (404) — paging by page[number] works."""
    base = ("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/auctions_query"
            "?fields=auction_date,security_type,security_term,offering_amt,total_accepted,"
            "bid_to_cover_ratio,high_yield,primary_dealer_accepted"
            "&filter=auction_date:gte:2010-01-01&sort=auction_date&page%5Bsize%5D=1000")
    out = []
    for page in range(1, 6):
        url = f"{base}&page%5Bnumber%5D={page}"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                j = json.loads(r.read())
        except Exception as e:                                    # noqa: BLE001
            print(f"    page {page} failed: {e}")
            break
        data = j.get("data", [])
        out += data
        if len(data) < 1000:
            break
    df = pd.DataFrame(out)
    if df.empty:
        return df
    df["auction_date"] = pd.to_datetime(df["auction_date"], errors="coerce")
    df = df.dropna(subset=["auction_date"])
    df["security_term"] = df["security_term"].astype(str)
    df = df[df.security_term.str.contains("10-Year|30-Year|2-Year|5-Year|7-Year", regex=True, na=False)]
    df["bid_to_cover_ratio"] = pd.to_numeric(df.bid_to_cover_ratio, errors="coerce")
    return df.sort_values("auction_date")


def build_calendar() -> pd.DataFrame:
    ev = []

    # 1a. FOMC (already parsed from the Fed's own site)
    p = os.path.join(OUT, "fomc_dates.csv")
    if os.path.exists(p):
        f = pd.read_csv(p)
        for d in pd.to_datetime(f.iloc[:, 0], errors="coerce").dropna():
            ev.append({"date": d, "event": "FOMC", "detail": "decision", "date_confidence": "high",
                       "known_in_advance": True})

    # 1b. Treasury auctions (with demand metrics)
    try:
        au = fetch_auctions()
        for _, r in au.iterrows():
            ev.append({"date": r.auction_date, "event": "AUCTION",
                       "detail": f'{r.security_term} btc={r.bid_to_cover_ratio:g}',
                       "date_confidence": "high", "known_in_advance": True,
                       "bid_to_cover": r.bid_to_cover_ratio, "high_yield": pd.to_numeric(r.high_yield, errors="coerce")})
        print(f"  auctions: {len(au)} ({au.auction_date.min().date()} → {au.auction_date.max().date()})")
    except Exception as e:                                        # noqa: BLE001
        print(f"  auctions FAILED: {e}")

    # 1c. option expiry (3rd Friday), month-end, quarter-end — exact calendar rules
    days = pd.bdate_range("2005-01-03", "2026-12-31")
    third_fridays = [d for d in days if d.weekday() == 4 and 15 <= d.day <= 21]
    for d in third_fridays:
        ev.append({"date": d, "event": "OPEX", "detail": "3rd Friday", "date_confidence": "high",
                   "known_in_advance": True})
    me = pd.Series(days, index=days).groupby([days.year, days.month]).max()
    for d in me:
        ev.append({"date": d, "event": "MONTH_END", "detail": "last business day", "date_confidence": "high",
                   "known_in_advance": True})
    qe = pd.Series(days, index=days).groupby([days.year, days.quarter]).max()
    for d in qe:
        ev.append({"date": d, "event": "QUARTER_END", "detail": "last business day of quarter",
                   "date_confidence": "high", "known_in_advance": True})

    # 2. NFP = first Friday (flagged)
    for y in range(2005, 2027):
        for m in range(1, 13):
            fridays = [d for d in pd.bdate_range(f"{y}-{m:02d}-01", f"{y}-{m:02d}-28") if d.weekday() == 4]
            if fridays:
                ev.append({"date": fridays[0], "event": "NFP_approx", "detail": "first Friday (rule)",
                           "date_confidence": "med", "known_in_advance": True})
    return pd.DataFrame(ev).drop_duplicates(subset=["date", "event"]).sort_values("date")


def build_trigger_events(spy: pd.Series, vix: pd.Series) -> pd.DataFrame:
    """State-triggered families: VIX regime onset, and >2.5σ shock days."""
    ev = []
    v = vix.reindex(spy.index).ffill()
    above = v >= 30
    onset = above & ~above.shift(1).fillna(False)
    for d in v[onset].index:
        ev.append({"date": d, "event": "VIX_ONSET30", "detail": f"vix={v.loc[d]:.1f}",
                   "date_confidence": "high", "known_in_advance": False})
    r = spy.pct_change()
    sig = r.rolling(63, min_periods=40).std()
    shock = (r.abs() > 2.5 * sig) & (sig > 0)
    for d in r[shock].index:
        ev.append({"date": d, "event": "SHOCK_2.5SIG", "detail": f"ret={r.loc[d]:+.3%}",
                   "date_confidence": "high", "known_in_advance": False})
    return pd.DataFrame(ev)


def main() -> None:
    px = {k: load_px(v) for k, v in ASSETS.items()}
    spy, vix = px["SPY"], load_px("data/official/VIX_CBOE_D.csv")

    cal = pd.concat([build_calendar(), build_trigger_events(spy, vix)], ignore_index=True)
    cal = cal.sort_values("date").drop_duplicates(subset=["date", "event"], keep="first")
    cal.to_csv(os.path.join(OUT, "event_calendar_full.csv"), index=False, date_format="%Y-%m-%d")
    print(f"calendar: {len(cal)} events, {cal.event.nunique()} types")
    print(cal.groupby("event").date.agg(["min", "max", "count"]).to_string())

    # ---- reaction statistics
    rows = []
    for name, s in px.items():
        r = s.pct_change()
        idx = s.index
        base_abs = r.abs().mean()
        for win, h in WINDOWS.items():
            fwd = (s.shift(-h) / s - 1.0) if h > 0 else r
            allm = fwd.dropna()
            rows.append({"event": "ALL_DAYS", "detail": "unconditional", "asset": name, "window": win,
                         "n": int(len(allm)), "mean": round(float(allm.mean()) * 100, 3),
                         "median": round(float(allm.median()) * 100, 3),
                         "pct_pos": round(float((allm > 0).mean()) * 100, 1),
                         "abs_mean": round(float(allm.abs().mean()) * 100, 3),
                         "abs_ratio_vs_all": 1.0})
        for (etype, conf), grp in cal.groupby(["event", "date_confidence"]):
            # forward window starts at the event day's close for scheduled events (known in advance),
            # and at the NEXT close for data-derived triggers (not knowable before that close)
            anchor = grp.date.values.copy()
            if not bool(grp.known_in_advance.iloc[0]):
                pos = idx.searchsorted(anchor)
                anchor = idx[np.clip(pos + 1, 0, len(idx) - 1)]
            for win, h in WINDOWS.items():
                a = pd.DatetimeIndex(pd.to_datetime(anchor))
                a = a[a.isin(idx)]
                if len(a) < 10:
                    continue
                # align on the anchor date itself, then measure forward from it
                sub = s.reindex(a)
                fwd = (s.shift(-h).reindex(a) / sub - 1.0) if h > 0 else r.reindex(a)
                fwd = fwd.dropna()
                if len(fwd) < 10:
                    continue
                d0 = r.reindex(a).dropna()
                rows.append({"event": etype, "detail": conf, "asset": name, "window": win,
                             "n": int(len(fwd)), "mean": round(float(fwd.mean()) * 100, 3),
                             "median": round(float(fwd.median()) * 100, 3),
                             "pct_pos": round(float((fwd > 0).mean()) * 100, 1),
                             "abs_mean": round(float(fwd.abs().mean()) * 100, 3),
                             "abs_ratio_vs_all": round(float(d0.abs().mean() / base_abs), 2)
                             if (win == "d0" and len(d0) > 5 and base_abs > 0) else np.nan})
    st = pd.DataFrame(rows)
    st.to_csv(os.path.join(OUT, "event_stats.csv"), index=False)

    # ---- markdown summary
    lines = ["# EVENT REACTION STATISTICS — measured on this repo's data", "",
             "Forward returns in %, measured from the event day's close (scheduled events) or the next "
             "close (data-triggered events). `abs_ratio_vs_all` = mean absolute event-day move divided by "
             "the all-days average: >1 means that event type genuinely moves the tape more than a random "
             "day.", ""]
    for et in ["FOMC", "AUCTION", "OPEX", "MONTH_END", "NFP_approx", "VIX_ONSET30", "SHOCK_2.5SIG"]:
        sub = st[(st.event == et) & (st.asset.isin(["SPY", "TLT", "GLD", "DXY"]))]
        if sub.empty:
            continue
        lines += [f"## {et}", "", "| asset | window | n | mean % | median % | %pos | |move| ratio |",
                  "|---|---|---|---|---|---|---|"]
        for _, r in sub.iterrows():
            ratio = "-" if pd.isna(r.abs_ratio_vs_all) else f"{r.abs_ratio_vs_all:.2f}"
            lines.append(f"| {r.asset} | {r.window} | {int(r.n)} | {r['mean']:+.3f} | {r['median']:+.3f} | "
                         f"{r.pct_pos:.0f} | {ratio} |")
        lines.append("")
    uncond = st[(st.event == "ALL_DAYS") & (st.asset.isin(["SPY", "TLT", "GLD", "DXY"]))]
    lines += ["## Unconditional baseline (compare against this, always)", "",
              "| asset | window | n | mean % | median % | %pos |", "|---|---|---|---|---|---|"]
    for _, r in uncond.iterrows():
        lines.append(f"| {r.asset} | {r.window} | {int(r.n)} | {r['mean']:+.3f} | {r['median']:+.3f} | {r.pct_pos:.0f} |")
    lines += ["", "## Reading rules", "",
              "- The `|move| ratio` column is the honest test of 'is this event special': the median event "
              "day should be visibly larger than a random day, otherwise the event only *sounds* important.",
              "- For directional claims compare the median against the unconditional median at the same "
              "window and require a big gap plus a consistent sign across assets.",
              "- `NFP_approx` dates are rule-derived (first Friday) and ~90-95% exact: treat its numbers as "
              "indicative. CPI is deliberately absent — BLS blocks this sandbox and a wrong date would "
              "poison the study.",
              "- `VIX_ONSET30` / `SHOCK_2.5SIG` cannot be known before the close, so their forward window "
              "starts the next day. Do not 'buy the shock day close' in a backtest."]
    with open(os.path.join(OUT, "EVENT_STATS.md"), "w") as f:
        f.write("\n".join(lines) + "\n")

    man = {"built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "events": int(len(cal)), "types": cal.event.value_counts().to_dict(),
           "assets": list(px), "windows": WINDOWS,
           "date_confidence": {"high": "official or exact calendar rule",
                               "med": "rule-derived (first Friday), ~90-95% exact"},
           "sources": {"FOMC": "federalreserve.gov calendars", "AUCTION": "Treasury Fiscal Data API",
                       "OPEX/MONTH_END/QUARTER_END": "calendar rules", "NFP_approx": "first-Friday rule",
                       "VIX_ONSET30/SHOCK": "derived from VIX/SPY"}}
    with open(os.path.join(OUT, "MANIFEST_EVENTS_FULL.json"), "w") as f:
        json.dump(man, f, indent=2)
    print(f"\nwrote event_stats.csv ({len(st)} rows) + EVENT_STATS.md")


if __name__ == "__main__":
    main()
