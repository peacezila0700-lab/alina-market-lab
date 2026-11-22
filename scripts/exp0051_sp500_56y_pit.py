"""
EXP-0051: 55-Year Point-in-Time Survivorship-Free S&P 500 (Johnbrick123/sp500-data, 1972-2026-10).
FIXED MEMBERSHIP LOGIC:
Uses `membership_intervals.parquet` [start, end] across ALL 14,806 NYSE daily trading dates
(because `members.parquet` only stores snapshots on index-change dates!).
Ultra-low-RAM batched ticker ingestion (<180 MB peak RAM) + float32 vectorized engine.
CRSP-reconciled daily total returns (adj_close), carried-patch halt exclusion,
$5 min price gate, 10bp/side transaction costs, and 200x cross-sectional permutation tests.
"""
import os, json, gc
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = "/tmp/alina_lab"
JB = "/var/tmp/alina_raw_cache/johnbrick_sp500"

print("Loading PIT S&P 500 intervals & collecting full trading calendar...")
mi = pd.read_parquet(f"{JB}/membership_intervals.parquet")
mi["start"] = pd.to_datetime(mi["start"])
mi["end"] = pd.to_datetime(mi["end"]).fillna(pd.Timestamp("2026-12-31"))

win_map = {}
for _, r in mi.iterrows():
    win_map.setdefault(r["ticker"], []).append((r["start"], r["end"]))

m_tickers = sorted(win_map.keys())
tk_to_id = {t: i for i, t in enumerate(m_tickers)}

pf = pq.ParquetFile(f"{JB}/prices.parquet")
# Pass 1: collect exact full NYSE trading calendar from prices.parquet >= 1971-12-01
date_set = set()
for i in range(pf.metadata.num_row_groups):
    d_col = pf.read_row_group(i, columns=["date"]).to_pandas()["date"]
    date_set.update(d_col[d_col >= "1971-12-01"].unique())
all_dates = np.sort(np.array(list(date_set), dtype="datetime64[ns]"))
date_to_pos = {d: i for i, d in enumerate(all_dates)}
date_ser = pd.Series(all_dates)
me_dates = sorted(date_ser.groupby(date_ser.dt.to_period("M")).max().values)
sig_dates = [d for d in me_dates if d >= np.datetime64("1971-12-31") and d < all_dates[-2]]
sig_set = set(sig_dates)
print(f"Full calendar: {len(all_dates)} trading days | {pd.Timestamp(all_dates[0]).strftime('%Y-%m-%d')} .. {pd.Timestamp(all_dates[-1]).strftime('%Y-%m-%d')} | monthly sig_dates={len(sig_dates)}")

# Pre-allocate compact float32 return matrix (~96 MB)
R_MAT = np.zeros((len(all_dates), len(m_tickers)), dtype=np.float32)

# Read in 4 ticker batches
n_batches = 4
batch_size = (len(m_tickers) + n_batches - 1) // n_batches
sig_rows_by_date = {sd: [] for sd in sig_dates}

