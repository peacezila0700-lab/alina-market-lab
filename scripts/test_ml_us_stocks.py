#!/usr/bin/env python3
"""
EXP-0020 / H22 — Purged walk-forward ML ranking on 115 US large caps + macro/vol + PIT SEC fundamentals.

Pre-registered question (H22):
  Does an expanding purged walk-forward ML model (Ridge / HistGradientBoosting) trained strictly
  causally on multi-horizon price/vol technicals + lagged macro/vol/DIX-GEX state interactions
  (+ causal PIT SEC fundamentals in arm 5) generate positive net Sharpe in a dollar-neutral
  top-vs-bottom quintile portfolio (and beat equal-weight on long-only top quintile) after
  5 bp/side costs?

Pre-registered protocol (anti-leakage + PITFALLS #1, #11, #12, #13, #15):
  * Features X[t, i] use only prices, macro series and SEC filings with available_from <= t.
  * Execution lag: weights w[t] decided after close[t] take effect at close[t+1] (earning t+2..t+1+H).
  * Purged walk-forward: quarterly refits (every 63 trading days, min 504d history); training samples
    strictly satisfy target_end <= t - 1 so zero target overlap exists with the test horizon.
  * Costs: 5 bp/side on sum(|Δw|) (plus 10 bp/side 2x-cost stress check).
  * Null control: 200 permutations with a FIXED whole-sample ticker permutation (turnover-matched).
  * Split: walk-forward predictions (~2018-11..2026-11) split 70/30 by date into IS and OOS.
  * PASS bar: at least one arm beats the 99.0th percentile (Bonferroni 5 arms) of its turnover-matched
    null in BOTH IS and OOS at 5 bp/side, stays positive at 2x cost (10 bp/side), and its long-only
    top quintile beats equal-weight buy-and-hold in both halves.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import Ridge

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "research" / "artifacts" / "ml_us_stocks.json"

COST_BASE = 0.0005   # 5 bp per side
COST_2X = 0.0010     # 10 bp per side
N_NULL = 200


def load_us_stocks() -> tuple[pd.DataFrame, pd.DataFrame]:
    prices, vols = {}, {}
    for p in sorted((ROOT / "data" / "stocks").glob("*.csv")):
        sym = p.stem
        df = pd.read_csv(p)
        if "date" not in df.columns:
            continue
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").drop_duplicates("date")
        col = "adjclose" if "adjclose" in df.columns else "close"
        s = pd.to_numeric(df[col], errors="coerce")
        v = pd.to_numeric(df.get("volume"), errors="coerce") if "volume" in df else pd.Series(np.nan, index=df.index)
        prices[sym] = pd.Series(s.values, index=df["date"])
        vols[sym] = pd.Series(v.values, index=df["date"])
    px = pd.DataFrame(prices).sort_index()
    vo = pd.DataFrame(vols).reindex(px.index)
    # Keep symbols with >= 1500 valid bars
    keep = px.columns[px.notna().sum() >= 1500]
    px = px[keep].ffill(limit=3)
    vo = vo[keep]
    return px, vo


def load_macro(dates: pd.DatetimeIndex) -> pd.DataFrame:
    m = pd.DataFrame(index=dates)
    # Vol stress features
    vt = pd.read_csv(ROOT / "data" / "collect" / "vol_stress_features.csv", index_col=0, parse_dates=True)
    vt = vt.sort_index()
    for c in ["vix", "slope_3m", "vvix_pct", "skew"]:
        m[c] = vt[c].reindex(dates).ffill()
    # DIX / GEX
    dg = pd.read_csv(ROOT / "data" / "collect" / "dix_gex.csv")
    dg["date"] = pd.to_datetime(dg["date"])
    dg = dg.sort_values("date").drop_duplicates("date").set_index("date")
    m["dix"] = pd.to_numeric(dg["dix"], errors="coerce").reindex(dates).ffill()
    m["gex"] = pd.to_numeric(dg["gex"], errors="coerce").reindex(dates).ffill()
    # OFR FSI
    fsi = pd.read_csv(ROOT / "data" / "collect" / "ofr_fsi.csv")
    fsi["Date"] = pd.to_datetime(fsi["Date"])
    fsi = fsi.sort_values("Date").drop_duplicates("Date").set_index("Date")
    m["ofr_fsi"] = pd.to_numeric(fsi["OFR FSI"], errors="coerce").reindex(dates).ffill()
    # Yield curve 10y - 3m
    yc = pd.read_csv(ROOT / "data" / "collect" / "treasury_yield_curve_full.csv")
    yc["Date"] = pd.to_datetime(yc["Date"])
    yc = yc.sort_values("Date").drop_duplicates("Date").set_index("Date")
    t10 = pd.to_numeric(yc.get("10 Yr"), errors="coerce")
    t3m = pd.to_numeric(yc.get("3 Mo"), errors="coerce")
    m["yc_slope"] = (t10 - t3m).reindex(dates).ffill()

    # Strictly causal trailing z-scores (252d)
    for c in ["vix", "dix", "ofr_fsi", "yc_slope"]:
        mu = m[c].rolling(252, min_periods=60).mean()
        sd = m[c].rolling(252, min_periods=60).std().replace(0, np.nan)
        m[f"{c}_z"] = ((m[c] - mu) / sd).clip(-3, 3).fillna(0.0)
    m["gex_neg"] = (m["gex"] < 0).astype(float)
    m["slope_3m_c"] = (m["slope_3m"] - 1.0).clip(-0.3, 0.3).fillna(0.0)
    return m


def cs_rank(df: pd.DataFrame) -> pd.DataFrame:
    """Cross-sectional centered percentile rank in [-0.5, +0.5] per date (purely causal)."""
    return df.rank(axis=1, pct=True) - 0.5


def build_features(px: pd.DataFrame, vo: pd.DataFrame, macro: pd.DataFrame) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    ret1 = px.pct_change(fill_method=None)
    feats = {}
    feats["ret_1d"] = cs_rank(px.pct_change(1, fill_method=None))
    feats["ret_5d"] = cs_rank(px.pct_change(5, fill_method=None))
    feats["ret_21d"] = cs_rank(px.pct_change(21, fill_method=None))
    feats["ret_63d"] = cs_rank(px.pct_change(63, fill_method=None))
    feats["ret_126d"] = cs_rank(px.pct_change(126, fill_method=None))
    # 12-1 momentum: close[t-21] / close[t-252] - 1
    feats["mom_12_1"] = cs_rank(px.shift(21) / px.shift(252) - 1.0)
    vol21 = ret1.rolling(21, min_periods=15).std()
    vol63 = ret1.rolling(63, min_periods=40).std()
    feats["vol_21d"] = cs_rank(vol21)
    feats["vol_63d"] = cs_rank(vol63)
    feats["vol_ratio"] = cs_rank(vol21 / vol63.replace(0, np.nan))
    feats["mom_vol_adj"] = cs_rank(px.pct_change(63, fill_method=None) / vol63.replace(0, np.nan))
    feats["rev_vol_adj"] = cs_rank(-px.pct_change(5, fill_method=None) / vol21.replace(0, np.nan))
    hi252 = px.rolling(252, min_periods=126).max()
    feats["dist_hi252"] = cs_rank(px / hi252.replace(0, np.nan) - 1.0)
    ma20 = px.rolling(20, min_periods=15).mean()
    feats["dist_ma20"] = cs_rank(px / ma20.replace(0, np.nan) - 1.0)
    # RSI14
    delta = ret1
    up = delta.clip(lower=0).rolling(14, min_periods=10).mean()
    dn = (-delta.clip(upper=0)).rolling(14, min_periods=10).mean()
    rsi = 100.0 - 100.0 / (1.0 + up / dn.replace(0, np.nan))
    feats["rsi14"] = cs_rank(rsi)
    # Volume ratio
    vma20 = vo.rolling(20, min_periods=10).mean()
    feats["vol_surge"] = cs_rank(vo / vma20.replace(0, np.nan))

    # Macro-stock interactions (strictly causal on date t)
    feats["ix_vixslope_mom"] = feats["mom_vol_adj"].mul(macro["slope_3m_c"], axis=0)
    feats["ix_vixz_vol"] = feats["vol_21d"].mul(macro["vix_z"], axis=0)
    feats["ix_dixz_rev"] = feats["ret_5d"].mul(macro["dix_z"], axis=0)
    feats["ix_gexneg_rev"] = feats["ret_5d"].mul(macro["gex_neg"], axis=0)
    feats["ix_fsiz_rev21"] = feats["ret_21d"].mul(macro["ofr_fsi_z"], axis=0)
    feats["ix_ycz_mom"] = feats["mom_12_1"].mul(macro["yc_slope_z"], axis=0)

    return feats, ret1


def build_pit_panels(px: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Map strictly lagged PIT SEC fundamentals onto the (dates x tickers) grid."""
    pit = pd.read_csv(ROOT / "data" / "sec" / "pit_fundamentals.csv")
    pit["available_from"] = pd.to_datetime(pit["available_from"])
    cols = ["rev_yoy", "net_margin", "roe", "cfo_to_assets", "accruals", "debt_to_assets", "cash_to_assets"]
    dates = px.index
    syms = px.columns
    panels = {f"pit_{c}": pd.DataFrame(np.nan, index=dates, columns=syms) for c in cols}
    has_pit = pd.DataFrame(0.0, index=dates, columns=syms)

    for sym, sub in pit.groupby("ticker"):
        if sym not in syms:
            continue
        sub = sub.sort_values("available_from").drop_duplicates("available_from", keep="last").set_index("available_from")
        # Strictly causal: available_from <= t (reindex + ffill forward only)
        al = sub[cols].reindex(dates.union(sub.index)).sort_index().ffill().reindex(dates)
        has_pit[sym] = al["net_margin"].notna().astype(float)
        for c in cols:
            panels[f"pit_{c}"][sym] = al[c]

    out = {}
    for k, df in panels.items():
        # Cross-sectional rank among covered stocks, 0.0 (neutral) where not covered
        out[k] = cs_rank(df).fillna(0.0)
    out["pit_covered"] = has_pit - 0.5
    return out


