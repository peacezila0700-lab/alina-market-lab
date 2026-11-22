"""
EXP-0054: Corporate Alt-Data Suite (Transcripts + SEC Buybacks + SEC 8-K + 38y Freight Macro).
Part A: 20,681 S&P 500 Earnings Transcripts (2013-2025, 492 matched CRSP-audited PIT firms):
        Event study (t+1..t+5/21/63d) & Monthly Cross-Sectional Portfolios (IS 2013-2019, OOS 2020-2025).
Part B: SEC XBRL Share Buyback Yield (2012-2026, 360 active+delisted firms, causal filed+1d, $5/25k vol gate).
Part C: SEC 8-K Events & Item 5.02 Exec Departure Drift (2012-2026, causal acceptance_dt+1d).
Part D: 38y FRED Deep Sea Freight PPI (1989-2026) & Cass Freight (2016-2026), causal +45d lag.
"""
import os, json, gc
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = "/tmp/alina_lab"
RAW = "/var/tmp/alina_raw_cache"
JB = f"{RAW}/johnbrick_sp500"

# 1. Build survivorship-free 2010-2026 daily price/return panel (Johnbrick + local active/delisted fallback)
print("Loading 2010-2026 PIT equity panel (Johnbrick + Tiingo active/delisted)...")
pf = pq.ParquetFile(f"{JB}/prices.parquet")
jb_parts = []
for i in range(pf.metadata.num_row_groups):
    rg = pf.read_row_group(i, columns=["date", "ticker", "close", "adj_close", "volume", "source"]).to_pandas()
    rg = rg[rg["date"] >= "2010-01-01"]
    if len(rg):
        jb_parts.append(rg)
px = pd.concat(jb_parts, ignore_index=True)
del jb_parts; gc.collect()

px["base_sym"] = px["ticker"].str.split("-").str[0].str.upper()
px = px.sort_values(["base_sym", "date", "ticker"]).drop_duplicates(["base_sym", "date"], keep="last")
px["is_carried"] = (px["source"] == "carried-patch")
px = px[["date", "base_sym", "close", "adj_close", "volume", "is_carried"]].rename(columns={"base_sym": "symbol"})
jb_syms = set(px["symbol"].unique())

# Add missing SEC symbols from data/stocks and data/stocks_delisted_tiingo
extra_rows = []
for folder in [f"{ROOT}/data/stocks", f"{ROOT}/data/stocks_delisted_tiingo"]:
    if not os.path.exists(folder):
        continue
    for fn in os.listdir(folder):
        if not fn.endswith(".csv"):
            continue
        sym = fn[:-4].upper()
        if sym in jb_syms:
            continue
        d = pd.read_csv(f"{folder}/{fn}")
        dcol = "date" if "date" in d.columns else "Date"
        ac = "adjclose" if "adjclose" in d.columns else ("adj_close" if "adj_close" in d.columns else "close")
        cc = "close" if "close" in d.columns else ac
        vc = "volume" if "volume" in d.columns else None
        d["date"] = pd.to_datetime(d[dcol])
        d = d[d["date"] >= "2010-01-01"].copy()
        if len(d) < 30:
            continue
        d["symbol"] = sym
        d["close"] = pd.to_numeric(d[cc], errors="coerce")
        d["adj_close"] = pd.to_numeric(d[ac], errors="coerce")
        d["volume"] = pd.to_numeric(d[vc], errors="coerce").fillna(50000.0) if vc else 50000.0
        d["is_carried"] = False
        extra_rows.append(d[["date", "symbol", "close", "adj_close", "volume", "is_carried"]])

if extra_rows:
    px = pd.concat([px, pd.concat(extra_rows, ignore_index=True)], ignore_index=True)
    del extra_rows; gc.collect()

px = px.sort_values(["symbol", "date"]).drop_duplicates(["symbol", "date"]).reset_index(drop=True)
px["close"] = px["close"].astype("float32")
px["adj_close"] = px["adj_close"].astype("float32")
px["volume"] = px["volume"].fillna(0).astype("float32")
px["ret"] = px.groupby("symbol", sort=False)["adj_close"].pct_change().clip(-0.95, 3.0).fillna(0.0).astype("float32")

