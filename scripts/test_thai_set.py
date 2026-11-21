#!/usr/bin/env python3
"""
EXP-0021 / H23 — First systematic test on Thai SET 64 stocks (cross-sectional factors + purged ML).

Pre-registered question (H23):
  Do classic cross-sectional factors (5d reversal, 21d reversal, 12-1 momentum) or purged expanding
  walk-forward ML rankers (Ridge / HistGradientBoosting on technicals + global VIX/OFR regime
  interactions) earn positive net Sharpe beyond a turnover-matched null on the 64-stock Thai SET
  panel after real Thai retail transaction costs?

Thai retail cost model (verified against Kasikorn Securities / Maybank / SET fee schedules):
  * Fee-only floor: 16.8 bp/side = 0.15% online Cash Balance commission + 0.007% SET/TSD/reg + 7% VAT.
  * Realistic retail base: 27.0 bp/side = 16.8 bp fee + ~10 bp half-spread/tick impact (54 bp RT).
  * Note: retail shorting on SET requires SBL & faces uptick rules, so BOTH Long-Short (theoretical)
    and Long-Only Top Quintile (actionable in Cash Balance) vs SET_EW buy-and-hold are tested.

Anti-leakage & null protocol (PITFALLS #1, #11, #12, #15):
  * Causal features only up to close[t]; rebalance takes effect at close[t+1] (no same-bar fill).
  * Purged walk-forward: expanding training uses only s + horizon + 2 <= t (zero overlap), refit 63d.
  * Null: 200 permutations with a FIXED whole-sample ticker permutation (turnover-matched).
  * Split: 70/30 by date on the walk-forward span (~2018-12..2026-11).
  * PASS bar: beat 99.0th pct of turnover-matched null in BOTH IS and OOS at 27 bp/side (and 16.8 bp),
    and Long-Only Top Quintile beats SET_EW net Sharpe in both halves.

Caveats written down:
  * Yahoo `.BK` series are price-only (`close`, no dividend adjustment; SET average yield ~3%/yr).
  * Panel covers 64 large/liquid SET names selected today (survivorship caveat on absolute level).
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
OUT_JSON = ROOT / "research" / "artifacts" / "thai_set.json"

COST_FEE_ONLY = 0.00168   # 16.8 bp/side (0.157% + 7% VAT)
COST_RETAIL = 0.00270     # 27.0 bp/side (fees + ~10 bp spread/tick)
N_NULL = 200


def load_thai() -> tuple[pd.DataFrame, pd.DataFrame]:
    prices, vols = {}, {}
    for p in sorted((ROOT / "data" / "thai").glob("*.csv")):
        sym = p.stem
        if sym == "SET_EW":
            continue
        df = pd.read_csv(p)
        if "date" not in df.columns or "close" not in df.columns:
            continue
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").drop_duplicates("date")
        s = pd.to_numeric(df["close"], errors="coerce")
        v = pd.to_numeric(df.get("volume"), errors="coerce") if "volume" in df else pd.Series(np.nan, index=df.index)
        prices[sym] = pd.Series(s.values, index=df["date"])
        vols[sym] = pd.Series(v.values, index=df["date"])
    px = pd.DataFrame(prices).sort_index().ffill(limit=3)
    vo = pd.DataFrame(vols).reindex(px.index)
    return px, vo


def load_global_macro(dates: pd.DatetimeIndex) -> pd.DataFrame:
    m = pd.DataFrame(index=dates)
    vt = pd.read_csv(ROOT / "data" / "collect" / "vol_stress_features.csv", index_col=0, parse_dates=True).sort_index()
    # Global US close on day D occurs AFTER Bangkok close -> lag 1 US calendar day to prevent any timezone leak
    vt = vt.shift(1)
    for c in ["vix", "slope_3m"]:
        m[c] = vt[c].reindex(dates, method="ffill")
    fsi = pd.read_csv(ROOT / "data" / "collect" / "ofr_fsi.csv")
    fsi["Date"] = pd.to_datetime(fsi["Date"])
    fsi = fsi.sort_values("Date").drop_duplicates("Date").set_index("Date").shift(1)
    m["ofr_fsi"] = pd.to_numeric(fsi["OFR FSI"], errors="coerce").reindex(dates, method="ffill")
    for c in ["vix", "ofr_fsi"]:
        mu = m[c].rolling(252, min_periods=60).mean()
        sd = m[c].rolling(252, min_periods=60).std().replace(0, np.nan)
        m[f"{c}_z"] = ((m[c] - mu) / sd).clip(-3, 3).fillna(0.0)
    m["slope_3m_c"] = (m["slope_3m"] - 1.0).clip(-0.3, 0.3).fillna(0.0)
    return m


def cs_rank(df: pd.DataFrame) -> pd.DataFrame:
    return df.rank(axis=1, pct=True) - 0.5


def build_features(px: pd.DataFrame, vo: pd.DataFrame, macro: pd.DataFrame) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    ret1 = px.pct_change(fill_method=None)
    feats = {}
    feats["ret_1d"] = cs_rank(px.pct_change(1, fill_method=None))
    feats["ret_5d"] = cs_rank(px.pct_change(5, fill_method=None))
    feats["ret_21d"] = cs_rank(px.pct_change(21, fill_method=None))
    feats["ret_63d"] = cs_rank(px.pct_change(63, fill_method=None))
    feats["ret_126d"] = cs_rank(px.pct_change(126, fill_method=None))
    feats["mom_12_1"] = cs_rank(px.shift(21) / px.shift(252) - 1.0)
    vol21 = ret1.rolling(21, min_periods=15).std()
    vol63 = ret1.rolling(63, min_periods=40).std()
    feats["vol_21d"] = cs_rank(vol21)
    feats["vol_63d"] = cs_rank(vol63)
    feats["mom_vol_adj"] = cs_rank(px.pct_change(63, fill_method=None) / vol63.replace(0, np.nan))
    feats["rev_vol_adj"] = cs_rank(-px.pct_change(5, fill_method=None) / vol21.replace(0, np.nan))
    hi252 = px.rolling(252, min_periods=126).max()
    feats["dist_hi252"] = cs_rank(px / hi252.replace(0, np.nan) - 1.0)
    ma20 = px.rolling(20, min_periods=15).mean()
    feats["dist_ma20"] = cs_rank(px / ma20.replace(0, np.nan) - 1.0)
    up = ret1.clip(lower=0).rolling(14, min_periods=10).mean()
    dn = (-ret1.clip(upper=0)).rolling(14, min_periods=10).mean()
    feats["rsi14"] = cs_rank(100.0 - 100.0 / (1.0 + up / dn.replace(0, np.nan)))
    vma20 = vo.rolling(20, min_periods=10).mean()
    feats["vol_surge"] = cs_rank(vo / vma20.replace(0, np.nan))

    feats["ix_vixslope_mom"] = feats["mom_vol_adj"].mul(macro["slope_3m_c"], axis=0)
    feats["ix_vixz_vol"] = feats["vol_21d"].mul(macro["vix_z"], axis=0)
    feats["ix_fsiz_rev21"] = feats["ret_21d"].mul(macro["ofr_fsi_z"], axis=0)
    return feats, ret1


def compute_weights(score_df: pd.DataFrame, dates: pd.DatetimeIndex, syms: pd.Index, mode: str = "ls") -> pd.DataFrame:
    n_dates = len(dates)
    daily_w = np.zeros((n_dates, len(syms)), dtype=float)
    pos_map = {d: i for i, d in enumerate(dates)}
    reb_targets = {}
    for d, row in score_df.iterrows():
        s = row.values
        valid = np.isfinite(s)
        n_v = int(valid.sum())
        w = np.zeros(len(syms), dtype=float)
        if n_v >= 20:
            q = max(4, n_v // 5)
            top_idx = np.argsort(np.where(valid, s, -np.inf))[-q:]
            bot_idx = np.argsort(np.where(valid, s, np.inf))[:q]
            if mode == "ls":
                w[top_idx] = 1.0 / q
                w[bot_idx] = -1.0 / q
            else:
                w[top_idx] = 1.0 / q
        t_pos = pos_map[d]
        if t_pos + 1 < n_dates:
            reb_targets[t_pos + 1] = w
    cur_w = np.zeros(len(syms), dtype=float)
    for i in range(n_dates):
        if i in reb_targets:
            cur_w = reb_targets[i]
        daily_w[i] = cur_w
    return pd.DataFrame(daily_w, index=dates, columns=syms)


def eval_weights(w_held: pd.DataFrame, ret1: pd.DataFrame, start_pos: int, split_pos: int, cost: float) -> dict:
    W = w_held.values
    R = np.nan_to_num(ret1.values, nan=0.0)
    gross = np.sum(W[:-1] * R[1:], axis=1)
    turn = np.sum(np.abs(W[1:] - W[:-1]), axis=1)
    net = gross - cost * turn

    def _st(g, n, t):
        sd_n = float(np.std(n, ddof=1))
        sd_g = float(np.std(g, ddof=1))
        sh_n = float(np.mean(n) / sd_n * np.sqrt(252)) if sd_n > 0 else 0.0
        sh_g = float(np.mean(g) / sd_g * np.sqrt(252)) if sd_g > 0 else 0.0
        eq = np.cumprod(1.0 + n)
        yrs = len(n) / 252.0
        cagr = float((eq[-1] ** (1.0 / yrs) - 1.0) * 100.0) if np.all(eq > 0) else -100.0
        pk = np.maximum.accumulate(eq)
        mdd = float(((eq / pk) - 1.0).min() * 100.0) if np.all(eq > 0) else -100.0
        # Breakeven cost per side (bp) = mean(gross) / mean(turn) * 1e4
        mean_turn = float(np.mean(t))
        be_bp = float(np.mean(g) / mean_turn * 1e4) if mean_turn > 0 else 0.0
        return {
            "sharpe_net": round(sh_n, 3),
            "sharpe_gross": round(sh_g, 3),
            "cagr_net_pct": round(cagr, 2),
            "maxdd_pct": round(mdd, 2),
            "ann_turn": round(mean_turn * 252.0, 2),
            "breakeven_bp_side": round(be_bp, 1),
        }

    return {
        "IS": _st(gross[start_pos:split_pos - 1], net[start_pos:split_pos - 1], turn[start_pos:split_pos - 1]),
        "OOS": _st(gross[split_pos - 1:], net[split_pos - 1:], turn[split_pos - 1:]),
    }


def turnover_matched_null(w_held: pd.DataFrame, ret1: pd.DataFrame, start_pos: int, split_pos: int,
                          cost: float, seed: int = 7) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    W = w_held.values
    R = np.nan_to_num(ret1.values, nan=0.0)
    turn = np.sum(np.abs(W[1:] - W[:-1]), axis=1)
    obs = eval_weights(w_held, ret1, start_pos, split_pos, cost)
    n_syms = W.shape[1]
    sh_is, sh_oos = np.empty(N_NULL), np.empty(N_NULL)
    for k in range(N_NULL):
        Wp = W[:, rng.permutation(n_syms)]
        net = np.sum(Wp[:-1] * R[1:], axis=1) - cost * turn
        a, b = net[start_pos:split_pos - 1], net[split_pos - 1:]
        sh_is[k] = float(np.mean(a) / np.std(a, ddof=1) * np.sqrt(252)) if np.std(a, ddof=1) > 0 else 0.0
        sh_oos[k] = float(np.mean(b) / np.std(b, ddof=1) * np.sqrt(252)) if np.std(b, ddof=1) > 0 else 0.0
    return (
        round(float((sh_is < obs["IS"]["sharpe_net"]).mean() * 100.0), 1),
        round(float((sh_oos < obs["OOS"]["sharpe_net"]).mean() * 100.0), 1),
    )


def walk_forward_predict(feats: dict[str, pd.DataFrame], cols: list[str], px: pd.DataFrame,
                         horizon: int, model_type: str, dates: pd.DatetimeIndex, step: int) -> pd.DataFrame:
    fwd = px.shift(-(horizon + 1)) / px.shift(-1) - 1.0
    fwd_xs = fwd.sub(fwd.mean(axis=1), axis=0)
    X_cube = np.stack([feats[c].values for c in cols], axis=-1)
    Y_mat = fwd_xs.values
    reb_indices = list(range(504, len(dates) - horizon - 2, step))
    scores = pd.DataFrame(np.nan, index=[dates[i] for i in reb_indices], columns=px.columns)

    model, last_fit = None, -999
    for i in reb_indices:
        if model is None or (i - last_fit) >= 63:
            max_tr = i - horizon - 2
            if max_tr < 260:
                continue
            X_tr_l, y_tr_l = [], []
            for s in range(255, max_tr + 1, max(3, horizon // 2)):
                y_s, x_s = Y_mat[s], X_cube[s]
                ok = np.isfinite(y_s) & np.all(np.isfinite(x_s), axis=1)
                if ok.sum() >= 15:
                    X_tr_l.append(x_s[ok])
                    y_tr_l.append(np.clip(y_s[ok], -0.4, 0.4))
            if not X_tr_l:
                continue
            X_tr, y_tr = np.vstack(X_tr_l), np.concatenate(y_tr_l)
            if model_type == "ridge":
                model = Ridge(alpha=500.0).fit(X_tr, y_tr)
            else:
                model = HistGradientBoostingRegressor(
                    max_iter=80, max_depth=3, learning_rate=0.05,
                    min_samples_leaf=150, l2_regularization=20.0, random_state=42
                ).fit(X_tr, y_tr)
            last_fit = i
        x_now = X_cube[i]
        ok_now = np.all(np.isfinite(x_now), axis=1)
        if ok_now.sum() >= 15 and model is not None:
            pred = np.full(px.shape[1], np.nan)
            pred[ok_now] = model.predict(x_now[ok_now])
            scores.loc[dates[i]] = pred
    return scores


def main() -> None:
    print("Loading Thai SET 64-stock panel...")
    px, vo = load_thai()
    dates, syms = px.index, px.columns
    macro = load_global_macro(dates)
    feats, ret1 = build_features(px, vo, macro)
    cols = list(feats.keys())

    start_pos = 505
    split_pos = start_pos + int(0.70 * (len(dates) - start_pos))
    wf_start = dates[start_pos].strftime("%Y-%m-%d")
    split_date = dates[split_pos].strftime("%Y-%m-%d")
    print(f"Panel: {len(syms)} SET stocks, {len(dates)} sessions | WF {wf_start}..{dates[-1]:%Y-%m-%d} | split {split_date}")

    # Equal-weight benchmark over active names each day
    active = px.notna().astype(float)
    ew_w = active.div(active.sum(axis=1), axis=0).fillna(0.0)
    ew_res = eval_weights(ew_w, ret1, start_pos, split_pos, cost=0.0)
    print(f"SET64_EW Buy&Hold (price-only): IS Sharpe {ew_res['IS']['sharpe_net']:+.3f} ({ew_res['IS']['cagr_net_pct']:+.2f}%/yr) | "
          f"OOS Sharpe {ew_res['OOS']['sharpe_net']:+.3f} ({ew_res['OOS']['cagr_net_pct']:+.2f}%/yr)")

    arms = [
        ("TH_REV_5D", -feats["ret_5d"], 5, None),
        ("TH_REV_21D", -feats["ret_21d"], 21, None),
        ("TH_MOM_12_1_21D", feats["mom_12_1"], 21, None),
        ("TH_ML_RIDGE_21D", None, 21, "ridge"),
        ("TH_ML_HGB_21D", None, 21, "hgb"),
    ]

    results = {}
    any_pass = False
    for name, fixed_sc, step, mtype in arms:
        if mtype is None:
            reb_dates = [dates[i] for i in range(504, len(dates) - step - 2, step)]
            sc = fixed_sc.loc[reb_dates]
        else:
            sc = walk_forward_predict(feats, cols, px, step, mtype, dates, step)

        w_ls = compute_weights(sc, dates, syms, mode="ls")
        w_lo = compute_weights(sc, dates, syms, mode="lo")

        ev_ret = eval_weights(w_ls, ret1, start_pos, split_pos, COST_RETAIL)
        ev_fee = eval_weights(w_ls, ret1, start_pos, split_pos, COST_FEE_ONLY)
        ev_lo = eval_weights(w_lo, ret1, start_pos, split_pos, COST_RETAIL)
        pct_is, pct_oos = turnover_matched_null(w_ls, ret1, start_pos, split_pos, COST_RETAIL)
        pct_lo_is, pct_lo_oos = turnover_matched_null(w_lo, ret1, start_pos, split_pos, COST_RETAIL)

        passed = (
            pct_is >= 99.0 and pct_oos >= 99.0
            and ev_ret["IS"]["sharpe_net"] > 0 and ev_ret["OOS"]["sharpe_net"] > 0
            and ev_fee["IS"]["sharpe_net"] > 0 and ev_fee["OOS"]["sharpe_net"] > 0
            and ev_lo["IS"]["sharpe_net"] > ew_res["IS"]["sharpe_net"]
            and ev_lo["OOS"]["sharpe_net"] > ew_res["OOS"]["sharpe_net"]
        )
        if passed:
            any_pass = True

        results[name] = {
            "ls_retail_27bp": {"IS": ev_ret["IS"], "OOS": ev_ret["OOS"], "null_pct_IS": pct_is, "null_pct_OOS": pct_oos},
            "ls_feeonly_16_8bp": {"IS": ev_fee["IS"], "OOS": ev_fee["OOS"]},
            "lo_topq_27bp": {"IS": ev_lo["IS"], "OOS": ev_lo["OOS"], "null_pct_IS": pct_lo_is, "null_pct_OOS": pct_lo_oos},
            "pass_bar": passed,
        }
        print(f"  {name:17s} LS 27bp | IS {ev_ret['IS']['sharpe_net']:+.3f} (gross {ev_ret['IS']['sharpe_gross']:+.3f}, "
              f"pct {pct_is:4.1f}, BE {ev_ret['IS']['breakeven_bp_side']:+.1f}bp) | "
              f"OOS {ev_ret['OOS']['sharpe_net']:+.3f} (gross {ev_ret['OOS']['sharpe_gross']:+.3f}, "
              f"pct {pct_oos:4.1f}, BE {ev_ret['OOS']['breakeven_bp_side']:+.1f}bp) | "
              f"LO OOS {ev_lo['OOS']['sharpe_net']:+.3f} (pct {pct_lo_oos:4.1f}) | PASS={passed}")

    verdict = "PASS" if any_pass else "FAIL"
    out = {
        "exp_id": "EXP-0021",
        "hyp_id": "H23",
        "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "universe": f"{len(syms)} Thai SET stocks (data/thai)",
        "walk_forward_range": f"{wf_start}..{dates[-1]:%Y-%m-%d}",
        "is_oos_split": split_date,
        "cost_feeonly_bp_side": 16.8,
        "cost_retail_bp_side": 27.0,
        "set64_ew_benchmark": {"IS": ew_res["IS"], "OOS": ew_res["OOS"]},
        "arms": results,
        "verdict": verdict,
    }
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(f"\nEXP-0021 verdict: {verdict} -> {OUT_JSON}")


if __name__ == "__main__":
    main()
