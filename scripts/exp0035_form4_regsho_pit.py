#!/usr/bin/env python3
"""
EXP-0035 — Causal Point-in-Time SEC Form 4 Insider (2018-2026) & FINRA RegSHO Short Volume (2019-2026)
Evaluated strictly causally (filing_date + 1td; regsho_date + 1td) on the 385-firm survivorship-free US panel
(317 active + 68 delisted), plus Risk Radar market-breadth predictive AUC/IC diagnostics.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SEC = ROOT / "data" / "sec"
EQ = ROOT / "data" / "equities"
PRICES_ACTIVE = SEC / "prices_pit"
PRICES_DELISTED = ROOT / "data" / "stocks_delisted_tiingo"
OUT_JSON = ROOT / "research" / "artifacts" / "exp0035_form4_regsho_pit.json"

N_PERMS = 200


def ann_sharpe_arr(r: np.ndarray) -> float:
    r = r[np.isfinite(r)]
    if len(r) < 30:
        return 0.0
    sd = float(np.std(r, ddof=1))
    return float(np.mean(r) / sd * math.sqrt(252)) if sd > 0 else 0.0


def max_dd_arr(r: np.ndarray) -> float:
    eq = np.cumprod(1.0 + np.nan_to_num(r, nan=0.0))
    return float(np.min(eq / np.maximum.accumulate(eq) - 1.0))


def roc_auc_fast(y_true: np.ndarray, y_score: np.ndarray) -> float:
    m = np.isfinite(y_true) & np.isfinite(y_score)
    y, s = y_true[m].astype(int), y_score[m]
    if len(y) < 30 or y.sum() == 0 or y.sum() == len(y):
        return 0.5
    order = np.argsort(s)
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(s) + 1)
    # handle ties
    df_tmp = pd.DataFrame({"s": s, "y": y})
    r = df_tmp["s"].rank(method="average").to_numpy()
    n1 = float((y == 1).sum())
    n0 = float((y == 0).sum())
    return float((r[y == 1].sum() - n1 * (n1 + 1.0) / 2.0) / (n1 * n0))


def load_survivorship_prices(start_date: str = "2018-01-01", end_date: str = "2026-11-20"):
    meta_act = pd.read_csv(SEC / "universe_pit_meta.csv").drop_duplicates("ticker")
    meta_del = pd.read_csv(SEC / "delisted_pit_meta.csv").drop_duplicates("ticker")
    closes = {}
    del_set = set()
    for tkr in meta_act["ticker"]:
        p = PRICES_ACTIVE / f"{tkr}.csv"
        if not p.exists():
            continue
        df = pd.read_csv(p)
        col = "adjclose" if "adjclose" in df.columns else "close"
        df["date"] = pd.to_datetime(df["date"])
        s = pd.to_numeric(df[col], errors="coerce").set_axis(df["date"]).dropna().sort_index()
        s = s[~s.index.duplicated(keep="last")]
        if len(s) >= 250:
            closes[tkr] = s
    for tkr in meta_del["ticker"]:
        p = PRICES_DELISTED / f"{tkr}.csv"
        if not p.exists() or tkr in closes:
            continue
        df = pd.read_csv(p)
        df["date"] = pd.to_datetime(df["date"])
        s = pd.to_numeric(df["adjclose"], errors="coerce").set_axis(df["date"]).dropna().sort_index()
        s = s[~s.index.duplicated(keep="last")]
        if len(s) >= 150:
            closes[tkr] = s
            del_set.add(tkr)

    px = pd.DataFrame(closes).sort_index().loc[start_date:end_date]
    px = px.dropna(axis=1, thresh=150)
    rets = px.pct_change(fill_method=None)
    for c in rets.columns:
        rets[c] = rets[c].clip(-1.0 if c in del_set else -0.75, 5.0 if c in del_set else 1.50)
    return px, rets, del_set


def fast_ls(score_mat: np.ndarray, rets_mat: np.ndarray, reb_idx: list[int], mode: str = "ls"):
    n_days, n_cols = rets_mat.shape
    gross = np.zeros(n_days)
    to = np.zeros(n_days)
    prev_w = np.zeros(n_cols)
    for k, r_i in enumerate(reb_idx):
        row = score_mat[k]
        valid = np.flatnonzero(np.isfinite(row))
        w = np.zeros(n_cols)
        if len(valid) >= 15:
            vals = row[valid]
            n_q = max(3, int(len(valid) * 0.2))
            order = np.argsort(vals)
            bot = valid[order[:n_q]]
            top = valid[order[-n_q:]]
            if mode == "ls":
                w[top] = 0.5 / n_q
                w[bot] = -0.5 / n_q
            elif mode == "ls_rev":
                w[bot] = 0.5 / n_q
                w[top] = -0.5 / n_q
            else:
                w[top] = 1.0 / n_q
        idx0 = r_i + 1
        idx1 = reb_idx[k + 1] + 1 if k + 1 < len(reb_idx) else n_days
        if idx0 >= n_days:
            continue
        to[idx0] = np.sum(np.abs(w - prev_w))
        gross[idx0:idx1] = rets_mat[idx0:idx1] @ w
        prev_w = w
    return gross, to


def evaluate_signal(name: str, sc_df: pd.DataFrame, rets_mat: np.ndarray, dates: pd.DatetimeIndex,
                    reb_idx: list[int], start_mask: np.ndarray, split_dt: pd.Timestamp) -> dict:
    sc_mat = sc_df.to_numpy()
    is_mask = start_mask & (dates < split_dt)
    oos_mask = start_mask & (dates >= split_dt)

    best_out = {}
    for sign_label, mode in [("pos", "ls"), ("neg", "ls_rev")]:
        g, to = fast_ls(sc_mat, rets_mat, reb_idx, mode)
        r5 = g - to * (5.0 / 10000.0)
        r10 = g - to * (10.0 / 10000.0)
        r20 = g - to * (20.0 / 10000.0)
        s_is, s_oos, s_all = ann_sharpe_arr(r10[is_mask]), ann_sharpe_arr(r10[oos_mask]), ann_sharpe_arr(r10[start_mask])
        best_out[sign_label] = {
            "ls_5bp_all": round(ann_sharpe_arr(r5[start_mask]), 3),
            "ls_10bp_is": round(s_is, 3),
            "ls_10bp_oos": round(s_oos, 3),
            "ls_10bp_all": round(s_all, 3),
            "ls_20bp_all": round(ann_sharpe_arr(r20[start_mask]), 3),
            "maxdd_10bp_pct": round(max_dd_arr(r10[start_mask]) * 100.0, 2),
        }

    # Pick direction by IS Sharpe ONLY (no OOS peeking!), then run 200 permutations on BOTH IS and OOS
    chosen = "pos" if best_out["pos"]["ls_10bp_is"] >= best_out["neg"]["ls_10bp_is"] else "neg"
    chosen_mode = "ls" if chosen == "pos" else "ls_rev"
    rng = np.random.default_rng(42)
    n_cols = sc_mat.shape[1]
    s_is_ref = best_out[chosen]["ls_10bp_is"]
    s_oos_ref = best_out[chosen]["ls_10bp_oos"]
    null_is, null_oos = [], []
    for _ in range(N_PERMS):
        perm = rng.permutation(n_cols)
        gp, top = fast_ls(sc_mat[:, perm], rets_mat, reb_idx, chosen_mode)
        rp = gp - top * (10.0 / 10000.0)
        null_is.append(ann_sharpe_arr(rp[is_mask]))
        null_oos.append(ann_sharpe_arr(rp[oos_mask]))
    return {
        "signal": name,
        "is_selected_dir": chosen,
        "chosen_metrics": best_out[chosen],
        "perm_pct_is": round(float(np.mean(np.array(null_is) <= s_is_ref) * 100.0), 1),
        "perm_pct_oos": round(float(np.mean(np.array(null_oos) <= s_oos_ref) * 100.0), 1),
        "both_dirs": best_out,
    }


def main() -> None:
    px, rets, del_set = load_survivorship_prices("2018-01-01", "2026-11-20")
    dates = px.index
    tickers = list(px.columns)
    ticker_set = set(tickers)
    rets_mat = np.nan_to_num(rets.to_numpy(), nan=0.0)
    print(f"Loaded survivorship-free panel: {len(dates)} days x {len(tickers)} firms ({len(del_set)} delisted)")

    # --- PART A: SEC FORM 4 CAUSAL SIGNALS (2018-01 .. 2026-03) ---
    f4 = pd.read_csv(SEC / "insider_form4_2018_2026q1.csv.gz")
    f4["ticker"] = f4["issuertradingsymbol"].astype(str).str.strip().str.upper()
    f4["filing_dt"] = pd.to_datetime(f4["filing_date"], format="%d-%b-%Y", errors="coerce")
    f4["shares"] = pd.to_numeric(f4["trans_shares"], errors="coerce")
    f4["price"] = pd.to_numeric(f4["trans_pricepershare"], errors="coerce")
    f4["usd"] = f4["shares"] * f4["price"]
    f4 = f4[
        f4["filing_dt"].notna()
        & f4["trans_code"].isin(["P", "S"])
        & (f4["shares"] > 0)
        & (f4["price"] > 0.1)
        & (f4["price"] < 50000)
        & (f4["usd"] >= 1000.0)
        & (f4["usd"] <= 1e9)
    ].copy()

    # Map filing_dt to STRICTLY NEXT trading day (causal filing_date + 1 trading day)
    cal_np = dates.to_numpy()
    pos = np.searchsorted(cal_np, f4["filing_dt"].to_numpy(), side="right")
    valid_pos = pos < len(dates)
    f4 = f4[valid_pos].copy()
    f4["avail_date"] = dates[pos[valid_pos]]

    # Market-wide Form 4 breadth (across ALL 8,826 tickers)
    f4["buy_usd"] = np.where(f4["trans_code"] == "P", f4["usd"], 0.0)
    f4["sell_usd"] = np.where(f4["trans_code"] == "S", f4["usd"], 0.0)
    f4["buy_cnt"] = (f4["trans_code"] == "P").astype(float)
    f4["sell_cnt"] = (f4["trans_code"] == "S").astype(float)

    mkt_f4 = f4.groupby("avail_date")[["buy_usd", "sell_usd", "buy_cnt", "sell_cnt"]].sum().reindex(dates, fill_value=0.0)
    mkt_f4_20 = mkt_f4.rolling(20, min_periods=5).sum()
    mkt_f4_buy_val_ratio = mkt_f4_20["buy_usd"] / (mkt_f4_20["buy_usd"] + mkt_f4_20["sell_usd"]).replace(0, np.nan)
    mkt_f4_buy_cnt_ratio = mkt_f4_20["buy_cnt"] / (mkt_f4_20["buy_cnt"] + mkt_f4_20["sell_cnt"]).replace(0, np.nan)

    # Universe Form 4 daily matrices
    f4_u = f4[f4["ticker"].isin(ticker_set)].copy()
    piv_b_usd = f4_u.groupby(["avail_date", "ticker"])["buy_usd"].sum().unstack(fill_value=0.0).reindex(index=dates, columns=tickers, fill_value=0.0)
    piv_s_usd = f4_u.groupby(["avail_date", "ticker"])["sell_usd"].sum().unstack(fill_value=0.0).reindex(index=dates, columns=tickers, fill_value=0.0)
    piv_b_cnt = f4_u.groupby(["avail_date", "ticker"])["buy_cnt"].sum().unstack(fill_value=0.0).reindex(index=dates, columns=tickers, fill_value=0.0)
    piv_s_cnt = f4_u.groupby(["avail_date", "ticker"])["sell_cnt"].sum().unstack(fill_value=0.0).reindex(index=dates, columns=tickers, fill_value=0.0)

    b_usd_63 = piv_b_usd.rolling(63, min_periods=1).sum()
    s_usd_63 = piv_s_usd.rolling(63, min_periods=1).sum()
    b_cnt_63 = piv_b_cnt.rolling(63, min_periods=1).sum()
    s_cnt_63 = piv_s_cnt.rolling(63, min_periods=1).sum()

    tot_usd_63 = b_usd_63 + s_usd_63
    tot_cnt_63 = b_cnt_63 + s_cnt_63

    f4_net_usd_ratio = (b_usd_63 - s_usd_63) / tot_usd_63.where(tot_usd_63 >= 25000.0)
    f4_net_cnt_ratio = (b_cnt_63 - s_cnt_63) / tot_cnt_63.where(tot_cnt_63 >= 2.0)
    f4_log_net_usd = np.log1p(b_usd_63) - np.log1p(s_usd_63)
    f4_log_net_usd = f4_log_net_usd.where(tot_usd_63 >= 10000.0)

    # Mask price < $2 at decision date
    px_mask = px >= 2.0
    f4_net_usd_ratio = f4_net_usd_ratio.where(px_mask)
    f4_net_cnt_ratio = f4_net_cnt_ratio.where(px_mask)
    f4_log_net_usd = f4_log_net_usd.where(px_mask)

    # Weekly (5d) and Monthly (21d) rebalances for Form 4 (2018-07-01 .. 2026-03-31, split 2022-07-01)
    f4_end = pd.Timestamp("2026-03-31")
    f4_start = pd.Timestamp("2018-07-01")
    f4_split = pd.Timestamp("2022-07-01")
    f4_mask = (dates >= f4_start) & (dates <= f4_end)
    reb_f4_21 = [i for i in range(126, len(dates) - 2, 21) if f4_start <= dates[i] <= f4_end]
    reb_f4_5 = [i for i in range(126, len(dates) - 2, 5) if f4_start <= dates[i] <= f4_end]

    f4_results = {}
    for label, reb_list in [("21d", reb_f4_21), ("5d", reb_f4_5)]:
        for sname, df_s in [
            ("F4_NET_USD_RATIO_63D", f4_net_usd_ratio),
            ("F4_NET_CNT_RATIO_63D", f4_net_cnt_ratio),
            ("F4_LOG_NET_USD_63D", f4_log_net_usd),
        ]:
            key = f"{sname}_{label}"
            f4_results[key] = evaluate_signal(key, df_s.iloc[reb_list], rets_mat, dates, reb_list, f4_mask, f4_split)

    # --- PART B: FINRA REGSHO CAUSAL SIGNALS (2019-06 .. 2026-11) ---
    reg = pd.read_csv(EQ / "finra_regsho_universe_daily.csv.gz")
    reg["dt"] = pd.to_datetime(reg["date"])
    reg = reg[reg["ticker"].isin(ticker_set) & (reg["total_vol"] > 1000)].copy()
    reg["sr"] = (reg["short_vol"] / reg["total_vol"]).clip(0.0, 1.0)
    reg["ex_r"] = (reg["short_exempt_vol"] / reg["total_vol"]).clip(0.0, 1.0)

    # Strict causal shift: RegSHO published evening of D -> available at next trading day
    piv_sr = reg.pivot_table(index="dt", columns="ticker", values="sr", aggfunc="last").reindex(index=dates, columns=tickers).shift(1)
    piv_ex = reg.pivot_table(index="dt", columns="ticker", values="ex_r", aggfunc="last").reindex(index=dates, columns=tickers).shift(1)

    sr_20 = piv_sr.rolling(20, min_periods=10).mean().where(px_mask)
    sr_5v60 = (piv_sr.rolling(5, min_periods=3).mean() - piv_sr.rolling(60, min_periods=30).mean()).where(px_mask)
    ex_20 = piv_ex.rolling(20, min_periods=10).mean().where(px_mask)

    reg_start = pd.Timestamp("2019-06-01")
    reg_split = pd.Timestamp("2023-01-01")
    reg_mask = dates >= reg_start
    reb_reg_21 = [i for i in range(126, len(dates) - 2, 21) if dates[i] >= reg_start]
    reb_reg_5 = [i for i in range(126, len(dates) - 2, 5) if dates[i] >= reg_start]

    reg_results = {}
    for label, reb_list in [("21d", reb_reg_21), ("5d", reb_reg_5)]:
        for sname, df_s in [
            ("REGSHO_SHORT_RATIO_20D", sr_20),
            ("REGSHO_SHORT_SURGE_5V60", sr_5v60),
            ("REGSHO_EXEMPT_RATIO_20D", ex_20),
        ]:
            key = f"{sname}_{label}"
            reg_results[key] = evaluate_signal(key, df_s.iloc[reb_list], rets_mat, dates, reb_list, reg_mask, reg_split)

    # --- PART C: MARKET-LEVEL RISK RADAR DIAGNOSTICS (SPY fwd 21d VolOnset & TailStress) ---
    spy_df = pd.read_csv(ROOT / "data" / "etfs_tiingo" / "SPY.csv")
    spy_df["date"] = pd.to_datetime(spy_df["date"])
    spy = pd.to_numeric(spy_df["adjclose"], errors="coerce").set_axis(spy_df["date"]).dropna().sort_index().reindex(dates).ffill()
    spy_ret = spy.pct_change()
    rv21 = spy_ret.rolling(21).std() * math.sqrt(252)
    fwd_rv21 = rv21.shift(-21)
    vol_onset = (fwd_rv21 > 1.25 * rv21).astype(float)
    vol_onset[fwd_rv21.isna() | rv21.isna()] = np.nan

    # Forward 21d SPY max drawdown <= -5%
    fwd_ret21 = spy.shift(-21) / spy - 1.0
    tail_stress = (fwd_ret21 <= -0.05).astype(float)
    tail_stress[fwd_ret21.isna()] = np.nan

    # RegSHO market aggregate (shifted 1 trading day strictly causal)
    mkt_reg = pd.read_csv(EQ / "finra_regsho_market_daily.csv")
    mkt_reg["dt"] = pd.to_datetime(mkt_reg["date"])
    mkt_reg = mkt_reg.set_index("dt").reindex(dates).shift(1)
    reg_sr = mkt_reg["mkt_short_ratio"]
    reg_sr_ma5 = reg_sr.rolling(5).mean()
    reg_sr_5v60 = reg_sr.rolling(5).mean() - reg_sr.rolling(60).mean()
    reg_sr_z60 = (reg_sr - reg_sr.rolling(60).mean()) / reg_sr.rolling(60).std()

    radar_diag = {}
    for fname, ser in [
        ("f4_mkt_buy_val_ratio_20d", mkt_f4_buy_val_ratio.loc["2018-07-01":"2026-03-31"]),
        ("f4_mkt_buy_cnt_ratio_20d", mkt_f4_buy_cnt_ratio.loc["2018-07-01":"2026-03-31"]),
        ("regsho_mkt_short_ratio_ma5", reg_sr_ma5.loc["2019-06-01":]),
        ("regsho_mkt_short_surge_5v60", reg_sr_5v60.loc["2019-06-01":]),
        ("regsho_mkt_short_z60", reg_sr_z60.loc["2019-06-01":]),
    ]:
        idx = ser.index
        vo = vol_onset.reindex(idx).to_numpy()
        ts = tail_stress.reindex(idx).to_numpy()
        fr = fwd_ret21.reindex(idx).to_numpy()
        sv = ser.to_numpy()
        m_fr = np.isfinite(sv) & np.isfinite(fr)
        radar_diag[fname] = {
            "n_days": int(np.isfinite(sv).sum()),
            "auc_vol_onset": round(roc_auc_fast(vo, sv), 4),
            "auc_tail_stress": round(roc_auc_fast(ts, sv), 4),
            "corr_fwd21_spy_ret": round(float(np.corrcoef(sv[m_fr], fr[m_fr])[0, 1]), 4) if m_fr.sum() > 30 else 0.0,
            "latest_value": round(float(ser.dropna().iloc[-1]), 5) if not ser.dropna().empty else None,
        }

    out = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "EXP-0035",
        "universe_firms": len(tickers),
        "delisted_firms": len(del_set),
        "form4_valid_rows": int(len(f4)),
        "form4_cross_section": f4_results,
        "regsho_cross_section": reg_results,
        "risk_radar_diagnostics": radar_diag,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, indent=2))

    print("=== EXP-0035 FORM 4 CROSS-SECTION (CAUSAL FILING_DATE+1TD, SURVIVORSHIP-FREE) ===")
    for k, v in f4_results.items():
        m = v["chosen_metrics"]
        print(f"  {k:28s} [{v['is_selected_dir']}] | IS={m['ls_10bp_is']:+.3f} OOS={m['ls_10bp_oos']:+.3f} All={m['ls_10bp_all']:+.3f} 5bp={m['ls_5bp_all']:+.3f} 20bp={m['ls_20bp_all']:+.3f} DD={m['maxdd_10bp_pct']:+.2f}% | perm={v['perm_pct_is']}/{v['perm_pct_oos']}%")

    print("\n=== EXP-0035 FINRA REGSHO CROSS-SECTION (CAUSAL DATE+1TD, SURVIVORSHIP-FREE) ===")
    for k, v in reg_results.items():
        m = v["chosen_metrics"]
        print(f"  {k:28s} [{v['is_selected_dir']}] | IS={m['ls_10bp_is']:+.3f} OOS={m['ls_10bp_oos']:+.3f} All={m['ls_10bp_all']:+.3f} 5bp={m['ls_5bp_all']:+.3f} 20bp={m['ls_20bp_all']:+.3f} DD={m['maxdd_10bp_pct']:+.2f}% | perm={v['perm_pct_is']}/{v['perm_pct_oos']}%")

    print("\n=== RISK RADAR MARKET BREADTH DIAGNOSTICS (SPY 21d VOL ONSET / TAIL STRESS) ===")
    for k, v in radar_diag.items():
        print(f"  {k:30s} | n={v['n_days']:4d} AUC_VolOnset={v['auc_vol_onset']:.4f} AUC_TailStress={v['auc_tail_stress']:.4f} Corr_Fwd21={v['corr_fwd21_spy_ret']:+.4f} last={v['latest_value']}")


if __name__ == "__main__":
    main()
