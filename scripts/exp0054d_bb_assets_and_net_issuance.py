import json, warnings
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

ROOT = "/tmp/alina_lab"
JB = "/var/tmp/alina_raw_cache/johnbrick_sp500"

mi = pd.read_parquet(f"{JB}/membership_intervals.parquet")
mi["start_dt"] = pd.to_datetime(mi["start"])
mi["end_dt"] = pd.to_datetime(mi["end"]).fillna(pd.Timestamp("2026-12-31"))
sp_mi = mi[mi["end_dt"] >= "2012-01-01"].copy()
sp_mi["ticker"] = sp_mi["ticker"].str.upper()

cik_map = pd.read_csv(f"{ROOT}/data/sec/sp500_2012_2026_cik_map.csv")
cik_map = cik_map[cik_map["cik"] > 0]
tk_to_cik = dict(zip(cik_map["ticker"].str.upper(), cik_map["cik"].astype(int)))
sec_meta = pd.read_csv(f"{ROOT}/data/sec/sp500_2012_2026_sec_meta.csv")
def sic_to_sector(sic_str):
    try: s = int(float(sic_str))
    except Exception: return "Other"
    if 2000 <= s <= 3999:
        if 2830 <= s <= 2836 or 3840 <= s <= 3851: return "Health_Bio"
        if 3570 <= s <= 3579 or 3660 <= s <= 3679 or 3810 <= s <= 3829: return "Tech_Hw"
        return "Industrials"
    if 4000 <= s <= 4999: return "Util_Trans_Tel"
    if 5000 <= s <= 5999: return "Retail_Whl"
    if 6000 <= s <= 6999: return "Financials"
    if 7000 <= s <= 8999:
        if 7370 <= s <= 7379: return "Tech_Sw"
        return "Services"
    return "Other"
cik_to_sector = {int(r["cik"]): sic_to_sector(r["sic"]) for _, r in sec_meta.iterrows()}

sp_tickers = sorted(sp_mi["ticker"].unique())
px_df = pd.read_parquet(
    f"{JB}/prices.parquet",
    columns=["date", "ticker", "close", "adj_close", "volume", "stock_splits", "source"],
    filters=[("date", ">=", pd.Timestamp("2012-01-01"))],
)
px_df["ticker"] = px_df["ticker"].str.upper()
px_df = px_df[px_df["ticker"].isin(sp_tickers)].sort_values(["ticker", "date"]).reset_index(drop=True)
px_df["y_sp"] = np.where((px_df["source"] == "yahoo") & (px_df["stock_splits"] > 0), px_df["stock_splits"], 1.0)
px_df["y_sp_next"] = px_df.groupby("ticker")["y_sp"].shift(-1).fillna(1.0)
px_df["fut_split"] = px_df.iloc[::-1].groupby("ticker")["y_sp_next"].cumprod().iloc[::-1]
px_df["unsplit_close"] = px_df["close"] * px_df["fut_split"]

all_dates = pd.DatetimeIndex(sorted(px_df["date"].unique()))
date_to_pos = {d: i for i, d in enumerate(all_dates)}
syms = sorted(px_df["ticker"].unique())
sym_to_id = {s: i for i, s in enumerate(syms)}
N_D, N_S = len(all_dates), len(syms)

R_MAT = px_df.pivot(index="date", columns="ticker", values="adj_close").reindex(index=all_dates, columns=syms).pct_change().fillna(0.0).clip(-0.95, 5.0).values.astype(np.float32)
U_MAT = px_df.pivot(index="date", columns="ticker", values="unsplit_close").reindex(index=all_dates, columns=syms).values.astype(np.float32)
V_MAT = px_df.pivot(index="date", columns="ticker", values="volume").reindex(index=all_dates, columns=syms).values.astype(np.float32)
F_MAT = px_df.pivot(index="date", columns="ticker", values="fut_split").reindex(index=all_dates, columns=syms).values.astype(np.float32)

PIT_MASK = np.zeros((N_D, N_S), dtype=bool)
for _, r in sp_mi.iterrows():
    sid = sym_to_id.get(r["ticker"])
    if sid is None: continue
    i0 = np.searchsorted(all_dates, r["start_dt"].to_datetime64(), side="left")
    i1 = np.searchsorted(all_dates, r["end_dt"].to_datetime64(), side="right")
    PIT_MASK[i0:i1, sid] = True

