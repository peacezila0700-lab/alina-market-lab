#!/usr/bin/env python3
"""
Workstream D — Daily Risk Radar (`scripts/risk_radar.py`)
EXPLICIT SCOPE: RISK MONITORING TOOL ONLY — NOT A SIGNAL GENERATOR OR PROOF OF EDGE.

Monitors:
  1. VIX & Implied Vol Term Structure (`vol_stress_features.csv`)
  2. Systemic Financial Stress (`ofr_fsi.csv`)
  3. Equity Realized Volatility & Technical Stress (`SPY.csv`, `technicals/latest.csv`)
  4. Support / Resistance Proximity (`levels/levels_latest.csv`)
  5. 7-Day Forward Event Calendar (`events/event_calendar_full.csv`, `econ_calendar.csv`)
  6. Macro Central Bank Policy Differentials (`macro/central_bank_rates_daily.csv`)
  7. News Feed Health & Stress Keyword Density (`news/feed_status.json`, `news/headlines.csv`)
  8. Crypto Funding & Perp Basis Monitor (`microstructure/deribit_BTC_funding_1h.csv.gz`, `collect/okx_BTCUSDT_funding_deep.csv`)

Every panel reports:
  - `data_source`
  - `last_updated`
  - `freshness_status` (`FRESH`, `STALE_WARNING`, `CRITICAL_STALE`, `MISSING_OR_ERROR`)
  - `risk_classification` (`LOW`, `MODERATE`, `ELEVATED`, `HIGH`)
  - `alert_thresholds`
  - `missing_data_warning`

Outputs:
  - `data/risk_radar/latest.json`
  - `data/risk_radar/history.jsonl` (append-only historical log, deduplicated per `run_date`)
  - `reports/RISK_RADAR_SPEC_AND_LATEST.md`
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "risk_radar"
OUT_JSON = OUT_DIR / "latest.json"
OUT_HIST = OUT_DIR / "history.jsonl"
OUT_MD = ROOT / "reports" / "RISK_RADAR_SPEC_AND_LATEST.md"

DISCLAIMER = (
    "RISK MONITORING TOOL ONLY — Not a buy/sell signal generator or proof of trading edge. "
    "Phase C Kill Point remains active (0 validated directional edges across 29 experiments)."
)

STRESS_KEYWORDS = ("crisis", "default", "emergency", "tariff", "war", "crash", "halt", "recession", "shock", "panic")


def _freshness(last_date_str: str | None, ref_dt: datetime, warn_days: int = 4, crit_days: int = 10) -> tuple[str, int | None]:
    if not last_date_str:
        return "MISSING_OR_ERROR", None
    dt = pd.to_datetime(last_date_str, utc=True, errors="coerce")
    if pd.isna(dt):
        return "MISSING_OR_ERROR", None
    age = int(max(0, (ref_dt - dt.to_pydatetime()).days))
    if age <= warn_days:
        return "FRESH", age
    if age <= crit_days:
        return "STALE_WARNING", age
    return "CRITICAL_STALE", age


def _rank_risk(val: float | None, elev: float, high: float, reverse: bool = False) -> str:
    if val is None or not np.isfinite(val):
        return "UNKNOWN"
    if not reverse:
        if val >= high:
            return "HIGH"
        if val >= elev:
            return "ELEVATED"
        return "LOW"
    else:
        if val <= high:
            return "HIGH"
        if val <= elev:
            return "ELEVATED"
        return "LOW"


def build_risk_radar() -> dict:
    now = datetime.now(timezone.utc)
    run_date = now.strftime("%Y-%m-%d")
    alerts: list[dict] = []
    missing_warnings: list[str] = []
    panels: dict[str, dict] = {}

    # 1. VIX & Term Structure
    try:
        p = ROOT / "data" / "collect" / "vol_stress_features.csv"
        df = pd.read_csv(p)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["date"]).sort_values("date")
        last = df.iloc[-1]
        ld = last["date"].strftime("%Y-%m-%d")
        fr, age = _freshness(ld, now)
        vix = float(last["vix"])
        s3 = float(last["slope_3m"])
        s9 = float(last["slope_9d"])
        vv = float(last["vvix_pct"])
        rc = "HIGH" if (vix >= 30 or s3 > 1.05) else ("ELEVATED" if (vix >= 22 or s3 > 1.00 or vv >= 0.90) else "LOW")
        if s3 > 1.0:
            alerts.append({"panel": "vol_term_structure", "severity": rc, "msg": f"VIX/VIX3M inverted at {s3:.3f} (>1.00)"})
        if vv >= 0.90:
            alerts.append({"panel": "vol_term_structure", "severity": "ELEVATED", "msg": f"VVIX percentile elevated at {vv:.2f} (>=0.90)"})
        panels["vol_term_structure"] = {
            "data_source": "data/collect/vol_stress_features.csv (CBOE VIX/VIX3M/VIX9D/VVIX)",
            "last_updated": ld,
            "age_days": age,
            "freshness_status": fr,
            "risk_classification": rc,
            "alert_thresholds": {"vix_elev": 22.0, "vix_high": 30.0, "slope_3m_inversion": 1.00, "vvix_pct_elev": 0.90},
            "metrics": {"vix": round(vix, 2), "slope_3m": round(s3, 3), "slope_9d": round(s9, 3), "vvix_pct": round(vv, 3)},
            "missing_data_warning": None if fr == "FRESH" else f"Vol term structure stale ({age}d old)",
        }
    except Exception as e:
        panels["vol_term_structure"] = {"data_source": "data/collect/vol_stress_features.csv", "freshness_status": "MISSING_OR_ERROR", "risk_classification": "UNKNOWN", "missing_data_warning": str(e)}
        missing_warnings.append(f"vol_term_structure error: {e}")

    # 2. OFR Financial Stress Index
    try:
        p = ROOT / "data" / "collect" / "ofr_fsi.csv"
        df = pd.read_csv(p)
        df["dt"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["dt"]).sort_values("dt")
        last = df.iloc[-1]
        ld = last["dt"].strftime("%Y-%m-%d")
        fr, age = _freshness(ld, now, warn_days=5, crit_days=14)
        fsi = float(last["OFR FSI"])
        cr = float(last["Credit"])
        rc = _rank_risk(fsi, 0.0, 2.0)
        if rc in ("ELEVATED", "HIGH"):
            alerts.append({"panel": "ofr_fsi", "severity": rc, "msg": f"OFR FSI positive at {fsi:+.2f} (>0 stress threshold)"})
        panels["ofr_fsi"] = {
            "data_source": "data/collect/ofr_fsi.csv (US Treasury OFR)",
            "last_updated": ld,
            "age_days": age,
            "freshness_status": fr,
            "risk_classification": rc,
            "alert_thresholds": {"fsi_elevated": 0.0, "fsi_high": 2.0},
            "metrics": {"ofr_fsi": round(fsi, 3), "credit": round(cr, 3), "volatility_sub": round(float(last["Volatility"]), 3)},
            "missing_data_warning": None if fr == "FRESH" else f"OFR FSI lagging ({age}d old)",
        }
    except Exception as e:
        panels["ofr_fsi"] = {"data_source": "data/collect/ofr_fsi.csv", "freshness_status": "MISSING_OR_ERROR", "risk_classification": "UNKNOWN", "missing_data_warning": str(e)}
        missing_warnings.append(f"ofr_fsi error: {e}")

    # 3. Equity Realized Vol & Technical Stress (SPY)
    try:
        p = ROOT / "data" / "universe" / "SPY.csv"
        df = pd.read_csv(p)
        df["dt"] = pd.to_datetime(df["date"], errors="coerce")
        df = df.dropna(subset=["dt"]).sort_values("dt")
        ld = df["dt"].iloc[-1].strftime("%Y-%m-%d")
        fr, age = _freshness(ld, now)
        r = df["close"].pct_change()
        rv20 = float(r.tail(20).std() * math.sqrt(252) * 100.0)
        rv63 = float(r.tail(63).std() * math.sqrt(252) * 100.0)
        hi252 = float(df["close"].tail(252).max())
        dd52 = float((df["close"].iloc[-1] / hi252 - 1.0) * 100.0)
        rc = "HIGH" if (rv20 >= 28 or dd52 <= -15) else ("ELEVATED" if (rv20 >= 18 or dd52 <= -8) else "LOW")
        if rc != "LOW":
            alerts.append({"panel": "equity_vol_dd", "severity": rc, "msg": f"SPY RV20={rv20:.1f}%, 52w DD={dd52:.1f}%"})
        panels["equity_vol_dd"] = {
            "data_source": "data/universe/SPY.csv (Yahoo Finance Daily)",
            "last_updated": ld,
            "age_days": age,
            "freshness_status": fr,
            "risk_classification": rc,
            "alert_thresholds": {"rv20_elev": 18.0, "rv20_high": 28.0, "dd52_elev": -8.0, "dd52_high": -15.0},
            "metrics": {"spy_close": round(float(df["close"].iloc[-1]), 2), "rv20_pct": round(rv20, 2), "rv63_pct": round(rv63, 2), "dd_52w_pct": round(dd52, 2)},
            "missing_data_warning": None if fr == "FRESH" else f"SPY data stale ({age}d)",
        }
    except Exception as e:
        panels["equity_vol_dd"] = {"data_source": "data/universe/SPY.csv", "freshness_status": "MISSING_OR_ERROR", "risk_classification": "UNKNOWN", "missing_data_warning": str(e)}
        missing_warnings.append(f"equity_vol_dd error: {e}")

    # 4. Support / Resistance Proximity (levels_latest.csv)
    try:
        p = ROOT / "data" / "levels" / "levels_latest.csv"
        df = pd.read_csv(p)
        ld = str(df["as_of"].iloc[0])[:10]
        fr, age = _freshness(ld, now, warn_days=5, crit_days=14)
        sub = df[df["instrument"].isin(["SPY", "QQQ", "EURUSD", "EURGBP", "BTC", "GOLD"])]
        prox = []
        near_crit = False
        for _, row in sub.iterrows():
            atr = float(row["atr14"]) if float(row["atr14"]) > 0 else 1.0
            c = float(row["close"])
            s1, r1 = float(row["pivot_s1"]), float(row["pivot_r1"])
            dist_s1_atr = round((c - s1) / atr, 2)
            dist_r1_atr = round((r1 - c) / atr, 2)
            if abs(dist_s1_atr) < 0.35 or abs(dist_r1_atr) < 0.35:
                near_crit = True
            prox.append({"instrument": row["instrument"], "close": round(c, 4), "s1": round(s1, 4), "r1": round(r1, 4), "dist_s1_atr": dist_s1_atr, "dist_r1_atr": dist_r1_atr})
        rc = "MODERATE" if near_crit else "LOW"
        panels["support_resistance"] = {
            "data_source": "data/levels/levels_latest.csv",
            "last_updated": ld,
            "age_days": age,
            "freshness_status": fr,
            "risk_classification": rc,
            "alert_thresholds": {"near_pivot_atr": 0.35},
            "metrics": {"instruments": prox},
            "missing_data_warning": None if fr == "FRESH" else f"Levels snapshot is {age}d old (regenerate build_levels)",
        }
    except Exception as e:
        panels["support_resistance"] = {"data_source": "data/levels/levels_latest.csv", "freshness_status": "MISSING_OR_ERROR", "risk_classification": "UNKNOWN", "missing_data_warning": str(e)}
        missing_warnings.append(f"support_resistance error: {e}")

    # 5. 7-Day Event Calendar
    try:
        ev = pd.read_csv(ROOT / "data" / "events" / "event_calendar_full.csv")
        ev["dt"] = pd.to_datetime(ev["date"], errors="coerce")
        today_pd = pd.Timestamp(now.date())
        win = ev[(ev["dt"] >= today_pd) & (ev["dt"] <= today_pd + pd.Timedelta(days=7))].sort_values("dt")
        # Also include data/collect/econ_calendar.csv latest snapshot info
        ev_list = [{"date": r["dt"].strftime("%Y-%m-%d"), "event": str(r["event"]), "detail": str(r["detail"])} for _, r in win.iterrows()]
        has_fomc = any("FOMC" in e["event"].upper() for e in ev_list)
        rc = "ELEVATED" if has_fomc else ("MODERATE" if len(ev_list) > 0 else "LOW")
        if has_fomc:
            alerts.append({"panel": "calendar_7d", "severity": "ELEVATED", "msg": "FOMC decision within next 7 days (historically 1.19x SPY abs move)"})
        panels["calendar_7d"] = {
            "data_source": "data/events/event_calendar_full.csv",
            "last_updated": run_date,
            "age_days": 0,
            "freshness_status": "FRESH",
            "risk_classification": rc,
            "alert_thresholds": {"fomc_7d": True},
            "metrics": {"upcoming_7d_count": len(ev_list), "events": ev_list[:10]},
            "missing_data_warning": "Note: ECB/BoE 2027 dates require annual calendar extension after Dec 2026.",
        }
    except Exception as e:
        panels["calendar_7d"] = {"data_source": "data/events/event_calendar_full.csv", "freshness_status": "MISSING_OR_ERROR", "risk_classification": "UNKNOWN", "missing_data_warning": str(e)}
        missing_warnings.append(f"calendar_7d error: {e}")

    # 6. Macro Central Bank Differentials
    try:
        cb = pd.read_csv(ROOT / "data" / "macro" / "central_bank_rates_daily.csv")
        cb["dt"] = pd.to_datetime(cb["date"], errors="coerce")
        cb = cb.dropna(subset=["dt"]).sort_values("dt")
        last = cb.iloc[-1]
        ld = last["dt"].strftime("%Y-%m-%d")
        fr, age = _freshness(ld, now)
        panels["macro_rates"] = {
            "data_source": "data/macro/central_bank_rates_daily.csv (ECB + BoE + NYFed EFFR)",
            "last_updated": ld,
            "age_days": age,
            "freshness_status": fr,
            "risk_classification": "LOW",
            "alert_thresholds": {"abs_spread_wide_pct": 2.0},
            "metrics": {
                "ecb_dfr": round(float(last["ecb_dfr"]), 3),
                "boe_rate": round(float(last["boe_rate"]), 3),
                "fed_rate_proxy": round(float(last["fed_rate_proxy"]), 3),
                "diff_boe_ecb_dfr": round(float(last["diff_boe_ecb_dfr"]), 3),
                "diff_fed_ecb_dfr": round(float(last["diff_fed_ecb_dfr"]), 3),
            },
            "missing_data_warning": None if fr == "FRESH" else f"CB rates stale ({age}d)",
        }
    except Exception as e:
        panels["macro_rates"] = {"data_source": "data/macro/central_bank_rates_daily.csv", "freshness_status": "MISSING_OR_ERROR", "risk_classification": "UNKNOWN", "missing_data_warning": str(e)}
        missing_warnings.append(f"macro_rates error: {e}")

    # 7. News Feed Health & Stress Keywords
    try:
        fs = json.loads((ROOT / "data" / "news" / "feed_status.json").read_text())
        hl = pd.read_csv(ROOT / "data" / "news" / "headlines.csv")
        feeds = fs.get("feeds", {})
        ok_cnt = sum(1 for v in feeds.values() if str(v).startswith("OK"))
        tot_cnt = len(feeds)
        stamp_val = fs.get("stamp") or fs.get("fetched_utc") or ""
        ld = str(stamp_val)[:10]
        fr, age = _freshness(stamp_val, now, warn_days=2, crit_days=5)
        titles = hl["title"].astype(str).tolist()
        stress_hits = [t for t in titles if any(kw in t.lower() for kw in STRESS_KEYWORDS)]
        rc = "ELEVATED" if (ok_cnt < tot_cnt or len(stress_hits) >= 25) else ("MODERATE" if len(stress_hits) >= 12 else "LOW")
        if ok_cnt < tot_cnt:
            missing_warnings.append(f"News feed partial degradation: {ok_cnt}/{tot_cnt} OK")
        panels["news_stress"] = {
            "data_source": "data/news/feed_status.json + headlines.csv (16 RSS feeds)",
            "last_updated": str(stamp_val)[:19],
            "age_days": age,
            "freshness_status": fr,
            "risk_classification": rc,
            "alert_thresholds": {"min_feeds_ok": tot_cnt, "stress_headlines_elev": 25},
            "metrics": {"feeds_ok": ok_cnt, "feeds_total": tot_cnt, "unique_headlines": len(hl), "stress_keyword_hits": len(stress_hits)},
            "missing_data_warning": None if ok_cnt == tot_cnt else f"Only {ok_cnt}/{tot_cnt} RSS feeds succeeded",
        }
    except Exception as e:
        panels["news_stress"] = {"data_source": "data/news/feed_status.json", "freshness_status": "MISSING_OR_ERROR", "risk_classification": "UNKNOWN", "missing_data_warning": str(e)}
        missing_warnings.append(f"news_stress error: {e}")

    # 8. Crypto Funding & Basis Monitor
    try:
        der = pd.read_csv(ROOT / "data" / "microstructure" / "deribit_BTC_funding_1h.csv.gz")
        der["dt"] = pd.to_datetime(der["ts"], utc=True)
        der = der.sort_values("dt")
        ld = der["dt"].iloc[-1].strftime("%Y-%m-%d")
        fr, age = _freshness(der["dt"].iloc[-1].isoformat(), now, warn_days=2, crit_days=7)
        der_24h_apr = float(der["interest_1h"].tail(24).mean() * 8760.0 * 100.0)
        okx_f = pd.read_csv(ROOT / "data" / "collect" / "okx_BTCUSDT_funding_deep.csv")
        okx_last_apr = float(okx_f["fundingRate"].tail(3).mean() * 3 * 365 * 100.0) if not okx_f.empty else None
        rc = "ELEVATED" if (abs(der_24h_apr) >= 25.0) else "LOW"
        panels["crypto_funding_basis"] = {
            "data_source": "data/microstructure/deribit_BTC_funding_1h.csv.gz + okx_BTCUSDT_funding_deep.csv",
            "last_updated": ld,
            "age_days": age,
            "freshness_status": fr,
            "risk_classification": rc,
            "alert_thresholds": {"abs_funding_apr_elev": 25.0},
            "metrics": {
                "deribit_btc_24h_apr_pct": round(der_24h_apr, 2),
                "deribit_btc_index": round(float(der["index_price"].iloc[-1]), 2),
                "okx_btc_24h_apr_pct": round(okx_last_apr, 2) if okx_last_apr is not None else None,
            },
            "missing_data_warning": "OKX public funding API limited to ~93d; Binance (HTTP 451) & Bybit (HTTP 403) blocked in sandbox.",
        }
    except Exception as e:
        panels["crypto_funding_basis"] = {"data_source": "data/microstructure/", "freshness_status": "MISSING_OR_ERROR", "risk_classification": "UNKNOWN", "missing_data_warning": str(e)}
        missing_warnings.append(f"crypto_funding_basis error: {e}")

    # Freshness SLA audit across all panels
    stale_panels = [k for k, v in panels.items() if v.get("freshness_status") in ("STALE_WARNING", "CRITICAL_STALE", "MISSING_OR_ERROR")]
    for sp in stale_panels:
        missing_warnings.append(f"{sp}: freshness={panels[sp].get('freshness_status')} (age={panels[sp].get('age_days')}d)")

    # Overall Risk Classification
    ranks = {"LOW": 0, "MODERATE": 1, "ELEVATED": 2, "HIGH": 3, "UNKNOWN": 1}
    max_r = max((ranks.get(v.get("risk_classification", "LOW"), 0) for v in panels.values()), default=0)
    inv_r = {0: "LOW", 1: "MODERATE", 2: "ELEVATED", 3: "HIGH"}
    overall_risk = inv_r[max_r]

    payload = {
        "generated_utc": now.isoformat(timespec="seconds"),
        "run_date": run_date,
        "disclaimer": DISCLAIMER,
        "overall_risk_classification": overall_risk,
        "fresh_panels": len(panels) - len(stale_panels),
        "total_panels": len(panels),
        "stale_or_missing_panels": stale_panels,
        "active_alerts": alerts,
        "missing_data_warnings": list(dict.fromkeys(missing_warnings)),
        "panels": panels,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2))

    # Append deduplicated snapshot to history.jsonl
    hist_lines = []
    if OUT_HIST.exists():
        for l in OUT_HIST.read_text().splitlines():
            if not l.strip():
                continue
            try:
                rec = json.loads(l)
                if rec.get("run_date") != run_date:
                    hist_lines.append(json.dumps(rec))
            except Exception:
                continue
    compact = {
        "run_date": run_date,
        "generated_utc": payload["generated_utc"],
        "overall_risk_classification": overall_risk,
        "fresh_panels": payload["fresh_panels"],
        "total_panels": payload["total_panels"],
        "alerts_count": len(alerts),
        "vix": panels.get("vol_term_structure", {}).get("metrics", {}).get("vix"),
        "slope_3m": panels.get("vol_term_structure", {}).get("metrics", {}).get("slope_3m"),
        "ofr_fsi": panels.get("ofr_fsi", {}).get("metrics", {}).get("ofr_fsi"),
        "spy_rv20": panels.get("equity_vol_dd", {}).get("metrics", {}).get("rv20_pct"),
    }
    hist_lines.append(json.dumps(compact))
    OUT_HIST.write_text("\n".join(hist_lines) + "\n")

    # Markdown Specification & Latest Reading
    lines = [
        "# Daily Risk Radar — Specification & Latest Reading",
        "",
        f"> **{DISCLAIMER}**",
        "",
        f"Generated UTC: `{payload['generated_utc']}` | Overall Risk Classification: **`{overall_risk}`** | Fresh Panels: `{payload['fresh_panels']}/{payload['total_panels']}`",
        "",
        "## 1. Panel Status, Data Sources, Freshness & Thresholds",
        "| Panel | Last Updated | Age (d) | Freshness | Risk Class | Key Metrics | Warning |",
        "|---|---|---:|---|---|---|---|",
    ]
    for k, v in panels.items():
        m_str = json.dumps(v.get("metrics", {}))[:95]
        w_str = v.get("missing_data_warning") or "none"
        lines.append(
            f"| `{k}` | `{v.get('last_updated', '?')}` | {v.get('age_days', '?')} | `{v.get('freshness_status')}` | "
            f"**{v.get('risk_classification')}** | `{m_str}` | {w_str} |"
        )
    lines += ["", "## 2. Active Risk Alerts"]
    if alerts:
        for a in alerts:
            lines.append(f"- **[{a['severity']}] `{a['panel']}`:** {a['msg']}")
    else:
        lines.append("- None triggered.")
    lines += ["", "## 3. Missing Data / Staleness Warnings"]
    if payload["missing_data_warnings"]:
        for w in payload["missing_data_warnings"]:
            lines.append(f"- {w}")
    else:
        lines.append("- None.")

    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text("\n".join(lines) + "\n")
    print(f"RISK RADAR OK: overall={overall_risk} | fresh={payload['fresh_panels']}/{payload['total_panels']} | alerts={len(alerts)}")
    return payload


if __name__ == "__main__":
    build_risk_radar()
