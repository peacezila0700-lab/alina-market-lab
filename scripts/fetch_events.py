#!/usr/bin/env python3
"""Free event / news layer — the "why did the chart move" data.

Three independent free sources, no API keys, no signup:

1. FOMC decision dates  — federalreserve.gov. Parsed from the statement-file
   names (monetaryYYYYMMDDa.htm), so the date is exact, not inferred from prose.
2. Economic calendar    — nfs.faireconomy.media weekly JSON (ForexFactory mirror).
   Only the *current* week is served, so we snapshot it every run and build our
   own archive from today forward. No historical backfill exists on this feed.
3. Public attention     — Wikimedia pageviews API, daily, per article, free.
   Used as a dated proxy for "how much the world was looking at this asset".

Outputs (all under data/events/, git-ignored except the manifests):
  fomc_dates.csv            iso_date, source_year
  ff_events.csv             date_iso, time_et, currency, title, impact, forecast, previous, first_seen
  attention/<article>.csv   date, views
  MANIFEST_EVENTS.json      what was fetched, when, how many rows, sha256
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone

UA = "Mozilla/5.0 (compatible; alina-market-lab research)"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EV = os.path.join(ROOT, "data", "events")
ATT = os.path.join(EV, "attention")
os.makedirs(ATT, exist_ok=True)


def get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def get_retry(url: str, attempts: int = 4, base_sleep: float = 12.0) -> bytes:
    """Rate-limited feeds (FF 429s aggressively) need backoff, not a bare retry."""
    last: Exception | None = None
    for i in range(attempts):
        try:
            return get(url)
        except Exception as e:                                   # noqa: BLE001
            last = e
            if "429" in str(e) or "Too Many" in str(e):
                time.sleep(base_sleep * (i + 1))
            else:
                time.sleep(1.5)
    raise last  # type: ignore[misc]


# ---------------------------------------------------------------- 1. FOMC dates
def fetch_fomc() -> list[tuple[str, str]]:
    """Every FOMC *decision* date, 1994+, proved from the Fed's own file naming.

    Two page generations:
      - modern (2011+): statement links `monetaryYYYYMMDDa.htm`, on fomccalendars.htm
      - historical (1994+): per-year pages, files named `fomcYYYYMMDDbeige...pdf`,
        with the meeting heading in a panel-heading <h5>. Conference calls are
        excluded — they are not policy decisions.
    """
    pages = ["https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"]
    pages += [f"https://www.federalreserve.gov/monetarypolicy/fomchistorical{y}.htm"
              for y in range(1994, 2027)]

    dates: dict[str, str] = {}

    def add(iso: str, src: str) -> None:
        y, m, d = iso[:4], iso[4:6], iso[6:8]
        if not ("1990" <= y <= "2027") or not ("01" <= m <= "12") or not ("01" <= d <= "31"):
            return
        dates.setdefault(f"{y}-{m}-{d}", src)

    for url in pages:
        try:
            h = get(url).decode("utf-8", "replace")
        except Exception:                                        # noqa: BLE001
            continue                    # 404 = that year lives on the modern page
        src = "calendar" if url.endswith("fomccalendars.htm") else url[-9:-4]
        for m in re.finditer(r"monetary(\d{8})a1?\.htm", h):
            add(m.group(1), src)
        # historical pages: one panel per meeting, heading names the meeting
        for block in re.split(r"panel panel-default", h):
            head = re.search(r"<h5>(.*?)</h5>", block, re.S)
            if not head:
                continue
            title = re.sub(r"<[^>]+>", " ", head.group(1))
            if "Conference" in title.capitalize() or "call" in title.lower():
                continue
            for m in re.finditer(r"fomc(\d{8})(?:beige|greenbook|gbpt|bluebook|tealbook|minutes|memo|roster|secloan|ac)", block):
                add(m.group(1), src)
        time.sleep(0.35)             # be polite to federalreserve.gov

    rows = sorted(dates.items())
    with open(os.path.join(EV, "fomc_dates.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["iso_date", "source"])
        w.writerows(rows)
    print(f"  FOMC decision dates: {len(rows)}  ({rows[0][0] if rows else '-'} -> {rows[-1][0] if rows else '-'})")
    return rows


# ----------------------------------------------------------- 2. economic calendar
def fetch_ff() -> int:
    """Snapshot the weekly calendar feed; append new rows to our own archive."""
    try:
        raw = get_retry("https://nfs.faireconomy.media/ff_calendar_thisweek.json").decode("utf-8")
    except Exception as e:                                       # noqa: BLE001
        print(f"  calendar: feed unavailable ({e}) — archive left untouched")
        return 0
    events = json.loads(raw)
    snap = os.path.join(EV, "ff", f"ff_{date.today().isoformat()}.json")
    os.makedirs(os.path.dirname(snap), exist_ok=True)
    with open(snap, "w") as f:
        f.write(raw)

    path = os.path.join(EV, "ff_events.csv")
    seen = set()
    if os.path.exists(path):
        with open(path) as f:
            for r in csv.DictReader(f):
                seen.add((r["date_iso"], r["currency"], r["title"]))
    new = 0
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if not seen:
            w.writerow(["date_iso", "time_et", "currency", "title", "impact",
                        "forecast", "previous", "first_seen"])
        for e in events:
            dt = datetime.fromisoformat(e["date"])
            key = (dt.date().isoformat(), e.get("country", ""), e.get("title", ""))
            if key in seen:
                continue
            seen.add(key)
            w.writerow([dt.date().isoformat(), dt.strftime("%H:%M"), e.get("country", ""),
                        e.get("title", ""), e.get("impact", ""), e.get("forecast", ""),
                        e.get("previous", ""), date.today().isoformat()])
            new += 1
    print(f"  calendar: {len(events)} events in this feed, {new} new rows archived")
    return new


# --------------------------------------------------------------- 3. attention
ATTENTION = {
    "XAUUSD": "Gold_as_an_investment",
    "BTCUSD": "Bitcoin",
    "ETHUSD": "Ethereum",
    "EURUSD": "Euro",
    "USDJPY": "Japanese_yen",
    "SP500": "S%26P_500",
    "WTI": "Price_of_oil",
    "COPPER": "Copper",
}


def fetch_attention(start="2016-01-01") -> int:
    """Daily Wikipedia pageviews — a free, dated 'how loud was the news' proxy."""
    today = date.today()
    n_ok = 0
    for sym, art in ATTENTION.items():
        url = (f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
               f"en.wikipedia/all-access/user/{art}/daily/"
               f"{start.replace('-', '')}/{today.strftime('%Y%m%d')}")
        try:
            items = json.loads(get_retry(url, attempts=3, base_sleep=5.0).decode())["items"]
        except Exception as e:                                   # noqa: BLE001
            print(f"  attention {sym} ({art}) failed: {e}")
            continue
        out = os.path.join(ATT, f"{sym}.csv")
        with open(out, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date", "views"])
            for it in items:
                ts = it["timestamp"]
                w.writerow([f"{ts[:4]}-{ts[4:6]}-{ts[6:8]}", it["views"]])
        print(f"  attention {sym:8} {len(items):5} days from {art}")
        n_ok += 1
    return n_ok


def main() -> None:
    print("=== free event layer ===")
    fomc = fetch_fomc()
    ff_new = fetch_ff()
    n_att = fetch_attention()

    man = {
        "fetched_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": {
            "fomc_dates": {"url": "federalreserve.gov fomccalendars + fomchistorical{year}",
                           "rows": len(fomc)},
            "econ_calendar": {"url": "nfs.faireconomy.media/ff_calendar_thisweek.json",
                              "rows": ff_new,
                              "caveat": "current week only; archive builds forward from today"},
            "attention": {"url": "wikimedia.org pageviews API", "series": n_att,
                          "caveat": "pageviews = attention, not sentiment"},
        },
    }
    with open(os.path.join(EV, "MANIFEST_EVENTS.json"), "w") as f:
        json.dump(man, f, indent=2)
    print("wrote data/events/MANIFEST_EVENTS.json")


if __name__ == "__main__":
    main()
