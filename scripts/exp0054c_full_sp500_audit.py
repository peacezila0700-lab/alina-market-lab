import json, os, warnings
warnings.filterwarnings("ignore")
import numpy as np
import pandas as pd

ROOT = "/tmp/alina_lab"
JB = "/var/tmp/alina_raw_cache/johnbrick_sp500"

print("Loading Johnbrick PIT S&P 500 membership & prices (>=2012)...", flush=True)
mi = pd.read_parquet(f"{JB}/membership_intervals.parquet")
mi["start_dt"] = pd.to_datetime(mi["start"])
mi["end_dt"] = pd.to_datetime(mi["end"]).fillna(pd.Timestamp("2026-12-31"))
sp_mi = mi[mi["end_dt"] >= "2012-01-01"].copy()
sp_mi["ticker"] = sp_mi["ticker"].str.upper()

cik_map = pd.read_csv(f"{ROOT}/data/sec/sp500_2012_2026_cik_map.csv")
cik_map = cik_map[cik_map["cik"] > 0].copy()
tk_to_cik = dict(zip(cik_map["ticker"].str.upper(), cik_map["cik"].astype(int)))

sec_meta = pd.read_csv(f"{ROOT}/data/sec/sp500_2012_2026_sec_meta.csv")
def sic_to_sector(sic_str):
    try:
        s = int(float(sic_str))
    except Exception:
        return "Other"
    if 100 <= s <= 999: return "Agri"
    if 1000 <= s <= 1499: return "Energy_Min"
    if 1500 <= s <= 1799: return "Constr"
    if 2000 <= s <= 3999:
        if 2830 <= s <= 2836 or 3840 <= s <= 3851: return "Health_Bio"
        if 3570 <= s <= 3579 or 3660 <= s <= 3679 or 3810 <= s <= 3829: return "Tech_Hw"
        if 2000 <= s <= 2199: return "Staples"
        if 2800 <= s <= 2999: return "Chem_Energy"
        return "Industrials"
    if 4000 <= s <= 4999:
        if 4800 <= s <= 4899: return "Telecom"
        if 4900 <= s <= 4999: return "Utilities"
        return "Transport"
    if 5000 <= s <= 5999: return "Retail_Whl"
    if 6000 <= s <= 6999: return "Financials"
    if 7000 <= s <= 8999:
        if 7370 <= s <= 7379: return "Tech_Sw"
        return "Services"
    return "Other"

cik_to_sector = {int(r["cik"]): sic_to_sector(r["sic"]) for _, r in sec_meta.iterrows()}

# Load prices >= 2012-01-01 ONLY for tickers in sp_mi
sp_tickers = sorted(sp_mi["ticker"].unique())
px_df = pd.read_parquet(
    f"{JB}/prices.parquet",
    columns=["date", "ticker", "close", "adj_close", "volume", "stock_splits", "source"],
    filters=[("date", ">=", pd.Timestamp("2012-01-01"))],
)
px_df["ticker"] = px_df["ticker"].str.upper()
px_df = px_df[px_df["ticker"].isin(sp_tickers)].sort_values(["ticker", "date"]).reset_index(drop=True)

# Reconstruct EXACT unadjusted close (yahoo backward split-adjusted -> unsplit; tiingo/crsp/wiki already unsplit!)
def add_unsplit_close(df):
    is_y = (df["source"] == "yahoo") & (df["stock_splits"] > 0)
    # For each yahoo split day d, multiply all prior dates by stock_splits[d]
    # Vectorized per-ticker reverse cumprod on yahoo splits
    fac = np.ones(len(df), dtype=np.float64)
    y_idx = np.where(is_y.values)[0]
    if len(y_idx) > 0:
        # group within df
        tks = df["ticker"].values
        for idx in y_idx:
            tk = tks[idx]
            spv = df["stock_splits"].iat[idx]
            if spv > 0 and abs(spv - 1.0) > 1e-6:
                # find start of this ticker
                # faster via groupby outside, let's do vectorized groupby below
                pass
    return fac

