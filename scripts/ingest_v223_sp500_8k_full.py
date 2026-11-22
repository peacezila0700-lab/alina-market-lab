import os, json, time
import pandas as pd
import requests

ROOT = "/tmp/alina_lab"
SUB_CACHE = "/var/tmp/alina_raw_cache/sec_submissions"
ARC_CACHE = "/var/tmp/alina_raw_cache/sec_sub_archives"
os.makedirs(ARC_CACHE, exist_ok=True)
HDR = {"User-Agent": "ALINA-Research-Lab research@alinaresearch.org"}

# 1. Clean placeholder metric=='0' from sec_buybacks_sp500_full_pit.csv.gz
bb = pd.read_csv(f"{ROOT}/data/sec/sec_buybacks_sp500_full_pit.csv.gz", low_memory=False)
bb = bb[bb["metric"].astype(str) != "0"].copy()
bb.to_csv(f"{ROOT}/data/sec/sec_buybacks_sp500_full_pit.csv.gz", index=False, compression="gzip")
print(f"Cleaned sec_buybacks_sp500_full_pit: {bb.shape}, metrics={bb['metric'].value_counts().to_dict()}", flush=True)

# 2. Fetch archive files + extract ALL 8-Ks >= 2012-01-01 for all 781 S&P 500 CIKs
m = pd.read_csv(f"{ROOT}/data/sec/sp500_2012_2026_cik_map.csv")
sp_ciks = sorted(set(int(x) for x in m["cik"] if x > 0))
cik_to_tk = m[m["cik"] > 0].drop_duplicates("cik").set_index("cik")["ticker"].to_dict()

archive_files = json.load(open("/var/tmp/alina_raw_cache/sp500_archive_files_needed.json"))
sess = requests.Session()
sess.headers.update(HDR)

t0 = time.time()
fetched = 0
for idx, (cik, fn) in enumerate(archive_files):
    p = f"{ARC_CACHE}/{fn}"
    if not os.path.exists(p):
        time.sleep(0.05)
        try:
            r = sess.get(f"https://data.sec.gov/submissions/{fn}", timeout=15)
            if r.status_code == 200:
                open(p, "wb").write(r.content)
                fetched += 1
        except Exception:
            pass
    if (idx + 1) % 200 == 0 or (idx + 1) == len(archive_files):
        print(f"  archives {idx+1}/{len(archive_files)} (fetched={fetched}, {time.time()-t0:.1f}s)", flush=True)

def extract_8k_from_rec(cik, tk, rec, seen):
    rows = []
    forms = rec.get("form", [])
    dates = rec.get("filingDate", [])
    acc = rec.get("accessionNumber", [])
    items = rec.get("items", [])
    rep_dates = rec.get("reportDate", [])
    for i, fm in enumerate(forms):
        if fm not in ("8-K", "8-K/A"):
            continue
        fd = dates[i] if i < len(dates) else ""
        if fd < "2012-01-01":
            continue
        an = acc[i] if i < len(acc) else ""
        if an in seen:
            continue
        seen.add(an)
        it = items[i] if i < len(items) else ""
        if isinstance(it, list):
            it = ",".join(str(x) for x in it)
        rd = rep_dates[i] if i < len(rep_dates) else ""
        rows.append((cik, tk, fm, fd, rd, str(it), an))
    return rows

arc_by_cik = {}
for cik, fn in archive_files:
    arc_by_cik.setdefault(cik, []).append(fn)

all_8k = []
for cik in sp_ciks:
    tk = cik_to_tk.get(cik, str(cik))
    seen = set()
    p = f"{SUB_CACHE}/CIK{cik:010d}.json"
    if os.path.exists(p):
        try:
            j = json.load(open(p))
            all_8k.extend(extract_8k_from_rec(cik, tk, j.get("filings", {}).get("recent", {}), seen))
        except Exception:
            pass
    for fn in arc_by_cik.get(cik, []):
        ap = f"{ARC_CACHE}/{fn}"
        if os.path.exists(ap):
            try:
                aj = json.load(open(ap))
                all_8k.extend(extract_8k_from_rec(cik, tk, aj, seen))
            except Exception:
                pass

df_8k = pd.DataFrame(all_8k, columns=["cik", "ticker", "form", "filing_date", "report_date", "items", "accession"])
out_8k = f"{ROOT}/data/sec/sec_8k_sp500_full_pit.csv.gz"
df_8k.to_csv(out_8k, index=False, compression="gzip")
df_8k["yr"] = df_8k["filing_date"].str[:4]
has_502 = df_8k[df_8k["items"].str.contains("5.02", na=False)]
print(f"Saved {out_8k}: rows={len(df_8k)}, ciks={df_8k['cik'].nunique()}, Item5.02={len(has_502)}", flush=True)
print("Item 5.02 by year:", has_502["yr"].value_counts().sort_index().to_dict(), flush=True)
