"""
EXP-0050: Point-in-Time US Macro Surprise (Forex Factory 2007-2025 Actual vs Forecast + 58y Philly Fed SPF).
Part A: Exact-UTC H1 Post-Macro-Surprise Drift on real Dukascopy Bid/Ask (EURUSD, GBPUSD, USDJPY, XAUUSD).
        Strictly filters out 00:00:00 untimed FF rows and enters AFTER the release H1 bar closes (zero peek).
Part B: Daily USD Surprise Index (2007-2025, causal +1d shift) on SPY, TLT, GLD, UUP.
Part C: Philly Fed SPF (1968-2026) quarterly macro surprise/regime on SPY/TLT & Base23 Risk Meta check.
"""
import os, re, json
import numpy as np
import pandas as pd

ROOT = "/tmp/alina_lab"

def parse_num(x):
    if pd.isna(x):
        return np.nan
    s = str(x).strip().replace(",", "").replace("$", "")
    mult = 1.0
    if s.endswith("%"):
        s = s[:-1]
    elif s.endswith("K"):
        s = s[:-1]; mult = 1e3
    elif s.endswith("M"):
        s = s[:-1]; mult = 1e6
    elif s.endswith("B"):
        s = s[:-1]; mult = 1e9
    elif s.endswith("T"):
        s = s[:-1]; mult = 1e12
    try:
        return float(s) * mult
    except Exception:
        return np.nan

# Sign convention for USD bullishness (+1 means Actual > Forecast is USD-bullish, -1 means inverse e.g. Claims/Unemp)
USD_BULL_EVENTS = {
    "Non-Farm Employment Change": +1.0,
    "Unemployment Rate": -1.0,
    "Unemployment Claims": -1.0,
    "ADP Non-Farm Employment Change": +1.0,
    "CPI y/y": +1.0,
    "CPI m/m": +1.0,
    "Core CPI m/m": +1.0,
    "Core PCE Price Index m/m": +1.0,
    "PPI m/m": +1.0,
    "Core PPI m/m": +1.0,
    "Retail Sales m/m": +1.0,
    "Core Retail Sales m/m": +1.0,
    "ISM Manufacturing PMI": +1.0,
    "ISM Services PMI": +1.0,
    "ISM Non-Manufacturing PMI": +1.0,
    "CB Consumer Confidence": +1.0,
    "Prelim UoM Consumer Sentiment": +1.0,
    "Core Durable Goods Orders m/m": +1.0,
    "Advance GDP q/q": +1.0,
    "Prelim GDP q/q": +1.0,
    "Final GDP q/q": +1.0,
    "Average Hourly Earnings m/m": +1.0,
    "Federal Funds Rate": +1.0,
    "Building Permits": +1.0,
}

ff = pd.read_csv(f"{ROOT}/data/events/forex_factory_2007_2025.csv.gz")
usd = ff[(ff["Currency"] == "USD") & ff["Event"].isin(USD_BULL_EVENTS.keys()) & ff["Actual"].notna() & ff["Forecast"].notna()].copy()
usd["act"] = usd["Actual"].map(parse_num)
usd["fcst"] = usd["Forecast"].map(parse_num)
usd = usd.dropna(subset=["act", "fcst"]).copy()
usd["time_part"] = usd["DateTime"].str[11:19]
usd["ts_utc"] = pd.to_datetime(usd["DateTime"], utc=True)
usd = usd.sort_values("ts_utc").reset_index(drop=True)
usd["sign_dir"] = usd["Event"].map(USD_BULL_EVENTS)
usd["raw_diff"] = (usd["act"] - usd["fcst"]) * usd["sign_dir"]

# Strictly causal per-event rolling std (min 8 past releases)
usd["surp_z"] = np.nan
for ev, grp in usd.groupby("Event"):
    sd = grp["raw_diff"].expanding(min_periods=8).std().shift(1).clip(lower=1e-6)
    z = (grp["raw_diff"] / sd).clip(-4.0, 4.0)
    usd.loc[grp.index, "surp_z"] = z

# Exact-hour subset (excludes 00:00:00 untimed scrapes AND outside 11..19 UTC)
exact = usd[(usd["time_part"] != "00:00:00") & (usd["ts_utc"].dt.hour.between(11, 19))].dropna(subset=["surp_z"]).copy()
# Round release time to bar start hour & post-release entry hour
exact["bar_hour"] = exact["ts_utc"].dt.floor("h")
exact["entry_hour"] = exact["ts_utc"].dt.ceil("h")
# If release was on exact :00 (e.g. 15:00:00), ceil == floor -> entry is bar_hour + 1h so entire reaction bar completes first!
exact.loc[exact["entry_hour"] == exact["bar_hour"], "entry_hour"] = exact["bar_hour"] + pd.Timedelta(hours=1)

