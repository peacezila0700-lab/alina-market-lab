"""
EXP-0053: Thai SET50 (2006-2023 Daily + Futures Basis/OI) & TFEX S50 1-Minute Intraday (2016-2025, 2,428 Days).
Part A: 17y Daily SET50 Trend/VT12, Futures Basis, OI & Basis+Trend vs BuyHold (IS 2006-2015 vs OOS 2016-2023).
Part B: 10y Intraday TFEX S50 1-minute (ORB 15m/30m, Gap Fade/Follow, Morning->Afternoon Mom/Rev, Overnight)
        at realistic retail TFEX friction (5 bp/side = ~85 THB/contract + 1 tick) AND prop (2 bp/side).
"""
import os, json, zipfile
import numpy as np
import pandas as pd

ROOT = "/tmp/alina_lab"
RAW = "/var/tmp/alina_raw_cache"

def stats_daily(s, ann=252.0):
    s = pd.Series(s).dropna()
    if len(s) < 60 or s.std(ddof=1) < 1e-12:
        return {"n": int(len(s)), "sharpe": 0.0, "cagr": 0.0, "dd": 0.0, "calmar": 0.0}
    sh = (s.mean() / s.std(ddof=1)) * np.sqrt(ann)
    eq = (1.0 + s).cumprod()
    cagr = eq.iloc[-1] ** (ann / len(s)) - 1.0 if eq.iloc[-1] > 0 else -1.0
    dd = (eq / eq.cummax() - 1.0).min()
    cal = cagr / abs(dd) if dd < -1e-9 else 0.0
    return {"n": int(len(s)), "sharpe": round(float(sh), 3), "cagr": round(float(cagr * 100), 2), "dd": round(float(dd * 100), 2), "calmar": round(float(cal), 3)}

def shift_test_daily(ret_arr, w_unshifted, rf_arr, cost_bps=5.0, n_shifts=300, seed=42):
    rng = np.random.default_rng(seed)
    w0 = pd.Series(w_unshifted).shift(1).fillna(0.0).clip(-1.0, 1.0).values
    dw0 = np.abs(np.diff(np.concatenate([[0.0], w0])))
    s0 = w0 * ret_arr + np.maximum(0.0, 1.0 - np.abs(w0)) * rf_arr - dw0 * (cost_bps / 10000.0)
    sh0 = (s0.mean() / s0.std(ddof=1)) * np.sqrt(252.0) if s0.std(ddof=1) > 1e-12 else 0.0
    n = len(ret_arr)
    beats = 0
    for _ in range(n_shifts):
        k = int(rng.integers(30, max(31, n - 30)))
        wr = np.roll(w0, k)
        dwr = np.abs(np.diff(np.concatenate([[0.0], wr])))
        sr = wr * ret_arr + np.maximum(0.0, 1.0 - np.abs(wr)) * rf_arr - dwr * (cost_bps / 10000.0)
        shr = (sr.mean() / sr.std(ddof=1)) * np.sqrt(252.0) if sr.std(ddof=1) > 1e-12 else 0.0
        if sh0 > shr:
            beats += 1
    return round(100.0 * beats / n_shifts, 2)

# -------------------------------------------------------------------------
# PART A: Daily SET50 + Futures Basis/OI (2006-2023)
# -------------------------------------------------------------------------
s50_idx = pd.read_csv(f"{ROOT}/data/thai/set50_index_2006_2023.csv")
s50_idx["date"] = pd.to_datetime(s50_idx["Date"]).dt.strftime("%Y-%m-%d")
s50_idx = s50_idx.sort_values("date").drop_duplicates("date").reset_index(drop=True)

fut = pd.read_csv(f"{ROOT}/data/thai/set50_futures_daily_2006_2023.csv.gz", low_memory=False)
fut["date"] = pd.to_datetime(fut["Date"]).dt.strftime("%Y-%m-%d")
for c in ["Open", "High", "Low", "Close", "SP", "Vol", "OI"]:
    fut[c] = pd.to_numeric(fut[c], errors="coerce")
# Front-month = contract with highest OI on that date (strictly causal at close!)
front = fut.sort_values(["date", "OI", "Vol"], ascending=[True, False, False]).drop_duplicates("date")
tot_oi = fut.groupby("date", as_index=False)[["Vol", "OI"]].sum().rename(columns={"Vol": "fut_tot_vol", "OI": "fut_tot_oi"})

