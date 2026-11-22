"""
ALINA v2.23 Batch 2 Ingestion:
1. glopardo/sp500-earnings-transcripts (all 3 Parquet shards = 20,681 calls across 496 S&P500 firms, 2013Q2-2025Q1)
   -> extracts Loughran-McDonald finance NLP metrics + Prepared vs Q&A split + causal dates into <2MB CSV.GZ!
2. SEC EDGAR per-CIK XBRL Buybacks & 8-K Events (388 active+delisted PIT firms via data.sec.gov, 9 req/s)
   -> saves sec_buybacks_pit.csv.gz & sec_8k_events_pit.csv.gz without downloading 3GB bulk zips.
"""
import os, re, gc, json, time, requests
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = "/tmp/alina_lab"
RAW = "/var/tmp/alina_raw_cache"
os.makedirs(RAW, exist_ok=True)
SEC_HEADERS = {"User-Agent": "ALINA-Research-Lab research@alinaresearch.org", "Accept-Encoding": "gzip, deflate"}

# -------------------------------------------------------------------------
# PART 1: S&P 500 Earnings Call Transcripts NLP Feature Extraction
# -------------------------------------------------------------------------
# Compact standard Loughran-McDonald Finance Sentiment Word Sets
LM_POS = {
    "achieve","achieved","achievement","achievements","advantage","advantages","beneficial","benefit","benefits",
    "best","better","bolster","boom","booming","boost","boosted","breakthrough","confident","constructive",
    "creative","delighted","deliver","delivered","delivering","efficiency","efficient","empower","enable",
    "encourage","encouraged","encouraging","enhance","enhanced","enhancement","enjoy","enthusiastic","exceed",
    "exceeded","exceeding","excellent","exceptional","excited","exciting","expand","expanded","expanding",
    "expansion","favorable","gain","gained","gains","good","great","greater","greatest","grow","growing",
    "growth","healthy","high","higher","highest","improve","improved","improvement","improvements","improving",
    "increase","increased","increases","increasing","innovation","innovative","leader","leadership","leading",
    "momentum","opportunity","opportunities","optimal","optimistic","outperform","outperformed","positive",
    "positively","profit","profitability","profitable","progress","progressing","prosper","rebound","record",
    "recover","recovery","resilient","resilience","rewarding","solid","strength","strengthen","strengthened",
    "strong","stronger","strongest","succeed","success","successful","successfully","superior","surpass",
    "surpassed","tremendous","upside","upturn","valuable","victory","win","winning","wins"
}
LM_NEG = {
    "abandon","abandoned","adverse","adversely","against","allegation","allegations","bad","bankrupt",
    "bankruptcy","barrier","barriers","burden","catastrophe","caution","cautious","challenge","challenged",
    "challenges","challenging","closure","collapse","concern","concerned","concerns","conflict","constrain",
    "constrained","constraint","constraints","contraction","costly","crisis","critical","cut","cuts","damage",
    "damaged","danger","decline","declined","declines","declining","decrease","decreased","default","defect",
    "deficit","delay","delayed","delays","deteriorate","deteriorated","deteriorating","deterioration",
    "difficult","difficulties","difficulty","disappoint","disappointed","disappointing","disappointment",
    "disruption","disruptions","doubt","downgrade","downturn","drop","dropped","erosion","fail","failed",
    "failing","failure","fall","falling","fear","force","fraud","headwind","headwinds","hurt","impair",
    "impaired","impairment","inability","inadequate","inflationary","lawsuit","layoff","layoffs","litigation",
    "lose","losing","loss","losses","lost","lower","miss","missed","negative","negatively","obstacle",
    "obstacles","penalty","poor","poorly","pressure","pressures","problem","problems","recession","reduce",
    "reduced","reduction","restructuring","risk","risks","risky","severe","severely","shortage","shortages",
    "shortfall","shrink","shrinking","slow","slowdown","slowed","slower","slowing","sluggish","slump",
    "soft","soften","softened","softness","strain","stress","suffer","suffered","threat","turmoil","unable",
    "uncertain","uncertainty","unfavorable","unforeseen","volatile","volatility","weak","weaken","weakened",
    "weakness","worse","worsen","worsened","worsening","worst","writedown","writeoff"
}
LM_UNC = {
    "ambiguous","approximate","approximately","assume","assumption","assumptions","believe","cautious",
    "could","depend","depends","dependent","doubt","estimate","estimated","estimates","expect","fluctuate",
    "fluctuation","fluctuations","forecast","indefinite","likely","may","might","nearly","pending","perhaps",
    "possible","possibly","predict","predicted","preliminary","probable","probably","projected","projection",
    "random","risk","risks","rough","roughly","seem","seems","sometimes","somewhat","speculate","speculation",
    "suggest","tentative","uncertain","uncertainties","uncertainty","unclear","unknown","unpredictable",
    "unproven","unspecified","variable","vary","volatility"
}
BUYBACK_RE = re.compile(r"\b(repurchase|repurchases|repurchased|buyback|buybacks|share\s+retirement)\b")
GUIDE_UP_RE = re.compile(r"\b(rais(?:e|ed|ing)\s+(?:our\s+)?(?:guidance|outlook|forecast)|above\s+(?:our\s+)?expectations)\b")
GUIDE_DN_RE = re.compile(r"\b(lower(?:ed|ing)?\s+(?:our\s+)?(?:guidance|outlook|forecast)|cut(?:ting)?\s+(?:our\s+)?(?:guidance|outlook)|below\s+expectations)\b")
QA_SPLIT_RE = re.compile(r"question[-\s]and[-\s]answer", re.IGNORECASE)
WORD_RE = re.compile(r"[a-z]+")

