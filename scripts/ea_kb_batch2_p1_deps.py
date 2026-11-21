#!/usr/bin/env python3
"""Batch 2 - Priority 1: Resolve all 158 custom_include_dependency + 5 custom_indicator_icustom tasks.
Rules:
- Never overwrite Batch 1 sources under data/ea_kb/sources/.
- Save newly fetched files under data/ea_kb/sources_batch2/deps/.
- Use normal authenticated GitHub API / GitLab API / raw HTTP (no WAF bypass).
- Output data/ea_kb/batch2_p1_deps.json and dependency links for the Batch 2 KB merger.
"""

from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/home/user/alina_lab")
KB = ROOT / "data" / "ea_kb"
OUT_SRC = KB / "sources_batch2" / "deps"
OUT_SRC.mkdir(parents=True, exist_ok=True)
OUT_JSON = KB / "batch2_p1_deps.json"

GIT_TOKEN = ""
tok_path = Path.home() / ".alina" / "git_token"
if tok_path.exists():
    GIT_TOKEN = tok_path.read_text(encoding="utf-8").strip()

# Known MetaQuotes MQL4/MQL5 Standard Library headers (never pretend they are custom missing files)
MQL_STDLIB_PREFIXES = (
    "arrays/", "charts/", "controls/", "canvas/", "expert/", "files/",
    "generic/", "indicators/", "math/", "strings/", "tools/", "trade/",
)
MQL_STDLIB_EXACT = {
    "movingaverages.mqh",
    "winuser32.mqh",
    "stdlib.mqh",
    "stderror.mqh",
    "errordescription.mqh",
    "object.mqh",
    "horizontalradiogroup.mqh",
}


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def http_get(url: str, github_api: bool = False, timeout: int = 25) -> tuple[int, bytes, str]:
    headers = {"User-Agent": "AlinaResearchBot/2.0 (Educational EA KB)"}
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


def norm_slash(s: str) -> str:
    return s.replace("\\", "/").strip()


def index_existing_sources() -> dict[str, list[dict]]:
    """Index all Batch 1 source files from source_code_index.csv and sources/ on disk."""
    import csv
    by_rel_suffix: dict[str, list[dict]] = {}
    csv_path = KB / "source_code_index.csv"
    with csv_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            src_url = row.get("source_url", "")
            lpath = row.get("local_path", "")
            sha = row.get("sha256", "")
            name = Path(lpath).name.lower() if lpath else ""
            rec = {"file_id": row["src_id"], "local_path": lpath, "source_url": src_url, "sha256": sha}
            if name:
                by_rel_suffix.setdefault(name, []).append(rec)
            # Also extract repo-relative path from raw github/gitlab URL
            m = re.match(r"https://raw\.githubusercontent\.com/([^/]+/[^/]+)/[^/]+/(.+)", src_url)
            if m:
                repo, rel = m.group(1).lower(), urllib.parse.unquote(m.group(2)).lower()
                by_rel_suffix.setdefault(f"gh:{repo}:{rel}", []).append(rec)
            m2 = re.match(r"https://gitlab\.com/([^/]+/[^/]+)/-/raw/[^/]+/(.+)", src_url)
            if m2:
                repo, rel = m2.group(1).lower(), urllib.parse.unquote(m2.group(2)).lower()
                by_rel_suffix.setdefault(f"gl:{repo}:{rel}", []).append(rec)
    return by_rel_suffix


def fetch_github_tree(repo: str, branch: str, cache: dict) -> tuple[str, list[str]]:
    key = f"gh:{repo}"
    if key in cache:
        return cache[key]
    for br in [branch, "main", "master"]:
        url = f"https://api.github.com/repos/{repo}/git/trees/{urllib.parse.quote(br)}?recursive=1"
        st, body, err = http_get(url, github_api=True)
        if st == 200:
            data = json.loads(body.decode("utf-8", errors="replace"))
            paths = [t["path"] for t in data.get("tree", []) if t.get("type") == "blob"]
            cache[key] = (br, paths)
            return br, paths
        time.sleep(0.15)
    cache[key] = (branch, [])
    return branch, []