df_d = s50_idx.merge(front[["date", "Close", "SP"]].rename(columns={"Close": "fut_close", "SP": "fut_sp"}), on="date", how="left")
df_d = df_d.merge(tot_oi, on="date", how="left").sort_values("date").reset_index(drop=True)
df_d["Close"] = pd.to_numeric(df_d["Close"], errors="coerce")
df_d["fut_sp"] = pd.to_numeric(df_d["fut_sp"], errors="coerce").fillna(pd.to_numeric(df_d["fut_close"], errors="coerce"))

# Bank of Thailand policy rate daily rf if present
rf_thb = np.zeros(len(df_d))
cb_path = f"{ROOT}/data/macro/central_bank_rates_daily.csv"
if os.path.exists(cb_path):
    cb = pd.read_csv(cb_path)
    thb_c = [c for c in cb.columns if "th" in c.lower() or "bot" in c.lower()]
    if thb_c:
        cb["date"] = pd.to_datetime(cb[cb.columns[0]]).dt.strftime("%Y-%m-%d")
        rm = dict(zip(cb["date"], pd.to_numeric(cb[thb_c[0]], errors="coerce").ffill().fillna(1.5) / 100.0 / 252.0))
        rf_thb = pd.Series(df_d["date"].map(rm)).ffill().fillna(0.015 / 252.0).values
else:
    rf_thb[:] = 0.015 / 252.0

df_d["ret"] = df_d["Close"].pct_change().fillna(0.0)
df_d["basis_pct"] = (df_d["fut_sp"] / df_d["Close"] - 1.0) * 100.0
df_d["basis_z"] = (df_d["basis_pct"] - df_d["basis_pct"].rolling(60, min_periods=20).mean()) / df_d["basis_pct"].rolling(60, min_periods=20).std().clip(lower=0.05)
df_d["oi_mom20"] = df_d["fut_tot_oi"] / df_d["fut_tot_oi"].rolling(20).mean() - 1.0
df_d["vol20"] = df_d["ret"].ewm(span=20, min_periods=15).std() * np.sqrt(252.0)
df_d["vt12"] = (0.12 / df_d["vol20"].clip(lower=0.04)).clip(upper=1.0).fillna(0.0)
df_d["sma50"] = (df_d["Close"] > df_d["Close"].rolling(50).mean()).astype(float)
df_d["sma100"] = (df_d["Close"] > df_d["Close"].rolling(100).mean()).astype(float)
df_d["trend_ens"] = np.mean([(df_d["Close"] > df_d["Close"].rolling(lb).mean()).astype(float) for lb in [20, 40, 60, 90, 120]], axis=0)
df_d = df_d[df_d["date"] >= "2006-06-01"].reset_index(drop=True)
rf_thb = rf_thb[-len(df_d):]

part_a = {}
print(f"\n=== PART A: Thai SET50 Daily ({df_d['date'].min()}..{df_d['date'].max()}, n={len(df_d)}, 5bp futures cost + THB BoT cash) ===")
strats_a = {
    "SET50_BuyHold": np.ones(len(df_d)),
    "SET50_VT12": df_d["vt12"].values,
    "SET50_SMA50_VT12": (df_d["sma50"] * df_d["vt12"]).values,
    "SET50_SMA100_VT12": (df_d["sma100"] * df_d["vt12"]).values,
    "SET50_TrendEns_VT12": (df_d["trend_ens"] * df_d["vt12"]).values,
    "SET50_BasisPos_VT12": (((df_d["basis_pct"].fillna(0) > 0).astype(float)) * df_d["vt12"]).values,
    "SET50_BasisZ_Contra_VT12": (((df_d["basis_z"].fillna(0) < 0).astype(float)) * df_d["vt12"]).values,
    "SET50_OIMom20_VT12": (((df_d["oi_mom20"].fillna(0) > 0).astype(float)) * df_d["vt12"]).values,
}
is_a = df_d["date"].values < "2016-01-01"
oos_a = df_d["date"].values >= "2016-01-01"

