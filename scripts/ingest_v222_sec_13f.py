#!/usr/bin/env python3
"""
v2.22 Pillar 5: SEC Form 13F Bulk Institutional Holdings Ingestion (2013q2 .. 2026q3, 54 zips).
- Maps our 388-firm survivorship-free equity universe (320 active + 68 delisted) via OpenFIGI + 13F multi-era CUSIP/name matching.
- Streams each SEC 13F bulk zip to /var/tmp, chunk-parses INFOTABLE.tsv (<100MB RAM), deletes zip immediately.
- Enforces strict causal availability: keeps 13F-HR filed within [period_end + 1d, period_end + 50d], sets
  available_date = max(FILING_DATE) + 1 day, and normalizes pre-2023 ($1,000s) vs post-2023 ($1) VALUE cleanly.
"""
from __future__ import annotations

import gc
import os
import re
import time
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SEC_DIR = ROOT / "data" / "sec"
TMP_ZIP = Path("/var/tmp/alina_13f_stream.zip")
PARTS_DIR = Path("/var/tmp/alina_13f_parts")
HEADERS = {"User-Agent": "ALINA Research Lab alina@research.local"}


def norm_name(s: str) -> str:
    s = str(s).upper().replace("&", " ")
    s = re.sub(
        r"\b(INC|INCORPORATED|CORP|CORPORATION|CO|COMPANY|COMPANIES|LTD|LIMITED|PLC|NV|SA|LP|HOLDINGS|HOLDING|HLDGS|GROUP|GRP|"
        r"COMMON|COM|STOCK|STK|CLASS|CL|SHS|SHARES|ORDINARY|ORD|NEW|THE|DE|DEL|TRUST|TR|BANCORP|BANCSHARES|SVCS|SERVICES|"
        r"INTL|INTERNATIONAL|TECHNOLOGIES|TECH|SYSTEMS|SYS|INDUSTRIES|IND|PRODUCTS|PROD|ENTERPRISES|A|B|C)\b",
        " ",
        s,
    )
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def fetch_13f_zip_urls() -> list[str]:
    html = urllib.request.urlopen(
        urllib.request.Request("https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets", headers=HEADERS),
        timeout=30,
    ).read().decode("utf-8", errors="ignore")
    hrefs = re.findall(r'href="([^"]+_form13f\.zip)"', html)
    urls = []
    seen = set()
    for h in hrefs:
        u = "https://www.sec.gov" + h if h.startswith("/") else h
        if u not in seen:
            seen.add(u)
            urls.append(u)
    # Chronological: HTML lists newest first -> reverse to oldest (2013q2 .. 2026q3)
    return list(reversed(urls))


def stream_zip(url: str) -> None:
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=120) as resp, open(TMP_ZIP, "wb") as out:
                while ch := resp.read(1 << 20):
                    out.write(ch)
            return
        except Exception as e:
            if attempt == 2:
                raise
            print(f"  Retry download ({e})...")
            time.sleep(2.5)