# Collapse simultaneous releases in the same entry_hour (e.g., NFP + Unemployment Rate + AHE at 13:30 UTC)
ev_hourly = exact.groupby("entry_hour", as_index=False).agg(
    bar_hour=("bar_hour", "first"),
    surp_z=("surp_z", "mean"),
    n_events=("Event", "count"),
    top_ev=("Event", "first"),
)
print(f"Total USD matched surprises={len(usd)}, exact timed={len(exact)}, unique hourly release clusters={len(ev_hourly)}")

results = {"counts": {"usd_matched": int(len(usd)), "exact_timed": int(len(exact)), "hourly_clusters": int(len(ev_hourly))}}

# -------------------------------------------------------------------------
# PART A: Real Bid/Ask H1 Dukascopy Post-Release Drift (2007-2025)
# -------------------------------------------------------------------------
# USD direction vs pair: for EURUSD, GBPUSD, XAUUSD -> USD bullish = SHORT pair (-1); for USDJPY -> LONG (+1)
pair_usd_mult = {"EURUSD": -1.0, "GBPUSD": -1.0, "XAUUSD": -1.0, "USDJPY": +1.0}
# ECN retail round-trip commission ~0.5 pip (on top of quoted bid/ask spread!)
ecn_comm_bp = 0.5

h1_res = {}
print("\n=== PART A: Dukascopy H1 Post-Macro-Surprise Real Bid/Ask (2007-2025) ===")
for sym, u_mult in pair_usd_mult.items():
    df = pd.read_csv(f"{ROOT}/data/intraday/{sym}_H1_bidask.csv.gz")
    df["ts"] = pd.to_datetime(df["ts_utc"], utc=True)
    df = df.set_index("ts").sort_index()
    df["mid_c"] = 0.5 * (df["bid_c"] + df["ask_c"])

    # Sanity check: volatility of release bar vs non-release bars!
    rel_bars = ev_hourly["bar_hour"].unique()
    is_rel = df.index.isin(rel_bars)
    rel_abs = np.abs(df["mid_c"].pct_change()).loc[is_rel].mean() * 1e4
    non_abs = np.abs(df["mid_c"].pct_change()).loc[~is_rel].mean() * 1e4
    vol_ratio = float(rel_abs / max(1e-9, non_abs))

    sym_res = {"release_bar_abs_bp": round(float(rel_abs), 2), "non_rel_bp": round(float(non_abs), 2), "vol_jump_ratio": round(vol_ratio, 2), "horizons": {}}
    print(f"\n[{sym}] Release-bar |ret| = {rel_abs:.2f} bp vs non-release {non_abs:.2f} bp (jump ratio = {vol_ratio:.2f}x)")

    for h in [1, 3, 6, 24]:
        for z_thr in [0.75, 1.5]:
            trades = []
            for _, er in ev_hourly.iterrows():
                z = er["surp_z"]
                if abs(z) < z_thr:
                    continue
                t0 = er["entry_hour"]
                if t0 not in df.index:
                    continue
                loc0 = df.index.get_loc(t0)
                if isinstance(loc0, slice) or loc0 + h >= len(df):
                    continue
                row_in = df.iloc[loc0]
                row_out = df.iloc[loc0 + h - 1]
                dir_pair = np.sign(z) * u_mult
                if dir_pair > 0:
                    gross = row_out["mid_c"] / (0.5 * (row_in["bid_o"] + row_in["ask_o"])) - 1.0
                    net = row_out["bid_c"] / row_in["ask_o"] - 1.0 - ecn_comm_bp / 10000.0
                else:
                    gross = 1.0 - row_out["mid_c"] / (0.5 * (row_in["bid_o"] + row_in["ask_o"]))
                    net = 1.0 - row_out["ask_c"] / row_in["bid_o"] - ecn_comm_bp / 10000.0
                trades.append({"ts": t0, "gross_bp": gross * 1e4, "net_bp": net * 1e4})

            tdf = pd.DataFrame(trades)
            is_m = tdf["ts"] < "2017-01-01"
            oos_m = tdf["ts"] >= "2017-01-01"
            def stat_tr(sub):
                if len(sub) < 15:
                    return None
                m = sub["net_bp"].mean()
                s = sub["net_bp"].std(ddof=1)
                t_st = m / (s / np.sqrt(len(sub))) if s > 1e-9 else 0.0
                yrs = max(1.0, (sub["ts"].max() - sub["ts"].min()).days / 365.25)
                tr_yr = len(sub) / yrs
                sh = (m / s) * np.sqrt(tr_yr) if s > 1e-9 else 0.0
                return {"n": int(len(sub)), "gross_bp": round(float(sub["gross_bp"].mean()), 2), "net_bp": round(float(m), 2), "t_stat": round(float(t_st), 2), "ann_sharpe": round(float(sh), 3)}
            h_stat = {"all": stat_tr(tdf), "is": stat_tr(tdf[is_m]), "oos": stat_tr(tdf[oos_m])}
            tag = f"H{h}_z{z_thr}"
            sym_res["horizons"][tag] = h_stat
            a, i_s, o_s = h_stat["all"], h_stat["is"], h_stat["oos"]
            print(f"  {tag:<9} | n={a['n']:3d} | gross={a['gross_bp']:+.2f}bp | net={a['net_bp']:+.2f}bp (t={a['t_stat']:+.2f}) | IS={i_s['net_bp']:+.2f}bp | OOS={o_s['net_bp']:+.2f}bp")
    h1_res[sym] = sym_res
