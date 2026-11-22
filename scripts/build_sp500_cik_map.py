import json, re, time, os
import pandas as pd
import requests
from io import StringIO

ROOT = "/tmp/alina_lab"
JB = "/var/tmp/alina_raw_cache/johnbrick_sp500"
SUB_CACHE = "/var/tmp/alina_raw_cache/sec_submissions"
os.makedirs(SUB_CACHE, exist_ok=True)
HDR = {"User-Agent": "ALINA-Research-Lab research@alinaresearch.org"}

mi = pd.read_parquet(f"{JB}/membership_intervals.parquet")
mi["end_dt"] = pd.to_datetime(mi["end"]).fillna(pd.Timestamp("2026-12-31"))
mi["start_dt"] = pd.to_datetime(mi["start"])
sp_2012 = mi[mi["end_dt"] >= "2012-01-01"].copy()
sp_grp = sp_2012.groupby("ticker", as_index=False).agg(start=("start_dt", "min"), end=("end_dt", "max"))
print(f"Loaded sp_grp: {len(sp_grp)} tickers", flush=True)

cmap = {}
for fn, tkc, cikc in [
    ("company_tickers.csv", "ticker", "cik"),
    ("sp500_earnings_transcript_features_2013_2025.csv.gz", "ticker", "cik"),
    ("delisted_pit_meta.csv", "ticker", "cik"),
    ("universe_pit_meta.csv", "ticker", "cik"),
]:
    d = pd.read_csv(f"{ROOT}/data/sec/{fn}", usecols=[tkc, cikc]).dropna()
    for t, c in zip(d[tkc].astype(str).str.upper(), d[cikc].astype(int)):
        if c > 0:
            cmap[t] = c
            cmap[t.replace("-", ".")] = c
            cmap[t.replace(".", "-")] = c
nd = json.load(open(f"{ROOT}/data/sec/new_delisted_cik_map.json"))
for t, arr in nd.items():
    if arr:
        cmap[t.upper()] = int(arr[0])

html = requests.get("https://en.wikipedia.org/w/index.php?title=List_of_S%26P_500_companies&oldid=1292523673", headers={"User-Agent": "ALINA/1.0"}, timeout=20).text
tbls = pd.read_html(StringIO(html))
wiki_name = {}
for _, r in tbls[0].iterrows():
    wiki_name[str(r["Symbol"]).strip().upper()] = str(r["Security"]).strip()
chg = tbls[1]
chg.columns = ["_".join([str(x) for x in c]) for c in chg.columns]
for _, r in chg.iterrows():
    for tc, nc in [("Added_Ticker", "Added_Security"), ("Removed_Ticker", "Removed_Security")]:
        tk = str(r[tc]).strip().upper()
        nm = str(r[nc]).strip()
        if tk and tk != "NAN" and nm and nm != "NAN":
            wiki_name.setdefault(tk, nm)

