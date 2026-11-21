#!/usr/bin/env python3
"""Batch 1 Recursive Multi-Source EA & Indicator Crawler.
Collects real HTML metadata and source files (.mq5/.mq4/.mqh/.py) from:
  1. MQL5 CodeBase EAs (English + non-English listings)
  2. MQL5 CodeBase Indicators
  3. MQL5 Market Commercial Listings (metadata/claims only, never bypassing .ex5)
  4. GitHub Open-Source MQL5 Repositories (including SMC/ICT/ML/frameworks)
  5. GitLab Open-Source MQL5 Repositories (fxce/mt5-libs, RoffildLibrary)
  6. ForexFactory Threads & Public .mq5 Attachments
  7. Official MQL5 Docs & Blocked-Source Audit Log

Strictly avoids paywall/CAPTCHA/login bypass. Logs every failed/blocked URL honestly.
"""

from __future__ import annotations

import csv
import hashlib
import html as html_lib
import io
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/home/user/alina_lab")
KB_DIR = ROOT / "data" / "ea_kb"
RAW_DIR = KB_DIR / "raw_pages"
SRC_DIR = KB_DIR / "sources"
TOKEN_FILE = Path("/home/user/.alina/git_token")

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def gh_token() -> str:
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text(encoding="utf-8", errors="ignore").strip()
    return os.environ.get("GITHUB_TOKEN", "").strip()


def clean_html_text(s: str) -> str:
    s = re.sub(r"<script[\s\S]*?</script>", " ", s, flags=re.I)
    s = re.sub(r"<style[\s\S]*?</style>", " ", s, flags=re.I)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"</p>|</div>|</li>|</tr>|</h[1-6]>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html_lib.unescape(s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def http_get(url: str, headers: dict[str, str] | None = None, timeout: int = 20) -> tuple[int, bytes, str]:
    hdrs = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            return int(getattr(resp, "status", 200)), data, ""
    except urllib.error.HTTPError as e:
        return int(e.code), b"", f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        return 0, b"", f"{type(e).__name__}: {e}"


def safe_slug(s: str, max_len: int = 64) -> str:
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_")
    return (s or "item")[:max_len]


