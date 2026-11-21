#!/usr/bin/env python3
"""
EXP-0048 — Untested Local Alt-Data Sweep: Wikipedia Daily Attention + CBOE SKEW + S&P 500 Inclusion Drift
1) Wikipedia Daily Pageviews (2016-2026) across 8 macro/crypto assets: attention spike contrarian vs FOMO momentum.
2) CBOE SKEW Index (1990-2026, 33y SPY overlap): tail-skew extremes as SPY risk timing.
3) S&P 500 Index Addition / Removal Event Study (sp500_changes_since_2019.csv) vs SPY excess return at 5d, 21d, 63d.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "research" / "artifacts" / "exp0048_wikipedia_attention_skew_and_sp500_events.json"


def perf_ex(tot: np.ndarray, rf: np.ndarray, scale: float = 252.0) -> dict:
    tot = tot[np.isfinite(tot)]
    rf = rf[: len(tot)]
    if len(tot) < 60:
        return {"sharpe": 0.0, "cagr_pct": 0.0, "maxdd_pct": 0.0}
    ex = tot - rf
    sd = float(np.std(ex, ddof=1))
    shp = float(np.mean(ex) / sd * math.sqrt(scale)) if sd > 0 else 0.0
    eq = np.cumprod(1.0 + tot)
    cagr = (float(eq[-1]) ** (scale / len(tot)) - 1.0) * 100.0 if eq[-1] > 0 else -100.0
    mdd = float(np.min(eq / np.maximum.accumulate(eq) - 1.0)) * 100.0
    return {"sharpe": round(shp, 3), "cagr_pct": round(cagr, 2), "maxdd_pct": round(mdd, 2)}


def main() -> None:
    # 1. Wikipedia Attention across 8 assets (lag +2d to guarantee UTC day close causality!)
    att_map = {
        "BTCUSD": (ROOT / "data" / "universe" / "BTC.csv", "close", 365.0),
        "ETHUSD": (ROOT / "data" / "universe" / "ETH.csv", "close", 365.0),
        "SP500": (ROOT / "data" / "etfs_tiingo" / "SPY.csv", "adjclose", 252.0),
        "XAUUSD": (ROOT / "data" / "broad" / "GLD.csv", "adjclose", 252.0),
        "WTI": (ROOT / "data" / "broad" / "USO.csv", "adjclose", 252.0),
        "COPPER": (ROOT / "data" / "broad" / "CPER.csv", "adjclose", 252.0),
    }
    cb = pd.read_csv(ROOT / "data" / "macro" / "central_bank_rates_daily.csv")
    cb["date"] = pd.to_datetime(cb["date"])
    cb = cb.drop_duplicates("date").set_index("date").sort_index()
    effr = cb["effr"].fillna(0.0) / 100.0

    wiki_res = {}
    for sym, (px_p, col, scale) in att_map.items():
        ap = ROOT / "data" / "events" / "attention" / f"{sym}.csv"
        if not ap.exists() or not px_p.exists():
            continue
        att = pd.read_csv(ap)
        att["date"] = pd.to_datetime(att["date"])
        att = att.drop_duplicates("date").set_index("date").sort_index()["views"].astype(float)
        att_z = (np.log1p(att) - np.log1p(att).rolling(90).mean()) / np.log1p(att).rolling(90).std()

        px_df = pd.read_csv(px_p)
        px_df["date"] = pd.to_datetime(px_df["date"])
        px_s = pd.to_numeric(px_df.drop_duplicates("date").set_index("date")[col], errors="coerce").dropna().sort_index()
        idx = px_s.index.intersection(att_z.dropna().index)
        if len(idx) < 500:
            continue
        r = px_s.pct_change().reindex(idx).fillna(0.0)
        rf = (effr.reindex(idx).ffill().fillna(0.0) / scale)
        az = att_z.reindex(idx).ffill().shift(2)  # strict +2d lag
        fwd7 = px_s.pct_change(7).reindex(idx).shift(-7)
        ic7 = float(az.corr(fwd7, method="spearman"))

        # Contrarian (cash when attention > +2 z) vs FOMO (only long when attention > 0 z)
        w_cnt = (az < 2.0).astype(float).fillna(1.0).to_numpy()
        w_fomo = (az > 0.5).astype(float).fillna(0.0).to_numpy()
        is_m = idx < pd.Timestamp("2022-01-01")
        oos_m = idx >= pd.Timestamp("2022-01-01")
        ra, rfa = r.to_numpy(), rf.to_numpy()
        def ev(w):
            to = np.abs(np.diff(w, prepend=0.0))
            tot = w * ra + (1.0 - w) * rfa - to * 10e-4
            return {"is": perf_ex(tot[is_m], rfa[is_m], scale)["sharpe"], "oos": perf_ex(tot[oos_m], rfa[oos_m], scale)["sharpe"], "all": perf_ex(tot, rfa, scale)["sharpe"]}
        wiki_res[sym] = {"spearman_ic7d": round(ic7, 4), "BuyHold": ev(np.ones(len(idx))), "Contrarian_Cash_if_zgt2": ev(w_cnt), "FOMO_Long_if_zgt05": ev(w_fomo)}

    # 2. CBOE SKEW Index (1993-2026 SPY overlap!)
    sk = pd.read_csv(ROOT / "data" / "options" / "SKEW.csv")
    sk["date"] = pd.to_datetime(sk["DATE"])
    sk = sk.drop_duplicates("date").set_index("date").sort_index()["SKEW"]
    spy = pd.read_csv(ROOT / "data" / "etfs_tiingo" / "SPY.csv")
    spy["date"] = pd.to_datetime(spy["date"])
    spy = spy.drop_duplicates("date").set_index("date").sort_index()["adjclose"]
    idx_sk = spy.index.intersection(sk.index)
    r_spy = spy.pct_change().reindex(idx_sk).fillna(0.0).to_numpy()
    rf_spy = (effr.reindex(idx_sk).ffill().fillna(0.0) / 252.0).to_numpy()
    sk_s = sk.reindex(idx_sk).ffill()
    sk_z = (sk_s - sk_s.rolling(252).mean()) / sk_s.rolling(252).std()
    is_sk, oos_sk = idx_sk < pd.Timestamp("2015-01-01"), idx_sk >= pd.Timestamp("2015-01-01")
    skew_res = {}
    for sn, w_s in [
        ("SPY_BuyHold_33y", pd.Series(1.0, index=idx_sk)),
        ("SPY_Cash_if_SKEW_zgt15", (sk_z < 1.5).astype(float).shift(1)),
        ("SPY_Cash_if_SKEW_gt145", (sk_s < 145.0).astype(float).shift(1)),
        ("SPY_Long_only_if_SKEW_zgt0", (sk_z > 0.0).astype(float).shift(1)),
    ]:
        w = w_s.fillna(0.0).to_numpy()
        to = np.abs(np.diff(w, prepend=0.0))
        tot = w * r_spy + (1.0 - w) * rf_spy - to * 5e-4
        skew_res[sn] = {"is_93_14": perf_ex(tot[is_sk], rf_spy[is_sk]), "oos_15_26": perf_ex(tot[oos_sk], rf_spy[oos_sk]), "all": perf_ex(tot, rf_spy)}

    # 3. S&P 500 Inclusion / Exclusion Post-Event Drift (2019-2026)
    chg = pd.read_csv(ROOT / "data" / "equities" / "sp500_changes_since_2019.csv")
    chg["date"] = pd.to_datetime(chg["date"])
    pit_dir = ROOT / "data" / "sec" / "prices_pit"
    del_dir = ROOT / "data" / "stocks_delisted_tiingo"
    px_cache = {}
    def get_px(tk):
        if tk in px_cache:
            return px_cache[tk]
        for d in (pit_dir, del_dir):
            fp = d / f"{tk}.csv"
            if fp.exists():
                df = pd.read_csv(fp, usecols=["date", "adjclose"])
                df["date"] = pd.to_datetime(df["date"])
                s = pd.to_numeric(df.drop_duplicates("date").set_index("date")["adjclose"], errors="coerce").dropna().sort_index()
                px_cache[tk] = s
                return s
        px_cache[tk] = None
        return None

    add_ex, rem_ex = {5: [], 21: [], 63: []}, {5: [], 21: [], 63: []}
    for row in chg.itertuples():
        ev_dt = row.date
        for grp, tk in [(add_ex, str(row.add)), (rem_ex, str(row.remove))]:
            if tk == "nan" or not tk:
                continue
            ps = get_px(tk)
            if ps is None:
                continue
            p0 = ps.index.searchsorted(ev_dt, side="right")  # t+1 after event date (strictly causal)
            s0 = spy.index.searchsorted(ev_dt, side="right")
            if p0 >= len(ps) or s0 >= len(spy):
                continue
            for h in (5, 21, 63):
                if p0 + h < len(ps) and s0 + h < len(spy):
                    rp = float(ps.iloc[p0 + h] / ps.iloc[p0] - 1.0)
                    rs = float(spy.iloc[s0 + h] / spy.iloc[s0] - 1.0)
                    grp[h].append(rp - rs)

    sp_ev = {
        "additions": {f"{h}d": {"n": len(v), "mean_ex_spy_pct": round(float(np.mean(v)*100), 3), "win_rate_pct": round(float(np.mean(np.array(v)>0)*100), 1), "t_stat": round(float(np.mean(v)/(np.std(v,ddof=1)/math.sqrt(len(v)))), 2)} for h, v in add_ex.items() if len(v) >= 5},
        "removals": {f"{h}d": {"n": len(v), "mean_ex_spy_pct": round(float(np.mean(v)*100), 3), "win_rate_pct": round(float(np.mean(np.array(v)>0)*100), 1), "t_stat": round(float(np.mean(v)/(np.std(v,ddof=1)/math.sqrt(len(v)))), 2)} for h, v in rem_ex.items() if len(v) >= 5},
    }

    out = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "EXP-0048",
        "wikipedia_attention": wiki_res,
        "cboe_skew_33y": skew_res,
        "sp500_addition_removal_drift": sp_ev,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, indent=2))

    print("=== EXP-0048 (1) WIKIPEDIA DAILY ATTENTION (2016-2026) ===")
    for k, v in wiki_res.items():
        print(f"  {k:8s} (IC7={v['spearman_ic7d']:+.4f}): BH={v['BuyHold']['all']:+.3f} | Cash_if_z>2 OOS={v['Contrarian_Cash_if_zgt2']['oos']:+.3f} All={v['Contrarian_Cash_if_zgt2']['all']:+.3f} | FOMO_z>0.5 OOS={v['FOMO_Long_if_zgt05']['oos']:+.3f}")
    print("\n=== EXP-0048 (2) CBOE SKEW INDEX 33-YEAR SPY TIMING ===")
    for k, v in skew_res.items():
        print(f"  {k:28s}: IS93-14={v['is_93_14']['sharpe']:+.3f} OOS15-26={v['oos_15_26']['sharpe']:+.3f} All={v['all']['sharpe']:+.3f}(DD={v['all']['maxdd_pct']:+.1f}%)")
    print("\n=== EXP-0048 (3) S&P 500 ADDITION/REMOVAL POST-EVENT DRIFT (t+1 vs SPY) ===")
    print(" ", sp_ev)


if __name__ == "__main__":
    main()