def norm(s):
    s = s.upper()
    s = re.sub(r"\([^)]*\)", " ", s)
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    for w in ["INC", "CORP", "CORPORATION", "CO", "COMPANY", "LTD", "PLC", "HOLDINGS", "GROUP", "THE", "OF", "DE", "DEL", "PA", "NEW", "SA", "NV", "CLASS", "A", "B", "C"]:
        s = re.sub(rf"\b{w}\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()

name_to_ciks = {}
with open("/var/tmp/alina_raw_cache/cik-lookup-data.txt", "rb") as f:
    for line in f:
        s = line.decode("latin1").strip()
        parts = s.rsplit(":", 2)
        if len(parts) == 3 and parts[1].isdigit():
            nm = norm(parts[0])
            if nm:
                name_to_ciks.setdefault(nm, []).append((int(parts[1]), parts[0]))
print("Parsed cik-lookup-data:", len(name_to_ciks), "unique names", flush=True)

MANUAL_NAME_HINTS = {
    "AABA": "ALTABA", "AIRC": "APARTMENT INCOME REIT", "ANRZQ": "ALPHA NATURAL RESOURCES",
    "ATGE": "ADTALEM GLOBAL EDUCATION", "BCR": "BARD C R", "BTUUQ": "PEABODY ENERGY",
    "CA": "CA", "CMCSK": "COMCAST", "HAR": "HARMAN INTERNATIONAL INDUSTRIES",
    "HNZ": "HEINZ H J", "HOT": "STARWOOD HOTELS", "HSH": "HILLSHIRE BRANDS",
    "JCP": "PENNEY J C", "LLTC": "LINEAR TECHNOLOGY", "LXK": "LEXMARK INTERNATIONAL",
    "MJN": "MEAD JOHNSON NUTRITION", "MWV": "MEADWESTVACO", "RRD": "DONNELLEY R R",
    "TSS": "TOTAL SYSTEM SERVICES", "WIN": "WINDSTREAM", "WRK": "WESTROCK",
    "WYND": "WYNDHAM DESTINATIONS", "CBE": "COOPER INDUSTRIES", "DO": "DIAMOND OFFSHORE DRILLING",
}

sess = requests.Session()
sess.headers.update(HDR)

def get_sub(cik):
    p = f"{SUB_CACHE}/CIK{cik:010d}.json"
    if os.path.exists(p):
        try: return json.load(open(p))
        except Exception: pass
    time.sleep(0.05)
    r = sess.get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", timeout=10)
    if r.status_code == 200:
        open(p, "wb").write(r.content)
        return r.json()
    return None

def verify_cands(cands, ticker_base, start_dt, end_dt):
    best, best_score = None, -1
    for cik, raw_nm in cands[:3]:
        j = get_sub(cik)
        if not j: continue
        rec = j.get("filings", {}).get("recent", {})
        forms = rec.get("form", [])
        dates = rec.get("filingDate", [])
        files = j.get("filings", {}).get("files", [])
        tks = [str(x).upper() for x in j.get("tickers", [])]
        if not (any(f in ("10-K", "10-Q", "8-K") for f in forms) or len(files) > 0):
            continue
        all_d = list(dates) + [fl.get("filingFrom") for fl in files if fl.get("filingFrom")] + [fl.get("filingTo") for fl in files if fl.get("filingTo")]
        if not all_d: continue
        dmin, dmax = pd.Timestamp(min(all_d)), pd.Timestamp(max(all_d))
        overlap = (dmax >= start_dt - pd.Timedelta(days=365)) and (dmin <= end_dt + pd.Timedelta(days=365))
        sc = (10 if ticker_base in tks else 0) + (5 if overlap else 0) + (2 if any(f == "10-K" for f in forms) else 0)
        if sc > best_score:
            best_score = sc
            best = (cik, j.get("name", raw_nm))
    return best

rows = []
for idx, r in sp_grp.iterrows():
    tk = r["ticker"].upper()
    base = tk.split("-")[0]
    src, cik, sec_name = "direct", None, ""
    if base in MANUAL_NAME_HINTS and (base not in cmap or base in ("CBE", "DO", "CA")):
        hint = MANUAL_NAME_HINTS[base]
        cands = name_to_ciks.get(norm(hint), [])
        if not cands:
            cands = [v for k, vs in name_to_ciks.items() if k.startswith(norm(hint)) for v in vs]
        if len(cands) == 1:
            cik, sec_name = cands[0]
            src = "manual_1"
        elif cands:
            v = verify_cands(cands, base, r["start"], r["end"])
            if v: cik, sec_name = v; src = "manual_verified"
    elif tk in cmap:
        cik = cmap[tk]
    elif base in cmap and ("-" not in tk or len(tk.split("-")[1]) == 1):
        cik = cmap[base]
    elif "-" in tk and len(tk.split("-")[1]) == 6:
        wname = wiki_name.get(base, "")
        cands = name_to_ciks.get(norm(wname), []) if wname else []
        if len(cands) == 1:
            cik, sec_name = cands[0]; src = "wiki_1"
        elif len(cands) > 1:
            v = verify_cands(cands, base, r["start"], r["end"])
            if v: cik, sec_name = v; src = "wiki_verified"
        if cik is None and base in cmap:
            cik = cmap[base]; src = "base_cmap"
    else:
        hint = MANUAL_NAME_HINTS.get(base) or wiki_name.get(base, "")
        if hint:
            cands = name_to_ciks.get(norm(hint), [])
            if not cands:
                cands = [v for k, vs in name_to_ciks.items() if k.startswith(norm(hint)) for v in vs]
            if len(cands) == 1:
                cik, sec_name = cands[0]; src = "wiki_1"
            elif cands:
                v = verify_cands(cands, base, r["start"], r["end"])
                if v: cik, sec_name = v; src = "wiki_verified"
    rows.append({
        "ticker": tk, "base_sym": base, "cik": int(cik) if cik else 0,
        "start": r["start"].strftime("%Y-%m-%d"), "end": r["end"].strftime("%Y-%m-%d"),
        "source": src if cik else "UNMAPPED", "sec_name": sec_name
    })

out = pd.DataFrame(rows)
out.to_csv(f"{ROOT}/data/sec/sp500_2012_2026_cik_map.csv", index=False)
mapped = (out["cik"] > 0).sum()
print(f"Total 2012-2026 S&P 500 tickers: {len(out)} | Mapped: {mapped} ({mapped/len(out)*100:.1f}%)", flush=True)
print("Sources:", out["source"].value_counts().to_dict(), flush=True)
unm = out[out["cik"] == 0]
print("Unmapped:", unm["ticker"].tolist(), flush=True)