results["h1_fx_post_surprise"] = h1_res

# -------------------------------------------------------------------------
# PART B: Daily Macro Surprise Regime (2007-2025) on SPY, TLT, GLD
# -------------------------------------------------------------------------
usd_clean = usd.dropna(subset=["surp_z"]).copy()
usd_clean["ny_date"] = usd_clean["ts_utc"].dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d")
daily_surp = usd_clean.groupby("ny_date")["surp_z"].mean()

daily_res = {}
print("\n=== PART B: Daily Macro Surprise Regime (2008-2025, 10bp/side, causal +1d) ===")
for sym in ["SPY", "TLT", "GLD"]:
    p = f"{ROOT}/data/etfs_tiingo/{sym}.csv"
    ed = pd.read_csv(p)
    ccol = "adjclose" if "adjclose" in ed.columns else "close"
    ed["date"] = pd.to_datetime(ed["date"]).dt.strftime("%Y-%m-%d")
    ed = ed.sort_values("date").drop_duplicates("date")
    ed["ret"] = pd.to_numeric(ed[ccol], errors="coerce").pct_change().fillna(0.0)
    ed["surp_raw"] = ed["date"].map(daily_surp).fillna(0.0)
    ed["surp_ema21"] = ed["surp_raw"].ewm(span=21).mean()
    ed["surp_ema63"] = ed["surp_raw"].ewm(span=63).mean()
    ed = ed[(ed["date"] >= "2008-01-01") & (ed["date"] <= "2025-04-30")].reset_index(drop=True)

    sym_d = {}
    for nm, sig in [
        ("BuyHold", np.ones(len(ed))),
        ("MacroSurp21_LongPos", (ed["surp_ema21"] > 0).astype(float).values),
        ("MacroSurp63_LongPos", (ed["surp_ema63"] > 0).astype(float).values),
        ("MacroSurp21_Contrarian", (ed["surp_ema21"] < 0).astype(float).values),
    ]:
        w = pd.Series(sig).shift(1).fillna(0.0).values
        dw = np.abs(np.diff(np.concatenate([[0.0], w])))
        st = w * ed["ret"].values - dw * (10.0 / 10000.0)
        is_m = ed["date"].values < "2017-01-01"
        oos_m = ed["date"].values >= "2017-01-01"
        def ms(arr):
            if len(arr) < 60 or np.std(arr, ddof=1) < 1e-12:
                return {"sharpe": 0.0, "cagr": 0.0, "dd": 0.0}
            sh = (np.mean(arr) / np.std(arr, ddof=1)) * np.sqrt(252.0)
            eq = np.cumprod(1.0 + arr)
            cagr = eq[-1] ** (252.0 / len(arr)) - 1.0
            dd = np.min(eq / np.maximum.accumulate(eq) - 1.0)
            return {"sharpe": round(float(sh), 3), "cagr": round(float(cagr * 100), 2), "dd": round(float(dd * 100), 2)}
        sym_d[nm] = {"all": ms(st), "is": ms(st[is_m]), "oos": ms(st[oos_m])}
    daily_res[sym] = sym_d
    print(f"  {sym}: BH OOS={sym_d['BuyHold']['oos']['sharpe']:+.3f} | Surp21 OOS={sym_d['MacroSurp21_LongPos']['oos']['sharpe']:+.3f} (All {sym_d['MacroSurp21_LongPos']['all']['sharpe']:+.3f}) | Surp63 OOS={sym_d['MacroSurp63_LongPos']['oos']['sharpe']:+.3f} | Contra21 OOS={sym_d['MacroSurp21_Contrarian']['oos']['sharpe']:+.3f}")
results["daily_macro_surprise"] = daily_res