def score_text(txt):
    if not isinstance(txt, str) or len(txt) < 50:
        return 0, 0, 0, 0, 0, 0, 0, 0, 0.0, 0.0
    low = txt.lower()
    m_qa = QA_SPLIT_RE.search(low)
    prep = low[:m_qa.start()] if m_qa else low
    qa = low[m_qa.end():] if m_qa else ""

    words_all = WORD_RE.findall(low)
    n_words = len(words_all)
    pos = sum(1 for w in words_all if w in LM_POS)
    neg = sum(1 for w in words_all if w in LM_NEG)
    unc = sum(1 for w in words_all if w in LM_UNC)
    bb = len(BUYBACK_RE.findall(low))
    gu = len(GUIDE_UP_RE.findall(low))
    gd = len(GUIDE_DN_RE.findall(low))

    # Prepared vs Q&A net sentiment
    pw = WORD_RE.findall(prep)
    prep_tone = (sum(1 for w in pw if w in LM_POS) - sum(1 for w in pw if w in LM_NEG)) / max(1, len(pw)) * 100.0
    if qa:
        qw = WORD_RE.findall(qa)
        qa_tone = (sum(1 for w in qw if w in LM_POS) - sum(1 for w in qw if w in LM_NEG)) / max(1, len(qw)) * 100.0
    else:
        qa_tone = prep_tone
    return n_words, pos, neg, unc, bb, gu, gd, int(bool(qa)), round(prep_tone, 4), round(qa_tone, 4)

tr_feats = []
shard_urls = [
    ("glopardo_0.parquet", "https://huggingface.co/datasets/glopardo/sp500-earnings-transcripts/resolve/main/data/train-00000-of-00003.parquet"),
    ("glopardo_1.parquet", "https://huggingface.co/datasets/glopardo/sp500-earnings-transcripts/resolve/main/data/train-00001-of-00003.parquet"),
    ("glopardo_2.parquet", "https://huggingface.co/datasets/glopardo/sp500-earnings-transcripts/resolve/main/data/train-00002-of-00003.parquet"),
]
print("=== PART 1: Downloading & scoring glopardo S&P 500 Earnings Transcripts (3 shards) ===")
out_tr = f"{ROOT}/data/sec/sp500_earnings_transcript_features_2013_2025.csv.gz"
if os.path.exists(out_tr) and os.path.getsize(out_tr) > 100_000:
    df_tr = pd.read_csv(out_tr)
    print(f"Loaded existing {out_tr}: {df_tr.shape}", flush=True)
