"""
EXP-0052: Individual Equity Options IV Surface (gauss314/options-IV-SP500, 3.16M rows, 2019-10..2023-07)
Cross-matched to CRSP-verified Johnbrick123 PIT S&P 500 + former-member prices (2019-2023).
Strictly causal t+1 execution, $5 min close, carried-patch halt exclusion, 10bp/side cost,
weekly & monthly rebalancing, IS (2019-2021) vs OOS (2022-2023), 200x rank permutation.
"""
import os, json, gc
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT = "/tmp/alina_lab"
RAW = "/var/tmp/alina_raw_cache"
JB = f"{RAW}/johnbrick_sp500"

# 1. Load Johnbrick prices strictly for 2019-09-01 .. 2023-08-15 (all tickers active in that window!)
pf = pq.ParquetFile(f"{JB}/prices.parquet")
parts = []
for i in range(pf.metadata.num_row_groups):
    rg = pf.read_row_group(i, columns=["date", "ticker", "close", "adj_close", "source"]).to_pandas()
    rg = rg[(rg["date"] >= "2019-09-01") & (rg["date"] <= "2023-08-15")]
    if len(rg):
        parts.append(rg)
px = pd.concat(parts, ignore_index=True)
del parts; gc.collect()

# Map base symbol cleanly (take latest active series per base symbol in 2019-2023)
px["base_sym"] = px["ticker"].str.split("-").str[0]
px = px.sort_values(["base_sym", "date", "ticker"]).drop_duplicates(["base_sym", "date"], keep="last")
px["close"] = px["close"].astype("float32")
px["adj_close"] = px["adj_close"].astype("float32")
px["is_carried"] = (px["source"] == "carried-patch")
px["ret"] = px.groupby("base_sym")["adj_close"].pct_change().clip(-0.95, 5.0).fillna(0.0).astype("float32")
valid_syms = set(px["base_sym"].unique())
print(f"PIT Equity Panel 2019-2023: {len(px):,} rows, {len(valid_syms)} unique symbols")

# 2. Load data_IV_USA.csv filtered to valid_syms
iv_chunks = []
use_cols = ["symbol", "date", "calls_contracts_traded", "puts_contracts_traded", "calls_open_interest", "puts_open_interest",
            "ITM_IV", "ATM_IV", "OTM_IV", "DOTM_IV", "hv_20", "hv_60"]
for ch in pd.read_csv(f"{RAW}/data_IV_USA.csv", usecols=use_cols, chunksize=300_000):
    ch = ch[ch["symbol"].isin(valid_syms)]
    if len(ch):
        iv_chunks.append(ch)
iv = pd.concat(iv_chunks, ignore_index=True)
del iv_chunks; gc.collect()
iv["date"] = pd.to_datetime(iv["date"])
iv = iv.sort_values(["symbol", "date"]).drop_duplicates(["symbol", "date"]).reset_index(drop=True)
print(f"Matched Equity Options IV rows: {len(iv):,} | {iv['symbol'].nunique()} symbols | {iv['date'].min().strftime('%Y-%m-%d')} .. {iv['date'].max().strftime('%Y-%m-%d')}")

# Build derived option-surface signals strictly causal at date t
iv["vrp_20"] = iv["ATM_IV"] - iv["hv_20"]
iv["neg_vrp_20"] = -iv["vrp_20"]
iv["iv_hv_ratio"] = iv["ATM_IV"] / iv["hv_60"].clip(lower=5.0)
iv["neg_smirk"] = -(iv["DOTM_IV"] - iv["ATM_IV"])  # low smirk long (Xing-Zhang-Zhao)
iv["otm_itm_skew"] = -(iv["OTM_IV"] - iv["ITM_IV"])
iv["pc_vol"] = -np.log1p(iv["puts_contracts_traded"].clip(lower=0) / iv["calls_contracts_traded"].clip(lower=1))
iv["pc_oi"] = -np.log1p(iv["puts_open_interest"].clip(lower=0) / iv["calls_open_interest"].clip(lower=1))
iv["neg_atm_iv"] = -iv["ATM_IV"]
iv["call_surge"] = iv["calls_contracts_traded"] / iv.groupby("symbol")["calls_contracts_traded"].rolling(20, min_periods=10).mean().reset_index(level=0, drop=True).clip(lower=10.0)

# Merge onto PIT returns & prices
m = px[["date", "base_sym", "close", "ret", "is_carried"]].rename(columns={"base_sym": "symbol"}).merge(
    iv[["date", "symbol", "vrp_20", "neg_vrp_20", "iv_hv_ratio", "neg_smirk", "otm_itm_skew", "pc_vol", "pc_oi", "neg_atm_iv", "call_surge"]],
    on=["date", "symbol"], how="left"
)
all_dates = np.sort(m[(m["date"] >= "2019-10-14") & (m["date"] <= "2023-07-28")]["date"].unique())
syms = sorted(valid_syms)
sym_to_id = {s: i for i, s in enumerate(syms)}
d_to_pos = {d: i for i, d in enumerate(all_dates)}

m_win = m[m["date"].isin(all_dates)].copy()
m_win["did"] = m_win["date"].map(d_to_pos)
m_win["sid"] = m_win["symbol"].map(sym_to_id)
R_MAT = np.zeros((len(all_dates), len(syms)), dtype=np.float32)
R_MAT[m_win["did"].values, m_win["sid"].values] = m_win["ret"].values

