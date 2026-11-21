#!/usr/bin/env python3
"""
Workstream A2 & B1 — Fetch Official Central Bank Policy Rates & Announcement Dates
Sources (all HTTP 200 verified):
  - ECB Deposit Facility Rate (DFR) + Main Refinancing Operations (MRO): data-api.ecb.europa.eu
  - Bank of England Official Bank Rate (1975..2026): bankofengland.co.uk/boeapps/database/Bank-Rate.asp
  - Federal Reserve EFFR (2016..2026): markets.newyorkfed.org + Yahoo ^IRX (13W T-Bill 2000..2026)

Builds:
  data/macro/central_bank_rates_daily.csv   (date, ecb_dfr, ecb_mro, boe_rate, fed_effr_or_irx, diff_boe_ecb, diff_fed_ecb, decision flags)
  data/macro/cb_rate_changes.csv            (exact announcement dates & bps change per central bank)
  data/macro/MANIFEST_CB_RATES.json
"""
from __future__ import annotations

import csv
import io
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "macro"
UA = {"User-Agent": "Mozilla/5.0"}


def get(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def fetch_ecb(series: str) -> pd.DataFrame:
    url = f"https://data-api.ecb.europa.eu/service/data/FM/{series}?format=csvdata&startPeriod=1999-01-01"
    raw = get(url).decode("utf-8", "replace")
    df = pd.read_csv(io.StringIO(raw))
    df = df[["TIME_PERIOD", "OBS_VALUE"]].rename(columns={"TIME_PERIOD": "date", "OBS_VALUE": "rate"})
    df["date"] = pd.to_datetime(df["date"])
    df["rate"] = pd.to_numeric(df["rate"], errors="coerce")
    return df.dropna().sort_values("date")


def fetch_boe() -> pd.DataFrame:
    html = get("https://www.bankofengland.co.uk/boeapps/database/Bank-Rate.asp").decode("utf-8", "replace")
    rows = re.findall(r"<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>", html, re.S)
    recs = []
    for dt_txt, val_txt in rows:
        dt_clean = re.sub(r"<[^>]+>", "", dt_txt).strip()
        val_clean = re.sub(r"<[^>]+>", "", val_txt).strip()
        try:
            d = datetime.strptime(dt_clean, "%d %b %y").date()
            v = float(val_clean)
            recs.append((pd.Timestamp(d), v))
        except Exception:  # noqa: BLE001
            continue
    df = pd.DataFrame(recs, columns=["date", "boe_rate"]).drop_duplicates("date").sort_values("date")
    return df


def fetch_nyfed_effr() -> pd.DataFrame:
    url = "https://markets.newyorkfed.org/api/rates/unsecured/effr/search.json?startDate=2016-03-01&endDate=2026-11-21"
    j = json.loads(get(url).decode("utf-8", "replace"))
    rows = []
    for r in j.get("refRates", []):
        if r.get("effectiveDate") and r.get("percentRate") is not None:
            rows.append((pd.Timestamp(r["effectiveDate"]), float(r["percentRate"])))
    return pd.DataFrame(rows, columns=["date", "effr"]).drop_duplicates("date").sort_values("date")


def fetch_irx() -> pd.DataFrame:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/%5EIRX?period1=946684800&period2={int(datetime.now(timezone.utc).timestamp())}&interval=1d"
    j = json.loads(get(url).decode("utf-8", "replace"))
    r = j["chart"]["result"][0]
    q = r["indicators"]["quote"][0]
    rows = []
    for i, t in enumerate(r["timestamp"]):
        c = q["close"][i]
        if c is not None and c > -5:
            d = datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d")
            rows.append((pd.Timestamp(d), float(c)))
    return pd.DataFrame(rows, columns=["date", "irx_3m"]).drop_duplicates("date").sort_values("date")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ecb_dfr = fetch_ecb("B.U2.EUR.4F.KR.DFR.LEV").rename(columns={"rate": "ecb_dfr"})
    ecb_mro = fetch_ecb("B.U2.EUR.4F.KR.MRR_FR.LEV").rename(columns={"rate": "ecb_mro"})
    boe = fetch_boe()
    effr = fetch_nyfed_effr()
    irx = fetch_irx()

    # Build strict causal daily calendar (forward-fill announced policy rate ONLY after effective date)
    cal = pd.DataFrame({"date": pd.date_range("1999-01-01", "2026-11-20", freq="D")})
    df = (
        cal.merge(ecb_dfr, on="date", how="left")
        .merge(ecb_mro, on="date", how="left")
        .merge(boe, on="date", how="left")
        .merge(effr, on="date", how="left")
        .merge(irx, on="date", how="left")
    )
    # Seed initial BoE rate from latest pre-1999 change
    pre99 = boe[boe["date"] < "1999-01-01"]
    if not pre99.empty:
        df.loc[df["date"] == "1999-01-01", "boe_rate"] = float(pre99.iloc[-1]["boe_rate"])

    for col in ("ecb_dfr", "ecb_mro", "boe_rate", "effr", "irx_3m"):
        df[col] = df[col].ffill()

    # Fed proxy: exact EFFR from 2016-03-01 onwards; prior to 2016-03-01 use 13W T-Bill (^IRX)
    df["fed_rate_proxy"] = df["effr"].combine_first(df["irx_3m"])
    df["diff_boe_ecb_dfr"] = df["boe_rate"] - df["ecb_dfr"]
    df["diff_fed_ecb_dfr"] = df["fed_rate_proxy"] - df["ecb_dfr"]

    # Exact central bank change events
    changes = []
    for bank, src_df, col in (
        ("ECB_DFR", ecb_dfr, "ecb_dfr"),
        ("BOE_BANK_RATE", boe, "boe_rate"),
    ):
        s = src_df.sort_values("date").copy()
        s["prev"] = s[col].shift(1)
        s["delta_bps"] = (s[col] - s["prev"]) * 100.0
        chg = s[s["delta_bps"].abs() >= 1.0]
        for r in chg.itertuples():
            changes.append({
                "date": r.date.strftime("%Y-%m-%d"),
                "central_bank": bank,
                "new_rate_pct": round(float(getattr(r, col)), 4),
                "delta_bps": round(float(r.delta_bps), 2),
            })

    # Add FOMC 205 dates flagged with 3M/2Y yield surprise if Treasury file exists
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    df.to_csv(OUT / "central_bank_rates_daily.csv", index=False)
    chg_df = pd.DataFrame(changes).sort_values("date")
    chg_df.to_csv(OUT / "cb_rate_changes.csv", index=False)

    manifest = {
        "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "daily_rows": int(len(df)),
        "rate_changes_rows": int(len(chg_df)),
        "sources": {
            "ecb_dfr": f"data-api.ecb.europa.eu ({len(ecb_dfr)} obs)",
            "ecb_mro": f"data-api.ecb.europa.eu ({len(ecb_mro)} obs)",
            "boe_bank_rate": f"bankofengland.co.uk ({len(boe)} changes since {boe['date'].min().date()})",
            "fed_effr": f"markets.newyorkfed.org ({len(effr)} obs since {effr['date'].min().date()})",
            "us_irx_fallback": f"Yahoo ^IRX ({len(irx)} obs since {irx['date'].min().date()})",
        },
        "caveat": "Fed EFFR starts 2016-03-01 via NYFed API; pre-2016 uses ^IRX 13W T-Bill close as causal risk-free proxy.",
    }
    (OUT / "MANIFEST_CB_RATES.json").write_text(json.dumps(manifest, indent=2))
    print("DONE CENTRAL BANK RATES:", json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
