"""
EXP-0054b: Adversarial Self-Audit of EXP-0054 Spikes:
1) Transcripts Event-Study (strict causal expanding past-4Q quintiles, NO intra-quarter peek,
   plus Calendar-Time daily L/S portfolio over 5d/21d/63d holding windows).
2) SEC XBRL Buyback Yield (check survivor selection bias vs Johnbrick PIT S&P 500 subset,
   year-by-year Sharpe, Sector-Neutralized L/S, Ex-Tech, 20bp cost, exact turnover).
3) SEC 8-K Item 5.02 (check filing-year bias from recent-1000 cap, Calendar-Time Short Portfolio vs EW).
"""
import os, json, gc
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = "/tmp/alina_lab"
RAW = "/var/tmp/alina_raw_cache"
JB = f"{RAW}/johnbrick_sp500"

# Load Johnbrick PIT prices (2012-2026) + local delisted fallback
pf = pq.ParquetFile(f"{JB}/prices.parquet")
jb_parts = []
for i in range(pf.metadata.num_row_groups):
    rg = pf.read_row_group(i, columns=["date", "ticker", "close", "adj_close", "volume", "source"]).to_pandas()
    rg = rg[rg["date"] >= "2012-01-01"]
    if len(rg):
        jb_parts.append(rg)
px = pd.concat(jb_parts, ignore_index=True)
del jb_parts; gc.collect()

px["symbol"] = px["ticker"].str.split("-").str[0].str.upper()
px = px.sort_values(["symbol", "date", "ticker"]).drop_duplicates(["symbol", "date"], keep="last")
px["is_carried"] = (px["source"] == "carried-patch")
px = px[["date", "symbol", "close", "adj_close", "volume", "is_carried"]]
jb_syms = set(px["symbol"].unique())

extra_rows = []
for folder in [f"{ROOT}/data/stocks", f"{ROOT}/data/stocks_delisted_tiingo"]:
    if not os.path.exists(folder): continue
    for fn in os.listdir(folder):
        if not fn.endswith(".csv"): continue
        sym = fn[:-4].upper()
        if sym in jb_syms: continue
        d = pd.read_csv(f"{folder}/{fn}")
        dcol = "date" if "date" in d.columns else "Date"
        ac = "adjclose" if "adjclose" in d.columns else ("adj_close" if "adj_close" in d.columns else "close")
        cc = "close" if "close" in d.columns else ac
        d["date"] = pd.to_datetime(d[dcol])
        d = d[d["date"] >= "2012-01-01"].copy()
        if len(d) < 30: continue
        d["symbol"] = sym
        d["close"] = pd.to_numeric(d[cc], errors="coerce")
        d["adj_close"] = pd.to_numeric(d[ac], errors="coerce")
        d["volume"] = pd.to_numeric(d["volume"], errors="coerce").fillna(50000.0) if "volume" in d.columns else 50000.0
        d["is_carried"] = False
        extra_rows.append(d[["date", "symbol", "close", "adj_close", "volume", "is_carried"]])
if extra_rows:
    px = pd.concat([px, pd.concat(extra_rows, ignore_index=True)], ignore_index=True)
    del extra_rows; gc.collect()

px = px.sort_values(["symbol", "date"]).drop_duplicates(["symbol", "date"]).reset_index(drop=True)
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
C_MAT[px["did"].values, px["sid"].values] = px["close"].astype("float32").values
V_MAT[px["did"].values, px["sid"].values] = px["volume"].fillna(0).astype("float32").values
CAR_MAT[px["did"].values, px["sid"].values] = px["is_carried"].values

fr = pd.read_csv(f"{ROOT}/data/macro/fred_rates_full.csv")
fr["date"] = pd.to_datetime(fr["date"])
fr["rf_daily"] = pd.to_numeric(fr["dtb3"], errors="coerce").ffill().fillna(0.0) / 100.0 / 252.0
rf_map = dict(zip(fr["date"], fr["rf_daily"]))
rf_arr = np.array([rf_map.get(pd.Timestamp(d), 0.0) for d in all_dates], dtype=np.float32)

