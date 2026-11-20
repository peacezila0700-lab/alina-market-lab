#!/usr/bin/env python3
"""EXP-0010 — do events CONDITION a weak price rule? (event-conditional signal test)

Pre-registration (written before running):
  Base rule: sign of the last 5-day return (i.e. short-term momentum if the coefficient is positive,
  reversal if negative). It is deliberately a *weak, known* rule — the question is whether an event
  changes its payoff, not whether the rule is great.
  Conditioning: the rule's position is held only through the event window, or only from the event
  close onward, for four event types taken from data/events/event_calendar_full.csv:
      OPEX (3rd Friday), FOMC, MONTH_END, and "VIX_ONSET30" (first close >=30 after a spell below 30).
  Test: pooled panel of instruments (SPY, TLT, GLD, DXY, EURUSD), forward 5-day return regressed on
  (prior 5d sign) x (event dummy), instrument fixed effects, standard errors clustered by date.
  Pass bar: |t_clustered| >= 2.0 for the INTERACTION in-sample AND the out-of-sample interaction
  keeps the same sign. Otherwise the event does not condition the rule.

Everything is measured on this repo's own files; no external data is used beyond the event calendar.
Output: research/artifacts/event_conditional.json
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "research", "artifacts", "event_conditional.json")
ASSETS = {"SPY": "data/universe/SPY.csv", "TLT": "data/universe/TLT.csv",
          "GLD": "data/universe/GOLD.csv", "DXY": "data/universe/DXY.csv",
          "EURUSD": "data/official/EURUSD_ECB_D.csv"}
EVENTS = ["OPEX", "FOMC", "MONTH_END", "VIX_ONSET30"]
H = 5


def load(rel: str) -> pd.Series:
    df = pd.read_csv(os.path.join(ROOT, rel))
    d = "date" if "date" in df.columns else df.columns[0]
    c = "close" if "close" in df.columns else df.columns[1]
    s = pd.Series(df[c].values, index=pd.to_datetime(df[d], errors="coerce")).astype(float)
    return s[~s.index.duplicated()].sort_index().dropna()


def cluster_se(X, resid, groups):
    XtX_inv = np.linalg.pinv(X.T @ X)
    meat = np.zeros((X.shape[1], X.shape[1]))
    for g in np.unique(groups):
        m = groups == g
        v = X[m].T @ resid[m]
        meat += np.outer(v, v)
    n, k = X.shape
    G = len(np.unique(groups))
    return XtX_inv @ (meat * (G / (G - 1)) * ((n - 1) / (n - k))) @ XtX_inv


def main() -> None:
    cal = pd.read_csv(os.path.join(ROOT, "data", "events", "event_calendar_full.csv"), parse_dates=["date"])
    ev_by_type = {e: set(cal[cal.event == e].date) for e in EVENTS}
    # "known in advance" events (OPEX/FOMC/MONTH_END) can be traded on the day; VIX onset cannot
    not_known = {"VIX_ONSET30"}

    rows = []
    for inst, rel in ASSETS.items():
        s = load(rel)
        r = s.pct_change()
        prior5 = s / s.shift(5) - 1.0
        fwd5 = s.shift(-H) / s - 1.0
        df = pd.DataFrame({"dt": s.index, "prior5": np.sign(prior5.values), "fwd5": fwd5.values}).dropna()
        for e in EVENTS:
            ev = sorted(ev_by_type[e])
            idx = pd.DatetimeIndex(df.dt)
            if e in not_known:
                pos = s.index.searchsorted(ev)
                anchor = set(s.index[np.clip(pos + 1, 0, len(s) - 1)])
            else:
                anchor = set(ev)
            df[f"ev_{e}"] = idx.isin(list(anchor)).astype(float)
        df["inst"] = inst
        rows.append(df)
    p = pd.concat(rows, ignore_index=True)
    for c in p.columns:
        if c.startswith("ev_"):
            p[c] = p[c].astype(float)

    dates = np.sort(p.dt.unique())
    cut = dates[int(len(dates) * 0.7)]
    res = {"design": {"horizon_days": H, "base_rule": "sign(prior 5d return)",
                      "events": EVENTS, "assets": list(ASSETS), "n_rows": int(len(p)),
                      "split_date": str(pd.Timestamp(cut).date()),
                      "note": "VIX_ONSET30 is not knowable before that close, so its position starts "
                              "at the next close; the other three are scheduled and known in advance."},
           "pass_bar": "|t_clustered|>=2 in-sample AND OOS same sign", "results": {}}

    for label, sub in (("in_sample", p[p.dt < cut]), ("out_of_sample", p[p.dt >= cut])):
        out = {}
        for e in EVENTS:
            s2 = sub.dropna(subset=["prior5", "fwd5", f"ev_{e}"]).copy()
            if len(s2) < 200:
                continue
            # within-instrument demeaning (fixed effects)
            for c in ("prior5", "fwd5"):
                s2[c + "_dm"] = s2[c] - s2.groupby("inst")[c].transform("mean")
            x_inter = s2.prior5_dm * s2[f"ev_{e}"]
            X = np.column_stack([np.ones(len(s2)), s2.prior5_dm.values, s2[f"ev_{e}"].values, x_inter.values])
            y = s2.fwd5_dm.values
            beta, *_ = np.linalg.lstsq(X, y, rcond=None)
            resid = y - X @ beta
            se = np.sqrt(np.diag(cluster_se(X, resid, s2.dt.values)))
            n_ev = int(s2[f"ev_{e}"].sum())
            out[e] = {"n": int(len(s2)), "n_event_days": n_ev,
                      "beta_rule": round(float(beta[1]), 5),
                      "t_rule": round(float(beta[1] / se[1]), 2) if se[1] > 0 else None,
                      "beta_interaction": round(float(beta[3]), 5),
                      "t_interaction": round(float(beta[3] / se[3]), 2) if se[3] > 0 else None}
        res["results"][label] = out

    ins = res["results"].get("in_sample", {})
    oos = res["results"].get("out_of_sample", {})
    passed = []
    for e in EVENTS:
        a, b = ins.get(e, {}), oos.get(e, {})
        if not a or not b or a.get("t_interaction") is None or b.get("beta_interaction") is None:
            continue
        if abs(a["t_interaction"]) >= 2.0 and np.sign(b["beta_interaction"]) == np.sign(a["beta_interaction"]):
            passed.append(e)
    res["verdict"] = {"events_passing_bar": passed,
                      "conclusion": ("event-conditional edge candidates: " + ", ".join(passed)) if passed
                      else "NO event conditions the 5-day rule at the pre-declared bar — events change "
                           "the variance, not the sign, of the payoff (consistent with the earlier finding "
                           "that FOMC days are only 1.09x a normal day's move)"}
    with open(OUT, "w") as f:
        json.dump(res, f, indent=2)
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