# Vectorized reverse cumprod for yahoo splits strictly after t
px_df["y_sp"] = np.where((px_df["source"] == "yahoo") & (px_df["stock_splits"] > 0), px_df["stock_splits"], 1.0)
# Shift y_sp back by 1 within ticker so split on day s affects days < s
px_df["y_sp_next"] = px_df.groupby("ticker")["y_sp"].shift(-1).fillna(1.0)
px_df["fut_split"] = px_df.iloc[::-1].groupby("ticker")["y_sp_next"].cumprod().iloc[::-1]
px_df["unsplit_close"] = px_df["close"] * px_df["fut_split"]

# Build aligned daily matrices (adj_close returns, unsplit_close, volume)
all_dates = pd.DatetimeIndex(sorted(px_df["date"].unique()))
date_to_pos = {d: i for i, d in enumerate(all_dates)}
syms = sorted(px_df["ticker"].unique())
sym_to_id = {s: i for i, s in enumerate(syms)}
N_D, N_S = len(all_dates), len(syms)

ADJ = px_df.pivot(index="date", columns="ticker", values="adj_close").reindex(index=all_dates, columns=syms)
RET_DF = ADJ.pct_change().fillna(0.0).clip(-0.95, 5.0)
R_MAT = RET_DF.values.astype(np.float32)
U_MAT = px_df.pivot(index="date", columns="ticker", values="unsplit_close").reindex(index=all_dates, columns=syms).values.astype(np.float32)
V_MAT = px_df.pivot(index="date", columns="ticker", values="volume").reindex(index=all_dates, columns=syms).values.astype(np.float32)

# Build daily PIT S&P 500 membership boolean matrix [N_D, N_S], deduplicated to 1 primary ticker per CIK per date!
PIT_MASK = np.zeros((N_D, N_S), dtype=bool)
for _, r in sp_mi.iterrows():
    sid = sym_to_id.get(r["ticker"])
    if sid is None: continue
    i0 = np.searchsorted(all_dates, r["start_dt"].to_datetime64(), side="left")
    i1 = np.searchsorted(all_dates, r["end_dt"].to_datetime64(), side="right")
    PIT_MASK[i0:i1, sid] = True

# Deduplicate multiple share classes of same CIK on the same day (keep higher trailing dollar volume)
cik_to_sids = {}
for s, sid in sym_to_id.items():
    ck = tk_to_cik.get(s, 0)
    if ck > 0:
        cik_to_sids.setdefault(ck, []).append(sid)
for ck, sids in cik_to_sids.items():
    if len(sids) > 1:
        # check days where >1 sid is in PIT_MASK
        sub_m = PIT_MASK[:, sids]
        dup_days = np.where(sub_m.sum(axis=1) > 1)[0]
        if len(dup_days) > 0:
            dv = np.nan_to_num(U_MAT[dup_days][:, sids] * V_MAT[dup_days][:, sids], nan=0.0)
            best_col = np.argmax(dv, axis=1)
            for row_i, d_i in enumerate(dup_days):
                for col_j, sid in enumerate(sids):
                    if col_j != best_col[row_i]:
                        PIT_MASK[d_i, sid] = False

print(f"Matrices built: {N_D} days x {N_S} syms | Avg PIT S&P 500 count/day={PIT_MASK.sum(axis=1).mean():.1f}", flush=True)

# Risk-free daily array (dtb3 from fred_rates_full.csv)
rf_df = pd.read_csv(f"{ROOT}/data/macro/fred_rates_full.csv", parse_dates=["date"]).set_index("date")["dtb3"].reindex(all_dates).ffill().fillna(0.0) / 100.0 / 252.0
rf_arr = rf_df.values.astype(np.float64)

# -------------------------------------------------------------------------
# PART 1: SEC XBRL BUYBACK YIELD ON 100% SURVIVORSHIP-FREE S&P 500 (2013-2026)
# -------------------------------------------------------------------------
print("\nBuilding strictly PIT Buyback / Shares / Assets panel...", flush=True)
bb = pd.read_csv(f"{ROOT}/data/sec/sec_buybacks_sp500_full_pit.csv.gz", low_memory=False)
bb["date"] = pd.to_datetime(bb["filed"], errors="coerce") + pd.Timedelta(days=1)
bb = bb.dropna(subset=["date", "cik", "val"]).copy()
bb["cik"] = bb["cik"].astype(int)
bb["end_s"] = bb["end"].astype(str)

