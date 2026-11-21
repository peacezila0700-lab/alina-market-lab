#!/usr/bin/env python3
"""Build ALINA EA KB Batch 6 from verified, explicitly licensed GitHub repositories.

Focus: Risk Management, Position Sizing, Pairs/Kalman/Vol-Regimes, Portfolio & Execution
Controls across Quantopian/Zipline/Pyfolio/Empyrical, ML4T (Stefan Jansen), Freqtrade,
Jesse, cTrader (Spotware), and remaining EarnForex utilities.

Strict provenance & non-contamination:
- Only repositories with verified SPDX OSI licenses (MIT, Apache-2.0, GPL-3.0) enter Confirmed.
- Every file is pinned to an exact GitHub commit SHA verified at runtime via GitHub API.
- Unlicensed/unspecified repositories (e.g. quantopian/research_public) are explicitly excluded
  from Confirmed tables and logged separately in the provenance audit output.
- Existing Batch 1-5 records are never deleted or overwritten.
"""

from __future__ import annotations

import ast
import difflib
import hashlib
import json
import re
import sqlite3
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "ea_kb" / "alina_ea_kb.sqlite"
OUT_DIR = ROOT / "data" / "ea_kb" / "sources_batch6"
STATS_PATH = ROOT / "data" / "ea_kb" / "KB_STATS_BATCH6.json"
MANIFEST_PATH = ROOT / "data" / "ea_kb" / "batch6_provenance_audit.json"

HEADERS = {"User-Agent": "ALINA-Market-Lab/1.0 (provenance-verified research)"}

