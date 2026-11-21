#!/usr/bin/env python3
"""Batch 2 Sub-batch:
1) Retry 14 GitLab files politely (sleep 1.5s) after 429.
2) Audit large GitHub repos before mass download; download prioritized high-signal
   GitHub source files from the 1,393 github_source_file queue + top curated repos
   discovered in github_75_repos.
3) Verify/inspect ForexFactory threads for the 12 compiled_binary_unreadable (.ex5) items
   to record exact public metadata without guessing source logic.
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
OUT_GL = KB / "sources_batch2" / "gitlab"
OUT_GH = KB / "sources_batch2" / "github"
OUT_GL.mkdir(parents=True, exist_ok=True)
OUT_GH.mkdir(parents=True, exist_ok=True)

GIT_TOKEN = ""
tok_path = Path.home() / ".alina" / "git_token"
if tok_path.exists():
    GIT_TOKEN = tok_path.read_text(encoding="utf-8").strip()


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def http_get(url: str, github_api: bool = False, timeout: int = 25) -> tuple[int, bytes, str]:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; AlinaResearchKB/2.0)"}
    if github_api and GIT_TOKEN:
        headers["Authorization"] = f"Bearer {GIT_TOKEN}"
        headers["Accept"] = "application/vnd.github+json"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), ""
    except urllib.error.HTTPError as e:
        return e.code, b"", f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        return 0, b"", f"{type(e).__name__}: {e}"


def main() -> None:
    probe = json.loads((KB / "batch2_gitlab_gh75_probe.json").read_text(encoding="utf-8"))
    tasks = [json.loads(l) for l in (KB / "research_queue.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

    # --- 1. Polite GitLab retry for the 14 429 items ---
    gl_retries = []
    for r in probe["gitlab_35_results"]:
        if r["status"] == "Completed":
            continue
        url = r["resolved_url"]
        parts = url.split("/-/raw/")
        repo_path = parts[0].replace("https://gitlab.com/", "")
        _, rel_file = parts[1].split("/", 1)
        rel_file = urllib.parse.unquote(rel_file)
        time.sleep(1.5)
        st, data, err = http_get(url)
        if st == 200 and data:
            dst = OUT_GL / repo_path.replace("/", "__") / rel_file.replace("/", "__")
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
            gl_retries.append({
                "task_id": r["task_id"],
                "status": "Completed",
                "resolved_url": url,
                "local_path": str(dst.relative_to(ROOT)),
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
            })
        else:
            gl_retries.append({
                "task_id": r["task_id"],
                "status": "Blocked" if st in (401, 403, 429) else "Deferred",
                "resolved_url": url,
                "http_status": st,
                "error": err,
            })

    # --- 2. Download from github_source_file queue (excluding repetitive unit tests first, prioritizing EAs/Indicators/Strategies) ---
    # Check already downloaded paths across sources/ and sources_batch2/
    existing_shas: dict[str, str] = {}
    for base in (KB / "sources", KB / "sources_batch2"):
        if base.exists():
            for p in base.rglob("*"):
                if p.is_file():
                    existing_shas[str(p.relative_to(ROOT))] = hashlib.sha256(p.read_bytes()).hexdigest()

    gh_tasks = [t for t in tasks if t["kind"] == "github_source_file"]
    # Partition github_source_file into high-value trading/EA/indicator/strategy files vs pure test/boiler files
    # Target: download up to ~250 high-value files across all repos in this pass (keeping EA31337-classes/Strategies & Indicators, excluding /tests/ unit tests)
    selected_gh = []
    deferred_gh_tests = []
    for t in gh_tasks:
        u = t["target"]
        ul = u.lower()
        repo = t.get("discovered_from", "").replace("https://github.com/", "")
        if "ea31337-classes" in ul and "/tests/" in ul:
            deferred_gh_tests.append(t["task_id"])
            continue
        if "profitable-expert-advisor" in ul and "/env/" in ul:
            deferred_gh_tests.append(t["task_id"])
            continue
        selected_gh.append(t)

    # Also add high-value curated files from newly inspected 75 github_repos (excluding bulk dumps; inspect & pick representative real EAs/Indicators)
    curated_repos = {
        "yanstd888/institutional-smc-scalper-mt5",
        "GifariKemal/xaubot-ai",
        "landim32/LadinoBot",
        "n30dyn4m1c/crt-turtlesoup-ea",
        "EarnForex/Account-Protector",
        "Narfinsel/Candlestick-Pattern-Scanner",
        "6alaile/MetaTrader5-to-Telegram",
        "cv4ever/FxTT-MT5-Free",
        "GeneralTradingSarl/trading-experts",
        "jimtin/build-your-own-mt5-ea",
        "pipbolt/experts",
        "Niferu/forex-trading-robots",
        "smizxe/mt5-agent-toolkit",
        "myk-francis/expert-advisors-mql5",
        "PopovMP/FSB_Expert_Advisor_Code",
        "nkanven/MT4-MT5-Trading-EA-Collections",
    }
    extra_repo_targets = []
    for rep in probe["github_75_repos"]:
        if rep.get("status") != "Completed":
            continue
        rname = rep["repo"]
        if rname not in curated_repos:
            continue
        br = rep["default_branch"]
        mqls = rep.get("mql_files", [])
        # Cap giant collections at 15 representative files each after auditing tree
        pick = mqls[:15] if len(mqls) > 25 else mqls
        for p in pick:
            raw_u = f"https://raw.githubusercontent.com/{rname}/{urllib.parse.quote(br)}/{urllib.parse.quote(p, safe='/')}"
            extra_repo_targets.append({"repo": rname, "path": p, "raw_url": raw_u, "from_task": rep["task_id"]})

    # Download cap for this pass to keep runtime & disk clean (~300 files in one clean batch)
    gh_queue_downloads = []
    seen_urls = set()
    # Stratify across repos so all 13 queued repos + curated repos get coverage!
    by_repo_buckets: dict[str, list[dict]] = {}
    for t in selected_gh:
        rep = t.get("discovered_from", "").replace("https://github.com/", "")
        by_repo_buckets.setdefault(rep, []).append(t)

    # Round-robin pick up to 250 from github_source_file queue (prioritizing EAs, Indicators, Strategies over helpers)
    def score_gh(t: dict) -> tuple[int, str]:
        ul = t["target"].lower()
        if any(k in ul for k in ("expert", "/ea", "_ea", "scalper", "smc", "orb", "ict", "bot", "strat")):
            return (0, ul)
        if any(k in ul for k in ("indicator", "indi_", "utbot", "supertrend", "chandelier")):
            return (1, ul)
        if ul.endswith(".mq5") or ul.endswith(".mq4"):
            return (2, ul)
        return (3, ul)

    for rep in by_repo_buckets:
        by_repo_buckets[rep].sort(key=score_gh)

    picked_queue_tasks = []
    idx = 0
    while len(picked_queue_tasks) < 250:
        added_any = False
        for rep, lst in sorted(by_repo_buckets.items()):
            if idx < len(lst):
                picked_queue_tasks.append(lst[idx])
                added_any = True
                if len(picked_queue_tasks) >= 250:
                    break
        if not added_any:
            break
        idx += 1

    gh_dl_count = 0
    gh_fail_count = 0
    for t in picked_queue_tasks:
        raw_u = t["target"]
        if raw_u in seen_urls:
            continue
        seen_urls.add(raw_u)
        m = re.match(r"https://raw\.githubusercontent\.com/([^/]+/[^/]+)/[^/]+/(.+)", raw_u)
        if not m:
            continue
        rep, rel = m.group(1), urllib.parse.unquote(m.group(2))
        dst = OUT_GH / rep.replace("/", "__") / rel.replace("/", "__")
        if dst.exists():
            gh_queue_downloads.append({
                "task_id": t["task_id"], "status": "Completed", "url": raw_u,
                "local_path": str(dst.relative_to(ROOT)),
                "sha256": hashlib.sha256(dst.read_bytes()).hexdigest(), "bytes": dst.stat().st_size,
            })
            continue
        st, data, err = http_get(raw_u)
        time.sleep(0.03)
        if st == 200 and data:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
            gh_dl_count += 1
            gh_queue_downloads.append({
                "task_id": t["task_id"], "status": "Completed", "url": raw_u,
                "local_path": str(dst.relative_to(ROOT)),
                "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
            })
        else:
            gh_fail_count += 1
            gh_queue_downloads.append({
                "task_id": t["task_id"],
                "status": "Blocked" if st in (401, 403, 429) else "Deferred",
                "url": raw_u, "http_status": st, "error": err,
            })

    extra_downloads = []
    extra_ok = 0
    for item in extra_repo_targets[:120]:
        raw_u = item["raw_url"]
        if raw_u in seen_urls:
            continue
        seen_urls.add(raw_u)
        dst = OUT_GH / item["repo"].replace("/", "__") / item["path"].replace("/", "__")
        st, data, err = http_get(raw_u)
        time.sleep(0.03)
        if st == 200 and data:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
            extra_ok += 1
            extra_downloads.append({
                "from_repo_task": item["from_task"], "repo": item["repo"], "path": item["path"],
                "url": raw_u, "local_path": str(dst.relative_to(ROOT)),
                "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "status": "Completed",
            })

    # --- 3. Priority 5: Inspect ForexFactory thread HTML/metadata for 12 .ex5 items ---
    ex5_tasks = [t for t in tasks if t["kind"] == "compiled_binary_unreadable"]
    ff_threads = sorted(set(t["discovered_from"] for t in ex5_tasks))
    ff_thread_meta = {}
    for fu in ff_threads:
        st, html, err = http_get(fu)
        time.sleep(0.5)
        if st == 200:
            txt = html.decode("utf-8", errors="replace")
            title_m = re.search(r"<title>(.*?)</title>", txt, re.S)
            # Extract post attachments & surrounding author/post text cleanly
            att_blocks = {}
            for t in ex5_tasks:
                if t["discovered_from"] != fu:
                    continue
                att_id = re.search(r"/file/(\d+)", t["target"])
                aid = att_id.group(1) if att_id else ""
                ctx = ""
                if aid and aid in txt:
                    pos = txt.find(aid)
                    snippet = re.sub(r"<[^>]+>", " ", txt[max(0, pos - 1200):min(len(txt), pos + 600)])
                    ctx = re.sub(r"\s+", " ", snippet).strip()[:500]
                att_blocks[t["task_id"]] = {"attachment_id": aid, "context": ctx}
            ff_thread_meta[fu] = {
                "http_status": st,
                "title": re.sub(r"\s+", " ", title_m.group(1)).strip() if title_m else "",
                "attachments_context": att_blocks,
            }
        else:
            ff_thread_meta[fu] = {"http_status": st, "error": err}

    summary = {
        "generated_utc": now_utc(),
        "gitlab_14_retry": dict(Counter(r["status"] for r in gl_retries)),
        "github_queue_picked": len(picked_queue_tasks),
        "github_queue_downloaded": gh_dl_count,
        "github_queue_failed": gh_fail_count,
        "github_curated_extra_downloaded": extra_ok,
        "ff_ex5_threads_checked": {k: v.get("http_status") for k, v in ff_thread_meta.items()},
    }
    out = {
        "summary": summary,
        "gitlab_14_retry": gl_retries,
        "github_queue_downloads": gh_queue_downloads,
        "github_curated_extra_downloads": extra_downloads,
        "ff_ex5_metadata": ff_thread_meta,
    }
    (KB / "batch2_subbatch_gh_gl_ff.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