for nm, w_raw in strats_a.items():
    w = pd.Series(w_raw).shift(1).fillna(0.0).values
    dw = np.abs(np.diff(np.concatenate([[0.0], w])))
    st = w * df_d["ret"].values + np.maximum(0.0, 1.0 - w) * rf_thb - dw * (5.0 / 10000.0)
    sh_p = shift_test_daily(df_d["ret"].values, w_raw, rf_thb, 5.0) if nm != "SET50_BuyHold" else None
    part_a[nm] = {"all": stats_daily(st), "is": stats_daily(st[is_a]), "oos": stats_daily(st[oos_a]), "shift300": sh_p}
    r = part_a[nm]
    print(f"  {nm:<26} | All={r['all']['sharpe']:+.3f} (CAGR {r['all']['cagr']:+.1f}%, DD {r['all']['dd']:+.1f}%) | IS={r['is']['sharpe']:+.3f} | OOS={r['oos']['sharpe']:+.3f} | Sh300={sh_p}")

# -------------------------------------------------------------------------
# PART B: TFEX S50 1-Minute Intraday Strategies (2016-2025, 2,428 Days)
# -------------------------------------------------------------------------
print("\nLoading TFEX S50 1-Minute Continuous Bars (2016-2025)...")
with zipfile.ZipFile(f"{RAW}/S50H16-S50Z25_1m.zip") as zf:
    with zf.open("S50H16-S50Z25_1m.csv") as fh:
        m1 = pd.read_csv(fh, dtype={"open":"float32","high":"float32","low":"float32","close":"float32","Volume":"int32"})

m1["dt"] = pd.to_datetime(m1["Date"] + " " + m1["Time"])
m1 = m1.sort_values("dt").drop_duplicates("dt").reset_index(drop=True)

# Save compact 15-minute TFEX S50 file into repo data/thai/!
m1_idx = m1.set_index("dt")
s15 = m1_idx.resample("15min", label="left", closed="left").agg(
    open=("open", "first"), high=("high", "max"), low=("low", "min"), close=("close", "last"), volume=("Volume", "sum")
).dropna().reset_index()
s15.to_csv(f"{ROOT}/data/thai/tfex_s50_15m_2016_2025.csv.gz", index=False, compression="gzip")
print(f"Saved compact 15m TFEX S50 ({len(s15):,} bars)")

# Vectorized per-day intraday simulations using 1-minute bars (zero lookahead!)
days_data = []
prev_day_close = None
for d_str, grp in m1.groupby("Date", sort=True):
    if len(grp) < 120:
        prev_day_close = float(grp["close"].iloc[-1])
        continue
    t_arr = grp["Time"].values
    o_arr = grp["open"].values.astype(float)
    h_arr = grp["high"].values.astype(float)
    l_arr = grp["low"].values.astype(float)
    c_arr = grp["close"].values.astype(float)
    # Locate key intraday checkpoints (Asia/Bangkok)
    # Morning open: first bar >= 09:45; Morning close: last bar <= 12:30
    # Afternoon open: first bar >= 14:15; Close exit: last bar before 16:50 (or [-2])
    morn_end_idx = np.searchsorted(t_arr, "12:30:00", side="right") - 1
    aft_start_idx = np.searchsorted(t_arr, "14:15:00", side="left")
    exit_idx = len(t_arr) - 2  # exit at open/close of penultimate bar (~16:53)
    if morn_end_idx < 25 or aft_start_idx >= exit_idx:
        prev_day_close = float(c_arr[-1])
        continue

    gap = (o_arr[0] / prev_day_close - 1.0) if prev_day_close is not None else 0.0
    ovn_ret = (o_arr[0] / prev_day_close - 1.0) if prev_day_close is not None else 0.0
    morn_ret = c_arr[morn_end_idx] / o_arr[0] - 1.0
    aft_open = o_arr[aft_start_idx]
    day_exit_p = c_arr[exit_idx]
    aft_ret = day_exit_p / aft_open - 1.0
    intraday_bh = day_exit_p / o_arr[0] - 1.0

    # ORB 15m (first 15 bars 09:45..09:59) & ORB 30m (first 30 bars 09:45..10:14)
    def sim_orb(n_orb):
        hi_orb = np.max(h_arr[:n_orb])
        lo_orb = np.min(l_arr[:n_orb])
        pos = 0
        ent_p = 0.0
        for j in range(n_orb, exit_idx):
            if c_arr[j] > hi_orb:
                pos = 1; ent_p = o_arr[j + 1]; break
            elif c_arr[j] < lo_orb:
                pos = -1; ent_p = o_arr[j + 1]; break
        if pos == 0:
            return 0.0, False
        return pos * (day_exit_p / ent_p - 1.0), True

    orb15_g, orb15_tr = sim_orb(15)
    orb30_g, orb30_tr = sim_orb(30)

    # Gap Fade / Follow: check gap vs prev_day_close -> enter at o_arr[1] (minute 09:46 open) or o_arr[0]!
    # Strictly enter at o_arr[1] (after 1st minute price discovery!)
    gap_post_ret = day_exit_p / o_arr[1] - 1.0
    gap_morn_ret = c_arr[morn_end_idx] / o_arr[1] - 1.0

    days_data.append({
        "date": d_str,
        "gap": gap,
        "ovn_ret": ovn_ret,
        "intraday_bh": intraday_bh,
        "morn_ret": morn_ret,
        "aft_ret": aft_ret,
        "orb15_g": orb15_g, "orb15_tr": orb15_tr,
        "orb30_g": orb30_g, "orb30_tr": orb30_tr,
        "gap_post_ret": gap_post_ret,
        "gap_morn_ret": gap_morn_ret,
    })
    prev_day_close = float(c_arr[-1])