all_dates = np.sort(px["date"].unique())
syms = sorted(px["symbol"].unique())
sym_to_id = {s: i for i, s in enumerate(syms)}
d_to_pos = {d: i for i, d in enumerate(all_dates)}
px["did"] = px["date"].map(d_to_pos).astype("int32")
px["sid"] = px["symbol"].map(sym_to_id).astype("int16")

R_MAT = np.zeros((len(all_dates), len(syms)), dtype=np.float32)
C_MAT = np.zeros((len(all_dates), len(syms)), dtype=np.float32)
V_MAT = np.zeros((len(all_dates), len(syms)), dtype=np.float32)
CAR_MAT = np.ones((len(all_dates), len(syms)), dtype=bool)
R_MAT[px["did"].values, px["sid"].values] = px["ret"].values
C_MAT[px["did"].values, px["sid"].values] = px["close"].values
V_MAT[px["did"].values, px["sid"].values] = px["volume"].values
CAR_MAT[px["did"].values, px["sid"].values] = px["is_carried"].values
print(f"Unified Panel ready: {len(all_dates)} days ({pd.Timestamp(all_dates[0]).strftime('%Y-%m-%d')}..{pd.Timestamp(all_dates[-1]).strftime('%Y-%m-%d')}), {len(syms)} firms")

fr = pd.read_csv(f"{ROOT}/data/macro/fred_rates_full.csv")
fr["date"] = pd.to_datetime(fr["date"])
fr["rf_daily"] = pd.to_numeric(fr["dtb3"], errors="coerce").ffill().fillna(0.0) / 100.0 / 252.0
rf_map = dict(zip(fr["date"], fr["rf_daily"]))
rf_arr = np.array([rf_map.get(pd.Timestamp(d), 0.0) for d in all_dates], dtype=np.float32)

