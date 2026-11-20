#!/usr/bin/env python3
"""NEWS LAYER — multi-outlet RSS harvester with entity tagging, for a local AI to read daily.

Why RSS and not an API: every free news API needs a key and rate-limits hard (GDELT 429s, NewsAPI
100 req/day). RSS is unlimited, key-less, stable and carries the headline + timestamp + link, which
is exactly what an LLM needs to reason about "what happened, per the people who reported it".

What it produces
  data/news/headlines.csv     append-only, de-duplicated by URL hash
  data/news/news_pressure.csv daily counts per entity (a cheap numeric feature, not sentiment)
  data/news/feed_status.json   which outlets answered — so a gap is visible, not silent

Entity tagging is deliberately crude (regex on asset names, countries, central banks). A local LLM can
do better on the text itself; the counts here exist so a *quant* layer has a numeric series without
paying for an NLP model.

Outputs are append-only and idempotent: run it as often as you like (the collector runs it daily).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "news")
os.makedirs(OUT, exist_ok=True)
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120"

FEEDS = {
    # global wires & business desks
    "BBC_Business": "https://feeds.bbci.co.uk/news/business/rss.xml",
    "BBC_World": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "AlJazeera": "https://www.aljazeera.com/xml/rss/all.xml",
    "WSJ_Markets": "https://feeds.a.dj.com/rss/RSSMarketsMain.xml",
    "WSJ_Economy": "https://feeds.a.dj.com/rss/RSSWSJD.xml",
    "FT_Home": "https://www.ft.com/rss/home",
    "CNBC_Top": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "CNBC_Economy": "https://www.cnbc.com/id/20910258/device/rss/rss.html",
    "MarketWatch": "https://www.marketwatch.com/rss/topstories",
    "Investing_Markets": "https://www.investing.com/rss/news_25.rss",
    "Investing_Economy": "https://www.investing.com/rss/news_14.rss",
    "SeekingAlpha": "https://seekingalpha.com/market_currents.xml",
    # primary sources — the words that actually move markets
    "Fed_Press": "https://www.federalreserve.gov/feeds/press_all.xml",
    "ECB_Press": "https://www.ecb.europa.eu/rss/press.html",
    # regional coverage
    "BangkokPost_Biz": "https://www.bangkokpost.com/rss/data/business.xml",
    "BangkokPost_World": "https://www.bangkokpost.com/rss/data/world.xml",
}

ENTITIES = {
    "USD": r"\b(dollar|USD|greenback|DXY)\b", "EUR": r"\b(euro|EUR|Eurozone|ECB)\b",
    "JPY": r"\b(yen|JPY|BOJ|Bank of Japan)\b", "GBP": r"\b(pound|GBP|sterling|BoE)\b",
    "CNY": r"\b(yuan|CNY|renminbi|PBOC|China)\b", "GOLD": r"\b(gold|bullion|XAU)\b",
    "OIL": r"\b(oil|crude|OPEC|Brent|WTI)\b", "GAS": r"\b(natural gas|LNG|Henry Hub)\b",
    "EQUITY": r"\b(stocks?|equit(y|ies)|S&P|Nasdaq|Dow|shares)\b",
    "BONDS": r"\b(Treasur(y|ies)|yields?|bonds?|gilts|JGB)\b",
    "CRYPTO": r"\b(bitcoin|BTC|ether|ETH|crypto)\b",
    "RATES": r"\b(Fed|FOMC|rate cut|rate hike|inflation|CPI|PCE|payrolls)\b",
    "WAR": r"\b(war|strike|missile|attack|sanctions|invasion|conflict)\b",
    "TARIFF": r"\b(tariffs?|trade war|export controls?)\b",
    "BANK": r"\b(bank|banking|credit|default|liquidity|bailout)\b",
}

NS = {"atom": "http://www.w3.org/2005/Atom"}


def get(url: str, timeout: int = 20) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception as e:                                        # noqa: BLE001
        print(f"    {url.split('/')[2]}: {e}")
        return None


def parse_feed(raw: bytes) -> list[dict]:
    out = []
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return out
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        pub = (item.findtext("pubDate") or "").strip()
        desc = re.sub(r"<[^>]+>", " ", item.findtext("description") or "").strip()
        if title and link:
            out.append({"title": title, "link": link, "published": pub, "summary": desc[:400]})
    if not out:                                                   # atom feeds
        for e in root.iter("{http://www.w3.org/2005/Atom}entry"):
            title = (e.findtext("{http://www.w3.org/2005/Atom}title") or "").strip()
            link_el = e.find("{http://www.w3.org/2005/Atom}link")
            link = link_el.get("href") if link_el is not None else ""
            pub = (e.findtext("{http://www.w3.org/2005/Atom}updated") or "").strip()
            if title and link:
                out.append({"title": title, "link": link, "published": pub, "summary": ""})
    return out


def main() -> None:
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows, status = [], {}
    for name, url in FEEDS.items():
        raw = get(url)
        if not raw:
            status[name] = "FAIL"
            continue
        items = parse_feed(raw)
        status[name] = f"OK {len(items)}"
        for it in items:
            text = f"{it['title']} {it['summary']}"
            tags = [k for k, pat in ENTITIES.items() if re.search(pat, text, re.I)]
            rows.append({"harvested_utc": stamp, "source": name, "published": it["published"],
                         "title": it["title"], "summary": it["summary"],
                         "entities": "|".join(tags),
                         "hash": hashlib.sha1(it["link"].encode()).hexdigest()[:16],
                         "link": it["link"]})
        time.sleep(0.25)

    if not rows:
        print("no headlines harvested")
        return
    df = pd.DataFrame(rows)
    path = os.path.join(OUT, "headlines.csv")
    if os.path.exists(path):
        old = pd.read_csv(path)
        df = pd.concat([old, df], ignore_index=True)
    df = df.drop_duplicates(subset=["hash"], keep="first").sort_values("harvested_utc")
    df.to_csv(path, index=False)
    print(f"headlines: {len(df)} total ({len(rows)} fetched, {df.hash.nunique()} unique)")

    # numeric pressure series per day per entity (counts, not sentiment)
    df["day"] = pd.to_datetime(df.harvested_utc).dt.date.astype(str)
    recs = []
    for ent in list(ENTITIES) + ["ALL"]:
        if ent == "ALL":
            g = df.groupby("day").size()
        else:
            g = df[df.entities.fillna("").str.contains(ent)].groupby("day").size()
        for day, n in g.items():
            recs.append({"day": day, "entity": ent, "n_headlines": int(n)})
    np_path = os.path.join(OUT, "news_pressure.csv")
    pd.DataFrame(recs).to_csv(np_path, index=False)
    with open(os.path.join(OUT, "feed_status.json"), "w") as f:
        json.dump({"stamp": stamp, "feeds": status, "total_rows": int(len(df))}, f, indent=2)
    print("feeds:", {k: v for k, v in list(status.items())[:6]}, "…")


if __name__ == "__main__":
    main()
