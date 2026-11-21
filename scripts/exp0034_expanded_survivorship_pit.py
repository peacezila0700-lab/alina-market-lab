#!/usr/bin/env python3
"""
EXP-0034 — Expanded Survivorship-Free SEC PIT Audit (+68 Delisted S&P 500 Firms)
Extends EXP-0032 from +27 delisted firms to +68 delisted US firms (2,372 zero-leak SEC XBRL snapshots + Tiingo EOD),
plus delisted-leg holding telemetry and 5/10/20 bp cost + 200-permutation tests.
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
OUT_JSON = ROOT / "research" / "artifacts" / "exp0034_expanded_survivorship_pit.json"

SPLIT_DATE = pd.Timestamp("2022-01-01")
REB_DAYS = 63
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


def sic_to_sector(sic: str) -> str:
    try:
        s = int(float(sic))
    except Exception:
        return "Other"
    if 6000 <= s <= 6799:
        return "Finance"
    if 3570 <= s <= 3579 or 3670 <= s <= 3679 or 7370 <= s <= 7379:
        return "Technology"
    if 2830 <= s <= 2836 or 3840 <= s <= 3851 or 8000 <= s <= 8099:
        return "Health Care"
    if 1000 <= s <= 1499 or 2900 <= s <= 2999:
        return "Energy"
    if 5200 <= s <= 5999 or 2000 <= s <= 2199:
        return "Consumer Discretionary"
    return "Industrials"


def load_panel(include_delisted: bool, min_price: float = 2.0):
    meta_act = pd.read_csv(SEC / "universe_pit_meta.csv").drop_duplicates("ticker")
    pit_act = pd.read_csv(SEC / "pit_fundamentals_expanded.csv")
    pit_act["available_from"] = pd.to_datetime(pit_act["available_from"])

    closes = {}
    is_tiingo_delisted = set()
    for tkr in meta_act["ticker"]:
        p = PRICES_ACTIVE / f"{tkr}.csv"
        if not p.exists():
            continue
        df = pd.read_csv(p)
        col = "adjclose" if "adjclose" in df.columns else "close"
        df["date"] = pd.to_datetime(df["date"])
        s = pd.to_numeric(df[col], errors="coerce").set_axis(df["date"]).dropna().sort_index()
        s = s[~s.index.duplicated(keep="last")]
        if len(s) >= 500:
            closes[tkr] = s

    meta_all = meta_act[["ticker", "sector"]].copy()
    pit_all = pit_act.copy()

    if include_delisted:
        meta_del = pd.read_csv(SEC / "delisted_pit_meta.csv").drop_duplicates("ticker")
        meta_del["sector"] = meta_del["sic"].astype(str).map(sic_to_sector)
        pit_del = pd.read_csv(SEC / "pit_fundamentals_delisted.csv")
        pit_del["available_from"] = pd.to_datetime(pit_del["available_from"])
        for tkr in meta_del["ticker"]:
            p = PRICES_DELISTED / f"{tkr}.csv"
            if not p.exists():
                continue
            df = pd.read_csv(p)
            df["date"] = pd.to_datetime(df["date"])
            s = pd.to_numeric(df["adjclose"], errors="coerce").set_axis(df["date"]).dropna().sort_index()
            s = s[~s.index.duplicated(keep="last")]
            if len(s) >= 200 and tkr not in closes:
                closes[tkr] = s
                is_tiingo_delisted.add(tkr)
        meta_all = pd.concat([meta_all, meta_del[["ticker", "sector"]]], ignore_index=True).drop_duplicates("ticker")
        pit_all = pd.concat([pit_all, pit_del], ignore_index=True)

    px = pd.DataFrame(closes).sort_index().loc["2015-01-01":"2026-11-20"]
    px = px.dropna(axis=1, thresh=200)
    rets = px.pct_change(fill_method=None)
    for c in rets.columns:
        if c not in is_tiingo_delisted:
            rets[c] = rets[c].clip(-0.75, 1.50)
        else:
            rets[c] = rets[c].clip(-1.0, 5.0)

    dates = px.index
    tickers = list(px.columns)
    meta_all = meta_all[meta_all["ticker"].isin(tickers)].set_index("ticker")

    reb_idx = list(range(252, len(dates) - 2, REB_DAYS))
    reb_dates = dates[reb_idx]
    factors = {k: pd.DataFrame(np.nan, index=reb_dates, columns=tickers) for k in
               ("F_NEG_ACCRUALS", "F_CFO_ASSETS", "F_REV_YOY", "F_QUALITY_COMP")}

    pit_by_tkr = {t: g.sort_values("available_from") for t, g in pit_all.groupby("ticker")}
    for t in tickers:
        g = pit_by_tkr.get(t)
        if g is None or g.empty:
            continue
        av = g["available_from"].to_numpy()
        for d in reb_dates:
            px_d = px.loc[d, t]
            if not np.isfinite(px_d) or px_d < min_price:
                continue
            pos = np.searchsorted(av, np.datetime64(d), side="right") - 1
            if pos < 0:
                continue
            row = g.iloc[pos]
            if (d - row["available_from"]).days > 460:
                continue
            acc, cfo_a, rev_y, roe, da = row["accruals"], row["cfo_to_assets"], row["revenue_yoy"], row["roe"], row["debt_to_assets"]
            if np.isfinite(acc) and abs(acc) < 2.0:
                factors["F_NEG_ACCRUALS"].loc[d, t] = -float(acc)
            if np.isfinite(cfo_a) and abs(cfo_a) < 2.0:
                factors["F_CFO_ASSETS"].loc[d, t] = float(cfo_a)
            if np.isfinite(rev_y) and -0.9 <= rev_y <= 5.0:
                factors["F_REV_YOY"].loc[d, t] = float(rev_y)
            if np.isfinite(acc) and np.isfinite(cfo_a) and np.isfinite(roe):
                factors["F_QUALITY_COMP"].loc[d, t] = float(-acc + cfo_a + np.clip(roe, -1.0, 2.0) - (da if np.isfinite(da) else 0.0))

    f_sec = factors["F_NEG_ACCRUALS"].copy()
    sec_map = meta_all["sector"].to_dict()
    for d in reb_dates:
        s = f_sec.loc[d].dropna()
        if s.empty:
            continue
        secs = pd.Series({t: sec_map.get(t, "Other") for t in s.index})
        ranked = s.groupby(secs).rank(pct=True)
        cnts = secs.map(secs.value_counts())
        ranked = ranked[cnts >= 4]
        f_sec.loc[d] = np.nan
        f_sec.loc[d, ranked.index] = ranked
    factors["F_SECTOR_NEUT_ACCRUALS"] = f_sec
    return px, rets, meta_all, factors, reb_idx, is_tiingo_delisted


def fast_portfolio_returns(score_mat: np.ndarray, rets_mat: np.ndarray, reb_idx: list[int], mode: str = "ls"):
    n_days, n_cols = rets_mat.shape
    gross = np.zeros(n_days)
    to = np.zeros(n_days)
    prev_w = np.zeros(n_cols)
    held_delisted_slots = 0
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
                w[top] = 1.0 / n_q
        idx0 = r_i + 1
        idx1 = reb_idx[k + 1] + 1 if k + 1 < len(reb_idx) else n_days
        if idx0 >= n_days:
            continue
        to[idx0] = np.sum(np.abs(w - prev_w))
        gross[idx0:idx1] = rets_mat[idx0:idx1] @ w
        prev_w = w
    return gross, to


def eval_panel(include_delisted: bool, min_price: float = 2.0) -> dict:
    px, rets, meta, factors, reb_idx, del_set = load_panel(include_delisted=include_delisted, min_price=min_price)
    dates = px.index
    valid_mask = (dates >= "2016-01-01")
    is_mask = valid_mask & (dates < SPLIT_DATE)
    oos_mask = (dates >= SPLIT_DATE)
    rets_mat = np.nan_to_num(rets.to_numpy(), nan=0.0)
    cols = list(px.columns)
    del_idx = np.array([i for i, c in enumerate(cols) if c in del_set], dtype=int)

    rng = np.random.default_rng(42)
    n_cols = px.shape[1]
    res = {}
    for fname, sc_df in factors.items():
        sc_mat = sc_df.to_numpy()
        g_ls, to_ls = fast_portfolio_returns(sc_mat, rets_mat, reb_idx, "ls")
        g_lo, to_lo = fast_portfolio_returns(sc_mat, rets_mat, reb_idx, "lo")

        # Count how many delisted firm-quarters entered top/bottom 20%
        del_in_top, del_in_bot = 0, 0
        if len(del_idx) > 0:
            del_set_idx = set(del_idx.tolist())
            for k in range(len(reb_idx)):
                row = sc_mat[k]
                valid = np.flatnonzero(np.isfinite(row))
                if len(valid) >= 15:
                    n_q = max(3, int(len(valid) * 0.2))
                    order = np.argsort(row[valid])
                    del_in_bot += sum(1 for x in valid[order[:n_q]] if x in del_set_idx)
                    del_in_top += sum(1 for x in valid[order[-n_q:]] if x in del_set_idx)

        r5 = g_ls - to_ls * (5.0 / 10000.0)
        r10 = g_ls - to_ls * (10.0 / 10000.0)
        r20 = g_ls - to_ls * (20.0 / 10000.0)
        rlo10 = g_lo - to_lo * (10.0 / 10000.0)

        s_is, s_oos = ann_sharpe_arr(r10[is_mask]), ann_sharpe_arr(r10[oos_mask])
        null_is, null_oos = [], []
        for _ in range(N_PERMS):
            perm = rng.permutation(n_cols)
            gp, top = fast_portfolio_returns(sc_mat[:, perm], rets_mat, reb_idx, "ls")
            rp = gp - top * (10.0 / 10000.0)
            null_is.append(ann_sharpe_arr(rp[is_mask]))
            null_oos.append(ann_sharpe_arr(rp[oos_mask]))
        res[fname] = {
            "ls_5bp_all": round(ann_sharpe_arr(r5[valid_mask]), 3),
            "ls_10bp_is": round(s_is, 3),
            "ls_10bp_oos": round(s_oos, 3),
            "ls_10bp_all": round(ann_sharpe_arr(r10[valid_mask]), 3),
            "ls_20bp_all": round(ann_sharpe_arr(r20[valid_mask]), 3),
            "ls_10bp_maxdd_pct": round(max_dd_arr(r10[valid_mask]) * 100.0, 2),
            "lo_10bp_all": round(ann_sharpe_arr(rlo10[valid_mask]), 3),
            "perm_pct_is": round(float(np.mean(np.array(null_is) <= s_is) * 100.0), 1),
            "perm_pct_oos": round(float(np.mean(np.array(null_oos) <= s_oos) * 100.0), 1),
            "delisted_long_legs": int(del_in_top),
            "delisted_short_legs": int(del_in_bot),
        }
    return {"firms": int(px.shape[1]), "delisted_in_panel": len(del_set), "results": res}


def main() -> None:
    act = eval_panel(include_delisted=False, min_price=2.0)
    surv = eval_panel(include_delisted=True, min_price=2.0)
    surv_nofilt = eval_panel(include_delisted=True, min_price=0.0)
    out = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "EXP-0034",
        "active_only": act,
        "survivorship_augmented_2usd": surv,
        "survivorship_augmented_no_price_floor": surv_nofilt,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"Active-Only ({act['firms']} firms) vs +Delisted ({surv['firms']} firms, {surv['delisted_in_panel']} delisted, $2 floor):")
    for fname in act["results"]:
        a, s, nf = act["results"][fname], surv["results"][fname], surv_nofilt["results"][fname]
        print(
            f"  {fname:24s} | Act: IS={a['ls_10bp_is']:+.3f} OOS={a['ls_10bp_oos']:+.3f} All={a['ls_10bp_all']:+.3f} ({a['perm_pct_is']}/{a['perm_pct_oos']}%) "
            f"| +Del($2): IS={s['ls_10bp_is']:+.3f} OOS={s['ls_10bp_oos']:+.3f} All={s['ls_10bp_all']:+.3f} DD={s['ls_10bp_maxdd_pct']:+.2f}% ({s['perm_pct_is']}/{s['perm_pct_oos']}%) [L={s['delisted_long_legs']}/S={s['delisted_short_legs']}] "
            f"| NoFloor All={nf['ls_10bp_all']:+.3f} OOS={nf['ls_10bp_oos']:+.3f}"
        )


if __name__ == "__main__":
    main()