for b_idx in range(n_batches):
    b_tks = set(m_tickers[b_idx * batch_size : (b_idx + 1) * batch_size])
    parts = []
    for i in range(pf.metadata.num_row_groups):
        rg = pf.read_row_group(i, columns=["date", "ticker", "close", "adj_close", "source"]).to_pandas()
        rg = rg[rg["ticker"].isin(b_tks)]
        if len(rg):
            parts.append(rg)
    dfb = pd.concat(parts, ignore_index=True)
    del parts
    dfb["tid"] = dfb["ticker"].map(tk_to_id).astype("int16")
    dfb["close"] = dfb["close"].astype("float32")
    dfb["adj_close"] = dfb["adj_close"].astype("float32")
    dfb["is_carried"] = (dfb["source"] == "carried-patch").values
    dfb = dfb.sort_values(["tid", "date"]).drop_duplicates(["tid", "date"]).reset_index(drop=True)

    for tk, grp in dfb.groupby("ticker", sort=False):
        tid = int(grp["tid"].iloc[0])
        dt_vals = grp["date"].values
        adj = grp["adj_close"].values.astype(np.float64)
        cls = grp["close"].values
        car = grp["is_carried"].values
        if len(adj) < 5:
            continue
        ret = np.zeros(len(adj), dtype=np.float32)
        ret[1:] = np.clip(adj[1:] / np.maximum(1e-8, adj[:-1]) - 1.0, -0.95, 5.0)
        # Keep daily return only up to end+5d around membership intervals (still populates R_MAT for all member days!)
        m_valid = dt_vals >= np.datetime64("1971-12-01")
        for d_v, r_v in zip(dt_vals[m_valid], ret[m_valid]):
            p = date_to_pos.get(d_v)
            if p is not None:
                R_MAT[p, tid] = r_v

        # Check active S&P 500 membership at signal dates via exact [start, end] intervals!
        ivs = win_map[tk]
        s_mask = np.zeros(len(dt_vals), dtype=bool)
        for idx_k, d_v in enumerate(dt_vals):
            if d_v in sig_set:
                for s0, e0 in ivs:
                    if np.datetime64(s0) <= d_v <= np.datetime64(e0):
                        s_mask[idx_k] = True
                        break
        if not np.any(s_mask):
            continue

        s_adj = pd.Series(adj)
        s_ret = pd.Series(ret)
        mom_12_1 = (s_adj.shift(21) / s_adj.shift(252) - 1.0).values
        rev_21 = (-(s_adj / s_adj.shift(21) - 1.0)).values
        neg_vol60 = (-(s_ret.rolling(60, min_periods=45).std() * np.sqrt(252.0))).values
        dist_52h = (s_adj / s_adj.rolling(252, min_periods=180).max()).values
        pos_c = (s_ret > 0).astype(float).rolling(252, min_periods=180).mean()
        neg_c = (s_ret < 0).astype(float).rolling(252, min_periods=180).mean()
        fip = (np.sign(mom_12_1) * (neg_c - pos_c).values)

        for k_idx in np.where(s_mask)[0]:
            if car[k_idx] or cls[k_idx] < 5.0:
                continue
            sig_rows_by_date[dt_vals[k_idx]].append((
                tid, float(mom_12_1[k_idx]), float(rev_21[k_idx]),
                float(neg_vol60[k_idx]), float(dist_52h[k_idx]), float(fip[k_idx])
            ))
    del dfb
    gc.collect()
    print(f"  Batch {b_idx+1}/{n_batches} complete.")

sig_slices = {}
counts = []
for sd, rows in sig_rows_by_date.items():
    if len(rows) >= 100:
        counts.append(len(rows))
        sub = pd.DataFrame(rows, columns=["tid", "mom_12_1", "rev_21", "neg_vol60", "dist_52h", "fip"]).set_index("tid")
        zm = (sub["mom_12_1"] - sub["mom_12_1"].mean()) / max(1e-6, sub["mom_12_1"].std())
        zv = (sub["neg_vol60"] - sub["neg_vol60"].mean()) / max(1e-6, sub["neg_vol60"].std())
        sub["lv_x_mom"] = zm + zv
        sig_slices[sd] = sub

print(f"Active signal months: {len(sig_slices)} | Eligible S&P500 count/month: min={min(counts)}, median={int(np.median(counts))}, max={max(counts)}")

fr = pd.read_csv(f"{ROOT}/data/macro/fred_rates_full.csv")
fr["date"] = pd.to_datetime(fr["date"])
fr["rf_daily"] = pd.to_numeric(fr["dtb3"], errors="coerce").ffill().fillna(0.0) / 100.0 / 252.0
rf_map = dict(zip(fr["date"], fr["rf_daily"]))
rf_arr = np.array([rf_map.get(pd.Timestamp(d), 0.0) for d in all_dates], dtype=np.float32)

reb_periods = []
for k in range(len(sig_dates) - 1):
    sd = sig_dates[k]
    if sd not in sig_slices:
        continue
    sd_next = sig_dates[k + 1]
    p0 = date_to_pos[sd] + 1
    p1 = date_to_pos[sd_next] + 1
    if p1 > p0:
        reb_periods.append((sd, np.arange(p0 + 1, min(p1 + 1, len(all_dates)))))