def fetch_gitlab_tree(repo: str, cache: dict) -> tuple[str, list[str]]:
    key = f"gl:{repo}"
    if key in cache:
        return cache[key]
    enc = urllib.parse.quote(repo, safe="")
    st, body, err = http_get(f"https://gitlab.com/api/v4/projects/{enc}")
    branch = "master"
    if st == 200:
        branch = json.loads(body.decode("utf-8", errors="replace")).get("default_branch", "master")
    paths: list[str] = []
    page = 1
    while page <= 10:
        st2, body2, _ = http_get(
            f"https://gitlab.com/api/v4/projects/{enc}/repository/tree?recursive=true&per_page=100&page={page}&ref={urllib.parse.quote(branch)}"
        )
        if st2 != 200:
            break
        arr = json.loads(body2.decode("utf-8", errors="replace"))
        if not arr:
            break
        paths.extend(x["path"] for x in arr if x.get("type") == "blob")
        if len(arr) < 100:
            break
        page += 1
        time.sleep(0.15)
    cache[key] = (branch, paths)
    return branch, paths


def resolve_repo_candidate_paths(inc_target: str, from_rel_path: str, is_icustom: bool, repo_paths: list[str]) -> list[str]:
    t = norm_slash(inc_target)
    t_no_lead = t.lstrip("./")
    parent_dir = posixpath.dirname(from_rel_path)

    candidates = []
    # 1. Direct relative resolution against parent directory
    rel_resolved = posixpath.normpath(posixpath.join(parent_dir, t))
    candidates.append(rel_resolved)

    if is_icustom:
        for ext in (".mq5", ".mq4", ".ex5", ".ex4"):
            candidates.append(posixpath.normpath(posixpath.join(parent_dir, t + ext)))
            candidates.append("Indicators/" + t_no_lead + ext)
            candidates.append("MQL5/Indicators/" + t_no_lead + ext)
            candidates.append("MQL4/Indicators/" + t_no_lead + ext)
            candidates.append(t_no_lead + ext)
    else:
        candidates.extend([
            t_no_lead,
            "Include/" + t_no_lead,
            "MQL5/Include/" + t_no_lead,
            "MQL4/Include/" + t_no_lead,
            "src/" + t_no_lead,
            "src/include/" + t_no_lead,
            "Include/FxceLibs/" + t_no_lead,
            "GOLD_ORB/" + t_no_lead,
            "GOLD_ORB/Include/" + t_no_lead,
        ])
        if t_no_lead.startswith("Include/"):
            candidates.append(t_no_lead[len("Include/"):])

    # Exact case-insensitive match first, then unique suffix match
    lower_map = {p.lower(): p for p in repo_paths}
    hits = []
    for c in candidates:
        cl = c.lower()
        if cl in lower_map and lower_map[cl] not in hits:
            hits.append(lower_map[cl])
    if hits:
        return hits

    # Suffix match on normalized path (e.g. "MEMO/Core/Settings.mqh" or "Include/MEMO/Core/Settings.mqh")
    suffix = ("/" + t_no_lead).lower()
    if is_icustom:
        for ext in (".mq5", ".mq4"):
            sfx = ("/" + t_no_lead + ext).lower()
            for p in repo_paths:
                if p.lower().endswith(sfx) or p.lower() == (t_no_lead + ext).lower():
                    if p not in hits:
                        hits.append(p)
    else:
        for p in repo_paths:
            pl = p.lower()
            if pl.endswith(suffix) or pl == t_no_lead.lower():
                if p not in hits:
                    hits.append(p)
    if hits:
        return hits

    # Basename match within same repo when path is relative or in subdir
    base = posixpath.basename(t_no_lead).lower()
    if is_icustom:
        for ext in (".mq5", ".mq4"):
            for p in repo_paths:
                if posixpath.basename(p).lower() == base + ext and p not in hits:
                    hits.append(p)
    else:
        for p in repo_paths:
            if posixpath.basename(p).lower() == base and p not in hits:
                hits.append(p)
    return hits


def is_stdlib_header(target: str) -> bool:
    t = norm_slash(target).lower().lstrip("./")
    if t in MQL_STDLIB_EXACT:
        return True
    if any(t.startswith(pref) for pref in MQL_STDLIB_PREFIXES):
        return True
    if t.startswith("include/math/"):
        return False
    return False


