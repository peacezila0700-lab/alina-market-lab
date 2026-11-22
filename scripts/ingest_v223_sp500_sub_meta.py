import os, json, time
import pandas as pd
import requests

ROOT = "/tmp/alina_lab"
SUB_CACHE = "/var/tmp/alina_raw_cache/sec_submissions"
os.makedirs(SUB_CACHE, exist_ok=True)
HDR = {"User-Agent": "ALINA-Research-Lab research@alinaresearch.org"}

# 1. Fix column alignment in sec_buybacks_sp500_full_pit.csv.gz cleanly!
raw_full = pd.read_csv(f"{ROOT}/data/sec/sec_buybacks_sp500_full_pit.csv.gz", low_memory=False)
# Notice earlier concatenation put existing_bb into raw_full with tag/val_usd in NaN metric/val rows — easiest: rebuild directly from sec_buybacks_pit + df_new rows already inside raw_full!
ex = pd.read_csv(f"{ROOT}/data/sec/sec_buybacks_pit.csv.gz")
tag_map = {
    "PaymentsForRepurchaseOfCommonStock": "bb_cash",
    "PaymentsForRepurchaseOfEquity": "bb_cash_eq",
    "StockRepurchasedDuringPeriodValue": "bb_val",
    "TreasuryStockValueAcquiredCostMethod": "bb_treas",
    "SHARES_OUT": "shares",
}
ex_norm = pd.DataFrame({
    "cik": ex["cik"].astype(int),
    "ticker": ex["ticker"].astype(str),
    "metric": ex["tag"].map(tag_map).fillna(ex["tag"]),
    "end": ex["end"].astype(str),
    "start": ex["start"].fillna("").astype(str),
    "days": pd.to_numeric(ex["days"], errors="coerce").fillna(0).astype(int),
    "filed": ex["filed"].astype(str),
    "form": ex["form"].fillna("").astype(str),
    "val": pd.to_numeric(ex["val_usd"], errors="coerce"),
})
new_norm = raw_full[raw_full["metric"].notna()][["cik", "ticker", "metric", "end", "start", "days", "filed", "form", "val"]].copy()
new_norm["cik"] = new_norm["cik"].astype(int)
new_norm["val"] = pd.to_numeric(new_norm["val"], errors="coerce")
clean_bb = pd.concat([ex_norm, new_norm], ignore_index=True).dropna(subset=["val"])
clean_bb.drop_duplicates(subset=["cik", "metric", "end", "start", "filed", "val"], inplace=True)
clean_bb.to_csv(f"{ROOT}/data/sec/sec_buybacks_sp500_full_pit.csv.gz", index=False, compression="gzip")
print(f"Normalized sec_buybacks_sp500_full_pit: shape={clean_bb.shape}, ciks={clean_bb['cik'].nunique()}, metrics={clean_bb['metric'].value_counts().to_dict()}", flush=True)

# 2. Fetch base submissions/CIK.json for all 781 S&P 500 CIKs (cached)
m = pd.read_csv(f"{ROOT}/data/sec/sp500_2012_2026_cik_map.csv")
sp_ciks = sorted(set(int(x) for x in m["cik"] if x > 0))
sess = requests.Session()
sess.headers.update(HDR)

meta_rows = []
archive_files = []
t0 = time.time()
fetched = 0
for i, cik in enumerate(sp_ciks):
    p = f"{SUB_CACHE}/CIK{cik:010d}.json"
    j = None
    if os.path.exists(p):
        try: j = json.load(open(p))
        except Exception: j = None
    if j is None:
        time.sleep(0.05)
        try:
            r = sess.get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", timeout=12)
            if r.status_code == 200:
                open(p, "wb").write(r.content)
                j = r.json()
                fetched += 1
        except Exception:
            j = None
    if j:
        rec = j.get("filings", {}).get("recent", {})
        dates = rec.get("filingDate", [])
        min_recent = min(dates) if dates else "9999-99-99"
        files = j.get("filings", {}).get("files", [])
        need_files = [fl["name"] for fl in files if fl.get("filingTo", "0000") >= "2012-01-01"]
        for fn in need_files:
            archive_files.append((cik, fn))
        meta_rows.append({
            "cik": cik,
            "name": j.get("name", ""),
            "sic": str(j.get("sic", "")),
            "sic_desc": j.get("sicDescription", ""),
            "tickers": ",".join([str(x) for x in j.get("tickers", [])]),
            "min_recent_date": min_recent,
            "n_archive_files_2012": len(need_files),
        })
    if (i + 1) % 200 == 0 or (i + 1) == len(sp_ciks):
        print(f"  submissions {i+1}/{len(sp_ciks)} (fetched={fetched}, {time.time()-t0:.1f}s) | archive_files_needed={len(archive_files)}", flush=True)

pd.DataFrame(meta_rows).to_csv(f"{ROOT}/data/sec/sp500_2012_2026_sec_meta.csv", index=False)
json.dump(archive_files, open("/var/tmp/alina_raw_cache/sp500_archive_files_needed.json", "w"))
print(f"Done! Meta rows={len(meta_rows)} | Total archive JSONs >=2012: {len(archive_files)}", flush=True)