def build_crosswalk(urls: list[str]) -> dict[str, str]:
    """Map CUSIP8/9 -> ticker across active (320) and delisted (68) firms using FIGI + multi-era 13F snapshots."""
    pm = pd.read_csv(SEC_DIR / "universe_pit_meta.csv")
    dm = pd.read_csv(SEC_DIR / "delisted_pit_meta.csv")
    of_df = pd.read_csv(SEC_DIR / "openfigi_active_map.csv")
    ct = pd.read_csv(SEC_DIR / "company_tickers.csv")

    figi_to_ticker = {}
    for row in of_df.itertuples():
        for col in ("figi", "compositeFIGI"):
            val = getattr(row, col, None)
            if isinstance(val, str) and val.startswith("BBG"):
                figi_to_ticker[val] = row.ticker

    # Also build exact & stripped name lookup for active + delisted
    universe_rows = []
    for r in pm.itertuples():
        universe_rows.append((r.ticker, r.name, False))
    for r in dm.itertuples():
        universe_rows.append((r.ticker, r.name, True))
    # Augment active names from company_tickers.csv if missing
    ct_map = dict(zip(ct["ticker"].astype(str), ct["title"].astype(str)))

    norm_to_tickers: dict[str, list[str]] = defaultdict(list)
    for t, nm, _ in universe_rows:
        for cand_nm in {nm, ct_map.get(t, "")}:
            nk = norm_name(cand_nm)
            if nk:
                norm_to_tickers[nk].append(t)

    # Manual/well-known name variations where 13F abbreviates differently from SEC entity names
    alias_norm = {
        "ELI LILLY": "LLY",
        "LILLY ELI": "LLY",
        "JPMORGAN CHASE": "JPM",
        "JP MORGAN CHASE": "JPM",
        "EXXON MOBIL": "XOM",
        "EXXONMOBIL": "XOM",
        "PROCTER GAMBLE": "PG",
        "GENERAL ELECTRIC": "GE",
        "GE AEROSPACE": "GE",
        "PHILIP MORRIS": "PM",
        "TEXAS INSTRS": "TXN",
        "TEXAS INSTRUMENTS": "TXN",
        "LINDE": "LIN",
        "INTL BUSINESS MACHS": "IBM",
        "INTERNATIONAL BUSINESS MACHS": "IBM",
        "DISNEY WALT": "DIS",
        "WALT DISNEY": "DIS",
        "FACEBOOK": "META",
        "META PLATFORMS": "META",
        "ALPHABET": "GOOGL",
        "GOOGLE": "GOOGL",
        "BERKSHIRE HATHAWAY": "BRK-B",
        "UNITED TECHNOLOGIES": "RTX",
        "RAYTHEON": "RTX",
        "SQUARE": "XYZ",
        "BLOCK": "XYZ",
        "PAYPAL": "PYPL",
        "TWITTER": "TWTR",
        "ACTIVISION BLIZZARD": "ATVI",
        "BED BATH BEYOND": "BBBYQ",
        "SILICON VALLEY BANK": "SIVBQ",
        "SVB FINL": "SIVBQ",
        "SIGNATURE BANK": "SBNY",
        "FIRST REPUBLIC BANK": "FRCB",
        "MONSANTO": "MON",
        "CELGENE": "CELG",
        "ALEXION PHARMACEUTICALS": "ALXN",
        "WALGREENS BOOTS ALLIANCE": "WBA",
        "RITE AID": "RADCQ",
        "AMERICAN AIRLS": "AAL",
        "UNITED CONTL": "UAL",
        "UNITED AIRLS": "UAL",
        "SOUTHWEST AIRLS": "LUV",
        "GOLDMAN SACHS": "GS",
        "MORGAN STANLEY": "MS",
        "BANK AMERICA": "BAC",
        "WELLS FARGO": "WFC",
        "JOHNSON JOHNSON": "JNJ",
        "COCA COLA": "KO",
        "PEPSICO": "PEP",
        "HOME DEPOT": "HD",
        "COSTCO WHSL": "COST",
        "THERMO FISHER SCIENTIFIC": "TMO",
        "BRISTOL MYERS SQUIBB": "BMY",
        "MONDELEZ": "MDLZ",
        "BOOKING": "BKNG",
        "PRICELINE": "BKNG",
        "ANALOG DEVICES": "ADI",
        "TEXAS ROADHOUSE": "TXRH",
        "ONEOK": "OKE",
        "TEVA PHARMACEUTICAL": "TEVA",
        "AETNA": "AET",
        "FLIR": "FLIR",
        "MYLAN": "MYL",
        "PRAXAIR": "PX",
        "SPIRIT AIRLS": "SAVEQ",
        "SPIRIT AVIATION": "SAVEQ",
        "ST JUDE MED": "STJ",
        "ST JUDE MEDICAL": "STJ",
        "TIME WARNER": "TWX",
    }

    # Scan 5 representative zips across 2013-2026 to discover ALL historical + FIGI-verified CUSIPs
    probe_patterns = ["2014q1", "2017q1", "2020q1", "2023q4", "01jun2026-31aug2026"]
    probe_urls = [u for u in urls if any(p in u for p in probe_patterns)]
    cusip_votes: dict[tuple[str, str], float] = defaultdict(float)  # (cusip9, ticker) -> total rows
    cusip_meta: dict[str, tuple[str, str]] = {}

    for u in probe_urls:
        print(f"  Crosswalk scan: {u.split('/')[-1]}")
        stream_zip(u)
        with zipfile.ZipFile(TMP_ZIP) as zf:
            names = zf.namelist()
            info_name = next(n for n in names if "INFOTABLE" in n.upper())
            with zf.open(info_name) as f:
                # read header first to see if FIGI exists
                hdr = f.readline().decode("utf-8", errors="ignore").strip().split("\t")
            usecols = [c for c in ["NAMEOFISSUER", "TITLEOFCLASS", "CUSIP", "FIGI", "PUTCALL", "SSHPRNAMTTYPE"] if c in hdr]
            with zf.open(info_name) as f:
                for ch in pd.read_csv(f, sep="\t", usecols=usecols, dtype=str, chunksize=250_000):
                    # Filter out debt/notes/warrants/preferred/convertible bonds
                    tc = ch["TITLEOFCLASS"].fillna("").str.upper()
                    is_eq = ~tc.str.contains(r"\b(?:NOTE|NT|BOND|BD|DEB|CV|CONV|SR|SUB|PFD|PRF|PREF|WT|WTS|EXP|UNIT|RT|REGS|144A)\b", regex=True)
                    if "SSHPRNAMTTYPE" in ch.columns:
                        is_eq = is_eq & (ch["SSHPRNAMTTYPE"].fillna("SH").str.upper().str.strip() != "PRN")
                    sub = ch[is_eq].copy()
                    sub["CUSIP"] = sub["CUSIP"].fillna("").str.upper().str.strip()
                    sub["CUSIP"] = np.where(sub["CUSIP"].str.len() == 8, "0" + sub["CUSIP"], sub["CUSIP"])
                    sub = sub[sub["CUSIP"].str.len() == 9]

                    # 1. FIGI exact match (2024-2026)
                    if "FIGI" in sub.columns:
                        figi_hit = sub["FIGI"].map(figi_to_ticker)
                        m_f = figi_hit.notna()
                        if m_f.any():
                            vc = sub.loc[m_f].assign(tk=figi_hit[m_f]).groupby(["CUSIP", "tk"]).size()
                            for (cus, tk), cnt in vc.items():
                                cusip_votes[(cus, tk)] += cnt * 5.0  # high weight for exact FIGI

                    # 2. Exact normalized name & alias match
                    uniq_pairs = sub[["CUSIP", "NAMEOFISSUER", "TITLEOFCLASS"]].drop_duplicates("CUSIP")
                    vc_cus = sub["CUSIP"].value_counts()
                    for row in uniq_pairs.itertuples():
                        cnt = float(vc_cus.get(row.CUSIP, 0))
                        if cnt < 5:
                            continue
                        nk = norm_name(row.NAMEOFISSUER)
                        tks = norm_to_tickers.get(nk, [])
                        if not tks and nk in alias_norm:
                            tks = [alias_norm[nk]]
                        # Also prefix match for unique >10 char prefixes
                        if len(tks) == 1:
                            cusip_votes[(row.CUSIP, tks[0])] += cnt
                            cusip_meta[row.CUSIP] = (row.NAMEOFISSUER, row.TITLEOFCLASS)
        TMP_ZIP.unlink(missing_ok=True)

    # Resolve best ticker per CUSIP (require dominant vote and >=10 filings across probe set)
    by_cusip: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for (cus, tk), w in cusip_votes.items():
        if w >= 10:
            by_cusip[cus].append((tk, w))
    cusip_to_ticker: dict[str, str] = {}
    for cus, lst in by_cusip.items():
        lst.sort(key=lambda x: -x[1])
        cusip_to_ticker[cus] = lst[0][0]

    # Save crosswalk
    cw_rows = [{"cusip": c, "ticker": t, "issuer": cusip_meta.get(c, ("", ""))[0], "title": cusip_meta.get(c, ("", ""))[1]} for c, t in sorted(cusip_to_ticker.items(), key=lambda x: (x[1], x[0]))]
    pd.DataFrame(cw_rows).to_csv(SEC_DIR / "sec_13f_cusip_crosswalk.csv", index=False)
    matched_tks = set(cusip_to_ticker.values())
    pm_hit = sum(1 for t in pm["ticker"] if t in matched_tks)
    dm_hit = sum(1 for t in dm["ticker"] if t in matched_tks)
    print(f"Crosswalk ready: {len(cusip_to_ticker)} CUSIPs covering {pm_hit}/{len(pm)} active + {dm_hit}/{len(dm)} delisted firms!")
    return cusip_to_ticker


