#!/usr/bin/env python3
"""
fetch_congress_trades.py — US congressional stock transactions from the House Clerk's own filings.

Source of the idea: the day-trader-skill project (MIT) has a `/trader-pelosi` skill that reads these
same documents. Its review is in research/THIRD_PARTY_REVIEW_day_trader_skill.md. Two things were worth
keeping: the endpoint (House Clerk, official, free) and the discipline of treating the 45-day disclosure
lag as part of the data rather than an inconvenience.

Data route (verified 2026-11-21):
  index   https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{YEAR}FD.zip
          -> {YEAR}FD.xml, one <Member> per filing; FilingType 'P' = Periodic Transaction Report (PTR)
  detail  https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{YEAR}/{DocID}.pdf
          -> PDF; text extracted with pypdf (pip install pypdf — pure python, no system packages)
There is no JSON/CSV endpoint: the transactions only exist inside those PDFs. The community S3 mirrors
(house-stock-watcher / senate-stock-watcher) now return 403, so the official PDFs are the only route.

Parsing rule (the PDF's table is positional, so we anchor on the transaction-type token):
  a row starts with one of the type codes (P purchase, S sale, S (partial), E exchange) followed by the
  transaction date and the notification date; the amount range follows, sometimes wrapped onto the next
  line. The asset description is the line(s) immediately before it. `[XX]` in the description is the
  House asset-TYPE code (ST stock, GS government security, CS corporate bond, MF mutual fund...), NOT a
  ticker: the ticker, when present, appears in parentheses like "Apple Inc. (AAPL) [ST]".

Uncertainty written down:
  * The STOCK Act allows up to 45 days between the trade and the disclosure. `filed_date` is when the
    market could know; `transaction_date` is when it happened. Any study must use filed_date.
  * Amounts are RANGES ($1,001-$15,000 etc.), not values. Never treat the midpoint as an exact size.
  * Only PTR filings are parsed; annual reports (FilingType 'O') contain no transactions.
  * The PDF table wraps descriptions across lines and the layout shifts between years, so a small share
    of rows is expected to fail parsing — the manifest reports how many rows per filing were found.
  * This is a PARTIAL, recent sample (`--max-ptr`), not a full history. Scaling up is just a longer run.

Outputs
  data/congress/ptrs_index.csv        every PTR filing on record (year, member, state, filed, DocID)
  data/congress/congress_trades.csv   parsed transactions from the most recent N filings
  data/congress/MANIFEST_CONGRESS.json
"""
import argparse
import io
import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "congress"
UA = "ALINA-Market-Lab research contact: alina.lab.contact@gmail.com"
IDX = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{y}FD.zip"
PTR = "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{y}/{doc}.pdf"
TYPE_RE = re.compile(r"^\s*(P|S|S \(partial\)|E)\s+(\d{2}/\d{2}/\d{4})\s+(\d{2}/\d{2}/\d{4})\s*\$?([\d,]*)\s*-?")
AMT_NEXT = re.compile(r"^\s*\$([\d,]+)")
TICKER_RE = re.compile(r"\(([A-Z]{1,5}(?:\.[A-Z])?)\)")
TYPE_CODE_RE = re.compile(r"\[([A-Z]{2})\]")


def get(url, tries=3, timeout=90):
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception:                                        # noqa: BLE001
            if a == tries - 1:
                return None
            time.sleep(2 + 3 * a)
    return None


def index_year(year):
    data = get(IDX.format(y=year))
    if not data:
        return []
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
        name = next(n for n in z.namelist() if n.lower().endswith(".xml"))
        root = ET.fromstring(z.read(name).decode("utf-8", "replace"))
    except Exception:                                            # noqa: BLE001
        return []
    out = []
    for m in root.findall(".//Member"):
        ft = (m.findtext("FilingType") or "").strip()
        out.append({"year": year, "last": (m.findtext("Last") or "").strip(),
                    "first": (m.findtext("First") or "").strip(),
                    "state_district": (m.findtext("StateDst") or "").strip(),
                    "filing_type": ft, "filed": (m.findtext("FilingDate") or "").strip(),
                    "doc_id": (m.findtext("DocID") or "").strip()})
    return out


def pdf_text(data):
    try:
        from pypdf import PdfReader
    except ImportError:
        raise SystemExit("pypdf missing: pip install pypdf")
    r = PdfReader(io.BytesIO(data))
    return "\n".join((p.extract_text() or "") for p in r.pages)


