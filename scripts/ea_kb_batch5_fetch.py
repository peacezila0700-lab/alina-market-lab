#!/usr/bin/env python3
"""
Workstream C — EA KB Batch 5 Reachable GitHub Header Resolver
Resolves all legitimate open-source GitHub dependencies in `data/ea_kb/research_queue_batch5.jsonl`
(`batch4_new_include_dependency` + any reachable non-MQL5 GitHub targets) WITHOUT attempting to
bypass MQL5's HTTP 403 / IP access controls on the 201 `mql5_external_archive` records.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(os.environ.get("ALINA_ROOT", Path(__file__).resolve().parents[1]))
KB = ROOT / "data" / "ea_kb"
Q5_PATH = KB / "research_queue_batch5.jsonl"
OUT_DIR = KB / "sources_batch5"
UA = {"User-Agent": "Mozilla/5.0"}


def get_json(url: str) -> dict | list | None:
    try:
        req = urllib.request.Request(url, headers={**UA, "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode("utf-8", "replace"))
    except Exception:  # noqa: BLE001
        return None


def get_raw(url: str) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.read()
    except Exception:  # noqa: BLE001
        return None


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    tasks = [json.loads(l) for l in Q5_PATH.open() if l.strip()]

    # Build GitHub tree index for every repo referenced in `discovered_from`
    repo_trees: dict[str, dict[str, str]] = {}
    repos_needed = set()
    for t in tasks:
        df = t.get("discovered_from") or ""
        if "raw.githubusercontent.com/" in df:
            parts = df.split("raw.githubusercontent.com/")[1].split("/")
            if len(parts) >= 2:
                repos_needed.add(f"{parts[0]}/{parts[1]}")

    for repo in sorted(repos_needed):
        meta = get_json(f"https://api.github.com/repos/{repo}")
        branch = (meta or {}).get("default_branch", "master")
        tree = get_json(f"https://api.github.com/repos/{repo}/git/trees/{branch}?recursive=1")
        if tree and "tree" in tree:
            idx = {}
            for node in tree["tree"]:
                if node.get("type") == "blob":
                    p = node["path"]
                    idx[p.lower()] = (p, f"https://raw.githubusercontent.com/{repo}/{branch}/{p}")
            repo_trees[repo] = idx
            print(f"  GitHub tree indexed {repo}@{branch}: {len(idx)} blobs")
        time.sleep(0.15)

    stdlib_cxx = {"limits", "cmath", "cstdio", "cstdlib", "cstring", "cstdint", "string", "vector", "map", "algorithm"}
    resolved_files = 0
    stats = defaultdict(int)
    resolutions = []

    for t in tasks:
        kind = t.get("kind")
        if kind == "mql5_external_archive":
            t["status"] = "blocked_ip_403_external"
            stats["mql5_blocked_external"] += 1
            continue

        target = (t.get("target") or "").strip().strip('"<>').replace("\\", "/")
        base_name = os.path.basename(target).lower()
        if target.lower() in stdlib_cxx or base_name in stdlib_cxx:
            t["status"] = "completed_stdlib_builtin"
            stats["stdlib_builtin"] += 1
            continue

        df = t.get("discovered_from") or ""
        repo = None
        if "raw.githubusercontent.com/" in df:
            parts = df.split("raw.githubusercontent.com/")[1].split("/")
            if len(parts) >= 2:
                repo = f"{parts[0]}/{parts[1]}"

        matched_url = None
        matched_path = None
        if repo and repo in repo_trees:
            idx = repo_trees[repo]
            # Exact suffix match first, then basename match
            norm_t = target.lstrip("./").lower()
            for k_low, (orig_p, raw_u) in idx.items():
                if k_low.endswith(norm_t):
                    matched_path, matched_url = orig_p, raw_u
                    break
            if not matched_url:
                for k_low, (orig_p, raw_u) in idx.items():
                    if os.path.basename(k_low) == base_name:
                        matched_path, matched_url = orig_p, raw_u
                        break

        if matched_url:
            repo_dir = OUT_DIR / "github" / repo.replace("/", "__")
            repo_dir.mkdir(parents=True, exist_ok=True)
            safe_fn = matched_path.replace("/", "__")
            dest = repo_dir / safe_fn
            if not dest.exists():
                raw = get_raw(matched_url)
                if raw:
                    dest.write_bytes(raw)
                    resolved_files += 1
                    time.sleep(0.05)
            if dest.exists():
                t["status"] = "completed"
                t["notes"] = f"Resolved from {matched_url}"
                stats["completed"] += 1
                resolutions.append({"task_id": t.get("task_id"), "target": target, "url": matched_url, "local_path": str(dest)})
                continue

        t["status"] = "deferred_external_sdk"
        stats["deferred_external_sdk"] += 1

    with Q5_PATH.open("w") as fh:
        for t in tasks:
            fh.write(json.dumps(t, ensure_ascii=False) + "\n")

    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "queue_total": len(tasks),
        "new_files_downloaded": resolved_files,
        "status_counts": dict(stats),
        "resolutions_sample": resolutions[:20],
    }
    (KB / "batch5_resolutions.json").write_text(json.dumps(summary, indent=2))
    print("BATCH 5 FETCH SUMMARY:", json.dumps({k: v for k, v in summary.items() if k != "resolutions_sample"}, indent=2))


if __name__ == "__main__":
    main()
