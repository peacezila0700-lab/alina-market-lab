"""
EXP-0049: Crypto On-Chain (CoinMetrics 2013-2026), DeFiLlama Stablecoins & TVL (2018-2026),
Crypto Fear & Greed (2018-2026), & CFTC CME Financial COT (2018-2026).
Tests BOTH standalone signals AND incremental overlays atop EXP-0041/0043 SMA50_VT25 / TrendEns_VT25.
Strict shift(1) causality, 10bp/side cost + EFFR cash yield, IS <= 2022-12-31, OOS >= 2023-01-01.
"""
import os, json
import numpy as np
import pandas as pd

ROOT = "/tmp/alina_lab"

# Load macro EFFR daily yield
fr = pd.read_csv(f"{ROOT}/data/macro/fred_rates_full.csv")
fr["date"] = pd.to_datetime(fr["date"]).dt.strftime("%Y-%m-%d")
effr_col = "dff" if "dff" in fr.columns else "dtb3"
fr["rf_daily"] = pd.to_numeric(fr[effr_col], errors="coerce").ffill().fillna(0.0) / 100.0 / 365.0
rf_map = dict(zip(fr["date"], fr["rf_daily"]))

def metrics_from_ret(dates, ret_arr):
    s = pd.Series(ret_arr, index=pd.to_datetime(dates)).dropna()
    if len(s) < 90:
        return None
    ann = 365.0
    mu = s.mean() * ann
    sd = s.std(ddof=1) * np.sqrt(ann)
    sh = mu / sd if sd > 1e-12 else 0.0
    eq = (1.0 + s).cumprod()
    yrs = len(s) / ann
    cagr = eq.iloc[-1] ** (1.0 / yrs) - 1.0 if eq.iloc[-1] > 0 else -1.0
    dd = (eq / eq.cummax() - 1.0).min()
    cal = cagr / abs(dd) if dd < -1e-9 else 0.0
    return {
        "n": int(len(s)),
        "sharpe": round(float(sh), 3),
        "cagr": round(float(cagr * 100), 2),
        "max_dd": round(float(dd * 100), 2),
        "calmar": round(float(cal), 3),
    }

def run_bt(dates, ret_asset, w_raw, rf_arr, cost_bps=10.0, split="2023-01-01"):
    # w_raw[t] is signal computed on day t -> held on day t+1
    w = pd.Series(w_raw, index=dates).shift(1).fillna(0.0).clip(0.0, 1.5).values
    dw = np.abs(np.diff(np.concatenate([[0.0], w])))
    strat = w * ret_asset + np.maximum(0.0, 1.0 - w) * rf_arr - dw * (cost_bps / 10000.0)
    mask_is = dates < split
    mask_oos = dates >= split
    return {
        "all": metrics_from_ret(dates, strat),
        "is": metrics_from_ret(dates[mask_is], strat[mask_is]),
        "oos": metrics_from_ret(dates[mask_oos], strat[mask_oos]),
        "avg_w": round(float(np.mean(w)), 3),
        "turnover_ann": round(float(np.sum(dw) / (len(dates) / 365.0)), 2),
        "_strat": strat,
        "_w": w,
        "_ret": ret_asset,
    }

def shift_test(ret_asset, w_unshifted, rf_arr, cost_bps=10.0, n_shifts=300, seed=42):
    rng = np.random.default_rng(seed)
    w0 = pd.Series(w_unshifted).shift(1).fillna(0.0).clip(0.0, 1.5).values
    dw0 = np.abs(np.diff(np.concatenate([[0.0], w0])))
    s0 = w0 * ret_asset + np.maximum(0.0, 1.0 - w0) * rf_arr - dw0 * (cost_bps / 10000.0)
    sh0 = (s0.mean() / s0.std(ddof=1)) * np.sqrt(365.0) if s0.std(ddof=1) > 1e-12 else 0.0
    n = len(ret_asset)
    beats = 0
    for _ in range(n_shifts):
        k = int(rng.integers(30, max(31, n - 30)))
        wr = np.roll(w0, k)
        dwr = np.abs(np.diff(np.concatenate([[0.0], wr])))
        sr = wr * ret_asset + np.maximum(0.0, 1.0 - wr) * rf_arr - dwr * (cost_bps / 10000.0)
        shr = (sr.mean() / sr.std(ddof=1)) * np.sqrt(365.0) if sr.std(ddof=1) > 1e-12 else 0.0
        if sh0 > shr:
            beats += 1
    return round(100.0 * beats / n_shifts, 2)

def vt25_scale(ret_s, target=0.25, span=20):
    vol = ret_s.ewm(span=span, min_periods=15).std() * np.sqrt(365.0)
    return (target / vol.clip(lower=0.05)).clip(upper=1.0).fillna(0.0)