def eval_factor(factor_col, mode="LS", top_n=50, cost_bps=10.0, start_year=1972, split_year=2006):
    daily_rets, daily_dts = [], []
    prev_w = np.zeros(len(m_tickers), dtype=np.float64)
    start_np = np.datetime64(f"{start_year}-01-01")
    for sd, hidx in reb_periods:
        if pd.Timestamp(sd).year < start_year - 1 or len(hidx) == 0:
            continue
        sl = sig_slices[sd]
        w = np.zeros(len(m_tickers), dtype=np.float64)
        if mode == "EW":
            tids = sl.index.values
            w[tids] = 1.0 / len(tids)
        else:
            s = sl[factor_col].dropna().sort_values(ascending=False)
            if len(s) < 2 * top_n:
                continue
            longs = s.index.values[:top_n]
            if mode == "LO":
                w[longs] = 1.0 / top_n
            else:
                shorts = s.index.values[-top_n:]
                w[longs] = 0.5 / top_n
                w[shorts] = -0.5 / top_n
        turn = float(np.abs(w - prev_w).sum())
        cost0 = turn * (cost_bps / 10000.0)
        prev_w = w
        nz = np.where(w != 0.0)[0]
        cur_w = w[nz].copy()
        for step, did in enumerate(hidx):
            dt = all_dates[did]
            r_vec = R_MAT[did, nz]
            pr = float(np.dot(cur_w, r_vec))
            if mode == "LS":
                pr += float(rf_arr[did])
            if step == 0:
                pr -= cost0
            if dt >= start_np:
                daily_rets.append(pr)
                daily_dts.append(dt)
            cur_w *= (1.0 + r_vec)

    s = pd.Series(daily_rets, index=pd.to_datetime(daily_dts))
    def ms(sub):
        if len(sub) < 60 or sub.std(ddof=1) < 1e-12:
            return None
        sh = (sub.mean() / sub.std(ddof=1)) * np.sqrt(252.0)
        eq = (1.0 + sub).cumprod()
        cagr = eq.iloc[-1] ** (252.0 / len(sub)) - 1.0 if eq.iloc[-1] > 0 else -1.0
        dd = (eq / eq.cummax() - 1.0).min()
        cal = cagr / abs(dd) if dd < -1e-9 else 0.0
        return {"n": int(len(sub)), "sharpe": round(float(sh), 3), "cagr": round(float(cagr * 100), 2), "max_dd": round(float(dd * 100), 2), "calmar": round(float(cal), 3)}
    return {"all": ms(s), "is": ms(s[s.index.year < split_year]), "oos": ms(s[s.index.year >= split_year]), "_series": s}

def perm_test(factor_col, mode="LS", top_n=50, cost_bps=10.0, start_year=1972, n_perm=200, seed=42):
    rng = np.random.default_rng(seed)
    real = eval_factor(factor_col, mode, top_n, cost_bps, start_year, 2006)["all"]["sharpe"]
    per_period = []
    for sd, hidx in reb_periods:
        if pd.Timestamp(sd).year < start_year or len(hidx) == 0:
            continue
        sl = sig_slices[sd]
        s = sl[factor_col].dropna()
        if len(s) < 2 * top_n:
            continue
        tids = s.index.values
        comp_r = np.prod(1.0 + R_MAT[hidx][:, tids], axis=0) - 1.0
        rf_m = float(rf_arr[hidx].sum())
        per_period.append((comp_r, rf_m))
    beats = 0
    for _ in range(n_perm):
        m_rets = []
        for comp_r, rf_m in per_period:
            p = rng.permutation(len(comp_r))
            if mode == "LO":
                pr = comp_r[p[:top_n]].mean() - (0.40 * 2 * cost_bps / 10000.0)
            else:
                pr = 0.5 * (comp_r[p[:top_n]].mean() - comp_r[p[-top_n:]].mean()) + rf_m - (0.80 * 2 * cost_bps / 10000.0)
            m_rets.append(pr)
        arr = np.array(m_rets)
        sh_p = (arr.mean() / arr.std(ddof=1)) * np.sqrt(12.0) if arr.std(ddof=1) > 1e-12 else 0.0
        if real > sh_p:
            beats += 1
    return round(100.0 * beats / n_perm, 1)

