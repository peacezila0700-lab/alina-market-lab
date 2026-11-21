#!/usr/bin/env python3
"""
tests/test_workstreams.py — Empirical verification suite for Workstreams A, B, C, D and Phase 1 fixes.
"""
from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def test_universe_and_vol_term_restored() -> None:
    uni = list((ROOT / "data" / "universe").glob("*.csv"))
    assert len(uni) >= 26, f"Expected >=26 universe CSVs, found {len(uni)}"
    assert (ROOT / "data" / "universe" / "SPY.csv").exists()
    assert (ROOT / "data" / "universe" / "VIXY.csv").exists()

    vt = pd.read_csv(ROOT / "data" / "collect" / "vol_term_structure.csv")
    assert vt.columns[0] == "date", f"Bad vol_term header: {vt.columns[0]}"
    assert len(vt) > 9000


def test_news_feeds_all_ok() -> None:
    fs = json.loads((ROOT / "data" / "news" / "feed_status.json").read_text())
    feeds = fs["feeds"]
    bad = {k: v for k, v in feeds.items() if not str(v).startswith("OK")}
    assert not bad, f"Broken news feeds: {bad}"


def test_workstream_a_sec_pit_expanded_zero_leaks() -> None:
    man = json.loads((ROOT / "data" / "sec" / "MANIFEST_PIT_SEC_EXPANDED.json").read_text())
    assert man["tickers"] >= 300, f"Expected >=300 SEC firms, got {man['tickers']}"
    assert man["leak_check_available_before_period_end"] == 0, "PIT leak detected!"

    pit = pd.read_csv(ROOT / "data" / "sec" / "pit_fundamentals_expanded.csv")
    assert len(pit) >= 14000
    assert (pd.to_datetime(pit["available_from"]) < pd.to_datetime(pit["latest_period_end"])).sum() == 0

    e26 = json.loads((ROOT / "research" / "artifacts" / "exp0026_sec_pit_300.json").read_text())
    assert e26["universe_firms"] >= 300
    assert e26["results"]["F_NEG_ACCRUALS"]["bonferroni_99_both_pass"] is False


def test_workstream_a2_macro_and_events() -> None:
    cb = pd.read_csv(ROOT / "data" / "macro" / "central_bank_rates_daily.csv")
    assert len(cb) > 9000
    assert pd.to_datetime(cb["date"]).is_monotonic_increasing

    e27 = json.loads((ROOT / "research" / "artifacts" / "exp0027_macro_events.json").read_text())
    assert e27["volatility_prediction"]["oos_onset_auc"] > 0.65


def test_workstream_b_microstructure_and_carry() -> None:
    f_btc = pd.read_csv(ROOT / "data" / "microstructure" / "deribit_BTC_funding_1h.csv.gz")
    assert len(f_btc) >= 24000

    e28 = json.loads((ROOT / "research" / "artifacts" / "exp0028_fx_carry.json").read_text())
    assert e28["pairs"]["EURGBP"]["rollover_spread_multiplier"] > 1.5
    e29 = json.loads((ROOT / "research" / "artifacts" / "exp0029_crypto_basis.json").read_text())
    assert "NOT_ARBITRAGE" in e29["cross_venue_okx_deribit"]["cross_venue_tradability_verdict"]


def test_workstream_c_ea_kb_batch5_integrity() -> None:
    db = ROOT / "data" / "ea_kb" / "alina_ea_kb.sqlite"
    conn = sqlite3.connect(db)
    chk = conn.execute("PRAGMA integrity_check").fetchone()[0]
    assert chk == "ok"
    cnt = conn.execute("SELECT COUNT(*) FROM source_files").fetchone()[0]
    assert cnt >= 2174, f"Expected >=2174 KB Batch 6 source files, found {cnt}"
    rows = conn.execute("SELECT local_path FROM source_files").fetchall()
    missing = [r[0] for r in rows if not (ROOT / r[0]).exists()]
    assert not missing, f"Missing local KB paths: {missing[:5]}"
    conn.close()

    prov = json.loads((ROOT / "data" / "ea_kb" / "batch6_provenance_audit.json").read_text())
    assert len(prov) == 74
    kb_b6 = json.loads((ROOT / "data" / "ea_kb" / "KB_STATS_BATCH6.json").read_text())
    assert kb_b6["totals"]["source_files"] >= 2174
    assert any("quantopian/research_public" in str(ex) for ex in kb_b6["excluded_unlicensed_audit"])


