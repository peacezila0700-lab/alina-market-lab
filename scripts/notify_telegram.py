#!/usr/bin/env python3
"""
scripts/notify_telegram.py — Push daily brief summary + offline HTML dashboard to a phone via Telegram.

Why this exists (mobile-only workflow, ฿0):
  With no PC, GitHub Actions runs `collect_daily.py` + `build_dashboard.py` on a schedule and calls
  this script to deliver the daily market state + self-contained `dashboard/alina_today.html` straight
  to Telegram on the user's phone.

Environment variables (or ~/.alina/telegram_{token,chat_id}):
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID

Live Telegram API sending is UNTESTED in this sandbox (requires user's bot token & chat_id).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import urllib.request
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _cfg(env_name: str, file_name: str) -> str:
    if os.environ.get(env_name):
        return os.environ[env_name].strip()
    p = Path.home() / ".alina" / file_name
    return p.read_text().strip() if p.exists() else ""


def format_message() -> str:
    brief = json.loads((ROOT / "briefs" / "latest.json").read_text())
    st = brief.get("state", {})
    d = brief.get("date") or brief.get("as_of") or "?"
    flags = brief.get("flags", [])

    exp_count = 0
    ep = ROOT / "research" / "EXPERIMENT_LOG.csv"
    if ep.exists():
        exp_count = max(0, len(list(csv.reader(ep.open()))) - 1)

    rr_path = ROOT / "data" / "risk_radar" / "latest.json"
    rr_block = ""
    if rr_path.exists():
        rr = json.loads(rr_path.read_text())
        rr_block = (
            f"Risk Radar: {rr.get('overall_risk_classification', '?')} "
            f"(Fresh {rr.get('fresh_panels', '?')}/{rr.get('total_panels', '?')}) | "
            f"Alerts: {len(rr.get('active_alerts', []))}\n"
        )
        if rr.get("missing_data_warnings"):
            rr_block += "Data Warnings: " + "; ".join(rr["missing_data_warnings"][:2]) + "\n"

    lines = [
        f"ALINA Risk Radar — {d}",
        rr_block.strip(),
        f"VIX: {st.get('vix', '?')} (pct {st.get('vix_percentile_all_history', '?')}) | "
        f"slope_3m: {st.get('vix_slope_3m', '?')}",
        f"VVIX pct: {st.get('vvix_percentile', '?')} | SKEW: {st.get('skew', '?')}",
        f"DIX: {st.get('dix', '?')} | GEX: {st.get('gex_usd_bn', '?')} bn ({st.get('gex_regime', '')})",
        "",
        "ธงเตือน: " + (" | ".join(flags[:4]) if flags else "ไม่มี"),
        "",
        f"สถานะวิจัย: {exp_count} การทดลอง, 0 validated edges (Risk Monitor Only — ไม่ใช่สัญญาณซื้อขาย)",
        "เปิดไฟล์ alina_today.html ด้านล่างบนมือถือได้ทันที (ไม่ต้องต่อเน็ต)",
    ]
    return "\n".join(line for line in lines if line is not None)


def send_text(token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = json.dumps({"chat_id": chat_id, "text": text}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        print("sendMessage:", r.status)


def send_document(token: str, chat_id: str, path: Path, caption: str = "") -> None:
    boundary = uuid.uuid4().hex
    parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"chat_id\"\r\n\r\n{chat_id}\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{caption}\r\n".encode(),
        (f"--{boundary}\r\nContent-Disposition: form-data; name=\"document\"; filename=\"{path.name}\"\r\n"
         f"Content-Type: text/html\r\n\r\n").encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode(),
    ]
    body = b"".join(parts)
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    req = urllib.request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=45) as r:
        print("sendDocument:", r.status)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    msg = format_message()
    dash = ROOT / "dashboard" / "alina_today.html"

    if args.dry_run:
        print("=== TELEGRAM DRY RUN ===")
        print(msg)
        print(f"Attachment: {dash} (exists={dash.exists()}, bytes={dash.stat().st_size if dash.exists() else 0})")
        return

    token = _cfg("TELEGRAM_BOT_TOKEN", "telegram_token")
    chat_id = _cfg("TELEGRAM_CHAT_ID", "telegram_chat_id")
    if not token or not chat_id:
        print("Telegram secrets not configured — skipping push cleanly.")
        return
    send_text(token, chat_id, msg)
    if dash.exists():
        send_document(token, chat_id, dash, caption="ALINA offline mobile dashboard")


if __name__ == "__main__":
    main()
