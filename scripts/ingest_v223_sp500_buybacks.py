import os, json, time, gzip, csv
import pandas as pd
import requests

ROOT = "/tmp/alina_lab"
HDR = {"User-Agent": "ALINA-Research-Lab research@alinaresearch.org"}
SUB_CACHE = "/var/tmp/alina_raw_cache/sec_submissions"
os.makedirs(SUB_CACHE, exist_ok=True)

m = pd.read_csv(f"{ROOT}/data/sec/sp500_2012_2026_cik_map.csv")
# Verify/patch the 3 remaining tickers via cik-lookup-data.txt
patches = {}
with open("/var/tmp/alina_raw_cache/cik-lookup-data.txt", "rb") as f:
    for line in f:
        s = line.decode("latin1").strip()
        if s.startswith("BARD C R INC:") or s.startswith("ENSCO PLC:") or s.startswith("FAMILY DOLLAR STORES INC:"):
            parts = s.rsplit(":", 2)
            if len(parts) == 3 and parts[1].isdigit():
                if "BARD" in parts[0]: patches["BCR-201712"] = (int(parts[1]), parts[0])
                elif "ENSCO" in parts[0]: patches["ESV"] = (int(parts[1]), parts[0])
                elif "FAMILY DOLLAR" in parts[0]: patches["FDO-201507"] = (int(parts[1]), parts[0])
for tk, (ck, nm) in patches.items():
    m.loc[m["ticker"] == tk, ["cik", "source", "sec_name"]] = [ck, "manual_exact", nm]
m.to_csv(f"{ROOT}/data/sec/sp500_2012_2026_cik_map.csv", index=False)
print(f"Map updated: {(m['cik'] > 0).sum()}/{len(m)} mapped", flush=True)

# Load existing buybacks so we don't re-fetch 388 already-pulled CIKs
existing_bb = pd.read_csv(f"{ROOT}/data/sec/sec_buybacks_pit.csv.gz")
have_ciks = set(existing_bb["cik"].astype(int).unique())

# Unique CIKs to pull for S&P 500 full universe (keep ticker -> cik list)
sp_ciks = sorted(set(int(x) for x in m["cik"] if x > 0))
todo = [c for c in sp_ciks if c not in have_ciks]
print(f"Total unique S&P 500 CIKs: {len(sp_ciks)} | Already in sec_buybacks_pit: {len(sp_ciks)-len(todo)} | Todo: {len(todo)}", flush=True)

sess = requests.Session()
sess.headers.update(HDR)

def extract_companyfacts(cik, ticker):
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
    r = sess.get(url, timeout=15)
    if r.status_code != 200:
        return []
    j = r.json()
    facts = j.get("facts", {})
    us = facts.get("us-gaap", {})
    dei = facts.get("dei", {})
    rows = []
    # Buyback cash & shares tags
    for tag, metric in [
        ("PaymentsForRepurchaseOfCommonStock", "bb_cash"),
        ("PaymentsForRepurchaseOfEquity", "bb_cash_eq"),
        ("StockRepurchasedDuringPeriodValue", "bb_val"),
        ("CommonStockSharesOutstanding", "shares"),
        ("WeightedAverageNumberOfDilutedSharesOutstanding", "sh_dil"),
        ("Assets", "assets"),
        ("StockholdersEquity", "equity"),
    ]:
        arr = us.get(tag, {}).get("units", {})
        for unit, items in arr.items():
            if metric in ("bb_cash", "bb_cash_eq", "bb_val", "assets", "equity") and unit != "USD":
                continue
            if metric in ("shares", "sh_dil") and unit != "shares":
                continue
            for it in items:
                filed = it.get("filed", "")
                end = it.get("end", "")
                start = it.get("start", "")
                val = it.get("val")
                form = it.get("form", "")
                if not filed or not end or val is None or form not in ("10-K", "10-Q", "10-K/A", "10-Q/A"):
                    continue
                if end < "2010-01-01":
                    continue
                days = (pd.Timestamp(end) - pd.Timestamp(start)).days if start else 0
                rows.append((cik, ticker, metric, end, start, days, filed, form, float(val)))
    # DEI EntityCommonStockSharesOutstanding
    for unit, items in dei.get("EntityCommonStockSharesOutstanding", {}).get("units", {}).items():
        if unit != "shares": continue
        for it in items:
            filed, end, val, form = it.get("filed", ""), it.get("end", ""), it.get("val"), it.get("form", "")
            if filed and end and val is not None and end >= "2010-01-01" and form in ("10-K", "10-Q", "10-K/A", "10-Q/A"):
                rows.append((cik, ticker, "dei_shares", end, "", 0, filed, form, float(val)))
    return rows

cik_to_tk = m[m["cik"] > 0].drop_duplicates("cik").set_index("cik")["ticker"].to_dict()
new_rows = []
t0 = time.time()
for i, cik in enumerate(todo):
    time.sleep(0.05)
    try:
        new_rows.extend(extract_companyfacts(cik, cik_to_tk.get(cik, str(cik))))
    except Exception:
        pass
    if (i + 1) % 100 == 0 or (i + 1) == len(todo):
        print(f"  companyfacts {i+1}/{len(todo)} ({time.time()-t0:.1f}s), rows={len(new_rows)}", flush=True)

df_new = pd.DataFrame(new_rows, columns=["cik", "ticker", "metric", "end", "start", "days", "filed", "form", "val"])
df_new["source"] = "sp500_full"
# Inspect existing_bb cols to match cleanly
print("existing_bb cols:", list(existing_bb.columns), flush=True)
# Normalize existing_bb + df_new
common_cols = ["cik", "ticker", "metric", "end", "start", "days", "filed", "form", "val"]
for c in common_cols:
    if c not in existing_bb.columns:
        existing_bb[c] = "" if c in ("start", "form") else 0
all_bb = pd.concat([existing_bb[common_cols], df_new[common_cols]], ignore_index=True)
all_bb.drop_duplicates(subset=["cik", "metric", "end", "start", "filed", "val"], inplace=True)
out_path = f"{ROOT}/data/sec/sec_buybacks_sp500_full_pit.csv.gz"
all_bb.to_csv(out_path, index=False, compression="gzip")
print(f"Saved {out_path}: shape={all_bb.shape}, unique_ciks={all_bb['cik'].nunique()}", flush=True)