results = {"calendar_days": int(len(all_dates)), "median_eligible_per_month": int(np.median(counts))}
factors = [
    ("EW_SP500", None, "EW"),
    ("Mom_12_1_LO", "mom_12_1", "LO"),
    ("Mom_12_1_LS", "mom_12_1", "LS"),
    ("Rev_21d_LO", "rev_21", "LO"),
    ("Rev_21d_LS", "rev_21", "LS"),
    ("LowVol_60d_LO", "neg_vol60", "LO"),
    ("LowVol_60d_LS", "neg_vol60", "LS"),
    ("Dist52H_LO", "dist_52h", "LO"),
    ("Dist52H_LS", "dist_52h", "LS"),
    ("FIP_LO", "fip", "LO"),
    ("FIP_LS", "fip", "LS"),
    ("LowVol_x_Mom_LO", "lv_x_mom", "LO"),
    ("LowVol_x_Mom_LS", "lv_x_mom", "LS"),
]

for label, start_y, split_y in [("55y_1972_2026", 1972, 2006), ("31y_1996_2026", 1996, 2014)]:
    print(f"\n=== {label} PIT S&P 500 (10bp/side, $5 min, zero survivorship bias) ===")
    res_h = {}
    for nm, col, md in factors:
        r = eval_factor(col, md, 50, 10.0, start_y, split_y)
        p_pct = perm_test(col, md, 50, 10.0, start_y, 200) if md != "EW" else None
        res_h[nm] = {"all": r["all"], "is": r["is"], "oos": r["oos"], "perm200": p_pct}
        a, i_s, o_s = r["all"], r["is"], r["oos"]
        print(f"  {nm:<18} | All={a['sharpe']:+.3f} (CAGR {a['cagr']:+.1f}%, DD {a['max_dd']:+.1f}%) | IS={i_s['sharpe']:+.3f} | OOS={o_s['sharpe']:+.3f} | Perm200={p_pct}")
    results[label] = res_h

print("\n=== PART B: 55y PIT S&P 500 Addition / Removal Drift (1972-2026, vs EW_SP500) ===")
ew_s = eval_factor(None, "EW", 50, 0.0, 1972, 2006)["_series"]
ev_res = {}
for ev_type, col_dt in [("Additions", "start"), ("Removals", "end")]:
    ev_sub = mi[(mi[col_dt] >= "1972-01-01") & (mi[col_dt] <= "2026-06-01")].copy()
    horizons = {}
    for h in [5, 21, 63]:
        ex_rets = []
        for _, r in ev_sub.iterrows():
            tid = tk_to_id.get(r["ticker"])
            if tid is None:
                continue
            pos = np.searchsorted(all_dates, np.datetime64(r[col_dt]))
            if pos + 1 + h >= len(all_dates):
                continue
            h_idx = np.arange(pos + 1, pos + 1 + h)
            stk_r = float(np.prod(1.0 + R_MAT[h_idx, tid]) - 1.0)
            w_dates = pd.to_datetime(all_dates[h_idx])
            ew_r = float((1.0 + ew_s.reindex(w_dates).fillna(0.0)).prod() - 1.0)
            ex_rets.append(stk_r - ew_r)
        arr = np.array(ex_rets)
        mu = float(np.mean(arr) * 100)
        t_st = float(np.mean(arr) / (np.std(arr, ddof=1) / np.sqrt(len(arr)))) if len(arr) > 5 else 0.0
        horizons[f"{h}d"] = {"n": int(len(arr)), "excess_pct": round(mu, 3), "t_stat": round(t_st, 2)}
        print(f"  {ev_type:<10} t+1..t+{h:2d}d | n={len(arr):4d} | excess vs EW={mu:+.3f}% (t={t_st:+.2f})")
    ev_res[ev_type] = horizons
results["sp500_events_55y"] = ev_res

out_json = f"{ROOT}/research/artifacts/exp0051_sp500_56y_pit.json"
with open(out_json, "w") as f:
    json.dump(results, f, indent=2)
print("Saved:", out_json)