# Shares: prefer 'shares' or 'dei_shares'; take latest 'end' reported on each 'filed' date!
sh_raw = bb[bb["metric"].isin(["shares", "dei_shares"]) & (bb["val"] > 1e5)].copy()
sh_raw["prio"] = np.where(sh_raw["metric"] == "shares", 2, 1)
sh_raw = sh_raw.sort_values(["cik", "date", "end_s", "prio"]).drop_duplicates(["cik", "date"], keep="last")

# Buybacks: keep days in [70, 400] (no multi-year 730d rows!), sort by ["cik", "date", "end_s", "days"] so ALWAYS latest fiscal end & longest YTD!
rep_raw = bb[bb["metric"].isin(["bb_cash", "bb_cash_eq", "bb_val", "bb_treas"]) & (bb["days"] >= 70) & (bb["days"] <= 400)].copy()
rep_raw["prio"] = rep_raw["metric"].map({"bb_cash": 4, "bb_val": 3, "bb_cash_eq": 2, "bb_treas": 1}).fillna(0)
rep_raw["ann_bb"] = rep_raw["val"] * (365.0 / rep_raw["days"].astype(float))
rep_raw = rep_raw.sort_values(["cik", "date", "prio", "end_s", "days"]).drop_duplicates(["cik", "date"], keep="last")

# Assets & Equity (latest filing date & end)
ast_raw = bb[(bb["metric"] == "assets") & (bb["val"] > 1e6)].sort_values(["cik", "date", "end_s"]).drop_duplicates(["cik", "date"], keep="last")

# Build per-CIK timeline via fast dictionary lookup for each monthly rebalance date!
# First map each active sid -> cik
sid_to_cik = {sid: tk_to_cik.get(syms[sid], 0) for sid in range(N_S)}

# Pre-group by cik for fast O(log N) searchsorted on rebalance dates
def build_cik_dict(df, val_col):
    d = {}
    for cik, grp in df.groupby("cik"):
        g = grp.sort_values("date")
        d[int(cik)] = (g["date"].values.astype("datetime64[ns]"), g[val_col].values.astype(np.float64), g["end_s"].values)
    return d

sh_dict = build_cik_dict(sh_raw, "val")
rep_dict = build_cik_dict(rep_raw, "ann_bb")
ast_dict = build_cik_dict(ast_raw, "val")

# Also load 10-K/10-Q activity from pit_fundamentals or sh_dict/ast_dict so we know if firm is an active SEC filer!
def get_last(dic, cik, dt64, max_age_days=400):
    tup = dic.get(cik)
    if tup is None: return None
    dts, vals, _ = tup
    idx = np.searchsorted(dts, dt64, side="right") - 1
    if idx < 0: return None
    age = (dt64 - dts[idx]) / np.timedelta64(1, "D")
    if age > max_age_days: return None
    return float(vals[idx])

# Monthly rebalance dates (last trading day of each month from 2012-12 to 2026-09)
dt_series = pd.Series(all_dates, index=all_dates)
month_ends = dt_series.resample("ME").last().dropna()
month_ends = month_ends[(month_ends >= "2012-12-01") & (month_ends <= "2026-09-30")].values