def compute_weights_from_scores(score_df: pd.DataFrame, reb_idx: np.ndarray, dates: pd.DatetimeIndex,
                                syms: pd.Index, mode: str = "ls") -> pd.DataFrame:
    """
    Given score_df indexed by rebalance dates, form held weights on daily grid.
    Decision at close[t] -> portfolio rebalances at close[t+1] (earns from t+2 onward).
    """
    n_dates = len(dates)
    daily_w = np.zeros((n_dates, len(syms)), dtype=float)
    pos_map = {d: i for i, d in enumerate(dates)}

    cur_w = np.zeros(len(syms), dtype=float)
    reb_targets = {}
    for d, row in score_df.iterrows():
        s = row.values
        valid = np.isfinite(s)
        n_v = int(valid.sum())
        if n_v < 20:
            w = np.zeros(len(syms), dtype=float)
        else:
            q = max(5, n_v // 5)
            order = np.argsort(np.where(valid, s, -np.inf))
            top_idx = order[-q:]
            valid_order = np.argsort(np.where(valid, s, np.inf))
            bot_idx = valid_order[:q]
            w = np.zeros(len(syms), dtype=float)
            if mode == "ls":
                w[top_idx] = 1.0 / q
                w[bot_idx] = -1.0 / q
            else:
                w[top_idx] = 1.0 / q
        t_pos = pos_map[d]
        # Signal decided at close[t_pos] takes effect at close[t_pos + 1]
        if t_pos + 1 < n_dates:
            reb_targets[t_pos + 1] = w

    for i in range(n_dates):
        if i in reb_targets:
            cur_w = reb_targets[i]
        daily_w[i] = cur_w

    return pd.DataFrame(daily_w, index=dates, columns=syms)


def eval_weights(w_held: pd.DataFrame, ret1: pd.DataFrame, start_pos: int, split_pos: int,
                 cost: float) -> dict:
    """
    Daily P&L: w_held[d-1] * ret1[d] - cost * sum(|w_held[d] - w_held[d-1]|).
    Wait: w_held was shifted by +1 at rebalance so w_held[t+1] has new weights at close[t+1].
    Thus on day d, weight held overnight from close[d-1] to close[d] is w_held[d-1], and rebalance
    trade happens at close[d] costing sum(|w_held[d] - w_held[d-1]|) * cost!
    """
    W = w_held.values
    R = np.nan_to_num(ret1.values, nan=0.0)
    gross = np.sum(W[:-1] * R[1:], axis=1)
    turn = np.sum(np.abs(W[1:] - W[:-1]), axis=1)
    net = gross - cost * turn

    # Align indices: entry d corresponds to return on date[d+1]
    sl_is = slice(start_pos, split_pos - 1)
    sl_oos = slice(split_pos - 1, len(net))

    def _stats(arr_g, arr_n, arr_t):
        if len(arr_n) < 20:
            return {"sharpe_net": 0.0, "sharpe_gross": 0.0, "cagr_net_pct": 0.0, "maxdd_pct": 0.0, "ann_turn": 0.0}
        sd_n = float(np.std(arr_n, ddof=1))
        sd_g = float(np.std(arr_g, ddof=1))
        sh_n = float(np.mean(arr_n) / sd_n * np.sqrt(252)) if sd_n > 0 else 0.0
        sh_g = float(np.mean(arr_g) / sd_g * np.sqrt(252)) if sd_g > 0 else 0.0
        eq = np.cumprod(1.0 + arr_n)
        if np.any(eq <= 0):
            cagr = -100.0
            mdd = -100.0
        else:
            yrs = len(arr_n) / 252.0
            cagr = float((eq[-1] ** (1.0 / yrs) - 1.0) * 100.0)
            pk = np.maximum.accumulate(eq)
            mdd = float(((eq / pk) - 1.0).min() * 100.0)
        ann_t = float(np.mean(arr_t) * 252.0)
        return {
            "sharpe_net": round(sh_n, 3),
            "sharpe_gross": round(sh_g, 3),
            "cagr_net_pct": round(cagr, 2),
            "maxdd_pct": round(mdd, 2),
            "ann_turn": round(ann_t, 2),
        }

    return {
        "IS": _stats(gross[sl_is], net[sl_is], turn[sl_is]),
        "OOS": _stats(gross[sl_oos], net[sl_oos], turn[sl_oos]),
        "net_series": net,
    }


def turnover_matched_null(w_held: pd.DataFrame, ret1: pd.DataFrame, start_pos: int, split_pos: int,
                          cost: float, seed: int = 42) -> tuple[float, float, np.ndarray, np.ndarray]:
    """Fixed whole-sample ticker permutation (PITFALLS #11 & #12): preserves persistence & turnover."""
    rng = np.random.default_rng(seed)
    W = w_held.values
    R = np.nan_to_num(ret1.values, nan=0.0)
    turn = np.sum(np.abs(W[1:] - W[:-1]), axis=1)
    n_syms = W.shape[1]
    sh_is_list = np.empty(N_NULL)
    sh_oos_list = np.empty(N_NULL)

    for k in range(N_NULL):
        perm = rng.permutation(n_syms)
        Wp = W[:, perm]
        gross = np.sum(Wp[:-1] * R[1:], axis=1)
        net = gross - cost * turn
        a = net[start_pos:split_pos - 1]
        b = net[split_pos - 1:]
        sh_is_list[k] = float(np.mean(a) / np.std(a, ddof=1) * np.sqrt(252)) if np.std(a, ddof=1) > 0 else 0.0
        sh_oos_list[k] = float(np.mean(b) / np.std(b, ddof=1) * np.sqrt(252)) if np.std(b, ddof=1) > 0 else 0.0

    obs = eval_weights(w_held, ret1, start_pos, split_pos, cost)
    pct_is = float((sh_is_list < obs["IS"]["sharpe_net"]).mean() * 100.0)
    pct_oos = float((sh_oos_list < obs["OOS"]["sharpe_net"]).mean() * 100.0)
    return round(pct_is, 1), round(pct_oos, 1), sh_is_list, sh_oos_list


def walk_forward_predict(
    feat_dict: dict[str, pd.DataFrame],
    feat_names: list[str],
    px: pd.DataFrame,
    horizon: int,
    model_type: str,
    dates: pd.DatetimeIndex,
    reb_step: int,
) -> tuple[pd.DataFrame, list[pd.Timestamp]]:
    """
    Purged expanding walk-forward ML:
      * For decision date t: features X[t], target = forward H-day return from t+1..t+1+H.
      * Training only uses dates s where s + horizon + 2 <= t (strict zero overlap!).
      * Refits model every 63 trading days; predicts on rebalance dates spaced by `reb_step`.
    """
    # Forward H-day return earned AFTER entering at t+1 close: px[t+1+H]/px[t+1] - 1
    fwd = px.shift(-(horizon + 1)) / px.shift(-1) - 1.0
    # Cross-sectionally demeaned excess return (so model learns relative ranking, not market drift)
    fwd_xs = fwd.sub(fwd.mean(axis=1), axis=0)

    n_dates = len(dates)
    syms = px.columns
    n_syms = len(syms)

    # Pre-stack feature cube: shape (n_dates, n_syms, n_feats)
    X_cube = np.stack([feat_dict[f].values for f in feat_names], axis=-1)
    Y_mat = fwd_xs.values

    # First prediction date after 504 trading days warmup
    start_i = 504
    reb_indices = list(range(start_i, n_dates - horizon - 2, reb_step))
    reb_dates = [dates[i] for i in reb_indices]
    scores = pd.DataFrame(np.nan, index=reb_dates, columns=syms)

    model = None
    last_fit_i = -999

    for idx_pos, i in enumerate(reb_indices):
        if model is None or (i - last_fit_i) >= 63:
            # Strict purge: only dates s <= i - horizon - 2
            max_train_i = i - horizon - 2
            if max_train_i < 260:
                continue
            # Subsample training dates every `horizon` steps to avoid serial redundancy and speed up
            train_is = list(range(255, max_train_i + 1, max(3, horizon // 2)))
            X_tr_list, y_tr_list = [], []
            for s in train_is:
                y_s = Y_mat[s]
                x_s = X_cube[s]
                ok = np.isfinite(y_s) & np.all(np.isfinite(x_s), axis=1)
                if ok.sum() >= 20:
                    X_tr_list.append(x_s[ok])
                    y_tr_list.append(np.clip(y_s[ok], -0.4, 0.4))
            if not X_tr_list:
                continue
            X_tr = np.vstack(X_tr_list)
            y_tr = np.concatenate(y_tr_list)
            if model_type == "ridge":
                model = Ridge(alpha=500.0)
                model.fit(X_tr, y_tr)
            else:
                model = HistGradientBoostingRegressor(
                    max_iter=80,
                    max_depth=3,
                    learning_rate=0.05,
                    min_samples_leaf=250,
                    l2_regularization=20.0,
                    random_state=42,
                )
                model.fit(X_tr, y_tr)
            last_fit_i = i

        x_now = X_cube[i]
        ok_now = np.all(np.isfinite(x_now), axis=1)
        if ok_now.sum() >= 20 and model is not None:
            pred = np.full(n_syms, np.nan)
            pred[ok_now] = model.predict(x_now[ok_now])
            scores.loc[dates[i]] = pred

    return scores, reb_dates


def main() -> None:
    print("Loading 115 US stocks + macro + PIT SEC fundamentals...")
    px, vo = load_us_stocks()
    dates = px.index
    syms = px.columns
    macro = load_macro(dates)
    feats, ret1 = build_features(px, vo, macro)
    pit_feats = build_pit_panels(px)
    all_feats = {**feats, **pit_feats}

    tech_macro_cols = list(feats.keys())
    all_cols = list(all_feats.keys())

    # Equal-weight benchmark over the same walk-forward span
    start_pos = 505
    n_wf = len(dates) - start_pos
    split_pos = start_pos + int(0.70 * n_wf)
    split_date = dates[split_pos].strftime("%Y-%m-%d")
    wf_start_date = dates[start_pos].strftime("%Y-%m-%d")
    print(f"Panel: {len(syms)} stocks, {len(dates)} days | WF: {wf_start_date}..{dates[-1]:%Y-%m-%d} | IS/OOS split: {split_date}")

    ew_w = pd.DataFrame(1.0 / len(syms), index=dates, columns=syms)
    ew_res = eval_weights(ew_w, ret1, start_pos, split_pos, cost=0.0)
    print(f"EW Buy&Hold benchmark: IS Sharpe {ew_res['IS']['sharpe_net']} ({ew_res['IS']['cagr_net_pct']}%/yr) | "
          f"OOS Sharpe {ew_res['OOS']['sharpe_net']} ({ew_res['OOS']['cagr_net_pct']}%/yr)")

    arms = [
        ("ML_RIDGE_5D", tech_macro_cols, 5, "ridge", 5),
        ("ML_HGB_5D", tech_macro_cols, 5, "hgb", 5),
        ("ML_RIDGE_21D", tech_macro_cols, 21, "ridge", 21),
        ("ML_HGB_21D", tech_macro_cols, 21, "hgb", 21),
        ("ML_HGB_PIT_21D", all_cols, 21, "hgb", 21),
    ]

    # Single-factor baselines on same 21d / 5d cadence
    baselines = [
        ("BASE_MOM_12_1_21D", feats["mom_12_1"], 21),
        ("BASE_REV_5D", -feats["ret_5d"], 5),
    ]

    results = {}
    for name, sc_full, step in baselines:
        reb_dates = [dates[i] for i in range(504, len(dates) - step - 2, step)]
        sc = sc_full.loc[reb_dates]
        w_ls = compute_weights_from_scores(sc, np.array([]), dates, syms, mode="ls")
        ev5 = eval_weights(w_ls, ret1, start_pos, split_pos, COST_BASE)
        pct_is, pct_oos, _, _ = turnover_matched_null(w_ls, ret1, start_pos, split_pos, COST_BASE)
        results[name] = {
            "ls_5bp": {"IS": ev5["IS"], "OOS": ev5["OOS"], "null_pct_IS": pct_is, "null_pct_OOS": pct_oos}
        }
        print(f"  {name:18s} LS 5bp | IS sh={ev5['IS']['sharpe_net']:+.3f} (pct {pct_is:4.1f}) | "
              f"OOS sh={ev5['OOS']['sharpe_net']:+.3f} (pct {pct_oos:4.1f}) | turn={ev5['IS']['ann_turn']:.1f}x")

    any_pass = False
    for name, fcols, h, mtype, step in arms:
        scores, reb_dates = walk_forward_predict(all_feats, fcols, px, h, mtype, dates, step)
        w_ls = compute_weights_from_scores(scores, np.array([]), dates, syms, mode="ls")
        w_lo = compute_weights_from_scores(scores, np.array([]), dates, syms, mode="lo")

        ev5 = eval_weights(w_ls, ret1, start_pos, split_pos, COST_BASE)
        ev10 = eval_weights(w_ls, ret1, start_pos, split_pos, COST_2X)
        ev_lo = eval_weights(w_lo, ret1, start_pos, split_pos, COST_BASE)
        pct_is, pct_oos, _, _ = turnover_matched_null(w_ls, ret1, start_pos, split_pos, COST_BASE)
        pct_lo_is, pct_lo_oos, _, _ = turnover_matched_null(w_lo, ret1, start_pos, split_pos, COST_BASE)

        passed = (
            pct_is >= 99.0 and pct_oos >= 99.0
            and ev5["IS"]["sharpe_net"] > 0 and ev5["OOS"]["sharpe_net"] > 0
            and ev10["IS"]["sharpe_net"] > 0 and ev10["OOS"]["sharpe_net"] > 0
            and ev_lo["IS"]["sharpe_net"] > ew_res["IS"]["sharpe_net"]
            and ev_lo["OOS"]["sharpe_net"] > ew_res["OOS"]["sharpe_net"]
        )
        if passed:
            any_pass = True

        results[name] = {
            "horizon_d": h,
            "n_features": len(fcols),
            "ls_5bp": {"IS": ev5["IS"], "OOS": ev5["OOS"], "null_pct_IS": pct_is, "null_pct_OOS": pct_oos},
            "ls_10bp": {"IS": ev10["IS"], "OOS": ev10["OOS"]},
            "lo_topq_5bp": {"IS": ev_lo["IS"], "OOS": ev_lo["OOS"], "null_pct_IS": pct_lo_is, "null_pct_OOS": pct_lo_oos},
            "pass_bar": passed,
        }
        print(f"  {name:18s} LS 5bp | IS sh={ev5['IS']['sharpe_net']:+.3f} (gross {ev5['IS']['sharpe_gross']:+.3f}, "
              f"pct {pct_is:4.1f}) | OOS sh={ev5['OOS']['sharpe_net']:+.3f} (gross {ev5['OOS']['sharpe_gross']:+.3f}, "
              f"pct {pct_oos:4.1f}) | 10bp OOS={ev10['OOS']['sharpe_net']:+.3f} | LO OOS={ev_lo['OOS']['sharpe_net']:+.3f} | "
              f"PASS={passed}")

    verdict = "PASS" if any_pass else "FAIL"
    out = {
        "exp_id": "EXP-0020",
        "hyp_id": "H22",
        "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "universe": f"{len(syms)} US stocks (data/stocks)",
        "walk_forward_range": f"{wf_start_date}..{dates[-1]:%Y-%m-%d}",
        "is_oos_split": split_date,
        "cost_base_bp_side": 5,
        "cost_2x_bp_side": 10,
        "ew_benchmark": {"IS": ew_res["IS"], "OOS": ew_res["OOS"]},
        "arms": results,
        "verdict": verdict,
        "caveats": [
            "Universe is today's top market-cap US stocks -> long-only return reflects survivorship bias; "
            "dollar-neutral L/S removes market & survivorship mean drift.",
            "Purged walk-forward enforces zero target overlap and 1-bar execution delay (t+1 close).",
        ],
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nEXP-0020 verdict: {verdict} -> {OUT_JSON}")


if __name__ == "__main__":
    main()
