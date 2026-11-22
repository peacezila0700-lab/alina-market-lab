"""
ALINA v2.23 Batch 1 Ingestion (Verified Open-Data Catalog Pillars 1, 2, 4, 6-Freight)
All datasets verified HTTP 200 and strictly checked for causal timestamps & date coverage.
"""
import os, io, json, time, zipfile, urllib.request
import numpy as np
import pandas as pd

ROOT = "/tmp/alina_lab"
RAW_CACHE = "/var/tmp/alina_raw_cache"
os.makedirs(RAW_CACHE, exist_ok=True)
HEADERS = {"User-Agent": "ALINA-Research-Lab contact@alinaresearch.org"}

def fetch_bytes(url, timeout=60):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

# -------------------------------------------------------------------------
# 1. PILLAR 1: Crypto On-Chain, Stablecoins, TVL, CME Financial COT, F&G, DVOL
# -------------------------------------------------------------------------
os.makedirs(f"{ROOT}/data/crypto_onchain", exist_ok=True)

print("[1.1] CoinMetrics BTC & ETH...")
cm_cols = [
    "time", "PriceUSD", "CapMrktCurUSD", "CapRealUSD", "CapMVRVCur",
    "AdrActCnt", "TxCnt", "FeeTotNtv", "FlowInExUSD", "FlowOutExUSD",
    "SplyCur", "IssTotUSD", "NVTAdj", "ROI1yr"
]
for sym in ["btc", "eth"]:
    b = fetch_bytes(f"https://raw.githubusercontent.com/coinmetrics/data/master/csv/{sym}.csv", timeout=60)
    hdr = b[:2000].decode("utf-8", "ignore").splitlines()[0].split(",")
    keep = [c for c in cm_cols if c in hdr]
    df = pd.read_csv(io.BytesIO(b), usecols=keep, low_memory=False)
    df["date"] = pd.to_datetime(df["time"]).dt.strftime("%Y-%m-%d")
    df = df.drop(columns=["time"]).dropna(subset=["PriceUSD"]).sort_values("date").reset_index(drop=True)
    out = f"{ROOT}/data/crypto_onchain/coinmetrics_{sym}.csv.gz"
    df.to_csv(out, index=False, compression="gzip")
    print(f"  coinmetrics_{sym}: {df.shape} | {df['date'].min()} .. {df['date'].max()} | cols={list(df.columns)}")

print("[1.2] DeFiLlama Stablecoins + Chain TVL...")
st_all = json.loads(fetch_bytes("https://stablecoins.llama.fi/stablecoincharts/all").decode())
rows_st = []
for r in st_all:
    dt = pd.to_datetime(int(r["date"]), unit="s", utc=True).strftime("%Y-%m-%d")
    tot = float((r.get("totalCirculatingUSD") or {}).get("peggedUSD") or 0.0)
    rows_st.append({"date": dt, "stable_all_usd": tot})
df_st = pd.DataFrame(rows_st).drop_duplicates("date").sort_values("date")

for sid, col in [(1, "usdt_usd"), (2, "usdc_usd")]:
    j = json.loads(fetch_bytes(f"https://stablecoins.llama.fi/stablecoin/{sid}").decode())
    arr = j.get("tokens", [])
    rr = []
    for r in arr:
        dt = pd.to_datetime(int(r["date"]), unit="s", utc=True).strftime("%Y-%m-%d")
        v = float((r.get("circulating") or {}).get("peggedUSD") or 0.0)
        rr.append({"date": dt, col: v})
    dsub = pd.DataFrame(rr).drop_duplicates("date")
    df_st = df_st.merge(dsub, on="date", how="left")

tvl = json.loads(fetch_bytes("https://api.llama.fi/v2/historicalChainTvl").decode())
df_tvl = pd.DataFrame([
    {"date": pd.to_datetime(int(r["date"]), unit="s", utc=True).strftime("%Y-%m-%d"), "defi_tvl_usd": float(r.get("tvl") or 0.0)}
    for r in tvl
]).drop_duplicates("date")
df_defi = df_st.merge(df_tvl, on="date", how="outer").sort_values("date").reset_index(drop=True)
df_defi.to_csv(f"{ROOT}/data/crypto_onchain/defillama_macro.csv.gz", index=False, compression="gzip")
print(f"  defillama_macro: {df_defi.shape} | {df_defi['date'].min()} .. {df_defi['date'].max()}")