def test_workstream_d_risk_radar_and_offline_dashboard() -> None:
    rr = json.loads((ROOT / "data" / "risk_radar" / "latest.json").read_text())
    assert rr["total_panels"] == 9
    assert "equity_short_insider_breadth" in rr["panels"]
    assert "RISK MONITORING TOOL ONLY" in rr["disclaimer"]
    assert rr["overall_risk_classification"] in ("LOW", "MODERATE", "ELEVATED", "HIGH")
    assert "calibrated_probabilities" in rr.get("risk_meta_model", {})
    assert "latest_spread_pips" in rr.get("fx_execution_guard", {})
    assert "btc_close" in rr.get("crypto_trend_overlay", {})

    hist_lines = (ROOT / "data" / "risk_radar" / "history.jsonl").read_text().strip().splitlines()
    assert len(hist_lines) >= 1
    json.loads(hist_lines[-1])

    html_txt = (ROOT / "dashboard" / "alina_today.html").read_text()
    assert "Risk Radar" in html_txt
    assert "Risk Meta-Labeling" in html_txt
    assert "FX Rollover & Liquidity Guard" in html_txt
    assert "Crypto Trend Regime & VolTarget25%" in html_txt
    assert "<script src=\"http" not in html_txt.lower()
    assert "fetch(" not in html_txt.lower()

    res = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "telegram_bot.py"), "--dry-run", "--mock-text", "/risk"],
        capture_output=True, text=True, check=True
    )
    assert "RISK MONITOR ONLY" in res.stdout


def test_registries_and_v218_meta_labeling_experiments() -> None:
    df_exp = pd.read_csv(ROOT / "research" / "EXPERIMENT_LOG.csv")
    df_hyp = pd.read_csv(ROOT / "research" / "HYPOTHESIS_REGISTER.csv")
    assert len(df_exp) >= 31 and len(df_exp.columns) == 16
    assert len(df_hyp) >= 26 and len(df_hyp.columns) == 25
    assert "EXP-0030" in set(df_exp["exp_id"]) and "EXP-0031" in set(df_exp["exp_id"])

    e30 = json.loads((ROOT / "research" / "artifacts" / "exp0030_triple_barrier.json").read_text())
    ta, tb = e30["track_a_spy_daily_triple_barrier"], e30["track_b_eurgbp_h1_triple_barrier"]
    assert ta["leakage_audit"]["purged_gap_assertion_passed"] is True
    assert ta["target_a3_tb_nondir_stress"]["purged_wf_5fold_hgbc"]["roc_auc"] > 0.63
    assert tb["risk_shock_classification"]["oos_state_only_noclock_platt"]["roc_auc"] > 0.63
    assert tb["execution_cost_survival_oos_6h_nonoverlap"]["MetaLabel_Risk_Gated_70pct_VALID"]["net_mean_pips"] < 0.0

    e31 = json.loads((ROOT / "research" / "artifacts" / "exp0031_cross_asset_overlay.json").read_text())
    wf = e31["wf_2015_2026_full"]
    assert wf["5_VolTarget12_Meta_Cash"]["net"]["max_dd_pct"] > wf["1_SPY_Buy_And_Hold"]["net"]["max_dd_pct"]
    assert wf["5_VolTarget12_Meta_Cash"]["net"]["max_dd_pct"] > wf["6_VolTarget12_Meta_TLT_Rot"]["net"]["max_dd_pct"]


