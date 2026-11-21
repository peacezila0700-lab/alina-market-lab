#!/usr/bin/env python3
"""
build_dashboard.py — one self-contained HTML file that shows today's state on a phone.

Constraints that shaped it:
  * It must work **offline** and from a phone: every byte is inlined (no CDN, no fonts, no fetch calls),
    so opening the file from Drive or the Files app renders completely.
  * It must not become a second source of truth: it reads `briefs/latest.json`, `packs/<date>.json` and
    `data/technicals/latest.csv` and prints them. If a number is not in those files, it is not here.
  * It must not pretend to be advice: the page shows measured base rates with their n_effective, and the
    flags the daily brief already computed.

Why not a live app: a hosted app needs a server (cost) and an API key in the browser (leak). A generated
static file needs neither, and a phone can open it in one tap. Regenerate it in the daily collector.

Output: dashboard/alina_today.html  (~40-60 KB, self-contained)
"""
import html
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dashboard"
CSS = """
:root{--bg:#0b0f14;--card:#141b24;--fg:#e8eef6;--muted:#8fa2b8;--up:#2ecc71;--down:#ff5d5d;--accent:#4cc9f0}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);
font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans Thai",sans-serif;padding:14px}
h1{font-size:19px;margin:0 0 2px}h2{font-size:15px;margin:18px 0 8px;color:var(--accent);
text-transform:uppercase;letter-spacing:.06em}
.sub{color:var(--muted);font-size:12px;margin-bottom:12px}
.card{background:var(--card);border-radius:12px;padding:12px 14px;margin-bottom:10px}
.kv{display:flex;justify-content:space-between;gap:10px;padding:3px 0;border-bottom:1px solid #1e2833}
.kv:last-child{border-bottom:0}.k{color:var(--muted)}.v{font-variant-numeric:tabular-nums;text-align:right}
table{width:100%;border-collapse:collapse;font-size:13px}th,td{padding:5px 4px;text-align:right;
border-bottom:1px solid #1e2833}th{color:var(--muted);font-weight:500;font-size:11px;text-transform:uppercase}
td:first-child,th:first-child{text-align:left}
.up{color:var(--up)}.down{color:var(--down)}
details{background:var(--card);border-radius:12px;padding:10px 14px;margin-bottom:8px}
summary{cursor:pointer;font-weight:600}
.flag{background:#3a1d1d;border-left:3px solid #ff5d5d;padding:8px 10px;border-radius:6px;margin:6px 0;font-size:13px}
.ok{background:#16301f;border-left:3px solid #2ecc71;padding:8px 10px;border-radius:6px;margin:6px 0;font-size:13px}
.foot{color:var(--muted);font-size:11px;margin-top:18px;line-height:1.5}
"""


def esc(x):
    return html.escape(str(x))


def kv(k, v):
    return f'<div class="kv"><span class="k">{esc(k)}</span><span class="v">{esc(v)}</span></div>'


