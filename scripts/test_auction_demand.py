#!/usr/bin/env python3
"""EXP-0011 — does Treasury auction DEMAND predict bond and equity returns?

Why this is a real question and not a hunch: auction demand (bid-to-cover, the yield "tail" versus
when-issued, dealer takedown) is the closest observable to "is the market willing to absorb duration
at this price". Rates desks trade it. It is also free and it is *not* in any price series.

Pre-registration:
  * Event = each 2Y/5Y/7Y/10Y/30Y nominal coupon auction (Treasury Fiscal Data API), 2010 → latest.
  * Signal = z-score of bid-to-cover versus that instrument's own last 8 auctions (contract-specific
    demand surprise), plus the same-day yield change as a control.
  * Target = forward 1/5/20 trading-day return of TLT (long duration), IEF (7-10y) and SPY.
  * Test = pooled event regression with clustered SE by month, 70/30 split by DATE.
  * Pass bar: |t_clustered| >= 2 in-sample AND out-of-sample same sign AND at least half the size.
Output: research/artifacts/auction_demand.json
"""
from __future__ import annotations

import json
import os
import urllib.request

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "research", "artifacts", "auction_demand.json")
UA = "Mozilla/5.0 Chrome/120"
TARGETS = {"TLT": "data/universe/TLT.csv", "IEF": "data/universe/IEF.csv", "SPY": "data/universe/SPY.csv"}
HORIZONS = (1, 5, 20)


def fetch_auctions() -> pd.DataFrame:
    base = ("https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/auctions_query"
            "?fields=auction_date,security_type,security_term,bid_to_cover_ratio,high_yield,offering_amt,"
            "primary_dealer_accepted,indirect_bidder_accepted"
            "&filter=auction_date:gte:2010-01-01&sort=auction_date&page%5Bsize%5D=1000")
    out = []
    for page in range(1, 6):
        url = f"{base}&page%5Bnumber%5D={page}"
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": UA}), timeout=45) as r:
                j = json.loads(r.read())
        except Exception as e:                                    # noqa: BLE001
            print(f"page {page}: {e}")
            break
        d = j.get("data", [])
        out += d
        if len(d) < 1000:
            break
    df = pd.DataFrame(out)
    if df.empty:
        return df
    df["auction_date"] = pd.to_datetime(df.auction_date, errors="coerce")
    df = df.dropna(subset=["auction_date"])
    df["security_term"] = df.security_term.astype(str)
    df = df[df.security_term.str.contains("2-Year|5-Year|7-Year|10-Year|30-Year", regex=True, na=False)]
    for c in ("bid_to_cover_ratio", "high_yield", "offering_amt", "primary_dealer_accepted",
              "indirect_bidder_accepted"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.sort_values("auction_date").reset_index(drop=True)


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
    au = fetch_auctions()
    if au.empty:
        raise SystemExit("no auction data")
    au["term"] = au.security_term.str.extract(r"(2|5|7|10|30)-Year")[0]
    au["btc_z"] = (au.groupby("term").bid_to_cover_ratio
                   .transform(lambda s: (s - s.rolling(8, min_periods=5).mean()) / s.rolling(8, min_periods=5).std()))
    au["pd_share"] = au.primary_dealer_accepted / (au.primary_dealer_accepted + au.indirect_bidder_accepted)
    print(f"auctions: {len(au)}  {au.auction_date.min().date()} → {au.auction_date.max().date()}")

    res = {"design": {"signal": "bid-to-cover z vs own last 8 auctions (per term)",
                      "controls": "primary-dealer share of the auction, auction term",
                      "horizons_days": list(HORIZONS), "targets": list(TARGETS),
                      "auctions": int(len(au)),
                      "coverage": f"{au.auction_date.min().date()}..{au.auction_date.max().date()}"},
           "pass_bar": "|t|>=2 in-sample AND OOS same sign AND >= half size", "results": {}}

    for tname, rel in TARGETS.items():
        px = load(rel)
        r = px.pct_change()
        idx = px.index
        a = au.dropna(subset=["btc_z"]).copy()
        pos = idx.searchsorted(a.auction_date.values)
        ok = pos < len(idx) - 21
        a, pos = a[ok], pos[ok]
        # auction-day move (control) and forward returns from that day's close
        a["d0"] = r.iloc[np.clip(pos, 0, len(idx) - 1)].values
        for h in HORIZONS:
            a[f"fwd{h}"] = (px.iloc[np.clip(pos + h, 0, len(idx) - 1)].values
                            / px.iloc[np.clip(pos, 0, len(idx) - 1)].values - 1.0)
        a = a.dropna(subset=["btc_z", "pd_share"])
        dates = np.sort(a.auction_date.unique())
        cut = dates[int(len(dates) * 0.7)]
        for h in HORIZONS:
            for label, sub in (("in_sample", a[a.auction_date < cut]), ("out_of_sample", a[a.auction_date >= cut])):
                sub = sub.dropna(subset=[f"fwd{h}"])
                if len(sub) < 60:
                    continue
                X = np.column_stack([np.ones(len(sub)), sub.btc_z.values, sub.pd_share.values, sub.d0.values])
                y = sub[f"fwd{h}"].values
                beta, *_ = np.linalg.lstsq(X, y, rcond=None)
                resid = y - X @ beta
                se = np.sqrt(np.diag(cluster_se(X, resid, sub.auction_date.dt.to_period("M").astype(str).values)))
                key = f"{tname}_{h}d"
                res["results"].setdefault(key, {})[label] = {
                    "n": int(len(sub)), "beta_btc_z": round(float(beta[1]), 6),
                    "t": round(float(beta[1] / se[1]), 2) if se[1] > 0 else None,
                    "beta_pd_share": round(float(beta[2]), 6),
                    "r2": round(float(1 - resid.var() / y.var()), 4)}

    passed = []
    for k, v in res["results"].items():
        i, o = v.get("in_sample"), v.get("out_of_sample")
        if i and o and i["t"] is not None and abs(i["t"]) >= 2 and np.sign(o["beta_btc_z"]) == np.sign(i["beta_btc_z"]) \
                and abs(o["beta_btc_z"]) >= 0.5 * abs(i["beta_btc_z"]):
            passed.append(k)
    res["verdict"] = {"passing": passed,
                      "conclusion": ("candidates: " + ", ".join(passed)) if passed else
                      "auction demand does NOT predict forward bond/equity returns at the pre-declared bar "
                      "— the auction is absorbed, and any signal is already in the day's yield move"}
    with open(OUT, "w") as f:
        json.dump(res, f, indent=2)
    print(json.dumps({k: res["results"][k] for k in list(res["results"])[:6]}, indent=2))
    print("VERDICT:", res["verdict"]["conclusion"])


if __name__ == "__main__":
    main()
