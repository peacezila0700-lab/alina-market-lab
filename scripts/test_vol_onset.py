#!/usr/bin/env python3
"""
EXP-0015 — Is a volatility ONSET predictable, and does acting on it beat plain volatility targeting?

CONTEXT (why this replaces calendar strategies)
EVENT_STATS says scheduled events do not move the tape more than a random day (FOMC 1.09x, OPEX 0.91x)
while crisis onset does (SHOCK_2.5SIG 1.75x, VIX_ONSET30 1.65x). So the exploitable object is the
ONSET, not the calendar. EXP-0013/0014 showed state variables move variance and not return, and that
anything must be benchmarked against vol targeting. This test therefore asks exactly one question:

    Does the CBOE term structure (VIX/VIX3M, VIX9D/VIX, VVIX) forecast a volatility onset early
    enough to be worth acting on, net of what volatility targeting already does for free?

PRE-REGISTERED DESIGN (written before the result)
-------------------------------------------------
Sample      : SPY daily 2011-01-04 .. latest (VIX9D starts 2011; VIX3M 2009; VVIX 2006).
Targets     : ON1 = VIX closes above 30 having been below 28 the previous day (the crisis-onset label).
              ON2 = RV20(t) > 1.5 x median RV20 over t-60..t-1 (vol-expansion onset, more frequent).
Features    : every feature is taken at t-1 (or at the same close, only if the label is measured
              from t+1 onward): vix level percentile (252d), slope_3m = VIX/VIX3M, slope_9d = VIX9D/VIX,
              vvix percentile, skew percentile, HYG/IEF 20-day return, breadth200 (11 sectors above
              their 200-day MA), dealer GEX sign, SPY 20-day realised vol percentile.
Model       : L2 logistic regression on standardised features, WALK-FORWARD: fit on everything up to
              year Y-1, predict year Y, refit each January. No hyper-parameter search, C fixed at 1.0.
Metrics     : OOS AUC, Brier skill vs the training base rate, and calibration by predicted-probability
              decile. Reported for both targets.
Economic    : SPY exposure, three arms, mean exposure matched:
                A  p-based  : w = 0.4 if p(t-1) >= threshold else 1.4   (threshold = in-sample 80th
                            percentile of p, fixed before OOS)
                B  voltarget: w = clip(0.15/RV20(t-1),0,2) * k           (k matches mean exposure of A)
                C  buy&hold : w = 1
              Statistic: Δ = Sharpe(A) − Sharpe(B); null = circular shifts of A's weight series (200).

PASS BAR (pre-declared)
  OOS AUC >= 0.65 on at least one target AND Δ(A−B) > 0 with percentile >= 95 on the OOS slice.
  A high AUC with no economic increment is a FAIL and is logged as "predictable but not tradeable" —
  which is itself an important, reusable finding (the onset is already in the vol estimate).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "artifacts" / "vol_onset.json"
SECTORS = ["XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"]
COST_BP = 2.0
N_SHIFT = 200


def load_broad(sym):
    df = pd.read_csv(ROOT / "data" / "broad" / f"{sym}.csv")
    dc = next(c for c in df.columns if c.lower() in ("date", "datetime"))
    cc = next(c for c in df.columns if c.lower() in ("close", "adj close", "price"))
    df[dc] = pd.to_datetime(df[dc])
    return df.set_index(dc)[cc].astype(float).sort_index()


def sharpe(r):
    r = pd.Series(r).dropna()
    return float(r.mean() / r.std() * np.sqrt(252)) if len(r) > 60 and r.std() > 0 else np.nan


def perf(r, w):
    df = pd.DataFrame({"r": r, "w": w}).dropna()
    dw = df["w"].astype(float).diff().abs().fillna(0.0)
    net = df["w"].astype(float) * df["r"] - dw * COST_BP / 1e4
    eq = (1 + net).cumprod()
    return {"sharpe": sharpe(net), "cagr": float(eq.iloc[-1] ** (252 / len(net)) - 1),
            "maxdd": float((eq / eq.cummax() - 1).min()), "n": int(len(net)),
            "mean_w": float(df["w"].mean()), "vol": float(net.std() * np.sqrt(252))}


def auc(y, p):
    y = np.asarray(y, float)
    p = np.asarray(p, float)
    m = ~(np.isnan(y) | np.isnan(p))
    y, p = y[m], p[m]
    if len(np.unique(y)) < 2:
        return np.nan
    order = np.argsort(p)
    ranks = np.empty(len(p), float)
    ranks[order] = np.arange(1, len(p) + 1)
    n1 = y.sum()
    n0 = len(y) - n1
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def logit_fit(X, y, l2=1.0):
    """plain Newton/IRLS logistic with L2, no scaling issues: X already standardised."""
    n, k = X.shape
    beta = np.zeros(k)
    for _ in range(50):
        z = X @ beta
        p = 1 / (1 + np.exp(-np.clip(z, -30, 30)))
        W = np.clip(p * (1 - p), 1e-6, None)
        grad = X.T @ (y - p) - l2 * beta
        H = (X * W[:, None]).T @ X + l2 * np.eye(k)
        try:
            step = np.linalg.solve(H, grad)
        except np.linalg.LinAlgError:
            break
        beta += step
        if np.abs(step).max() < 1e-8:
            break
    return beta


def main():
    spy = load_broad("SPY")
    vt = pd.read_csv(ROOT / "data" / "collect" / "vol_stress_features.csv", index_col=0, parse_dates=True)
    px = pd.DataFrame({s: load_broad(s) for s in SECTORS + ["HYG", "IEF"]})
    px["SPY"] = spy

    df = pd.DataFrame(index=spy.index)
    df["r"] = spy.pct_change()
    df["rv20"] = df["r"].rolling(20).std() * np.sqrt(252)
    df["rv_pct"] = df["rv20"].rolling(252, min_periods=120).rank(pct=True)
    df["vix"] = vt["vix"].reindex(df.index).ffill()
    df["vix_pct"] = df["vix"].rolling(252, min_periods=120).rank(pct=True)
    df["slope_3m"] = vt["slope_3m"].reindex(df.index).ffill()
    df["slope_9d"] = vt["slope_9d"].reindex(df.index).ffill()
    df["vvix_pct"] = vt["vvix_pct"].reindex(df.index).ffill()
    df["skew"] = vt["skew"].reindex(df.index).ffill()
    df["skew_pct"] = df["skew"].rolling(252, min_periods=120).rank(pct=True)
    df["credit_20d"] = (px["HYG"] / px["IEF"]).pct_change(20)
    ma200 = px[SECTORS].rolling(200).mean()
    df["breadth200"] = (px[SECTORS] > ma200).mean(axis=1)
    g = pd.read_csv(ROOT / "data" / "alt" / "dix_gex.csv")
    gc = next(c for c in g.columns if c.lower() == "gex")
    g["date"] = pd.to_datetime(g["date"])
    df["gex_pos"] = (g.set_index("date")[gc].astype(float).sort_index().reindex(df.index).ffill() > 0).astype(float)

    # labels, measured strictly forward
    # FORWARD-looking labels: does an onset happen within the next H days, given we are calm now?
    H = 8
    raw1 = ((df["vix"] > 30) & (df["vix"].shift(1) <= 28)).astype(float)
    med = df["rv20"].rolling(60).median().shift(1)
    raw2 = (df["rv20"] > 1.5 * med).astype(float)
    fwd = lambda s: s.iloc[::-1].rolling(H, min_periods=1).max().iloc[::-1].shift(-1)  # noqa: E731
    df["ON1"] = fwd(raw1)
    df["ON2"] = fwd(raw2)

    feats = ["vix_pct", "slope_3m", "slope_9d", "vvix_pct", "skew_pct", "credit_20d",
             "breadth200", "gex_pos", "rv_pct"]
    d = df.dropna(subset=feats + ["r"]).copy()
    print(f"  sample {d.index[0].date()} .. {d.index[-1].date()}  n={len(d)}")
    for lab in ("ON1", "ON2"):
        print(f"  {lab}: {int(d[lab].sum())} onsets ({d[lab].mean()*100:.2f}% of days)")

    # walk-forward logistic, refit each January on all prior data
    X = d[feats].copy()
    X = (X - X.rolling(252, min_periods=120).mean()) / X.rolling(252, min_periods=120).std()
    X = X.replace([np.inf, -np.inf], np.nan)
    probs = {}
    for lab in ("ON1", "ON2"):
        p = pd.Series(np.nan, index=d.index)
        years = sorted(set(d.index.year))
        for y in years[3:]:
            tr = d.index[d.index.year < y]
            te = d.index[d.index.year == y]
            Xtr = X.loc[tr].dropna()
            Xte = X.loc[te].dropna()
            if len(Xtr) < 500 or len(Xte) < 20:
                continue
            ytr = d.loc[Xtr.index, lab].values.astype(float)
            if ytr.sum() < 10:
                continue
            mu, sd = Xtr.mean(), Xtr.std().replace(0, 1)
            Z = np.column_stack([np.ones(len(Xtr)), ((Xtr - mu) / sd).values])
            beta = logit_fit(Z, ytr)
            Zte = np.column_stack([np.ones(len(Xte)), ((Xte - mu) / sd).values])
            p.loc[Xte.index] = 1 / (1 + np.exp(-np.clip(Zte @ beta, -30, 30)))
        probs[lab] = p
        ok = p.notna()
        a = auc(d.loc[ok, lab], p[ok])
        base = float(d.loc[ok, lab].mean())
        brier = float(((p[ok] - d.loc[ok, lab]) ** 2).mean())
        brier_base = float(((base - d.loc[ok, lab]) ** 2).mean())
        print(f"  {lab} walk-forward AUC {a:.3f}  Brier skill {1 - brier/brier_base:+.3f}  "
              f"(base rate {base*100:.2f}%, {int(ok.sum())} preds)")

    # economic test with ON1 probabilities
    p = probs["ON1"]
    live = p.dropna().index
    thr = float(p.loc[live[:int(len(live)*0.7)]].quantile(0.80))
    wA = pd.Series(np.where(p >= thr, 0.4, 1.4), index=d.index).where(p.notna()).shift(1)
    rv = df["rv20"].shift(1).reindex(d.index)
    raw = (0.15 / rv).clip(0, 2)
    # both arms already lagged one day: weights are set at the close and earn the next day's return
    kk = float(np.nanmean(wA) / np.nanmean(raw))
    wB = raw * kk
    print(f"  threshold p>={thr:.3f}; arms mean exposure A={np.nanmean(wA):.3f} B={np.nanmean(wB):.3f}")

    n = len(live)
    i_is, i_oos = live[:int(n * 0.70)], live[int(n * 0.70):]
    out = {}
    for name, w in (("A_probsize", wA), ("B_voltarget", wB)):
        out[name] = {"is": perf(d["r"].reindex(i_is), w.reindex(i_is)),
                     "oos": perf(d["r"].reindex(i_oos), w.reindex(i_oos))}
        print(f"  {name:<12} IS Sharpe {out[name]['is']['sharpe']:>6.3f}  OOS Sharpe {out[name]['oos']['sharpe']:>6.3f}"
              f"  maxDD IS {out[name]['is']['maxdd']:.1%} OOS {out[name]['oos']['maxdd']:.1%}")

    def delta(idx, label):
        a = wA.reindex(idx)
        b = wB.reindex(idx)
        rr = d["r"].reindex(idx)
        base = sharpe(b * rr - b.diff().abs().fillna(0) * COST_BP / 1e4)
        obs = sharpe(a * rr - a.diff().abs().fillna(0) * COST_BP / 1e4) - base
        s = a.ffill().bfill().values.astype(float)
        rng = np.random.default_rng(11)
        ds = []
        for _ in range(N_SHIFT):
            ws = pd.Series(np.roll(s, rng.integers(1, len(s))), index=idx)
            ds.append(sharpe(ws * rr - ws.diff().abs().fillna(0) * COST_BP / 1e4) - base)
        ds = np.array(ds)
        pct = float((ds < obs).mean() * 100)
        print(f"  Δ(A−B) {label}: {obs:+.3f}  pct {pct:.1f}  null p95 {np.percentile(ds,95):+.3f}")
        return obs, pct, float(np.percentile(ds, 95))

    d_is, p_is, _ = delta(i_is, "IS ")
    d_oos, p_oos, _ = delta(i_oos, "OOS")
    auc1 = auc(d.loc[p.notna(), "ON1"], p.dropna())
    auc2 = auc(d.loc[probs["ON2"].notna(), "ON2"], probs["ON2"].dropna())
    passed = (max(auc1, auc2) >= 0.65) and d_oos > 0 and p_oos >= 95
    print(f"\n  VERDICT: {'PASS (review)' if passed else 'FAIL'}"
          f"{' — predictable but not tradeable' if max(auc1,auc2) >= 0.65 and not passed else ''}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"experiment": "EXP-0015", "hypothesis": "H18",
                               "design": __doc__.split("PRE-REGISTERED DESIGN")[1][:2500],
                               "sample": [str(d.index[0].date()), str(d.index[-1].date())],
                               "onsets": {k: int(d[k].sum()) for k in ("ON1", "ON2")},
                               "auc": {"ON1": auc1, "ON2": auc2},
                               "arms": out, "threshold": thr, "vol_scale_k": kk,
                               "delta_is": d_is, "delta_is_pct": p_is,
                               "delta_oos": d_oos, "delta_oos_pct": p_oos,
                               "bar": "AUC>=0.65 on some target AND Δ(A−B)>0 at >=95th pct OOS",
                               "verdict": "PASS" if passed else "FAIL"}, indent=2, default=str))
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()