# Helper: Monthly Cross-Sectional Portfolio evaluator given sparse signal DataFrame (date, sid, <cols>)
def run_cs_suite(sig_df, feat_cols, eligible_sids, start_year, split_year, max_staleness_days=120, top_n=30, cost_bps=10.0):
    date_ser = pd.Series(all_dates)
    me_dates = sorted(date_ser.groupby(date_ser.dt.to_period("M")).max().values)
    sig_dates = [d for d in me_dates if pd.Timestamp(d).year >= start_year - 1 and d < all_dates[-2]]

    # Build as-of causal signal dictionary at each monthly sig_date (merge_asof per feature row <= sig_date & >= sig_date - max_staleness)
    sig_df = sig_df[sig_df["sid"].isin(eligible_sids)].sort_values("date").copy()
    slices = {}
    elig_arr = np.array(sorted(eligible_sids), dtype=int)
    for sd in sig_dates:
        p = d_to_pos[sd]
        # Eligible price/vol/carried filter at signal date
        ok = (C_MAT[p, elig_arr] >= 5.0) & (V_MAT[p, elig_arr] >= 25000.0) & (~CAR_MAT[p, elig_arr])
        ok_sids = elig_arr[ok]
        if len(ok_sids) < 2 * top_n + 10:
            continue
        sd_min = sd - np.timedelta64(max_staleness_days, "D")
        sub = sig_df[(sig_df["date"] <= sd) & (sig_df["date"] >= sd_min) & (sig_df["sid"].isin(ok_sids))].drop_duplicates("sid", keep="last")
        if len(sub) >= 2 * top_n + 10:
            slices[sd] = sub.set_index("sid")[feat_cols]

    periods = []
    v_sd = sorted(slices.keys())
    for k in range(len(v_sd) - 1):
        p0 = d_to_pos[v_sd[k]] + 1
        p1 = d_to_pos[v_sd[k + 1]] + 1
        if p1 > p0:
            periods.append((v_sd[k], np.arange(p0 + 1, min(p1 + 1, len(all_dates)))))

    def eval_col(col, mode="LS"):
        rets, dts = [], []
        prev_w = np.zeros(len(syms))
        start_np = np.datetime64(f"{start_year}-01-01")
        for sd, hidx in periods:
            sl = slices[sd]
            w = np.zeros(len(syms))
            if mode == "EW":
                w[sl.index.values] = 1.0 / len(sl)
            else:
                s = sl[col].replace([np.inf, -np.inf], np.nan).dropna().sort_values(ascending=False)
                if len(s) < 2 * top_n:
                    continue
                longs = s.index.values[:top_n]
                if mode == "LO":
                    w[longs] = 1.0 / top_n
                else:
                    shorts = s.index.values[-top_n:]
                    w[longs] = 0.5 / top_n
                    w[shorts] = -0.5 / top_n
            cost0 = float(np.abs(w - prev_w).sum()) * (cost_bps / 10000.0)
            prev_w = w
            nz = np.where(w != 0.0)[0]
            cur_w = w[nz].copy()
            for step, did in enumerate(hidx):
                dt = all_dates[did]
                pr = float(np.dot(cur_w, R_MAT[did, nz])) + (float(rf_arr[did]) if mode == "LS" else 0.0) - (cost0 if step == 0 else 0.0)
                if dt >= start_np:
                    rets.append(pr); dts.append(dt)
                cur_w *= (1.0 + R_MAT[did, nz])
        s = pd.Series(rets, index=pd.to_datetime(dts))
        def ms(sub):
            if len(sub) < 60 or sub.std(ddof=1) < 1e-12:
                return None
            sh = (sub.mean() / sub.std(ddof=1)) * np.sqrt(252.0)
            eq = (1.0 + sub).cumprod()
            cagr = eq.iloc[-1] ** (252.0 / len(sub)) - 1.0
            dd = (eq / eq.cummax() - 1.0).min()
            return {"sharpe": round(float(sh), 3), "cagr": round(float(cagr * 100), 2), "dd": round(float(dd * 100), 2)}
        return {"all": ms(s), "is": ms(s[s.index.year < split_year]), "oos": ms(s[s.index.year >= split_year])}

    def perm(col, mode="LS", n_perm=200):
        rng = np.random.default_rng(42)
        real = eval_col(col, mode)["all"]["sharpe"]
        per = []
        for sd, hidx in periods:
            if pd.Timestamp(sd).year < start_year:
                continue
            s = slices[sd][col].replace([np.inf, -np.inf], np.nan).dropna()
            if len(s) < 2 * top_n:
                continue
            comp_r = np.prod(1.0 + R_MAT[hidx][:, s.index.values], axis=0) - 1.0
            per.append((comp_r, float(rf_arr[hidx].sum())))
        beats = 0
        for _ in range(n_perm):
            rs = []
            for cr, rfm in per:
                p = rng.permutation(len(cr))
                if mode == "LO":
                    rs.append(cr[p[:top_n]].mean() - (0.5 * 2 * cost_bps / 10000.0))
                else:
                    rs.append(0.5 * (cr[p[:top_n]].mean() - cr[p[-top_n:]].mean()) + rfm - (1.0 * 2 * cost_bps / 10000.0))
            a = np.array(rs)
            sh_p = (a.mean() / a.std(ddof=1)) * np.sqrt(12.0) if a.std(ddof=1) > 1e-12 else 0.0
            if real > sh_p:
                beats += 1
        return round(100.0 * beats / n_perm, 1)

    res = {"EW_Univ": eval_col(None, "EW")}
    print(f"  {'EW_Univ':<22} | All={res['EW_Univ']['all']['sharpe']:+.3f} (DD {res['EW_Univ']['all']['dd']:+.1f}%) | IS={res['EW_Univ']['is']['sharpe']:+.3f} | OOS={res['EW_Univ']['oos']['sharpe']:+.3f}")
    for c in feat_cols:
        for md in ["LO", "LS"]:
            r = eval_col(c, md)
            pp = perm(c, md)
            k = f"{c}_{md}"
            res[k] = {**r, "perm200": pp}
            print(f"  {k:<22} | All={r['all']['sharpe']:+.3f} (DD {r['all']['dd']:+.1f}%) | IS={r['is']['sharpe']:+.3f} | OOS={r['oos']['sharpe']:+.3f} | Perm={pp}")
    return res

results = {}

# -------------------------------------------------------------------------
# PART A: S&P 500 Earnings Transcripts NLP (2013-2025)
# -------------------------------------------------------------------------
tr = pd.read_csv(f"{ROOT}/data/sec/sp500_earnings_transcript_features_2013_2025.csv.gz")
tr["symbol"] = tr["ticker"].str.upper()
tr["date"] = pd.to_datetime(tr["earnings_date"]) + pd.Timedelta(days=1)  # strictly available next day!
tr = tr[tr["symbol"].isin(sym_to_id)].sort_values(["symbol", "date"]).reset_index(drop=True)
tr["sid"] = tr["symbol"].map(sym_to_id)
tr["yoy_tone"] = tr["net_tone"] - tr.groupby("symbol")["net_tone"].shift(4)
tr["neg_unc_pct"] = -tr["unc_pct"]
tr["guide_net"] = tr["guide_up"] - tr["guide_dn"]