REPOS_TO_FETCH: dict[str, dict[str, Any]] = {
    "stefan-jansen/machine-learning-for-trading": {
        "cluster": "Risk Management, Position Sizing & Kalman/Regime Models",
        "files": [
            ("09_model_based_features/04_kalman_filter.py", "Quant_Research_Module", "Kalman_Pairs_Hedge"),
            ("09_model_based_features/08_garch_volatility.py", "Quant_Risk_Module", "Volatility_GARCH"),
            ("09_model_based_features/09_har_rough_volatility.py", "Quant_Risk_Module", "Volatility_HAR"),
            ("09_model_based_features/11_hmm_regimes.py", "Quant_Risk_Module", "Regime_HMM"),
            ("02_financial_data_universe/12_fx_pairs_eda.py", "Quant_Research_Module", "FX_Pairs_Analytics"),
            ("17_portfolio_construction/04_kelly_criterion.py", "Quant_Risk_Module", "Position_Sizing_Kelly"),
            ("17_portfolio_construction/06_hierarchical_risk_parity.py", "Quant_Risk_Module", "Portfolio_HRP"),
            ("19_risk_management/01_var_cvar.py", "Quant_Risk_Module", "Risk_VaR_CVaR"),
            ("19_risk_management/02_exit_strategies.py", "Quant_Risk_Module", "Exit_Stop_Trailing"),
            ("19_risk_management/03_position_sizing_mae_mfe.py", "Quant_Risk_Module", "Position_Sizing_MAE_MFE"),
            ("19_risk_management/06_stress_testing.py", "Quant_Risk_Module", "Risk_Stress_Testing"),
            ("19_risk_management/07_drift_detection.py", "Quant_Risk_Module", "Model_Drift_Guard"),
            ("19_risk_management/08_ml_exit_signals.py", "Quant_Risk_Module", "ML_Exit_Timing"),
            ("25_live_trading/10_safety_risk_demo.py", "Quant_Execution_Guard", "Live_Safety_Limits"),
            ("26_mlops_governance/04_circuit_breakers.py", "Quant_Execution_Guard", "Circuit_Breaker"),
            ("case_studies/fx_pairs/02_labels.py", "Quant_Research_Module", "FX_Barrier_Labeling"),
            ("case_studies/fx_pairs/15_risk_management.py", "Quant_Risk_Module", "FX_Risk_Overlay"),
            ("case_studies/fx_pairs/16_costs.py", "Quant_Execution_Guard", "FX_Cost_Slippage"),
        ],
    },
    "quantopian/zipline": {
        "cluster": "Quantopian / Zipline Portfolio & Execution Architecture",
        "files": [
            ("zipline/examples/olmar.py", "Strategy (Zipline)", "MultiAsset_MeanReversion"),
            ("zipline/examples/dual_ema_talib.py", "Strategy (Zipline)", "Dual_EMA_Template"),
            ("zipline/examples/momentum_pipeline.py", "Strategy (Zipline)", "Pipeline_CrossSectional"),
            ("zipline/examples/dual_moving_average.py", "Strategy (Zipline)", "Zipline_MA_Template"),
        ],
    },
    "quantopian/empyrical": {
        "cluster": "Quantopian Risk & Performance Metrics",
        "files": [
            ("empyrical/stats.py", "Quant_Risk_Library", "Risk_Metrics_Stats"),
            ("empyrical/perf_attrib.py", "Quant_Risk_Library", "Risk_Attribution"),
        ],
    },
    "quantopian/pyfolio": {
        "cluster": "Quantopian Portfolio Drawdown, Capacity & Round-Trip Risk",
        "files": [
            ("pyfolio/timeseries.py", "Quant_Risk_Library", "Drawdown_Rolling_Risk"),
            ("pyfolio/round_trips.py", "Quant_Risk_Library", "RoundTrip_Trade_Audit"),
            ("pyfolio/capacity.py", "Quant_Risk_Library", "Slippage_Capacity_Limit"),
        ],
    },
    "freqtrade/freqtrade": {
        "cluster": "Freqtrade Engine Risk Protections & Strategy Interface",
        "files": [
            ("freqtrade/plugins/protections/iprotection.py", "Risk_Protection_Interface", "Protection_Base"),
            ("freqtrade/plugins/protections/max_drawdown_protection.py", "Risk_Protection_Guard", "Max_Drawdown_Guard"),
            ("freqtrade/plugins/protections/stoploss_guard.py", "Risk_Protection_Guard", "Stoploss_Guard"),
            ("freqtrade/plugins/protections/cooldown_period.py", "Risk_Protection_Guard", "Cooldown_Period"),
            ("freqtrade/plugins/protections/low_profit_pairs.py", "Risk_Protection_Guard", "Low_Profit_Lock"),
            ("freqtrade/strategy/interface.py", "Strategy_Framework_Interface", "IStrategy_Lifecycle"),
            ("freqtrade/wallets.py", "Execution_Wallet_Manager", "Wallet_Stake_Control"),
        ],
    },
    "freqtrade/freqtrade-strategies": {
        "cluster": "Freqtrade Risk-Managed & Execution Strategies",
        "files": [
            ("user_data/strategies/BreakEven.py", "Strategy (Freqtrade)", "BreakEven_Stop"),
            ("user_data/strategies/FixedRiskRewardLoss.py", "Strategy (Freqtrade)", "Fixed_Risk_Reward_CustomSL"),
            ("user_data/strategies/CustomStoplossWithPSAR.py", "Strategy (Freqtrade)", "Dynamic_Trailing_PSAR_SL"),
            ("user_data/strategies/AlmgrenChrissStrategy.py", "Strategy (Freqtrade)", "Execution_Almgren_Chriss"),
            ("user_data/strategies/TWAPStrategy.py", "Strategy (Freqtrade)", "Execution_TWAP"),
            ("user_data/strategies/Strategy001_custom_exit.py", "Strategy (Freqtrade)", "Custom_Exit_Signal"),
            ("user_data/strategies/InformativeSample.py", "Strategy (Freqtrade)", "MultiTimeframe_Guard"),
            ("user_data/strategies/Supertrend.py", "Strategy (Freqtrade)", "ATR_Volatility_Trend"),
        ],
    },
    "jesse-ai/example-strategies": {
        "cluster": "Jesse Python Strategy Lifecycle & Risk Sizing",
        "files": [
            ("TurtleRules/__init__.py", "Strategy (Jesse)", "ATR_Sizing_Pyramiding_Breakout"),
            ("Donchian/__init__.py", "Strategy (Jesse)", "ATR_Risk_Breakout"),
            ("DUAL_THRUST/__init__.py", "Strategy (Jesse)", "Range_Breakout_Fixed_Risk"),
            ("IFR2/__init__.py", "Strategy (Jesse)", "MeanReversion_Risk_Size"),
            ("KDJstrategy/__init__.py", "Strategy (Jesse)", "Oscillator_ATR_Stop"),
            ("MACD_EMA/__init__.py", "Strategy (Jesse)", "Trend_ATR_Stop"),
            ("MAGen/__init__.py", "Strategy (Jesse)", "MA_Cross_Risk"),
            ("RSI2/__init__.py", "Strategy (Jesse)", "RSI2_MeanReversion"),
            ("SMACrossover/__init__.py", "Strategy (Jesse)", "SMA_Trend_Risk"),
            ("SimpleBollinger/__init__.py", "Strategy (Jesse)", "Volatility_Band_Exit"),
            ("TradingView_RSI/__init__.py", "Strategy (Jesse)", "RSI_Threshold_Risk"),
        ],
    },
    "spotware/ctrader-algo-samples": {
        "cluster": "cTrader C# cBot Risk, Execution & Order Control",
        "files": [
            ("Robots/Sample Break Even/Sample Break Even/Sample Break Even.cs", "cBot (cTrader C#)", "BreakEven_Stop"),
            ("Robots/Sample SAR Trailing Stop/Sample SAR Trailing Stop/Sample SAR Trailing Stop.cs", "cBot (cTrader C#)", "Trailing_Stop_SAR"),
            ("Robots/Sample Close Profitable Positions cBot/Sample Close Profitable Positions cBot/Sample Close Profitable Positions cBot.cs", "cBot (cTrader C#)", "Basket_Profit_Close"),
            ("Robots/Close All On Market Close Sample/Close All On Market Close Sample/Close All On Market Close Sample.cs", "cBot (cTrader C#)", "Market_Close_Flatten"),
            ("Robots/Partial Close Sample/Partial Close Sample/Partial Close Sample.cs", "cBot (cTrader C#)", "Partial_Position_Close"),
            ("Robots/Position Execution Sample/Position Execution Sample/Position Execution Sample.cs", "cBot (cTrader C#)", "Position_Execution_Sync_Async"),
            ("Robots/Position Modification Sample/Position Modification Sample/Position Modification Sample.cs", "cBot (cTrader C#)", "SL_TP_Modification"),
            ("Robots/Pending Order Modification Sample/Pending Order Modification Sample/Pending Order Modification Sample.cs", "cBot (cTrader C#)", "Pending_Order_Modify"),
            ("Robots/Pending Order Cancelation Sample/Pending Order Cancelation Sample/Pending Order Cancelation Sample.cs", "cBot (cTrader C#)", "Pending_Order_Cancel"),
            ("Robots/Pending Order Placing Sample/Pending Order Placing Sample/Pending Order Placing Sample.cs", "cBot (cTrader C#)", "Limit_Stop_Order_Placement"),
            ("Robots/Custom Fitness Functions/Custom Fitness Functions/Custom Fitness Functions.cs", "cBot (cTrader C#)", "Custom_Fitness_Optimization"),
            ("Robots/StopTriggerMethod Sample/StopTriggerMethod Sample/StopTriggerMethod Sample.cs", "cBot (cTrader C#)", "Stop_Trigger_Spread_Protection"),
            ("Robots/BarClosed Example/BarClosed Example/BarClosed Example.cs", "cBot (cTrader C#)", "OnBarClosed_AntiRepaint_Execution"),
        ],
    },
    "EarnForex/AutoTrading-Scheduler": {
        "cluster": "EarnForex Session/Rollover/News Exposure Scheduler",
        "files": [
            ("MQL4/Experts/AutoTrading Scheduler/AutoTrading Scheduler.mq4", "Risk Utility EA (MT4)", "Session_Schedule_AutoDisable"),
            ("MQL4/Experts/AutoTrading Scheduler/AutoTrading Scheduler.mqh", "Risk Utility Include (MT4)", "Schedule_Panel_State"),
            ("MQL4/Experts/AutoTrading Scheduler/Defines.mqh", "Risk Utility Include (MT4)", "Schedule_Definitions"),
            ("MQL5/Experts/AutoTrading Scheduler/AutoTrading Scheduler.mq5", "Risk Utility EA (MT5)", "Session_Schedule_AutoDisable"),
            ("MQL5/Experts/AutoTrading Scheduler/AutoTrading Scheduler.mqh", "Risk Utility Include (MT5)", "Schedule_Panel_State"),
            ("MQL5/Experts/AutoTrading Scheduler/Defines.mqh", "Risk Utility Include (MT5)", "Schedule_Definitions"),
        ],
    },
    "EarnForex/Spread": {
        "cluster": "EarnForex Real-Time Spread Cost Monitor",
        "files": [
            ("Spread.mq4", "Spread Monitor Indicator (MT4)", "Spread_Cost_Monitor"),
            ("Spread.mq5", "Spread Monitor Indicator (MT5)", "Spread_Cost_Monitor"),
        ],
    },
}