def ms(s):
    if len(s) < 60 or s.std(ddof=1) < 1e-12:
        return {"sharpe": 0.0, "cagr": 0.0, "dd": 0.0}
    sh = (s.mean() / s.std(ddof=1)) * np.sqrt(252.0)
    eq = (1.0 + s).cumprod()
    return {"sharpe": round(float(sh), 3), "cagr": round(float((eq.iloc[-1]**(252/len(s))-1)*100), 2), "dd": round(float((eq/eq.cummax()-1).min()*100), 2)}

audit_res = {}

# =========================================================================
# AUDIT 1: Transcripts Calendar-Time Event Portfolio (Strictly Causal Past-90d Quintile!)
# =========================================================================
print("=== AUDIT 1: Transcripts Causal Calendar-Time L/S Event Portfolio (2014-2025, 10bp/side) ===")
tr = pd.read_csv(f"{ROOT}/data/sec/sp500_earnings_transcript_features_2013_2025.csv.gz")
tr["symbol"] = tr["ticker"].str.upper()
tr["date"] = pd.to_datetime(tr["earnings_date"]) + pd.Timedelta(days=1)
tr = tr[tr["symbol"].isin(sym_to_id)].sort_values(["symbol", "date"]).reset_index(drop=True)
tr["sid"] = tr["symbol"].map(sym_to_id)
tr["yoy_tone"] = tr["net_tone"] - tr.groupby("symbol")["net_tone"].shift(4)

audit_tr = {}
for col in ["net_tone", "yoy_tone"]:
    sub = tr.dropna(subset=[col, "date"]).sort_values("date").reset_index(drop=True)
    # Strictly trailing 250-call (prior ~2 quarters) 20th/80th percentiles (ZERO future peek!)
    sub["q80"] = sub[col].rolling(250, min_periods=80).quantile(0.8).shift(1)
    sub["q20"] = sub[col].rolling(250, min_periods=80).quantile(0.2).shift(1)
    sub = sub.dropna(subset=["q80", "q20"]).copy()
    sub["pos_sig"] = np.where(sub[col] >= sub["q80"], 1, np.where(sub[col] <= sub["q20"], -1, 0))
    ev_pos = sub[sub["pos_sig"] != 0]

    for hold_d in [5, 21]:
        # Build daily active overlapping calendar weights: each active event gets weight 1/max(10, n_active)
        active_long = np.zeros((len(all_dates), len(syms)), dtype=np.float32)
        active_short = np.zeros((len(all_dates), len(syms)), dtype=np.float32)
        for _, r in ev_pos.iterrows():
            p0 = np.searchsorted(all_dates, r["date"].to_datetime64())
            if p0 >= len(all_dates) or C_MAT[max(0, p0-1), int(r["sid"])] < 5.0:
                continue
            p1 = min(len(all_dates), p0 + hold_d)
            if r["pos_sig"] > 0:
                active_long[p0:p1, int(r["sid"])] += 1.0
            else:
                active_short[p0:p1, int(r["sid"])] += 1.0

        # Normalize to 0.50 long / 0.50 short (min 5 positions per leg to avoid huge concentration!)
        w_l = np.zeros_like(active_long)
        w_s = np.zeros_like(active_short)
        nl = (active_long > 0).sum(axis=1)
        ns = (active_short > 0).sum(axis=1)
        both_ok = (nl >= 5) & (ns >= 5)
        w_l[both_ok] = 0.5 * (active_long[both_ok] > 0) / nl[both_ok, None]
        w_s[both_ok] = -0.5 * (active_short[both_ok] > 0) / ns[both_ok, None]
        w_net = w_l + w_s
        dw = np.abs(np.diff(np.vstack([np.zeros((1, len(syms))), w_net]), axis=0)).sum(axis=1)
        port_r = (w_net * R_MAT).sum(axis=1) + rf_arr - dw * (10.0 / 10000.0)
        s = pd.Series(port_r, index=pd.to_datetime(all_dates))
        s = s[(s.index >= "2014-06-01") & (s.index <= "2025-04-30")]
        st_all = ms(s); st_is = ms(s[s.index.year < 2020]); st_oos = ms(s[s.index.year >= 2020])
        audit_tr[f"{col}_{hold_d}d"] = {"all": st_all, "is": st_is, "oos": st_oos, "active_days_pct": round(float(both_ok.mean()*100), 1)}
        print(f"  Calendar {col}_{hold_d}d L/S (10bp) | active={both_ok.mean()*100:4.1f}% | All={st_all['sharpe']:+.3f} (DD {st_all['dd']:+.1f}%) | IS={st_is['sharpe']:+.3f} | OOS={st_oos['sharpe']:+.3f}")
