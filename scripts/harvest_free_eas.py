#!/usr/bin/env python3
"""Harvest what people actually give away: free EAs / strategy sources.

Sources that respond without a key (verified 2026-11-20):
  - MQL5 Code Base listings  https://www.mql5.com/en/code/mt5/experts (+ /page2..)
  - GitHub repo search       https://api.github.com/search/repositories (unauthenticated)
Not available: GitHub code search (401 without token).

Output: data/free_eas/CATALOG.csv, data/free_eas/catalog.json
The point is not to run their code (we cannot compile MQL5 here) but to know what the
free ecosystem actually offers, so the families can be re-implemented and tested on the
same data as everything else.
"""
from __future__ import annotations

import csv
import json
import os
import re
import time
import urllib.request

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/122 Safari/537.36"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "free_eas")
os.makedirs(OUT, exist_ok=True)


def get(url: str, timeout: int = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "replace")


def harvest_mql5(pages: int = 6) -> list[dict]:
    rows = []
    seen = set()
    for p in range(1, pages + 1):
        url = "https://www.mql5.com/en/code/mt5/experts" + ("" if p == 1 else f"/page{p}")
        try:
            html = get(url)
        except Exception as e:                                  # noqa: BLE001
            print(f"  mql5 page {p} failed: {e}")
            continue
        # listing items: <a href="/en/code/12345">Title</a> ... downloads nearby
        for m in re.finditer(r'<a href="(/en/code/\d+)"[^>]*>(.*?)</a>', html, re.S):
            href, title = m.group(1), re.sub(r"<[^>]+>", "", m.group(2)).strip()
            if not title or len(title) < 3 or href in seen:
                continue
            seen.add(href)
            rows.append({"source": "mql5", "title": title[:120],
                         "url": "https://www.mql5.com" + href})
        time.sleep(0.5)
    return rows


GITHUB_QUERIES = [
    "metatrader5 expert advisor language:MQL5",
    "topic:mql5",
    "topic:metatrader5",
    "mt5 ea robot language:MQL5",
    "expert advisor forex language:MQL5",
]


def harvest_github() -> list[dict]:
    rows = []
    seen = set()
    for q in GITHUB_QUERIES:
        url = ("https://api.github.com/search/repositories?q="
               + urllib.parse.quote(q) + "&sort=stars&order=desc&per_page=25")
        try:
            data = json.loads(get(url))
        except Exception as e:                                  # noqa: BLE001
            print(f"  github '{q}' failed: {e}")
            continue
        for it in data.get("items", []):
            full = it["full_name"]
            if full in seen:
                continue
            seen.add(full)
            rows.append({"source": "github", "title": full, "url": it["html_url"],
                         "stars": it.get("stargazers_count", 0),
                         "desc": (it.get("description") or "")[:160],
                         "updated": (it.get("updated_at") or "")[:10]})
        time.sleep(2.0)               # unauthenticated search limit
    rows.sort(key=lambda r: -r.get("stars", 0))
    return rows


def classify(title: str, desc: str = "") -> str:
    t = (title + " " + desc).lower()
    fams = [
        ("grid/martingale", ["grid", "martingale", "averaging", "hedge", "recovery", "lot multiplier"]),
        ("scalping", ["scalp", "tick", "m1", "ping"]),
        ("breakout", ["breakout", "donchian", "channel", "range break"]),
        ("trend/MA", ["moving average", "ma cross", "trend", "supertrend", "adx", "ichimoku"]),
        ("mean-reversion", ["reversion", "rsi", "bollinger", "stochastic", "z-score", "fade"]),
        ("MACD/momentum", ["macd", "momentum", "roc"]),
        ("news/time", ["news", "session", "time filter", "calendar"]),
        ("ML/AI", ["neural", "machine learning", "lstm", "ai ", "deep"]),
    ]
    for name, keys in fams:
        if any(k in t for k in keys):
            return name
    return "other"


def main() -> None:
    print("=== MQL5 Code Base ===")
    mq = harvest_mql5()
    print(f"  {len(mq)} listings")
    print("=== GitHub ===")
    gh = harvest_github()
    print(f"  {len(gh)} repositories")
    for r in mq + gh:
        r["family"] = classify(r["title"], r.get("desc", ""))

    cats = {}
    for r in mq + gh:
        cats[r["family"]] = cats.get(r["family"], 0) + 1
    print("  by family:", dict(sorted(cats.items(), key=lambda x: -x[1])))

    with open(os.path.join(OUT, "catalog.json"), "w") as f:
        json.dump({"mql5": mq, "github": gh, "families": cats}, f, indent=2)
    with open(os.path.join(OUT, "CATALOG.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["source", "title", "family", "url", "stars", "desc", "updated"],
                           extrasaction="ignore")
        w.writeheader()
        for r in mq + gh:
            w.writerow(r)
    print(f"wrote {OUT}/CATALOG.csv")


if __name__ == "__main__":
    import urllib.parse
    main()