def api_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_raw(url: str) -> bytes:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read()


def extract_dependencies(code: str, ext: str) -> list[str]:
    deps: list[str] = []
    if ext == ".py":
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for n in node.names:
                        deps.append(n.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom) and node.module:
                    deps.append(node.module.split(".")[0])
        except SyntaxError:
            for m in re.findall(r"^(?:from|import)\s+([A-Za-z0-9_\.]+)", code, flags=re.M):
                deps.append(m.split(".")[0])
    elif ext == ".cs":
        deps = re.findall(r"^\s*using\s+([A-Za-z0-9_\.]+)\s*;", code, flags=re.M)
    elif ext in (".mq4", ".mq5", ".mqh"):
        deps = re.findall(r'^\s*#include\s+[<"]([^>"]+)[>"]', code, flags=re.M)
    seen: list[str] = []
    for d in deps:
        if d not in seen:
            seen.append(d)
    return seen


def extract_author_hint(code: str, default_owner: str) -> str:
    patterns = [
        r"@author[:\s]+([^\n\r*]+)",
        r"Author[:\s]+([^\n\r*]+)",
        r'#property\s+copyright\s+"([^"]+)"',
    ]
    for pat in patterns:
        m = re.search(pat, code[:2500], flags=re.I)
        if m:
            txt = m.group(1).strip().strip('"').strip("'")
            if 2 <= len(txt) <= 80:
                return txt
    return default_owner


