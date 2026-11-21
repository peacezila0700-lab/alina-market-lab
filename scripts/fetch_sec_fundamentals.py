#!/usr/bin/env python3
"""
fetch_sec_fundamentals.py — SEC filings and financial statements, free and key-less, in compact form.

Why this exists: the pack had prices, positioning and macro but zero company fundamentals. That left
three of the owner's categories empty (Fundamental, Financial Statements, SEC filings) and made any
"is this move justified by earnings" question unanswerable.

Sources (all verified 200 on 2026-11-20, with a real contact User-Agent — SEC blocks generic UAs):
  https://www.sec.gov/files/company_tickers.json            ticker <-> CIK map   (796 KB)
  https://data.sec.gov/submissions/CIK##########.json       filing history       (160 KB/company)
  https://data.sec.gov/submissions/CIK##########.json       (same call)
  https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json   all XBRL facts (2-4 MB/company)
  https://api.nasdaq.com/api/screener/stocks?download=true  market cap / sector / industry (2.3 MB)

SEC fair-access rules are honoured: max ~5 requests/second (we use 4), one contact UA, no parallel floods.

What is extracted (us-gaap tags; alternatives tried in order so the column is populated across filers):
  revenue      Revenues | RevenueFromContractWithCustomerExcludingAssessedTax | SalesRevenueNet
  net_income   NetIncomeLoss
  eps_diluted  EarningsPerShareDiluted
  assets       Assets
  liabilities  Liabilities
  equity       StockholdersEquity
  cash         CashAndCashEquivalentsAtCarryingValue
  cfo          NetCashProvidedByUsedInOperatingActivities
  lt_debt      LongTermDebtNoncurrent | LongTermDebt

Uncertainty written down:
  * XBRL facts are AS FILED; there are no restatements here and no point-in-time vintage. A backtest that
    uses these must use `filed` (the filing date) as `available_from`, never `end` (period end).
  * Financial companies use different tags (e.g. Revenues is often absent); revenue will be NaN for some
    banks rather than wrong.
  * Only the top N companies by market cap are covered (default 80) — enough to answer "why did this
    index move" questions, not a full fundamental screener. Raise N with --top if needed.
  * Nasdaq's screener is unofficial: field names/lists can change without notice.

Outputs
  data/sec/company_tickers.csv     cik, ticker, title                     (~10k rows)
  data/sec/filings.csv             cik, ticker, form, filed, period, accession   (recent 25/company)
  data/sec/fundamentals.csv        cik, ticker, tag, period_end, fy, fp, form, filed, value, unit
  data/screener/nasdaq_all.csv     symbol, name, market_cap, sector, industry, country
  data/sec/MANIFEST_SEC.json       coverage + caveats
"""
import argparse
import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SEC = ROOT / "data" / "sec"
SCR = ROOT / "data" / "screener"
UA = "ALINA-Market-Lab research contact: alina.lab.contact@gmail.com"
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
PAUSE = 0.25          # ~4 req/s, under SEC's 10 req/s fair-access limit


BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def get(url, tries=3, timeout=90, ua=None):
    """ua=None -> the SEC contact UA (required by SEC). Nasdaq stalls on that UA and needs a browser UA."""
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua or UA,
                                                       "Accept": "*/*",
                                                       "Accept-Encoding": "gzip, deflate"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    import gzip
                    raw = gzip.decompress(raw)
                return raw.decode("utf-8", "replace")
        except Exception as e:                                   # noqa: BLE001
            if a == tries - 1:
                print(f"    ! {url.split('/')[-1][:40]}: {e}")
                return None
            time.sleep(2 + 3 * a)
    return None


