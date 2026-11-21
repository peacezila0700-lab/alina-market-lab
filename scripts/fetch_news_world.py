#!/usr/bin/env python3
"""
fetch_news_world.py — Google News RSS as a global news wire, per topic and per country edition.

Why: the 15-outlet RSS list in fetch_news.py is Western financial media. Google News RSS is the only
free, key-less aggregator that lets you ask for an arbitrary query in an arbitrary country edition, so
this script turns "news from all countries" into a finite, repeatable job:

  topics   (global, en-US edition):
     stock market, central bank, inflation, oil price, bond yields, trade war, currency crisis,
     earnings surprise, banking stress, recession
  countries (local editions, local language where the edition supports it):
     US, UK, Germany (de), France (fr), Japan (ja), China (zh), India, Brazil (pt), Russia, Thailand (th),
     Vietnam (vi), Indonesia (id), Turkey (tr), Mexico (es), Saudi Arabia (ar), Nigeria, South Africa

Each query returns ~100 items with title, source, published time and link. We de-duplicate by title hash
so the same story from three outlets counts once, and tag entities with the same regex layer used by
fetch_news.py, so the two feeds are directly comparable.

Uncertainty written down:
  * Google News RSS is not an official API. It can rate-limit (HTTP 429), change layout, or drop
    editions without notice; every query is recorded with its status so the gap is visible.
  * Items are headlines + links only. There is no article body, so sentiment must come from a local model
    reading the titles (the pack ships entity tags, not sentiment scores, on purpose — see PITFALLS #10).
  * `published` timestamps are usually correct to the minute but occasionally absent; those rows keep a
    blank published and are excluded from the pressure series.

Outputs
  data/news/headlines_world.csv     title, source, published, query, edition, entities, link, hash
  data/news/news_world_pressure.csv daily counts per query and per country edition
  data/news/news_world_status.json  per-query status, item counts, fetch time
"""
import csv
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "news"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
BASE = "https://news.google.com/rss/search?q={q}&hl={hl}&gl={gl}&ceid={gl}:{lang}"

TOPICS = ["stock market", "central bank", "inflation data", "oil price", "bond yields",
          "trade war", "currency crisis", "earnings surprise", "banking stress", "recession risk"]

# (label, edition query suffix, hl, gl, lang) — Google editions require the hl/gl/ceid triple
EDITIONS = [
    ("US", "US", "en-US", "US", "en"),
    ("UK", "UK", "en-GB", "GB", "en"),
    ("DE", "Germany", "de", "DE", "de"),
    ("FR", "France", "fr", "FR", "fr"),
    ("JP", "Japan", "ja", "JP", "ja"),
    ("CN", "China", "zh-CN", "CN", "zh"),
    ("IN", "India", "en-IN", "IN", "en"),
    ("BR", "Brazil", "pt-BR", "BR", "pt"),
    ("RU", "Russia", "ru", "RU", "ru"),
    ("TH", "Thailand", "th", "TH", "th"),
    ("VN", "Vietnam", "vi", "VN", "vi"),
    ("ID", "Indonesia", "id", "ID", "id"),
    ("TR", "Turkey", "tr", "TR", "tr"),
    ("MX", "Mexico", "es-419", "MX", "es"),
    ("SA", "Saudi Arabia", "ar", "SA", "ar"),
    ("ZA", "South Africa", "en-ZA", "ZA", "en"),
]
ENTITIES = {
    "USD": r"\b(dollar|USD|fed|federal reserve|FOMC|treasury)\b",
    "EUR": r"\b(euro|EUR|ECB|eurozone|Lagarde)\b",
    "JPY": r"\b(yen|JPY|BOJ|Bank of Japan)\b",
    "CNY": r"\b(yuan|CNY|renminbi|PBOC|China)\b",
    "GBP": r"\b(pound|GBP|BoE|Bank of England)\b",
    "GOLD": r"\b(gold|bullion|XAU)\b",
    "OIL": r"\b(oil|crude|OPEC|Brent|WTI)\b",
    "BTC": r"\b(bitcoin|BTC|crypto)\b",
    "EQUITIES": r"\b(stocks|equities|S&P|Nasdaq|shares)\b",
    "BONDS": r"\b(bonds|yields|Treasury|gilts|JGB)\b",
    "INFLATION": r"\b(inflation|CPI|PPI|prices)\b",
    "RATES": r"\b(rate cut|rate hike|interest rate|policy rate)\b",
}


