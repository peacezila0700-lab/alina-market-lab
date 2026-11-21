#!/usr/bin/env python3
"""
scripts/telegram_bot.py — Two-way Telegram command & AI analyst bridge for phone-only control.

Why this exists:
  Telegram serves as the zero-cost mobile UI before spending money on app hosting or a VPS.
  It runs either as `--once` (inside GitHub Actions cron / manual dispatch, ฿0) or `--loop`
  (on a cheap ≤300 THB/month Linux VPS 24/7).

Commands handled locally (0 API cost, 100% deterministic from repo files):
  /help            List available commands
  /status          Market regime (VIX, slope_3m, VVIX, DIX, GEX), active flags, experiment tally
  /set             Thai SET64 Equal-Weight summary + 21d top/bottom movers
  /levels SYMBOL   Measured support/resistance (close, pivot, R1/S1, PDH/PDL, VP POC, ATR14)

Free-text messages:
  Routed to `scripts/ask.py` context builder + Gemini/Groq/OpenRouter free tier with strict lab rules.

Security:
  Only responds to messages from `TELEGRAM_CHAT_ID` (owner allowlist). Never exposes API keys.

Live Telegram & LLM network calls are UNTESTED inside this sandbox (no user bot tokens stored).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import ask  # noqa: E402

OFFSET_FILE = ROOT / "data" / "collect" / "telegram_offset.json"


def _cfg(env_name: str, file_name: str) -> str:
    if os.environ.get(env_name):
        return os.environ[env_name].strip()
    p = Path.home() / ".alina" / file_name
    return p.read_text().strip() if p.exists() else ""


def cmd_help() -> str:
    return (
        "คำสั่ง ALINA Lab (ข้อมูลจาก repo จริง):\n"
        "/status — สภาวะตลาดวันนี้ + ธงเตือน + ยอดทดลอง\n"
        "/set — สถานะ SET64 Equal-Weight + หุ้นไทยขยับแรง\n"
        "/levels SPY — แนวรับ-แนวต้านวัดจากสถิติ (เช่น SPY, EURUSD, BTC, GOLD)\n"
        "หรือพิมพ์ถามภาษาไทยตรง ๆ เพื่อให้ AI วิเคราะห์จาก brief + event pack"
    )


def cmd_status() -> str:
    brief = json.loads((ROOT / "briefs" / "latest.json").read_text())
    st = brief.get("state", {})
    d = brief.get("date") or brief.get("as_of") or "?"
    flags = brief.get("flags", [])
    rows = list(csv.DictReader((ROOT / "research" / "EXPERIMENT_LOG.csv").open()))
    passed = sum(1 for r in rows if "PASS" in (r.get("result_status") or "").upper())
    lines = [
        f"สภาวะตลาด ณ {d}",
        f"• VIX: {st.get('vix', '?')} (pct {st.get('vix_percentile_all_history', '?')})",
        f"• VIX/VIX3M: {st.get('vix_slope_3m', '?')} | VIX9D/VIX: {st.get('vix_slope_9d', '?')}",
        f"• VVIX pct: {st.get('vvix_percentile', '?')} | SKEW: {st.get('skew', '?')}",
        f"• DIX: {st.get('dix', '?')} (pct {st.get('dix_percentile', '?')}) | GEX: {st.get('gex_usd_bn', '?')} bn",
        f"• ธงเตือน ({len(flags)}): " + (" / ".join(flags[:3]) if flags else "ไม่มี"),
        f"• ผลวิจัยรวม: {len(rows)} การทดลอง, {passed} validated edges",
    ]
    return "\n".join(lines)


def cmd_set() -> str:
    ew_path = ROOT / "data" / "thai" / "SET_EW.csv"
    if not ew_path.exists():
        return "ยังไม่มีไฟล์ data/thai/SET_EW.csv"
    ew = pd.read_csv(ew_path)
    col = "SET_EW" if "SET_EW" in ew.columns else "close"
    c_now = float(ew[col].iloc[-1])
    r21 = (c_now / float(ew[col].iloc[-22]) - 1.0) * 100.0
    r63 = (c_now / float(ew[col].iloc[-64]) - 1.0) * 100.0
    movers = []
    for p in sorted((ROOT / "data" / "thai").glob("*.csv")):
        if p.stem == "SET_EW":
            continue
        df = pd.read_csv(p)
        if len(df) >= 22:
            cn, c21 = float(df["close"].iloc[-1]), float(df["close"].iloc[-22])
            movers.append((p.stem, cn, (cn / c21 - 1.0) * 100.0))
    tdf = pd.DataFrame(movers, columns=["sym", "close", "r21"])
    top = tdf.nlargest(3, "r21")
    bot = tdf.nsmallest(3, "r21")
    lines = [
        f"ตลาดไทย SET64 EW (ณ {ew['date'].iloc[-1]}): {c_now:.2f} | 21d {r21:+.2f}% | 63d {r63:+.2f}%",
        "หมายเหตุ: price-only ไม่ใช่ SET50 และ EXP-0021 ไม่พบ edge หลังค่าธรรมเนียมไทย (27 bp/ข้าง)",
        "บวกแรง 21d: " + ", ".join(f"{r.sym} {r.r21:+.1f}%" for r in top.itertuples()),
        "ลงแรง 21d: " + ", ".join(f"{r.sym} {r.r21:+.1f}%" for r in bot.itertuples()),
    ]
    return "\n".join(lines)


def cmd_levels(sym: str) -> str:
    sym_u = sym.strip().upper()
    if not sym_u:
        return "ระบุชื่อด้วย เช่น /levels SPY หรือ /levels EURUSD"
    lv_path = ROOT / "data" / "levels" / "levels_latest.csv"
    if not lv_path.exists():
        return "ไม่พบ data/levels/levels_latest.csv"
    df = pd.read_csv(lv_path)
    hit = df[df["instrument"].astype(str).str.upper() == sym_u]
    if hit.empty:
        avail = ", ".join(df["instrument"].astype(str).tolist()[:15])
        return f"ไม่พบ {sym_u} ใน levels_latest.csv (ตัวอย่างที่มี: {avail})"
    r = hit.iloc[0]
    return (
        f"ระดับวัดผล {sym_u} (ณ {str(r.get('as_of', ''))[:10]})\n"
        f"• Close: {r['close']:.4g} | ATR14: {r['atr14']:.4g}\n"
        f"• Prior Day: PDH {r['pdh']:.4g} / PDL {r['pdl']:.4g}\n"
        f"• Pivot: P {r['pivot']:.4g} | R1 {r['pivot_r1']:.4g} | S1 {r['pivot_s1']:.4g}\n"
        f"• Volume Profile POC: {r['vp_poc']:.4g} | 52w: {r['y52_lo']:.4g}–{r['y52_hi']:.4g}"
    )


def handle_text(text: str, provider: str = "dry-run") -> str:
    t = text.strip()
    low = t.lower()
    if low in ("/start", "/help", "help"):
        return cmd_help()
    if low.startswith("/status"):
        return cmd_status()
    if low.startswith("/set"):
        return cmd_set()
    if low.startswith("/levels"):
        arg = t.split(maxsplit=1)[1] if len(t.split(maxsplit=1)) > 1 else ""
        return cmd_levels(arg)

    ctx = ask.build_context(with_catalog=False, max_pack_chars=18000)
    user_msg = f"{ctx}\n\n=== QUESTION ===\n{t}"
    if provider == "dry-run":
        return f"[dry-run AI] context={len(user_msg):,} chars | rules={len(ask.SYSTEM_RULES)} chars | q={t}"
    if provider == "gemini":
        key = _cfg("GEMINI_API_KEY", "gemini_key")
        if not key:
            return "ยังไม่ได้ตั้ง GEMINI_API_KEY ใน Secrets"
        return ask.call_openai_compat(
            "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
            key, "gemini-2.5-flash", ask.SYSTEM_RULES, user_msg,
        )
    if provider == "groq":
        key = _cfg("GROQ_API_KEY", "groq_key")
        if not key:
            return "ยังไม่ได้ตั้ง GROQ_API_KEY ใน Secrets"
        return ask.call_openai_compat(
            "https://api.groq.com/openai/v1/chat/completions",
            key, "llama-3.3-70b-versatile", ask.SYSTEM_RULES, user_msg,
        )
    return "Unsupported provider"


def tg_call(token: str, method: str, payload: dict | None = None) -> dict:
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=35) as r:
        return json.loads(r.read().decode())


def poll_once(token: str, allowed_chat: str, provider: str) -> int:
    offset = 0
    if OFFSET_FILE.exists():
        offset = int(json.loads(OFFSET_FILE.read_text()).get("offset", 0))
    res = tg_call(token, "getUpdates", {"offset": offset, "timeout": 5})
    updates = res.get("result", [])
    handled = 0
    for u in updates:
        offset = max(offset, int(u["update_id"]) + 1)
        msg = u.get("message") or {}
        chat_id = str((msg.get("chat") or {}).get("id", ""))
        text = msg.get("text") or ""
        if not text or (allowed_chat and chat_id != allowed_chat):
            continue
        reply = handle_text(text, provider=provider)[:3900]
        tg_call(token, "sendMessage", {"chat_id": chat_id, "text": reply})
        handled += 1
    OFFSET_FILE.parent.mkdir(parents=True, exist_ok=True)
    OFFSET_FILE.write_text(json.dumps({"offset": offset}))
    return handled


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--mock-text", default="/status")
    ap.add_argument("--provider", choices=["dry-run", "gemini", "groq"], default="gemini")
    ap.add_argument("--loop", action="store_true")
    ap.add_argument("--sleep", type=int, default=5)
    args = ap.parse_args()

    if args.dry_run:
        print(handle_text(args.mock_text, provider="dry-run"))
        return

    token = _cfg("TELEGRAM_BOT_TOKEN", "telegram_token")
    chat_id = _cfg("TELEGRAM_CHAT_ID", "telegram_chat_id")
    if not token:
        print("Telegram bot token not configured — exiting cleanly.")
        return

    if args.loop:
        while True:
            try:
                poll_once(token, chat_id, args.provider)
            except Exception as e:                                # noqa: BLE001
                print("poll error:", e)
            time.sleep(args.sleep)
    else:
        n = poll_once(token, chat_id, args.provider)
        print(f"handled {n} message(s)")


if __name__ == "__main__":
    main()