def eval_buybacks(universe_mode="ZERO_FILL", weight_mode="EW", neutral_mode="NONE", cost_bps=10.0, top_frac=0.20, min_yr=2013):
    reb_pos = [date_to_pos[pd.Timestamp(d)] for d in month_ends]
    daily_ls, daily_dates = [], []
    q_rets = {q: [] for q in range(1, 6)}
    q_dates = []
    counts = []
    for k in range(len(reb_pos) - 1):
        p0, p1 = reb_pos[k], reb_pos[k + 1]
        dt_ts = pd.Timestamp(all_dates[p0])
        if dt_ts.year < min_yr: continue
        dt64 = np.datetime64(dt_ts)
        # Active PIT S&P 500 sids with unsplit_close >= $5
        sids = np.where(PIT_MASK[p0])[0]
        rows = []
        for sid in sids:
            ck = sid_to_cik[sid]
            if ck <= 0: continue
            upx = float(U_MAT[p0, sid])
            if not np.isfinite(upx) or upx < 5.0: continue
            sh = get_last(sh_dict, ck, dt64, 420)
            if sh is None or sh <= 1e5: continue
            mcap = upx * sh
            if mcap < 1e8: continue
            ann_bb = get_last(rep_dict, ck, dt64, 420)
            if ann_bb is None:
                if universe_mode == "REP_ONLY": continue
                ann_bb = 0.0
            bby = ann_bb / mcap
            if not (-0.05 <= bby <= 0.40): continue
            sec = cik_to_sector.get(ck, "Other")
            rows.append((sid, ck, bby, mcap, sec))
        if len(rows) < 100: continue
        df_m = pd.DataFrame(rows, columns=["sid", "cik", "bby", "mcap", "sec"])
        counts.append(len(df_m))

        # Neutralize signal if requested
        sig = df_m["bby"].values.copy()
        if neutral_mode == "SECTOR":
            # within-sector rank or demean (use demeaned z/rank within sectors with >=5 stocks, else overall)
            df_m["sig"] = df_m.groupby("sec")["bby"].transform(lambda s: s - s.mean() if len(s) >= 5 else s - df_m["bby"].mean())
        elif neutral_mode == "SIZE":
            df_m["sz_bin"] = pd.qcut(df_m["mcap"], 3, labels=False, duplicates="drop")
            df_m["sig"] = df_m.groupby("sz_bin")["bby"].transform(lambda s: s - s.mean())
        elif neutral_mode == "SEC_SIZE":
            df_m["sig"] = df_m.groupby("sec")["bby"].transform(lambda s: s - s.mean() if len(s) >= 5 else s - df_m["bby"].mean())
            df_m["sz_bin"] = pd.qcut(df_m["mcap"], 3, labels=False, duplicates="drop")
            df_m["sig"] = df_m.groupby("sz_bin")["sig"].transform(lambda s: s - s.mean())
        else:
            df_m["sig"] = sig

        df_m = df_m.sort_values("sig").reset_index(drop=True)
        n = len(df_m)
        n_q = max(10, int(round(n * top_frac)))
        # Quintiles Q1..Q5 (on raw bby or sig)
        h_idx = np.arange(p0 + 1, p1 + 1)
        R_sub = R_MAT[h_idx]
        rf_sub = rf_arr[h_idx]

        def port_daily(sub_df):
            s_arr = sub_df["sid"].values
            if weight_mode == "VW":
                w = sub_df["mcap"].values
                w = np.minimum(w, np.percentile(w, 95))  # cap mega-cap single stock at 95th pct or pure VW? Let's test pure VW!
                w = sub_df["mcap"].values
                w = w / w.sum()
            else:
                w = np.ones(len(s_arr)) / len(s_arr)
            return R_sub[:, s_arr] @ w

        r_q1 = port_daily(df_m.iloc[:n_q])
        r_q5 = port_daily(df_m.iloc[-n_q:])
        # Exact daily L/S: 0.5*(r_q5 - r_q1) + rf - tx cost on day 0
        tx = 2.0 * cost_bps / 10000.0  # 100% gross exposure per side = 0.5L + 0.5S, conservative full turnover = 2*cost_bps
        ls_d = 0.5 * (r_q5 - r_q1) + rf_sub
        ls_d[0] -= tx
        daily_ls.extend(ls_d.tolist())
        daily_dates.extend(all_dates[h_idx])

        # Also record 5 quintile compounded returns
        if neutral_mode == "NONE" and weight_mode == "EW":
            qs = np.array_split(df_m.index.values, 5)
            for qi in range(5):
                rd = port_daily(df_m.iloc[qs[qi]])
                q_rets[qi + 1].append(float(np.prod(1.0 + rd) - 1.0))
            q_dates.append(all_dates[p1])

    s = pd.Series(daily_ls, index=pd.DatetimeIndex(daily_dates))
    def ms(sub):
        if len(sub) < 60: return {"sharpe": 0.0, "cagr": 0.0, "dd": 0.0}
        sh = (sub.mean() / sub.std(ddof=1)) * np.sqrt(252.0)
        eq = (1.0 + sub).cumprod()
        cagr = eq.iloc[-1] ** (252.0 / len(sub)) - 1.0
        dd = (eq / eq.cummax() - 1.0).min()
        return {"sharpe": round(float(sh), 3), "cagr": round(float(cagr * 100), 2), "dd": round(float(dd * 100), 2)}
    yr_sh = {int(yr): round(float((g.mean() / max(1e-12, g.std(ddof=1))) * np.sqrt(252.0)), 3) for yr, g in s.groupby(s.index.year)}
    res = {
        "n_avg": round(float(np.mean(counts)), 1),
        "all": ms(s),
        "is_pre2020": ms(s[s.index.year < 2020]),
        "oos_2020p": ms(s[s.index.year >= 2020]),
        "is_pre2019": ms(s[s.index.year < 2019]),
        "oos_2019p": ms(s[s.index.year >= 2019]),
        "yearly": yr_sh,
    }
    if q_rets[1]:
        res["quintiles_ann_ret_pct"] = {f"Q{q}": round(float(np.mean(q_rets[q]) * 12.0 * 100), 2) for q in range(1, 6)}
    return res, s

