#!/usr/bin/env python3
"""
EXP-0013 — Does a market-state overlay (breadth / credit / vol / positioning) improve a
plain long-SPY book, once you account for the fact that timing strategies can get lucky?

PRE-REGISTERED DESIGN (written before the result; do not edit after running)
------------------------------------------------------------------------------
Target      : SPY daily close-to-close return, 2000-01-03 .. latest.
Overlay     : exposure w_t in [0, 2], mean-normalised to 1 over the sample so the comparison is
              "same average exposure, different timing" — no free leverage in the comparison.
              w is computed from data available at the close of day t-1 and applied to day t.
Signals (6, all lagged, all causal):
  S1 BREADTH200 : share of the 11 sector SPDRs above their own 200-day MA, mapped linearly
                  w = clip(0.5 + 1.0*(b - 0.5), 0, 2)   (b = 0 -> 0x, b = 1 -> 1.5x)
  S2 BREADTH50  : same with 50-day MA
  S3 VIXLVL     : w = 1.5 if VIX < its own 60-day median else 0.5
  S4 CREDIT     : w = 1.5 if HYG/IEF ratio above its 60-day MA else 0.5   (risk-on credit)
  S5 GEXSIGN    : w = 1.5 if dealer GEX > 0 else 0.5                      (2011+ only)
  S6 DISP       : w = 1.5 if cross-sector 20-day return dispersion is BELOW its 1-year median
                  else 0.5  (crowded/quiet tape vs. rotating tape)
Also: BEST = equal-weight average of the six w series (a single combined signal, not selected
      after the fact).

Costs       : 2 bp of notional per unit of |Δw| (ETF commission + spread, generous).
Split       : first 70% of days = in-sample, last 30% = out-of-sample. Nothing is fitted —
              every parameter above is fixed a priori — so the split is a stability check, not a
              fitting device.

NULL (the honest part)
----------------------
A timing overlay has the same turnover as its own random circular shift. So the null is: shift the
weight series by a random offset (1..n-1) and re-run. This preserves the entire autocorrelation,
volatility clustering and turnover of the overlay and destroys only its alignment with the market.
200 shifts. Percentile of the real Sharpe inside that distribution is the test statistic.

PASS BAR (pre-declared, Bonferroni over 6 signals at one-sided 5% -> alpha 0.0083)
  Sweep: percentile >= 99.2 WITH positive Sharpe in-sample.
  Then the same signal must also exceed the 99.2nd percentile on the OOS slice alone.
  Anything less is logged FAIL. No exceptions, no "close enough".
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BROAD = ROOT / "data" / "broad"
OUT = ROOT / "research" / "artifacts" / "breadth_overlay.json"
N_SHIFT = 200
SECTORS = ["XLB", "XLC", "XLE", "XLF", "XLI", "XLK", "XLP", "XLRE", "XLU", "XLV", "XLY"]


def load(sym):
    p = BROAD / f"{sym}.csv"
    df = pd.read_csv(p)
    dcol = next(c for c in df.columns if c.lower() in ("date", "datetime", "dt"))
    ccol = next(c for c in df.columns if c.lower() in ("close", "adj close", "price"))
    df[dcol] = pd.to_datetime(df[dcol])
    return df.set_index(dcol)[ccol].astype(float).sort_index()


def series(d, sym):
    return d[sym] if sym in d else None


def sharpe(r, ann=252):
    r = r.dropna()
    if len(r) < 60 or r.std() == 0:
        return np.nan
    return float(r.mean() / r.std() * np.sqrt(ann))


def stats(ret, w, cost_bp=2.0):
    """ret: daily asset returns, w: weight applied to that day (already lagged)."""
    df = pd.DataFrame({"r": ret, "w": w}).dropna()
    if len(df) < 250:
        return None
    dw = df["w"].diff().abs().fillna(0.0)
    net = df["w"] * df["r"] - dw * cost_bp / 1e4
    eq = (1 + net).cumprod()
    yr = len(net) / 252
    cagr = float(eq.iloc[-1] ** (1 / yr) - 1) if eq.iloc[-1] > 0 else np.nan
    dd = float((eq / eq.cummax() - 1).min())
    return {"sharpe": sharpe(net), "cagr": cagr, "maxdd": dd,
            "vol": float(net.std() * np.sqrt(252)), "n": int(len(net))}


def main():
    syms = SECTORS + ["SPY", "HYG", "IEF", "VIX_PLACEHOLDER"]
    d = {}
    for s in SECTORS + ["SPY", "HYG", "IEF"]:
        try:
            d[s] = load(s)
        except Exception as e:  # noqa: BLE001
            print(f"  ! missing {s}: {e}")
    vix = pd.read_csv(ROOT / "data" / "collect" / "vix.csv")
    dc = next(c for c in vix.columns if c.lower() in ("date", "observation_date"))
    cc = next(c for c in vix.columns if "vix" in c.lower() or c.lower() == "close")
    vix[dc] = pd.to_datetime(vix[dc])
    vixs = vix.set_index(dc)[cc].astype(float).sort_index()

    px = pd.DataFrame({s: d[s] for s in d})
    px = px.dropna(how="all")
    ret = px.pct_change()
    spy = ret["SPY"]

    sec = pd.DataFrame({s: d[s] for s in SECTORS if s in d})
    ma200 = sec.rolling(200).mean()
    ma50 = sec.rolling(50).mean()

    sig = pd.DataFrame(index=px.index)
    sig["BREADTH200"] = (sec > ma200).where(ma200.notna()).mean(axis=1)
    sig["BREADTH50"] = (sec > ma50).where(ma50.notna()).mean(axis=1)
    sig["VIXLVL"] = vixs.reindex(px.index).ffill()
    sig["CREDIT"] = (px["HYG"] / px["IEF"]).rolling(60).mean()
    cr = (px["HYG"] / px["IEF"])
    sig["CREDIT"] = (cr > cr.rolling(60).mean()).astype(float)
    disp = sec.pct_change(20).std(axis=1)
    sig["DISP"] = (disp < disp.rolling(252).median()).astype(float).where(disp.rolling(252).median().notna())

    # GEX from the collected CSVs
    gex_w = None
    try:
        g = pd.read_csv(ROOT / "data" / "alt" / "dix_gex.csv")
        gd = next(c for c in g.columns if c.lower() == "date")
        g["date"] = pd.to_datetime(g[gd])
        gc = next(c for c in g.columns if c.lower() == "gex")
        gex = g.set_index("date")[gc].astype(float).sort_index()
        gex_w = (gex > 0).astype(float).reindex(px.index).ffill()
        sig["GEXSIGN"] = gex_w
    except Exception as e:  # noqa: BLE001
        print(f"  ! GEX unavailable: {e}")

    W = pd.DataFrame(index=px.index)
    W["BREADTH200"] = (0.5 + 1.0 * (sig["BREADTH200"] - 0.5)).clip(0, 2)
    W["BREADTH50"] = (0.5 + 1.0 * (sig["BREADTH50"] - 0.5)).clip(0, 2)
    W["VIXLVL"] = np.where(sig["VIXLVL"] < sig["VIXLVL"].rolling(60).median(), 1.5, 0.5)
    W["CREDIT"] = np.where(sig["CREDIT"] > 0.5, 1.5, 0.5)
    W["VIXLVL"] = W["VIXLVL"].where(sig["VIXLVL"].rolling(60).median().notna())
    W["CREDIT"] = W["CREDIT"].where(sig["CREDIT"].notna())
    W["DISP"] = np.where(sig["DISP"] > 0.5, 1.5, 0.5)
    W["DISP"] = W["DISP"].where(sig["DISP"].notna())
    if gex_w is not None:
        W["GEXSIGN"] = np.where(gex_w > 0.5, 1.5, 0.5)
        W["GEXSIGN"] = W["GEXSIGN"].where(gex_w.notna())
    avail = [c for c in W.columns if W[c].notna().sum() > 500]
    W = W[avail]
    # mean-normalise each overlay to 1 over its own live sample
    for c in W.columns:
        m = W[c].mean()
        if m and m > 0:
            W[c] = (W[c] / m).clip(0, 2.5)
    W["BEST"] = W.mean(axis=1)

    # apply with a one-day lag (w known at close t-1 -> applied to return t)
    Wl = W.shift(1)

    n = len(spy)
    is_end = int(n * 0.70)
    idx_is = spy.index[:is_end]
    idx_oos = spy.index[is_end:]

    def run(w_col, use_idx=None):
        w = Wl[w_col]
        r = spy
        if use_idx is not None:
            w = w.reindex(use_idx)
            r = r.reindex(use_idx)
        return stats(r, w), (r, w)

    def null_pct(r, w, base_sharpe, rng):
        """circular shifts of the weight series; returns percentile of base_sharpe."""
        v = w.values.astype(float)
        rv = r.values.astype(float)
        mask = ~np.isnan(v) & ~np.isnan(rv)
        if mask.sum() < 250:
            return np.nan, np.nan, np.nan
        v = v.copy()
        # fill gaps by ffill then bfill so shifts stay meaningful
        s = pd.Series(v).ffill().bfill().values
        shs = []
        for _ in range(N_SHIFT):
            k = rng.integers(1, len(s))
            ws = np.roll(s, k)
            st = stats(pd.Series(rv), pd.Series(ws))
            if st and not np.isnan(st["sharpe"]):
                shs.append(st["sharpe"])
        shs = np.array(shs)
        pct = float((shs < base_sharpe).mean() * 100)
        return pct, float(np.percentile(shs, 95)), float(np.percentile(shs, 99.17))

    rng = np.random.default_rng(20261120)
    results = {}
    print("\n  signal        IS Sharpe  IS pct  OOS Sharpe  OOS pct   null p99.2 (IS)   verdict")
    for c in W.columns:
        st_is, (r_is, w_is) = run(c, idx_is)
        if st_is is None:
            continue
        pct_is, p95_is, p99_is = null_pct(r_is, w_is, st_is["sharpe"], rng)
        st_oos, (r_oos, w_oos) = run(c, idx_oos)
        pct_oos, p95_oos, p99_oos = null_pct(r_oos, w_oos, st_oos["sharpe"], rng) if st_oos else (np.nan,) * 3
        ok = (pct_is >= 99.17) and (st_is["sharpe"] > 0) and (pct_oos >= 99.17)
        results[c] = {"is": st_is, "is_pct": pct_is, "is_null_p95": p95_is, "is_null_p99": p99_is,
                      "oos": st_oos, "oos_pct": pct_oos, "oos_null_p99": p99_oos,
                      "verdict": "PASS" if ok else "FAIL"}
        print(f"  {c:<13} {st_is['sharpe']:>9.3f} {pct_is:>6.1f} {st_oos['sharpe'] if st_oos else float('nan'):>11.3f} "
              f"{pct_oos:>8.1f} {p99_is:>17.3f}   {'PASS' if ok else 'FAIL'}")

    bench_is = stats(spy.reindex(idx_is), pd.Series(1.0, index=idx_is))
    bench_oos = stats(spy.reindex(idx_oos), pd.Series(1.0, index=idx_oos))
    print(f"\n  buy&hold SPY  IS Sharpe {bench_is['sharpe']:.3f}  OOS Sharpe {bench_oos['sharpe']:.3f}")
    print(f"  (a pass needs the OVERLAY's net Sharpe to be unusually high vs its own shifted copies,")
    print(f"   not merely to beat buy&hold — beating buy&hold is not evidence of timing skill.)")

    payload = {"experiment": "EXP-0013", "hypothesis": "H16",
               "design": __doc__.split("PRE-REGISTERED DESIGN")[1][:2600],
               "n_shift": N_SHIFT, "bar_percentile": 99.17,
               "buy_hold": {"is": bench_is, "oos": bench_oos},
               "signals": results,
               "any_pass": any(v["verdict"] == "PASS" for v in results.values())}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, default=str))
    print(f"\n  -> {OUT}")
    print(f"  VERDICT: {'PASS (review)' if payload['any_pass'] else 'FAIL — overlay timing adds nothing'}")


if __name__ == "__main__":
    main()