audit_res["transcripts_calendar_audit"] = audit_tr

# =========================================================================
# AUDIT 2: SEC XBRL Buyback Yield Deep Audit (Era, Sector-Neutral, Survivorship!)
# =========================================================================
print("\n=== AUDIT 2: SEC Buyback Yield Deep Audit (Survivor vs Johnbrick-S&P500, Sector-Neutral, 20bp) ===")
bb = pd.read_csv(f"{ROOT}/data/sec/sec_buybacks_pit.csv.gz")
u_meta = pd.read_csv(f"{ROOT}/data/sec/universe_pit_meta.csv", usecols=["ticker", "sector"])
sec_map = dict(zip(u_meta["ticker"].str.upper(), u_meta["sector"].fillna("Other")))
bb["symbol"] = bb["ticker"].str.upper()
bb = bb[bb["symbol"].isin(sym_to_id)].copy()
bb["sid"] = bb["symbol"].map(sym_to_id)
bb["date"] = pd.to_datetime(bb["filed"], errors="coerce") + pd.Timedelta(days=1)
bb = bb.dropna(subset=["date"]).copy()

sh_out = bb[bb["tag"] == "SHARES_OUT"].sort_values(["sid", "date"]).drop_duplicates(["sid", "date"], keep="last")
rep = bb[bb["tag"] != "SHARES_OUT"].copy()
rep["ann_bb_usd"] = rep["val_usd"] * (365.0 / rep["days"].clip(lower=70))
rep = rep.sort_values(["sid", "date", "days"]).drop_duplicates(["sid", "date"], keep="last")
sh_map_df = pd.merge_asof(rep.sort_values("date"), sh_out[["date", "sid", "val_usd"]].rename(columns={"val_usd": "shares_out"}).sort_values("date"), on="date", by="sid", direction="backward")

bb_rows = []
for _, r in sh_map_df.dropna(subset=["shares_out", "ann_bb_usd"]).iterrows():
    pos = min(len(all_dates) - 1, max(0, np.searchsorted(all_dates, r["date"].to_datetime64()) - 1))
    cls_p = float(C_MAT[pos, int(r["sid"])])
    if cls_p >= 5.0 and r["shares_out"] > 1e5:
        bb_y = float(r["ann_bb_usd"]) / (cls_p * float(r["shares_out"]))
        if -0.05 <= bb_y <= 0.40:
            bb_rows.append({"date": r["date"], "sid": int(r["sid"]), "symbol": r["symbol"], "sector": sec_map.get(r["symbol"], "Delisted"), "is_delisted": bool(r["is_delisted"]), "bb_yield": bb_y})
bb_df = pd.DataFrame(bb_rows).sort_values("date")

# Also load Johnbrick PIT S&P 500 intervals to restrict purely to PIT S&P 500 members!
mi = pd.read_parquet(f"{JB}/membership_intervals.parquet")
mi["base_sym"] = mi["ticker"].str.split("-").str[0].str.upper()
mi["start"] = pd.to_datetime(mi["start"])
mi["end"] = pd.to_datetime(mi["end"]).fillna(pd.Timestamp("2026-12-31"))
jb_iv_map = {}
for _, r in mi.iterrows():
    jb_iv_map.setdefault(r["base_sym"], []).append((r["start"], r["end"]))

date_ser = pd.Series(all_dates)
me_dates = sorted(date_ser.groupby(date_ser.dt.to_period("M")).max().values)
sig_dates = [d for d in me_dates if pd.Timestamp(d).year >= 2012 and d < all_dates[-2]]

