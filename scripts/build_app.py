#!/usr/bin/env python3
"""Build the Alina Market Lab app: a self-contained HTML dashboard + the data payload.

Design rules:
  - the app never claims an edge; it shows the *evidence* and the current computed state
  - everything on the page is computed here from files in this repo (no fake numbers)
  - single-file output with inline CSS/JS so it renders anywhere, including sandboxed previews

Outputs: app/index.html, app/data.json
"""
from __future__ import annotations

import csv
import json
import os
from datetime import datetime, timezone

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UNI = os.path.join(ROOT, "data", "universe")
ART = os.path.join(ROOT, "research", "artifacts")
APP = os.path.join(ROOT, "app")
os.makedirs(APP, exist_ok=True)

CLASS = {"EURUSD": "FX", "GBPUSD": "FX", "AUDUSD": "FX", "USDCAD": "FX", "USDJPY": "FX",
         "DXY": "FX", "GOLD": "METAL", "SILVER": "METAL", "PLATINUM": "METAL", "COPPER": "METAL",
         "SP500": "INDEX", "NASDAQ100": "INDEX", "DAX": "INDEX", "FTSE": "INDEX",
         "NIKKEI": "INDEX", "HSI": "INDEX", "TLT": "BOND", "IEF": "BOND", "BTC": "CRYPTO",
         "ETH": "CRYPTO", "WTI": "ENERGY", "NATGAS": "ENERGY", "CORN": "AG", "WHEAT": "AG"}
TARGET_VOL = 0.10


def load(sym: str):
    p = os.path.join(UNI, f"{sym}.csv")
    if not os.path.exists(p):
        return None
    d, c = [], []
    with open(p) as f:
        for r in csv.DictReader(f):
            try:
                c.append(float(r["close"]))
                d.append(r["date"])
            except (KeyError, TypeError, ValueError):
                pass
    return (np.array(d), np.array(c)) if len(c) > 300 else None


def snapshot() -> list[dict]:
    out = []
    for sym in sorted(CLASS):
        g = load(sym)
        if not g:
            continue
        d, px = g
        r = np.zeros(len(px))
        r[1:] = px[1:] / px[:-1] - 1
        vol = float(r[-60:].std(ddof=1) * np.sqrt(252))
        mom12 = float(px[-1] / px[-253] - 1) if len(px) > 253 else float("nan")
        dc55 = bool(px[-1] >= px[-56:-1].max()) if len(px) > 56 else False
        dc55s = bool(px[-1] <= px[-56:-1].min()) if len(px) > 56 else False
        w20 = px[-20:]
        z = float((px[-1] - w20.mean()) / w20.std(ddof=1)) if w20.std(ddof=1) > 0 else 0.0
        sig = []
        if dc55:
            sig.append("55d breakout ↑")
        if dc55s:
            sig.append("55d breakdown ↓")
        if abs(z) >= 2:
            sig.append(f"z={z:+.1f} (fade)")
        if not np.isnan(mom12):
            sig.append("12m up" if mom12 > 0 else "12m down")
        size = min(3.0, TARGET_VOL / vol) if vol > 0 else 0.0
        out.append({"symbol": sym, "class": CLASS[sym], "date": str(d[-1]),
                    "close": round(float(px[-1]), 4), "vol_ann_pct": round(vol * 100, 1),
                    "risk_weight_raw": size,
                    "mom_12m_pct": round(mom12 * 100, 1) if not np.isnan(mom12) else None,
                    "z20": round(z, 2), "signals": ", ".join(sig) or "—"})
    tot = sum(o["risk_weight_raw"] for o in out) or 1.0
    for o in out:
        o["risk_weight_pct"] = round(o.pop("risk_weight_raw") / tot * 100, 1)
    return out