def parse_ptr(text):
    lines = [l.rstrip() for l in text.splitlines()]
    rows = []
    for i, line in enumerate(lines):
        m = TYPE_RE.match(line)
        if not m:
            continue
        code, tdate, ndate, amt_lo = m.groups()
        amt_hi = None
        if i + 1 < len(lines):
            m2 = AMT_NEXT.match(lines[i + 1])
            if m2:
                amt_hi = m2.group(1)
        # the asset description is the closest preceding non-empty line that is not boilerplate
        asset = ""
        for j in range(i - 1, max(-1, i - 4), -1):
            cand = lines[j].strip()
            if not cand or cand.startswith(("ID Owner", "Type", "T", "F", "C", "I ", "S O:", "F S:")):
                continue
            asset = (cand + " " + asset).strip()
            if TYPE_CODE_RE.search(cand) or TICKER_RE.search(cand):
                break
        tick = TICKER_RE.search(asset)
        tcode = TYPE_CODE_RE.search(asset)
        rows.append({"type": code, "transaction_date": tdate, "notification_date": ndate,
                     "amount_low": int(amt_lo.replace(",", "")) if amt_lo else None,
                     "amount_high": int(amt_hi.replace(",", "")) if amt_hi else None,
                     "asset": asset[:120], "ticker_guess": tick.group(1) if tick else None,
                     "asset_type_code": tcode.group(1) if tcode else None})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", default="2019-2026")
    ap.add_argument("--max-ptr", type=int, default=250, help="how many recent PTR PDFs to parse")
    args = ap.parse_args()
    y0, y1 = (int(x) for x in args.years.split("-"))
    OUT.mkdir(parents=True, exist_ok=True)

    idx = []
    for y in range(y0, y1 + 1):
        rows = index_year(y)
        idx += rows
        ptrs = sum(1 for r in rows if r["filing_type"] == "P")
        print(f"  {y}: {len(rows):>5} filings ({ptrs} PTR)")
        time.sleep(0.3)
    if not idx:
        print("  index unavailable")
        return
    idf = pd.DataFrame(idx)
    idf.to_csv(OUT / "ptrs_index.csv", index=False)

    todo = idf[idf.filing_type == "P"].copy()
    todo["filed_dt"] = pd.to_datetime(todo["filed"], errors="coerce", format="%m/%d/%Y")
    todo = todo.dropna(subset=["filed_dt"]).sort_values("filed_dt", ascending=False).head(args.max_ptr)
    print(f"  parsing {len(todo)} most recent PTR PDFs …")

    out, failed, empty = [], 0, 0
    for i, r in enumerate(todo.itertuples(), 1):
        data = get(PTR.format(y=r.year, doc=r.doc_id))
        if not data:
            failed += 1
            continue
        try:
            txt = pdf_text(data)
        except Exception:                                        # noqa: BLE001
            failed += 1
            continue
        rows = parse_ptr(txt)
        if not rows:
            empty += 1
        for row in rows:
            row.update({"member": f"{r.first} {r.last}".strip(), "state_district": r.state_district,
                        "filed_date": r.filed_dt.date().isoformat(), "doc_id": r.doc_id})
            out.append(row)
        if i % 25 == 0:
            print(f"    {i}/{len(todo)} … ({len(out)} rows)")
        time.sleep(0.25)

    df = pd.DataFrame(out)
    if len(df):
        df["amount_mid"] = (df["amount_low"].fillna(0) + df["amount_high"].fillna(df["amount_low"])) / 2
        df = df.sort_values("filed_date")
        df.to_csv(OUT / "congress_trades.csv", index=False)
        top = df["asset_type_code"].value_counts().head(6).to_dict()
        print(f"\n  transactions {len(df)} from {df.member.nunique()} members "
              f"| purchases {int((df.type=='P').sum())} sales {int((df.type.str.startswith('S')).sum())} "
              f"| asset types {top} | failed {failed} empty {empty}")
    (OUT / "MANIFEST_CONGRESS.json").write_text(json.dumps({
        "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "disclosures-clerk.house.gov (House Clerk financial disclosure index + PTR PDFs), "
                  "text extracted with pypdf",
        "years_indexed": [y0, y1], "ptr_filings_indexed": int((idf.filing_type == "P").sum()),
        "ptr_parsed": int(len(todo)), "failed": failed, "empty": empty,
        "rows": int(len(df)) if len(df) else 0,
        "caveats": ["STOCK Act allows up to 45 days between trade and disclosure: use filed_date as "
                    "available_from, never transaction_date.",
                    "Amounts are ranges; amount_mid is an approximation, not a size.",
                    "Asset type code [ST] is a stock, [GS] a government security — the bracketed code is "
                    "NOT a ticker; ticker_guess comes from the (PAREN) in the description.",
                    "Partial sample only (--max-ptr); the index covers every filing in the years indexed.",
                    "House only. Senate eFD needs an interactive agreement flow and is not covered."]},
        indent=2))
    print(f"  -> {OUT/'congress_trades.csv'}")


if __name__ == "__main__":
    main()
