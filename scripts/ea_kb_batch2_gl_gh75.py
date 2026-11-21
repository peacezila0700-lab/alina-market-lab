#!/usr/bin/env python3
"""Batch 2 - Sub-batch:
1) Priority 3A: Resolve and download all 35 gitlab_source_file tasks (using actual default_branch).
2) Priority 3B: Inspect all 75 github_repo tasks via GitHub REST API (metadata + source file inventory).
3) Summarize 1,393 github_source_file tasks by repo & category for controlled batch download.
4) Polite single-URL check on MQL5 and ForexFactory.
"""

from __future__ import annotations

import hashlib
import json
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
OUT_GL.mkdir(parents=True, exist_ok=True)

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
    tasks = [json.loads(l) for l in (KB / "research_queue.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]

    # --- 1. GitLab 35 files ---
    gl_tasks = [t for t in tasks if t["kind"] == "gitlab_source_file"]
    gl_branch_cache: dict[str, str] = {}
    gl_results = []
    gl_downloaded = 0

    for t in gl_tasks:
        tid = t["task_id"]
        url = t["target"]
        # Format: https://gitlab.com/fxce/mt5-libs/-/raw/master/Include/FxceLibs/...
        parts = url.split("/-/raw/")
        repo_path = parts[0].replace("https://gitlab.com/", "")
        rest = parts[1]
        old_br, rel_file = rest.split("/", 1)
        if repo_path not in gl_branch_cache:
            enc = urllib.parse.quote(repo_path, safe="")
            st, body, _ = http_get(f"https://gitlab.com/api/v4/projects/{enc}")
            br = old_br
            if st == 200:
                br = json.loads(body.decode("utf-8", errors="replace")).get("default_branch", old_br)
            gl_branch_cache[repo_path] = br

        br = gl_branch_cache[repo_path]
        raw_url = f"https://gitlab.com/{repo_path}/-/raw/{urllib.parse.quote(br)}/{urllib.parse.quote(rel_file, safe='/')}"
        st, data, err = http_get(raw_url)
        time.sleep(0.1)
        if st == 200 and data:
            safe_repo = repo_path.replace("/", "__")
            safe_file = rel_file.replace("/", "__")
            dst = OUT_GL / safe_repo / safe_file
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
            gl_downloaded += 1
            gl_results.append({
                "task_id": tid,
                "status": "Completed",
                "original_url": url,
                "resolved_url": raw_url,
                "branch_used": br,
                "local_path": str(dst.relative_to(ROOT)),
                "sha256": hashlib.sha256(data).hexdigest(),
                "bytes": len(data),
            })
        else:
            gl_results.append({
                "task_id": tid,
                "status": "Blocked" if st in (401, 403, 429) else "Deferred",
                "original_url": url,
                "resolved_url": raw_url,
                "http_status": st,
                "error": err,
            })

    # --- 2. GitHub 75 repos inspection ---
    gh_repos = [t for t in tasks if t["kind"] == "github_repo"]
    gh_repo_reports = []
    for t in gh_repos:
        tid = t["task_id"]
        url = t["target"].rstrip("/")
        repo = url.replace("https://github.com/", "")
        st, body, err = http_get(f"https://api.github.com/repos/{repo}", github_api=True)
        time.sleep(0.08)
        if st == 200:
            meta = json.loads(body.decode("utf-8", errors="replace"))
            br = meta.get("default_branch", "main")
            st2, tbody, err2 = http_get(f"https://api.github.com/repos/{repo}/git/trees/{urllib.parse.quote(br)}?recursive=1", github_api=True)
            time.sleep(0.08)
            mql_files, py_files, pine_files = [], [], []
            if st2 == 200:
                tree = json.loads(tbody.decode("utf-8", errors="replace")).get("tree", [])
                for node in tree:
                    if node.get("type") != "blob":
                        continue
                    p = node["path"]
                    pl = p.lower()
                    if pl.endswith((".mq5", ".mq4", ".mqh")):
                        mql_files.append(p)
                    elif pl.endswith(".py"):
                        py_files.append(p)
                    elif pl.endswith(".pine"):
                        pine_files.append(p)
            gh_repo_reports.append({
                "task_id": tid,
                "status": "Completed",
                "repo": repo,
                "url": url,
                "owner": (meta.get("owner") or {}).get("login", ""),
                "owner_url": (meta.get("owner") or {}).get("html_url", ""),
                "description": meta.get("description") or "",
                "stars": meta.get("stargazers_count", 0),
                "forks": meta.get("forks_count", 0),
                "license": (meta.get("license") or {}).get("spdx_id", ""),
                "default_branch": br,
                "updated_at": meta.get("pushed_at", ""),
                "mql_file_count": len(mql_files),
                "py_file_count": len(py_files),
                "pine_file_count": len(pine_files),
                "mql_files": mql_files,
                "py_files": py_files[:50],
                "pine_files": pine_files[:50],
            })
        else:
            gh_repo_reports.append({
                "task_id": tid,
                "status": "Blocked" if st in (401, 403, 429) else "Deferred",
                "repo": repo,
                "url": url,
                "http_status": st,
                "error": err,
            })

    # --- 3. Analyze 1,393 github_source_file inventory ---
    gh_files = [t for t in tasks if t["kind"] == "github_source_file"]
    by_repo = Counter(t.get("discovered_from", "").replace("https://github.com/", "") for t in gh_files)

    # --- 4. Polite single-request HTTP probe on MQL5 ---
    st_mql, _, err_mql = http_get("https://www.mql5.com/en/code/78715")

    out = {
        "generated_utc": now_utc(),
        "gitlab_35_summary": {
            "total": len(gl_results),
            "downloaded": gl_downloaded,
            "by_status": dict(Counter(r["status"] for r in gl_results)),
        },
        "gitlab_35_results": gl_results,
        "github_75_repos_summary": {
            "total": len(gh_repo_reports),
            "by_status": dict(Counter(r["status"] for r in gh_repo_reports)),
            "total_mql_files_discovered": sum(r.get("mql_file_count", 0) for r in gh_repo_reports),
            "total_pine_files_discovered": sum(r.get("pine_file_count", 0) for r in gh_repo_reports),
            "total_py_files_discovered": sum(r.get("py_file_count", 0) for r in gh_repo_reports),
        },
        "github_75_repos": gh_repo_reports,
        "github_1393_files_by_repo": dict(by_repo.most_common()),
        "mql5_sandbox_ip_probe": {"url": "https://www.mql5.com/en/code/78715", "http_status": st_mql, "error": err_mql},
    }
    (KB / "batch2_gitlab_gh75_probe.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("GitLab 35 summary:", json.dumps(out["gitlab_35_summary"]))
    print("GitHub 75 repos summary:", json.dumps(out["github_75_repos_summary"]))
    print("Top repos in 1393 queue:", list(by_repo.most_common(20)))
    print("MQL5 sandbox probe:", out["mql5_sandbox_ip_probe"])


if __name__ == "__main__":
    main()