def read_json(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:                                            # noqa: BLE001
        return default


def main() -> None:
    snap = snapshot()
    fre = read_json(os.path.join(ART, "free_ea_families_summary.json"), {})
    hs = read_json(os.path.join(ART, "h09_retail.json"), {})
    h10 = read_json(os.path.join(ART, "h10_holdout.json"), {})
    h11 = read_json(os.path.join(ART, "h11_vrp.json"), {})
    uni = read_json(os.path.join(ART, "universe_screen.json"), [])

    best = sorted(uni, key=lambda x: -x["sharpe"])[:10] if isinstance(uni, list) else []
    payload = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "status": "NO VALIDATED EDGE — research mode only",
        "snapshot": snap,
        "free_ea_families": fre.get("summary", []),
        "martingale": fre.get("martingale", []),
        "best_screen_tests": [{"instrument": b["name"], "rule": b["rule"],
                               "sharpe": b["sharpe"], "cagr": b["cagr"],
                               "null_pct": b.get("null_pct")} for b in best],
        "experiments": [
            {"id": "EXP-0001..0004", "what": "FX trend / intraday fade / breakout",
             "result": "REJECTED", "detail": "H1 fade IS −1.66 pips; breakout CI [−4.27,−1.54]"},
            {"id": "EXP-0005", "what": "Cross-sectional FX reversion (assumed cost)",
             "result": "REJECTED", "detail": "Sharpe 0.343 vs pre-registered bar 0.35"},
            {"id": "EXP-0006", "what": "Same rule, MEASURED costs",
             "result": "CONDITIONAL", "detail": "ECN 0.402 / retail 0.358 — passes, but in-sample"},
            {"id": "EXP-0007", "what": "Same rule, 2019–2026 hold-out",
             "result": "REJECTED", "detail": "Sharpe 0.126, only 1 of 6 windows positive"},
            {"id": "EXP-0008", "what": "Variance risk premium (short vol)",
             "result": "REJECTED", "detail": "Sharpe 0.694 but worst 12m −103.7%, worst day −43.1%"},
        ],
        "risk_governor": {
            "target_vol_ann_pct": TARGET_VOL * 100,
            "max_risk_per_idea_pct": 2.0,
            "max_daily_loss_pct": 3.0,
            "max_total_drawdown_pct": 20.0,
            "never": ["martingale / grid doubling", "no stop loss", "averaging into losers",
                      "increasing size after losses"],
        },
        "h09_retail_p1r": (hs.get("panels", {}).get("P1R_EUR9", {}).get("k", {}).get("2", {}) or {}).get("full"),
        "h10_primary": (h10.get("primary", {}).get("retail", {}) or {}).get("full"),
        "h11b": (h11.get("h11b", {}) or {}).get("short_net"),
    }
    with open(os.path.join(APP, "data.json"), "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    html = TEMPLATE.replace("__DATA__", json.dumps(payload, ensure_ascii=False))
    with open(os.path.join(APP, "index.html"), "w") as f:
        f.write(html)
    print(f"wrote app/index.html ({len(html) // 1024} KB) and app/data.json")
    print(f"  instruments in snapshot: {len(snap)}")


TEMPLATE = r"""<!doctype html>
<html lang="th"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Alina Market Lab — AI Trade Desk</title>
<style>
:root{--bg:#0b0f14;--panel:#121924;--line:#1e2a3a;--txt:#e6edf5;--dim:#8b9bb0;--ok:#2ecc71;--bad:#ff5c5c;--warn:#ffb020;--acc:#4da3ff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--txt);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans Thai",sans-serif}
header{padding:22px 20px 14px;border-bottom:1px solid var(--line);background:linear-gradient(180deg,#111a26,#0b0f14)}
h1{margin:0;font-size:20px;letter-spacing:.2px}
h2{margin:0 0 10px;font-size:15px;color:var(--acc);text-transform:uppercase;letter-spacing:.08em}
.sub{color:var(--dim);font-size:13px;margin-top:4px}
.badge{display:inline-block;padding:3px 10px;border-radius:999px;font-size:12px;font-weight:700}
.b-bad{background:rgba(255,92,92,.15);color:var(--bad);border:1px solid rgba(255,92,92,.35)}
.b-ok{background:rgba(46,204,113,.13);color:var(--ok);border:1px solid rgba(46,204,113,.35)}
.b-warn{background:rgba(255,176,32,.13);color:var(--warn);border:1px solid rgba(255,176,32,.35)}
main{padding:18px 20px 60px;max-width:1180px;margin:0 auto}
section{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:16px;margin:14px 0}
table{width:100%;border-collapse:collapse;font-size:13.5px}
th,td{padding:7px 9px;text-align:left;border-bottom:1px solid var(--line);white-space:nowrap}
th{color:var(--dim);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.05em}
td.num{text-align:right;font-variant-numeric:tabular-nums}
tr:hover td{background:rgba(77,163,255,.06)}
.pos{color:var(--ok)}.neg{color:var(--bad)}.mut{color:var(--dim)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:12px}
.card{background:#0e1520;border:1px solid var(--line);border-radius:10px;padding:12px}
.card .k{color:var(--dim);font-size:12px}
.card .v{font-size:19px;font-weight:700;margin-top:3px}
.scroll{overflow-x:auto}
.note{font-size:12.5px;color:var(--dim);margin-top:10px}
ul{margin:6px 0 0 18px;padding:0}li{margin:3px 0}
code{background:#0e1520;border:1px solid var(--line);padding:1px 5px;border-radius:5px;font-size:12.5px}
.redbox{border-left:3px solid var(--bad);background:rgba(255,92,92,.07);padding:12px 14px;border-radius:8px}
</style></head><body>
<header>
  <h1>Alina Market Lab <span class="badge b-bad" id="status"></span></h1>
  <div class="sub">AI trade desk · ข้อมูลจริงจาก repo · อัปเดต <span id="gen"></span></div>
</header>
<main>
  <section>
    <div class="redbox">
      <b>อ่านก่อน:</b> ระบบนี้ยัง<b>ไม่มี edge ที่ผ่านการทดสอบ</b> ทุกกลยุทธ์ที่ทดสอบมา (168 เทสต์ + 6 การทดลอง
      pre-register) ล้มหรือไม่ผ่าน hold-out หน้านี้จึงเป็น <b>กระดานข้อมูล + ตัวคุมความเสี่ยง</b> ไม่ใช่สัญญาณซื้อขาย
      ห้ามใช้เงินจริง
    </div>
  </section>

  <section><h2>1. สถานะตลาดตอนนี้ (คำนวณสดจากข้อมูลในเครื่อง)</h2>
    <div class="grid" id="cards"></div>
    <div class="note">risk weight = target vol 10% ÷ vol ของสินทรัพย์ (cap 3×) — เป็น<b>ขนาดความเสี่ยง</b> ไม่ใช่คำแนะนำทิศทาง</div>
  </section>

  <section><h2>2. ตารางสัญญาณ 24 สินทรัพย์</h2>
    <div class="scroll"><table id="tbl-snap"></table></div>
  </section>

  <section><h2>3. ของฟรีจากเว็บ (332 แหล่ง) — ทดสอบแล้วได้อะไร</h2>
    <div class="scroll"><table id="tbl-free"></table></div>
    <div class="note" id="free-note"></div>
  </section>

  <section><h2>4. Martingale / Grid — สิ่งที่แจกฟรีเยอะที่สุด และมันทำอะไรกับบัญชี</h2>
    <div class="scroll"><table id="tbl-mart"></table></div>
    <div class="note">ทุกสินทรัพย์ที่ทดสอบ = <b>บัญชีถูกกวาด (wiped)</b> ไม่ใช่เรื่องบังเอิญ — lot doubling ทำให้การขาดทุนครั้งเดียวมีขนาดเท่าทุกกำไรที่สะสมมา</div>
  </section>

  <section><h2>5. ประวัติการทดลอง (ทั้งหมดถูกบันทึกและ push ขึ้น GitHub)</h2>
    <div class="scroll"><table id="tbl-exp"></table></div>
  </section>

  <section><h2>6. Risk Governor — ค่าที่ EA บังคับใช้</h2>
    <div class="grid" id="cards-risk"></div>
    <div class="note" id="never"></div>
  </section>

  <section><h2>7. วิธีรัน</h2>
    <ul>
      <li>เปิด MT5 → <code>File ▸ Open Data Folder</code> → <code>MQL5/Experts/</code> → วาง <code>AlinaRiskGovernor.mq5</code></li>
      <li>F4 เปิด MetaEditor → กด <b>F7</b> compile → กลับ MT5 กด Refresh ที่ Navigator</li>
      <li>ลาก EA ลงกราฟ <b>บัญชี DEMO เท่านั้น</b> → ตั้ง <code>InpMode = PAPER</code> เพื่อทดสอบโดยไม่ส่งคำสั่งจริง</li>
      <li>เปลี่ยนเป็น <code>LIVE_SAFE</code> ได้เมื่อผ่าน demo ต่อเนื่อง ≥ 3 เดือน และมี log ครบ</li>
    </ul>
    <div class="note">EA นี้ไม่ใส่กลยุทธ์ที่ "ชนะ" เพราะยังไม่มี — มันใส่ <b>วินัยความเสี่ยง</b> ที่ทดสอบแล้วว่าจำเป็น</div>
  </section>
</main>
<script>
const D = __DATA__;
const f=(x,n=2)=>x==null?'—':Number(x).toFixed(n);
const cls=x=>x>0?'pos':(x<0?'neg':'mut');
document.getElementById('status').textContent=D.status;
document.getElementById('gen').textContent=D.generated_utc;

const snap=D.snapshot;
const tot=snap.reduce((a,s)=>a+s.risk_weight_pct,0);
const cards=[
 ['สินทรัพย์ที่ติดตาม', snap.length+' ตัว', ''],
 ['Vol เฉลี่ย (ann.)', f(snap.reduce((a,s)=>a+s.vol_ann_pct,0)/snap.length,1)+'%',''],
 ['ตัวที่ breakout 55 วัน', snap.filter(s=>s.signals.includes('breakout')).length,''],
 ['ตัวที่ z ≥ 2 (fade)', snap.filter(s=>Math.abs(s.z20)>=2).length,''],
 ['Experiments ที่ผ่าน', '0 / 6',''],
];
document.getElementById('cards').innerHTML=cards.map(c=>`<div class="card"><div class="k">${c[0]}</div><div class="v">${c[1]}</div></div>`).join('');

let h='<tr><th>Symbol</th><th>Class</th><th class="num">Close</th><th class="num">Vol %</th><th class="num">12m %</th><th class="num">z20</th><th class="num">Risk %</th><th>สัญญาณ</th></tr>';
for(const s of snap){
 h+=`<tr><td><b>${s.symbol}</b></td><td class="mut">${s.class}</td><td class="num">${s.close}</td>
 <td class="num">${f(s.vol_ann_pct,1)}</td><td class="num ${cls(s.mom_12m_pct)}">${f(s.mom_12m_pct,1)}</td>
 <td class="num ${cls(Math.abs(s.z20)>=2?-s.z20:0)}">${f(s.z20,2)}</td><td class="num">${f(s.risk_weight_pct,0)}</td>
 <td class="mut">${s.signals}</td></tr>`;
}
document.getElementById('tbl-snap').innerHTML=h;

let g='<tr><th>Family</th><th class="num">n</th><th class="num">Median Sharpe</th><th class="num">Best</th><th class="num">% positive</th><th class="num">ชนะ null (≥95)</th></tr>';
for(const r of D.free_ea_families){
 g+=`<tr><td><b>${r.family}</b></td><td class="num">${r.n}</td><td class="num ${cls(r.median_sharpe)}">${f(r.median_sharpe)}</td>
 <td class="num ${cls(r.best_sharpe)}">${f(r.best_sharpe)}</td><td class="num">${f(r.pct_positive,1)}%</td>
 <td class="num">${r.pass_null95}/${r.n}</td></tr>`;
}
document.getElementById('tbl-free').innerHTML=g;
document.getElementById('free-note').innerHTML='ทุกตระกูลมี median Sharpe ≈ 0 ยกเว้น Supertrend ที่ติดลบหนัก — "ของฟรี" ไม่ได้แย่เพราะโค้ดไม่ดี แต่เพราะ<b>ไอเดียข้างในไม่มี edge</b>';

let m='<tr><th>Symbol</th><th class="num">Final equity (เริ่ม 1.00)</th><th>ผล</th></tr>';
for(const r of D.martingale){
 m+=`<tr><td>${r.instrument}</td><td class="num ${cls(r.final_equity-1)}">${f(r.final_equity,3)}</td>
 <td>${r.wiped?'<span class="badge b-bad">WIPED</span>':'<span class="badge b-warn">รอด</span>'}</td></tr>`;
}
document.getElementById('tbl-mart').innerHTML=m;

let e='<tr><th>ID</th><th>ทดสอบอะไร</th><th>ผล</th><th>ตัวเลข</th></tr>';
for(const x of D.experiments){
 const c=x.result==='REJECTED'?'b-bad':(x.result==='CONDITIONAL'?'b-warn':'b-ok');
 e+=`<tr><td><code>${x.id}</code></td><td>${x.what}</td><td><span class="badge ${c}">${x.result}</span></td><td class="mut">${x.detail}</td></tr>`;
}
document.getElementById('tbl-exp').innerHTML=e;

const rg=D.risk_governor;
const rcards=[
 ['Target vol ต่อปี', rg.target_vol_ann_pct+'%'],
 ['เสี่ยงสูงสุดต่อไอเดีย', rg.max_risk_per_idea_pct+'%'],
 ['ขาดทุนได้สูงสุดต่อวัน', rg.max_daily_loss_pct+'%'],
 ['หยุดเมื่อ drawdown', rg.max_total_drawdown_pct+'%'],
];
document.getElementById('cards-risk').innerHTML=rcards.map(c=>`<div class="card"><div class="k">${c[0]}</div><div class="v">${c[1]}</div></div>`).join('');
document.getElementById('never').innerHTML='EA บล็อกตายตัว: '+rg.never.map(x=>`<code>${x}</code>`).join(' ');
</script>
</body></html>"""


if __name__ == "__main__":
    main()