def test_v219_cloud_data_upgrades_and_cleanups() -> None:
    # Broad panel includes TLT & post-close 2026-11-20 SPY=689.81
    tlt = pd.read_csv(ROOT / "data" / "broad" / "TLT.csv")
    spy = pd.read_csv(ROOT / "data" / "broad" / "SPY.csv")
    assert len(tlt) >= 6100 and "adjclose" in tlt.columns
    assert str(spy["date"].iloc[-1]) == "2026-11-20" and abs(float(spy["close"].iloc[-1]) - 689.81) < 0.05

    # Central bank EFFR 100% backfilled via FRED DFF
    cb = pd.read_csv(ROOT / "data" / "macro" / "central_bank_rates_daily.csv")
    assert int(cb["effr"].isna().sum()) == 0

    # COT deduplicated (0 duplicates)
    cot_f = pd.read_csv(ROOT / "data" / "cot" / "cot_features.csv")
    assert int(cot_f.duplicated(["instrument", "report_date"]).sum()) == 0

    # Event calendar extends through 2027 with official CB meetings
    ev = pd.read_csv(ROOT / "data" / "events" / "event_calendar_full.csv")
    assert str(ev["date"].max()) >= "2027-12-31"
    assert {"FOMC", "ECB", "BOE", "BOJ"}.issubset(set(ev[ev["date"].astype(str).str.startswith("2027")]["event"]))

    # Intraday H1 crossed spreads fixed & Deribit funding 0 gaps
    for pair in ("EURUSD", "USDJPY"):
        df_h = pd.read_csv(ROOT / "data" / "intraday" / f"{pair}_H1_bidask.csv.gz")
        assert int((df_h["spread_close_pips"] < 0).sum()) == 0
    for sym in ("BTC", "ETH"):
        df_d = pd.read_csv(ROOT / "data" / "microstructure" / f"deribit_{sym}_funding_1h.csv.gz")
        ts = pd.to_datetime(df_d["ts"], format="ISO8601", utc=True)
        assert int((ts.diff() > pd.Timedelta(hours=1)).sum()) == 0

    # Binance Vision 2020-2026 & SEC Delisted PIT zero-leak
    bv = pd.read_csv(ROOT / "data" / "crypto_vision" / "binance_BTCUSDT_um_perp_1h.csv.gz")
    assert len(bv) >= 59000 and str(bv["ts_utc"].iloc[0]).startswith("2020-01-01")
    pdel = pd.read_csv(ROOT / "data" / "sec" / "pit_fundamentals_delisted.csv")
    assert pdel["ticker"].nunique() >= 65
    assert int((pd.to_datetime(pdel["available_from"]) < pd.to_datetime(pdel["latest_period_end"])).sum()) == 0
    assert not (ROOT / "data" / "equities" / "finra_short_interest_latest5k.csv.gz").exists()


def test_exp0032_0033_survivorship_and_total_return() -> None:
    e32 = json.loads((ROOT / "research" / "artifacts" / "exp0032_survivorship_free_sec_pit.json").read_text())
    assert e32["survivorship_augmented"]["firms"] >= e32["active_only"]["firms"] + 25
    # Survivorship bias test confirms active-only overstated F_NEG_ACCRUALS Sharpe
    assert e32["survivorship_augmented"]["results"]["F_NEG_ACCRUALS"]["ls_10bp_all"] < e32["active_only"]["results"]["F_NEG_ACCRUALS"]["ls_10bp_all"]

    e33 = json.loads((ROOT / "research" / "artifacts" / "exp0033_total_return_tiingo_overlay.json").read_text())
    tr = e33["total_return_results"]
    assert tr["5_VolTarget12_Meta_Cash"]["cash_bil_etf"]["calmar_cagr"] > tr["1_SPY_Buy_And_Hold"]["cash_bil_etf"]["calmar_cagr"]
    assert tr["5_VolTarget12_Meta_Cash"]["cash_bil_etf"]["max_dd_pct"] > tr["6_VolTarget12_Meta_TLT_Rot"]["cash_bil_etf"]["max_dd_pct"]


def test_exp0034_0035_expanded_survivorship_and_form4_regsho() -> None:
    e34 = json.loads((ROOT / "research" / "artifacts" / "exp0034_expanded_survivorship_pit.json").read_text())
    assert e34["survivorship_augmented_2usd"]["delisted_in_panel"] >= 65
    assert e34["survivorship_augmented_2usd"]["firms"] >= 380
    assert (
        e34["survivorship_augmented_2usd"]["results"]["F_NEG_ACCRUALS"]["ls_10bp_all"]
        < e34["active_only"]["results"]["F_NEG_ACCRUALS"]["ls_10bp_all"]
    )

    f4 = pd.read_csv(ROOT / "data" / "sec" / "insider_form4_2018_2026q1.csv.gz")
    assert len(f4) >= 900000 and f4["issuertradingsymbol"].nunique() >= 8000

    reg_m = pd.read_csv(ROOT / "data" / "equities" / "finra_regsho_market_daily.csv")
    assert len(reg_m) >= 1900 and str(reg_m["date"].iloc[-1]) >= "2026-11-20"
    reg_u = pd.read_csv(ROOT / "data" / "equities" / "finra_regsho_universe_daily.csv.gz")
    assert len(reg_u) >= 600000 and reg_u["ticker"].nunique() >= 370

    e35 = json.loads((ROOT / "research" / "artifacts" / "exp0035_form4_regsho_pit.json").read_text())
    assert e35["universe_firms"] >= 380 and e35["delisted_firms"] >= 65
    assert e35["form4_cross_section"]["F4_LOG_NET_USD_63D_21d"]["perm_pct_oos"] < 95.0