results = {}

# -------------------------------------------------------------------------
# PART A: CoinMetrics Long-Horizon BTC (2013-2026) & ETH (2016-2026)
# -------------------------------------------------------------------------
for sym, start_dt in [("btc", "2013-01-01"), ("eth", "2016-01-01")]:
    cm = pd.read_csv(f"{ROOT}/data/crypto_onchain/coinmetrics_{sym}.csv.gz")
    cm = cm[cm["date"] >= start_dt].sort_values("date").reset_index(drop=True)
    for c in cm.columns:
        if c != "date":
            cm[c] = pd.to_numeric(cm[c], errors="coerce")
    cm["ret"] = cm["PriceUSD"].pct_change().fillna(0.0)
    cm["rf"] = cm["date"].map(rf_map).ffill().fillna(0.0)
    cm["vt25"] = vt25_scale(cm["ret"])
    cm["sma50"] = (cm["PriceUSD"] > cm["PriceUSD"].rolling(50).mean()).astype(float)
    cm["netflow_usd"] = cm["FlowOutExUSD"].fillna(0) - cm["FlowInExUSD"].fillna(0)
    cm["nf_z"] = (cm["netflow_usd"].rolling(14).mean() - cm["netflow_usd"].rolling(180, min_periods=60).mean()) / cm["netflow_usd"].rolling(180, min_periods=60).std().clip(lower=1.0)
    cm["adr_mom"] = cm["AdrActCnt"].rolling(14).mean() / cm["AdrActCnt"].rolling(90).mean().clip(lower=1.0) - 1.0
    cm["mvrv_z"] = (cm["CapMVRVCur"] - cm["CapMVRVCur"].rolling(365, min_periods=90).mean()) / cm["CapMVRVCur"].rolling(365, min_periods=90).std().clip(lower=0.05)

    print(f"\n=== PART A: CoinMetrics {sym.upper()} ({cm['date'].min()}..{cm['date'].max()}, n={len(cm)}) ===")
    print("  non-null MVRV:", cm["CapMVRVCur"].notna().sum(), "| FlowOut:", cm["FlowOutExUSD"].notna().sum(), "| Adr:", cm["AdrActCnt"].notna().sum())

    strats = {
        "BuyHold": np.ones(len(cm)),
        "SMA50_VT25_Base": (cm["sma50"] * cm["vt25"]).values,
        "MVRV_Value_LT2p5": ((cm["CapMVRVCur"] < 2.5).astype(float)).values,
        "MVRV_Z_Contrarian_VT25": (((cm["mvrv_z"] < 1.5).astype(float)) * cm["vt25"]).values,
        "ExchOutflow_Pos_VT25": (((cm["nf_z"] > 0).astype(float)) * cm["vt25"]).values,
        "ActiveAddr_Mom_VT25": (((cm["adr_mom"] > 0).astype(float)) * cm["vt25"]).values,
        "Overlay_SMA50_VT25_MVRVCap2p5": (cm["sma50"] * np.where(cm["CapMVRVCur"] > 2.5, 0.5, 1.0) * cm["vt25"]).values,
        "Overlay_SMA50_VT25_AdrPos": (cm["sma50"] * (cm["adr_mom"] > -0.05).astype(float) * cm["vt25"]).values,
    }
    res_sym = {}
    for nm, w in strats.items():
        bt = run_bt(cm["date"].values, cm["ret"].values, w, cm["rf"].values)
        sh_p = shift_test(cm["ret"].values, w, cm["rf"].values) if nm != "BuyHold" else None
        out = {"all": bt["all"], "is": bt["is"], "oos": bt["oos"], "shift300": sh_p, "avg_w": bt["avg_w"]}
        res_sym[nm] = out
        print(f"  {nm:<32} | All={bt['all']['sharpe']:+.3f} (DD {bt['all']['max_dd']:+.1f}%) | IS={bt['is']['sharpe']:+.3f} | OOS={bt['oos']['sharpe']:+.3f} (Cal {bt['oos']['calmar']:.2f}) | Sh300={sh_p}")
    results[f"coinmetrics_{sym}"] = res_sym