else:
    for fn, url in shard_urls:
        lp = f"{RAW}/{fn}"
        if not os.path.exists(lp) or os.path.getsize(lp) < 100_000_000:
            print(f"  Fetching {fn}...", flush=True)
            with requests.get(url, stream=True, timeout=180) as r:
                r.raise_for_status()
                with open(lp, "wb") as f:
                    for ch in r.iter_content(1 << 20):
                        if ch:
                            f.write(ch)
        df_s = pd.read_parquet(lp, columns=["ticker", "cik", "sector", "year", "quarter", "earnings_date", "transcript"])
        rows_out = []
        for _, r in df_s.iterrows():
            nw, pos, neg, unc, bb, gu, gd, has_qa, pt, qt = score_text(r["transcript"])
            net_tone = (pos - neg) / max(1, pos + neg)
            unc_pct = unc / max(1, nw) * 100.0
            rows_out.append({
                "ticker": str(r["ticker"]).upper(),
                "cik": int(r["cik"]) if pd.notna(r["cik"]) else -1,
                "sector": r["sector"],
                "year": r["year"],
                "quarter": r["quarter"],
                "earnings_date": str(r["earnings_date"])[:10],
                "n_words": nw,
                "pos_cnt": pos,
                "neg_cnt": neg,
                "unc_cnt": unc,
                "net_tone": round(net_tone, 4),
                "unc_pct": round(unc_pct, 4),
                "prep_tone": pt,
                "qa_tone": qt,
                "qa_minus_prep": round(qt - pt, 4),
                "has_qa": has_qa,
                "buyback_mentions": bb,
                "guide_up": gu,
                "guide_dn": gd,
            })
        tr_feats.append(pd.DataFrame(rows_out))
        print(f"  Scored {fn}: {len(rows_out)} transcripts", flush=True)
        del df_s, rows_out
        gc.collect()

    df_tr = pd.concat(tr_feats, ignore_index=True).sort_values(["ticker", "earnings_date"]).reset_index(drop=True)
    df_tr.to_csv(out_tr, index=False, compression="gzip")
    print(f"Saved {out_tr}: {df_tr.shape} | {df_tr['earnings_date'].min()} .. {df_tr['earnings_date'].max()} | firms={df_tr['ticker'].nunique()}", flush=True)

# -------------------------------------------------------------------------
# PART 2: SEC EDGAR Per-CIK Buybacks (XBRL) + 8-K Events (388 Active+Delisted Firms)
# -------------------------------------------------------------------------
u_act = pd.read_csv(f"{ROOT}/data/sec/universe_pit_meta.csv", usecols=["cik", "ticker"])
u_del = pd.read_csv(f"{ROOT}/data/sec/delisted_pit_meta.csv", usecols=["cik", "ticker"])
u_act["is_delisted"] = False
u_del["is_delisted"] = True
univ = pd.concat([u_act, u_del], ignore_index=True).drop_duplicates("cik").reset_index(drop=True)
print(f"\n=== PART 2: SEC EDGAR Per-CIK Buybacks & 8-K Events ({len(univ)} CIKs) ===")

BUYBACK_TAGS = [
    "PaymentsForRepurchaseOfCommonStock",
    "PaymentsForRepurchaseOfEquity",
    "StockRepurchasedDuringPeriodValue",
    "TreasuryStockValueAcquiredCostMethod",
]
SHARES_TAGS = ["CommonStockSharesOutstanding", "EntityCommonStockSharesOutstanding"]

