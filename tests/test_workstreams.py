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
    assert rr["total_panels"] == 8
    assert "RISK MONITORING TOOL ONLY" in rr["disclaimer"]
    assert rr["overall_risk_classification"] in ("LOW", "MODERATE", "ELEVATED", "HIGH")
    assert "calibrated_probabilities" in rr.get("risk_meta_model", {})
    assert "latest_spread_pips" in rr.get("fx_execution_guard", {})

    hist_lines = (ROOT / "data" / "risk_radar" / "history.jsonl").read_text().strip().splitlines()
    assert len(hist_lines) >= 1
    json.loads(hist_lines[-1])

    html_txt = (ROOT / "dashboard" / "alina_today.html").read_text()
    assert "Risk Radar" in html_txt
    assert "Risk Meta-Labeling" in html_txt
    assert "FX Rollover & Liquidity Guard" in html_txt
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


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in tests:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"ALL {len(tests)}/{len(tests)} WORKSTREAM TESTS PASSED.")
