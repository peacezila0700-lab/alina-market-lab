#!/usr/bin/env python3
"""
build_insider.py — parse Form 4 filings into a clean insider-transaction dataset.

This is the one category the coverage matrix flagged as "held raw but not turned into numbers". Form 4
is genuinely non-price information: an officer buying their own stock with their own money, disclosed
within two business days, is one of the few free signals that is not derived from the tape.

Source: SEC EDGAR full-text archive, one XML per filing
  https://www.sec.gov/Archives/edgar/data/{cik}/{accession-without-dashes}/{primary_doc}
  (primary_doc from data/sec/filings.csv, which fetch_sec_fundamentals.py already stored)
All requests use the SEC contact UA at ~5 req/s.

Parsed fields (non-derivative transactions only — options/RSUs distort the money flow):
  transaction_date, transaction_code (P purchase, S sale, A grant, M exercise, F tax, D disposal...),
  shares, price_per_share, acquired_disposed (A/D), shares_owned_after, and the reporting owner's
  name / is_director / is_officer / is_ten_percent_owner.

Uncertainty written down:
  * Form 4 is filed within 2 business days, so transaction_date is slightly EARLIER than the date the
    market could know. A backtest must use `filed` as available_from, not transaction_date.
  * Only Form 4 filings already in data/sec/filings.csv exist here (last 25 filings per company), so the
    history is short and uneven. This is a starting panel, not a 10-year insider database.
  * Grants (code A) and option exercises (M) are NOT purchases: treating them as bullish flow is the
    classic error. Only P and S are used for the net-flow measure.
  * Values are as-filed dollar amounts; there is no adjustment for splits later.

Outputs
  data/sec/insider_transactions.csv
  data/sec/MANIFEST_INSIDER.json
"""
import json
import time
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SEC = ROOT / "data" / "sec"
UA = "ALINA-Market-Lab research contact: alina.lab.contact@gmail.com"
ARCHIVE = "https://www.sec.gov/Archives/edgar/data/{cik}/{acc}/{doc}"


def get(url, tries=3, timeout=45):
    for a in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8", "replace")
        except Exception:                                        # noqa: BLE001
            if a == tries - 1:
                return None
            time.sleep(1.5 + 2 * a)
    return None


def txt(node, path):
    el = node.find(path)
    return el.text.strip() if el is not None and el.text else None


def parse_form4(xml_text, cik, ticker, filed):
    rows = []
    try:
        root = ET.fromstring(xml_text)
    except Exception:                                            # noqa: BLE001
        return rows
    owner = root.find(".//reportingOwner")
    name = txt(owner, "reportingOwnerId/rptOwnerName") if owner is not None else None
    rel = owner.find("reportingOwnerRelationship") if owner is not None else None
    is_dir = txt(rel, "isDirector") if rel is not None else None
    is_off = txt(rel, "isOfficer") if rel is not None else None
    is_ten = txt(rel, "isTenPercentOwner") if rel is not None else None
    title = txt(rel, "officerTitle") if rel is not None else None
    for t in root.findall(".//nonDerivativeTransaction"):
        code = txt(t, "transactionCoding/transactionCode")
        date_ = txt(t, "transactionDate/value")
        shares = txt(t, "transactionAmounts/transactionShares/value")
        price = txt(t, "transactionAmounts/transactionPricePerShare/value")
        ad = txt(t, "transactionAmounts/transactionAcquiredDisposedCode/value")
        after = txt(t, "postTransactionAmounts/sharesOwnedFollowingTransaction/value")
        try:
            shares_f = float(shares) if shares is not None else None
            price_f = float(price) if price not in (None, "") else None
        except ValueError:
            shares_f, price_f = None, None
        rows.append({"cik": cik, "ticker": ticker, "filed": filed, "transaction_date": date_,
                     "code": code, "acquired_disposed": ad, "shares": shares_f,
                     "price": price_f,
                     "value_usd": (shares_f * price_f) if (shares_f and price_f) else None,
                     "shares_after": float(after) if after not in (None, "") else None,
                     "insider": name, "is_director": is_dir, "is_officer": is_off,
                     "is_ten_percent": is_ten, "title": title})
    return rows


def main():
    fil = pd.read_csv(SEC / "filings.csv")
    f4 = fil[fil["form"].astype(str).str.startswith("4")].copy()
    print(f"  Form 4 filings to parse: {len(f4)}")
    rows, failed = [], 0
    for i, r in enumerate(f4.itertuples(), 1):
        acc = str(r.accession).replace("-", "")
        # `primary_doc` is the XSL-RENDERED HTML (e.g. "xslF345X06/form4.xml"), not the raw XML. Strip the
        # xsl directory: .../000114036126044952/form4.xml is the machine-readable document. Feeding the
        # rendered HTML to ElementTree yields zero rows, which is exactly what happened on the first run.
        doc = str(r.primary_doc).split("/")[-1]
        xml_text = get(ARCHIVE.format(cik=int(r.cik), acc=acc, doc=doc))
        if not xml_text or "<ownershipDocument" not in xml_text:
            # fall back to the filing index: pick the first .xml that is not the xsl wrapper
            idx = get(f"https://www.sec.gov/Archives/edgar/data/{int(r.cik)}/{acc}/index.json")
            xml_text = None
            if idx:
                try:
                    items = json.loads(idx)["directory"]["item"]
                    cand = [it["name"] for it in items
                            if str(it["name"]).endswith(".xml") and not str(it["name"]).startswith("R")]
                    for c in cand:
                        t = get(ARCHIVE.format(cik=int(r.cik), acc=acc, doc=c))
                        if t and "<ownershipDocument" in t:
                            xml_text = t
                            break
                except Exception:                                # noqa: BLE001
                    pass
        if not xml_text:
            failed += 1
            continue
        rows += parse_form4(xml_text, int(r.cik), r.ticker, r.filed)
        if i % 50 == 0:
            print(f"    {i}/{len(f4)} …")
        time.sleep(0.2)

    df = pd.DataFrame(rows)
    if len(df):
        df = df.dropna(subset=["transaction_date"]).sort_values("transaction_date")
        df.to_csv(SEC / "insider_transactions.csv", index=False)
        p = df[df.code == "P"]
        s = df[df.code == "S"]
        print(f"\n  insider rows {len(df)} | purchases {len(p)} (${p.value_usd.sum() if len(p) else 0:,.0f}) "
              f"| sales {len(s)} (${s.value_usd.sum() if len(s) else 0:,.0f}) "
              f"| insiders {df.insider.nunique()} | failed fetches {failed}")
    (SEC / "MANIFEST_INSIDER.json").write_text(json.dumps({
        "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "form4_filings_parsed": int(len(f4)), "failed": failed, "rows": int(len(df)),
        "caveats": ["Only Form 4s inside the last-25-filings window of the covered companies.",
                    "A backtest must use `filed`, not `transaction_date` (Form 4 is filed up to 2 "
                    "business days after the trade).",
                    "Grants (A) and exercises (M) are not purchases; only P and S measure money flow.",
                    "No split adjustment."]}, indent=2))
    print(f"  -> {SEC/'insider_transactions.csv'}")


if __name__ == "__main__":
    main()
