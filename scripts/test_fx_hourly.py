#!/usr/bin/env python3
"""
EXP-0017 — Hour-scale FX with REAL bid/ask and one-bar execution latency. Does anything survive?

This is the test the intraday question has always deserved. Everything before it either assumed a cost
or used a single contract. Now the data has both sides of the quote for 6 pairs over 23 years
(scripts/backfill_duka_h1.py: ~145k hourly bars each, 2003 -> 2026, median quoted spreads EURUSD 0.50,
GBPUSD 1.10, USDJPY 0.70, EURGBP 1.00, EURCHF 1.50, XAUUSD 39.4 pips).

PRE-REGISTERED DESIGN (written before the result)
-------------------------------------------------
Universe  : EURUSD, GBPUSD, USDJPY, EURGBP, EURCHF, XAUUSD. Bars with zero volume (weekend flat) are
            dropped. Returns are computed on the BID close (a long is bought at the ask and sold at the
            bid; the cost accounting below charges the spread explicitly instead of trying to model both
            books).
Signals   : S1 REV1     pos = -sign(r_t)                                  (1-hour reversal)
            S2 REV6     pos = -sign(mean r over t-5..t)                   (6-hour reversal)
            S3 MOM12    pos = +sign(mean r over t-11..t)                  (12-hour momentum)
            S4 BREAK    long above the 00-07 UTC range high, short below its low, flat inside,
                        active only during 07-15 UTC (London session breakout)
            S5 HOURSEAS pos = sign of the hour-of-day mean return, estimated only from data strictly
                        before the current day (expanding, minimum 250 days)
Execution : decision at bar close t, position applies to bar t+1 -> exactly one bar of latency (~60
            minutes), which is what a REST-snapshot / retail-MT5 setup can honour.
Costs     : one side of the quoted spread per unit of |Δposition|, using THAT BAR's measured spread
            (not an average): cost_t = 0.5 * spread_pips_t * pip_size / price_{t-1} on |Δpos|.
            Quoted Dukascopy spreads are a FLOOR for a retail account — commission and slippage are not
            included, so any result here is optimistic.
Split     : first 70% of hours = in-sample, last 30% = out-of-sample (per pair, same dates).
Portfolio : equal-weight average of the 6 pairs' net return series, per signal.
Null      : circular shifts of the position series (200), which keeps turnover, sign balance and
            autocorrelation and destroys only the timing. Bar = 99th percentile (Bonferroni over the 5
            signals on the pooled portfolio). Per-pair numbers are reported descriptively, not tested.

PASS BAR: pooled net Sharpe must be > 0 and above the 99th percentile of its shift null in BOTH halves.
A signal may pass per-pair and still fail pooled — pooled is the bar, because that is what a real book is.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
INTRA = ROOT / "data" / "intraday"
OUT = ROOT / "research" / "artifacts" / "fx_hourly.json"
PAIRS = ["EURUSD", "GBPUSD", "USDJPY", "EURGBP", "EURCHF", "XAUUSD"]
N_SHIFT = 200
BAR_PCT = 99.0


def pip_size(sym):
    return 0.01 if (sym.endswith("JPY") or sym == "XAUUSD") else 0.0001


def load(sym):
    df = pd.read_csv(INTRA / f"{sym}_H1_bidask.csv", parse_dates=["ts_utc"])
    df = df.sort_values("ts_utc").reset_index(drop=True)
    df = df[df["bid_c"] > 0].copy()
    df["r"] = df["bid_c"].pct_change()
    return df.dropna(subset=["r"]).reset_index(drop=True)


def signals(df):
    r = df["r"].values
    c = df["bid_c"].values
    ts = df["ts_utc"]
    s = {}
    s["REV1"] = -np.sign(r)
    s["REV6"] = -np.sign(pd.Series(r).rolling(6).mean().fillna(0).values)
    s["MOM12"] = np.sign(pd.Series(r).rolling(12).mean().fillna(0).values)

    d = pd.DataFrame({"ts": ts, "c": c})
    d["date"] = d["ts"].dt.date
    d["hour"] = d["ts"].dt.hour
    asia = d[(d["hour"] < 7)].groupby("date")["c"].agg(["max", "min"]).rename(
        columns={"max": "asia_hi", "min": "asia_lo"})
    d = d.merge(asia, left_on="date", right_index=True, how="left")
    active = (d["hour"] >= 7) & (d["hour"] <= 15)
    s["BREAK"] = np.where(active & (d["c"] > d["asia_hi"]), 1.0,
                          np.where(active & (d["c"] < d["asia_lo"]), -1.0, 0.0))

    # hour-of-day seasonality, expanding and strictly lagged by one day
    dd = d.copy()
    dd["ret"] = r
    dd["date"] = pd.to_datetime(dd["date"])
    hour_mean = (dd.groupby(["date", "hour"])["ret"].mean().reset_index()
                 .sort_values("date")
                 .assign(exp=lambda x: x.groupby("hour")["ret"]
                         .transform(lambda v: v.shift(1).expanding(min_periods=250).mean())))
    hm = hour_mean.set_index(["date", "hour"])["exp"]
    dd["hm"] = dd.set_index(["date", "hour"]).index.map(hm)
    s["HOURSEAS"] = np.sign(dd["hm"].fillna(0).values)
    for k in s:
        s[k] = np.nan_to_num(s[k], nan=0.0)
    return s, dd


def run(df, pos, label):
    """pos is decided at bar t-1 and applied to bar t; cost charged on |Δpos| at that bar's spread."""
    p = pd.Series(pos).shift(1).fillna(0.0).values
    spread_cost = 0.5 * df["spread_close_pips"].values * pip_size(label) / df["bid_c"].shift(1).bfill().values
    dp = np.abs(np.diff(np.concatenate([[0.0], p])))
    net = p * df["r"].values - dp * spread_cost
    return pd.Series(net, index=df["ts_utc"]), pd.Series(p, index=df["ts_utc"])