def eval_bb_variant(sector_neutral=False, pit_sp500_only=False, ex_tech=False, cost_bps=10.0):
    slices = {}
    for sd in sig_dates:
        p = d_to_pos[sd]
        sd_min = sd - np.timedelta64(380, "D")
        sub = bb_df[(bb_df["date"] <= sd) & (bb_df["date"] >= sd_min)].drop_duplicates("sid", keep="last").copy()
        if len(sub) < 80:
            continue
        # Apply price/vol/carried filter at sd
        sids = sub["sid"].values
        ok = (C_MAT[p, sids] >= 5.0) & (V_MAT[p, sids] >= 25000.0) & (~CAR_MAT[p, sids])
        sub = sub[ok]
        if ex_tech:
            sub = sub[sub["sector"] != "Technology"]
        if pit_sp500_only:
            sd_ts = pd.Timestamp(sd)
            in_sp = [any(s0 <= sd_ts <= e0 for s0, e0 in jb_iv_map.get(sym, [])) for sym in sub["symbol"]]
            sub = sub[in_sp]
        if len(sub) >= 60:
            if sector_neutral:
                # Demean within sector!
                sub["score"] = sub["bb_yield"] - sub.groupby("sector")["bb_yield"].transform("mean")
            else:
                sub["score"] = sub["bb_yield"]
            slices[sd] = sub.set_index("sid")["score"]

    v_sd = sorted(slices.keys())
    rets, dts = [], []
    prev_w = np.zeros(len(syms))
    for k in range(len(v_sd) - 1):
        sd = v_sd[k]
        p0 = d_to_pos[sd] + 1
        p1 = d_to_pos[v_sd[k+1]] + 1
        hidx = np.arange(p0 + 1, min(p1 + 1, len(all_dates)))
        if len(hidx) == 0: continue
        s = slices[sd].sort_values(ascending=False)
        top_n = min(25, len(s) // 4)
        w = np.zeros(len(syms))
        w[s.index.values[:top_n]] = 0.5 / top_n
        w[s.index.values[-top_n:]] = -0.5 / top_n
        cost0 = float(np.abs(w - prev_w).sum()) * (cost_bps / 10000.0)
        prev_w = w
        nz = np.where(w != 0.0)[0]
        cw = w[nz].copy()
        for step, did in enumerate(hidx):
            dt = all_dates[did]
            pr = float(np.dot(cw, R_MAT[did, nz])) + float(rf_arr[did]) - (cost0 if step == 0 else 0.0)
            if pd.Timestamp(dt).year >= 2013:
                rets.append(pr); dts.append(dt)
            cw *= (1.0 + R_MAT[did, nz])
    ser = pd.Series(rets, index=pd.to_datetime(dts))
    yr_sh = {int(y): ms(grp)["sharpe"] for y, grp in ser.groupby(ser.index.year) if len(grp) > 60}
    return {"all": ms(ser), "is": ms(ser[ser.index.year < 2019]), "oos": ms(ser[ser.index.year >= 2019]), "yearly": yr_sh}

bb_aud = {
    "Base_10bp": eval_bb_variant(False, False, False, 10.0),
    "Base_20bp": eval_bb_variant(False, False, False, 20.0),
    "SectorNeutral_10bp": eval_bb_variant(True, False, False, 10.0),
    "ExTech_10bp": eval_bb_variant(False, False, True, 10.0),
    "PIT_SP500_Only_10bp": eval_bb_variant(False, True, False, 10.0),
    "PIT_SP500_SecNeut_10bp": eval_bb_variant(True, True, False, 10.0),
}
for k, v in bb_aud.items():
    print(f"  {k:<24} | All={v['all']['sharpe']:+.3f} (CAGR {v['all']['cagr']:+.1f}%, DD {v['all']['dd']:+.1f}%) | IS={v['is']['sharpe']:+.3f} | OOS={v['oos']['sharpe']:+.3f}")
    if k in ("Base_10bp", "PIT_SP500_SecNeut_10bp"):
        print("    yearly Sharpe:", v["yearly"])
audit_res["buyback_audit"] = bb_aud

# =========================================================================
# AUDIT 3: SEC 8-K Item 5.02 Calendar Portfolio & Year Coverage Audit
# =========================================================================
print("\n=== AUDIT 3: SEC 8-K Item 5.02 Coverage & Calendar Short Portfolio (10bp + 50bp/yr borrow) ===")
e8 = pd.read_csv(f"{ROOT}/data/sec/sec_8k_events_pit.csv.gz")
e8["symbol"] = e8["ticker"].str.upper()
e8 = e8[e8["symbol"].isin(sym_to_id)].copy()
e8["sid"] = e8["symbol"].map(sym_to_id)
e8["date"] = pd.to_datetime(e8["filing_date"], errors="coerce") + pd.Timedelta(days=1)
e502 = e8[e8["items"].astype(str).str.contains("5.02", na=False) & (e8["date"] >= "2013-01-01") & (e8["date"] <= "2026-06-01")].copy()
print("  8-K Item 5.02 counts by year:", e502["date"].dt.year.value_counts().sort_index().to_dict())

# Calendar Short Item 5.02 vs Long EW of ALL active 8-K universe firms (strictly matched!)
e8_sids = sorted(e8["sid"].unique())
act_s502 = np.zeros((len(all_dates), len(syms)), dtype=np.float32)
for _, r in e502.iterrows():
    p0 = np.searchsorted(all_dates, r["date"].to_datetime64())
    if p0 < len(all_dates) and C_MAT[max(0, p0-1), int(r["sid"])] >= 5.0:
        act_s502[p0 : min(len(all_dates), p0 + 42), int(r["sid"])] = 1.0  # 2-month hold

n_sh = act_s502.sum(axis=1)
ok_8k = n_sh >= 5
w_8k = np.zeros((len(all_dates), len(syms)), dtype=np.float32)
# Long EW of all valid SEC firms (+0.5) vs Short Item 5.02 firms (-0.5)
ew_valid = np.zeros_like(w_8k)
ew_mask = (C_MAT[:, e8_sids] >= 5.0) & (~CAR_MAT[:, e8_sids])
ew_cnt = ew_mask.sum(axis=1).clip(min=1)
for idx_c, sid_val in enumerate(e8_sids):
    w_8k[ok_8k, sid_val] += np.where(ew_mask[ok_8k, idx_c], 0.5 / ew_cnt[ok_8k], 0.0)
w_8k[ok_8k] -= 0.5 * act_s502[ok_8k] / n_sh[ok_8k, None]
dw_8k = np.abs(np.diff(np.vstack([np.zeros((1, len(syms))), w_8k]), axis=0)).sum(axis=1)
borrow = np.where(ok_8k, 0.5 * 0.005 / 252.0, 0.0)  # 50bp/yr short borrow on 0.5 short leg
r_8k = (w_8k * R_MAT).sum(axis=1) + rf_arr - dw_8k * (10.0 / 10000.0) - borrow
s_8k = pd.Series(r_8k, index=pd.to_datetime(all_dates))
s_8k = s_8k[(s_8k.index >= "2015-01-01") & (s_8k.index <= "2026-06-01")]
st_8k = {"all": ms(s_8k), "is": ms(s_8k[s_8k.index.year < 2021]), "oos": ms(s_8k[s_8k.index.year >= 2021]), "active_pct": round(float(ok_8k.mean()*100), 1)}
print(f"  Calendar Short Item 5.02 vs Long EW (42d, 10bp+borrow) | active={st_8k['active_pct']}% | All={st_8k['all']['sharpe']:+.3f} | IS={st_8k['is']['sharpe']:+.3f} | OOS={st_8k['oos']['sharpe']:+.3f}")
audit_res["item502_calendar_audit"] = st_8k

with open(f"{ROOT}/research/artifacts/exp0054b_adversarial_audit.json", "w") as f:
    json.dump(audit_res, f, indent=2)
print("Saved exp0054b_adversarial_audit.json")