ddf = pd.DataFrame(days_data)
print(f"TFEX S50 Intraday days ready: {len(ddf)} ({ddf['date'].min()} .. {ddf['date'].max()})")

# Build strategies on ddf for 5 bp/side (retail TFEX ~10bp RT) & 2 bp/side (prop 4bp RT)
def eval_intraday_strats(cost_bps=5.0):
    rt = 2.0 * cost_bps / 10000.0
    strats = {
        "S50_Intraday_BH": ddf["intraday_bh"].values,
        "S50_Overnight_BH": ddf["ovn_ret"].values,
        "S50_ORB15m": np.where(ddf["orb15_tr"], ddf["orb15_g"] - rt, 0.0),
        "S50_ORB30m": np.where(ddf["orb30_tr"], ddf["orb30_g"] - rt, 0.0),
        "S50_GapFade_GT0.3pct": np.where(np.abs(ddf["gap"]) > 0.003, -np.sign(ddf["gap"]) * ddf["gap_morn_ret"] - rt, 0.0),
        "S50_GapFollow_GT0.3pct": np.where(np.abs(ddf["gap"]) > 0.003, np.sign(ddf["gap"]) * ddf["gap_post_ret"] - rt, 0.0),
        "S50_AftFollow_Morn0.3": np.where(np.abs(ddf["morn_ret"]) > 0.003, np.sign(ddf["morn_ret"]) * ddf["aft_ret"] - rt, 0.0),
        "S50_AftFade_Morn0.3": np.where(np.abs(ddf["morn_ret"]) > 0.003, -np.sign(ddf["morn_ret"]) * ddf["aft_ret"] - rt, 0.0),
        "S50_AftFollow_All": np.sign(ddf["morn_ret"]) * ddf["aft_ret"] - rt,
    }
    is_m = ddf["date"].values < "2021-01-01"
    oos_m = ddf["date"].values >= "2021-01-01"
    out = {}
    for nm, arr in strats.items():
        out[nm] = {
            "all": stats_daily(arr),
            "is": stats_daily(arr[is_m]),
            "oos": stats_daily(arr[oos_m]),
            "n_trades": int(np.sum(arr != 0)),
        }
    return out

part_b_5bp = eval_intraday_strats(5.0)
part_b_2bp = eval_intraday_strats(2.0)
print("\n=== PART B: TFEX S50 1-Min Intraday (2016-2025, 5bp/side retail vs 2bp/side prop) ===")
for nm in part_b_5bp:
    r5 = part_b_5bp[nm]
    r2 = part_b_2bp[nm]
    print(f"  {nm:<24} | tr={r5['n_trades']:4d} | 5bp All={r5['all']['sharpe']:+.3f} (IS {r5['is']['sharpe']:+.2f}, OOS {r5['oos']['sharpe']:+.2f}) | 2bp All={r2['all']['sharpe']:+.3f} (OOS {r2['oos']['sharpe']:+.2f})")

res = {"part_a_daily_set50": part_a, "part_b_intraday_5bp": part_b_5bp, "part_b_intraday_2bp": part_b_2bp}
with open(f"{ROOT}/research/artifacts/exp0053_thai_set50_and_tfex_s50_intraday.json", "w") as f:
    json.dump(res, f, indent=2)
print("Saved exp0053_thai_set50_and_tfex_s50_intraday.json")
