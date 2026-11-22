"""
EXP-0051b: Deep Falsification of the Two Candidate Findings in EXP-0051:
1) Is LowVol_60d_LO truly adding alpha over Vol-Targeted EW_SP500 / SPY (VT12% + DTB3 cash)?
2) Does S&P 500 Addition Post-Effective Reversal (t+1..t+21d, n=1,257) hold in modern OOS (2014-2026) and survive realistic short-portfolio trading?
"""
import os, json, gc
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = "/tmp/alina_lab"
JB = "/var/tmp/alina_raw_cache/johnbrick_sp500"

mi = pd.read_parquet(f"{JB}/membership_intervals.parquet")
mi["start"] = pd.to_datetime(mi["start"])
mi["end"] = pd.to_datetime(mi["end"]).fillna(pd.Timestamp("2026-12-31"))
win_map = {}
for _, r in mi.iterrows():
    win_map.setdefault(r["ticker"], []).append((r["start"], r["end"]))
m_tickers = sorted(win_map.keys())
tk_to_id = {t: i for i, t in enumerate(m_tickers)}

pf = pq.ParquetFile(f"{JB}/prices.parquet")
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

R_MAT = np.zeros((len(all_dates), len(m_tickers)), dtype=np.float32)
sig_rows_by_date = {sd: [] for sd in sig_dates}
n_batches = 4
batch_size = (len(m_tickers) + n_batches - 1) // n_batches

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
        m_valid = dt_vals >= np.datetime64("1971-12-01")
        for d_v, r_v in zip(dt_vals[m_valid], ret[m_valid]):
            p = date_to_pos.get(d_v)
            if p is not None:
                R_MAT[p, tid] = r_v
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
        s_ret = pd.Series(ret)
        neg_vol60 = (-(s_ret.rolling(60, min_periods=45).std() * np.sqrt(252.0))).values
        for k_idx in np.where(s_mask)[0]:
            if not car[k_idx] and cls[k_idx] >= 5.0:
                sig_rows_by_date[dt_vals[k_idx]].append((tid, float(neg_vol60[k_idx])))
    del dfb
    gc.collect()

sig_slices = {sd: pd.DataFrame(rows, columns=["tid", "neg_vol60"]).set_index("tid") for sd, rows in sig_rows_by_date.items() if len(rows) >= 100}

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
    p0 = date_to_pos[sd] + 1
    p1 = date_to_pos[sig_dates[k + 1]] + 1
    if p1 > p0:
        reb_periods.append((sd, np.arange(p0 + 1, min(p1 + 1, len(all_dates)))))

def build_series(mode, cost_bps=10.0):
    rets, dts = [], []
    prev_w = np.zeros(len(m_tickers))
    for sd, hidx in reb_periods:
        if len(hidx) == 0:
            continue
        sl = sig_slices[sd]
        w = np.zeros(len(m_tickers))
        if mode == "EW":
            tids = sl.index.values
            w[tids] = 1.0 / len(tids)
        else:
            s = sl["neg_vol60"].dropna().sort_values(ascending=False)
            tids = s.index.values[:50]
            w[tids] = 1.0 / 50.0
        cost0 = float(np.abs(w - prev_w).sum()) * (cost_bps / 10000.0)
        prev_w = w
        nz = np.where(w != 0.0)[0]
        cur_w = w[nz].copy()
        for step, did in enumerate(hidx):
            pr = float(np.dot(cur_w, R_MAT[did, nz])) - (cost0 if step == 0 else 0.0)
            rets.append(pr)
            dts.append(all_dates[did])
            cur_w *= (1.0 + R_MAT[did, nz])
    return pd.Series(rets, index=pd.to_datetime(dts))

ew = build_series("EW", 10.0)
lv = build_series("LV", 10.0)
rf_s = pd.Series([rf_map.get(d, 0.0) for d in ew.index], index=ew.index)

