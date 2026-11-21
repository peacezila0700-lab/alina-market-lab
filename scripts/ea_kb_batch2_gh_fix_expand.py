#!/usr/bin/env python3
"""Batch 2 Sub-batch:
1) Fix URL space encoding and download remaining high-value files from github_source_file (1,393).
2) Download key Strategy/Indicator/EA files from curated github_repo (75) without bulk test dumps.
3) Parse exact post authors, filenames, sizes, download counts for Priority 5 (12 .ex5 items).
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/home/user/alina_lab")
KB = ROOT / "data" / "ea_kb"
OUT_GH = KB / "sources_batch2" / "github"
OUT_GH.mkdir(parents=True, exist_ok=True)


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def encode_url(u: str) -> str:
    p = urllib.parse.urlsplit(u)
    path = urllib.parse.quote(urllib.parse.unquote(p.path), safe="/%")
    return urllib.parse.urlunsplit((p.scheme, p.netloc, path, p.query, p.fragment))


def http_get(url: str, timeout: int = 25) -> tuple[int, bytes, str]:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; AlinaResearchKB/2.0)"}
    req = urllib.request.Request(encode_url(url), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), ""
    except urllib.error.HTTPError as e:
        return e.code, b"", f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        return 0, b"", f"{type(e).__name__}: {e}"


def main() -> None:
    tasks = [json.loads(l) for l in (KB / "research_queue.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    prev_sub = json.loads((KB / "batch2_subbatch_gh_gl_ff.json").read_text(encoding="utf-8"))
    probe = json.loads((KB / "batch2_gitlab_gh75_probe.json").read_text(encoding="utf-8"))

    already_done = {
        r["url"]
        for r in prev_sub.get("github_queue_downloads", [])
        if r.get("status") == "Completed"
    }

    gh_tasks = [t for t in tasks if t["kind"] == "github_source_file"]

    # Download all remaining non-unit-test github_source_file tasks (up to 650 in this pass)
    # Specifically skip pure repetitive EA31337-classes/Indicators/tests/* and /tests/* and /env/ scripts
    # while grabbing EA31337-classes/Strategies/*, Indicators/*, EA_SCALPER_XAUUSD, peterthomet, xxvw, yulz008, geraked, EarnForex, MegaJoctan, etc.
    results = []
    downloaded = 0
    already_disk = 0
    failed = 0
    deferred_unit_tests = 0

    for t in gh_tasks:
        u = t["target"]
        if u in already_done:
            continue
        ul = u.lower()
        if ("ea31337-classes" in ul and "/tests/" in ul) or ("profitable-expert-advisor" in ul and "/env/" in ul):
            deferred_unit_tests += 1
            results.append({"task_id": t["task_id"], "status": "Deferred", "url": u, "reason": "Unit-test or RL env boilerplate deferred after repo-priority filter"})
            continue

        m = re.match(r"https://raw\.githubusercontent\.com/([^/]+/[^/]+)/[^/]+/(.+)", u)
        if not m:
            continue
        rep, rel = m.group(1), urllib.parse.unquote(m.group(2))
        dst = OUT_GH / rep.replace("/", "__") / rel.replace("/", "__")
        if dst.exists() and dst.stat().st_size > 0:
            already_disk += 1
            results.append({
                "task_id": t["task_id"], "status": "Completed", "url": u,
                "local_path": str(dst.relative_to(ROOT)),
                "sha256": hashlib.sha256(dst.read_bytes()).hexdigest(),
                "bytes": dst.stat().st_size,
            })
            continue

        if downloaded >= 650:
            # Keep remainder Pending cleanly
            continue

        st, data, err = http_get(u)
        time.sleep(0.025)
        if st == 200 and data:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
            downloaded += 1
            results.append({
                "task_id": t["task_id"], "status": "Completed", "url": u,
                "local_path": str(dst.relative_to(ROOT)),
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
            })
        else:
            failed += 1
            results.append({
                "task_id": t["task_id"],
                "status": "Blocked" if st in (401, 403, 429) else "Deferred",
                "url": u, "http_status": st, "error": err,
            })

    # --- Also grab representative real EAs from high-star curated repos in github_75_repos not yet sampled ---
    already_curated_urls = {r["url"] for r in prev_sub.get("github_curated_extra_downloads", [])}
    more_curated_repos = {
        "nkanven/MT4-MT5-Trading-EA-Collections",
        "PopovMP/FSB_Expert_Advisor_Code",
        "9nix6/Median-and-Turbo-Renko-indicator-bundle",
        "ejtraderLabs/Metatrader5-Docker",
        "cv4ever/FxTT-MT5-Free",
        "SenaDev007/A2Sniper",
        "monir71/Meta-Trader-MQL5-MQL4-Programming-Expert-Advisor-Robot",
        "GeneralTradingSarl/expert-mt5",
        "Desmath3/MT5-EA-Project",
        "hushamQA/mql5-pro-skill",
        "hungpixi/ex5-backtest",
    }
    curated_extra2 = []
    curated_dl = 0
    for rep in probe["github_75_repos"]:
        rname = rep["repo"]
        if rep.get("status") != "Completed" or rname not in more_curated_repos:
            continue
        br = rep["default_branch"]
        mqls = [p for p in rep.get("mql_files", []) if p.lower().endswith((".mq5", ".mq4", ".mqh"))]
        # Pick up to 12 most representative EAs/Indicators per giant repo (prefer Experts/Indicators over random libs)
        mqls.sort(key=lambda p: (0 if any(k in p.lower() for k in ("expert", "ea", "scalp", "grid", "trend", "orb", "smc")) else 1, p))
        for p in mqls[:12]:
            raw_u = f"https://raw.githubusercontent.com/{rname}/{urllib.parse.quote(br)}/{urllib.parse.quote(p, safe='/')}"
            if raw_u in already_curated_urls:
                continue
            dst = OUT_GH / rname.replace("/", "__") / p.replace("/", "__")
            if dst.exists():
                continue
            st, data, err = http_get(raw_u)
            time.sleep(0.025)
            if st == 200 and data:
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_bytes(data)
                curated_dl += 1
                curated_extra2.append({
                    "from_repo_task": rep["task_id"], "repo": rname, "path": p,
                    "url": raw_u, "local_path": str(dst.relative_to(ROOT)),
                    "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "status": "Completed",
                })

    # --- Deep parse ForexFactory .ex5 metadata (Priority 5: 12 items) ---
    ex5_tasks = [t for t in tasks if t["kind"] == "compiled_binary_unreadable"]
    ff_urls = sorted(set(t["discovered_from"] for t in ex5_tasks))
    ex5_enriched = []
    thread_html = {}
    for fu in ff_urls:
        st, html, _ = http_get(fu)
        if st == 200:
            thread_html[fu] = html.decode("utf-8", errors="replace")
        time.sleep(0.3)

    for t in ex5_tasks:
        fu = t["discovered_from"]
        txt = thread_html.get(fu, "")
        m_id = re.search(r"/file/(\d+)", t["target"])
        aid = m_id.group(1) if m_id else ""
        fname_m = re.search(r"\(([^)]+\.ex5)\)", t.get("notes", ""))
        fname = fname_m.group(1) if fname_m else t["target"]
        author = "Unknown"
        dl_info = ""
        post_excerpt = ""
        if aid and aid in txt:
            pos = txt.find(aid)
            pre = txt[max(0, pos - 6000):pos + 800]
            # ForexFactory username in threadpost-header__username
            users = re.findall(r'threadpost-header__username[^>]*>.*?<span[^>]*>(.*?)</span>', pre, re.S)
            if not users:
                users = re.findall(r'data-username="([^"]+)"', pre)
            if users:
                author = re.sub(r"<[^>]+>", "", users[-1]).strip()
            snippet = re.sub(r"<[^>]+>", " ", txt[max(0, pos - 1200):min(len(txt), pos + 600)])
            snippet = re.sub(r"\s+", " ", snippet).strip()
            post_excerpt = snippet[:450]
            m_dl = re.search(rf"{re.escape(fname)}\s+([0-9.,]+\s*(?:KB|MB|bytes)\s*\|\s*[0-9,]+\s*downloads)", snippet, re.I)
            if m_dl:
                dl_info = m_dl.group(1)
        ex5_enriched.append({
            "task_id": t["task_id"],
            "filename": fname,
            "source_url": t["target"],
            "thread_url": fu,
            "author": author,
            "size_and_downloads": dl_info,
            "public_thread_context": post_excerpt,
            "verification_status": "Unverified",
            "evidence_level": 5,
            "note": "Compiled .ex5 binary only; source unavailable; internal logic NOT guessed.",
        })

    out = {
        "generated_utc": now_utc(),
        "summary": {
            "gh_queue_new_downloaded": downloaded,
            "gh_queue_already_disk": already_disk,
            "gh_queue_failed": failed,
            "gh_queue_deferred_unit_tests": deferred_unit_tests,
            "curated_extra2_downloaded": curated_dl,
            "ex5_metadata_enriched": len(ex5_enriched),
        },
        "gh_queue_results": results,
        "curated_extra2": curated_extra2,
        "ex5_enriched": ex5_enriched,
    }
    (KB / "batch2_subbatch_gh_expand.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(out["summary"], indent=2))


if __name__ == "__main__":
    main()