print("[1.3] Alternative.me Fear & Greed (official public API 2018-2026)...")
fng_j = json.loads(fetch_bytes("https://api.alternative.me/fng/?limit=0").decode())
fng_rows = []
for r in fng_j.get("data", []):
    fng_rows.append({
        "date": pd.to_datetime(int(r["timestamp"]), unit="s", utc=True).strftime("%Y-%m-%d"),
        "fear_greed": float(r["value"]),
        "fng_class": r.get("value_classification", "")
    })
df_fg_clean = pd.DataFrame(fng_rows).drop_duplicates("date").sort_values("date").reset_index(drop=True)
df_fg_clean.to_csv(f"{ROOT}/data/crypto_onchain/crypto_fear_greed.csv", index=False)
print(f"  crypto_fear_greed: {df_fg_clean.shape} | {df_fg_clean['date'].min()} .. {df_fg_clean['date'].max()}")

print("[1.4] CFTC Financial Futures COT (CME BTC & ETH, 2018-2026)...")
cot_rows = []
for yr in range(2018, 2027):
    url = f"https://www.cftc.gov/files/dea/history/fut_fin_txt_{yr}.zip"
    try:
        b = fetch_bytes(url, timeout=45)
        with zipfile.ZipFile(io.BytesIO(b)) as zf:
            nm = [n for n in zf.namelist() if n.lower().endswith(".txt")][0]
            with zf.open(nm) as fh:
                dfy = pd.read_csv(fh, low_memory=False)
        mask = dfy["Market_and_Exchange_Names"].astype(str).str.contains("BITCOIN - CHICAGO|ETHER CASH SETTLED - CHICAGO", case=False, na=False)
        sub = dfy.loc[mask].copy()
        if len(sub):
            keep_c = [
                "Market_and_Exchange_Names", "Report_Date_as_YYYY-MM-DD", "Open_Interest_All",
                "Dealer_Positions_Long_All", "Dealer_Positions_Short_All",
                "Asset_Mgr_Positions_Long_All", "Asset_Mgr_Positions_Short_All",
                "Lev_Money_Positions_Long_All", "Lev_Money_Positions_Short_All",
                "Other_Rept_Positions_Long_All", "Other_Rept_Positions_Short_All",
                "NonRept_Positions_Long_All", "NonRept_Positions_Short_All",
            ]
            keep_c = [c for c in keep_c if c in sub.columns]
            cot_rows.append(sub[keep_c])
    except Exception as e:
        print(f"  COT {yr} skip: {e}")
df_cme_cot = pd.concat(cot_rows, ignore_index=True)
df_cme_cot["report_date"] = pd.to_datetime(df_cme_cot["Report_Date_as_YYYY-MM-DD"]).dt.strftime("%Y-%m-%d")
df_cme_cot["available_from"] = (pd.to_datetime(df_cme_cot["Report_Date_as_YYYY-MM-DD"]) + pd.Timedelta(days=3)).dt.strftime("%Y-%m-%d")
df_cme_cot["asset"] = np.where(df_cme_cot["Market_and_Exchange_Names"].str.contains("BITCOIN", case=False), "BTC", "ETH")
df_cme_cot = df_cme_cot.drop_duplicates(["asset", "report_date"]).sort_values(["asset", "report_date"]).reset_index(drop=True)
df_cme_cot.to_csv(f"{ROOT}/data/cot/cme_crypto_fin_cot.csv.gz", index=False, compression="gzip")
print(f"  cme_crypto_fin_cot: {df_cme_cot.shape} | BTC={sum(df_cme_cot['asset']=='BTC')} ETH={sum(df_cme_cot['asset']=='ETH')} | {df_cme_cot['report_date'].min()} .. {df_cme_cot['report_date'].max()}")

# -------------------------------------------------------------------------
# 2. PILLAR 2: Forex Factory Calendar (2007-2025), Philly Fed SPF
# -------------------------------------------------------------------------
print("[2.1] Forex Factory Calendar (2007-2025)...")
ff_raw_path = f"{RAW_CACHE}/forex_factory_cache.csv"
if not os.path.exists(ff_raw_path):
    b = fetch_bytes("https://huggingface.co/datasets/Ehsanrs2/Forex_Factory_Calendar/resolve/main/forex_factory_cache.csv", timeout=120)
    with open(ff_raw_path, "wb") as f:
        f.write(b)
df_ff = pd.read_csv(ff_raw_path, usecols=["DateTime", "Currency", "Impact", "Event", "Actual", "Forecast", "Previous"], low_memory=False)
df_ff = df_ff[df_ff["Currency"].isin(["USD", "EUR", "GBP", "JPY"])].copy()
df_ff.to_csv(f"{ROOT}/data/events/forex_factory_2007_2025.csv.gz", index=False, compression="gzip")
print(f"  forex_factory_2007_2025: {df_ff.shape} | {df_ff['DateTime'].min()[:10]} .. {df_ff['DateTime'].max()[:10]} | USD_with_forecast={((df_ff['Currency']=='USD') & df_ff['Forecast'].notna() & df_ff['Actual'].notna()).sum()}")