def tag_entities(text: str) -> str:
    t = text.lower()
    return "|".join(k for k, pat in ENTITIES.items() if re.search(pat, t, re.I))


def fetch(url, tries=3, timeout=40):
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/rss+xml,*/*"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:                                   # noqa: BLE001
            if a == tries - 1:
                return f"__ERR__{type(e).__name__}:{e}"[:200]
            time.sleep(2 + 2 * a)
    return "__ERR__unknown"


def parse_items(xml_text):
    items = []
    try:
        root = ET.fromstring(xml_text)
    except Exception:                                            # noqa: BLE001
        return items
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        pub = (it.findtext("pubDate") or "").strip()
        src = it.find("source")
        source = (src.text.strip() if src is not None and src.text else "google_news")
        if title:
            items.append({"title": title, "link": link, "published": pub, "source": source})
    return items


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows, status = [], []
    jobs = [("topic", t, "en-US", "US", "en") for t in TOPICS] + [("country", e[0], e[2], e[3], e[4])
                                                                 for e in EDITIONS]
    for i, (kind, label, hl, gl, lang) in enumerate(jobs, 1):
        # a country job asks for market news in that edition; a topic job asks for the topic globally
        q = "stock market OR economy OR central bank" if kind == "country" else label
        url = BASE.format(q=urllib.parse.quote(q), hl=hl, gl=gl, lang=lang)
        txt = fetch(url)
        if txt.startswith("__ERR__"):
            status.append({"kind": kind, "label": label, "status": txt, "items": 0})
            print(f"  {kind:8} {label:<12} FAIL {txt[:60]}")
            continue
        items = parse_items(txt)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for it in items:
            rows.append({"title": it["title"], "source": it["source"], "published": it["published"],
                         "query": label, "kind": kind, "edition": f"{gl}:{lang}",
                         "entities": tag_entities(it["title"]), "link": it["link"],
                         "harvested_utc": now,
                         "hash": hashlib.sha256(it["title"].lower().encode()).hexdigest()[:16]})
        status.append({"kind": kind, "label": label, "status": "OK", "items": len(items)})
        print(f"  {kind:8} {label:<12} {len(items):>3} items")
        time.sleep(0.6)

    df = pd.DataFrame(rows)
    if len(df):
        df = df.drop_duplicates(subset=["hash"]).sort_values("harvested_utc")
        df["published_dt"] = pd.to_datetime(df["published"], errors="coerce", utc=True)
        df.to_csv(OUT / "headlines_world.csv", index=False)
        press = (df.dropna(subset=["published_dt"])
                   .assign(day=lambda x: x["published_dt"].dt.date)
                   .groupby(["day", "kind", "query"]).size().reset_index(name="headlines"))
        press.to_csv(OUT / "news_world_pressure.csv", index=False)
        print(f"\n  world news: {len(df)} unique headlines from {df['source'].nunique()} outlets, "
              f"{df['query'].nunique()} queries")
        top = df["entities"].str.split("|").explode().value_counts().head(8)
        print("  entity hits:", dict(top))
    (OUT / "news_world_status.json").write_text(json.dumps(
        {"fetched_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         "jobs": status, "unique_headlines": int(len(df)) if len(df) else 0,
         "note": "Google News RSS is unofficial; every query status is recorded so failures stay visible."},
        indent=2))


if __name__ == "__main__":
    main()
