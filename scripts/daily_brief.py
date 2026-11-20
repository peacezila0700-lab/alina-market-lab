#!/usr/bin/env python3
"""DAILY BRIEF — the file a local AI reads every morning (and again before each event).

The problem this solves: a local model cannot re-read 200 MB of CSVs each day, and it cannot search
the web reliably at 03:00. So this script compresses the whole data pack into a single small object:
the current STATE, the next 7 days of SCHEDULED EVENTS, the base-rate odds for the current state, the
levels that matter per instrument, the last 48h of headlines tagged by entity, plus pre-written
SCENARIO BRANCHES so the model only has to pick a branch instead of inventing a forecast.

Outputs (both written for the same instant):
  briefs/YYYY-MM-DD.json   machine-readable, ~25-40 KB
  briefs/YYYY-MM-DD.md     ~1.5-2.5k tokens, ordered by decision importance
  briefs/latest.json|md    copies of the newest

Design rules
  * Nothing here is a forecast. Every number is a *measured state* or a *measured base rate*.
  * Every section states its own data age, so the model never trusts a stale series silently.
  * Token discipline: the markdown is deduped and rounded; the JSON keeps full precision for code.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "briefs")
os.makedirs(OUT, exist_ok=True)
FOCUS = ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "GOLD", "SPY", "TLT", "DXY", "BTC", "VIX"]
RISK_ASSETS = ["SPY", "BTC", "GOLD"]


def rd(*rels: str) -> pd.DataFrame | None:
    for rel in rels:
        p = os.path.join(ROOT, rel)
        if not os.path.exists(p):
            continue
        try:
            return pd.read_csv(p)
        except Exception:                                         # noqa: BLE001
            continue
    return None


def age_days(dates: pd.Series | pd.Index | None) -> float | None:
    if dates is None or len(dates) == 0:
        return None
    d = pd.to_datetime(pd.Series(dates).astype(str), errors="coerce", utc=True).max()
    if pd.isna(d):
        return None
    return round((pd.Timestamp.now(tz="UTC") - d).total_seconds() / 86400, 2)


def base_rate_lookup(vix: float | None, dix_pct: float | None, fsi: float | None) -> list[dict]:
    br = rd("data/facts/base_rates.csv")
    if br is None:
        return []
    out = []
    for factor, value in (("VIX", vix), ("OFR_FSI", fsi)):
        if value is None or pd.isna(value):
            continue
        sub = br[(br.factor == factor) & (br.horizon_d.isin([21, 252]))]
        if sub.empty:
            continue
        # find the bucket that contains today's value by parsing the label
        for _, row in sub.iterrows():
            lab = str(row.bucket)
            hit = False
            if isinstance(value, float):
                try:
                    if lab.startswith("<"):
                        hit = value < float(lab[1:])
                    elif lab.startswith(">="):
                        hit = value >= float(lab[2:])
                    elif "-" in lab:
                        a, b = lab.split("-")
                        hit = float(a) <= value < float(b)
                except ValueError:
                    hit = False
            if hit:
                out.append({"factor": factor, "value": round(float(value), 3), "bucket": lab,
                            "horizon_days": int(row.horizon_d), "n_obs": int(row.n),
                            "n_effective": int(row.n_eff),
                            "median_ret_pct": float(row["median"]), "pct_positive": float(row.pct_pos),
                            "worst_pct": float(row.worst)})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    args = ap.parse_args()
    today = pd.Timestamp(args.date)

    brief: dict = {"generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                   "as_of": args.date, "state": {}, "scheduled_events": [], "base_rates": [],
                   "levels": {}, "news": [], "flags": [], "data_age_days": {}, "scenarios": []}

    # ---------------- state: vol, tails, stress, positioning, gamma
    vix_df = rd("data/collect/vix.csv", "data/official/VIX_CBOE_D.csv")
    vix = None
    if vix_df is not None:
        col = "VIXCLS" if "VIXCLS" in vix_df.columns else ("CLOSE" if "CLOSE" in vix_df.columns else vix_df.columns[-1])
        dcol = "DATE" if "DATE" in vix_df.columns else vix_df.columns[0]
        vix_df[dcol] = pd.to_datetime(vix_df[dcol], errors="coerce")
        vix_df = vix_df.dropna(subset=[dcol]).sort_values(dcol)
        vix = float(pd.to_numeric(vix_df[col], errors="coerce").dropna().iloc[-1])
        brief["state"]["vix"] = round(vix, 2)
        brief["state"]["vix_percentile_all_history"] = round(float(
            (pd.to_numeric(vix_df[col], errors="coerce") < vix).mean()) * 100, 1)
        brief["data_age_days"]["vix"] = age_days(vix_df[dcol].tail(1))

    skew_df = rd("data/collect/skew.csv", "data/options/SKEW.csv")
    if skew_df is not None:
        c = [x for x in skew_df.columns if x.upper() == "SKEW"][0]
        brief["state"]["skew"] = round(float(pd.to_numeric(skew_df[c], errors="coerce").dropna().iloc[-1]), 2)
        brief["state"]["skew_note"] = ">145 = tail protection expensive; <115 = complacent"

    dix = rd("data/collect/dix_gex.csv")
    if dix is not None:
        dix.columns = [c.lower() for c in dix.columns]
        dix["date"] = pd.to_datetime(dix.date, errors="coerce")
        dix = dix.dropna(subset=["date"]).sort_values("date")
        last = dix.iloc[-1]
        pct = float((dix.dix < last.dix).mean()) * 100
        brief["state"]["dix"] = round(float(last.dix), 4)
        brief["state"]["dix_percentile"] = round(pct, 1)
        brief["state"]["gex_usd_bn"] = round(float(last.gex) / 1e9, 1)
        brief["state"]["gex_regime"] = "negative (dealers amplify moves)" if last.gex < 0 else "positive (dealers dampen moves)"
        brief["data_age_days"]["dix_gex"] = age_days(dix.date.tail(1))

    fsi = rd("data/collect/ofr_fsi.csv", "data/alt/ofr_fsi.csv")
    fsi_val = None
    if fsi is not None:
        fsi["Date"] = pd.to_datetime(fsi.Date, errors="coerce")
        fsi = fsi.dropna(subset=["Date"]).sort_values("Date")
        fsi_val = float(fsi["OFR FSI"].iloc[-1])
        brief["state"]["ofr_fsi"] = round(fsi_val, 2)
        brief["state"]["ofr_fsi_4w_chg"] = round(float(fsi["OFR FSI"].iloc[-1] - fsi["OFR FSI"].iloc[-21]), 2) \
            if len(fsi) > 21 else None
        brief["data_age_days"]["ofr_fsi"] = age_days(fsi.Date.tail(1))

    fund = rd("data/collect/okx_btc_funding.csv")
    if fund is not None and len(fund):
        brief["state"]["btc_funding_8h_pct"] = round(float(fund.fundingRate.iloc[-1]) * 100, 5)
        brief["state"]["btc_funding_annualised_pct"] = round(float(fund.fundingRate.tail(21).mean()) * 3 * 365 * 100, 2)

    lsr = rd("data/collect/okx_btc_lsr.csv")
    if lsr is not None and len(lsr):
        brief["state"]["btc_long_short_ratio"] = round(float(lsr.long_short_ratio.iloc[-1]), 3)

    cot = rd("data/cot/cot_features.csv")
    if cot is not None:
        cot["available_from"] = pd.to_datetime(cot.available_from, errors="coerce")
        last_date = cot.available_from.max()
        snap = cot[cot.available_from == last_date][["instrument", "noncomm_net_pct_oi_pct156"]].dropna()
        brief["state"]["cot_as_of"] = str(last_date.date())
        brief["state"]["cot_extremes"] = (
            snap[(snap.noncomm_net_pct_oi_pct156 <= 0.10) | (snap.noncomm_net_pct_oi_pct156 >= 0.90)]
            .assign(side=lambda d: np.where(d.noncomm_net_pct_oi_pct156 >= 0.9, "crowded_long", "crowded_short"))
            .round(2).to_dict("records"))
        brief["data_age_days"]["cot"] = age_days(pd.Series([last_date]))

    news_p = rd("data/news/news_pressure.csv")
    if news_p is not None and len(news_p):
        last_day = news_p.day.max()
        brief["state"]["news_volume_today"] = int(news_p[(news_p.day == last_day) & (news_p.entity == "ALL")].n_headlines.sum())
        brief["data_age_days"]["news"] = age_days(pd.Series([last_day]))

    # ---------------- scheduled events, next 7 days
    cal = rd("data/events/event_calendar_full.csv")
    if cal is not None:
        cal["date"] = pd.to_datetime(cal.date, errors="coerce")
        win = cal[(cal.date >= today) & (cal.date <= today + pd.Timedelta(days=7))]
        brief["scheduled_events"] = (win[["date", "event", "detail", "date_confidence"]]
                                     .assign(date=lambda d: d.date.dt.strftime("%Y-%m-%d"))
                                     .sort_values("date").to_dict("records"))
    econ = rd("data/collect/econ_calendar.csv")
    if econ is not None and len(econ):
        econ["_d"] = pd.to_datetime(econ.get("date"), errors="coerce")
        upcoming = econ[(econ._d >= today) & (econ._d <= today + pd.Timedelta(days=7))]
        cols = [c for c in ("date", "time", "country", "title", "impact", "forecast", "previous") if c in upcoming.columns]
        brief["scheduled_events"] += upcoming[cols].head(40).to_dict("records")

    # ---------------- base rates for the current state
    brief["base_rates"] = base_rate_lookup(vix, brief["state"].get("dix_percentile"), fsi_val)

    # ---------------- levels for the focus list
    lv = rd("data/levels/levels_latest.csv")
    if lv is not None:
        keep = ["instrument", "close", "atr14", "pdh", "pdl", "pmh", "pml", "pivot", "pivot_r1", "pivot_s1",
                "swing_hi", "swing_lo", "vp_poc", "vp_hi", "vp_lo", "y52_hi", "y52_lo"]
        sub = lv[lv.instrument.isin(FOCUS)][[c for c in keep if c in lv.columns]]
        brief["levels"] = sub.to_dict("records")

    # ---------------- headlines, last 48h, entity-tagged
    news = rd("data/news/headlines.csv")
    if news is not None and len(news):
        news["_t"] = pd.to_datetime(news.harvested_utc, errors="coerce", utc=True)
        recent = news[news._t >= pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=48)]
        recent = recent.sort_values("_t", ascending=False).drop_duplicates("hash")
        brief["news"] = recent[["source", "title", "entities", "link"]].head(40).to_dict("records")

    # ---------------- flags: anything that should stop a naive trade
    s = brief["state"]
    if s.get("vix", 0) and s["vix"] >= 30:
        brief["flags"].append("VIХ>=30: volatility elevated — halve size, widen stops, expect gap risk")
    if s.get("gex_regime", "").startswith("negative"):
        brief["flags"].append("dealer gamma is NEGATIVE: moves get amplified both ways; trend signals are "
                              "less reliable and stop-hunts are more common")
    if s.get("ofr_fsi", 0) and s["ofr_fsi"] > 0.5:
        brief["flags"].append("OFR stress above average: funding/credit stress — check the sub-indices before sizing up")
    if any(e.get("event") in ("FOMC", "AUCTION") for e in brief["scheduled_events"]):
        brief["flags"].append("scheduled high-attention event inside 7 days: pre-write the scenario, "
                              "do not enter naked risk the session before")
    if brief["scheduled_events"]:
        conf_med = [e for e in brief["scheduled_events"] if e.get("date_confidence") == "med"]
        if conf_med:
            brief["flags"].append(f"{len(conf_med)} rule-derived event dates (~90-95% exact) — verify before "
                                  "relying on them")

    # ---------------- scenario branches: pre-written, pick one instead of inventing
    if vix is not None:
        for b in brief["base_rates"]:
            if b["factor"] == "VIX" and b["horizon_days"] == 21:
                brief["scenarios"].append({
                    "branch": f"VIX stays in {b['bucket']}",
                    "measured": f"median 21d SPY {b['median_ret_pct']:+.2f}%, {b['pct_positive']:.0f}% positive, "
                                f"worst {b['worst_pct']:+.1f}%, n_eff {b['n_effective']}",
                    "action": "size normally" if b["median_ret_pct"] > 0 and b["pct_positive"] > 60 else
                              "reduce size, require 2x cost coverage"})
    brief["scenarios"].append({
        "branch": "event surprise larger than expected",
        "measured": "FOMC day |SPY move| = 1.09x a random day; NFP = 1.33x on TLT",
        "action": "trade the SECOND move (post-event drift), not the first print — the first print is where "
                  "spreads are widest and the edge is thinnest"})
    brief["scenarios"].append({
        "branch": "nothing scheduled and vol low",
        "measured": "VIX 12-15 bucket: median 12m SPY +11.9%, 86.7% positive (n_eff small)",
        "action": "this is a carry/momentum environment, not a mean-reversion one"})

    # ---------------- write
    jpath = os.path.join(OUT, f"{args.date}.json")
    with open(jpath, "w") as f:
        json.dump(brief, f, indent=1, default=str)
    with open(os.path.join(OUT, "latest.json"), "w") as f:
        json.dump(brief, f, indent=1, default=str)

    md = [f"# Brief {args.date} (generated {brief['generated_utc']})", ""]
    md += ["## State", "| key | value |", "|---|---|"]
    for k, v in s.items():
        if isinstance(v, (list, dict)):
            v = json.dumps(v, default=str)[:220]
        md.append(f"| {k} | {v} |")
    md += ["", "## Next 7 days (scheduled)", "| date | event | detail | confidence |", "|---|---|---|---|"]
    for e in brief["scheduled_events"][:25]:
        md.append(f"| {e.get('date')} | {e.get('event', e.get('title', ''))} | {str(e.get('detail', ''))[:40]} | "
                  f"{e.get('date_confidence', e.get('impact', ''))} |")
    if brief["base_rates"]:
        md += ["", "## Base rates for the current state (measured, not forecast)", "",
               "| factor | value | bucket | horizon | median % | % positive | n_eff |", "|---|---|---|---|---|---|---|"]
        for b in brief["base_rates"]:
            md.append(f"| {b['factor']} | {b['value']} | {b['bucket']} | {b['horizon_days']}d | "
                      f"{b['median_ret_pct']:+.2f} | {b['pct_positive']:.0f} | {b['n_effective']} |")
    if brief["levels"]:
        md += ["", "## Levels (support/resistance, measured rules)", "",
               "| inst | close | pdh | pdl | pivot | r1 | s1 | poc | swing_hi | swing_lo | atr |",
               "|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in brief["levels"]:
            md.append(f"| {r['instrument']} | {r.get('close')} | {r.get('pdh')} | {r.get('pdl')} | {r.get('pivot')} | "
                      f"{r.get('pivot_r1')} | {r.get('pivot_s1')} | {r.get('vp_poc')} | {r.get('swing_hi')} | "
                      f"{r.get('swing_lo')} | {r.get('atr14')} |")
    if brief["news"]:
        md += ["", "## Headlines (last 48h, entity-tagged)", ""]
        for n in brief["news"][:18]:
            md.append(f"- [{n['source']}] {n['title']}" + (f"  `{n['entities']}`" if n.get("entities") else ""))
    md += ["", "## Flags", ""] + [f"- {x}" for x in brief["flags"]]
    md += ["", "## Scenario branches (pick one, do not invent)", ""] + \
          [f"- **{b['branch']}** — measured: {b['measured']} → action: {b['action']}" for b in brief["scenarios"]]
    md += ["", "## Data age (days)", ""] + [f"- {k}: {v}" for k, v in brief["data_age_days"].items()]
    with open(os.path.join(OUT, f"{args.date}.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    with open(os.path.join(OUT, "latest.md"), "w") as f:
        f.write("\n".join(md) + "\n")
    print(f"brief → {jpath}  ({os.path.getsize(jpath) / 1024:.0f} KB) + .md ({len(' '.join(md))} chars)")


if __name__ == "__main__":
    main()
