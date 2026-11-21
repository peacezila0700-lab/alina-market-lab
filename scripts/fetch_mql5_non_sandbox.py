#!/usr/bin/env python3
"""Standalone Non-Sandbox MQL5 CodeBase Archive Downloader.

Why this exists:
  In Batch 2/3/4, all 205 queued MQL5 CodeBase metadata pages, profiles, and logic summaries were
  fetched and persisted into `data/ea_kb/batch2_mql5_fetched.json`. However, direct TCP connections
  to `https://www.mql5.com/en/code/download/...` are blocked/reset on the Arena sandbox IP, and
  HTML-to-Markdown proxies strip `<...>` comparison/include delimiters.

Usage (on local machine, Colab, or external VPS with normal internet access):
  python3 scripts/fetch_mql5_non_sandbox.py --out data/ea_kb/sources_mql5_external

Downloads the raw `.mq5/.mq4/.mqh/.zip` files for all queued `mql5_source_archive_followup` items,
verifies non-HTML integrity, extracts `.zip` bundles cleanly, records SHA-256 checksums, and writes
`data/ea_kb/mql5_external_manifest.json` ready for re-ingestion into `ea_kb_batch4_build.py`.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KB = ROOT / "data" / "ea_kb"


def sanitize(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_")


def fetch_url(url: str, timeout: int = 30) -> tuple[int, bytes, str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128.0",
        "Accept": "*/*",
        "Referer": "https://www.mql5.com/en/code",
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), ""
    except urllib.error.HTTPError as e:
        return e.code, b"", f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        return 0, b"", f"{type(e).__name__}: {e}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(KB / "sources_mql5_external"))
    ap.add_argument("--delay", type=float, default=1.2)
    ap.add_argument("--limit", type=int, default=0, help="0 = download all queued tasks")
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    mql_fetched = json.loads((KB / "batch2_mql5_fetched.json").read_text(encoding="utf-8"))
    by_cid = {str(x["code_id"]): x for x in mql_fetched.get("codebase_items", [])}
    b4 = [json.loads(l) for l in (KB / "research_queue_batch4.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    targets = [r for r in b4 if r["kind"] == "mql5_source_archive_followup"]
    if args.limit > 0:
        targets = targets[:args.limit]

    manifest = []
    for i, task in enumerate(targets, 1):
        cid = task["target"].rstrip("/").split("/")[-1]
        item = by_cid.get(cid, {})
        files = item.get("files") or []
        saved = []
        errs = []
        zip_url = f"https://www.mql5.com/en/code/download/{cid}"
        dl_candidates = [zip_url]
        for f in files:
            fn = f.split(" (")[0].strip().split("\\")[-1]
            if fn:
                dl_candidates.append(f"https://www.mql5.com/en/code/download/{cid}/{fn}")

        for url in dl_candidates:
            code, raw, err = fetch_url(url)
            time.sleep(args.delay)
            if code != 200 or not raw:
                errs.append(f"{url} -> {code} {err}")
                continue
            head_low = raw[:256].lstrip().lower()
            if head_low.startswith(b"<!doctype html") or head_low.startswith(b"<html"):
                errs.append(f"{url} -> HTML error page")
                continue
            cdir = out_dir / cid
            cdir.mkdir(parents=True, exist_ok=True)
            if raw[:2] == b"PK":
                with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                    for info in zf.infolist():
                        if info.is_dir():
                            continue
                        bname = sanitize(Path(info.filename).name)
                        if not bname:
                            continue
                        content = zf.read(info.filename)
                        p = cdir / bname
                        p.write_bytes(content)
                        saved.append({"path": str(p.relative_to(ROOT)), "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest()})
                break
            else:
                bname = sanitize(url.rsplit("/", 1)[-1]) or f"{cid}.mq5"
                p = cdir / bname
                p.write_bytes(raw)
                saved.append({"path": str(p.relative_to(ROOT)), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})

        status = "completed" if saved else "failed"
        print(f"[{i}/{len(targets)}] code_id={cid} -> {status} ({len(saved)} files)")
        manifest.append({"task_id": task["task_id"], "code_id": cid, "status": status, "saved": saved, "errors": errs})

    mpath = KB / "mql5_external_manifest.json"
    mpath.write_text(json.dumps({"total": len(manifest), "completed": sum(1 for x in manifest if x["status"] == "completed"), "items": manifest}, indent=2), encoding="utf-8")
    print(f"Saved external MQL5 manifest to {mpath}")


if __name__ == "__main__":
    main()