def test_exp0036_to_0042_exhaustive_research_and_crypto_trend() -> None:
    df_exp = pd.read_csv(ROOT / "research" / "EXPERIMENT_LOG.csv")
    assert len(df_exp) >= 42
    for eid in ("EXP-0036", "EXP-0037", "EXP-0038", "EXP-0039", "EXP-0040", "EXP-0041", "EXP-0042"):
        assert eid in set(df_exp["exp_id"])

    e36 = json.loads((ROOT / "research" / "artifacts" / "exp0036_sp500_rebalance_drift.json").read_text())
    assert e36["calendar_portfolio_21d"]["ls_remove_minus_add_21d_net10bp_all"] < 0.0

    e37 = json.loads((ROOT / "research" / "artifacts" / "exp0037_sec_pit_pead_drift.json").read_text())
    assert e37["total_events"] >= 14000
    assert all(v["ls_10bp_all"] < 0.0 for v in e37["calendar_21d_rebalance"].values())

    e38 = json.loads((ROOT / "research" / "artifacts" / "exp0038_crypto_6y_funding_dvol_ofi.json").read_text())
    assert e38["microstructure_1h_ofi_basis"]["BTCUSDT"]["OFI_MOM_1H"]["net4bp_all"] < 0.0
    assert e38["btc_vol_dvol_overlay_2021_2026"]["3_BTC_VT30_DVOL_Throttle"]["all"]["sharpe"] < e38["btc_vol_dvol_overlay_2021_2026"]["2_BTC_VolTarget30"]["all"]["sharpe"]

    e39 = json.loads((ROOT / "research" / "artifacts" / "exp0039_etf_dix_gex_rotation.json").read_text())
    assert e39["global_etf_allocation_2009_2026"]["3_Antonacci_GEM"]["shift_pct_oos"] < 95.0
    assert e39["sector_momentum_2001_2026"]["SPDR_Mom12_1_LS_Top3_Bot3"]["net5bp_all"]["sharpe"] < 0.0

    e40 = json.loads((ROOT / "research" / "artifacts" / "exp0040_treasury_curve_auctions.json").read_text())
    assert e40["curve_duration_timing"]["1_TLT_BuyHold"]["excess_vs_bil_oos"]["sharpe"] < 0.0
    assert e40["treasury_auction_10y_30y"]["n_auctions"] >= 400

    e41 = json.loads((ROOT / "research" / "artifacts" / "exp0041_crypto_trend_regime_verification.json").read_text())
    btc_sma = e41["btc_11_5y"]["SMA50_VT25_1dLag"]
    assert btc_sma["all_10bp"]["sharpe_ex"] > 1.5
    assert btc_sma["circ_shift1000_all_pct"] >= 99.5
    assert btc_sma["cost_stress_sharpe"]["50bp"] > 1.2
    assert e41["cross_asset_blend_spy_vt12_btc_trend_vt25"]["eras"]["CryptoTrend_15pct"]["All_15_26"]["sharpe_ex"] > 1.1

    e42 = json.loads((ROOT / "research" / "artifacts" / "exp0042_overnight_vs_intraday_cost_wall.json").read_text())
    assert e42["results"]["SPY"]["Overnight_2bp_side"]["sharpe"] < 0.0
    assert e42["results"]["SPY"]["Breakeven_bps_per_side"] < 2.0