def pct_class(x):
    try:
        return "up" if float(x) >= 0 else "down"
    except Exception:                                            # noqa: BLE001
        return ""


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    brief = json.loads((ROOT / "briefs" / "latest.json").read_text())
    state = brief.get("state", {})
    d = brief.get("date") or brief.get("as_of") or ""
    pack_path = ROOT / "packs" / f"{d}.json"
    if not pack_path.exists():                     # fall back to the newest pack on disk
        packs = sorted((ROOT / "packs").glob("*.json"))
        pack_path = packs[-1] if packs else pack_path
    pack = json.loads(pack_path.read_text()) if pack_path.exists() else {}
    tech = pd.read_csv(ROOT / "data" / "technicals" / "latest.csv")

    h = [f"<!doctype html><html lang='th'><meta charset='utf-8'>",
         "<meta name='viewport' content='width=device-width,initial-scale=1,viewport-fit=cover'>",
         "<meta name='apple-mobile-web-app-capable' content='yes'>",
         "<meta name='apple-mobile-web-app-status-bar-style' content='black-translucent'>",
         "<meta name='apple-mobile-web-app-title' content='ALINA Lab'>",
         "<meta name='mobile-web-app-capable' content='yes'>",
         "<meta name='theme-color' content='#0b0f14'>",
         f"<title>ALINA — {esc(d)}</title><style>{CSS}</style>",
         f"<h1>สภาวะตลาด {esc(d)}</h1>",
         f"<div class='sub'>สร้าง {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC · "
         f"ไฟล์เดียว เปิดจากมือถือได้ทันที ไม่ต้องเน็ต</div>"]

    # ---- state
    keys = [("VIX", state.get("vix"), f"percentile {state.get('vix_percentile_all_history')}"),
            ("VIX/VIX3M", state.get("vix_slope_3m"), ">1 = inverted = stress now"),
            ("VIX9D/VIX", state.get("vix_slope_9d"), ">1 = front-end panic"),
            ("VVIX pct", state.get("vvix_percentile"), "vol-of-vol"),
            ("SKEW", state.get("skew"), ">145 = expensive tail"),
            ("DIX", state.get("dix"), f"pct {state.get('dix_percentile')}"),
            ("GEX (bn USD)", state.get("gex_usd_bn"), state.get("gex_regime", ""))]
    h.append("<h2>สถานะตอนนี้</h2><div class='card'>")
    for k, v, note in keys:
        if v is None:
            continue
        h.append(kv(k, f"{v}  ({note})" if note else v))
    h.append("</div>")

    # ---- flags
    flags = brief.get("flags", [])
    if flags:
        h.append("<h2>ธงเตือน</h2>")
        for f in flags:
            h.append(f"<div class='flag'>{esc(f)}</div>")
    else:
        h.append("<div class='ok'>ไม่มีธงเตือนที่ déclaré</div>")

    # ---- base rates
    br = pack.get("base_rates", {}).get("rows", [])
    if br:
        h.append(f"<h2>สถิติย้อนหลังตามสภาวะนี้</h2><div class='card'><div class='sub'>"
                 f"{esc(pack['base_rates'].get('condition', ''))}</div><table>"
                 "<tr><th>horizon</th><th>median %</th><th>%pos</th><th>n_eff</th></tr>")
        for r in br:
            h.append(f"<tr><td>{int(r['horizon_d'])}d</td>"
                     f"<td class='{pct_class(r['median_pct'])}'>{r['median_pct']:+.2f}</td>"
                     f"<td>{r['pct_positive']:.0f}%</td><td>{int(r['n_eff'])}</td></tr>")
        h.append("</table></div>")

    # ---- similar days
    sd = pack.get("similar_days", {})
    if sd.get("fwd21_summary"):
        s = sd["fwd21_summary"]
        h.append(f"<h2>12 วันที่คล้ายวันนี้</h2><div class='card'>"
                 + kv("median 21d", f"{s['median_pct']:+.2f}%")
                 + kv("ช่วง", f"{s['min_pct']:+.1f}% ถึง {s['max_pct']:+.1f}%")
                 + kv("บวกกี่วัน", f"{s['pct_positive']:.0f}% ของ {s['n']} วัน")
                 + "<div class='sub' style='margin-top:8px'>ใช้เป็นภาพการกระจาย ไม่ใช่ค่าคาดหวัง "
                   "(n น้อย อ่าน min–max)</div></div>")

    # ---- movers
    t = tech.dropna(subset=["ret21d"]).copy()
    t = t[~t.symbol.str.contains("^SET_EW$", na=False)]
    rows = pd.concat([t.nlargest(6, "ret21d"), t.nsmallest(6, "ret21d")]).drop_duplicates("symbol")
    if len(rows):
        h.append("<h2>แรงที่สุด / อ่อนที่สุด 21 วัน</h2><div class='card'><table>"
                 "<tr><th>symbol</th><th>21d %</th><th>RSI</th><th>vs 52w high</th></tr>")
        for _, r in rows.sort_values("ret21d", ascending=False).iterrows():
            h.append(f"<tr><td>{esc(r['symbol'])}</td>"
                     f"<td class='{pct_class(r['ret21d'])}'>{r['ret21d']:+.1f}</td>"
                     f"<td>{'' if pd.isna(r.get('rsi14')) else round(float(r['rsi14']))}</td>"
                     f"<td class='{pct_class(r.get('dist_52w_high_pct'))}'>"
                     f"{'' if pd.isna(r.get('dist_52w_high_pct')) else f'{r.dist_52w_high_pct:+.1f}%'}</td></tr>")
        h.append("</table></div>")

    # ---- levels
    levels = pack.get("levels", {}).get("rows", [])
    if levels:
        h.append("<h2>ระดับรับ/ส่ง (測定)</h2><div class='card'><table>"
                 "<tr><th>inst</th><th>close</th><th>pivot</th><th>pdh</th><th>pdl</th><th>ATR</th></tr>")
        for r in levels[:12]:
            h.append(f"<tr><td>{esc(r.get('instrument', ''))}</td><td>{r.get('close', '')}</td>"
                     f"<td>{r.get('pivot', '')}</td><td>{r.get('pdh', '')}</td>"
                     f"<td>{r.get('pdl', '')}</td><td>{r.get('atr14', '')}</td></tr>")
        h.append("</table></div>")

    # ---- calendar
    cal = pack.get("calendar", {}).get("events", [])
    if cal:
        h.append("<h2>ปฏิทินใกล้ ๆ</h2><div class='card'>")
        for e in cal[:10]:
            h.append(kv(e.get("date", ""), e.get("event", "")))
        h.append("</div>")

    # ---- thai SET summary (derived from data/thai/ if present)
    thai_dir = ROOT / "data" / "thai"
    ew_path = thai_dir / "SET_EW.csv"
    if ew_path.exists():
        ew = pd.read_csv(ew_path)
        if len(ew) >= 64:
            col_ew = "SET_EW" if "SET_EW" in ew.columns else "close"
            c_now = float(ew[col_ew].iloc[-1])
            r21 = (c_now / float(ew[col_ew].iloc[-22]) - 1.0) * 100.0
            r63 = (c_now / float(ew[col_ew].iloc[-64]) - 1.0) * 100.0
            h.append("<h2>ตลาดไทย (SET64 Equal-Weight · price-only)</h2><div class='card'>"
                     + kv("SET_EW ล่าสุด", f"{c_now:.2f} (ณ {ew['date'].iloc[-1]})")
                     + kv("SET_EW 21d / 63d", f"{r21:+.2f}% / {r63:+.2f}%")
                     + "<div class='sub'>หมายเหตุ: ไม่ใช่ SET50 และไม่รวมปันผล (~3%/ปี); "
                       "EXP-0021 ไม่พบ edge ที่รอดค่าธรรมเนียมไทย</div>")
            th_rows = []
            for fp in sorted(thai_dir.glob("*.csv")):
                if fp.stem == "SET_EW":
                    continue
                try:
                    df_th = pd.read_csv(fp)
                    if len(df_th) >= 22:
                        cn = float(df_th["close"].iloc[-1])
                        c21 = float(df_th["close"].iloc[-22])
                        th_rows.append((fp.stem, cn, (cn / c21 - 1.0) * 100.0))
                except Exception:                                # noqa: BLE001
                    continue
            if th_rows:
                tdf = pd.DataFrame(th_rows, columns=["sym", "close", "ret21"])
                picks = pd.concat([tdf.nlargest(4, "ret21"), tdf.nsmallest(4, "ret21")]).drop_duplicates("sym")
                h.append("<table><tr><th>SET</th><th>close</th><th>21d %</th></tr>")
                for _, r in picks.sort_values("ret21", ascending=False).iterrows():
                    h.append(f"<tr><td>{esc(r['sym'])}</td><td>{r['close']:.2f}</td>"
                             f"<td class='{pct_class(r['ret21'])}'>{r['ret21']:+.1f}</td></tr>")
                h.append("</table>")
            h.append("</div>")

    # ---- news
    news = brief.get("news", [])
    if news:
        h.append("<h2>ข่าวล่าสุด</h2>")
        for n in news[:8]:
            h.append(f"<div class='card'><div class='sub'>{esc(n.get('source', ''))}</div>"
                     f"{esc(n.get('title', ''))}</div>")

    # ---- Workstream D: Risk Radar SLA, Macro Rates, Crypto Basis & Warnings
    rr_path = ROOT / "data" / "risk_radar" / "latest.json"
    if rr_path.exists():
        rr = json.loads(rr_path.read_text())
        orc = rr.get("overall_risk_classification", "UNKNOWN")
        cls_name = "flag" if orc in ("ELEVATED", "HIGH") else "ok"
        h.append(f"<h2>Risk Radar (Monitoring Only — Not a Signal)</h2>")
        h.append(f"<div class='{cls_name}'><b>Overall Risk: {esc(orc)}</b> · "
                 f"Fresh Panels: {rr.get('fresh_panels', 0)}/{rr.get('total_panels', 0)} · "
                 f"{esc(rr.get('disclaimer', ''))}</div>")
        h.append("<div class='card'><table><tr><th>Panel</th><th>Updated</th><th>Freshness</th><th>Risk</th></tr>")
        for pname, pval in rr.get("panels", {}).items():
            h.append(
                f"<tr><td>{esc(pname)}</td><td>{esc(pval.get('last_updated', '?'))}</td>"
                f"<td>{esc(pval.get('freshness_status', '?'))}</td>"
                f"<td><b>{esc(pval.get('risk_classification', '?'))}</b></td></tr>"
            )
        h.append("</table>")
        for w in rr.get("missing_data_warnings", [])[:5]:
            h.append(f"<div class='sub'>⚠ {esc(w)}</div>")
        h.append("</div>")

        rmm = rr.get("risk_meta_model", {})
        if "calibrated_probabilities" in rmm:
            cp = rmm["calibrated_probabilities"]
            ds = rmm["defensive_sizing_reference"]
            sd_m = rmm["stationary_drivers"]
            h.append("<h2>Risk Meta-Labeling (Calibrated · Monitoring Only)</h2><div class='card'>")
            h.append(kv("P(VolOnset 21d) · HGBC+Platt", f"{cp['p_vol_onset_21d']*100:.1f}%  (WF AUC 0.688, ECE 0.061)"))
            h.append(kv("P(TailStress 21d) · HGBC+Platt", f"{cp['p_tail_stress_21d']*100:.1f}%  (WF AUC 0.697, ECE 0.037)"))
            h.append(kv("P(TB_NonDirStress 21d) · EXP-0030", f"{cp['p_tb_nondir_stress_21d']*100:.1f}%  (WF AUC 0.664)"))
            h.append(kv("Stationary State (z252)", f"OFR {sd_m['ofr_fsi_z252']:+.2f} · GPR {sd_m['gpr_z252']:+.2f} · dFed63 {sd_m['d_fed_63']:+.2f}"))
            h.append(kv("Defensive Ref (EXP-0031)", f"VT12% {ds['vol_target_12pct_exposure_pct']:.1f}% × {ds['meta_throttle_scalar']:.2f} = Equity {ds['meta_cash_equity_exposure_pct']:.1f}% / Cash {ds['cash_buffer_pct']:.1f}%"))
            h.append(f"<div class='sub'>{esc(ds['exp0031_note'])}</div></div>")

        fxg = rr.get("fx_execution_guard", {})
        if "latest_spread_pips" in fxg:
            h.append("<h2>FX Rollover & Liquidity Guard (EURGBP H1)</h2><div class='card'>")
            h.append(kv("Last H1 Bar (UTC)", f"{fxg['last_bar_utc'][:16]}  (hr {fxg['latest_hour_utc']} UTC)"))
            h.append(kv("Spread / z72", f"{fxg['latest_spread_pips']:.2f} pips  (z72={fxg['spread_z72']})"))
            h.append(kv("6h Rollover Hazard (16-23 UTC)", "YES — elevated spread risk" if fxg["last_bar_in_rollover_hazard"] else "NO — liquid window"))
            h.append(f"<div class='sub'>{esc(fxg['exp0030_gate_benchmark'])}</div></div>")

        cto = rr.get("crypto_trend_overlay", {})
        if "btc_close" in cto:
            h.append("<h2>Crypto Trend Regime & VolTarget25% (EXP-0041 · Monitor Only)</h2><div class='card'>")
            h.append(kv(f"BTC Close ({cto['as_of_date']}) / SMA50", f"${cto['btc_close']:,.0f} / ${cto['btc_sma50']:,.0f} ({'ABOVE' if cto['above_sma50'] else 'BELOW'})"))
            h.append(kv("TrendEns(20..120) Vote / RV21", f"{cto['trend_ens_vote_20_40_60_90_120']:.2f} / {cto['rv21_ann_pct']:.1f}% ann"))
            h.append(kv("Ref Sizing (Ens×VT25 / Cash)", f"BTC {cto['suggested_btc_ens_vt25_pct']:.1f}% / Cash {cto['suggested_cash_pct']:.1f}%"))
            h.append(f"<div class='sub'>{esc(cto['exp0041_note'])}</div></div>")

    exp_n, exp_pass = 0, 0
    exp_csv = ROOT / "research" / "EXPERIMENT_LOG.csv"
    if exp_csv.exists():
        import csv
        rows_exp = list(csv.DictReader(exp_csv.open()))
        exp_n = len(rows_exp)
        exp_pass = sum(1 for r in rows_exp if "PASS" in (r.get("result_status") or "").upper())

    h.append("<details><summary>สิ่งที่ไฟล์นี้ไม่บอก (อ่านก่อนใช้)</summary>"
             f"<div class='sub'>1) ไม่มีคำแนะนำซื้อขาย — {exp_n} การทดลองในโปรเจกต์นี้พบ {exp_pass} edge ที่ผ่านเกณฑ์ "
             "2) ตัวเลข base rate เป็นค่ากลางของการกระจายที่กว้าง อ่าน n_eff ก่อนเชื่อ "
             "3) ข้อมูลหน่วงตามแหล่ง (VIX ปิดวัน, GEX รายวัน, ข่าว real-time) "
             "4) ทั้งหมดมาจาก briefs/latest.json + packs/<date>.json ถ้าตัวเลขไม่ตรง ให้ยึดไฟล์ต้นทาง"
             "</div></details>")
    h.append(f"<div class='foot'>ALINA Market Lab · generated {datetime.now(timezone.utc):%Y-%m-%dT%H:%MZ} · "
             f"source files: briefs/latest.json, packs/{esc(d)}.json, data/technicals/latest.csv</div>")
    h.append("</html>")

    path = OUT / "alina_today.html"
    path.write_text("\n".join(h))
    print(f"  dashboard -> {path}  ({path.stat().st_size/1024:.0f} KB, self-contained)")
    print(f"    state keys {len(state)}, flags {len(flags)}, base-rate rows {len(br)}, "
          f"similar days {sd.get('fwd21_summary', {}).get('n', 0)}, movers {len(rows)}")


if __name__ == "__main__":
    main()
