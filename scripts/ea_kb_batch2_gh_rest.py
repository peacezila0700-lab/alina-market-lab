#!/usr/bin/env python3
"""Finish remaining non-unit-test github_source_file downloads cleanly & audit sizes."""

from __future__ import annotations

import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/home/user/alina_lab")
KB = ROOT / "data" / "ea_kb"
OUT_GH = KB / "sources_batch2" / "github"


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
    sub1 = json.loads((KB / "batch2_subbatch_gh_gl_ff.json").read_text(encoding="utf-8"))
    sub2 = json.loads((KB / "batch2_subbatch_gh_expand.json").read_text(encoding="utf-8"))

    done_urls = set()
    for r in sub1.get("github_queue_downloads", []):
        if r.get("status") == "Completed":
            done_urls.add(r["url"])
    for r in sub2.get("gh_queue_results", []):
        done_urls.add(r["url"])

    gh_tasks = [t for t in tasks if t["kind"] == "github_source_file" and t["target"] not in done_urls]
    print("Remaining unprocessed github_source_file:", len(gh_tasks))

    res = []
    dl = 0
    deferred = 0
    failed = 0
    for t in gh_tasks:
        u = t["target"]
        ul = u.lower()
        if ("ea31337-classes" in ul and "/tests/" in ul) or ("profitable-expert-advisor" in ul and "/env/" in ul):
            deferred += 1
            res.append({"task_id": t["task_id"], "status": "Deferred", "url": u, "reason": "Unit-test or RL env boilerplate"})
            continue
        m = re.match(r"https://raw\.githubusercontent\.com/([^/]+/[^/]+)/[^/]+/(.+)", u)
        if not m:
            continue
        rep, rel = m.group(1), urllib.parse.unquote(m.group(2))
        dst = OUT_GH / rep.replace("/", "__") / rel.replace("/", "__")
        if dst.exists() and dst.stat().st_size > 0:
            res.append({
                "task_id": t["task_id"], "status": "Completed", "url": u,
                "local_path": str(dst.relative_to(ROOT)),
                "sha256": hashlib.sha256(dst.read_bytes()).hexdigest(), "bytes": dst.stat().st_size,
            })
            continue
        st, data, err = http_get(u)
        time.sleep(0.025)
        if st == 200 and data:
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(data)
            dl += 1
            res.append({
                "task_id": t["task_id"], "status": "Completed", "url": u,
                "local_path": str(dst.relative_to(ROOT)),
                "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
            })
        else:
            failed += 1
            res.append({
                "task_id": t["task_id"],
                "status": "Blocked" if st in (401, 403, 429) else "Deferred",
                "url": u, "http_status": st, "error": err,
            })

    total_b2_bytes = sum(p.stat().st_size for p in (KB / "sources_batch2").rglob("*") if p.is_file())
    total_b2_files = sum(1 for p in (KB / "sources_batch2").rglob("*") if p.is_file())
    out = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "downloaded": dl, "deferred": deferred, "failed": failed,
        "total_sources_batch2_files": total_b2_files,
        "total_sources_batch2_bytes": total_b2_bytes,
        "results": res,
    }
    (KB / "batch2_subbatch_gh_rest.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "results"}, indent=2))


if __name__ == "__main__":
    main()