bb_rows = []
ev8k_rows = []
session = requests.Session()
session.headers.update(SEC_HEADERS)

for idx, row in univ.iterrows():
    cik = int(row["cik"])
    tk = str(row["ticker"]).upper()
    is_del = bool(row["is_delisted"])
    cik10 = f"{cik:010d}"

    # 2a. XBRL CompanyFacts -> Buybacks & Shares
    try:
        r = session.get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json", timeout=15)
        if r.status_code == 200:
            j = r.json()
            us_gaap = j.get("facts", {}).get("us-gaap", {})
            dei = j.get("facts", {}).get("dei", {})
            for tag in BUYBACK_TAGS:
                if tag in us_gaap:
                    for item in us_gaap[tag].get("units", {}).get("USD", []):
                        # Filter single-quarter or annual/YTD cleanly using start..end length
                        s_dt = item.get("start")
                        e_dt = item.get("end")
                        f_dt = item.get("filed")
                        val = item.get("val")
                        if s_dt and e_dt and f_dt and val is not None:
                            days = (pd.Timestamp(e_dt) - pd.Timestamp(s_dt)).days
                            if 70 <= days <= 380:
                                bb_rows.append({
                                    "cik": cik, "ticker": tk, "is_delisted": is_del,
                                    "tag": tag, "start": s_dt, "end": e_dt, "days": days,
                                    "filed": f_dt, "val_usd": float(val),
                                    "form": item.get("form", "")
                                })
                    break  # prefer primary tag found first
            for tag in SHARES_TAGS:
                src = dei if tag in dei else us_gaap
                if tag in src:
                    for item in src[tag].get("units", {}).get("shares", []):
                        e_dt = item.get("end")
                        f_dt = item.get("filed")
                        val = item.get("val")
                        if e_dt and f_dt and val is not None and val > 0:
                            bb_rows.append({
                                "cik": cik, "ticker": tk, "is_delisted": is_del,
                                "tag": "SHARES_OUT", "start": e_dt, "end": e_dt, "days": 0,
                                "filed": f_dt, "val_usd": float(val),
                                "form": item.get("form", "")
                            })
                    break
    except Exception:
        pass
    time.sleep(0.04)

    # 2b. Submissions -> 8-K filings with exact acceptanceDateTime & items
    try:
        r2 = session.get(f"https://data.sec.gov/submissions/CIK{cik10}.json", timeout=15)
        if r2.status_code == 200:
            rec = r2.json().get("filings", {}).get("recent", {})
            forms = rec.get("form", [])
            fdates = rec.get("filingDate", [])
            adts = rec.get("acceptanceDateTime", [])
            items = rec.get("items", [])
            for fm, fd, adt, itm in zip(forms, fdates, adts, items):
                if fm in ("8-K", "8-K/A"):
                    ev8k_rows.append({
                        "cik": cik, "ticker": tk, "is_delisted": is_del,
                        "form": fm, "filing_date": fd, "acceptance_dt": adt,
                        "items": ",".join(itm) if isinstance(itm, list) else str(itm),
                    })
    except Exception:
        pass
    time.sleep(0.04)

    if (idx + 1) % 50 == 0:
        print(f"  SEC progress: {idx+1}/{len(univ)} CIKs | bb_rows={len(bb_rows)} | 8k_rows={len(ev8k_rows)}", flush=True)

df_bb = pd.DataFrame(bb_rows)
df_8k = pd.DataFrame(ev8k_rows)
df_bb.to_csv(f"{ROOT}/data/sec/sec_buybacks_pit.csv.gz", index=False, compression="gzip")
df_8k.to_csv(f"{ROOT}/data/sec/sec_8k_events_pit.csv.gz", index=False, compression="gzip")
print(f"Saved sec_buybacks_pit: {df_bb.shape} | sec_8k_events_pit: {df_8k.shape}")