# -------------------------------------------------------------------------
# PART C: 58y Philly Fed SPF (1968-2026) Quarterly Consensus Growth/CPI Regimes
# -------------------------------------------------------------------------
spf = pd.read_csv(f"{ROOT}/data/macro/philly_spf_median.csv.gz")
rgdp = spf[spf["series"] == "RGDP"].dropna(axis=1, how="all").copy()
cpi = spf[spf["series"] == "CPI"].dropna(axis=1, how="all").copy()
rgdp["q_end"] = pd.PeriodIndex.from_fields(year=rgdp["YEAR"].astype(int), quarter=rgdp["QUARTER"].astype(int), freq="Q").end_time.strftime("%Y-%m-%d")
rgdp["spf_rgdp_fwd_g"] = pd.to_numeric(rgdp.get("RGDP3"), errors="coerce") / pd.to_numeric(rgdp.get("RGDP2"), errors="coerce") - 1.0
cpi["q_end"] = pd.PeriodIndex.from_fields(year=cpi["YEAR"].astype(int), quarter=cpi["QUARTER"].astype(int), freq="Q").end_time.strftime("%Y-%m-%d")
cpi["spf_cpi_fwd"] = pd.to_numeric(cpi.get("CPI3"), errors="coerce")
cpi["spf_cpi_chg"] = cpi["spf_cpi_fwd"].diff()

spf_panel = rgdp[["q_end", "spf_rgdp_fwd_g"]].merge(cpi[["q_end", "spf_cpi_fwd", "spf_cpi_chg"]], on="q_end", how="inner").sort_values("q_end")

spf_panel["dt"] = pd.to_datetime(spf_panel["q_end"])
spf_res = {}
print("\n=== PART C: Philly Fed SPF Quarterly Consensus Regime on SPY (2000-2026) & TLT (2003-2026) ===")
for sym, split in [("SPY", "2014-01-01"), ("TLT", "2015-01-01")]:
    ed = pd.read_csv(f"{ROOT}/data/etfs_tiingo/{sym}.csv")
    ccol = "adjclose" if "adjclose" in ed.columns else "close"
    ed["date"] = pd.to_datetime(ed["date"]).dt.strftime("%Y-%m-%d")
    ed["dt"] = pd.to_datetime(ed["date"])
    ed = ed.sort_values("dt").drop_duplicates("dt")
    ed["ret"] = pd.to_numeric(ed[ccol], errors="coerce").pct_change().fillna(0.0)
    m = pd.merge_asof(ed[["date", "dt", "ret"]], spf_panel.sort_values("dt"), on="dt", direction="backward")
    for nm, sig in [
        ("BuyHold", np.ones(len(m))),
        ("SPF_RGDP_Pos", (m["spf_rgdp_fwd_g"].fillna(0) > 0.004).astype(float).values),
        ("SPF_Disinfl_Bonds", (m["spf_cpi_chg"].fillna(0) < 0).astype(float).values),
        ("SPF_RGDP_GT_0", (m["spf_rgdp_fwd_g"].fillna(0) > 0).astype(float).values),
    ]:
        w = pd.Series(sig).shift(1).fillna(0.0).values
        dw = np.abs(np.diff(np.concatenate([[0.0], w])))
        st = w * m["ret"].values - dw * (10.0 / 10000.0)
        def ms(arr):
            if len(arr) < 60 or np.std(arr, ddof=1) < 1e-12:
                return {"sharpe": 0.0, "cagr": 0.0, "dd": 0.0}
            sh = (np.mean(arr) / np.std(arr, ddof=1)) * np.sqrt(252.0)
            eq = np.cumprod(1.0 + arr)
            return {"sharpe": round(float(sh), 3), "cagr": round(float((eq[-1]**(252/len(arr))-1)*100), 2), "dd": round(float(np.min(eq/np.maximum.accumulate(eq)-1)*100), 2)}
        is_m = m["date"].values < split
        oos_m = m["date"].values >= split
        spf_res[f"{sym}_{nm}"] = {"all": ms(st), "is": ms(st[is_m]), "oos": ms(st[oos_m])}
        print(f"  {sym} {nm:<20} | All={spf_res[f'{sym}_{nm}']['all']['sharpe']:+.3f} (DD {spf_res[f'{sym}_{nm}']['all']['dd']:+.1f}%) | IS={spf_res[f'{sym}_{nm}']['is']['sharpe']:+.3f} | OOS={spf_res[f'{sym}_{nm}']['oos']['sharpe']:+.3f}")
results["philly_spf_regime"] = spf_res

out_json = f"{ROOT}/research/artifacts/exp0050_macro_surprise_ff_spf.json"
with open(out_json, "w") as f:
    json.dump(results, f, indent=2)
print("Saved:", out_json)