# -------------------------------------------------------------------------
# PART B: Modern Crypto Panel (2018-2026) — DeFiLlama, Fear&Greed, CME COT
# Align on Binance Vision BTCUSDT (2017-08..2026-10) + 19-Coin EW
# -------------------------------------------------------------------------
sp = pd.read_csv(f"{ROOT}/data/crypto_vision/spot_daily_19coins.csv.gz")
sp["date"] = pd.to_datetime(sp["date"]).dt.strftime("%Y-%m-%d")
piv_c = sp.pivot(index="date", columns="symbol", values="close").sort_index()
piv_r = piv_c.pct_change()
# 19-coin causal EW & SMA50_VT25 (same rules as EXP-0043)
valid = piv_c.rolling(120, min_periods=120).count() >= 120
ew_ret = piv_r.where(valid.shift(1)).mean(axis=1).fillna(0.0)
sma50_mat = (piv_c > piv_c.rolling(50).mean()).astype(float)
vol_mat = piv_r.ewm(span=20, min_periods=15).std() * np.sqrt(365.0)
vt_mat = (0.25 / vol_mat.clip(lower=0.05)).clip(upper=1.0)
w_19_base = (sma50_mat * vt_mat).where(valid).fillna(0.0)
# Normalize active coin weights at time t -> average across eligible coins (or fixed 1/n_eligible)
n_elig = valid.sum(axis=1).clip(lower=1)
w_19_shifted = w_19_base.div(n_elig, axis=0).shift(1).fillna(0.0)
dw_19 = w_19_shifted.diff().abs().sum(axis=1).fillna(0.0)
rf_19 = pd.Series(piv_c.index.map(rf_map), index=piv_c.index).ffill().fillna(0.0)
w_19_sum = w_19_shifted.sum(axis=1).clip(upper=1.0)
ret_19_base = (w_19_shifted * piv_r.fillna(0.0)).sum(axis=1) + (1.0 - w_19_sum) * rf_19 - dw_19 * (10.0 / 10000.0)

# Merge external daily features onto BTCUSDT (2018-04..2026-10)
btc = sp[sp["symbol"] == "BTCUSDT"].sort_values("date").copy()
btc["ret"] = btc["close"].pct_change().fillna(0.0)
btc["rf"] = btc["date"].map(rf_map).ffill().fillna(0.0)
btc["vt25"] = vt25_scale(btc["ret"]).values
btc["sma50"] = (btc["close"] > btc["close"].rolling(50).mean()).astype(float).values

dl = pd.read_csv(f"{ROOT}/data/crypto_onchain/defillama_macro.csv.gz")
fg = pd.read_csv(f"{ROOT}/data/crypto_onchain/crypto_fear_greed.csv")
cot = pd.read_csv(f"{ROOT}/data/cot/cme_crypto_fin_cot.csv.gz")
cot_btc = cot[cot["asset"] == "BTC"].sort_values("available_from").copy()
cot_btc["am_net_pct"] = (cot_btc["Asset_Mgr_Positions_Long_All"] - cot_btc["Asset_Mgr_Positions_Short_All"]) / cot_btc["Open_Interest_All"].clip(lower=1.0)
cot_btc["lev_net_pct"] = (cot_btc["Lev_Money_Positions_Long_All"] - cot_btc["Lev_Money_Positions_Short_All"]) / cot_btc["Open_Interest_All"].clip(lower=1.0)
cot_btc["am_z"] = (cot_btc["am_net_pct"] - cot_btc["am_net_pct"].rolling(52, min_periods=12).mean()) / cot_btc["am_net_pct"].rolling(52, min_periods=12).std().clip(lower=1e-4)
cot_btc["lev_z"] = (cot_btc["lev_net_pct"] - cot_btc["lev_net_pct"].rolling(52, min_periods=12).mean()) / cot_btc["lev_net_pct"].rolling(52, min_periods=12).std().clip(lower=1e-4)

df = btc[["date", "close", "ret", "rf", "vt25", "sma50"]].merge(dl, on="date", how="left").merge(fg[["date", "fear_greed"]], on="date", how="left")
df = df.merge(cot_btc[["available_from", "am_net_pct", "lev_net_pct", "am_z", "lev_z"]].rename(columns={"available_from": "date"}), on="date", how="left")
df = df.sort_values("date").ffill()
df["stable_30d"] = df["stable_all_usd"] / df["stable_all_usd"].shift(30) - 1.0
df["tvl_30d"] = df["defi_tvl_usd"] / df["defi_tvl_usd"].shift(30) - 1.0
df = df[df["date"] >= "2018-06-01"].reset_index(drop=True)