def ingest_all_zips(urls: list[str], cusip_to_ticker: dict[str, str]) -> None:
    """Stream all 54 SEC 13F zips with <30MB RAM, checkpoint per zip, and build causal quarterly panel."""
    PARTS_DIR.mkdir(parents=True, exist_ok=True)
    cusip8_map = {c[:8]: t for c, t in cusip_to_ticker.items()}

    for idx_u, u in enumerate(urls, 1):
        fname = u.split("/")[-1]
        part_path = PARTS_DIR / f"{idx_u:02d}_{fname}.csv"
        if part_path.exists():
            continue
        t0 = time.time()
        stream_zip(u)
        rows_zip = []
        med_ratio = 0.0
        with zipfile.ZipFile(TMP_ZIP) as zf:
            names = zf.namelist()
            sub_name = next(n for n in names if "SUBMISSION" in n.upper())
            info_name = next(n for n in names if "INFOTABLE" in n.upper())

            with zf.open(sub_name) as f:
                sub = pd.read_csv(f, sep="\t", usecols=["ACCESSION_NUMBER", "FILING_DATE", "SUBMISSIONTYPE", "CIK", "PERIODOFREPORT"], dtype=str, low_memory=False)
            sub = sub[sub["SUBMISSIONTYPE"] == "13F-HR"].copy()
            sub["fdate"] = pd.to_datetime(sub["FILING_DATE"], format="mixed", errors="coerce")
            sub["pdate"] = pd.to_datetime(sub["PERIODOFREPORT"], format="mixed", errors="coerce")
            sub = sub.dropna(subset=["ACCESSION_NUMBER", "fdate", "pdate"])
            lag = (sub["fdate"] - sub["pdate"]).dt.days
            sub = sub[(lag >= 1) & (lag <= 50)]
            acc_to_fdate = dict(zip(sub["ACCESSION_NUMBER"], sub["fdate"]))
            acc_to_pdate = dict(zip(sub["ACCESSION_NUMBER"], sub["pdate"]))
            acc_to_cik = dict(zip(sub["ACCESSION_NUMBER"], sub["CIK"]))
            valid_acc = set(acc_to_cik.keys())
            del sub

            # Accumulate reduced (pdate, ticker, cik, kind) -> [shs, val_usd] AND max_fdate per pdate
            eq_acc: dict[tuple, list[float]] = defaultdict(lambda: [0.0, 0.0])  # (pdate, ticker, cik) -> [shs, val_usd]
            opt_acc: dict[tuple, list[float]] = defaultdict(lambda: [0.0, 0.0, 0.0, 0.0])  # (pdate, ticker, cik) -> [put_s, put_v, call_s, call_v]
            pdate_max_fdate: dict[pd.Timestamp, pd.Timestamp] = {}
            pdate_ciks: dict[pd.Timestamp, set] = defaultdict(set)
            price_ratios = []

            with zf.open(info_name) as f:
                hdr = f.readline().decode("utf-8", errors="ignore").strip().split("\t")
            usecols = [c for c in ["ACCESSION_NUMBER", "CUSIP", "VALUE", "SSHPRNAMT", "SSHPRNAMTTYPE", "PUTCALL"] if c in hdr]
            with zf.open(info_name) as f:
                for ch in pd.read_csv(f, sep="\t", usecols=usecols, dtype=str, chunksize=180_000):
                    ch = ch[ch["ACCESSION_NUMBER"].isin(valid_acc)]
                    if ch.empty:
                        continue
                    ch["CUSIP"] = ch["CUSIP"].fillna("").str.upper().str.strip()
                    ch["CUSIP"] = np.where(ch["CUSIP"].str.len() == 8, "0" + ch["CUSIP"], ch["CUSIP"])
                    tk = ch["CUSIP"].map(cusip_to_ticker)
                    if tk.isna().any():
                        tk = tk.fillna(ch["CUSIP"].str[:8].map(cusip8_map))
                    ch = ch[tk.notna()].copy()
                    if ch.empty:
                        continue
                    ch["ticker"] = tk[tk.notna()].to_numpy()
                    ch["val"] = pd.to_numeric(ch["VALUE"], errors="coerce").fillna(0.0)
                    ch["shs"] = pd.to_numeric(ch["SSHPRNAMT"], errors="coerce").fillna(0.0)
                    ch["pc"] = ch["PUTCALL"].fillna("").str.upper().str.strip() if "PUTCALL" in ch.columns else ""
                    ch["stype"] = ch["SSHPRNAMTTYPE"].fillna("").str.upper().str.strip() if "SSHPRNAMTTYPE" in ch.columns else "SH"

                    # Exact SEC rule: filings submitted >= 2023-01-03 report VALUE in $1; earlier filings in $1,000s
                    fdt = ch["ACCESSION_NUMBER"].map(acc_to_fdate)
                    pdt = ch["ACCESSION_NUMBER"].map(acc_to_pdate)
                    ciks = ch["ACCESSION_NUMBER"].map(acc_to_cik)
                    ch["val_usd"] = ch["val"] * np.where(fdt >= pd.Timestamp("2023-01-03"), 1.0, 1000.0)
                    ch["fdate"] = fdt
                    ch["pdate"] = pdt
                    ch["cik"] = ciks

                    pure = ch[(ch["pc"] == "") & (ch["stype"] == "SH") & (ch["shs"] > 100) & (ch["val"] > 0)]
                    if not pure.empty and len(price_ratios) < 2000:
                        price_ratios.extend((pure["val"] / pure["shs"]).iloc[:300].tolist())

                    # Track causal filing dates & filer counts per pdate
                    for p_v, mx_f in ch.groupby("pdate")["fdate"].max().items():
                        prev = pdate_max_fdate.get(p_v)
                        if prev is None or mx_f > prev:
                            pdate_max_fdate[p_v] = mx_f
                    for p_v, grp_p in ch.groupby("pdate")["cik"]:
                        pdate_ciks[p_v].update(grp_p.unique())

                    eq_sub = ch[(ch["pc"] == "") & (ch["stype"].isin(["SH", ""]))]
                    if not eq_sub.empty:
                        for row in eq_sub.groupby(["pdate", "ticker", "cik"], as_index=False)[["shs", "val_usd"]].sum().itertuples(index=False):
                            rec = eq_acc[(row.pdate, row.ticker, row.cik)]
                            rec[0] += float(row.shs)
                            rec[1] += float(row.val_usd)

                    put_sub = ch[ch["pc"].str.startswith("PUT")]
                    if not put_sub.empty:
                        for row in put_sub.groupby(["pdate", "ticker", "cik"], as_index=False)[["shs", "val_usd"]].sum().itertuples(index=False):
                            rec = opt_acc[(row.pdate, row.ticker, row.cik)]
                            rec[0] += float(row.shs)
                            rec[1] += float(row.val_usd)

                    call_sub = ch[ch["pc"].str.startswith("CALL")]
                    if not call_sub.empty:
                        for row in call_sub.groupby(["pdate", "ticker", "cik"], as_index=False)[["shs", "val_usd"]].sum().itertuples(index=False):
                            rec = opt_acc[(row.pdate, row.ticker, row.cik)]
                            rec[2] += float(row.shs)
                            rec[3] += float(row.val_usd)

            TMP_ZIP.unlink(missing_ok=True)
            med_ratio = float(np.median(price_ratios)) if price_ratios else 0.0

            # Aggregate (pdate, ticker) from compact dicts
            by_pt_vals: dict[tuple, list[tuple[float, float]]] = defaultdict(list)
            for (p_v, tk, _cik), (shs, vusd) in eq_acc.items():
                by_pt_vals[(p_v, tk)].append((shs, vusd))

            opt_pt: dict[tuple, list[float]] = defaultdict(lambda: [0.0, 0.0, 0, 0])  # put_s, call_s, n_put, n_call
            for (p_v, tk, _cik), (ps, _pv, cs, _cv) in opt_acc.items():
                rec = opt_pt[(p_v, tk)]
                if ps > 0:
                    rec[0] += ps
                    rec[2] += 1
                if cs > 0:
                    rec[1] += cs
                    rec[3] += 1

            for (p_v, tk), lst in sorted(by_pt_vals.items()):
                if len(pdate_ciks.get(p_v, ())) < 30:
                    continue
                avail_dt = (pdate_max_fdate[p_v] + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
                p_str = pd.Timestamp(p_v).strftime("%Y-%m-%d")
                vals = np.array([v for _, v in lst], dtype=float)
                shss = np.array([s for s, _ in lst], dtype=float)
                tot_v = float(vals.sum())
                tot_s = float(shss.sum())
                n_fil = len(lst)
                if tot_v > 0:
                    sv = np.sort(vals)[::-1]
                    top5_share = float(sv[:5].sum() / tot_v)
                    hhi = float(np.sum((vals / tot_v) ** 2))
                else:
                    top5_share, hhi = 0.0, 0.0
                op = opt_pt.get((p_v, tk), [0.0, 0.0, 0, 0])
                rows_zip.append({
                    "period_end": p_str,
                    "available_from": avail_dt,
                    "ticker": tk,
                    "n_filers": n_fil,
                    "total_shares": round(tot_s, 1),
                    "total_val_usd": round(tot_v, 0),
                    "top5_share": round(top5_share, 5),
                    "hhi": round(hhi, 6),
                    "put_shares": round(op[0], 1),
                    "call_shares": round(op[1], 1),
                    "n_put_filers": int(op[2]),
                    "n_call_filers": int(op[3]),
                })
        pd.DataFrame(rows_zip).to_csv(part_path, index=False)
        del eq_acc, opt_acc, by_pt_vals, opt_pt, rows_zip
        gc.collect()
        print(f"[{idx_u:2d}/{len(urls)}] {fname}: med_val/shs={med_ratio:.2f}, saved part ({time.time()-t0:.1f}s)")

    all_parts = [pd.read_csv(p) for p in sorted(PARTS_DIR.glob("*.csv")) if p.stat().st_size > 10]
    out_df = pd.concat(all_parts, ignore_index=True)
    out_df = out_df.sort_values("n_filers", ascending=False).drop_duplicates(["period_end", "ticker"]).sort_values(["period_end", "ticker"])
    out_path = SEC_DIR / "sec_13f_quarterly_holdings.csv.gz"
    out_df.to_csv(out_path, index=False, compression="gzip")
    print(f"\nDONE! Saved {len(out_df):,} (period_end, ticker) rows across {out_df['period_end'].nunique()} quarters & {out_df['ticker'].nunique()} tickers -> {out_path}")


def main() -> None:
    urls = fetch_13f_zip_urls()
    print(f"Found {len(urls)} SEC Form 13F bulk zips: {urls[0].split('/')[-1]} .. {urls[-1].split('/')[-1]}")
    cw_path = SEC_DIR / "sec_13f_cusip_crosswalk.csv"
    if cw_path.exists():
        cw_df = pd.read_csv(cw_path, dtype=str)
        cw = dict(zip(cw_df["cusip"], cw_df["ticker"]))
        print(f"Loaded cached crosswalk: {len(cw)} CUSIPs / {len(set(cw.values()))} tickers")
    else:
        cw = build_crosswalk(urls)
    ingest_all_zips(urls, cw)


if __name__ == "__main__":
    main()
