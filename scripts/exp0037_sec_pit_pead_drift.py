#!/usr/bin/env python3
"""
EXP-0037 — Causal Event-Driven SEC EDGAR Post-Filing Drift (PEAD Proxy) & Fundamental Acceleration (2016-2026)
Uses 17,445 zero-leak SEC available_from filings across 385 survivorship-free US firms (317 active + 68 delisted).
Strict t_avail + 1td entry after 2-day filing reaction CAR_FILING_2D and fundamental surprises (delta_ROE, delta_RevYoY, delta_NI_YoY).
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
PRICES_ACTIVE = SEC / "prices_pit"
PRICES_DELISTED = ROOT / "data" / "stocks_delisted_tiingo"
OUT_JSON = ROOT / "research" / "artifacts" / "exp0037_sec_pit_pead_drift.json"

SPLIT_DATE = pd.Timestamp("2022-01-01")
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


def load_full_panel():
    meta_act = pd.read_csv(SEC / "universe_pit_meta.csv").drop_duplicates("ticker")
    meta_del = pd.read_csv(SEC / "delisted_pit_meta.csv").drop_duplicates("ticker")
    pit_act = pd.read_csv(SEC / "pit_fundamentals_expanded.csv")
    pit_del = pd.read_csv(SEC / "pit_fundamentals_delisted.csv")
    pit = pd.concat([pit_act, pit_del], ignore_index=True)
    pit["avail_dt"] = pd.to_datetime(pit["available_from"])
    pit = pit.sort_values(["ticker", "avail_dt"]).reset_index(drop=True)

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

    spy_df = pd.read_csv(ROOT / "data" / "etfs_tiingo" / "SPY.csv")
    spy_df["date"] = pd.to_datetime(spy_df["date"])
    spy = pd.to_numeric(spy_df["adjclose"], errors="coerce").set_axis(spy_df["date"]).dropna().sort_index()
    spy = spy[~spy.index.duplicated(keep="last")]

    px = pd.DataFrame(closes).sort_index().loc["2015-01-01":"2026-11-20"]
    px = px.dropna(axis=1, thresh=150)
    rets = px.pct_change(fill_method=None)
    for c in rets.columns:
        rets[c] = rets[c].clip(-1.0 if c in del_set else -0.75, 5.0 if c in del_set else 1.50)
    spy_r = spy.pct_change().reindex(px.index).fillna(0.0)
    return px, rets, spy_r, pit, del_set


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
            else:
                w[bot] = 0.5 / n_q
                w[top] = -0.5 / n_q
        idx0 = r_i + 1
        idx1 = reb_idx[k + 1] + 1 if k + 1 < len(reb_idx) else n_days
        if idx0 >= n_days:
            continue
        to[idx0] = np.sum(np.abs(w - prev_w))
        gross[idx0:idx1] = rets_mat[idx0:idx1] @ w
        prev_w = w
    return gross, to


def main() -> None:
    px, rets, spy_r, pit, del_set = load_full_panel()
    dates = px.index
    tickers = list(px.columns)
    t_to_col = {t: i for i, t in enumerate(tickers)}
    rets_mat = np.nan_to_num(rets.to_numpy(), nan=0.0)
    px_mat = px.to_numpy()
    cal_np = dates.to_numpy()
    spy_cum = (1.0 + spy_r).cumprod().to_numpy()

    # Build event-level surprises strictly observed at t_avail (first trading day >= available_from)
    # Note: available_from in SEC PIT already shifted past 16:00 ET, so t_avail close includes filing-day reaction!
    events = []
    for tkr, g in pit.groupby("ticker"):
        if tkr not in t_to_col:
            continue
        c_idx = t_to_col[tkr]
        g = g.sort_values("avail_dt").reset_index(drop=True)
        last_ev_dt = None
        prev_roe, prev_rev, prev_ni = np.nan, np.nan, np.nan
        for _, row in g.iterrows():
            adt = row["avail_dt"]
            roe, rev, ni = row["roe"], row["revenue_yoy"], row["net_income_yoy"]
            pos = int(np.searchsorted(cal_np, np.datetime64(adt), side="left"))
            if pos >= 2 and pos < len(dates) - 45:
                p_now = px_mat[pos, c_idx]
                p_prev = px_mat[pos - 2, c_idx]
                if np.isfinite(p_now) and np.isfinite(p_prev) and p_now >= 2.0 and p_prev >= 2.0:
                    if last_ev_dt is None or (adt - last_ev_dt).days >= 30:
                        car_2d = (p_now / p_prev - 1.0) - (spy_cum[pos] / spy_cum[pos - 2] - 1.0)
                        d_roe = (roe - prev_roe) if (np.isfinite(roe) and np.isfinite(prev_roe)) else np.nan
                        d_rev = (rev - prev_rev) if (np.isfinite(rev) and np.isfinite(prev_rev)) else np.nan
                        d_ni = (ni - prev_ni) if (np.isfinite(ni) and np.isfinite(prev_ni)) else np.nan
                        events.append({
                            "ticker": tkr, "col": c_idx, "pos": pos, "date": dates[pos],
                            "car_2d": float(car_2d),
                            "d_roe": float(np.clip(d_roe, -1.0, 1.0)) if np.isfinite(d_roe) else np.nan,
                            "d_rev": float(np.clip(d_rev, -2.0, 2.0)) if np.isfinite(d_rev) else np.nan,
                            "d_ni": float(np.clip(d_ni, -5.0, 5.0)) if np.isfinite(d_ni) else np.nan,
                            "fwd_21d_ex": float((px_mat[pos + 21, c_idx] / px_mat[pos + 1, c_idx] - 1.0) - (spy_cum[pos + 21] / spy_cum[pos + 1] - 1.0))
                            if np.isfinite(px_mat[pos + 21, c_idx]) and np.isfinite(px_mat[pos + 1, c_idx]) else np.nan,
                        })
                        last_ev_dt = adt
            if np.isfinite(roe):
                prev_roe = roe
            if np.isfinite(rev):
                prev_rev = rev
            if np.isfinite(ni):
                prev_ni = ni

    ev_df = pd.DataFrame(events)
    print(f"SEC PIT Filing Events (>=2015, $2+): {len(ev_df):,} events across {ev_df['ticker'].nunique()} firms")

    # Part A: Event-Study IC & Quintile Q5-Q1 post-filing drift (strictly entered at pos+1, exiting pos+21)
    ev_study = {}
    for col in ("car_2d", "d_roe", "d_rev", "d_ni"):
        sub = ev_df[[col, "fwd_21d_ex", "date"]].dropna().copy()
        is_s = sub[sub["date"] < SPLIT_DATE]
        oos_s = sub[sub["date"] >= SPLIT_DATE]
        ic_is = float(is_s[col].corr(is_s["fwd_21d_ex"], method="spearman")) if len(is_s) > 30 else 0.0
        ic_oos = float(oos_s[col].corr(oos_s["fwd_21d_ex"], method="spearman")) if len(oos_s) > 30 else 0.0
        q_is = is_s.groupby(pd.qcut(is_s[col], 5, labels=False, duplicates="drop"))["fwd_21d_ex"].mean()
        q_oos = oos_s.groupby(pd.qcut(oos_s[col], 5, labels=False, duplicates="drop"))["fwd_21d_ex"].mean()
        spread_is = float(q_is.iloc[-1] - q_is.iloc[0]) * 100.0 if len(q_is) >= 2 else 0.0
        spread_oos = float(q_oos.iloc[-1] - q_oos.iloc[0]) * 100.0 if len(q_oos) >= 2 else 0.0
        ev_study[col] = {
            "n_events": int(len(sub)),
            "spearman_ic_is": round(ic_is, 4),
            "spearman_ic_oos": round(ic_oos, 4),
            "q5_q1_20d_spread_is_pct": round(spread_is, 3),
            "q5_q1_20d_spread_oos_pct": round(spread_oos, 3),
        }

    # Part B: Calendar-Time Tradeable 21-day & 10-day Rebalance L/S of fresh SEC filing surprises (within trailing 63d)
    start_mask = dates >= pd.Timestamp("2016-01-01")
    is_mask = start_mask & (dates < SPLIT_DATE)
    oos_mask = dates >= SPLIT_DATE
    reb_21 = [i for i in range(252, len(dates) - 2, 21) if dates[i] >= pd.Timestamp("2016-01-01")]

    # Build sparse matrices on reb_21 from latest event <= d (within 63 calendar days)
    f_mats = {k: np.full((len(reb_21), len(tickers)), np.nan) for k in ("PEAD_CAR2D", "PEAD_DROE", "PEAD_DREV", "PEAD_DNI")}
    col_map = {"PEAD_CAR2D": "car_2d", "PEAD_DROE": "d_roe", "PEAD_DREV": "d_rev", "PEAD_DNI": "d_ni"}
    ev_by_col = {c: g.sort_values("pos") for c, g in ev_df.groupby("col")}
    for c_idx, g in ev_by_col.items():
        poss = g["pos"].to_numpy()
        for k, r_i in enumerate(reb_21):
            if not np.isfinite(px_mat[r_i, c_idx]) or px_mat[r_i, c_idx] < 2.0:
                continue
            p_idx = np.searchsorted(poss, r_i, side="right") - 1
            if p_idx >= 0 and (r_i - poss[p_idx]) <= 45:
                row = g.iloc[p_idx]
                for fk, ek in col_map.items():
                    f_mats[fk][k, c_idx] = row[ek]

    rng = np.random.default_rng(42)
    cal_results = {}
    for fk, sc_mat in f_mats.items():
        # Pick direction IS-only
        g_p, to_p = fast_ls(sc_mat, rets_mat, reb_21, "ls")
        g_n, to_n = fast_ls(sc_mat, rets_mat, reb_21, "ls_rev")
        r_p = g_p - to_p * 10e-4
        r_n = g_n - to_n * 10e-4
        chosen_dir = "pos" if ann_sharpe_arr(r_p[is_mask]) >= ann_sharpe_arr(r_n[is_mask]) else "neg"
        mode = "ls" if chosen_dir == "pos" else "ls_rev"
        g, to = (g_p, to_p) if chosen_dir == "pos" else (g_n, to_n)
        r5 = g - to * 5e-4
        r10 = g - to * 10e-4
        r20 = g - to * 20e-4
        s_is, s_oos = ann_sharpe_arr(r10[is_mask]), ann_sharpe_arr(r10[oos_mask])
        null_is, null_oos = [], []
        for _ in range(N_PERMS):
            perm = rng.permutation(len(tickers))
            gp, top = fast_ls(sc_mat[:, perm], rets_mat, reb_21, mode)
            rp = gp - top * 10e-4
            null_is.append(ann_sharpe_arr(rp[is_mask]))
            null_oos.append(ann_sharpe_arr(rp[oos_mask]))
        cal_results[fk] = {
            "is_dir": chosen_dir,
            "ls_5bp_all": round(ann_sharpe_arr(r5[start_mask]), 3),
            "ls_10bp_is": round(s_is, 3),
            "ls_10bp_oos": round(s_oos, 3),
            "ls_10bp_all": round(ann_sharpe_arr(r10[start_mask]), 3),
            "ls_20bp_all": round(ann_sharpe_arr(r20[start_mask]), 3),
            "maxdd_10bp_pct": round(max_dd_arr(r10[start_mask]) * 100.0, 2),
            "perm_pct_is": round(float(np.mean(np.array(null_is) <= s_is) * 100.0), 1),
            "perm_pct_oos": round(float(np.mean(np.array(null_oos) <= s_oos) * 100.0), 1),
        }

    out = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "EXP-0037",
        "universe_firms": len(tickers),
        "delisted_firms": len(del_set),
        "total_events": int(len(ev_df)),
        "event_study_20d_excess": ev_study,
        "calendar_21d_rebalance": cal_results,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print("\n=== EXP-0037 EVENT-STUDY [t+1..t+21] EXCESS RETURN VS SPY ===")
    for k, v in ev_study.items():
        print(f"  {k:8s}: n={v['n_events']:5d} | IC IS={v['spearman_ic_is']:+.4f} OOS={v['spearman_ic_oos']:+.4f} | Q5-Q1 IS={v['q5_q1_20d_spread_is_pct']:+.3f}% OOS={v['q5_q1_20d_spread_oos_pct']:+.3f}%")
    print("\n=== EXP-0037 CALENDAR PORTFOLIO (21d REBALANCE, SURVIVORSHIP-FREE 384 FIRMS) ===")
    for k, v in cal_results.items():
        print(f"  {k:12s} [{v['is_dir']}]: IS={v['ls_10bp_is']:+.3f} OOS={v['ls_10bp_oos']:+.3f} All={v['ls_10bp_all']:+.3f} 5bp={v['ls_5bp_all']:+.3f} 20bp={v['ls_20bp_all']:+.3f} DD={v['maxdd_10bp_pct']:+.2f}% | perm={v['perm_pct_is']}/{v['perm_pct_oos']}%")


if __name__ == "__main__":
    main()