print("\n=== PART A1: Transcripts Cross-Section (2014-2025, 492 S&P 500 firms, IS<2020, OOS>=2020) ===")
tr_sids = set(tr["sid"].unique())
results["transcripts_cs"] = run_cs_suite(
    tr, ["net_tone", "yoy_tone", "qa_minus_prep", "neg_unc_pct", "guide_net"],
    tr_sids, start_year=2014, split_year=2020, max_staleness_days=110, top_n=30
)

# Event study on Transcripts: Q5 vs Q1 Net Tone excess return over t+1..t+5/21/63d!
ew_px_daily = pd.Series(np.nanmean(np.where(C_MAT[:, sorted(tr_sids)] >= 5.0, R_MAT[:, sorted(tr_sids)], np.nan), axis=1), index=all_dates).fillna(0.0)
print("\n=== PART A2: Post-Earnings-Transcript Tone Event Study (t+1..t+5/21/63d vs EW) ===")
ev_tr = {}
for col in ["net_tone", "yoy_tone", "qa_minus_prep"]:
    sub_tr = tr.dropna(subset=[col, "date"]).copy()
    # Strictly rolling expanding quintiles per quarter (no future rank peek!)
    sub_tr["yq"] = sub_tr["date"].dt.to_period("Q").astype(str)
    q_res = {}
    for h in [5, 21, 63]:
        q5_ex, q1_ex = [], []
        for yq, grp in sub_tr.groupby("yq"):
            if len(grp) < 40:
                continue
            hi_thr = grp[col].quantile(0.8)
            lo_thr = grp[col].quantile(0.2)
            for _, r in grp.iterrows():
                pos = np.searchsorted(all_dates, r["date"].to_datetime64())
                if pos + h >= len(all_dates):
                    continue
                h_idx = np.arange(pos, pos + h)
                stk_r = float(np.prod(1.0 + R_MAT[h_idx, int(r["sid"])]) - 1.0)
                ew_r = float(np.prod(1.0 + ew_px_daily.iloc[h_idx].values) - 1.0)
                ex = stk_r - ew_r
                if r[col] >= hi_thr:
                    q5_ex.append(ex)
                elif r[col] <= lo_thr:
                    q1_ex.append(ex)
        q5_m = float(np.mean(q5_ex) * 100)
        q1_m = float(np.mean(q1_ex) * 100)
        spread = q5_m - q1_m
        se = np.sqrt(np.var(q5_ex, ddof=1)/len(q5_ex) + np.var(q1_ex, ddof=1)/len(q1_ex)) * 100
        t_st = spread / max(1e-9, se)
        q_res[f"{h}d"] = {"n_q5": len(q5_ex), "q5_pct": round(q5_m, 3), "q1_pct": round(q1_m, 3), "q5_m_q1_pct": round(spread, 3), "t_stat": round(float(t_st), 2)}
        print(f"  {col:<15} {h:2d}d | Q5={q5_m:+.3f}% vs Q1={q1_m:+.3f}% | Q5-Q1={spread:+.3f}% (t={t_st:+.2f})")
    ev_tr[col] = q_res
results["transcripts_event_study"] = ev_tr

# -------------------------------------------------------------------------
# PART B: SEC XBRL Share Buyback Yield (2013-2026, 360 Active+Delisted Firms)
# -------------------------------------------------------------------------
bb = pd.read_csv(f"{ROOT}/data/sec/sec_buybacks_pit.csv.gz")
bb["symbol"] = bb["ticker"].str.upper()
bb = bb[bb["symbol"].isin(sym_to_id)].copy()
bb["sid"] = bb["symbol"].map(sym_to_id)
bb["date"] = pd.to_datetime(bb["filed"], errors="coerce") + pd.Timedelta(days=1)
bb = bb.dropna(subset=["date"]).copy()