print("\n=== PART 1: SURVIVORSHIP-FREE S&P 500 BUYBACK YIELD (2013-2026) ===", flush=True)
bb_results = {}
bb_series = {}
configs = [
    ("ZERO_FILL_EW_10bp", "ZERO_FILL", "EW", "NONE", 10.0),
    ("ZERO_FILL_EW_20bp", "ZERO_FILL", "EW", "NONE", 20.0),
    ("ZERO_FILL_SecNeut_10bp", "ZERO_FILL", "EW", "SECTOR", 10.0),
    ("ZERO_FILL_SizeNeut_10bp", "ZERO_FILL", "EW", "SIZE", 10.0),
    ("ZERO_FILL_SecSizeNeut_10bp", "ZERO_FILL", "EW", "SEC_SIZE", 10.0),
    ("ZERO_FILL_VW_10bp", "ZERO_FILL", "VW", "NONE", 10.0),
    ("ZERO_FILL_VW_SecNeut_10bp", "ZERO_FILL", "VW", "SECTOR", 10.0),
    ("REP_ONLY_EW_10bp", "REP_ONLY", "EW", "NONE", 10.0),
    ("REP_ONLY_SecNeut_10bp", "REP_ONLY", "EW", "SECTOR", 10.0),
]
for name, um, wm, nm, cb in configs:
    r, sr = eval_buybacks(um, wm, nm, cb)
    bb_results[name] = r
    bb_series[name] = sr
    print(f"  {name:<26} n={r['n_avg']:>5} | All={r['all']['sharpe']:+.3f} (CAGR {r['all']['cagr']:+.1f}%, DD {r['all']['dd']:+.1f}%) | <2020={r['is_pre2020']['sharpe']:+.3f} | >=2020={r['oos_2020p']['sharpe']:+.3f}", flush=True)
    if "quintiles_ann_ret_pct" in r:
        print(f"    Quintiles AnnRet%: {r['quintiles_ann_ret_pct']}", flush=True)
print("  ZERO_FILL_SecNeut yearly:", bb_results["ZERO_FILL_SecNeut_10bp"]["yearly"], flush=True)
print("  ZERO_FILL_EW_10bp yearly:", bb_results["ZERO_FILL_EW_10bp"]["yearly"], flush=True)

# Check correlations against SPY & EXP-0033 / EXP-0038 if available
spy = pd.read_csv(f"{ROOT}/data/etfs_tiingo/SPY.csv", parse_dates=["date"]).set_index("date")["adjclose"].pct_change()
print("  Corr w/ SPY: EW_10bp=", round(float(bb_series["ZERO_FILL_EW_10bp"].corr(spy)), 3),
      "SecNeut=", round(float(bb_series["ZERO_FILL_SecNeut_10bp"].corr(spy)), 3), flush=True)

# -------------------------------------------------------------------------
# PART 2: SURVIVORSHIP-FREE, ZERO-TRUNCATION SEC 8-K (2013-2026)
# -------------------------------------------------------------------------
print("\n=== PART 2: COMPLETE PIT S&P 500 SEC 8-K EVENT STUDY & CALENDAR PORTFOLIOS (2013-2026) ===", flush=True)
e8 = pd.read_csv(f"{ROOT}/data/sec/sec_8k_sp500_full_pit.csv.gz")
e8["date"] = pd.to_datetime(e8["filing_date"], errors="coerce") + pd.Timedelta(days=1)  # strictly next trading day!
e8 = e8[(e8["date"] >= "2013-01-01") & (e8["date"] <= "2026-09-30")].dropna(subset=["date", "cik"]).copy()
e8["cik"] = e8["cik"].astype(int)