def sharpe(x):
    x = pd.Series(x).dropna()
    return float(x.mean() / x.std() * np.sqrt(252 * 24)) if len(x) > 500 and x.std() > 0 else np.nan


def main():
    per_pair = {}
    pooled = {}
    for sym in PAIRS:
        df = load(sym)
        sig, dd = signals(df)
        per_pair[sym] = {}
        for name, pos in sig.items():
            net, p = run(df, pos, sym)
            per_pair[sym][name] = net
            pooled.setdefault(name, []).append(net)
        print(f"  {sym:<7} {len(df):>7} bars  {df['ts_utc'].iloc[0].date()} .. {df['ts_utc'].iloc[-1].date()}"
              f"  trades/h (REV1) {float((np.abs(np.diff(per_pair[sym]['REV1'].values))>0).mean()):.3f}")
        if sym == PAIRS[0]:
            first_index = df["ts_utc"]

    results = {}
    print("\n  signal    IS Sharpe  IS pct   OOS Sharpe  OOS pct    null p99 IS   verdict")
    for name, series_list in pooled.items():
        port = pd.concat([s.rename(i) for i, s in enumerate(series_list)], axis=1).mean(axis=1)
        port = port.sort_index()
        n = len(port)
        cut = int(n * 0.70)
        is_s, oos_s = port.iloc[:cut], port.iloc[cut:]
        sh_is, sh_oos = sharpe(is_s), sharpe(oos_s)

        def shift_pct(s, base):
            v = s.values.astype(float)
            rng = np.random.default_rng(5)
            shs = []
            for _ in range(N_SHIFT):
                shs.append(sharpe(np.roll(v, rng.integers(1, len(v)))))
            shs = np.array(shs)
            return float((shs < base).mean() * 100), float(np.percentile(shs, BAR_PCT))

        p_is, q_is = shift_pct(is_s, sh_is)
        p_oos, q_oos = shift_pct(oos_s, sh_oos)
        ok = (sh_is > 0 and sh_oos > 0 and p_is >= BAR_PCT and p_oos >= BAR_PCT)
        results[name] = {"is": {"sharpe": sh_is, "mean_bp": float(is_s.mean() * 1e4)},
                         "oos": {"sharpe": sh_oos, "mean_bp": float(oos_s.mean() * 1e4)},
                         "is_pct": p_is, "oos_pct": p_oos, "null_p99_is": q_is, "null_p99_oos": q_oos,
                         "per_pair_is": {s: round(sharpe(per_pair[s][name].iloc[:int(len(per_pair[s][name]) * 0.7)]), 3)
                                         for s in PAIRS},
                         "verdict": "PASS" if ok else "FAIL"}
        print(f"  {name:<9} {sh_is:>9.3f} {p_is:>7.1f} {sh_oos:>11.3f} {p_oos:>8.1f} {q_is:>13.3f}"
              f"   {'PASS' if ok else 'FAIL'}")

    # gross vs net for the best signal, so the cost wall is explicit
    print("\n  cost check (REV1, EURUSD): gross mean return per hour vs net after measured spread")
    sym = "EURUSD"
    df = load(sym)
    sig, _ = signals(df)
    net, p = run(df, sig["REV1"], sym)
    gross = pd.Series(p.values * df["r"].values, index=df["ts_utc"])
    print(f"    gross {gross.mean()*1e4:+.3f} bp/h  net {net.mean()*1e4:+.3f} bp/h  "
          f"cost drag {(gross.mean()-net.mean())*1e4:.3f} bp/h")

    any_pass = any(v["verdict"] == "PASS" for v in results.values())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"experiment": "EXP-0017", "hypothesis": "H20",
                               "design": __doc__.split("PRE-REGISTERED DESIGN")[1][:2600],
                               "bar_percentile": BAR_PCT, "results": results,
                               "any_pass": any_pass}, indent=2, default=str))
    print(f"\n  VERDICT: {'PASS (review)' if any_pass else 'FAIL — nothing survives real spreads + 1-bar latency'}")
    print(f"  -> {OUT}")


if __name__ == "__main__":
    main()