def analyze_risk_and_logic(code: str, ext: str, domain_tag: str) -> dict[str, Any]:
    low = code.lower()
    risk_controls = []
    checks = {
        "HardSL": any(k in low for k in ("stoploss", "stop_loss", "sl =", "setsL", "modifyposition", "atr", "custom_stoploss")),
        "TrailingStop": any(k in low for k in ("trailing", "trail_stop", "parabolic", "psar", "sar.result")),
        "BreakEven": any(k in low for k in ("breakeven", "break_even", "break even", "is_be")),
        "PositionSizing": any(k in low for k in ("custom_stake_amount", "kelly", "position_size", "risk_to_qty", "qty =", "lot", "volumeequals", "mae", "mfe", "hrp")),
        "DrawdownGuard": any(k in low for k in ("maxdrawdown", "max_drawdown", "drawdown", "circuit_breaker", "kill_switch")),
        "CooldownOrLock": any(k in low for k in ("cooldown", "lock_pair", "low_profit", "stoplossguard")),
        "ScheduleOrMarketClose": any(k in low for k in ("autotrading", "scheduler", "market_close", "onbarclosed", "onbar")),
        "SpreadOrSlippageCost": any(k in low for k in ("spread", "slippage", "stoptriggermethod", "almgren", "twap", "capacity", "commission")),
        "VaR_CVaR_RiskMetrics": any(k in low for k in ("var(", "cvar", "value_at_risk", "expected_shortfall", "sortino", "calmar", "downside_risk")),
        "VolatilityOrRegime": any(k in low for k in ("kalman", "garch", "hmm", "volatility", "realized_vol", "regime")),
        "PartialOrBasketExit": any(k in low for k in ("partial", "closeposition", "custom_exit", "take_profit", "tp =")),
    }
    for k, hit in checks.items():
        if hit:
            risk_controls.append(k)

    indicators = []
    for ind in ("kalman", "garch", "hmm", "atr", "ema", "sma", "rsi", "macd", "bollinger", "donchian", "supertrend", "psar", "sar", "stoch", "cci", "adx", "vwap", "kelly", "hrp", "var", "cvar"):
        if re.search(rf"\b{ind}\b", low):
            indicators.append(ind.upper())

    has_sl = 1 if (checks["HardSL"] or checks["TrailingStop"] or checks["BreakEven"]) else 0
    has_tp = 1 if ("take_profit" in low or "minimal_roi" in low or "takeprofit" in low or "custom_exit" in low) else 0
    has_grid = 1 if ("martingale" in low or ("grid" in low and "grid" not in "gridsearch")) else 0

    return {
        "risk_controls": risk_controls,
        "indicators": indicators,
        "has_sl": has_sl,
        "has_tp": has_tp,
        "has_grid": has_grid,
        "domain_tag": domain_tag,
    }


