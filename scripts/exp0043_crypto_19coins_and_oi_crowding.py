#!/usr/bin/env python3
"""
EXP-0043 — Crypto 19-Coin Survivorship-Free Trend & Cross-Section + 4.9y Binance OI/L-S Crowding (2018-2026)
Tests whether EXP-0041 (TrendEns / SMA50 + VT25) survives on a survivorship-resistant 19-coin panel
(including fallen 2018-2021 majors EOS, FIL, ALGO, ICP, LTC, BCH, ETC, XLM) AND whether
4.9 years of Binance Futures daily metrics (OI, Top-Trader L/S, Global L/S, Taker L/S) add alpha or filter value.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "research" / "artifacts" / "exp0043_crypto_19coins_and_oi_crowding.json"


def stats_arr(tot: np.ndarray, rf: np.ndarray, scale: float = 365.0) -> dict:
    tot = tot[np.isfinite(tot)]
    rf = rf[: len(tot)]
    if len(tot) < 60:
        return {"sharpe_ex": 0.0, "cagr_pct": 0.0, "maxdd_pct": 0.0, "calmar": 0.0}
    ex = tot - rf
    sd = float(np.std(ex, ddof=1))
    shp = float(np.mean(ex) / sd * math.sqrt(scale)) if sd > 0 else 0.0
    eq = np.cumprod(1.0 + tot)
    cagr = (float(eq[-1]) ** (scale / len(tot)) - 1.0) * 100.0 if eq[-1] > 0 else -100.0
    mdd = float(np.min(eq / np.maximum.accumulate(eq) - 1.0)) * 100.0
    return {
        "sharpe_ex": round(shp, 3),
        "cagr_pct": round(cagr, 2),
        "maxdd_pct": round(mdd, 2),
        "calmar": round(cagr / max(abs(mdd), 1e-3), 3),
    }


def main() -> None:
    rng = np.random.default_rng(42)
    df = pd.read_csv(ROOT / "data" / "crypto_vision" / "spot_daily_19coins.csv.gz")
    df["date"] = pd.to_datetime(df["date"])
    px = df.pivot(index="date", columns="symbol", values="close").sort_index()
    ret = px.pct_change().clip(lower=-0.95)  # valid daily spot returns

    cb = pd.read_csv(ROOT / "data" / "macro" / "central_bank_rates_daily.csv")
    cb["date"] = pd.to_datetime(cb["date"])
    cb = cb.drop_duplicates("date").set_index("date").sort_index()
    rf_d = (cb["effr"].reindex(px.index).ffill().fillna(0.0) / 100.0 / 365.0).fillna(0.0)

    # 1. Per-coin SMA50_VT25 vs Buy&Hold (strictly from coin's 120th trading day forward)
    per_coin = {}
    w_sma50_vt25 = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    w_ens_vt25 = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    w_bh = pd.DataFrame(0.0, index=px.index, columns=px.columns)
    eligible = pd.DataFrame(False, index=px.index, columns=px.columns)

    for sym in px.columns:
        c = px[sym].dropna()
        if len(c) < 365:
            continue
        r = c.pct_change().fillna(0.0)
        rf_c = rf_d.reindex(c.index).fillna(0.0)
        sma50 = (c > c.rolling(50).mean()).astype(float)
        ens = sum((c > c.rolling(lb).mean()).astype(float) for lb in (20, 40, 60, 90, 120)) / 5.0
        rv21 = (r.rolling(21).std() * math.sqrt(365.0)).clip(lower=0.15)
        vt = np.minimum(1.0, 0.25 / rv21)

        w50 = (sma50 * vt).shift(1).fillna(0.0)
        we = (ens * vt).shift(1).fillna(0.0)
        start_c = c.index[120]
        m = c.index >= start_c
        w50_m, we_m, r_m, rf_m = w50[m].to_numpy(), we[m].to_numpy(), r[m].to_numpy(), rf_c[m].to_numpy()
        to50 = np.abs(np.diff(w50_m, prepend=0.0))
        toe = np.abs(np.diff(we_m, prepend=0.0))
        tot50 = w50_m * r_m + (1.0 - w50_m) * rf_m - to50 * 10e-4
        tote = we_m * r_m + (1.0 - we_m) * rf_m - toe * 10e-4

        per_coin[sym] = {
            "start": start_c.strftime("%Y-%m-%d"),
            "days": int(m.sum()),
            "BuyHold": stats_arr(r_m, rf_m),
            "SMA50_VT25": stats_arr(tot50, rf_m),
            "TrendEns_VT25": stats_arr(tote, rf_m),
        }

        w_sma50_vt25.loc[c.index[m], sym] = w50[m]
        w_ens_vt25.loc[c.index[m], sym] = we[m]
        w_bh.loc[c.index[m], sym] = 1.0
        eligible.loc[c.index[m], sym] = True

    # 2. Dynamic Equal-Weight Portfolios (All 19 Coins & 17 Non-BTC/ETH Altcoins, 2018-06 .. 2026-10)
    m_port = px.index >= pd.Timestamp("2018-06-01")
    idx_p = px.index[m_port]
    rf_p = rf_d[m_port].to_numpy()
    r_mat = ret.reindex(idx_p).fillna(0.0)
    elig_m = eligible.reindex(idx_p)

    def eval_basket(cols_subset: list[str], label: str) -> dict:
        el = elig_m[cols_subset]
        n_active = el.sum(axis=1).replace(0, np.nan)
        rm = r_mat[cols_subset].to_numpy()
        out_b = {}
        for sname, wraw in [
            ("EqualWeight_BuyHold", w_bh.reindex(idx_p)[cols_subset]),
            ("EqualWeight_SMA50_VT25", w_sma50_vt25.reindex(idx_p)[cols_subset]),
            ("EqualWeight_TrendEns_VT25", w_ens_vt25.reindex(idx_p)[cols_subset]),
        ]:
            wn = wraw.div(n_active, axis=0).fillna(0.0).to_numpy()
            to = np.sum(np.abs(np.diff(wn, axis=0, prepend=0.0)), axis=1)
            wc = np.maximum(0.0, 1.0 - np.sum(wn, axis=1))
            tot10 = np.sum(wn * rm, axis=1) + wc * rf_p - to * 10e-4
            tot30 = np.sum(wn * rm, axis=1) + wc * rf_p - to * 30e-4
            m_is = idx_p < pd.Timestamp("2023-01-01")
            m_oos = idx_p >= pd.Timestamp("2023-01-01")
            # 300 circular shifts of portfolio weights vs BuyHold excess
            bh_ex = (np.sum((el.div(n_active, axis=0).fillna(0.0).to_numpy()) * rm, axis=1) - rf_p)
            sh_all = stats_arr(tot10, rf_p)["sharpe_ex"]
            p_sh = None
            if "BuyHold" not in sname:
                null = []
                for _ in range(300):
                    sh = int(rng.integers(30, len(wn) - 30))
                    ws = np.roll(wn, sh, axis=0)
                    tos = np.sum(np.abs(np.diff(ws, axis=0, prepend=0.0)), axis=1)
                    w_tot = np.sum(ws, axis=1)
                    exs = np.sum(ws * (rm - rf_p[:, None]), axis=1) - tos * 10e-4
                    sd = float(np.std(exs, ddof=1))
                    null.append(float(np.mean(exs) / sd * math.sqrt(365.0)) if sd > 0 else 0.0)
                p_sh = round(float(np.mean(np.array(null) <= sh_all) * 100.0), 2)
            out_b[sname] = {
                "all_10bp": stats_arr(tot10, rf_p),
                "all_30bp": stats_arr(tot30, rf_p),
                "is_18_22": stats_arr(tot10[m_is], rf_p[m_is]),
                "oos_23_26": stats_arr(tot10[m_oos], rf_p[m_oos]),
                "circ_shift300_all_pct": p_sh,
            }
        return out_b

    all_cols = list(per_coin.keys())
    alt_cols = [c for c in all_cols if c not in ("BTCUSDT", "ETHUSDT")]
    bask_19 = eval_basket(all_cols, "All_19_Coins")
    bask_17 = eval_basket(alt_cols, "17_Altcoins_Ex_BTC_ETH")

    # 3. Cross-Sectional Crypto Momentum (21d & 60d Top4 vs Bot4 across 19 coins, 7d rebalance)
    xs_res = {}
    for lb in (21, 60):
        mom = px.pct_change(lb)
        w_lo = pd.DataFrame(0.0, index=idx_p, columns=all_cols)
        w_ls = pd.DataFrame(0.0, index=idx_p, columns=all_cols)
        reb = list(range(lb + 1, len(idx_p) - 1, 7))
        for k, ri in enumerate(reb):
            dt = idx_p[ri]
            valid = mom.loc[dt, all_cols].where(elig_m.loc[dt, all_cols]).dropna()
            if len(valid) < 8:
                continue
            top4 = valid.nlargest(4).index
            bot4 = valid.nsmallest(4).index
            i0 = ri + 1
            i1 = reb[k + 1] + 1 if k + 1 < len(reb) else len(idx_p)
            w_lo.iloc[i0:i1, [all_cols.index(c) for c in top4]] = 0.25
            w_ls.iloc[i0:i1, [all_cols.index(c) for c in top4]] = 0.125
            w_ls.iloc[i0:i1, [all_cols.index(c) for c in bot4]] = -0.125
        for tag, wm, is_ls in [(f"XS_Mom{lb}_Top4_LO", w_lo, False), (f"XS_Mom{lb}_Top4Bot4_LS", w_ls, True)]:
            wa = wm.to_numpy()
            to = np.sum(np.abs(np.diff(wa, axis=0, prepend=0.0)), axis=1)
            rm = r_mat[all_cols].to_numpy()
            cash_w = np.zeros(len(wa)) if is_ls else np.maximum(0.0, 1.0 - np.sum(wa, axis=1))
            tot10 = np.sum(wa * rm, axis=1) + cash_w * rf_p - to * 10e-4
            rf_cmp = np.zeros(len(wa)) if is_ls else rf_p
            m_is = idx_p < pd.Timestamp("2023-01-01")
            m_oos = idx_p >= pd.Timestamp("2023-01-01")
            xs_res[tag] = {
                "all_10bp": stats_arr(tot10, rf_cmp),
                "is_18_22": stats_arr(tot10[m_is], rf_cmp[m_is]),
                "oos_23_26": stats_arr(tot10[m_oos], rf_cmp[m_oos]),
            }

    # 4. Binance Futures Daily Metrics (2021-12..2026-10: OI, TopTrader L/S, Global L/S, Taker L/S)
    met = pd.read_csv(ROOT / "data" / "crypto_vision" / "binance_um_daily_metrics.csv.gz")
    met["date"] = pd.to_datetime(met["date"])
    met_res = {}
    for sym in ("BTCUSDT", "ETHUSDT"):
        sub_m = met[met["symbol"] == sym].set_index("date").sort_index()
        c_s = px[sym].reindex(sub_m.index).dropna()
        r_s = c_s.pct_change().fillna(0.0)
        rf_s = rf_d.reindex(c_s.index).fillna(0.0)
        sub_m = sub_m.reindex(c_s.index)
        oi_z = (sub_m["oi_usd"] - sub_m["oi_usd"].rolling(30).mean()) / sub_m["oi_usd"].rolling(30).std()
        tt_z = (sub_m["toptrader_ls_pos_ratio"] - sub_m["toptrader_ls_pos_ratio"].rolling(30).mean()) / sub_m["toptrader_ls_pos_ratio"].rolling(30).std()
        gl_z = (sub_m["global_ls_count_ratio"] - sub_m["global_ls_count_ratio"].rolling(30).mean()) / sub_m["global_ls_count_ratio"].rolling(30).std()
        tk_z = (sub_m["taker_ls_vol_ratio_mean"] - sub_m["taker_ls_vol_ratio_mean"].rolling(30).mean()) / sub_m["taker_ls_vol_ratio_mean"].rolling(30).std()

        fwd7 = c_s.pct_change(7).shift(-7)
        corrs = {}
        for fn, fser in [("oi_usd_z30", oi_z), ("toptrader_ls_z30", tt_z), ("global_ls_z30", gl_z), ("taker_ls_z30", tk_z)]:
            df_c = pd.DataFrame({"f": fser, "r1": r_s.shift(-1), "r7": fwd7}).dropna()
            corrs[fn] = {"ic_1d": round(float(df_c["f"].corr(df_c["r1"], method="spearman")), 4),
                         "ic_7d": round(float(df_c["f"].corr(df_c["r7"], method="spearman")), 4)}

        # Causal trading strategies on metrics (strictly t-1 lag, 10bp) & crowding gate on TrendEns_VT25
        ens = sum((c_s > c_s.rolling(lb).mean()).astype(float) for lb in (20, 40, 60, 90, 120)) / 5.0
        rv21 = (r_s.rolling(21).std() * math.sqrt(365.0)).clip(lower=0.15)
        vt = np.minimum(1.0, 0.25 / rv21)
        m_valid = c_s.index >= pd.Timestamp("2022-02-01")
        idx_m = c_s.index[m_valid]
        rm_a, rfm_a = r_s[m_valid].to_numpy(), rf_s[m_valid].to_numpy()
        m_is_m = idx_m < pd.Timestamp("2024-06-01")
        m_oos_m = idx_m >= pd.Timestamp("2024-06-01")

        strats = {
            "TrendEns_VT25_Base": (ens * vt).shift(1),
            "TrendEns_VT25_Deleverage_HighGlobalLS": ((ens * vt) * np.where(gl_z > 1.5, 0.5, 1.0)).shift(1),
            "Contrarian_RetailCrowding_LongCash": (gl_z < -0.5).astype(float).shift(1),
            "TakerVol_Momentum_LongCash": (tk_z > 0.5).astype(float).shift(1),
        }
        s_out = {}
        for sn, ws in strats.items():
            wa = ws.fillna(0.0)[m_valid].to_numpy()
            to = np.abs(np.diff(wa, prepend=0.0))
            tot = wa * rm_a + (1.0 - wa) * rfm_a - to * 10e-4
            s_out[sn] = {
                "all": stats_arr(tot, rfm_a),
                "is_22_24": stats_arr(tot[m_is_m], rfm_a[m_is_m]),
                "oos_24_26": stats_arr(tot[m_oos_m], rfm_a[m_oos_m]),
            }
        met_res[sym] = {"spearman_ic": corrs, "strategies": s_out}

    out = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "experiment": "EXP-0043",
        "coins_tested": len(per_coin),
        "per_coin_sma50_vt25": per_coin,
        "basket_all_19_coins_2018_2026": bask_19,
        "basket_17_altcoins_ex_btc_eth_2018_2026": bask_17,
        "cross_sectional_momentum_19coins": xs_res,
        "binance_um_oi_ls_metrics_2021_2026": met_res,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, indent=2))

    print("=== EXP-0043 (1) CRYPTO 19-COIN SURVIVORSHIP-FREE TEST (2018-2026, 10bp, EX-EFFR) ===")
    winners_vs_bh = sum(1 for v in per_coin.values() if v["SMA50_VT25"]["sharpe_ex"] > v["BuyHold"]["sharpe_ex"])
    print(f"  Coins where SMA50_VT25 > BuyHold Sharpe: {winners_vs_bh}/{len(per_coin)}")
    for sym, v in sorted(per_coin.items()):
        print(f"    {sym:9s} ({v['start']}): BH={v['BuyHold']['sharpe_ex']:+.3f}(DD={v['BuyHold']['maxdd_pct']:+.1f}%) | SMA50_VT25={v['SMA50_VT25']['sharpe_ex']:+.3f}(DD={v['SMA50_VT25']['maxdd_pct']:+.1f}%) | EnsVT25={v['TrendEns_VT25']['sharpe_ex']:+.3f}(DD={v['TrendEns_VT25']['maxdd_pct']:+.1f}%)")
    for bname, bres in [("ALL 19 COINS", bask_19), ("17 ALTCOINS (EX BTC/ETH)", bask_17)]:
        print(f"\n  --- BASKET: {bname} ---")
        for sn, sv in bres.items():
            a = sv["all_10bp"]
            print(f"    {sn:26s}: All={a['sharpe_ex']:+.3f}(CAGR={a['cagr_pct']:+.1f}%,DD={a['maxdd_pct']:+.1f}%,Cal={a['calmar']:.3f}) | IS={sv['is_18_22']['sharpe_ex']:+.3f} OOS23-26={sv['oos_23_26']['sharpe_ex']:+.3f} | 30bp={sv['all_30bp']['sharpe_ex']:+.3f} | Shift300={sv['circ_shift300_all_pct']}%")
    print("\n=== EXP-0043 (2) CROSS-SECTIONAL 19-COIN MOMENTUM ===")
    for k, v in xs_res.items():
        print(f"  {k:24s}: All={v['all_10bp']['sharpe_ex']:+.3f} IS={v['is_18_22']['sharpe_ex']:+.3f} OOS={v['oos_23_26']['sharpe_ex']:+.3f}")
    print("\n=== EXP-0043 (3) BINANCE FUTURES OI & L/S CROWDING (2021-12..2026-10) ===")
    for sym, mv in met_res.items():
        print(f"  {sym} IC:", mv["spearman_ic"])
        for sn, sv in mv["strategies"].items():
            print(f"    {sn:40s}: All={sv['all']['sharpe_ex']:+.3f} IS={sv['is_22_24']['sharpe_ex']:+.3f} OOS={sv['oos_24_26']['sharpe_ex']:+.3f}")


if __name__ == "__main__":
    main()