def save_source_bytes(dest_dir: Path, filename: str, raw: bytes) -> dict:
    dest_dir.mkdir(parents=True, exist_ok=True)
    fn = safe_slug(Path(filename).name, 80)
    if not any(fn.lower().endswith(ext) for ext in (".mq5", ".mq4", ".mqh", ".py", ".set", ".txt", ".md")):
        fn += ".txt"
    out = dest_dir / fn
    out.write_bytes(raw)
    return {
        "local_path": str(out.relative_to(ROOT)),
        "file_name": fn,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def parse_mql5_code_page(url: str, html_text: str, kind: str) -> dict:
    title_m = re.search(r"<h1[^>]*>(.*?)</h1>", html_text, re.S)
    title = clean_html_text(title_m.group(1)) if title_m else ""
    author_m = re.search(r'href="(/en/users/[^"/]+)"[^>]*>([^<]+)<', html_text)
    author_url = ("https://www.mql5.com" + author_m.group(1)) if author_m else ""
    author_name = html_lib.unescape(author_m.group(2).strip()) if author_m else ""
    date_m = re.search(r'datetime="([^"]+)"', html_text)
    pub_date = date_m.group(1) if date_m else ""

    # Description body
    desc_m = re.search(r'<div[^>]+class="[^"]*code-description[^"]*"[^>]*>(.*?)</div>\s*<div', html_text, re.S)
    if not desc_m:
        desc_m = re.search(r'<div[^>]+id="description"[^>]*>(.*?)</div>', html_text, re.S)
    desc = clean_html_text(desc_m.group(1))[:3500] if desc_m else ""
    if not desc:
        meta_m = re.search(r'<meta\s+name="description"\s+content="([^"]+)"', html_text, re.I)
        desc = html_lib.unescape(meta_m.group(1)) if meta_m else ""

    dl_paths = sorted(set(re.findall(r'/en/code/download/\d+[^"\'\s<]+', html_text)))
    src_urls = []
    zip_urls = []
    img_urls = sorted(set(re.findall(r'https://c\.mql5\.com/18/[^"\'\s>]+\.(?:png|jpg|jpeg)', html_text)))
    for p in dl_paths:
        full = "https://www.mql5.com" + html_lib.unescape(p)
        low = p.lower()
        if low.endswith((".mq5", ".mq4", ".mqh")):
            src_urls.append(full)
        elif low.endswith(".zip"):
            zip_urls.append(full)
        elif low.endswith((".png", ".jpg", ".jpeg")) and full not in img_urls:
            img_urls.append(full)

    # Related code links on page for recursive queue
    related = sorted(set("https://www.mql5.com" + x for x in re.findall(r'href="(/en/code/\d+)"', html_text)))
    related = [r for r in related if r != url][:12]

    # Rating / views / downloads if visible
    rating_m = re.search(r'"ratingValue"\s*:\s*"?([0-9.]+)"?', html_text)
    views_m = re.search(r'Views:\s*<[^>]*>\s*([0-9\s]+)', html_text)
    return {
        "kind": kind,
        "url": url,
        "title": title,
        "author_name": author_name,
        "author_url": author_url,
        "published_at": pub_date,
        "description": desc,
        "source_urls": src_urls,
        "zip_urls": zip_urls,
        "image_urls": img_urls[:8],
        "rating": rating_m.group(1) if rating_m else "",
        "views": views_m.group(1).strip() if views_m else "",
        "related_urls": related,
    }


def parse_mql5_market_page(url: str, html_text: str) -> dict:
    title_m = re.search(r"<h1[^>]*>(.*?)</h1>", html_text, re.S)
    title = clean_html_text(title_m.group(1)) if title_m else ""
    author_m = re.search(r'href="(/en/users/[^"/]+/seller)"[^>]*>([^<]+)<', html_text)
    if not author_m:
        author_m = re.search(r'href="(/en/users/[^"/]+)"[^>]*>([^<]+)<', html_text)
    author_url = ("https://www.mql5.com" + author_m.group(1)) if author_m else ""
    author_name = html_lib.unescape(author_m.group(2).strip()) if author_m else ""
    price_m = re.search(r'([0-9\s]+)\s*USD', html_text)
    rating_m = re.search(r'"ratingValue"\s*:\s*"?([0-9.]+)"?', html_text)
    rev_m = re.search(r'"reviewCount"\s*:\s*"?([0-9]+)"?', html_text)
    demo_m = re.search(r'Demo downloaded:\s*</[^>]+>\s*<[^>]+>\s*([0-9\s]+)', html_text)
    pub_m = re.search(r'Published:\s*</[^>]+>\s*<[^>]+>\s*([^<]+)', html_text)
    desc_m = re.search(r'<div[^>]+id="description"[^>]*>(.*?)<div[^>]+id="screenshots"', html_text, re.S)
    desc = clean_html_text(desc_m.group(1))[:3500] if desc_m else clean_html_text(html_text)[:1500]
    signals = sorted(set("https://www.mql5.com" + s for s in re.findall(r'(/en/signals/\d+)', html_text)))[:6]
    return {
        "url": url,
        "title": title,
        "author_name": author_name,
        "author_url": author_url,
        "price_usd": price_m.group(1).strip() if price_m else "",
        "rating": rating_m.group(1) if rating_m else "",
        "reviews_count": rev_m.group(1) if rev_m else "",
        "demo_downloads": demo_m.group(1).strip() if demo_m else "",
        "published": clean_html_text(pub_m.group(1)) if pub_m else "",
        "description": desc,
        "signal_urls": signals,
    }


def main() -> None:
    KB_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    SRC_DIR.mkdir(parents=True, exist_ok=True)

    crawl_log: dict = {
        "started_utc": now_utc(),
        "websites_attempted": [],
        "websites_read": [],
        "websites_blocked_or_failed": [],
        "mql5_codebase_items": [],
        "mql5_non_en_listings": [],
        "mql5_market_items": [],
        "github_repos": [],
        "gitlab_repos": [],
        "forexfactory_threads": [],
        "docs_pages": [],
        "downloaded_files": [],
        "research_queue": [],
    }

    seen_urls: set[str] = set()
    queue_seen: set[str] = set()

    def queue_add(kind: str, target: str, discovered_from: str, priority: str = "medium", notes: str = "") -> None:
        key = f"{kind}::{target}"
        if key in queue_seen:
            return
        queue_seen.add(key)
        crawl_log["research_queue"].append({
            "task_id": f"Q-{len(crawl_log['research_queue']) + 1:04d}",
            "kind": kind,
            "target": target,
            "discovered_from": discovered_from,
            "priority": priority,
            "status": "pending",
            "notes": notes,
            "added_utc": now_utc(),
        })

    def fetch_and_log(url: str, category: str, headers: dict[str, str] | None = None) -> tuple[int, bytes]:
        crawl_log["websites_attempted"].append({"url": url, "category": category})
        status, data, err = http_get(url, headers=headers, timeout=20)
        if status == 200 and data:
            crawl_log["websites_read"].append({"url": url, "category": category, "status": status, "bytes": len(data)})
        else:
            crawl_log["websites_blocked_or_failed"].append({"url": url, "category": category, "status": status, "error": err})
        return status, data

    # ------------------------------------------------------------------
    # 1. MQL5 CodeBase EA Discovery (Latest Pages 1-2 + Diverse Families from CATALOG.csv)
    # ------------------------------------------------------------------
    ea_urls: list[str] = []
    for list_url in [
        "https://www.mql5.com/en/code/mt5/experts",
        "https://www.mql5.com/en/code/mt5/experts/page2",
        "https://www.mql5.com/en/code/mt5/experts/best",
    ]:
        st, b = fetch_and_log(list_url, "mql5_ea_listing")
        if st == 200:
            txt = b.decode("utf-8", "replace")
            for cid in re.findall(r'href="(/en/code/\d+)"', txt):
                full = "https://www.mql5.com" + cid
                if full not in seen_urls:
                    seen_urls.add(full)
                    ea_urls.append(full)
        time.sleep(0.15)

    # Mix in diverse families from existing CATALOG.csv so we don't only grab latest
    cat_csv = ROOT / "data" / "free_eas" / "CATALOG.csv"
    if cat_csv.exists():
        by_fam: dict[str, list[str]] = {}
        with cat_csv.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("source") == "mql5" and row.get("url"):
                    by_fam.setdefault(row.get("family", "other"), []).append(row["url"])
        for fam, urls in sorted(by_fam.items()):
            for u in urls[:6]:
                if u not in seen_urls:
                    seen_urls.add(u)
                    ea_urls.append(u)

    # Cap Batch 1 MQL5 EA deep fetch at 45 real pages, queue remainder!
    for u in ea_urls[45:]:
        queue_add("mql5_ea_page", u, "mql5_ea_listing", "medium", "Discovered in Batch 1 MQL5 listing/catalog")

    print(f"[1/7] Fetching {min(45, len(ea_urls))} MQL5 CodeBase EAs...")
    for u in ea_urls[:45]:
        st, b = fetch_and_log(u, "mql5_ea_detail")
        if st != 200:
            queue_add("retry_blocked", u, "mql5_ea_detail", "high", f"HTTP {st}")
            continue
        html_text = b.decode("utf-8", "replace")
        meta = parse_mql5_code_page(u, html_text, "EA")
        cid = u.rstrip("/").split("/")[-1]
        if meta["author_url"]:
            queue_add("developer_profile", meta["author_url"], u, "medium", f"Author: {meta['author_name']}")
        for rel in meta["related_urls"][:4]:
            if rel not in seen_urls:
                queue_add("mql5_related", rel, u, "low", "Related MQL5 item")

        downloaded_for_item = []
        dest = SRC_DIR / "mql5_ea" / cid
        for su in meta["source_urls"][:4]:
            sst, sb = fetch_and_log(su, "mql5_ea_source")
            if sst == 200 and sb:
                info = save_source_bytes(dest, su.split("/")[-1], sb)
                info["source_url"] = su
                info["parent_url"] = u
                info["author_name"] = meta["author_name"]
                info["author_url"] = meta["author_url"]
                info["item_title"] = meta["title"]
                info["item_kind"] = "EA"
                downloaded_for_item.append(info)
                crawl_log["downloaded_files"].append(info)
            time.sleep(0.1)

        # If no direct .mq5/.mqh, try extracting from .zip
        if not downloaded_for_item and meta["zip_urls"]:
            zu = meta["zip_urls"][0]
            zst, zb = fetch_and_log(zu, "mql5_ea_zip")
            if zst == 200 and zb:
                try:
                    with zipfile.ZipFile(io.BytesIO(zb)) as zf:
                        for name in zf.namelist():
                            if name.lower().endswith((".mq5", ".mq4", ".mqh")) and not name.endswith("/"):
                                data = zf.read(name)
                                info = save_source_bytes(dest, Path(name).name, data)
                                info["source_url"] = f"{zu}#{name}"
                                info["parent_url"] = u
                                info["author_name"] = meta["author_name"]
                                info["author_url"] = meta["author_url"]
                                info["item_title"] = meta["title"]
                                info["item_kind"] = "EA"
                                downloaded_for_item.append(info)
                                crawl_log["downloaded_files"].append(info)
                                if len(downloaded_for_item) >= 6:
                                    break
                except Exception as e:
                    crawl_log["websites_blocked_or_failed"].append({"url": zu, "category": "zip_extract", "status": 200, "error": str(e)})

        meta["downloaded_sources"] = downloaded_for_item
        crawl_log["mql5_codebase_items"].append(meta)
        time.sleep(0.15)

    # ------------------------------------------------------------------
    # 2. MQL5 CodeBase Indicators (Pages 1 + Best)
    # ------------------------------------------------------------------
    ind_urls: list[str] = []
    for list_url in [
        "https://www.mql5.com/en/code/mt5/indicators",
        "https://www.mql5.com/en/code/mt5/indicators/best",
    ]:
        st, b = fetch_and_log(list_url, "mql5_ind_listing")
        if st == 200:
            txt = b.decode("utf-8", "replace")
            for cid in re.findall(r'href="(/en/code/\d+)"', txt):
                full = "https://www.mql5.com" + cid
                if full not in seen_urls:
                    seen_urls.add(full)
                    ind_urls.append(full)
        time.sleep(0.15)

    for u in ind_urls[25:]:
        queue_add("mql5_ind_page", u, "mql5_ind_listing", "medium", "Discovered in Batch 1 MQL5 indicator listing")

    print(f"[2/7] Fetching {min(25, len(ind_urls))} MQL5 CodeBase Indicators...")
    for u in ind_urls[:25]:
        st, b = fetch_and_log(u, "mql5_ind_detail")
        if st != 200:
            continue
        html_text = b.decode("utf-8", "replace")
        meta = parse_mql5_code_page(u, html_text, "Indicator")
        cid = u.rstrip("/").split("/")[-1]
        if meta["author_url"]:
            queue_add("developer_profile", meta["author_url"], u, "medium", f"Indicator Author: {meta['author_name']}")

        downloaded_for_item = []
        dest = SRC_DIR / "mql5_ind" / cid
        for su in meta["source_urls"][:4]:
            sst, sb = fetch_and_log(su, "mql5_ind_source")
            if sst == 200 and sb:
                info = save_source_bytes(dest, su.split("/")[-1], sb)
                info["source_url"] = su
                info["parent_url"] = u
                info["author_name"] = meta["author_name"]
                info["author_url"] = meta["author_url"]
                info["item_title"] = meta["title"]
                info["item_kind"] = "Indicator"
                downloaded_for_item.append(info)
                crawl_log["downloaded_files"].append(info)
            time.sleep(0.1)

        if not downloaded_for_item and meta["zip_urls"]:
            zu = meta["zip_urls"][0]
            zst, zb = fetch_and_log(zu, "mql5_ind_zip")
            if zst == 200 and zb:
                try:
                    with zipfile.ZipFile(io.BytesIO(zb)) as zf:
                        for name in zf.namelist():
                            if name.lower().endswith((".mq5", ".mq4", ".mqh")) and not name.endswith("/"):
                                data = zf.read(name)
                                info = save_source_bytes(dest, Path(name).name, data)
                                info["source_url"] = f"{zu}#{name}"
                                info["parent_url"] = u
                                info["author_name"] = meta["author_name"]
                                info["author_url"] = meta["author_url"]
                                info["item_title"] = meta["title"]
                                info["item_kind"] = "Indicator"
                                downloaded_for_item.append(info)
                                crawl_log["downloaded_files"].append(info)
                                if len(downloaded_for_item) >= 4:
                                    break
                except Exception:
                    pass

        meta["downloaded_sources"] = downloaded_for_item
        crawl_log["mql5_codebase_items"].append(meta)
        time.sleep(0.15)

    # ------------------------------------------------------------------
    # 3. Non-English MQL5 CodeBase Listings (RU / JA / ZH)
    # ------------------------------------------------------------------
    print("[3/7] Fetching Multilingual MQL5 CodeBase listings (RU/JA/ZH)...")
    for lang, lurl in [
        ("ru", "https://www.mql5.com/ru/code/mt5/experts/page30"),
        ("ja", "https://www.mql5.com/ja/code/mt5/experts/page4"),
        ("zh", "https://www.mql5.com/zh/code/mt5/experts/page26"),
    ]:
        st, b = fetch_and_log(lurl, f"mql5_multilingual_{lang}")
        if st == 200:
            txt = b.decode("utf-8", "replace")
            pairs = re.findall(rf'<a href="(/{lang}/code/\d+)"[^>]*>(.*?)</a>', txt, re.S)
            items = []
            seen_l = set()
            for href, raw_t in pairs:
                t = clean_html_text(raw_t)
                if t and href not in seen_l:
                    seen_l.add(href)
                    full = "https://www.mql5.com" + href
                    items.append({"lang": lang, "url": full, "title_orig": t})
                    queue_add("mql5_multilingual_item", full, lurl, "low", f"Lang={lang}: {t[:80]}")
            crawl_log["mql5_non_en_listings"].append({"lang": lang, "url": lurl, "count": len(items), "sample": items[:20]})

    # ------------------------------------------------------------------
    # 4. MQL5 Market Commercial Listings (Metadata / Public Claims Only)
    # ------------------------------------------------------------------
    print("[4/7] Fetching MQL5 Market Commercial EA metadata...")
    mkt_urls = ["https://www.mql5.com/en/market/product/153540"]
    st, b = fetch_and_log("https://www.mql5.com/en/market/mt5/expert", "mql5_market_listing")
    if st == 200:
        txt = b.decode("utf-8", "replace")
        for mp in re.findall(r'href="(/en/market/product/\d+)"', txt):
            full = "https://www.mql5.com" + mp
            if full not in mkt_urls:
                mkt_urls.append(full)
    for mu in mkt_urls[15:]:
        queue_add("mql5_market_product", mu, "https://www.mql5.com/en/market/mt5/expert", "low", "Commercial closed-source metadata")
    for mu in mkt_urls[:15]:
        mst, mb = fetch_and_log(mu, "mql5_market_detail")
        if mst == 200:
            mmeta = parse_mql5_market_page(mu, mb.decode("utf-8", "replace"))
            crawl_log["mql5_market_items"].append(mmeta)
            if mmeta["author_url"]:
                queue_add("commercial_seller", mmeta["author_url"], mu, "low", mmeta["author_name"])
        time.sleep(0.15)

    # ------------------------------------------------------------------
    # 5. GitHub Open-Source MQL5 Repositories
    # ------------------------------------------------------------------
    print("[5/7] Crawling GitHub Open-Source MQL5 Repositories...")
    tok = gh_token()
    gh_hdrs = {"User-Agent": "ALINA-Research-KB", "Accept": "application/vnd.github+json"}
    if tok:
        gh_hdrs["Authorization"] = f"Bearer {tok}"

    target_repos = [
        "xxvw/ICT_Library_MQ5",
        "Moenabiel/memo-smt-ea",
        "SiyabongaDlamini/SmartMoney.MQ5",
        "zhutoutoutousan/profitable-expert-advisor",
        "MrOwl1011/Smc_ZOB_CISD",
        "LesleyJJ/MultiIndicatorAdvisor-public",
        "Astralchemist/Expert-Advisor-v0.5.1",
        "EA31337/EA31337",
    ]
    if cat_csv.exists():
        with cat_csv.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("source") != "mql5" and "github.com/" in row.get("url", ""):
                    slug = row["url"].split("github.com/")[-1].strip("/")
                    if slug and slug not in target_repos:
                        target_repos.append(slug)

    for slug in target_repos[22:]:
        queue_add("github_repo", f"https://github.com/{slug}", "CATALOG.csv", "medium", "Remaining GitHub MQL5 repo")

    for slug in target_repos[:22]:
        meta_url = f"https://api.github.com/repos/{slug}"
        st, mb = fetch_and_log(meta_url, "github_repo_meta", headers=gh_hdrs)
        if st != 200:
            continue
        rmeta = json.loads(mb.decode("utf-8", "replace"))
        branch = rmeta.get("default_branch", "main")
        tree_url = f"https://api.github.com/repos/{slug}/git/trees/{branch}?recursive=1"
        tst, tb = fetch_and_log(tree_url, "github_repo_tree", headers=gh_hdrs)
        mq_paths = []
        if tst == 200:
            tdata = json.loads(tb.decode("utf-8", "replace"))
            mq_paths = [
                item["path"] for item in tdata.get("tree", [])
                if item.get("type") == "blob"
                and item.get("path", "").lower().endswith((".mq5", ".mq4", ".mqh"))
                and item.get("size", 0) <= 300_000
            ]

        # Prioritize .mq5 Experts/Indicators first, then .mqh
        mq_sorted = sorted(
            mq_paths,
            key=lambda p: (0 if p.lower().endswith(".mq5") else (1 if p.lower().endswith(".mq4") else 2), len(p)),
        )
        for extra_p in mq_sorted[4:]:
            queue_add("github_source_file", f"https://raw.githubusercontent.com/{slug}/{branch}/{extra_p}", f"https://github.com/{slug}", "low", "Additional repo source file")

        downloaded_repo = []
        dest = SRC_DIR / "github" / safe_slug(slug.replace("/", "__"), 64)
        for rel_p in mq_sorted[:4]:
            raw_u = f"https://raw.githubusercontent.com/{slug}/{branch}/{urllib.parse.quote(rel_p)}"
            fst, fb = fetch_and_log(raw_u, "github_raw_source")
            if fst == 200 and fb:
                info = save_source_bytes(dest, rel_p.replace("/", "__"), fb)
                info["source_url"] = raw_u
                info["parent_url"] = rmeta.get("html_url", f"https://github.com/{slug}")
                info["author_name"] = (rmeta.get("owner") or {}).get("login", slug.split("/")[0])
                info["author_url"] = (rmeta.get("owner") or {}).get("html_url", "")
                info["item_title"] = f"{slug} :: {rel_p}"
                info["item_kind"] = "GitHub_MQL"
                info["license"] = (rmeta.get("license") or {}).get("spdx_id", "")
                downloaded_repo.append(info)
                crawl_log["downloaded_files"].append(info)

        crawl_log["github_repos"].append({
            "slug": slug,
            "html_url": rmeta.get("html_url", ""),
            "stars": rmeta.get("stargazers_count", 0),
            "forks": rmeta.get("forks_count", 0),
            "license": (rmeta.get("license") or {}).get("spdx_id", ""),
            "description": rmeta.get("description") or "",
            "updated_at": rmeta.get("updated_at", ""),
            "mq_files_total_in_tree": len(mq_paths),
            "downloaded_sources": downloaded_repo,
        })
        time.sleep(0.1)

    # ------------------------------------------------------------------
    # 6. GitLab Open-Source Repositories (fxce/mt5-libs, RoffildLibrary)
    # ------------------------------------------------------------------
    print("[6/7] Crawling GitLab Open-Source MQL5 Repositories...")
    for gl_slug, branch in [("fxce/mt5-libs", "master"), ("Roffild/RoffildLibrary", "master")]:
        enc = urllib.parse.quote(gl_slug, safe="")
        tree_url = f"https://gitlab.com/api/v4/projects/{enc}/repository/tree?recursive=true&per_page=100"
        st, tb = fetch_and_log(tree_url, "gitlab_repo_tree")
        if st != 200:
            continue
        items = json.loads(tb.decode("utf-8", "replace"))
        mq_paths = [
            x["path"] for x in items
            if x.get("type") == "blob" and x.get("path", "").lower().endswith((".mq5", ".mqh", ".py"))
        ]
        mq_sorted = sorted(mq_paths, key=lambda p: (0 if p.lower().endswith(".mq5") else 1, len(p)))
        for extra_p in mq_sorted[6:]:
            queue_add("gitlab_source_file", f"https://gitlab.com/{gl_slug}/-/raw/{branch}/{extra_p}", f"https://gitlab.com/{gl_slug}", "low", "Additional GitLab file")

        downloaded_gl = []
        dest = SRC_DIR / "gitlab" / safe_slug(gl_slug.replace("/", "__"), 64)
        for rel_p in mq_sorted[:6]:
            raw_u = f"https://gitlab.com/{gl_slug}/-/raw/{branch}/{urllib.parse.quote(rel_p)}"
            fst, fb = fetch_and_log(raw_u, "gitlab_raw_source")
            if fst == 200 and fb:
                info = save_source_bytes(dest, rel_p.replace("/", "__"), fb)
                info["source_url"] = raw_u
                info["parent_url"] = f"https://gitlab.com/{gl_slug}"
                info["author_name"] = gl_slug.split("/")[0]
                info["author_url"] = f"https://gitlab.com/{gl_slug.split('/')[0]}"
                info["item_title"] = f"{gl_slug} :: {rel_p}"
                info["item_kind"] = "GitLab_MQL"
                downloaded_gl.append(info)
                crawl_log["downloaded_files"].append(info)

        crawl_log["gitlab_repos"].append({
            "slug": gl_slug,
            "html_url": f"https://gitlab.com/{gl_slug}",
            "mq_files_total_sampled": len(mq_paths),
            "downloaded_sources": downloaded_gl,
        })

    # ------------------------------------------------------------------
    # 7. ForexFactory Threads & Blocked/Docs Audit
    # ------------------------------------------------------------------
    print("[7/7] Crawling ForexFactory threads & testing docs/blocked sources...")
    ff_threads = [
        "https://www.forexfactory.com/thread/1379620-only-mq5-and-python-eas-and-indicators-for?page=6",
        "https://www.forexfactory.com/thread/1179529-mt5-trading-bots",
        "https://www.forexfactory.com/thread/864355-lrsf-tms-expert-advisor-mt5",
    ]
    for fu in ff_threads:
        st, fb = fetch_and_log(fu, "forexfactory_thread")
        if st != 200:
            continue
        ftxt = fb.decode("utf-8", "replace")
        atts = re.findall(r'href="([^"]*attachment/file/[^"]*)"[^>]*>\s*([^<]+)', ftxt)
        mq_atts = [(a, fn.strip()) for a, fn in atts if fn.strip().lower().endswith((".mq5", ".mq4", ".mqh", ".zip"))]
        bin_atts = [(a, fn.strip()) for a, fn in atts if fn.strip().lower().endswith((".ex5", ".ex4"))]
        dl_ff = []
        dest = SRC_DIR / "forexfactory"
        for a, fn in mq_atts[:6]:
            au = "https://www.forexfactory.com" + a if a.startswith("/") else a
            ast, ab = fetch_and_log(au, "forexfactory_attachment")
            if ast == 200 and ab:
                if fn.lower().endswith(".zip"):
                    try:
                        with zipfile.ZipFile(io.BytesIO(ab)) as zf:
                            for zn in zf.namelist():
                                if zn.lower().endswith((".mq5", ".mq4", ".mqh")):
                                    info = save_source_bytes(dest, Path(zn).name, zf.read(zn))
                                    info["source_url"] = f"{au}#{zn}"
                                    info["parent_url"] = fu
                                    info["author_name"] = "ForexFactory Contributor"
                                    info["item_title"] = zn
                                    info["item_kind"] = "Forum_EA"
                                    dl_ff.append(info)
                                    crawl_log["downloaded_files"].append(info)
                    except Exception:
                        pass
                else:
                    info = save_source_bytes(dest, fn, ab)
                    info["source_url"] = au
                    info["parent_url"] = fu
                    info["author_name"] = "ForexFactory Contributor"
                    info["item_title"] = fn
                    info["item_kind"] = "Forum_EA"
                    dl_ff.append(info)
                    crawl_log["downloaded_files"].append(info)
        for a, fn in bin_atts[:6]:
            queue_add("compiled_binary_unreadable", f"https://www.forexfactory.com{a}" if a.startswith("/") else a, fu, "low", f"Compiled binary only ({fn}) - source unavailable")
        crawl_log["forexfactory_threads"].append({
            "url": fu,
            "mq_attachments_found": [fn for _, fn in mq_atts],
            "ex5_binaries_found": [fn for _, fn in bin_atts],
            "downloaded_sources": dl_ff,
        })

    # Verify MQL5 official docs + log known blocked/paywalled targets honestly
    for d_url in [
        "https://www.mql5.com/en/docs/customind/indicators_examples/draw_arrow",
        "https://www.mql5.com/en/docs/constants/objectconstants/wingdings",
        "https://www.mql5.com/en/docs/indicators",
    ]:
        st, db = fetch_and_log(d_url, "mql5_official_docs")
        if st == 200:
            crawl_log["docs_pages"].append({"url": d_url, "bytes": len(db)})

    # Test ForexPeaceArmy directly so blocked status is logged with HTTP truth
    st_fpa, _ = fetch_and_log("https://www.forexpeacearmy.com/forex-books/204/mt4-expert-advisor-scams", "forexpeacearmy_review")
    if st_fpa != 200:
        queue_add("blocked_403_manual_or_search", "https://www.forexpeacearmy.com/forex-books/204/mt4-expert-advisor-scams", "direct_crawl", "low", f"Blocked HTTP {st_fpa}")

    crawl_log["finished_utc"] = now_utc()
    crawl_log["summary"] = {
        "websites_attempted": len(crawl_log["websites_attempted"]),
        "websites_read_200": len(crawl_log["websites_read"]),
        "websites_blocked_or_failed": len(crawl_log["websites_blocked_or_failed"]),
        "mql5_codebase_items": len(crawl_log["mql5_codebase_items"]),
        "mql5_market_items": len(crawl_log["mql5_market_items"]),
        "github_repos_crawled": len(crawl_log["github_repos"]),
        "gitlab_repos_crawled": len(crawl_log["gitlab_repos"]),
        "forexfactory_threads": len(crawl_log["forexfactory_threads"]),
        "downloaded_source_files": len(crawl_log["downloaded_files"]),
        "research_queue_pending": len(crawl_log["research_queue"]),
    }

    out_json = KB_DIR / "crawl_batch1_log.json"
    out_json.write_text(json.dumps(crawl_log, indent=2, ensure_ascii=False), encoding="utf-8")
    print("DONE Batch 1 Crawl:", json.dumps(crawl_log["summary"], indent=2))


if __name__ == "__main__":
    main()