sh_out = bb[bb["tag"] == "SHARES_OUT"].sort_values(["sid", "date"]).drop_duplicates(["sid", "date"], keep="last")
rep = bb[bb["tag"] != "SHARES_OUT"].copy()
rep["ann_bb_usd"] = rep["val_usd"] * (365.0 / rep["days"].clip(lower=70))
rep = rep.sort_values(["sid", "date", "days"]).drop_duplicates(["sid", "date"], keep="last")

sh_map_df = pd.merge_asof(
    rep.sort_values("date"),
    sh_out[["date", "sid", "val_usd"]].rename(columns={"val_usd": "shares_out"}).sort_values("date"),
    on="date", by="sid", direction="backward"
)
bb_rows_clean = []
for _, r in sh_map_df.dropna(subset=["shares_out", "ann_bb_usd"]).iterrows():
    pos = min(len(all_dates) - 1, max(0, np.searchsorted(all_dates, r["date"].to_datetime64()) - 1))
    cls_p = float(C_MAT[pos, int(r["sid"])])
    if cls_p >= 5.0 and r["shares_out"] > 1e5:
        mcap = cls_p * float(r["shares_out"])
        bb_yield = float(r["ann_bb_usd"]) / mcap
        if -0.05 <= bb_yield <= 0.40:
            bb_rows_clean.append({"date": r["date"], "sid": int(r["sid"]), "bb_yield": bb_yield, "neg_bb_yield": -bb_yield})
bb_sig = pd.DataFrame(bb_rows_clean)
print(f"\n=== PART B: SEC XBRL Buyback Yield Cross-Section (2013-2026, n_rows={len(bb_sig)}, firms={bb_sig['sid'].nunique()}, IS<2019) ===")
results["sec_buybacks_cs"] = run_cs_suite(
    bb_sig, ["bb_yield", "neg_bb_yield"], set(bb_sig["sid"].unique()),
    start_year=2013, split_year=2019, max_staleness_days=380, top_n=25
)

# -------------------------------------------------------------------------
# PART C: SEC 8-K Item 5.02 Executive Departure Drift (2013-2026)
# -------------------------------------------------------------------------
e8 = pd.read_csv(f"{ROOT}/data/sec/sec_8k_events_pit.csv.gz")
e8["symbol"] = e8["ticker"].str.upper()
e8 = e8[e8["symbol"].isin(sym_to_id)].copy()
e8["sid"] = e8["symbol"].map(sym_to_id)
e8["date"] = pd.to_datetime(e8["filing_date"], errors="coerce") + pd.Timedelta(days=1)
e8 = e8.dropna(subset=["date"]).copy()
e502 = e8[e8["items"].astype(str).str.contains("5.02", na=False) & (e8["date"] >= "2013-01-01") & (e8["date"] <= "2026-06-01")].copy()
e8_all_sids = sorted(e8["sid"].unique())
ew_sec_daily = pd.Series(np.nanmean(np.where(C_MAT[:, e8_all_sids] >= 5.0, R_MAT[:, e8_all_sids], np.nan), axis=1), index=all_dates).fillna(0.0)

print(f"\n=== PART C: SEC 8-K Item 5.02 Executive Turnover Event Drift (n={len(e502)}, causal filing+1d) ===")
res_8k = {}
for h in [5, 21, 63]:
    ex_is, ex_oos = [], []
    for _, r in e502.iterrows():
        pos = np.searchsorted(all_dates, r["date"].to_datetime64())
        if pos + h >= len(all_dates) or C_MAT[max(0, pos-1), int(r["sid"])] < 5.0:
            continue
        h_idx = np.arange(pos, pos + h)
        stk_r = float(np.prod(1.0 + R_MAT[h_idx, int(r["sid"])]) - 1.0)
        ew_r = float(np.prod(1.0 + ew_sec_daily.iloc[h_idx].values) - 1.0)
        ex = stk_r - ew_r
        if r["date"].year < 2020:
            ex_is.append(ex)
        else:
            ex_oos.append(ex)
    all_ex = ex_is + ex_oos
    def st_ev(arr):
        if len(arr) < 20:
            return None
        return {"n": len(arr), "excess_pct": round(float(np.mean(arr)*100), 3), "t_stat": round(float(np.mean(arr)/(np.std(arr,ddof=1)/np.sqrt(len(arr)))), 2)}
    res_8k[f"{h}d"] = {"all": st_ev(all_ex), "is": st_ev(ex_is), "oos": st_ev(ex_oos)}
    a, i_s, o_s = res_8k[f"{h}d"]["all"], res_8k[f"{h}d"]["is"], res_8k[f"{h}d"]["oos"]
    print(f"  Item 5.02 {h:2d}d | n={a['n']} | All={a['excess_pct']:+.3f}% (t={a['t_stat']:+.2f}) | IS={i_s['excess_pct']:+.3f}% | OOS={o_s['excess_pct']:+.3f}%")