def fetch_screener():
    SCR.mkdir(parents=True, exist_ok=True)
    # NOTE: `download=true` is what returns all 7,301 rows; without it `rows` comes back empty even
    # though `totalrecords` says 7301. limit=25 is ignored when download=true (response is ~2.3 MB).
    txt = get("https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=25&offset=0&download=true",
              timeout=60, ua=BROWSER_UA)
    if not txt:
        return None
    j = json.loads(txt)
    rows = (j.get("data") or {}).get("rows") or []
    df = pd.DataFrame(rows)
    if df.empty:
        return None
    ren = {"symbol": "symbol", "name": "name", "lastsale": "last_sale", "marketCap": "market_cap",
           "sector": "sector", "industry": "industry", "country": "country"}
    df = df[[c for c in ren if c in df.columns]].rename(columns=ren)
    if "market_cap" in df:
        df["market_cap"] = pd.to_numeric(df["market_cap"].astype(str).str.replace(r"[$,]", "", regex=True),
                                         errors="coerce")
    if "last_sale" in df:
        df["last_sale"] = pd.to_numeric(df["last_sale"].astype(str).str.replace(r"[$,]", "", regex=True),
                                        errors="coerce")
    df = df.sort_values("market_cap", ascending=False)
    df.to_csv(SCR / "nasdaq_all.csv", index=False)
    print(f"  screener: {len(df)} symbols -> {SCR/'nasdaq_all.csv'}")
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=80)
    args = ap.parse_args()
    SEC.mkdir(parents=True, exist_ok=True)

    screener = fetch_screener()

    txt = get("https://www.sec.gov/files/company_tickers.json")
    if not txt:
        print("  SEC tickers unavailable — stopping")
        return
    tk = pd.DataFrame(json.loads(txt).values())
    tk = tk.rename(columns={"cik_str": "cik", "ticker": "ticker", "title": "title"})
    tk["cik"] = tk["cik"].astype(int)
    tk.to_csv(SEC / "company_tickers.csv", index=False)
    print(f"  tickers: {len(tk)} companies")

    # choose the universe: top market caps that also have a CIK
    universe = []
    if screener is not None:
        m = screener.merge(tk, left_on="symbol", right_on="ticker", how="inner")
        m = m.drop_duplicates(subset=["cik"]).head(args.top)
        universe = [(int(r.cik), r.ticker) for r in m.itertuples()]
    if not universe:
        universe = [(int(r.cik), r.ticker) for r in tk.head(args.top).itertuples()]

    filings, fund_rows, done, failed = [], [], [], []
    for i, (cik, ticker) in enumerate(universe, 1):
        c8 = f"{cik:010d}"
        sub = get(f"https://data.sec.gov/submissions/CIK{c8}.json")
        if sub:
            j = json.loads(sub)
            recent = (j.get("filings") or {}).get("recent") or {}
            n = min(25, len(recent.get("form", [])))
            for k in range(n):
                filings.append({"cik": cik, "ticker": ticker, "form": recent["form"][k],
                                "filed": recent["filingDate"][k], "period": recent["reportDate"][k],
                                "accession": recent["accessionNumber"][k],
                                "primary_doc": recent["primaryDocument"][k]})
            done.append(ticker)
        else:
            failed.append((ticker, "submissions"))
        time.sleep(PAUSE)

        cf = get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{c8}.json", timeout=120)
        if not cf:
            failed.append((ticker, "companyfacts"))
            continue
        facts = (json.loads(cf).get("facts") or {}).get("us-gaap") or {}
        for name, tag_list in TAGS.items():
            # Collect ALL matching tags across accounting standard transitions (e.g. ASC 606 tag switch
            # around 2018); deduplicate per (period_start, period_end, form, filed) by tag priority.
            for rank, tag in enumerate(tag_list):
                if tag not in facts:
                    continue
                for unit, arr in (facts[tag].get("units") or {}).items():
                    for f in arr:
                        if f.get("form") not in ("10-K", "10-Q"):
                            continue
                        fund_rows.append({"cik": cik, "ticker": ticker, "field": name, "tag": tag,
                                          "tag_rank": rank,
                                          "period_start": f.get("start", ""),
                                          "period_end": f.get("end"), "fy": f.get("fy"), "fp": f.get("fp"),
                                          "form": f.get("form"), "filed": f.get("filed"),
                                          "value": f.get("val"), "unit": unit})
        time.sleep(PAUSE)
        if i % 10 == 0:
            print(f"    {i}/{len(universe)} companies …")

    fdf = pd.DataFrame(filings).drop_duplicates(subset=["cik", "accession"]) if filings else pd.DataFrame()
    if len(fdf):
        fdf.to_csv(SEC / "filings.csv", index=False)
    if fund_rows:
        gdf = (pd.DataFrame(fund_rows)
               .sort_values(["ticker", "field", "period_end", "filed", "tag_rank"])
               .drop_duplicates(subset=["cik", "field", "period_start", "period_end", "form", "filed"],
                                keep="first")
               .drop(columns=["tag_rank"]))
        gdf.to_csv(SEC / "fundamentals.csv", index=False)
    else:
        gdf = pd.DataFrame()

    (SEC / "MANIFEST_SEC.json").write_text(json.dumps({
        "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "data.sec.gov (XBRL companyfacts + submissions), sec.gov company_tickers, api.nasdaq.com",
        "companies_covered": len(done), "companies_failed": failed,
        "filings_rows": int(len(fdf)), "fundamental_rows": int(len(gdf)),
        "caveats": [
            "XBRL values are as-filed; use `filed` as available_from, never `period_end`.",
            "Banks/insurers often lack a Revenues tag -> NaN, not wrong.",
            "Only the top market-cap companies in the screener are covered.",
            "Nasdaq screener is an unofficial endpoint and may change."]}, indent=2))
    print(f"\n  filings {len(fdf)} rows | fundamentals {len(gdf)} rows | companies {len(done)}"
          f" | failed {len(failed)}")
    print(f"  -> {SEC}")


if __name__ == "__main__":
    main()