def test_exp0043_to_0048_v222_open_data_validation() -> None:
    df_exp = pd.read_csv(ROOT / "research" / "EXPERIMENT_LOG.csv")
    assert len(df_exp) >= 48
    for eid in ("EXP-0043", "EXP-0044", "EXP-0045", "EXP-0046", "EXP-0047", "EXP-0048"):
        assert eid in set(df_exp["exp_id"])

    # Verify new v2.22 datasets
    c19 = pd.read_csv(ROOT / "data" / "crypto_vision" / "spot_daily_19coins.csv.gz")
    assert len(c19) >= 50000 and c19["symbol"].nunique() == 19
    um = pd.read_csv(ROOT / "data" / "crypto_vision" / "binance_um_daily_metrics.csv.gz")
    assert len(um) >= 3500 and um["symbol"].nunique() == 2
    liq = pd.read_csv(ROOT / "data" / "macro" / "fred_liquidity_credit.csv")
    assert len(liq) >= 7500 and liq["net_liquidity_bn"].notna().sum() >= 6000
    kf = pd.read_csv(ROOT / "data" / "macro" / "ken_french_ff5_mom_daily.csv.gz")
    assert len(kf) >= 15800
    cot = pd.read_csv(ROOT / "data" / "cot" / "cot_disagg_commodities.csv.gz")
    assert len(cot) >= 8500
    f13 = pd.read_csv(ROOT / "data" / "sec" / "sec_13f_quarterly_holdings.csv.gz")
    assert len(f13) >= 18000 and f13["period_end"].nunique() >= 50 and f13["ticker"].nunique() >= 380
    assert (pd.to_datetime(f13["available_from"]) > pd.to_datetime(f13["period_end"])).all()

    # Verify EXP-0043..0048 artifact results
    e43 = json.loads((ROOT / "research" / "artifacts" / "exp0043_crypto_19coins_and_oi_crowding.json").read_text())
    assert e43["coins_tested"] == 19
    b19 = e43["basket_all_19_coins_2018_2026"]["EqualWeight_SMA50_VT25"]
    assert b19["all_10bp"]["sharpe_ex"] > 1.15 and b19["circ_shift300_all_pct"] >= 99.0
    assert e43["binance_um_oi_ls_metrics_2021_2026"]["BTCUSDT"]["strategies"]["TrendEns_VT25_Deleverage_HighGlobalLS"]["oos_24_26"]["sharpe_ex"] < e43["binance_um_oi_ls_metrics_2021_2026"]["BTCUSDT"]["strategies"]["TrendEns_VT25_Base"]["oos_24_26"]["sharpe_ex"]

    e44 = json.loads((ROOT / "research" / "artifacts" / "exp0044_fed_liquidity_credit_and_svxy_switch.json").read_text())
    assert e44["risk_meta_23f_vs_27f_netliq_hy_auc"]["n_rows"] >= 3800
    assert e44["risk_meta_23f_vs_27f_netliq_hy_auc"]["y_on"]["Plus2_NetLiq"] <= e44["risk_meta_23f_vs_27f_netliq_hy_auc"]["y_on"]["Base23"]
    assert e44["vix_etp_term_switch_2012_2026"]["Switch_SVXY_lt090_else_BIL"]["oos_19_26"]["sharpe"] < 0.0

    e45 = json.loads((ROOT / "research" / "artifacts" / "exp0045_commodity_cot_eia_and_24country_etfs.json").read_text())
    assert e45["eia_inventories_timing"]["USO"]["All"]["sharpe"] < 0.0
    assert e45["country_etf_strategies"]["Country_Mom12_1_Top4Bot4_LS"]["all"]["sharpe"] < 0.0

    e46 = json.loads((ROOT / "research" / "artifacts" / "exp0046_ken_french_63y_factor_timing.json").read_text())
    assert e46["factor_timing_strategies"]["Factor_TSMOM_21d_LS"]["net10bp_recent_10_26"]["sharpe"] < 0.0
    assert e46["individual_factors_decay"]["HML"]["post2010_10_26"]["sharpe"] < 0.0

    e47 = json.loads((ROOT / "research" / "artifacts" / "exp0047_sec_13f_institutional_crowding.json").read_text())
    assert e47["universe_matched_with_13f"] >= 380
    assert e47["strategies"]["13F_breadth_1q_Q5Q1_LS"]["perm200_oos_pct"] < 95.0

    e48 = json.loads((ROOT / "research" / "artifacts" / "exp0048_wikipedia_attention_skew_and_sp500_events.json").read_text())
    assert e48["cboe_skew_33y"]["SPY_Cash_if_SKEW_zgt15"]["oos_15_26"]["sharpe"] < e48["cboe_skew_33y"]["SPY_BuyHold_33y"]["oos_15_26"]["sharpe"]
    assert e48["sp500_addition_removal_drift"]["additions"]["5d"]["mean_ex_spy_pct"] < 0.0


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"ALL {len(tests)}/{len(tests)} WORKSTREAM TESTS PASSED.")