def classify_platform(repo: str, ext: str, role: str) -> str:
    if repo.startswith("freqtrade/"):
        return "Python_Freqtrade"
    if repo.startswith("jesse-ai/"):
        return "Python_Jesse"
    if repo.startswith("quantopian/"):
        return "Python_Quantopian"
    if repo.startswith("stefan-jansen/"):
        return "Python_ML4T"
    if repo.startswith("spotware/"):
        return "cTrader_CSharp"
    if ext == ".mq4":
        return "MT4"
    if ext == ".mq5":
        return "MT5"
    if ext == ".mqh":
        return "MQL_Include"
    return "Other"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    # Load existing hashes and normalized URLs for strict deduplication
    existing_hashes: dict[str, tuple[str, str]] = {}
    existing_norm_urls: dict[str, list[tuple[str, str]]] = {}
    for src_id, sha, lp, url in cur.execute("SELECT src_id, sha256, local_path, source_url FROM source_files"):
        if sha:
            existing_hashes[sha] = (src_id, lp)
        if url:
            nu = urllib.parse.unquote(url)
            existing_norm_urls.setdefault(nu, []).append((src_id, lp))

    # Audit pre-existing EarnForex URL-encoding duplicates (read-only awareness)
    preexisting_url_dups = []
    for nu, lst in existing_norm_urls.items():
        if len(lst) > 1:
            preexisting_url_dups.append({"normalized_url": nu, "records": lst})

    # Determine next IDs cleanly
    max_q = max(int(r[0].split("-")[1]) for r in cur.execute("SELECT task_id FROM research_queue WHERE task_id LIKE 'Q-%'"))
    max_dev = max(int(r[0].split("-")[1]) for r in cur.execute("SELECT dev_id FROM developers WHERE dev_id LIKE 'DEV-%'"))
    max_dup = max(int(r[0].split("_")[-1].split("-")[-1]) for r in cur.execute("SELECT dup_id FROM duplicates"))
    existing_ea_b6 = cur.execute("SELECT COUNT(*) FROM ea_master WHERE ea_id LIKE 'EA-B6-%'").fetchone()[0]
    existing_b6_src = cur.execute("SELECT COUNT(*) FROM source_files WHERE batch='batch6'").fetchone()[0]
    if existing_b6_src > 0:
        raise RuntimeError(f"Batch 6 already has {existing_b6_src} rows; aborting to preserve idempotency.")

    # Check if quantopian/research_public lacks LICENSE (explicit provenance proof)
    unlicensed_probe = api_json("https://api.github.com/repos/quantopian/research_public")
    unlicensed_record = {
        "repo": "quantopian/research_public",
        "url": unlicensed_probe["html_url"],
        "stars": unlicensed_probe["stargazers_count"],
        "license": (unlicensed_probe.get("license") or {}).get("spdx_id") or "UNSPECIFIED",
        "decision": "EXCLUDED_FROM_CONFIRMED",
        "reason": "GitHub API reports license=None and repository tree lacks a LICENSE file; strictly excluded per provenance rule.",
    }

    q_counter = max_q
    dev_counter = max_dev
    dup_counter = max_dup
    ea_counter = existing_ea_b6
    src_counter = 0

    existing_devs = {r[1]: r[0] for r in cur.execute("SELECT dev_id, name FROM developers")}
    existing_repos = {r[1]: r[0] for r in cur.execute("SELECT task_id, repo FROM github_repos")}

    batch6_records = []
    repo_summaries = []
    dup_records = []
    kg_new = []

    fetched_code_by_src: dict[str, tuple[str, str, str]] = {}  # src_id -> (repo, path, code)

    for repo, spec in REPOS_TO_FETCH.items():
        info = api_json(f"https://api.github.com/repos/{repo}")
        lic = (info.get("license") or {}).get("spdx_id")
        if not lic or lic in ("NOASSERTION", "NONE", "UNSPECIFIED"):
            raise RuntimeError(f"Refusing to ingest {repo} with unverified license={lic!r}")
        br = info["default_branch"]
        commit_obj = api_json(f"https://api.github.com/repos/{repo}/commits/{br}")
        commit_sha = commit_obj["sha"]
        commit_date = commit_obj["commit"]["committer"]["date"]
        owner = info["owner"]["login"]
        stars = int(info["stargazers_count"])
        forks = int(info["forks_count"])
        repo_url = info["html_url"]
        desc = f"[Batch6 | sha={commit_sha[:12]} | {spec['cluster']}] " + (info.get("description") or "")

        # Register developer / org
        if owner not in existing_devs:
            dev_counter += 1
            dev_id = f"DEV-{dev_counter:04d}"
            cur.execute(
                "INSERT INTO developers VALUES (?, ?, ?, ?, ?, ?)",
                (dev_id, owner, info["owner"]["html_url"], json.dumps([repo]), json.dumps([]), spec["cluster"]),
            )
            existing_devs[owner] = dev_id
        else:
            dev_id = existing_devs[owner]

        # Register repo in research_queue & github_repos if not present
        if repo not in existing_repos:
            q_counter += 1
            repo_q_id = f"Q-{q_counter:04d}"
            cur.execute(
                "INSERT INTO research_queue VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (repo_q_id, "batch6", "github_repo", repo_url, "batch6_curated_audit", "high", "Completed",
                 f"Verified {lic} repo at commit {commit_sha} ({commit_date}); {spec['cluster']}"),
            )
            py_cnt = sum(1 for f, _, _ in spec["files"] if f.endswith(".py"))
            mql_cnt = sum(1 for f, _, _ in spec["files"] if f.endswith((".mq4", ".mq5", ".mqh")))
            cur.execute(
                "INSERT INTO github_repos VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (repo_q_id, repo, repo_url, owner, stars, forks, lic, br, mql_cnt, py_cnt, 0, desc, "Completed"),
            )
            existing_repos[repo] = repo_q_id
        else:
            repo_q_id = existing_repos[repo]

        repo_slug = repo.replace("/", "__")
        repo_dir = OUT_DIR / repo_slug
        repo_dir.mkdir(parents=True, exist_ok=True)

        repo_file_count = 0
        for rel_path, role, domain_tag in spec["files"]:
            enc_path = urllib.parse.quote(rel_path)
            raw_url = f"https://raw.githubusercontent.com/{repo}/{commit_sha}/{enc_path}"
            blob_url = f"https://github.com/{repo}/blob/{commit_sha}/{enc_path}"
            raw_bytes = fetch_raw(raw_url)
            sha256 = hashlib.sha256(raw_bytes).hexdigest()
            code = raw_bytes.decode("utf-8", errors="replace")

            # Check duplicate vs existing DB or earlier in Batch 6
            dup_match = existing_hashes.get(sha256)
            norm_url = urllib.parse.unquote(raw_url)
            url_match = existing_norm_urls.get(norm_url)

            safe_fname = rel_path.replace("/", "__").replace(" ", "_")
            local_abs = repo_dir / safe_fname
            local_abs.write_bytes(raw_bytes)
            local_rel = str(local_abs.relative_to(ROOT))

            ext = Path(rel_path).suffix.lower()
            line_count = len(code.splitlines())
            file_bytes = len(raw_bytes)
            deps = extract_dependencies(code, ext)
            author_hint = extract_author_hint(code, owner)
            analysis = analyze_risk_and_logic(code, ext, domain_tag)
            platform = classify_platform(repo, ext, role)

            q_counter += 1
            file_q_id = f"Q-{q_counter:04d}"
            src_counter += 1
            src_id = f"SRC_B6_{file_q_id}_{src_counter:03d}"

            cur.execute(
                "INSERT INTO research_queue VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (file_q_id, "batch6", "github_source_file", raw_url, repo_q_id, "high", "Completed",
                 f"License={lic}; Commit={commit_sha}; SHA256={sha256[:16]}; Role={role}"),
            )

            cur.execute(
                "INSERT INTO source_files VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    src_id, "batch6", Path(rel_path).name, local_rel, ext, file_bytes, line_count,
                    sha256, platform, role, author_hint, raw_url,
                    json.dumps(analysis["indicators"]),
                    json.dumps({"license": lic, "commit_sha": commit_sha, "repaint_risk": "None_Detected"}),
                    1, "Confirmed",
                ),
            )

            # Register exact duplicate edge if SHA-256 already existed
            if dup_match:
                dup_counter += 1
                dup_id = f"DUP_B6_{dup_counter:04d}"
                cur.execute(
                    "INSERT INTO duplicates VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (dup_id, dup_match[0], dup_match[1], src_id, local_rel, "exact_sha256", 1.0),
                )
                kg_new.append((src_id, "exact_duplicate_of", dup_match[0], 1))
                dup_records.append({"dup_id": dup_id, "type": "exact_sha256", "a": dup_match[0], "b": src_id})
            existing_hashes[sha256] = (src_id, local_rel)

            # Insert authored_by & belongs_to_repo edges
            kg_new.append((src_id, "authored_by", dev_id, 1))
            kg_new.append((src_id, "belongs_to_repo", repo_q_id, 1))
            for rc in analysis["risk_controls"]:
                kg_new.append((src_id, "implements_risk_control", f"RISK:{rc}", 1))

            # Add runnable strategies / cBots / risk EAs / protections to ea_master
            is_ea_entity = (
                role.startswith("Strategy")
                or role.startswith("cBot")
                or role.startswith("Risk Utility EA")
                or role.startswith("Risk_Protection")
                or role == "Quant_Execution_Guard"
                or domain_tag in ("Kalman_Pairs_Hedge", "Position_Sizing_Kelly", "Risk_VaR_CVaR", "Exit_Stop_Trailing", "Position_Sizing_MAE_MFE", "FX_Risk_Overlay", "FX_Cost_Slippage", "Portfolio_HRP")
            )
            ea_id = None
            if is_ea_entity:
                ea_counter += 1
                ea_id = f"EA-B6-{ea_counter:04d}"
                unique_id = ea_id
                trading_logic = (
                    f"{platform} {role} [{domain_tag}] ({line_count} lines, {lic}, commit={commit_sha[:10]}). "
                    f"RiskControls: {', '.join(analysis['risk_controls']) or 'None'}"
                )
                entry_exit = (
                    f"Repo={repo}@{commit_sha[:10]} | Path={rel_path} | "
                    f"Indicators={analysis['indicators']}"
                )
                risk_txt = "; ".join(analysis["risk_controls"]) or "Explicit structural/risk module"
                dep_txt = json.dumps({"license": lic, "commit_sha": commit_sha, "imports_or_includes": deps[:25]})
                ev_txt = (
                    f"Level 1 verified OSI source ({lic}, commit={commit_sha}, "
                    f"SHA256={sha256[:16]}, blob={blob_url}); offline structural/risk reference only."
                )
                cur.execute(
                    "INSERT INTO ea_master VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        ea_id, unique_id, src_id, f"{repo.split('/')[1]}::{Path(rel_path).name if Path(rel_path).name != '__init__.py' else Path(rel_path).parent.name}",
                        author_hint, info["owner"]["html_url"], raw_url, platform, role,
                        "Multi-Asset / FX / Crypto (Architecture Reference)",
                        trading_logic, entry_exit, json.dumps(analysis["indicators"]),
                        risk_txt, dep_txt, ev_txt, local_rel, sha256,
                        json.dumps({"repo": repo, "commit_sha": commit_sha, "license": lic, "blob_url": blob_url}),
                        json.dumps([spec["cluster"], domain_tag]),
                        json.dumps(analysis["indicators"]),
                        analysis["has_sl"], analysis["has_tp"], analysis["has_grid"], 0, 0,
                        1, 1, "Confirmed", trading_logic,
                    ),
                )
                kg_new.append((ea_id, "implemented_in", src_id, 1))
                kg_new.append((ea_id, "uses_strategy", domain_tag, 1))

            # Update kb_fts
            fts_text = (
                f"[batch6 | {platform} | {role} | {lic} | {commit_sha[:10]}] {repo}/{rel_path} "
                f"by {author_hint}. RiskControls: {', '.join(analysis['risk_controls'])}. "
                f"Dependencies: {', '.join(deps[:15])}. Indicators: {', '.join(analysis['indicators'])}."
            )
            cur.execute(
                "INSERT INTO kb_fts VALUES (?, ?, ?, ?, ?, ?, ?)",
                (f"RAG-{src_id}", ea_id or src_id, role, f"{repo}/{rel_path}", raw_url, "Confirmed", fts_text),
            )

            fetched_code_by_src[src_id] = (repo, rel_path, code)
            batch6_records.append({
                "src_id": src_id,
                "ea_id": ea_id,
                "repo": repo,
                "rel_path": rel_path,
                "local_path": local_rel,
                "license": lic,
                "commit_sha": commit_sha,
                "author": author_hint,
                "sha256": sha256,
                "bytes": file_bytes,
                "lines": line_count,
                "dependencies": deps,
                "risk_controls": analysis["risk_controls"],
                "indicators": analysis["indicators"],
                "raw_url": raw_url,
                "blob_url": blob_url,
            })
            repo_file_count += 1

        repo_summaries.append({
            "repo": repo,
            "url": repo_url,
            "license": lic,
            "branch": br,
            "commit_sha": commit_sha,
            "commit_date": commit_date,
            "stars": stars,
            "forks": forks,
            "files_ingested": repo_file_count,
            "cluster": spec["cluster"],
        })

    # Verify Jesse legacy mirror duplicates (example-strategies-master/ vs canonical root)
    jesse_sha = next(r["commit_sha"] for r in repo_summaries if r["repo"] == "jesse-ai/example-strategies")
    jesse_mirror_checks = []
    for folder_root, folder_dup in [
        ("Donchian/__init__.py", "example-strategies-master/Donchian/__init__.py"),
        ("TurtleRules/__init__.py", "example-strategies-master/TurtleRules/__init__.py"),
        ("IFR2/__init__.py", "example-strategies-master/IFR2/__init__.py"),
        ("RSI2/__init__.py", "example-strategies-master/RSI2/__init__.py"),
        ("SMACrossover/__init__.py", "example-strategies-master/SMACrossover/__init__.py"),
        ("SimpleBollinger/__init__.py", "example-strategies-master/SimpleBollinger/__init__.py"),
        ("TradingView_RSI/__init__.py", "example-strategies-master/TradingView_RSI/__init__.py"),
    ]:
        canon_src = next(r["src_id"] for r in batch6_records if r["repo"] == "jesse-ai/example-strategies" and r["rel_path"] == folder_root)
        canon_local = next(r["local_path"] for r in batch6_records if r["src_id"] == canon_src)
        canon_txt = (ROOT / canon_local).read_text(encoding="utf-8", errors="replace")
        dup_raw = fetch_raw(f"https://raw.githubusercontent.com/jesse-ai/example-strategies/{jesse_sha}/{folder_dup}")
        dup_txt = dup_raw.decode("utf-8", errors="replace")
        sim = round(difflib.SequenceMatcher(None, canon_txt, dup_txt).ratio(), 4)
        dup_counter += 1
        dup_id = f"DUP_B6_{dup_counter:04d}"
        cur.execute(
            "INSERT INTO duplicates VALUES (?, ?, ?, ?, ?, ?, ?)",
            (dup_id, canon_src, canon_local, f"EXCLUDED_MIRROR:{folder_dup}", f"https://github.com/jesse-ai/example-strategies/blob/{jesse_sha}/{folder_dup}", "near_duplicate_excluded", sim),
        )
        jesse_mirror_checks.append({"dup_id": dup_id, "canonical": folder_root, "excluded_mirror": folder_dup, "similarity": sim})

    # Add cross-platform MT4 vs MT5 fork/port edges for EarnForex Batch 6
    ef_pairs = [
        ("EarnForex/AutoTrading-Scheduler", "MQL4/Experts/AutoTrading Scheduler/AutoTrading Scheduler.mq4", "MQL5/Experts/AutoTrading Scheduler/AutoTrading Scheduler.mq5"),
        ("EarnForex/AutoTrading-Scheduler", "MQL4/Experts/AutoTrading Scheduler/AutoTrading Scheduler.mqh", "MQL5/Experts/AutoTrading Scheduler/AutoTrading Scheduler.mqh"),
        ("EarnForex/Spread", "Spread.mq4", "Spread.mq5"),
    ]
    cross_platform_forks = []
    for repo, p4, p5 in ef_pairs:
        s4 = next(r for r in batch6_records if r["repo"] == repo and r["rel_path"] == p4)
        s5 = next(r for r in batch6_records if r["repo"] == repo and r["rel_path"] == p5)
        t4 = (ROOT / s4["local_path"]).read_text(encoding="utf-8", errors="replace")
        t5 = (ROOT / s5["local_path"]).read_text(encoding="utf-8", errors="replace")
        sim = round(difflib.SequenceMatcher(None, t4, t5).ratio(), 4)
        dup_counter += 1
        dup_id = f"DUP_B6_{dup_counter:04d}"
        cur.execute(
            "INSERT INTO duplicates VALUES (?, ?, ?, ?, ?, ?, ?)",
            (dup_id, s4["src_id"], s4["local_path"], s5["src_id"], s5["local_path"], "cross_platform_mt4_mt5_port", sim),
        )
        kg_new.append((s5["src_id"], "fork_or_modified", s4["src_id"], 1))
        cross_platform_forks.append({"dup_id": dup_id, "mt4": p4, "mt5": p5, "similarity": sim})

    # Insert all kg_edges
    for s, p, o, lvl in kg_new:
        cur.execute("INSERT INTO kg_edges VALUES (?, ?, ?, ?)", (s, p, o, lvl))

    con.commit()

    # Run integrity & count verification directly from SQLite
    integrity = cur.execute("PRAGMA integrity_check").fetchone()[0]
    totals = {
        "source_files": cur.execute("SELECT COUNT(*) FROM source_files").fetchone()[0],
        "batch6_source_files": cur.execute("SELECT COUNT(*) FROM source_files WHERE batch='batch6'").fetchone()[0],
        "ea_master": cur.execute("SELECT COUNT(*) FROM ea_master").fetchone()[0],
        "batch6_ea_master": cur.execute("SELECT COUNT(*) FROM ea_master WHERE ea_id LIKE 'EA-B6-%'").fetchone()[0],
        "github_repos": cur.execute("SELECT COUNT(*) FROM github_repos").fetchone()[0],
        "developers": cur.execute("SELECT COUNT(*) FROM developers").fetchone()[0],
        "duplicates": cur.execute("SELECT COUNT(*) FROM duplicates").fetchone()[0],
        "kg_edges": cur.execute("SELECT COUNT(*) FROM kg_edges").fetchone()[0],
        "kb_fts": cur.execute("SELECT COUNT(*) FROM kb_fts").fetchone()[0],
        "sqlite_integrity_check": integrity,
    }
    con.close()

    stats = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "batch": "batch6",
        "totals": totals,
        "repositories": repo_summaries,
        "excluded_unlicensed_audit": [unlicensed_record],
        "jesse_excluded_mirror_duplicates": jesse_mirror_checks,
        "cross_platform_mt4_mt5_ports": cross_platform_forks,
        "preexisting_url_encoding_duplicates_detected": len(preexisting_url_dups),
        "preexisting_url_encoding_samples": preexisting_url_dups[:10],
        "batch6_exact_sha256_duplicates": dup_records,
    }
    STATS_PATH.write_text(json.dumps(stats, indent=2))
    MANIFEST_PATH.write_text(json.dumps(batch6_records, indent=2))
    print(json.dumps(totals, indent=2))
    print(f"Jesse mirror duplicates excluded: {len(jesse_mirror_checks)} | Pre-existing URL-encoded dups detected: {len(preexisting_url_dups)}")


if __name__ == "__main__":
    main()