# Map each (date, cik) -> active PIT S&P 500 sid on that date!
# First build active PIT mapping (day_pos, cik) -> sid
cik_day_sid = {}
for sid in range(N_S):
    ck = sid_to_cik[sid]
    if ck <= 0: continue
    days_on = np.where(PIT_MASK[:, sid])[0]
    if len(days_on) > 0:
        cik_day_sid[ck] = cik_day_sid.get(ck, [])
        cik_day_sid[ck].append((days_on[0], days_on[-1], sid))

# Build PIT S&P 500 daily EW return
ew_sp500 = np.nanmean(np.where(PIT_MASK & (U_MAT >= 5.0), R_MAT, np.nan), axis=1)
ew_sp500 = np.nan_to_num(ew_sp500, nan=0.0)

def resolve_event_pos_sid(dt64, ck):
    pos = int(np.searchsorted(all_dates, dt64, side="left"))
    if pos >= N_D: return None, None
    spans = cik_day_sid.get(ck)
    if not spans: return None, None
    for d0, d1, sid in spans:
        if d0 <= pos <= d1 and PIT_MASK[pos, sid] and U_MAT[pos, sid] >= 5.0:
            return pos, sid
    return None, None

# Attach exact (pos, sid) strictly inside PIT S&P 500!
pos_arr, sid_arr = [], []
for dt_v, ck_v in zip(e8["date"].values, e8["cik"].values):
    p, s = resolve_event_pos_sid(dt_v, int(ck_v))
    pos_arr.append(-1 if p is None else p)
    sid_arr.append(-1 if s is None else s)
e8["pos"] = pos_arr
e8["sid"] = sid_arr
e8_pit = e8[e8["pos"] >= 0].copy()
print(f"Total 8-Ks strictly while in PIT S&P 500 (2013-2026): {len(e8_pit)} across {e8_pit['cik'].nunique()} CIKs", flush=True)

item_defs = {
    "Item_5.02_All": e8_pit["items"].str.contains("5.02", na=False),
    "Item_5.02_PureNo202": e8_pit["items"].str.contains("5.02", na=False) & (~e8_pit["items"].str.contains("2.02", na=False)),
    "Item_1.01_MatAgree": e8_pit["items"].str.contains("1.01", na=False),
    "Item_2.02_Earnings": e8_pit["items"].str.contains("2.02", na=False),
    "Item_2.05_2.06_Restruct": e8_pit["items"].str.contains("2.05|2.06", na=False, regex=True),
    "Item_4.02_Restate": e8_pit["items"].str.contains("4.02", na=False),
    "Item_8.01_Other": e8_pit["items"].str.contains("8.01", na=False) & (~e8_pit["items"].str.contains("2.02|5.02", na=False, regex=True)),
}

ev_res = {}
for nm, mask in item_defs.items():
    sub = e8_pit[mask].drop_duplicates(["pos", "sid"])
    if len(sub) < 30:
        print(f"  {nm:<24} n={len(sub)} (too small)", flush=True)
        continue
    row_r = {"n": len(sub)}
    for h in [5, 21, 42, 63]:
        exs = []
        yrs = []
        for p0, sd in zip(sub["pos"].values, sub["sid"].values):
            if p0 + h >= N_D: continue
            sr = float(np.prod(1.0 + R_MAT[p0:p0+h, sd]) - 1.0)
            er = float(np.prod(1.0 + ew_sp500[p0:p0+h]) - 1.0)
            exs.append(sr - er)
            yrs.append(all_dates[p0].year)
        a = np.array(exs)
        ya = np.array(yrs)
        m_pct = float(a.mean() * 100)
        t_st = float(a.mean() / (a.std(ddof=1) / np.sqrt(len(a)))) if len(a) > 5 else 0.0
        is_m = float(a[ya < 2020].mean() * 100) if (ya < 2020).any() else 0.0
        oos_m = float(a[ya >= 2020].mean() * 100) if (ya >= 2020).any() else 0.0
        row_r[f"{h}d"] = {"mean_pct": round(m_pct, 3), "t": round(t_st, 2), "is_pct": round(is_m, 3), "oos_pct": round(oos_m, 3)}
    ev_res[nm] = row_r
    print(f"  {nm:<24} n={len(sub):>5} | 5d={row_r['5d']['mean_pct']:+.3f}% (t={row_r['5d']['t']:+.2f}) | 21d={row_r['21d']['mean_pct']:+.3f}% (t={row_r['21d']['t']:+.2f}) | 42d={row_r['42d']['mean_pct']:+.3f}% (t={row_r['42d']['t']:+.2f}) | 63d={row_r['63d']['mean_pct']:+.3f}% (t={row_r['63d']['t']:+.2f} IS={row_r['63d']['is_pct']:+.2f} OOS={row_r['63d']['oos_pct']:+.2f})", flush=True)