sid_to_cik = {sid: tk_to_cik.get(syms[sid], 0) for sid in range(N_S)}
cik_to_sids = {}
for s, sid in sym_to_id.items():
    ck = tk_to_cik.get(s, 0)
    if ck > 0: cik_to_sids.setdefault(ck, []).append(sid)
for ck, sids in cik_to_sids.items():
    if len(sids) > 1:
        dup_days = np.where(PIT_MASK[:, sids].sum(axis=1) > 1)[0]
        if len(dup_days) > 0:
            dv = np.nan_to_num(U_MAT[dup_days][:, sids] * V_MAT[dup_days][:, sids], nan=0.0)
            best = np.argmax(dv, axis=1)
            for ri, di in enumerate(dup_days):
                for cj, sid in enumerate(sids):
                    if cj != best[ri]: PIT_MASK[di, sid] = False

rf_arr = pd.read_csv(f"{ROOT}/data/macro/fred_rates_full.csv", parse_dates=["date"]).set_index("date")["dtb3"].reindex(all_dates).ffill().fillna(0.0).values / 100.0 / 252.0

bb = pd.read_csv(f"{ROOT}/data/sec/sec_buybacks_sp500_full_pit.csv.gz", low_memory=False)
bb["date"] = pd.to_datetime(bb["filed"], errors="coerce") + pd.Timedelta(days=1)
bb = bb.dropna(subset=["date", "cik", "val"]).copy()
bb["cik"] = bb["cik"].astype(int)
bb["end_s"] = bb["end"].astype(str)

sh_raw = bb[bb["metric"].isin(["shares", "dei_shares"]) & (bb["val"] > 1e5)].copy()
sh_raw["prio"] = np.where(sh_raw["metric"] == "shares", 2, 1)
sh_raw = sh_raw.sort_values(["cik", "date", "end_s", "prio"]).drop_duplicates(["cik", "date"], keep="last")

rep_raw = bb[bb["metric"].isin(["bb_cash", "bb_cash_eq", "bb_val", "bb_treas"]) & (bb["days"] >= 70) & (bb["days"] <= 400)].copy()
rep_raw["prio"] = rep_raw["metric"].map({"bb_cash": 4, "bb_val": 3, "bb_cash_eq": 2, "bb_treas": 1}).fillna(0)
rep_raw["ann_bb"] = rep_raw["val"] * (365.0 / rep_raw["days"].astype(float))
rep_raw = rep_raw.sort_values(["cik", "date", "prio", "end_s", "days"]).drop_duplicates(["cik", "date"], keep="last")

ast_raw = bb[(bb["metric"] == "assets") & (bb["val"] > 1e6)].sort_values(["cik", "date", "end_s"]).drop_duplicates(["cik", "date"], keep="last")

def build_cik_dict(df, val_col):
    d = {}
    for cik, grp in df.groupby("cik"):
        g = grp.sort_values("date")
        d[int(cik)] = (g["date"].values.astype("datetime64[ns]"), g[val_col].values.astype(np.float64))
    return d
sh_dict = build_cik_dict(sh_raw, "val")
rep_dict = build_cik_dict(rep_raw, "ann_bb")
ast_dict = build_cik_dict(ast_raw, "val")

def get_val(dic, cik, dt64, max_age=420):
    tup = dic.get(cik)
    if tup is None: return None
    dts, vals = tup
    idx = np.searchsorted(dts, dt64, side="right") - 1
    if idx < 0 or ((dt64 - dts[idx]) / np.timedelta64(1, "D")) > max_age: return None
    return float(vals[idx])

# Also compute split-adjusted market cap at p0 vs p0-252 (using unsplit_close * shares = TRUE market cap, then shares_split_adj = mcap / split_adj_close!)
# Actually even cleaner: TRUE shares on current split basis = (unsplit_close * shares) / split_adj_close = shares * fut_split!
dt_series = pd.Series(all_dates, index=all_dates)
month_ends = dt_series.resample("ME").last().dropna()
month_ends = month_ends[(month_ends >= "2012-12-01") & (month_ends <= "2026-09-30")].values
reb_pos = [date_to_pos[pd.Timestamp(d)] for d in month_ends]