results["sec_8k_item502"] = res_8k

# -------------------------------------------------------------------------
# PART D: 38y Deep Sea Freight PPI (1989-2026) & Cass Freight (2016-2026)
# -------------------------------------------------------------------------
fr_m = pd.read_csv(f"{ROOT}/data/macro/fred_freight_monthly.csv")
fr_m["avail_dt"] = pd.to_datetime(fr_m["date"]) + pd.Timedelta(days=45)  # strict BLS/Cass release lag
fr_m["sea_yoy"] = fr_m["PCU483111483111"] / fr_m["PCU483111483111"].shift(12) - 1.0
fr_m["sea_3m"] = fr_m["PCU483111483111"] / fr_m["PCU483111483111"].shift(3) - 1.0
fr_m["cass_ship_yoy"] = fr_m["FRGSHPUSM649NCIS"] / fr_m["FRGSHPUSM649NCIS"].shift(12) - 1.0

print("\n=== PART D: 38y Deep Sea Freight PPI & Cass Freight Timing (10bp/side, causal +45d lag) ===")
res_fr = {}
for sym in ["SPY", "XLI", "TLT", "GLD"]:
    fp = f"{ROOT}/data/etfs_tiingo/{sym}.csv"
    if not os.path.exists(fp):
        continue
    ed = pd.read_csv(fp)
    ed["dt"] = pd.to_datetime(ed["date"])
    ed = ed.sort_values("dt").drop_duplicates("dt")
    ed["ret"] = pd.to_numeric(ed["adjclose"], errors="coerce").pct_change().fillna(0.0)
    m_f = pd.merge_asof(ed[["dt", "ret"]], fr_m[["avail_dt", "sea_yoy", "sea_3m", "cass_ship_yoy"]].rename(columns={"avail_dt": "dt"}).sort_values("dt"), on="dt", direction="backward")
    sym_f = {}
    for nm, sig in [
        ("BuyHold", np.ones(len(m_f))),
        ("SeaFreight_YoY_Pos", (m_f["sea_yoy"].fillna(0) > 0).astype(float).values),
        ("SeaFreight_3m_Pos", (m_f["sea_3m"].fillna(0) > 0).astype(float).values),
    ]:
        w = pd.Series(sig).shift(1).fillna(0.0).values
        dw = np.abs(np.diff(np.concatenate([[0.0], w])))
        st = w * m_f["ret"].values - dw * (10.0 / 10000.0)
        is_m = m_f["dt"].dt.year.values < 2014
        oos_m = m_f["dt"].dt.year.values >= 2014
        def ms_f(a):
            sh = (a.mean() / a.std(ddof=1)) * np.sqrt(252.0) if a.std(ddof=1) > 1e-12 else 0.0
            eq = np.cumprod(1.0 + a)
            dd = np.min(eq / np.maximum.accumulate(eq) - 1.0)
            return {"sharpe": round(float(sh), 3), "dd": round(float(dd * 100), 2)}
        sym_f[nm] = {"all": ms_f(st), "is": ms_f(st[is_m]), "oos": ms_f(st[oos_m])}
    res_fr[sym] = sym_f
    print(f"  {sym:<4} | BH OOS={sym_f['BuyHold']['oos']['sharpe']:+.3f} | SeaYoY OOS={sym_f['SeaFreight_YoY_Pos']['oos']['sharpe']:+.3f} (All {sym_f['SeaFreight_YoY_Pos']['all']['sharpe']:+.3f}) | Sea3m OOS={sym_f['SeaFreight_3m_Pos']['oos']['sharpe']:+.3f}")
results["freight_macro"] = res_fr

with open(f"{ROOT}/research/artifacts/exp0054_transcripts_buybacks_8k_freight.json", "w") as f:
    json.dump(results, f, indent=2)
print("Saved exp0054_transcripts_buybacks_8k_freight.json")