def apply_vt12(r_s):
    vol = r_s.ewm(span=20, min_periods=15).std() * np.sqrt(252.0)
    w = (0.12 / vol.clip(lower=0.04)).clip(upper=1.0).shift(1).fillna(0.0)
    dw = w.diff().abs().fillna(0.0)
    return w * r_s + (1.0 - w) * rf_s - dw * (10.0 / 10000.0)

ew_vt = apply_vt12(ew)
lv_vt = apply_vt12(lv)

def stats(s):
    sh = (s.mean() / s.std(ddof=1)) * np.sqrt(252.0)
    eq = (1.0 + s).cumprod()
    cagr = eq.iloc[-1] ** (252.0 / len(s)) - 1.0
    dd = (eq / eq.cummax() - 1.0).min()
    cal = cagr / abs(dd)
    return {"sharpe": round(float(sh), 3), "cagr": round(float(cagr * 100), 2), "max_dd": round(float(dd * 100), 2), "calmar": round(float(cal), 3), "vol": round(float(s.std(ddof=1)*np.sqrt(252)*100), 2)}

print("\n=== CHECK 1: Vol-Target 12% Comparison (1972-2026 & 1996-2026 & 2014-2026) ===")
vt_res = {}
for era, mask in [("55y_1972_2026", ew.index.year >= 1972), ("31y_1996_2026", ew.index.year >= 1996), ("OOS_2014_2026", ew.index.year >= 2014)]:
    vt_res[era] = {}
    print(f"\n[{era}]")
    for nm, sr in [("EW_SP500", ew[mask]), ("EW_SP500_VT12", ew_vt[mask]), ("LowVol60_LO", lv[mask]), ("LowVol60_LO_VT12", lv_vt[mask])]:
        st = stats(sr)
        vt_res[era][nm] = st
        print(f"  {nm:<18} | Sh={st['sharpe']:+.3f} | CAGR={st['cagr']:+.2f}% | Vol={st['vol']:.1f}% | DD={st['max_dd']:+.1f}% | Calmar={st['calmar']:.3f}")

print("\n=== CHECK 2: S&P 500 Additions Post-Effective Drift by Era (vs EW_SP500) ===")
add_res = {}
for era, y0, y1 in [("1972_1995", "1972-01-01", "1995-12-31"), ("1996_2013", "1996-01-01", "2013-12-31"), ("2014_2026", "2014-01-01", "2026-06-01")]:
    sub = mi[(mi["start"] >= y0) & (mi["start"] <= y1)]
    add_res[era] = {}
    for h in [5, 21]:
        ex = []
        for _, r in sub.iterrows():
            tid = tk_to_id.get(r["ticker"])
            if tid is None:
                continue
            pos = np.searchsorted(all_dates, np.datetime64(r["start"]))
            if pos + 1 + h >= len(all_dates):
                continue
            h_idx = np.arange(pos + 1, pos + 1 + h)
            stk_r = float(np.prod(1.0 + R_MAT[h_idx, tid]) - 1.0)
            ew_r = float((1.0 + ew.reindex(pd.to_datetime(all_dates[h_idx])).fillna(0.0)).prod() - 1.0)
            ex.append(stk_r - ew_r)
        arr = np.array(ex)
        mu = float(np.mean(arr) * 100)
        t_st = float(np.mean(arr) / (np.std(arr, ddof=1) / np.sqrt(len(arr))))
        add_res[era][f"{h}d"] = {"n": int(len(arr)), "excess_pct": round(mu, 3), "t_stat": round(t_st, 2)}
        print(f"  {era} t+1..t+{h:2d}d | n={len(arr):3d} | excess vs EW={mu:+.3f}% (t={t_st:+.2f})")

with open(f"{ROOT}/research/artifacts/exp0051b_sp500_deep_check.json", "w") as f:
    json.dump({"vt12_comparison": vt_res, "additions_by_era": add_res}, f, indent=2)