res_54d = {}
for metric_name in ["bb_to_assets", "bb_to_assets_secneut", "net_share_red_yoy", "net_share_red_secneut"]:
    daily_ls, daily_dates = [], []
    for k in range(len(reb_pos) - 1):
        p0, p1 = reb_pos[k], reb_pos[k + 1]
        dt_ts = pd.Timestamp(all_dates[p0])
        if dt_ts.year < 2013: continue
        dt64 = np.datetime64(dt_ts)
        dt64_1y = np.datetime64(dt_ts - pd.Timedelta(days=365))
        p0_1y = max(0, np.searchsorted(all_dates, dt64_1y, side="left"))
        rows = []
        for sid in np.where(PIT_MASK[p0])[0]:
            ck = sid_to_cik[sid]
            if ck <= 0 or not np.isfinite(U_MAT[p0, sid]) or U_MAT[p0, sid] < 5.0: continue
            sec = cik_to_sector.get(ck, "Other")
            if "bb_to_assets" in metric_name:
                ast = get_val(ast_dict, ck, dt64, 420)
                if ast is None: continue
                ann_bb = get_val(rep_dict, ck, dt64, 420) or 0.0
                val = ann_bb / ast
                if not (-0.05 <= val <= 0.50): continue
            else:
                sh0 = get_val(sh_dict, ck, dt64, 420)
                sh1 = get_val(sh_dict, ck, dt64_1y, 420)
                if sh0 is None or sh1 is None or sh1 <= 1e5: continue
                # adjust both to today's split basis via F_MAT!
                s0_adj = sh0 * (float(F_MAT[p0, sid]) if np.isfinite(F_MAT[p0, sid]) else 1.0)
                s1_adj = sh1 * (float(F_MAT[p0_1y, sid]) if np.isfinite(F_MAT[p0_1y, sid]) else 1.0)
                val = -(s0_adj / s1_adj - 1.0)
                if not (-0.35 <= val <= 0.35): continue
            rows.append((sid, val, sec))
        if len(rows) < 100: continue
        df_m = pd.DataFrame(rows, columns=["sid", "val", "sec"])
        if "secneut" in metric_name:
            df_m["sig"] = df_m.groupby("sec")["val"].transform(lambda s: s - s.mean() if len(s) >= 5 else s - df_m["val"].mean())
        else:
            df_m["sig"] = df_m["val"]
        df_m = df_m.sort_values("sig").reset_index(drop=True)
        nq = max(10, int(round(len(df_m) * 0.20)))
        h_idx = np.arange(p0 + 1, p1 + 1)
        r_l = R_MAT[h_idx][:, df_m.iloc[-nq:]["sid"].values].mean(axis=1)
        r_s = R_MAT[h_idx][:, df_m.iloc[:nq]["sid"].values].mean(axis=1)
        ls_d = 0.5 * (r_l - r_s) + rf_arr[h_idx]
        ls_d[0] -= 2.0 * 10.0 / 10000.0
        daily_ls.extend(ls_d.tolist())
        daily_dates.extend(all_dates[h_idx])
    s = pd.Series(daily_ls, index=pd.DatetimeIndex(daily_dates))
    sh_all = float((s.mean() / s.std(ddof=1)) * np.sqrt(252.0))
    sh_is = float((s[s.index.year < 2020].mean() / s[s.index.year < 2020].std(ddof=1)) * np.sqrt(252.0))
    sh_oos = float((s[s.index.year >= 2020].mean() / s[s.index.year >= 2020].std(ddof=1)) * np.sqrt(252.0))
    dd = float(((1 + s).cumprod() / (1 + s).cumprod().cummax() - 1).min() * 100)
    res_54d[metric_name] = {"all": round(sh_all, 3), "dd": round(dd, 2), "is_pre2020": round(sh_is, 3), "oos_2020p": round(sh_oos, 3)}
    print(f"  {metric_name:<24} | All={sh_all:+.3f} (DD {dd:+.1f}%) | <2020={sh_is:+.3f} | >=2020={sh_oos:+.3f}")
json.dump(res_54d, open(f"{ROOT}/research/artifacts/exp0054d_bb_assets_and_net_issuance.json", "w"), indent=2)