# Calendar-Time Portfolios for Item 5.02 (All & Pure) vs PIT S&P 500 EW (10bp/side + 50bp/yr borrow)
cal_8k = {}
start_cal = np.searchsorted(all_dates, np.datetime64("2013-01-01"))
for nm in ["Item_5.02_All", "Item_5.02_PureNo202"]:
    sub = e8_pit[item_defs[nm]].drop_duplicates(["pos", "sid"])
    for h in [5, 21, 42]:
        w_s = np.zeros((N_D, N_S), dtype=np.float32)
        for p0, sd in zip(sub["pos"].values, sub["sid"].values):
            p1 = min(N_D, p0 + h)
            w_s[p0:p1, sd] = 1.0
        # normalize short leg within PIT_MASK & >=$5
        w_s = np.where(PIT_MASK & (U_MAT >= 5.0), w_s, 0.0)
        rs = w_s.sum(axis=1, keepdims=True)
        act = (rs[:, 0] >= 5)  # require at least 5 active names on short side
        w_short = np.divide(w_s, np.maximum(1.0, rs))
        # long leg = PIT S&P 500 EW excluding shorted names (or full EW)
        w_l = np.where(PIT_MASK & (U_MAT >= 5.0) & (w_s == 0), 1.0, 0.0)
        w_long = np.divide(w_l, np.maximum(1.0, w_l.sum(axis=1, keepdims=True)))
        # turnover per side
        to_l = 0.5 * np.abs(np.diff(w_long, axis=0, prepend=0.0)).sum(axis=1)
        to_s = 0.5 * np.abs(np.diff(w_short, axis=0, prepend=0.0)).sum(axis=1)
        r_long = (w_long * R_MAT).sum(axis=1)
        r_short = (w_short * R_MAT).sum(axis=1)
        net_d = np.where(act, 0.5 * (r_long - r_short) + rf_arr - 0.5 * (to_l + to_s) * 2.0 * 10.0 / 10000.0 - 0.5 * (0.0050 / 252.0), 0.0)
        s = pd.Series(net_d[start_cal:], index=all_dates[start_cal:])
        s = s[s.index <= "2026-09-30"]
        sh_all = float((s.mean() / max(1e-12, s.std(ddof=1))) * np.sqrt(252.0))
        sh_is = float((s[s.index.year < 2020].mean() / max(1e-12, s[s.index.year < 2020].std(ddof=1))) * np.sqrt(252.0))
        sh_oos = float((s[s.index.year >= 2020].mean() / max(1e-12, s[s.index.year >= 2020].std(ddof=1))) * np.sqrt(252.0))
        dd = float(((1 + s).cumprod() / (1 + s).cumprod().cummax() - 1).min() * 100)
        key = f"{nm}_{h}d"
        cal_8k[key] = {"active_pct": round(float(act[start_cal:].mean()*100), 1), "all": round(sh_all, 3), "dd": round(dd, 2), "is": round(sh_is, 3), "oos": round(sh_oos, 3)}
        print(f"  CalShort {key:<26} act={cal_8k[key]['active_pct']:>5.1f}% | All={sh_all:+.3f} (DD {dd:+.1f}%) | IS={sh_is:+.3f} | OOS={sh_oos:+.3f}", flush=True)

out = {"buybacks_full_sp500": bb_results, "sec_8k_events": ev_res, "sec_8k_calendar": cal_8k}
json.dump(out, open(f"{ROOT}/research/artifacts/exp0054c_full_sp500_audit.json", "w"), indent=2)
print("Saved exp0054c_full_sp500_audit.json", flush=True)