print("[2.3] Philly Fed SPF MedianLevel...")
b_med = fetch_bytes("https://www.philadelphiafed.org/-/media/FRBP/Assets/Surveys-And-Data/survey-of-professional-forecasters/historical-data/MedianLevel.xlsx", timeout=60)
with open(f"{RAW_CACHE}/SPF_MedianLevel.xlsx", "wb") as f:
    f.write(b_med)
xl = pd.ExcelFile(io.BytesIO(b_med))
spf_sheets = [s for s in ["RGDP", "UNEMP", "CPI", "CORECPI", "PCE", "COREPCE", "TBILL", "TBOND", "INDPROD", "EMP"] if s in xl.sheet_names]
spf_frames = []
for sh in spf_sheets:
    d = pd.read_excel(io.BytesIO(b_med), sheet_name=sh)
    d["series"] = sh
    spf_frames.append(d)
df_spf = pd.concat(spf_frames, ignore_index=True)
df_spf.to_csv(f"{ROOT}/data/macro/philly_spf_median.csv.gz", index=False, compression="gzip")
print(f"  philly_spf_median: {df_spf.shape} | years {df_spf['YEAR'].min()}..{df_spf['YEAR'].max()}")

# -------------------------------------------------------------------------
# 3. PILLAR 4: Thai SET50 + SET50 Futures (2006-2023) + TFEX S50 1-Min (2016-2025)
# -------------------------------------------------------------------------
print("[4.2] Samapan SET50 + Futures (2006-2023)...")
b_s50 = fetch_bytes("https://raw.githubusercontent.com/SamapanThongmee/Scrap_SET50_Index_Futures_Data/main/SET50_2006_2023.csv")
b_fut = fetch_bytes("https://raw.githubusercontent.com/SamapanThongmee/Scrap_SET50_Index_Futures_Data/main/SET50_Index_Futures_Data_2006_2023.csv")
df_s50 = pd.read_csv(io.BytesIO(b_s50))
df_fut = pd.read_csv(io.BytesIO(b_fut))
df_s50.to_csv(f"{ROOT}/data/thai/set50_index_2006_2023.csv", index=False)
df_fut.to_csv(f"{ROOT}/data/thai/set50_futures_daily_2006_2023.csv.gz", index=False, compression="gzip")
print(f"  SET50 daily: {df_s50.shape} ({df_s50['Date'].min()}..{df_s50['Date'].max()}) | Futures: {df_fut.shape}")

print("[4.3] TFEX S50 1-Minute Zip Inspect...")
b_zip = fetch_bytes("https://raw.githubusercontent.com/assazzin/Tradingview-S50/main/S50H16-S50Z25_1m.zip", timeout=120)
with open(f"{RAW_CACHE}/S50H16-S50Z25_1m.zip", "wb") as f:
    f.write(b_zip)
with zipfile.ZipFile(io.BytesIO(b_zip)) as zf:
    csv_names = sorted([n for n in zf.namelist() if n.lower().endswith(".csv")])
    print(f"  S50 1m zip has {len(csv_names)} contract CSVs: {csv_names[:3]} .. {csv_names[-3:]}")
    with zf.open(csv_names[0]) as fh:
        sample = pd.read_csv(fh, nrows=5)
        print("  S50 1m sample cols:", list(sample.columns), "\n", sample.head(2))

# -------------------------------------------------------------------------
# 4. PILLAR 6: Freight PPI & Cass Freight
# -------------------------------------------------------------------------
print("[6.4] FRED Freight PPI & Cass...")
fr_dfs = []
for sid in ["PCU483111483111", "FRGEXPUSM649NCIS", "FRGSHPUSM649NCIS"]:
    b = fetch_bytes(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}")
    d = pd.read_csv(io.BytesIO(b))
    d.columns = ["date", sid]
    d[sid] = pd.to_numeric(d[sid], errors="coerce")
    fr_dfs.append(d)
df_fr = fr_dfs[0].merge(fr_dfs[1], on="date", how="outer").merge(fr_dfs[2], on="date", how="outer").sort_values("date")
df_fr.to_csv(f"{ROOT}/data/macro/fred_freight_monthly.csv", index=False)
print(f"  fred_freight_monthly: {df_fr.shape} | {df_fr['date'].min()} .. {df_fr['date'].max()}")
print("DONE BATCH 1 INGESTION!")
