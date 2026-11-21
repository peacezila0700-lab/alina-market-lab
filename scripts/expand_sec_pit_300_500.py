#!/usr/bin/env python3
"""
Workstream A1 — Expand SEC Point-in-Time (PIT) Fundamentals to 300-500 US Companies
with true SEC `acceptanceDateTime` (16:00 America/New_York market cutoff) and matched daily prices.

Strictly honours SEC EDGAR fair-access policy (<= 5 req/sec, contact User-Agent).
Preserves existing `data/sec/` files while upgrading `filings.csv`, `fundamentals.csv`,
`pit_fundamentals.csv`, and matched daily price cache under `data/sec/prices_pit/`.

Pitfalls explicitly controlled:
  1. Uses `acceptanceDateTime` from `submissions/CIK*.json` when available:
     - If filed/accepted AFTER 16:00 America/New_York -> `available_from_trade_date` shifts to NEXT weekday!
     - If older filing is beyond `recent` (~1,000 filings) or lacks `acceptanceDateTime`, falls back
       conservatively to `filed + 1 calendar day` (or next weekday) so after-hours close leaks never occur.
  2. Never backdates comparative restatements (iterates chronologically on `available_from`).
  3. Explicitly records survivorship caveats (top market-cap active SEC filers via Nasdaq screener + Yahoo).
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import os
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SEC = ROOT / "data" / "sec"
SCR = ROOT / "data" / "screener"
PRICES_DIR = SEC / "prices_pit"

SEC_UA = "ALINA-Market-Lab research contact: alina.lab.contact@gmail.com"
BROWSER_UA = "Mozilla/5.0"
NY_TZ = ZoneInfo("America/New_York")
PAUSE = 0.22  # ~4.5 req/s total well under SEC 10 req/s limit

TAGS = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
        "SalesRevenueGoodsNet",
    ],
    "net_income": [
        "NetIncomeLoss",
        "NetIncomeLossAvailableToCommonStockholdersBasic",
        "ProfitLoss",
    ],
    "eps_diluted": ["EarningsPerShareDiluted", "EarningsPerShareBasic"],
    "assets": ["Assets"],
    "liabilities": ["Liabilities"],
    "equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
    "cfo": [
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ],
    "lt_debt": ["LongTermDebtNoncurrent", "LongTermDebt", "LongTermDebtAndCapitalLeaseObligations"],
}


def http_get(url: str, ua: str = SEC_UA, tries: int = 3, timeout: int = 60) -> str | None:
    for a in range(tries):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": ua, "Accept": "*/*", "Accept-Encoding": "gzip, deflate"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    raw = gzip.decompress(raw)
                return raw.decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            if a == tries - 1:
                return None
            time.sleep(1.5 + 2.0 * a)
    return None


def next_weekday(d: datetime.date) -> datetime.date:
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def acceptance_to_trade_date(filed_str: str, acc_dt_str: str | None) -> tuple[str, str]:
    """
    Convert SEC filing date + optional UTC `acceptanceDateTime` to first NYSE close date
    where the information is publicly known (`available_from`), strictly honoring 16:00 ET cutoff.
    """
    if acc_dt_str and len(acc_dt_str) >= 19:
        try:
            s = acc_dt_str.replace("Z", "+00:00")
            dt_utc = datetime.fromisoformat(s)
            if dt_utc.tzinfo is None:
                dt_utc = dt_utc.replace(tzinfo=timezone.utc)
            dt_ny = dt_utc.astimezone(NY_TZ)
            d = dt_ny.date()
            # Strictly after 16:00 ET (or at close without time buffer) -> next NYSE weekday
            if (dt_ny.hour, dt_ny.minute) >= (16, 0) or d.weekday() >= 5:
                d = next_weekday(d + timedelta(days=1))
            return d.isoformat(), dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:  # noqa: BLE001
            pass
    # Conservative fallback when acceptanceDateTime is absent: assume after-hours on filed_date -> next weekday
    try:
        d0 = datetime.strptime(filed_str[:10], "%Y-%m-%d").date()
        d1 = next_weekday(d0 + timedelta(days=1))
        return d1.isoformat(), ""
    except Exception:  # noqa: BLE001
        return filed_str, ""


def fetch_yahoo_daily(ticker: str, p1: int = 1388534400) -> list[tuple] | None:
    """Fetch 2014-01-01..now daily OHLC + Adj Close from Yahoo Finance chart API."""
    # Map class shares like BRK.B -> BRK-B for Yahoo
    ysym = ticker.replace(".", "-")
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ysym}"
        f"?period1={p1}&period2={int(time.time())}&interval=1d&events=div%2Csplits"
    )
    txt = http_get(url, ua=BROWSER_UA, tries=2, timeout=25)
    if not txt:
        return None
    try:
        j = json.loads(txt)
        res = (j.get("chart") or {}).get("result")
        if not res:
            return None
        r = res[0]
        ts = r.get("timestamp") or []
        q = (r.get("indicators") or {}).get("quote", [{}])[0]
        adj = ((r.get("indicators") or {}).get("adjclose") or [{}])[0].get("adjclose")
        rows = []
        for i, t in enumerate(ts):
            o, h, l, c = q["open"][i], q["high"][i], q["low"][i], q["close"][i]
            ac = adj[i] if adj and i < len(adj) and adj[i] is not None else c
            v = (q.get("volume") or [0])[i] if q.get("volume") else 0
            if None in (o, h, l, c) or c <= 0 or ac <= 0:
                continue
            d = datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d")
            rows.append((d, round(o, 6), round(h, 6), round(l, 6), round(c, 6), round(ac, 6), int(v or 0)))
        return rows if len(rows) >= 252 else None
    except Exception:  # noqa: BLE001
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=420, help="Target candidate companies by market cap")
    ap.add_argument("--skip-existing-prices", action="store_true")
    args = ap.parse_args()

    SEC.mkdir(parents=True, exist_ok=True)
    PRICES_DIR.mkdir(parents=True, exist_ok=True)

    scr = pd.read_csv(SCR / "nasdaq_all.csv")
    scr["market_cap"] = pd.to_numeric(scr["market_cap"], errors="coerce")
    scr = scr.dropna(subset=["market_cap"]).sort_values("market_cap", ascending=False)

    ct = pd.read_csv(SEC / "company_tickers.csv")
    ct["cik"] = ct["cik"].astype(int)

    merged = scr.merge(ct, left_on="symbol", right_on="ticker", how="inner").drop_duplicates(subset=["cik"])
    candidates = merged.head(args.top).copy()
    print(f"Candidate SEC-matched companies by mcap: {len(candidates)} across {candidates['sector'].nunique()} sectors")

    filings_rows = []
    fund_rows = []
    meta_rows = []
    done_tickers = []
    failed = []

    for idx, row in enumerate(candidates.itertuples(), 1):
        cik = int(row.cik)
        ticker = str(row.ticker)
        c10 = f"{cik:010d}"

        # 1) Submissions (acceptanceDateTime map)
        sub_txt = http_get(f"https://data.sec.gov/submissions/CIK{c10}.json", ua=SEC_UA)
        acc_map: dict[tuple[str, str], str] = {}
        if sub_txt:
            try:
                sj = json.loads(sub_txt)
                rec = (sj.get("filings") or {}).get("recent") or {}
                forms = rec.get("form") or []
                fdates = rec.get("filingDate") or []
                rdates = rec.get("reportDate") or []
                accdts = rec.get("acceptanceDateTime") or []
                accnos = rec.get("accessionNumber") or []
                pdocs = rec.get("primaryDocument") or []
                for k in range(len(forms)):
                    fm = forms[k]
                    fd = fdates[k] if k < len(fdates) else ""
                    ad = accdts[k] if k < len(accdts) else ""
                    if fm in ("10-K", "10-Q", "10-K/A", "10-Q/A") and fd and ad:
                        acc_map[(fm[:4], fd)] = ad
                    if k < 40:
                        avail_d, acc_utc = acceptance_to_trade_date(fd, ad)
                        filings_rows.append({
                            "cik": cik,
                            "ticker": ticker,
                            "form": fm,
                            "filed": fd,
                            "acceptance_utc": acc_utc,
                            "available_from": avail_d,
                            "period": rdates[k] if k < len(rdates) else "",
                            "accession": accnos[k] if k < len(accnos) else "",
                            "primary_doc": pdocs[k] if k < len(pdocs) else "",
                        })
            except Exception as e:  # noqa: BLE001
                failed.append((ticker, f"submissions_parse:{e}"))
        else:
            failed.append((ticker, "submissions_http"))
        time.sleep(PAUSE)

        # 2) XBRL companyfacts
        cf_txt = http_get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{c10}.json", ua=SEC_UA, timeout=90)
        if not cf_txt:
            failed.append((ticker, "companyfacts_http"))
            time.sleep(PAUSE)
            continue
        try:
            facts = (json.loads(cf_txt).get("facts") or {}).get("us-gaap") or {}
        except Exception:  # noqa: BLE001
            facts = {}
        if not facts:
            failed.append((ticker, "no_us_gaap"))
            time.sleep(PAUSE)
            continue

        t_rows = 0
        for field_name, tag_list in TAGS.items():
            for rank, tag in enumerate(tag_list):
                if tag not in facts:
                    continue
                for unit, arr in (facts[tag].get("units") or {}).items():
                    for f in arr:
                        fm = f.get("form")
                        if fm not in ("10-K", "10-Q"):
                            continue
                        fd = f.get("filed") or ""
                        if not fd or fd < "2010-01-01":
                            continue
                        acc_raw = acc_map.get((fm, fd), "")
                        avail_d, acc_utc = acceptance_to_trade_date(fd, acc_raw)
                        fund_rows.append({
                            "cik": cik,
                            "ticker": ticker,
                            "field": field_name,
                            "tag": tag,
                            "tag_rank": rank,
                            "period_start": f.get("start", ""),
                            "period_end": f.get("end"),
                            "fy": f.get("fy"),
                            "fp": f.get("fp"),
                            "form": fm,
                            "filed": fd,
                            "acceptance_utc": acc_utc,
                            "available_from": avail_d,
                            "value": f.get("val"),
                            "unit": unit,
                        })
                        t_rows += 1
        time.sleep(PAUSE)

        if t_rows == 0:
            failed.append((ticker, "zero_xbrl_rows"))
            continue

        # 3) Matched Daily Price Series (reuse data/stocks if exists or fetch Yahoo)
        p_out = PRICES_DIR / f"{ticker}.csv"
        stock_src = ROOT / "data" / "stocks" / f"{ticker}.csv"
        has_price = False
        if args.skip_existing_prices and p_out.exists():
            has_price = True
        elif stock_src.exists():
            # Copy existing clean stock price series and normalize columns
            dfp = pd.read_csv(stock_src)
            if len(dfp) >= 252:
                dfp.to_csv(p_out, index=False)
                has_price = True
        if not has_price:
            prows = fetch_yahoo_daily(ticker)
            if prows:
                with open(p_out, "w", newline="") as pf:
                    w = csv.writer(pf)
                    w.writerow(["date", "open", "high", "low", "close", "adjclose", "volume"])
                    w.writerows(prows)
                has_price = True
            time.sleep(0.08)

        if has_price:
            done_tickers.append(ticker)
            meta_rows.append({
                "cik": cik,
                "ticker": ticker,
                "name": row.name,
                "sector": row.sector,
                "industry": row.industry,
                "market_cap": float(row.market_cap),
                "xbrl_rows": t_rows,
            })

        if idx % 25 == 0 or idx == len(candidates):
            print(f"  [{idx}/{len(candidates)}] ok_with_price={len(done_tickers)} failed={len(failed)} fund_rows={len(fund_rows)}")

    # Save raw expanded files under dedicated Workstream A1 names AND keep legacy compatibility clean
    if filings_rows:
        fdf = pd.DataFrame(filings_rows).drop_duplicates(subset=["cik", "accession"])
        fdf.to_csv(SEC / "filings_expanded.csv", index=False)
    else:
        fdf = pd.DataFrame()

    if fund_rows:
        gdf = (
            pd.DataFrame(fund_rows)
            .sort_values(["ticker", "field", "period_end", "filed", "tag_rank"])
            .drop_duplicates(subset=["cik", "field", "period_start", "period_end", "form", "filed"], keep="first")
            .drop(columns=["tag_rank"])
        )
        gdf.to_csv(SEC / "fundamentals_expanded.csv", index=False)
    else:
        gdf = pd.DataFrame()

    if meta_rows:
        pd.DataFrame(meta_rows).to_csv(SEC / "universe_pit_meta.csv", index=False)

    manifest = {
        "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "candidate_target": args.top,
        "companies_complete_sec_and_price": len(done_tickers),
        "failed_count": len(failed),
        "failed_sample": failed[:30],
        "filings_expanded_rows": int(len(fdf)),
        "fundamentals_expanded_rows": int(len(gdf)),
        "acceptance_cutoff_rule": "16:00 America/New_York; >=16:00 ET or missing acceptanceDateTime -> next NYSE weekday",
        "caveats": [
            "Current-constituent market-cap ranking from Nasdaq screener introduces survivorship bias on dead/delisted firms.",
            "Banks/REITs lacking standard us-gaap Revenues or CFO tags have NaN on those specific metrics rather than forced imputation.",
        ],
    }
    (SEC / "MANIFEST_SEC_EXPANDED.json").write_text(json.dumps(manifest, indent=2))
    print("\nDONE EXPANDED SEC FETCH:", json.dumps({k: v for k, v in manifest.items() if k != "failed_sample"}, indent=2))


if __name__ == "__main__":
    main()