fr = pd.read_csv(f"{ROOT}/data/macro/fred_rates_full.csv")
fr["date"] = pd.to_datetime(fr["date"])
fr["rf_daily"] = pd.to_numeric(fr["dtb3"], errors="coerce").ffill().fillna(0.0) / 100.0 / 252.0
rf_map = dict(zip(fr["date"], fr["rf_daily"]))
rf_arr = np.array([rf_map.get(pd.Timestamp(d), 0.0) for d in all_dates], dtype=np.float32)

sig_cols = ["vrp_20", "neg_vrp_20", "iv_hv_ratio", "neg_smirk", "otm_itm_skew", "pc_vol", "pc_oi", "neg_atm_iv", "call_surge"]

def run_freq(freq_name, step_days):
    sig_pos_list = list(range(0, len(all_dates) - 2, step_days))
    slices = {}
    for p in sig_pos_list:
        sd = all_dates[p]
        sub = m_win[(m_win["did"] == p) & (~m_win["is_carried"]) & (m_win["close"] >= 5.0) & m_win["vrp_20"].notna()]
        if len(sub) >= 100:
            slices[p] = sub.set_index("sid")[sig_cols]

    periods = []
    valid_ps = sorted(slices.keys())
    for k in range(len(valid_ps) - 1):
        p0 = valid_ps[k] + 1
        p1 = valid_ps[k + 1] + 1
        if p1 > p0:
            periods.append((valid_ps[k], np.arange(p0 + 1, min(p1 + 1, len(all_dates)))))

    def eval_col(col, mode="LS", top_n=30, cost_bps=10.0):
        rets, dts = [], []
        prev_w = np.zeros(len(syms))
        for sp, hidx in periods:
            sl = slices[sp]
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
                pr = float(np.dot(cur_w, R_MAT[did, nz])) + (float(rf_arr[did]) if mode == "LS" else 0.0) - (cost0 if step == 0 else 0.0)
                rets.append(pr); dts.append(all_dates[did])
                cur_w *= (1.0 + R_MAT[did, nz])
        s = pd.Series(rets, index=pd.to_datetime(dts))
        def ms(sub):
            if len(sub) < 40 or sub.std(ddof=1) < 1e-12:
                return None
            sh = (sub.mean() / sub.std(ddof=1)) * np.sqrt(252.0)
            eq = (1.0 + sub).cumprod()
            cagr = eq.iloc[-1] ** (252.0 / len(sub)) - 1.0
            dd = (eq / eq.cummax() - 1.0).min()
            return {"sharpe": round(float(sh), 3), "cagr": round(float(cagr * 100), 2), "dd": round(float(dd * 100), 2)}
        return {"all": ms(s), "is": ms(s[s.index.year < 2022]), "oos": ms(s[s.index.year >= 2022])}

    def perm(col, mode="LS", top_n=30, cost_bps=10.0, n_perm=200):
        rng = np.random.default_rng(42)
        real = eval_col(col, mode, top_n, cost_bps)["all"]["sharpe"]
        per = []
        for sp, hidx in periods:
            s = slices[sp][col].replace([np.inf, -np.inf], np.nan).dropna()
            if len(s) < 2 * top_n:
                continue
            comp_r = np.prod(1.0 + R_MAT[hidx][:, s.index.values], axis=0) - 1.0
            per.append((comp_r, float(rf_arr[hidx].sum())))
        ann = 252.0 / step_days
        beats = 0
        for _ in range(n_perm):
            rs = []
            for cr, rfm in per:
                p = rng.permutation(len(cr))
                if mode == "LO":
                    rs.append(cr[p[:top_n]].mean() - (0.50 * 2 * cost_bps / 10000.0))
                else:
                    rs.append(0.5 * (cr[p[:top_n]].mean() - cr[p[-top_n:]].mean()) + rfm - (1.0 * 2 * cost_bps / 10000.0))
            a = np.array(rs)
            sh_p = (a.mean() / a.std(ddof=1)) * np.sqrt(ann) if a.std(ddof=1) > 1e-12 else 0.0
            if real > sh_p:
                beats += 1
        return round(100.0 * beats / n_perm, 1)

    print(f"\n=== Options IV Cross-Section [{freq_name}] (2019-10..2023-07, 10bp/side) ===")
    out = {"EW_Univ": eval_col(None, "EW")}
    print(f"  {'EW_Univ':<18} | All={out['EW_Univ']['all']['sharpe']:+.3f} | IS={out['EW_Univ']['is']['sharpe']:+.3f} | OOS={out['EW_Univ']['oos']['sharpe']:+.3f}")
    for c in sig_cols:
        for md in ["LO", "LS"]:
            r = eval_col(c, md)
            pp = perm(c, md)
            k = f"{c}_{md}"
            out[k] = {**r, "perm200": pp}
            print(f"  {k:<18} | All={r['all']['sharpe']:+.3f} (DD {r['all']['dd']:+.1f}%) | IS={r['is']['sharpe']:+.3f} | OOS={r['oos']['sharpe']:+.3f} | Perm={pp}")
    return out

results = {
    "monthly_21d": run_freq("Monthly_21d", 21),
    "weekly_5d": run_freq("Weekly_5d", 5),
}
with open(f"{ROOT}/research/artifacts/exp0052_equity_options_iv_surface.json", "w") as f:
    json.dump(results, f, indent=2)
print("Saved exp0052_equity_options_iv_surface.json")
