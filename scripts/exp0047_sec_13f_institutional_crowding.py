#!/usr/bin/env python3
"""
EXP-0047 — SEC Form 13F Institutional Breadth, Crowding & Put/Call on 385-Firm Survivorship-Free US Panel (2017-2026)
Tests whether causal SEC Form 13F institutional metrics (available_from = max(FILING_DATE)+1 <= t)
generate out-of-sample alpha across active (317) + delisted (68) firms.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "research" / "artifacts" / "exp0047_sec_13f_institutional_crowding.json"


def perf_ex(tot: np.ndarray, rf: np.ndarray) -> dict:
    tot = tot[np.isfinite(tot)]
    rf = rf[: len(tot)]
    if len(tot) < 60:
        return {"sharpe": 0.0, "cagr_pct": 0.0, "maxdd_pct": 0.0}
    ex = tot - rf
    sd = float(np.std(ex, ddof=1))
    shp = float(np.mean(ex) / sd * math.sqrt(252.0)) if sd > 0 else 0.0
    eq = np.cumprod(1.0 + tot)
    cagr = (float(eq[-1]) ** (252.0 / len(tot)) - 1.0) * 100.0 if eq[-1] > 0 else -100.0
    mdd = float(np.min(eq / np.maximum.accumulate(eq) - 1.0)) * 100.0
    return {"sharpe": round(shp, 3), "cagr_pct": round(cagr, 2), "maxdd_pct": round(mdd, 2)}


def main() -> None:
    rng = np.random.default_rng(42)
    f13 = pd.read_csv(ROOT / "data" / "sec" / "sec_13f_quarterly_holdings.csv.gz")
    f13["period_end"] = pd.to_datetime(f13["period_end"])
    f13["available_from"] = pd.to_datetime(f13["available_from"])
    f13 = f13.sort_values(["ticker", "period_end"])

    # Compute strictly causal per-(ticker, quarter) signals BEFORE mapping to daily calendar
    g = f13.groupby("ticker", group_keys=False)
    f13["prev_filers"] = g["n_filers"].shift(1)
    f13["filers_4q"] = g["n_filers"].shift(4)
    f13["breadth_1q"] = (f13["n_filers"] - f13["prev_filers"]) / f13["prev_filers"].clip(lower=10.0)
    f13["breadth_4q"] = (f13["n_filers"] - f13["filers_4q"]) / f13["filers_4q"].clip(lower=10.0)
    f13["anti_hhi"] = -f13["hhi"]
    f13["low_put_call_filers"] = -(np.log1p(f13["n_put_filers"]) - np.log1p(f13["n_call_filers"]))
    f13["low_put_call_shares"] = -(np.log1p(f13["put_shares"]) - np.log1p(f13["call_shares"]))

    # Load all active (prices_pit) + delisted (stocks_delisted_tiingo) adjclose & close & volume
    series_map: dict[str, pd.Series] = {}
    raw_close_map: dict[str, pd.Series] = {}
    vol_map: dict[str, pd.Series] = {}
    for folder in (ROOT / "data" / "sec" / "prices_pit", ROOT / "data" / "stocks_delisted_tiingo"):
        for fp in sorted(folder.glob("*.csv")):
            tk = fp.stem
            if tk in series_map:
                continue
            df = pd.read_csv(fp, usecols=["date", "close", "volume", "adjclose"])
            df["date"] = pd.to_datetime(df["date"])
            df = df.drop_duplicates("date").set_index("date").sort_index()
            df = df[df.index >= pd.Timestamp("2016-11-21")]
            s = pd.to_numeric(df["adjclose"], errors="coerce").dropna()
            rc = pd.to_numeric(df["close"], errors="coerce").reindex(s.index)
            vl = pd.to_numeric(df["volume"], errors="coerce").reindex(s.index).fillna(0.0)
            if len(s) >= 60:
                series_map[tk] = s
                raw_close_map[tk] = rc
                vol_map[tk] = vl

    # Restrict to tickers present in 13F
    f13_tickers = set(f13["ticker"].unique())
    tickers = sorted(set(series_map.keys()) & f13_tickers)
    px = pd.DataFrame({t: series_map[t] for t in tickers}).sort_index()
    rc_df = pd.DataFrame({t: raw_close_map[t] for t in tickers}).reindex(px.index)
    vl_df = pd.DataFrame({t: vol_map[t] for t in tickers}).reindex(px.index).fillna(0.0)
    # Keep returns strictly inside each ticker's live window; drop corporate-action/OTC quote glitches (>300% daily spike)
    ret = px.pct_change(fill_method=None)
    ret = ret.where(ret <= 3.0, 0.0)

    bil = pd.read_csv(ROOT / "data" / "etfs_tiingo" / "BIL.csv")
    bil["date"] = pd.to_datetime(bil["date"])
    bil = bil.drop_duplicates("date").set_index("date").sort_index()["adjclose"]
    rb = bil.pct_change().reindex(px.index).fillna(0.0).to_numpy()

    idx = px.index
    # Investable institutional mask on rebalance date: close >= $5.00 AND volume >= 25,000
    valid_px = px.notna()
    investable = valid_px & (rc_df >= 5.0) & (vl_df >= 25_000.0)

    # Map causal 13F snapshots onto trading dates (available_from <= t and stale <= 160d)
    sig_names = ["breadth_1q", "breadth_4q", "anti_hhi", "low_put_call_filers", "low_put_call_shares"]
    f13_by_tk = {tk: sub.sort_values("available_from").reset_index(drop=True) for tk, sub in f13[f13["ticker"].isin(tickers)].groupby("ticker")}

    # Monthly rebalance (21td starting 2017-03-01 so >=3 months of price history & 13F available)
    start_pos = int(np.searchsorted(idx, pd.Timestamp("2017-03-01")))
    reb = list(range(start_pos, len(idx) - 1, 21))
    eval_sl = slice(start_pos + 1, len(idx))
    idx_e = idx[eval_sl]
    rb_e = rb[eval_sl]
    rm_e = ret.iloc[eval_sl].fillna(0.0).to_numpy()
    valid_e = valid_px.iloc[eval_sl].to_numpy()
    is_m = idx_e < pd.Timestamp("2022-01-01")
    oos_m = idx_e >= pd.Timestamp("2022-01-01")

    # Equal-weight benchmark across investable stocks (monthly rebalanced, keeps holding through collapse if delisted mid-month!)
    w_ew = np.zeros((len(idx_e), len(tickers)), dtype=float)
    for k, ri in enumerate(reb):
        inv_cols = np.where(investable.iloc[ri].to_numpy())[0]
        if len(inv_cols) == 0:
            continue
        i0 = (ri + 1) - (start_pos + 1)
        i1 = (reb[k + 1] + 1 - (start_pos + 1)) if k + 1 < len(reb) else len(idx_e)
        w_ew[i0:i1, inv_cols] = 1.0 / len(inv_cols)
    w_ew = np.where(valid_e, w_ew, 0.0)
    to_ew = np.sum(np.abs(np.diff(w_ew, axis=0, prepend=0.0)), axis=1)
    tot_ew = np.sum(w_ew * rm_e, axis=1) - to_ew * 5e-4

    results = {
        "EqualWeight_Universe": {
            "is_17_21": perf_ex(tot_ew[is_m], rb_e[is_m]),
            "oos_22_26": perf_ex(tot_ew[oos_m], rb_e[oos_m]),
            "all": perf_ex(tot_ew, rb_e),
            "perm200_oos_pct": None,
        }
    }

    tk_idx = {t: i for i, t in enumerate(tickers)}
    idx_ns = idx.asi8

    for sig in sig_names:
        # Build causal score matrix on rebalance dates
        w_ls = np.zeros((len(idx_e), len(tickers)), dtype=float)
        w_lo = np.zeros((len(idx_e), len(tickers)), dtype=float)

        for k, ri in enumerate(reb):
            dt = idx[ri]
            dt_ns = idx_ns[ri]
            scores = []
            for tk in tickers:
                j = tk_idx[tk]
                if not investable.iloc[ri, j]:
                    continue
                sub = f13_by_tk.get(tk)
                if sub is None:
                    continue
                av = sub["available_from"].to_numpy().astype("int64")
                pos = int(np.searchsorted(av, dt_ns, side="right")) - 1
                if pos < 0:
                    continue
                row = sub.iloc[pos]
                if (dt - row["available_from"]).days > 160 or row["n_filers"] < 15:
                    continue
                val = float(row[sig])
                if np.isfinite(val):
                    scores.append((j, val))
            if len(scores) < 50:
                continue
            scores.sort(key=lambda x: x[1])
            q = max(10, len(scores) // 5)
            bot = [j for j, _ in scores[:q]]
            top = [j for j, _ in scores[-q:]]
            top25 = [j for j, _ in scores[-25:]]

            i0 = (ri + 1) - (start_pos + 1)
            i1 = (reb[k + 1] + 1 - (start_pos + 1)) if k + 1 < len(reb) else len(idx_e)
            w_ls[i0:i1, top] = 0.5 / len(top)
            w_ls[i0:i1, bot] = -0.5 / len(bot)
            w_lo[i0:i1, top25] = 1.0 / len(top25)

        for mode, wm, is_ls, cbps in [
            (f"13F_{sig}_Q5Q1_LS", w_ls, True, 10.0),
            (f"13F_{sig}_Top25_LO", w_lo, False, 5.0),
        ]:
            # Mask out dead delisted positions cleanly
            w_live = np.where(valid_e, wm, 0.0)
            to = np.sum(np.abs(np.diff(w_live, axis=0, prepend=0.0)), axis=1)
            rf_cmp = np.zeros(len(w_live)) if is_ls else rb_e
            tot = np.sum(w_live * rm_e, axis=1) - to * (cbps / 10000.0)
            m_oos = perf_ex(tot[oos_m], rf_cmp[oos_m])
            # 200 Ticker-permutation null in OOS
            null = []
            wo, ro, rfo = w_live[oos_m], rm_e[oos_m], rf_cmp[oos_m]
            for _ in range(200):
                perm = rng.permutation(len(tickers))
                wp = wo[:, perm]
                top_n = np.sum(np.abs(np.diff(wp, axis=0, prepend=0.0)), axis=1)
                null.append(perf_ex(np.sum(wp * ro, axis=1) - top_n * (cbps / 10000.0), rfo)["sharpe"])
            results[mode] = {
                "is_17_21": perf_ex(tot[is_m], rf_cmp[is_m]),
                "oos_22_26": m_oos,
                "all": perf_ex(tot, rf_cmp),
                "perm200_oos_pct": round(float(np.mean(np.array(null) <= m_oos["sharpe"]) * 100.0), 1),
            }

    out = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "EXP-0047",
        "universe_matched_with_13f": len(tickers),
        "sample": f"{idx_e[0].strftime('%Y-%m-%d')}..{idx_e[-1].strftime('%Y-%m-%d')}",
        "strategies": results,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, indent=2))

    print(f"=== EXP-0047 SEC FORM 13F ON {len(tickers)}-FIRM SURVIVORSHIP-FREE UNIVERSE ({out['sample']}) ===")
    for k, v in results.items():
        print(f"  {k:34s}: IS={v['is_17_21']['sharpe']:+.3f} | OOS22-26={v['oos_22_26']['sharpe']:+.3f}(p={v['perm200_oos_pct']}%) | All={v['all']['sharpe']:+.3f}(CAGR={v['all']['cagr_pct']:+.1f}%,DD={v['all']['maxdd_pct']:+.1f}%)")


if __name__ == "__main__":
    main()
