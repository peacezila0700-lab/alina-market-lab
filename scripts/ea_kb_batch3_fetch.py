#!/usr/bin/env python3
"""Batch 3 Acquisition Script for ALINA Global EA Intelligence KB.

Executes all 951 tasks in `data/ea_kb/research_queue_batch3.jsonl` (`Q-1925..Q-2875`):
  1. Downloads full GitLab ZIP archives via GitLab REST API v4 (`fxce/mt5-libs`, `Roffild/RoffildLibrary`)
     to resolve all 14 `gitlab_source_retry`, 4 GitLab `batch2_new_include_dependency`, and `Roffild/ToIndicator`.
  2. Audits full GitHub trees (using `batch2_gitlab_gh75_probe.json` + GitHub Tree API with `~/.alina/git_token`)
     across all Batch 3 repos and downloads verbatim headers/indicators for the 719 `batch2_new_include_dependency`,
     13 `batch2_new_icustom_target`, and 2 `p1_dep_retry` tasks.
  3. Cross-checks the 203 `mql5_source_archive` tasks against local files and honestly records sandbox IP blocks
     where direct binary/raw `.zip/.mq5` archive download is unavailable from sandbox.

All new files are written under `data/ea_kb/sources_batch3/` (never overwriting Batch 1/2 files).
Outputs `data/ea_kb/batch3_resolutions.json`.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import io
import json
import os
import posixpath
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(os.environ.get("ALINA_ROOT", str(Path(__file__).resolve().parent.parent)))
KB = ROOT / "data" / "ea_kb"
OUT_B3 = KB / "sources_batch3"
OUT_GL = OUT_B3 / "gitlab"
OUT_DEPS = OUT_B3 / "deps"
OUT_JSON = KB / "batch3_resolutions.json"

for d in (OUT_B3, OUT_GL, OUT_DEPS):
    d.mkdir(parents=True, exist_ok=True)

GIT_TOKEN = ""
tok_path = Path.home() / ".alina" / "git_token"
if tok_path.exists():
    GIT_TOKEN = tok_path.read_text(encoding="utf-8").strip()

MQL_STDLIB_PREFIXES = (
    "arrays/", "charts/", "chartobjects/", "controls/", "canvas/", "expert/",
    "files/", "generic/", "graphics/", "indicators/", "math/", "strings/",
    "tools/", "trade/", "winapi/",
)
MQL_STDLIB_EXACT = {
    "movingaverages.mqh", "winuser32.mqh", "stdlib.mqh", "stdlib.mq4", "stderror.mqh",
    "errordescription.mqh", "object.mqh", "horizontalradiogroup.mqh",
    "trade.mqh", "symbolinfo.mqh", "positioninfo.mqh", "orderinfo.mqh",
    "accountinfo.mqh", "historyorderinfo.mqh", "dealinfo.mqh",
}
MT_BUILTIN_ICUSTOM = {
    "heiken ashi", "examples/heiken_ashi", "examples/zigzag", "zigzag",
    "examples/macd", "examples/rsi", "examples/atr", "examples/parabolicsar",
}


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def norm_slash(s: str) -> str:
    return s.replace("\\", "/").strip()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def http_get(url: str, github_api: bool = False, timeout: int = 45, retries: int = 2) -> tuple[int, bytes, str]:
    headers = {"User-Agent": "AlinaResearchBot/3.0 (Educational EA KB)"}
    if github_api and GIT_TOKEN:
        headers["Authorization"] = f"Bearer {GIT_TOKEN}"
        headers["Accept"] = "application/vnd.github+json"
    last_err = ""
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.status, r.read(), ""
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}: {e.reason}"
            if e.code in (404, 403, 410):
                return e.code, b"", last_err
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
        time.sleep(0.6 * (attempt + 1))
    return 0, b"", last_err


def index_local_files() -> tuple[dict[str, str], dict[str, list[str]], set[str]]:
    """Index all Batch 1 & Batch 2 local files by sha256, normalized path suffix, and lowercase filename."""
    by_sha: dict[str, str] = {}
    by_name: dict[str, list[str]] = {}
    by_rel_low: set[str] = set()
    for base in (KB / "sources", KB / "sources_batch2", ROOT / "ea" / "AlinaRiskGovernor.mq5"):
        paths = [base] if base.is_file() else (sorted(p for p in base.rglob("*") if p.is_file()) if base.exists() else [])
        for p in paths:
            rel = str(p.relative_to(ROOT))
            by_rel_low.add(rel.lower())
            h = sha256_bytes(p.read_bytes())
            by_sha.setdefault(h, rel)
            by_name.setdefault(p.name.lower(), []).append(rel)
    return by_sha, by_name, by_rel_low


def fetch_gitlab_archive(slug: str) -> tuple[str, dict[str, bytes]]:
    """Download full repository zip from GitLab API v4 (no per-file 429!). Returns (branch_hint, {rel_path: bytes})."""
    enc = urllib.parse.quote(slug, safe="")
    url = f"https://gitlab.com/api/v4/projects/{enc}/repository/archive.zip"
    code, data, err = http_get(url, timeout=90, retries=2)
    if code != 200 or not data:
        # Try explicit develop / master if default didn't respond
        for br in ("develop", "master", "main"):
            code2, data2, err2 = http_get(f"{url}?sha={br}", timeout=90, retries=1)
            if code2 == 200 and data2:
                code, data = code2, data2
                break
    if code != 200 or not data:
        raise RuntimeError(f"GitLab archive failed for {slug}: HTTP {code} {err}")

    files: dict[str, bytes] = {}
    branch_hint = "default"
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            parts = info.filename.split("/", 1)
            if len(parts) < 2:
                continue
            rel = parts[1]
            ext = Path(rel).suffix.lower()
            if ext in (".mq4", ".mq5", ".mqh", ".h", ".py", ".pine"):
                files[rel] = zf.read(info.filename)
    return branch_hint, files


def fetch_github_tree(slug: str) -> dict[str, Any]:
    """Fetch default branch + full recursive file tree for a GitHub repo."""
    code, data, err = http_get(f"https://api.github.com/repos/{slug}", github_api=True)
    if code != 200:
        return {"repo": slug, "ok": False, "error": f"repo_meta {code} {err}", "default_branch": "main", "files": []}
    meta = json.loads(data.decode("utf-8"))
    branch = meta.get("default_branch", "main")
    code2, tdata, err2 = http_get(
        f"https://api.github.com/repos/{slug}/git/trees/{urllib.parse.quote(branch)}?recursive=1",
        github_api=True,
        timeout=60,
    )
    if code2 != 200:
        return {"repo": slug, "ok": False, "error": f"tree {code2} {err2}", "default_branch": branch, "files": []}
    tree = json.loads(tdata.decode("utf-8"))
    files = [
        x["path"] for x in tree.get("tree", [])
        if x.get("type") == "blob" and Path(x["path"]).suffix.lower() in (".mq4", ".mq5", ".mqh", ".h", ".py", ".pine")
    ]
    return {"repo": slug, "ok": True, "default_branch": branch, "files": files, "truncated": tree.get("truncated", False)}


def safe_save(dest: Path, raw: bytes) -> tuple[str, str]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(raw)
    return str(dest.relative_to(ROOT)), sha256_bytes(raw)


def resolve_path_in_tree(target: str, from_url: str, tree_files: list[str], extra_exts: tuple[str, ...] = ()) -> str | None:
    """Resolve relative include / iCustom path inside a repo's file tree."""
    t_norm = norm_slash(target).lstrip("./")
    t_low = t_norm.lower()
    if not t_low:
        return None
    low_map = {p.lower(): p for p in tree_files}

    # 1. Exact relative resolution against discovered_from raw URL path
    if from_url.startswith("https://raw.githubusercontent.com/") or from_url.startswith("https://gitlab.com/"):
        if "raw.githubusercontent.com/" in from_url:
            parts = from_url.split("raw.githubusercontent.com/")[1].split("/")
            repo_rel = "/".join(parts[3:]) if len(parts) > 3 else ""
        else:
            parts = from_url.split("/-/raw/")[1].split("/") if "/-/raw/" in from_url else []
            repo_rel = "/".join(parts[1:]) if len(parts) > 1 else ""
        if repo_rel:
            base_dir = posixpath.dirname(repo_rel)
            cand = posixpath.normpath(posixpath.join(base_dir, t_norm)).lstrip("./")
            if cand.lower() in low_map:
                return low_map[cand.lower()]
            for ext in extra_exts:
                if (cand + ext).lower() in low_map:
                    return low_map[(cand + ext).lower()]

    # 2. Direct path match from repo root
    if t_low in low_map:
        return low_map[t_low]
    for ext in extra_exts:
        if (t_low + ext) in low_map:
            return low_map[t_low + ext]

    # 3. Clean leading ../ segments and match suffix
    clean_parts = [p for p in t_norm.split("/") if p not in ("", ".", "..")]
    if clean_parts:
        clean_low = "/".join(clean_parts).lower()
        cands_ext = [clean_low] + [clean_low + ext for ext in extra_exts]
        for ce in cands_ext:
            matches = [p for pl, p in low_map.items() if pl == ce or pl.endswith("/" + ce)]
            if matches:
                # Prefer shortest path
                return sorted(matches, key=len)[0]

    # 4. Exact filename fallback (only if unambiguous or shortest inside same top folder)
    bn = Path(t_low).name
    if bn:
        bn_cands = [bn] + ([bn + ext for ext in extra_exts] if not Path(bn).suffix else [])
        for bc in bn_cands:
            matches = [p for pl, p in low_map.items() if Path(pl).name == bc]
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1 and t_norm.count("/") == 0:
                return sorted(matches, key=len)[0]
    return None


