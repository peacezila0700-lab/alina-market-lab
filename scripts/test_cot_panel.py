#!/usr/bin/env python3
"""B4 — POOLED COT PANEL TEST (the only pre-registered-quality test of the positioning idea).

Question: pooled across all contracts, does extreme non-commercial positioning predict forward
returns — and in which direction?

Why a panel and not the 59-instrument sweep already in this repo (H12): a single-instrument test has
almost no power (n≈20-40 non-overlapping events). Pooling 24 contracts multiplies the sample while
instrument fixed effects stop one market's drift from being mistaken for the effect.

Design (written BEFORE looking at the result — this file is the pre-registration):
  * Target  y = sign-adjusted forward 4-week return. sign = +1 if the futures contract is the same
    thing the price file quotes, -1 if the contract is the foreign currency (JPY/CHF/CAD) so that a
    net long contract position maps to the price direction it actually bets on.
  * Regressor x = (percentile rank of noncomm_net_pct_oi over a trailing 156 weeks) − 0.5, i.e. a
    centered crowding score in [-0.5, +0.5]. Positive x = funds crowded long.
  * Controls: instrument fixed effects (within-instrument demeaning) and a time trend.
  * Inference: standard errors clustered by report date (contracts are observed simultaneously, so
    cross-sectional correlation is guaranteed).
  * Split: first 70% of DATES in-sample, last 30% untouched out-of-sample. Decile spread reported
    out-of-sample only.
  * Non-overlapping: every 4th weekly report per instrument, so forward windows do not overlap.

Verdict rule (pre-declared): the idea lives only if |t_clustered| >= 2.0 in-sample AND the
out-of-sample decile spread has the same sign and at least half the magnitude. Anything else = dead.
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "research", "artifacts", "cot_panel.json")

PRICE_MAP = {
    "EURUSD": ("LEG:EURUSD", 1), "GBPUSD": ("LEG:GBPUSD", 1), "AUDUSD": ("LEG:AUDUSD", 1),
    "NZDUSD": ("LEG:NZDUSD", 1), "USDJPY": ("LEG:USDJPY", -1), "USDCHF": ("LEG:USDCHF", -1),
    "USDCAD": ("LEG:USDCAD", -1),
    "GOLD": ("data/universe/GOLD.csv", 1), "SILVER": ("data/universe/SILVER.csv", 1),
    "COPPER": ("data/universe/COPPER.csv", 1), "PLATINUM": ("data/universe/PLATINUM.csv", 1),
    "WTI": ("data/universe/WTI.csv", 1), "NATGAS": ("data/universe/NATGAS.csv", 1),
    "CORN": ("data/universe/CORN.csv", 1), "WHEAT": ("data/universe/WHEAT.csv", 1),
    "SP500": ("data/universe/SP500.csv", 1), "NASDAQ100": ("data/universe/NASDAQ100.csv", 1),
    "BTC": ("data/universe/BTC.csv", 1), "ETH": ("data/universe/ETH.csv", 1),
    "VIX": ("data/universe/VIXY.csv", 1), "UST_BOND": ("data/universe/TLT.csv", 1),
    "UST_10Y": ("data/universe/IEF.csv", 1),
}
H = 4          # weeks forward
MIN_N = 40     # per instrument, else the FE estimate is noise


def _ecb(ccy: str) -> pd.Series | None:
    p = os.path.join(ROOT, "data", "official", f"EUR{ccy}_ECB_D.csv")
    if not os.path.exists(p):
        return None
    d = pd.read_csv(p, parse_dates=["date"])
    return d.set_index("date")["close"].astype(float).sort_index()


def load_prices(rel: str) -> pd.Series | None:
    if rel.startswith("LEG:"):
        pair = rel[4:]
        base, quote = pair[:3], pair[3:]
        if base == "EUR":
            return _ecb(quote)
        if quote == "EUR":
            s = _ecb(base)
            return None if s is None else 1.0 / s
        a, b = _ecb(base), _ecb(quote)
        if a is None or b is None:
            return None
        s = (a / b).dropna()
        return s[s > 0]
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return None
    df = pd.read_csv(p)
    dc = "date" if "date" in df.columns else df.columns[0]
    cc = "close" if "close" in df.columns else df.columns[1]
    s = pd.Series(df[cc].values, index=pd.to_datetime(df[dc], errors="coerce")).astype(float)
    return s[~s.index.duplicated()].sort_index().dropna()


def cluster_se(X: np.ndarray, resid: np.ndarray, groups: np.ndarray) -> np.ndarray:
    """Cluster-robust covariance (CR1) for OLS: (X'X)^-1 (sum_g X_g'u_g u_g'X_g) (X'X)^-1."""
    XtX_inv = np.linalg.pinv(X.T @ X)
    meat = np.zeros((X.shape[1], X.shape[1]))
    for g in np.unique(groups):
        m = groups == g
        Xg, ug = X[m], resid[m]
        s = Xg.T @ ug
        meat += np.outer(s, s)
    n, k = X.shape
    G = len(np.unique(groups))
    adj = G / (G - 1) * (n - 1) / (n - k)
    return XtX_inv @ (meat * adj) @ XtX_inv


def main() -> None:
    cot = pd.read_csv(os.path.join(ROOT, "data", "cot", "cot_features.csv"),
                      parse_dates=["report_date", "available_from"])
    rows = []
    for inst, (rel, sign) in PRICE_MAP.items():
        px = load_prices(rel)
        if px is None:
            continue
        sub = cot[cot.instrument == inst].dropna(subset=["noncomm_net_pct_oi_pct156"]).copy()
        if len(sub) < 60:
            continue
        # non-overlapping: every H-th weekly observation
        sub = sub.iloc[::H].copy()
        idx = px.index
        pos = idx.searchsorted(sub.available_from.values)
        ok = pos < len(idx)
        sub, pos = sub[ok], pos[ok]
        entry_px = px.iloc[np.clip(pos, 0, len(idx) - 1)].values
        exit_px = []
        for p0 in np.clip(pos, 0, len(idx) - 1):
            j = min(p0 + int(H * 5), len(idx) - 1)      # ~4 weeks of trading days
            exit_px.append(px.iloc[j])
        sub["y"] = (np.array(exit_px) / entry_px - 1.0) * sign
        sub["x"] = sub.noncomm_net_pct_oi_pct156 - 0.5
        sub["inst"] = inst
        rows.append(sub[["report_date", "available_from", "inst", "x", "y"]])
    df = pd.concat(rows, ignore_index=True).dropna()
    # per-instrument demeaning = fixed effects
    df["y_dm"] = df.y - df.groupby("inst").y.transform("mean")
    df["x_dm"] = df.x - df.groupby("inst").x.transform("mean")

    dates = np.sort(df.report_date.unique())
    cut = dates[int(len(dates) * 0.7)]
    res = {"design": {"horizon_weeks": H, "non_overlapping": True, "split_date": str(pd.Timestamp(cut).date()),
                      "n_rows": int(len(df)), "n_instruments": int(df.inst.nunique()),
                      "regressor": "centered 156w percentile of noncomm_net_pct_oi",
                      "target": "sign-adjusted forward 4w return"},
           "verdict_rule": "|t_clustered|>=2 in-sample AND OOS decile spread same sign & >=half size"}
    for label, sub in (("in_sample", df[df.report_date < cut]), ("out_of_sample", df[df.report_date >= cut])):
        if len(sub) < 50:
            continue
        X = np.column_stack([np.ones(len(sub)), sub.x_dm.values])
        y = sub.y_dm.values
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        resid = y - X @ beta
        cov = cluster_se(X, resid, sub.report_date.values)
        se = np.sqrt(np.diag(cov))
        # decile spread: top vs bottom 20% of crowding, raw (un-demeaned) returns
        q = pd.qcut(sub.x, 5, labels=False, duplicates="drop")
        lo, hi = sub.y[q == 0], sub.y[q == q.max()]
        res[label] = {"n": int(len(sub)), "beta": round(float(beta[1]), 5),
                      "t_clustered": round(float(beta[1] / se[1]), 2),
                      "r2": round(float(1 - resid.var() / y.var()), 4),
                      "quintile_spread_pct": round(float(hi.mean() - lo.mean()) * 100, 3),
                      "q_means_pct": [round(float(sub.y[q == k].mean()) * 100, 3) for k in sorted(q.dropna().unique())]}

    ins, oos = res.get("in_sample", {}), res.get("out_of_sample", {})
    ok = (abs(ins.get("t_clustered", 0)) >= 2.0
          and np.sign(oos.get("quintile_spread_pct", 0)) == np.sign(ins.get("quintile_spread_pct", 0))
          and abs(oos.get("quintile_spread_pct", 0)) >= 0.5 * abs(ins.get("quintile_spread_pct", 0)))
    res["result"] = ("PASSES the pre-declared bar — promote to a strategy test"
                     if ok else "FAILS the pre-declared bar — close the hypothesis")
    with open(OUT, "w") as f:
        json.dump(res, f, indent=2)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