print(f"\n=== PART B: Modern Panel BTC ({df['date'].min()}..{df['date'].max()}, n={len(df)}) ===")
mod_strats = {
    "BTC_BuyHold": np.ones(len(df)),
    "BTC_SMA50_VT25_Base": (df["sma50"] * df["vt25"]).values,
    "Stable30d_Pos_VT25": (((df["stable_30d"] > 0).astype(float)) * df["vt25"]).values,
    "Stable30d_GT1pct_VT25": (((df["stable_30d"] > 0.01).astype(float)) * df["vt25"]).values,
    "DeFi_TVL30d_Pos_VT25": (((df["tvl_30d"] > 0).astype(float)) * df["vt25"]).values,
    "FearGreed_Contrarian_VT25": (np.where(df["fear_greed"] < 30, 1.0, np.where(df["fear_greed"] > 75, 0.0, 0.5)) * df["vt25"]).values,
    "FearGreed_Mom_GT50_VT25": (((df["fear_greed"] > 50).astype(float)) * df["vt25"]).values,
    "CME_COT_AssetMgr_ZPos_VT25": (((df["am_z"].fillna(0) > 0).astype(float)) * df["vt25"]).values,
    "CME_COT_LevShort_Contra_VT25": (((df["lev_z"].fillna(0) < 0).astype(float)) * df["vt25"]).values,
    "Overlay_SMA50_StablePos_VT25": (df["sma50"] * (df["stable_30d"] > -0.005).astype(float) * df["vt25"]).values,
    "Overlay_SMA50_FGCap80_VT25": (df["sma50"] * np.where(df["fear_greed"] > 80, 0.5, 1.0) * df["vt25"]).values,
    "Overlay_SMA50_AssetMgr_VT25": (df["sma50"] * np.where(df["am_z"].fillna(0) < -1.0, 0.5, 1.0) * df["vt25"]).values,
}

res_mod = {}
for nm, w in mod_strats.items():
    bt = run_bt(df["date"].values, df["ret"].values, w, df["rf"].values)
    sh_p = shift_test(df["ret"].values, w, df["rf"].values) if nm != "BTC_BuyHold" else None
    res_mod[nm] = {"all": bt["all"], "is": bt["is"], "oos": bt["oos"], "shift300": sh_p, "avg_w": bt["avg_w"]}
    print(f"  {nm:<32} | All={bt['all']['sharpe']:+.3f} (DD {bt['all']['max_dd']:+.1f}%) | IS={bt['is']['sharpe']:+.3f} | OOS={bt['oos']['sharpe']:+.3f} (Cal {bt['oos']['calmar']:.2f}) | Sh300={sh_p}")
results["modern_btc_2018_2026"] = res_mod

# Also test overlays on 19-Coin EW portfolio (2018-06..2026-10)
df_idx = df.set_index("date")
common = sorted(set(piv_c.index).intersection(df_idx.index))
r19_base = ret_19_base.reindex(common).fillna(0.0)
# Apply Stablecoin & FearGreed global multipliers to 19-coin w_19_shifted
res_19 = {"19Coin_SMA50_VT25_Base": {
    "all": metrics_from_ret(common, r19_base.values),
    "is": metrics_from_ret([d for d in common if d < "2023-01-01"], r19_base.loc[[d for d in common if d < "2023-01-01"]].values),
    "oos": metrics_from_ret([d for d in common if d >= "2023-01-01"], r19_base.loc[[d for d in common if d >= "2023-01-01"]].values),
}}
for tag, mult_s in [
    ("19Coin_Overlay_StablePos", (df_idx.loc[common, "stable_30d"] > -0.005).astype(float)),
    ("19Coin_Overlay_FGCap80", np.where(df_idx.loc[common, "fear_greed"] > 80, 0.5, 1.0)),
]:
    m_sh = pd.Series(mult_s, index=common).shift(1).fillna(1.0)
    w_adj = w_19_shifted.loc[common].mul(m_sh, axis=0)
    dw_adj = w_adj.diff().abs().sum(axis=1).fillna(0.0)
    w_sum = w_adj.sum(axis=1).clip(upper=1.0)
    r_adj = (w_adj * piv_r.loc[common].fillna(0.0)).sum(axis=1) + (1.0 - w_sum) * rf_19.loc[common] - dw_adj * (10.0 / 10000.0)
    res_19[tag] = {
        "all": metrics_from_ret(common, r_adj.values),
        "is": metrics_from_ret([d for d in common if d < "2023-01-01"], r_adj.loc[[d for d in common if d < "2023-01-01"]].values),
        "oos": metrics_from_ret([d for d in common if d >= "2023-01-01"], r_adj.loc[[d for d in common if d >= "2023-01-01"]].values),
    }

print("\n=== PART C: 19-Coin EW Portfolio Overlays (2018-06..2026-10) ===")
for k, v in res_19.items():
    print(f"  {k:<32} | All={v['all']['sharpe']:+.3f} (DD {v['all']['max_dd']:+.1f}%) | IS={v['is']['sharpe']:+.3f} | OOS={v['oos']['sharpe']:+.3f} (Cal {v['oos']['calmar']:.2f})")
results["portfolio_19coins"] = res_19

out_json = f"{ROOT}/research/artifacts/exp0049_crypto_onchain_defi_cot.json"
with open(out_json, "w") as f:
    json.dump(results, f, indent=2)
print("Saved:", out_json)
