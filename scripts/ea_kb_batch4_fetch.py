#!/usr/bin/env python3
"""Batch 4 Acquisition Script for ALINA Global EA Intelligence KB.

Executes all 375 tasks in `data/ea_kb/research_queue_batch4.jsonl` (`Q-2876..Q-3250`):
  1. Resolves all sandbox-reachable `150` `batch3_new_include_dependency` headers from the audited
     GitHub repository trees (`EA31337/EA31337-classes`, `EA31337/EA31337`, `9nix6/...`,
     `PopovMP/FSB_Expert_Advisor_Code`, `francomascareloai/EA_SCALPER_XAUUSD`, `nkanven/...`)
     and GitLab Archive API v4 (`fxce/mt5-libs`, `Roffild/RoffildLibrary`), plus C++/OS/MQL stdlibs.
  2. Re-checks the `24` follow-up tasks (`18` B2 include, `4` B2 iCustom, `2` P1 dep) against local/repo trees.
  3. Cross-checks the `201` `mql5_source_archive_followup` tasks and honestly preserves sandbox IP blocks
     while linking them directly to `scripts/fetch_mql5_non_sandbox.py` for one-command external fetch.

All newly fetched files are stored strictly under `data/ea_kb/sources_batch4/` (never touching Batch 1-3).
Outputs `data/ea_kb/batch4_resolutions.json`.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import posixpath
import sys
import urllib.parse
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(os.environ.get("ALINA_ROOT", str(Path(__file__).resolve().parent.parent)))
KB = ROOT / "data" / "ea_kb"
OUT_B4 = KB / "sources_batch4"
OUT_GL = OUT_B4 / "gitlab"
OUT_GH = OUT_B4 / "github"
OUT_JSON = KB / "batch4_resolutions.json"
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from ea_kb_batch3_fetch import (  # noqa: E402
    MQL_STDLIB_EXACT,
    MQL_STDLIB_PREFIXES,
    MT_BUILTIN_ICUSTOM,
    fetch_github_tree,
    fetch_gitlab_archive,
    http_get,
    norm_slash,
    resolve_path_in_tree,
    safe_save,
    sha256_bytes,
)

for d in (OUT_B4, OUT_GL, OUT_GH):
    d.mkdir(parents=True, exist_ok=True)

EXTRA_STDLIB_EXACT = MQL_STDLIB_EXACT | {
    "iomanip", "locale", "sstream", "vector", "string", "memory", "algorithm",
    "windows.h", "python.h", "stdint.h", "stddef.h",
}


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def index_all_local() -> tuple[dict[str, str], dict[str, list[str]]]:
    by_sha: dict[str, str] = {}
    by_name: dict[str, list[str]] = {}
    for base in (KB / "sources", KB / "sources_batch2", KB / "sources_batch3", ROOT / "ea" / "AlinaRiskGovernor.mq5"):
        paths = [base] if base.is_file() else (sorted(p for p in base.rglob("*") if p.is_file()) if base.exists() else [])
        for p in paths:
            rel = str(p.relative_to(ROOT))
            h = sha256_bytes(p.read_bytes())
            by_sha.setdefault(h, rel)
            by_name.setdefault(p.name.lower(), []).append(rel)
    return by_sha, by_name


def main() -> None:
    b4_path = KB / "research_queue_batch4.jsonl"
    b4_rows = [json.loads(l) for l in b4_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"Loaded {len(b4_rows)} Batch 4 tasks from {b4_path}.")

    by_sha, by_name = index_all_local()
    probe = json.loads((KB / "batch2_gitlab_gh75_probe.json").read_text(encoding="utf-8"))
    b3_json = json.loads((KB / "batch3_resolutions.json").read_text(encoding="utf-8"))
    mql_fetched = json.loads((KB / "batch2_mql5_fetched.json").read_text(encoding="utf-8"))
    mql_by_cid = {str(x["code_id"]): x for x in mql_fetched.get("codebase_items", [])}

    # 1. Fetch GitLab archives (fxce/mt5-libs + Roffild/RoffildLibrary)
    gl_archives: dict[str, dict[str, bytes]] = {}
    for slug in ("fxce/mt5-libs", "Roffild/RoffildLibrary"):
        print(f"Downloading GitLab archive for {slug}...")
        _, files = fetch_gitlab_archive(slug)
        gl_archives[slug.lower()] = files
        print(f"  -> Extracted {len(files)} files from {slug}.")

    # 2. Fetch full GitHub file trees across all needed repos
    gh_trees: dict[str, dict[str, Any]] = {}
    for r in probe.get("github_75_repos", []):
        files = list(r.get("mql_files", [])) + list(r.get("py_files", [])) + list(r.get("pine_files", []))
        gh_trees[r["repo"].lower()] = {
            "repo": r["repo"], "ok": True,
            "default_branch": r.get("default_branch", "main"),
            "files": files, "source": "gh75_cache",
        }
    needed_gh_repos: set[str] = {
        "EA31337/EA31337-classes", "EA31337/EA31337",
        "9nix6/Median-and-Turbo-Renko-indicator-bundle",
        "PopovMP/FSB_Expert_Advisor_Code",
        "francomascareloai/EA_SCALPER_XAUUSD",
        "nkanven/MT4-MT5-Trading-EA-Collections",
        "CThompson18/MQL5", "GeneralTradingSarl/Smart-Money-Concepts",
        "GeneralTradingSarl/expert-mt5", "peterthomet/MetaTrader-5-and-4-Tools",
    }
    for row in b4_rows:
        df = row.get("discovered_from", "")
        if "raw.githubusercontent.com/" in df:
            ps = df.split("raw.githubusercontent.com/")[1].split("/")
            if len(ps) >= 2:
                needed_gh_repos.add(f"{ps[0]}/{ps[1]}")

    for slug in sorted(needed_gh_repos):
        if slug.lower() not in gh_trees:
            print(f"Fetching GitHub tree for {slug}...")
            tinfo = fetch_github_tree(slug)
            tinfo["source"] = "github_api_b4"
            gh_trees[slug.lower()] = tinfo
            print(f"  -> ok={tinfo['ok']} branch={tinfo.get('default_branch')} files={len(tinfo.get('files', []))}")

    # Also build synthetic source URLs from Batch 3 local path when discovered_from points to raw GitHub
    pending_gh_downloads: dict[tuple[str, str], str] = {}
    pre_resolved: list[dict[str, Any]] = []
    b4_saved_by_key: dict[tuple[str, str], tuple[str, str, str]] = {}

    def materialize_gitlab(slug_low: str, repo_path: str) -> tuple[str, str, str, bool]:
        key = ("gl:" + slug_low, repo_path)
        if key in b4_saved_by_key:
            r, s, u = b4_saved_by_key[key]
            return r, s, u, False
        raw = gl_archives[slug_low][repo_path]
        h = sha256_bytes(raw)
        if h in by_sha:
            rel_existing = by_sha[h]
            url = f"https://gitlab.com/{slug_low}/-/raw/HEAD/{repo_path}"
            b4_saved_by_key[key] = (rel_existing, h, url)
            return rel_existing, h, url, False
        repo_dir = slug_low.replace("/", "__")
        safe_name = repo_path.replace("/", "__")
        dest = OUT_GL / repo_dir / safe_name
        rel, sha = safe_save(dest, raw)
        by_sha[sha] = rel
        url = f"https://gitlab.com/{slug_low}/-/raw/HEAD/{repo_path}"
        b4_saved_by_key[key] = (rel, sha, url)
        return rel, sha, url, True

    def extract_slug_from_row(row: dict[str, Any]) -> str:
        df = row.get("discovered_from", "")
        notes = row.get("notes", "")
        if "raw.githubusercontent.com/" in df:
            ps = df.split("raw.githubusercontent.com/")[1].split("/")
            return f"{ps[0]}/{ps[1]}".lower()
        if "gitlab.com/" in df:
            ps = df.split("gitlab.com/")[1].split("/")
            return f"{ps[0]}/{ps[1]}".lower()
        for sl in list(gh_trees.keys()) + list(gl_archives.keys()):
            if sl in notes.lower():
                return sl
        return ""

    for row in b4_rows:
        tid = row["task_id"]
        kind = row["kind"]
        tgt = row["target"]
        df = row.get("discovered_from", "")

        if kind == "mql5_source_archive_followup":
            cid = tgt.rstrip("/").split("/")[-1]
            it = mql_by_cid.get(cid, {})
            files = it.get("files") or []
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
                    "resolution_type": "blocked_sandbox_mql5_ip", "local_path": "", "sha256": "",
                    "resolved_url": tgt, "newly_downloaded": False, "files_listed": files,
                    "details": "Sandbox IP blocked by MQL5 raw download CDN; ready via scripts/fetch_mql5_non_sandbox.py.",
                })
            continue

        t_norm = norm_slash(tgt).lstrip(":")
        t_low = t_norm.lower()
        bn = Path(t_low).name

        # Stdlib / built-in check
        if (
            ("icustom" in kind and (t_low in MT_BUILTIN_ICUSTOM or t_low.startswith("examples/")))
            or ("icustom" not in kind and (any(t_low.startswith(p) for p in MQL_STDLIB_PREFIXES) or bn in EXTRA_STDLIB_EXACT or t_low in EXTRA_STDLIB_EXACT))
        ):
            pre_resolved.append({
                "task_id": tid, "kind": kind, "target": tgt, "status": "completed_stdlib_builtin",
                "resolution_type": "mql_cpp_or_os_stdlib_builtin", "local_path": "", "sha256": "",
                "resolved_url": "https://www.mql5.com/en/docs/standardlibrary", "newly_downloaded": False,
            })
            continue

        # Local KB match by unique filename (e.g., ToIndicator.mqh, stdafx.h, public.h)
        local_hits = by_name.get(bn, [])
        if len(local_hits) >= 1 and ("/" not in t_norm or any(h.lower().endswith(t_low.replace("/", "__")) for h in local_hits)):
            chosen = next((h for h in local_hits if h.lower().endswith(t_low.replace("/", "__"))), local_hits[0])
            pre_resolved.append({
                "task_id": tid, "kind": kind, "target": tgt, "status": "completed",
                "resolution_type": "matched_existing_local_source", "local_path": chosen,
                "sha256": "", "resolved_url": "local://" + chosen, "newly_downloaded": False,
            })
            continue

        slug_low = extract_slug_from_row(row)
        extra_exts = (".mq5", ".mq4", ".ex5") if "icustom" in kind else ()

        if slug_low in gl_archives:
            gl_files = gl_archives[slug_low]
            resolved = resolve_path_in_tree(t_norm, df, list(gl_files.keys()), extra_exts=extra_exts)
            if not resolved and bn:
                # Search by basename inside archive when relative path crosses subfolders (e.g. ../CustomBot.mqh, Roffild/*.mqh)
                cands = [p for p in gl_files if Path(p).name.lower() == bn or p.lower().endswith("/" + t_low)]
                if cands:
                    resolved = sorted(cands, key=len)[0]
            if resolved:
                rel, sha, raw_u, newly = materialize_gitlab(slug_low, resolved)
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
                    "details": f"Not found in {slug_low} archive ({len(gl_files)} files).",
                })
        elif slug_low in gh_trees and gh_trees[slug_low].get("ok"):
            tree_info = gh_trees[slug_low]
            resolved = resolve_path_in_tree(t_norm, df, tree_info["files"], extra_exts=extra_exts)
            alt_slug = ""
            # Handle EA31337 relative / root-based includes cleanly
            if not resolved and slug_low in ("ea31337/ea31337-classes", "ea31337/ea31337"):
                # Try normalized suffix match ignoring leading ../
                clean_bn = Path(t_low).name
                cands = [p for p in tree_info["files"] if p.lower().endswith("/" + clean_bn) or p.lower() == clean_bn]
                if len(cands) == 1:
                    resolved = cands[0]
                elif len(cands) > 1:
                    # Prefer match sharing subfolder hint from target or parent URL
                    best = [c for c in cands if norm_slash(t_norm.lstrip("./")).lower() in c.lower()]
                    resolved = sorted(best or cands, key=len)[0]
                if not resolved and slug_low == "ea31337/ea31337":
                    c2 = [p for p in gh_trees.get("ea31337/ea31337-classes", {}).get("files", []) if p.lower().endswith("/" + clean_bn) or p.lower() == clean_bn]
                    if c2:
                        resolved = sorted(c2, key=len)[0]
                        alt_slug = "ea31337/ea31337-classes"
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
                "details": f"No repo tree mapping for {df or tid}.",
            })

    print(f"Downloading {len(pending_gh_downloads)} unique resolved Batch 4 GitHub files...")
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
        dest = OUT_GH / repo_dir / safe_name
        rel, sha = safe_save(dest, raw)
        return (slug_low, rpath), (rel, sha, raw_u, True, "downloaded")

    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as ex:
        for k, val in ex.map(dl_one, pending_gh_downloads.items()):
            dl_results[k] = val

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

    new_files_saved = sorted(str(p.relative_to(ROOT)) for p in OUT_B4.rglob("*") if p.is_file())
    new_bytes = sum((ROOT / r).stat().st_size for r in new_files_saved)
    summary = {
        "generated_utc": now_utc(),
        "total_tasks": len(final_resolutions),
        "by_status": dict(Counter(r["status"] for r in final_resolutions)),
        "by_kind_and_status": dict(Counter(f"{r['kind']}::{r['status']}" for r in final_resolutions)),
        "new_files_saved_on_disk": len(new_files_saved),
        "new_bytes_saved_on_disk": new_bytes,
    }
    OUT_JSON.write_text(json.dumps({
        "summary": summary,
        "resolutions": final_resolutions,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print("BATCH 4 FETCH COMPLETE:")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
