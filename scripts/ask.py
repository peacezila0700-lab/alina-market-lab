#!/usr/bin/env python3
"""
scripts/ask.py — Compose a compact, rule-enforced prompt from ALINA's derived files and call a free LLM.

Why this exists (zero-budget & mobile-ready):
  Instead of indexing 400 GB into a paid vector DB, we feed ONLY the curated ~40 KB state:
    1) briefs/latest.md                  (~6.6 KB)
    2) packs/<latest>.json               (~35 KB)
    3) compact dataset index / exp tally (~3 KB, or catalog.json if present)

Providers supported (zero GPU required):
  * gemini      Google AI Studio free tier (`GEMINI_API_KEY` or ~/.alina/gemini_key)
  * groq        Groq free tier (`GROQ_API_KEY` or ~/.alina/groq_key)
  * openrouter  OpenRouter `:free` models (`OPENROUTER_API_KEY` or ~/.alina/openrouter_key)
  * ollama      Local Ollama (http://127.0.0.1:11434) if running on a PC
  * dry-run     Print exact composed payload + byte/token estimate (no network call)

Note: Live external provider calls are UNTESTED inside this sandbox (no user API keys stored here).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SYSTEM_RULES = """You are ALINA Market Lab's research analyst. Answer in concise, direct Thai (unless asked in English).
HARD RULES (never violate):
1. Quote ONLY numbers present in the supplied brief, event pack, or experiment summary.
2. NEVER call any signal or rule an "edge" unless it passed BOTH in-sample and out-of-sample pre-registered bars.
3. Always state `n_eff` (or sample count `n`) and cost assumptions alongside any conditional return / base rate.
4. If asked about data, prices, or tests NOT in the context, reply exactly "ยังไม่ได้ทดสอบ" or "ไม่มีข้อมูลในแพ็กนี้" — NEVER fabricate numbers.
5. Never give buy/sell trade recommendations or position advice; present base rates, spreads, invalidation levels, and uncertainty."""


def _load_key(env_name: str, file_name: str) -> str:
    if os.environ.get(env_name):
        return os.environ[env_name].strip()
    p = Path.home() / ".alina" / file_name
    if p.exists():
        return p.read_text().strip()
    return ""


def _compact_catalog_summary() -> str:
    # Prefer built catalog.json if present; otherwise extract dataset IDs + titles from build_datapack.py
    cat_path = ROOT / "pack" / "ALINA_DATAPACK" / "catalog.json"
    if cat_path.exists():
        data = json.loads(cat_path.read_text())
        lines = [f"- {d['id']} [{d.get('grade', '?')}]: {d.get('title', '')}" for d in data.get("datasets", [])]
        return "\n".join(lines)
    bp = ROOT / "scripts" / "build_datapack.py"
    if bp.exists():
        txt = bp.read_text()
        matches = re.findall(r'dict\(id="([^"]+)".*?title="([^"]+)"', txt, flags=re.S)
        if matches:
            return "\n".join(f"- {i}: {t}" for i, t in matches)
    return "(catalog unavailable)"


def _experiment_tally() -> str:
    ep = ROOT / "research" / "EXPERIMENT_LOG.csv"
    if not ep.exists():
        return "Experiment tally unavailable."
    rows = list(csv.DictReader(ep.open()))
    passed = [r["exp_id"] for r in rows if "PASS" in (r.get("result_status") or "").upper()]
    tail = rows[-3:] if len(rows) >= 3 else rows
    lines = [
        f"Total registered experiments: {len(rows)} | Validated PASS: {len(passed)}",
        "Latest experiments:",
    ]
    for r in tail:
        lines.append(f"  * {r['exp_id']} ({r['hyp_id']}): {r['result_status']} — {r['decision'][:140]}")
    return "\n".join(lines)


def build_context(with_catalog: bool = False, max_pack_chars: int = 24000) -> str:
    parts = []
    brief_md = ROOT / "briefs" / "latest.md"
    if brief_md.exists():
        parts.append("=== BRIEFS/LATEST.MD ===\n" + brief_md.read_text().strip())

    packs = sorted((ROOT / "packs").glob("*.json"))
    if packs:
        ptxt = packs[-1].read_text().strip()
        if len(ptxt) > max_pack_chars:
            ptxt = ptxt[:max_pack_chars] + "\n... (truncated for prompt budget)"
        parts.append(f"=== {packs[-1].name} ===\n" + ptxt)

    parts.append("=== EXPERIMENT TALLY ===\n" + _experiment_tally())
    if with_catalog:
        parts.append("=== DATASET INDEX ===\n" + _compact_catalog_summary())
    return "\n\n".join(parts)


def call_openai_compat(url: str, key: str, model: str, system: str, user_msg: str, extra_headers: dict | None = None) -> str:
    payload = json.dumps({
        "model": model,
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
    }).encode()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, data=payload, headers=headers)
    with urllib.request.urlopen(req, timeout=90) as r:
        res = json.loads(r.read().decode())
    return res["choices"][0]["message"]["content"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("question", nargs="?", default="สรุปสภาวะตลาดวันนี้ base rates ที่มี n_eff ชัดเจน และจุดที่ต้องระวัง")
    ap.add_argument("--provider", choices=["dry-run", "gemini", "groq", "openrouter", "ollama"], default="dry-run")
    ap.add_argument("--dry-run", action="store_true", help="Alias for --provider dry-run")
    ap.add_argument("--model", default="")
    ap.add_argument("--with-catalog", action="store_true")
    ap.add_argument("--key", default="")
    args = ap.parse_args()
    if args.dry_run:
        args.provider = "dry-run"

    ctx = build_context(with_catalog=args.with_catalog)
    user_msg = f"{ctx}\n\n=== QUESTION ===\n{args.question}"

    if args.provider == "dry-run":
        est_tokens = (len(SYSTEM_RULES) + len(user_msg)) // 4
        print(f"[dry-run] context chars={len(user_msg):,} (~{est_tokens:,} tokens est.)")
        print(f"[dry-run] system rules chars={len(SYSTEM_RULES)}")
        print(f"[dry-run] question={args.question}")
        print("[dry-run] sections:", [line for line in user_msg.splitlines() if line.startswith("=== ")])
        return

    if args.provider == "gemini":
        key = args.key or _load_key("GEMINI_API_KEY", "gemini_key")
        if not key:
            raise SystemExit("Missing Gemini key: set GEMINI_API_KEY or save to ~/.alina/gemini_key")
        model = args.model or "gemini-2.5-flash"
        url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        print(call_openai_compat(url, key, model, SYSTEM_RULES, user_msg))

    elif args.provider == "groq":
        key = args.key or _load_key("GROQ_API_KEY", "groq_key")
        if not key:
            raise SystemExit("Missing Groq key: set GROQ_API_KEY or save to ~/.alina/groq_key")
        model = args.model or "llama-3.3-70b-versatile"
        url = "https://api.groq.com/openai/v1/chat/completions"
        print(call_openai_compat(url, key, model, SYSTEM_RULES, user_msg))

    elif args.provider == "openrouter":
        key = args.key or _load_key("OPENROUTER_API_KEY", "openrouter_key")
        if not key:
            raise SystemExit("Missing OpenRouter key: set OPENROUTER_API_KEY or save to ~/.alina/openrouter_key")
        model = args.model or "meta-llama/llama-3.3-70b-instruct:free"
        url = "https://openrouter.ai/api/v1/chat/completions"
        print(call_openai_compat(url, key, model, SYSTEM_RULES, user_msg))

    elif args.provider == "ollama":
        model = args.model or "qwen3:8b"
        url = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/v1/chat/completions")
        print(call_openai_compat(url, "", model, SYSTEM_RULES, user_msg))


if __name__ == "__main__":
    main()