def main() -> None:
    rq_path = KB / "research_queue.jsonl"
    tasks = [json.loads(l) for l in rq_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    existing_idx = index_existing_sources()
    tree_cache: dict = {}
    downloaded_cache: dict[str, dict] = {}
    resolutions = []
    http_calls = 0
    new_downloads = 0

    for task in tasks:
        if task.get("kind") not in ("custom_include_dependency", "custom_indicator_icustom"):
            continue
        tid = task["task_id"]
        kind = task["kind"]
        is_icustom = kind == "custom_indicator_icustom"
        target = task["target"]
        frm = task.get("discovered_from", "")
        notes = task.get("notes", "")

        rec = {
            "task_id": tid,
            "kind": kind,
            "target": target,
            "discovered_from": frm,
            "parent_local_note": notes,
            "resolution_status": "Pending",
            "resolution_type": "",
            "resolved_source_url": "",
            "local_path": "",
            "sha256": "",
            "bytes": 0,
            "details": "",
            "checked_utc": now_utc(),
        }

        # Case 1: MQL5 parent (79679, 79683, 79074)
        if "www.mql5.com" in frm:
            norm_t = norm_slash(target)
            base_t = posixpath.basename(norm_t).lower()
            hits = existing_idx.get(base_t, [])
            mql_local = [h for h in hits if "mql5_ea/" in h["local_path"] or "mql5_ind/" in h["local_path"]]
            if mql_local:
                h = mql_local[0]
                rec.update({
                    "resolution_status": "Completed",
                    "resolution_type": "already_in_local_kb",
                    "resolved_source_url": h["source_url"],
                    "local_path": h["local_path"],
                    "sha256": h["sha256"],
                    "bytes": (ROOT / h["local_path"]).stat().st_size if (ROOT / h["local_path"]).exists() else 0,
                    "details": f"Matched local companion MQL5 file {h['file_id']}",
                })
                resolutions.append(rec)
                continue
            elif is_stdlib_header(target):
                rec.update({
                    "resolution_status": "Completed",
                    "resolution_type": "mql_standard_library",
                    "resolved_source_url": "https://www.mql5.com/en/docs/standardlibrary",
                    "details": f"Official MetaQuotes MT5 Standard Library header <{norm_t}>",
                })
                resolutions.append(rec)
                continue

        # Case 2: GitHub raw parent
        m_gh = re.match(r"https://raw\.githubusercontent\.com/([^/]+/[^/]+)/([^/]+)/(.+)", frm)
        m_gl = re.match(r"https://gitlab\.com/([^/]+/[^/]+)/-/raw/([^/]+)/(.+)", frm)

        if m_gh or m_gl:
            if m_gh:
                host = "github"
                repo, branch, from_rel = m_gh.group(1), urllib.parse.unquote(m_gh.group(2)), urllib.parse.unquote(m_gh.group(3))
                branch_used, repo_paths = fetch_github_tree(repo, branch, tree_cache)
            else:
                host = "gitlab"
                repo, branch, from_rel = m_gl.group(1), urllib.parse.unquote(m_gl.group(2)), urllib.parse.unquote(m_gl.group(3))
                branch_used, repo_paths = fetch_gitlab_tree(repo, tree_cache)

            candidates = resolve_repo_candidate_paths(target, from_rel, is_icustom, repo_paths)
            if candidates:
                chosen = candidates[0]
                key_prefix = "gh" if host == "github" else "gl"
                existing_match = existing_idx.get(f"{key_prefix}:{repo.lower()}:{chosen.lower()}", [])
                if existing_match:
                    h = existing_match[0]
                    rec.update({
                        "resolution_status": "Completed",
                        "resolution_type": "already_in_local_kb",
                        "resolved_source_url": h["source_url"],
                        "local_path": h["local_path"],
                        "sha256": h["sha256"],
                        "bytes": (ROOT / h["local_path"]).stat().st_size if (ROOT / h["local_path"]).exists() else 0,
                        "details": f"Already downloaded in Batch 1 as {h['file_id']} ({chosen})",
                    })
                else:
                    if host == "github":
                        raw_url = f"https://raw.githubusercontent.com/{repo}/{urllib.parse.quote(branch_used)}/{urllib.parse.quote(chosen, safe='/')}"
                    else:
                        raw_url = f"https://gitlab.com/{repo}/-/raw/{urllib.parse.quote(branch_used)}/{urllib.parse.quote(chosen, safe='/')}"

                    if raw_url in downloaded_cache:
                        dinfo = downloaded_cache[raw_url]
                        rec.update({
                            "resolution_status": "Completed",
                            "resolution_type": "downloaded_batch2",
                            "resolved_source_url": raw_url,
                            "local_path": dinfo["local_path"],
                            "sha256": dinfo["sha256"],
                            "bytes": dinfo["bytes"],
                            "details": f"Resolved in {repo} ({chosen}) [cached this batch]",
                        })
                    else:
                        http_calls += 1
                        st, content, err = http_get(raw_url)
                        time.sleep(0.08)
                        if st == 200 and content:
                            safe_repo = repo.replace("/", "__")
                            safe_file = chosen.replace("/", "__")
                            dst = OUT_SRC / host / safe_repo / safe_file
                            dst.parent.mkdir(parents=True, exist_ok=True)
                            dst.write_bytes(content)
                            sha = hashlib.sha256(content).hexdigest()
                            lpath = str(dst.relative_to(ROOT))
                            dinfo = {"local_path": lpath, "sha256": sha, "bytes": len(content)}
                            downloaded_cache[raw_url] = dinfo
                            new_downloads += 1
                            rec.update({
                                "resolution_status": "Completed",
                                "resolution_type": "downloaded_batch2",
                                "resolved_source_url": raw_url,
                                "local_path": lpath,
                                "sha256": sha,
                                "bytes": len(content),
                                "details": f"Downloaded dependency from {host} {repo}:{chosen}",
                            })
                        else:
                            rec.update({
                                "resolution_status": "Blocked" if st in (401, 403, 429) else "Deferred",
                                "resolution_type": "download_failed",
                                "resolved_source_url": raw_url,
                                "details": f"Download error {st}: {err}",
                            })
                resolutions.append(rec)
                continue

            # Not found in own repo tree -> check MetaQuotes Standard Library vs external third-party
            if is_stdlib_header(target) and (
                # Special check: in RoffildLibrary / fxce, Object.mqh or Common.mqh could be stdlib or external
                # In fxce CustomMessage.mqh: <Object.mqh> is MT5 stdlib; in MikePapinski StdLibErr.mqh is external/MT4
                True
            ):
                # Distinguish true MT4/MT5 standard library vs repo-specific files like Object.mqh/Common.mqh
                t_norm = norm_slash(target).lower().lstrip("./")
                if t_norm == "object.mqh" and "mql4" in frm.lower():
                    rec.update({
                        "resolution_status": "Completed",
                        "resolution_type": "mql_standard_library",
                        "resolved_source_url": "https://www.mql5.com/en/docs/standardlibrary/cobject",
                        "details": "Standard MQL4/MQL5 CObject header",
                    })
                elif t_norm == "object.mqh" and "fxce" in frm.lower():
                    rec.update({
                        "resolution_status": "Completed",
                        "resolution_type": "mql_standard_library",
                        "resolved_source_url": "https://www.mql5.com/en/docs/standardlibrary/cobject",
                        "details": "Official MetaQuotes MT5 Standard Library <Object.mqh>",
                    })
                else:
                    rec.update({
                        "resolution_status": "Completed",
                        "resolution_type": "mql_standard_library",
                        "resolved_source_url": "https://www.mql5.com/en/docs/standardlibrary",
                        "details": f"Official MetaQuotes MT4/MT5 Standard Library header ({norm_slash(target)})",
                    })
                resolutions.append(rec)
                continue

            # Check if found in another known repo in our Batch 1 / Batch 2 pool (e.g. Math/Stat/Normal.mqh or EA31337)
            base_t = posixpath.basename(norm_slash(target)).lower()
            # Special case: EA31337-classes Math or EA31337 include/
            # Special case: DillonGrech Custom\MovingAverageCross vs MovingAverageCross.mq5 (search repo tree for close match)
            close_matches = [p for p in repo_paths if posixpath.basename(p).lower().startswith(base_t.split(".")[0])]
            if is_icustom and close_matches:
                # Could be named slightly differently in repo, check if exact indicator name appears
                rec.update({
                    "resolution_status": "Deferred",
                    "resolution_type": "missing_in_repo_tree",
                    "details": f"Not present in {repo} tree (close names: {close_matches[:5]}). Likely external or pre-compiled indicator.",
                })
            else:
                rec.update({
                    "resolution_status": "Deferred",
                    "resolution_type": "external_dependency_missing_in_repo",
                    "details": f"Include '{target}' is not inside {repo} repo tree ({len(repo_paths)} files scanned); external third-party/author header.",
                })
            resolutions.append(rec)

    summary = {
        "generated_utc": now_utc(),
        "total_p1_tasks": len(resolutions),
        "new_unique_files_downloaded": new_downloads,
        "http_file_fetches": http_calls,
        "by_status": {},
        "by_resolution_type": {},
    }
    for r in resolutions:
        summary["by_status"][r["resolution_status"]] = summary["by_status"].get(r["resolution_status"], 0) + 1
        summary["by_resolution_type"][r["resolution_type"]] = summary["by_resolution_type"].get(r["resolution_type"], 0) + 1

    OUT_JSON.write_text(json.dumps({"summary": summary, "resolutions": resolutions}, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