def main() -> None:
    b3_path = KB / "research_queue_batch3.jsonl"
    b3_rows = [json.loads(l) for l in b3_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"Loaded {len(b3_rows)} Batch 3 tasks from {b3_path}.")

    by_sha, by_name, _ = index_local_files()
    probe = json.loads((KB / "batch2_gitlab_gh75_probe.json").read_text(encoding="utf-8"))

    # 1. Fetch GitLab full archives via GitLab Archive API v4
    gl_archives: dict[str, dict[str, bytes]] = {}
    for slug in ("fxce/mt5-libs", "Roffild/RoffildLibrary"):
        print(f"Downloading GitLab archive for {slug}...")
        _, files = fetch_gitlab_archive(slug)
        gl_archives[slug.lower()] = files
        print(f"  -> Extracted {len(files)} MQL/Py/Pine files from {slug}.")

    # 2. Gather GitHub repo trees (cached from gh75 + API fetch for remaining repos)
    gh_trees: dict[str, dict[str, Any]] = {}
    for r in probe.get("github_75_repos", []):
        files = list(r.get("mql_files", [])) + list(r.get("py_files", [])) + list(r.get("pine_files", []))
        gh_trees[r["repo"].lower()] = {
            "repo": r["repo"],
            "ok": True,
            "default_branch": r.get("default_branch", "main"),
            "files": files,
            "source": "gh75_cache",
        }

    needed_gh_repos: set[str] = {"CThompson18/MQL5", "GeneralTradingSarl/Smart-Money-Concepts", "MegaJoctan/MALE5"}
    for row in b3_rows:
        df = row.get("discovered_from", "")
        if "raw.githubusercontent.com/" in df:
            parts = df.split("raw.githubusercontent.com/")[1].split("/")
            if len(parts) >= 2:
                needed_gh_repos.add(f"{parts[0]}/{parts[1]}")

    for slug in sorted(needed_gh_repos):
        if slug.lower() not in gh_trees:
            print(f"Fetching GitHub tree for {slug}...")
            tinfo = fetch_github_tree(slug)
            tinfo["source"] = "github_api_b3"
            gh_trees[slug.lower()] = tinfo
            print(f"  -> ok={tinfo['ok']} branch={tinfo.get('default_branch')} files={len(tinfo.get('files', []))}")

    # Load MQL5 fetched metadata for cross-checking code_ids / filenames
    mql_fetched = json.loads((KB / "batch2_mql5_fetched.json").read_text(encoding="utf-8"))
    mql_by_cid = {str(x["code_id"]): x for x in mql_fetched.get("codebase_items", [])}

    # Track already-saved files in Batch 3 to avoid duplicate disk writes
    b3_saved_by_key: dict[tuple[str, str], tuple[str, str, str]] = {}  # (repo_low, repo_path) -> (local_rel, sha, url)

    def materialize_gitlab(slug_low: str, repo_path: str, kind_dir: str) -> tuple[str, str, str, bool]:
        """Save file from GitLab archive if not already identically on disk. Returns (rel, sha, url, newly_saved)."""
        key = ("gl:" + slug_low, repo_path)
        if key in b3_saved_by_key:
            r, s, u = b3_saved_by_key[key]
            return r, s, u, False
        raw = gl_archives[slug_low][repo_path]
        h = sha256_bytes(raw)
        if h in by_sha:
            rel_existing = by_sha[h]
            url = f"https://gitlab.com/{slug_low}/-/raw/HEAD/{repo_path}"
            b3_saved_by_key[key] = (rel_existing, h, url)
            return rel_existing, h, url, False
        repo_dir = slug_low.replace("/", "__")
        safe_name = repo_path.replace("/", "__")
        dest = (OUT_GL if kind_dir == "gitlab" else OUT_DEPS / "gitlab") / repo_dir / safe_name
        rel, sha = safe_save(dest, raw)
        by_sha[sha] = rel
        url = f"https://gitlab.com/{slug_low}/-/raw/HEAD/{repo_path}"
        b3_saved_by_key[key] = (rel, sha, url)
        return rel, sha, url, True

    # Collect GitHub raw download tasks first so we can fetch them concurrently
    pending_gh_downloads: dict[tuple[str, str], str] = {}  # (repo_low, repo_path) -> raw_url
    pre_resolved: list[dict[str, Any]] = []

    for row in b3_rows:
        tid = row["task_id"]
        kind = row["kind"]
        tgt = row["target"]
        df = row.get("discovered_from", "")

        if kind == "gitlab_source_retry":
            # Parse gitlab slug & path from https://gitlab.com/owner/repo/-/raw/branch/path
            m_parts = tgt.split("gitlab.com/")[1].split("/-/raw/")
            slug_low = m_parts[0].lower()
            sub_after_branch = "/".join(m_parts[1].split("/")[1:])
            gl_files = gl_archives.get(slug_low, {})
            resolved = resolve_path_in_tree(sub_after_branch, tgt, list(gl_files.keys()))
            if resolved:
                rel, sha, raw_u, newly = materialize_gitlab(slug_low, resolved, "gitlab")
                pre_resolved.append({
                    "task_id": tid, "kind": kind, "target": tgt, "status": "completed",
                    "resolution_type": "gitlab_archive_api", "local_path": rel, "sha256": sha,
                    "resolved_url": raw_u, "newly_downloaded": newly,
                })
            else:
                pre_resolved.append({
                    "task_id": tid, "kind": kind, "target": tgt, "status": "blocked",
                    "resolution_type": "not_in_gitlab_archive", "local_path": "", "sha256": "",
                    "resolved_url": tgt, "newly_downloaded": False,
                })

        elif kind in ("batch2_new_include_dependency", "p1_dep_retry", "batch2_new_icustom_target"):
            t_norm = norm_slash(tgt).lstrip(":")
            t_low = t_norm.lower()
            bn = Path(t_low).name

            # 1) Check MetaQuotes stdlib or built-in MT indicator
            if (
                kind == "batch2_new_icustom_target"
                and (t_low in MT_BUILTIN_ICUSTOM or t_low.startswith("examples/"))
            ) or (
                kind != "batch2_new_icustom_target"
                and (any(t_low.startswith(p) for p in MQL_STDLIB_PREFIXES) or bn in MQL_STDLIB_EXACT or t_low in MQL_STDLIB_EXACT)
            ):
                pre_resolved.append({
                    "task_id": tid, "kind": kind, "target": tgt, "status": "completed_stdlib_builtin",
                    "resolution_type": "mql_stdlib_or_builtin", "local_path": "", "sha256": "",
                    "resolved_url": "https://www.mql5.com/en/docs/standardlibrary", "newly_downloaded": False,
                })
                continue

            # 2) Determine source repo from discovered_from (or p1_dep_retry notes)
            slug_low = ""
            if "raw.githubusercontent.com/" in df:
                ps = df.split("raw.githubusercontent.com/")[1].split("/")
                slug_low = f"{ps[0]}/{ps[1]}".lower()
            elif "gitlab.com/" in df:
                ps = df.split("gitlab.com/")[1].split("/")
                slug_low = f"{ps[0]}/{ps[1]}".lower()
            elif tid == "Q-2142":
                slug_low = "cthompson18/mql5"
            elif tid == "Q-2143":
                slug_low = "generaltradingsarl/smart-money-concepts"

            extra_exts = (".mq5", ".mq4", ".ex5") if kind == "batch2_new_icustom_target" else ()

            if slug_low in gl_archives:
                gl_files = gl_archives[slug_low]
                resolved = resolve_path_in_tree(t_norm, df, list(gl_files.keys()), extra_exts=extra_exts)
                if resolved:
                    rel, sha, raw_u, newly = materialize_gitlab(slug_low, resolved, "deps")
                    pre_resolved.append({
                        "task_id": tid, "kind": kind, "target": tgt, "status": "completed",
                        "resolution_type": "gitlab_archive_dep", "local_path": rel, "sha256": sha,
                        "resolved_url": raw_u, "newly_downloaded": newly,
                    })
                else:
                    pre_resolved.append({
                        "task_id": tid, "kind": kind, "target": tgt, "status": "deferred",
                        "resolution_type": "external_or_missing_in_repo", "local_path": "", "sha256": "",
                        "resolved_url": "", "newly_downloaded": False,
                        "details": f"Not found in {slug_low} archive ({len(gl_files)} files scanned).",
                    })
            elif slug_low in gh_trees and gh_trees[slug_low].get("ok"):
                tree_info = gh_trees[slug_low]
                resolved = resolve_path_in_tree(t_norm, df, tree_info["files"], extra_exts=extra_exts)
                # Cross-repo / submodule fallback for EA31337-classes & MegaJoctan/MALE5
                alt_slug = ""
                if not resolved and slug_low == "ea31337/ea31337" and "classes/" in t_low:
                    sub_t = t_norm.split("classes/", 1)[1]
                    alt_resolved = resolve_path_in_tree(sub_t, "", gh_trees.get("ea31337/ea31337-classes", {}).get("files", []), extra_exts=extra_exts)
                    if alt_resolved:
                        resolved, alt_slug = alt_resolved, "ea31337/ea31337-classes"
                if not resolved and t_low.startswith("male5/") and gh_trees.get("megajoctan/male5", {}).get("ok"):
                    sub_t = t_norm[len("male5/"):]
                    alt_resolved = resolve_path_in_tree(sub_t, "", gh_trees["megajoctan/male5"]["files"], extra_exts=extra_exts)
                    if alt_resolved:
                        resolved, alt_slug = alt_resolved, "megajoctan/male5"
                if resolved:
                    use_info = gh_trees[alt_slug] if alt_slug else tree_info
                    use_slug = alt_slug or slug_low
                    br = use_info["default_branch"]
                    raw_u = f"https://raw.githubusercontent.com/{use_info['repo']}/{urllib.parse.quote(br)}/{urllib.parse.quote(resolved)}"
                    pending_gh_downloads[(use_slug, resolved)] = raw_u
                    pre_resolved.append({
                        "task_id": tid, "kind": kind, "target": tgt, "status": "PENDING_GH_DL",
                        "repo_low": use_slug, "repo_path": resolved, "raw_url": raw_u,
                    })
                else:
                    # Check if unambiguous match exists locally in Batch 1/2
                    local_hits = by_name.get(bn, [])
                    if len(local_hits) == 1:
                        pre_resolved.append({
                            "task_id": tid, "kind": kind, "target": tgt, "status": "completed",
                            "resolution_type": "local_kb_match", "local_path": local_hits[0], "sha256": "",
                            "resolved_url": "local://" + local_hits[0], "newly_downloaded": False,
                        })
                    else:
                        rtype = "external_sdk_dependency" if "az-invest" in t_low or "sdk/" in t_low else "external_or_missing_in_repo"
                        pre_resolved.append({
                            "task_id": tid, "kind": kind, "target": tgt, "status": "deferred",
                            "resolution_type": rtype, "local_path": "", "sha256": "",
                            "resolved_url": "", "newly_downloaded": False,
                            "details": f"Not present in {tree_info['repo']} tree ({len(tree_info['files'])} files scanned).",
                        })
            else:
                pre_resolved.append({
                    "task_id": tid, "kind": kind, "target": tgt, "status": "deferred",
                    "resolution_type": "repo_tree_unavailable", "local_path": "", "sha256": "",
                    "resolved_url": "", "newly_downloaded": False,
                })

        elif kind == "mql5_source_archive":
            cid = tgt.rstrip("/").split("/")[-1]
            it = mql_by_cid.get(cid, {})
            files = it.get("files") or []
            # Cross-check if any attachment filename matches an existing local file uniquely by code_id or exact unique filename
            matched_local = ""
            for f in files:
                fn = f.split(" (")[0].strip().split("\\")[-1].lower()
                if fn in by_name and len(by_name[fn]) == 1:
                    matched_local = by_name[fn][0]
                    break
            if matched_local:
                pre_resolved.append({
                    "task_id": tid, "kind": kind, "target": tgt, "status": "completed",
                    "resolution_type": "matched_existing_local_source", "local_path": matched_local,
                    "sha256": "", "resolved_url": tgt, "newly_downloaded": False,
                })
            else:
                pre_resolved.append({
                    "task_id": tid, "kind": kind, "target": tgt, "status": "blocked",
                    "resolution_type": "blocked_sandbox_mql5_ip",
                    "local_path": "", "sha256": "", "resolved_url": tgt, "newly_downloaded": False,
                    "files_listed": files,
                    "details": "Direct MQL5 raw .zip/.mq5 TCP connections dropped on sandbox IP; metadata/trading logic already persisted in batch2_mql5_fetched.json.",
                })
        else:
            raise RuntimeError(f"Unexpected Batch 3 task kind {kind} at {tid}")

    # 3. Execute unique GitHub dependency downloads in parallel
    print(f"Downloading {len(pending_gh_downloads)} unique resolved GitHub dependency files...")
    dl_results: dict[tuple[str, str], tuple[str, str, str, bool, str]] = {}

    def dl_one(item: tuple[tuple[str, str], str]) -> tuple[tuple[str, str], tuple[str, str, str, bool, str]]:
        (slug_low, rpath), raw_u = item
        code, raw, err = http_get(raw_u, timeout=25, retries=2)
        if code != 200 or not raw:
            return (slug_low, rpath), ("", "", raw_u, False, f"HTTP {code} {err}")
        h = sha256_bytes(raw)
        if h in by_sha:
            return (slug_low, rpath), (by_sha[h], h, raw_u, False, "dedup_existing_sha256")
        repo_dir = gh_trees[slug_low]["repo"].replace("/", "__")
        safe_name = rpath.replace("/", "__")
        dest = OUT_DEPS / "github" / repo_dir / safe_name
        rel, sha = safe_save(dest, raw)
        return (slug_low, rpath), (rel, sha, raw_u, True, "downloaded")

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        for k, val in ex.map(dl_one, pending_gh_downloads.items()):
            dl_results[k] = val

    # 4. Finalize resolutions list
    final_resolutions: list[dict[str, Any]] = []
    for rec in pre_resolved:
        if rec["status"] == "PENDING_GH_DL":
            k = (rec["repo_low"], rec["repo_path"])
            rel, sha, raw_u, newly, note = dl_results[k]
            if rel:
                final_resolutions.append({
                    "task_id": rec["task_id"], "kind": rec["kind"], "target": rec["target"],
                    "status": "completed", "resolution_type": f"github_tree_{note}",
                    "local_path": rel, "sha256": sha, "resolved_url": raw_u,
                    "newly_downloaded": newly,
                })
            else:
                final_resolutions.append({
                    "task_id": rec["task_id"], "kind": rec["kind"], "target": rec["target"],
                    "status": "blocked", "resolution_type": "github_raw_fetch_failed",
                    "local_path": "", "sha256": "", "resolved_url": raw_u,
                    "newly_downloaded": False, "details": note,
                })
        else:
            final_resolutions.append(rec)

    new_files_saved = sorted(str(p.relative_to(ROOT)) for p in OUT_B3.rglob("*") if p.is_file())
    # Also materialize any remaining unique MQL/Py/Pine files from the downloaded GitLab archives
    gitlab_extras: list[dict[str, Any]] = []
    for slug_low, gl_files in gl_archives.items():
        for repo_path, raw in sorted(gl_files.items()):
            h = sha256_bytes(raw)
            if h not in by_sha and Path(repo_path).suffix.lower() in (".mq4", ".mq5", ".mqh", ".h"):
                rel, sha, raw_u, newly = materialize_gitlab(slug_low, repo_path, "gitlab")
                if newly:
                    gitlab_extras.append({
                        "repo": slug_low, "repo_path": repo_path, "local_path": rel,
                        "sha256": sha, "resolved_url": raw_u,
                    })

    new_files_saved = sorted(str(p.relative_to(ROOT)) for p in OUT_B3.rglob("*") if p.is_file())
    new_bytes = sum((ROOT / r).stat().st_size for r in new_files_saved)
    summary = {
        "generated_utc": now_utc(),
        "total_tasks": len(final_resolutions),
        "by_status": dict(Counter(r["status"] for r in final_resolutions)),
        "by_kind_and_status": dict(Counter(f"{r['kind']}::{r['status']}" for r in final_resolutions)),
        "new_files_saved_on_disk": len(new_files_saved),
        "new_bytes_saved_on_disk": new_bytes,
        "gitlab_extra_archive_files_saved": len(gitlab_extras),
    }
    OUT_JSON.write_text(json.dumps({
        "summary": summary,
        "repo_trees_audited": {k: {kk: vv for kk, vv in v.items() if kk != "files"} | {"file_count": len(v.get("files", []))} for k, v in gh_trees.items()},
        "gitlab_extra_archive_files": gitlab_extras,
        "resolutions": final_resolutions,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print("BATCH 3 FETCH COMPLETE:")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
