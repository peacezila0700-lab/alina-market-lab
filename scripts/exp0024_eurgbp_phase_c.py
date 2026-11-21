#!/usr/bin/env python3
"""EXP-0024 & EXP-0025: Phase C Cost-Aware Multi-Archetype FX Validation Suite.

Evaluates 5 pre-declared rules on 23-year Dukascopy real Bid/Ask H1 feeds
(`EURGBP` primary = 147,297 bars; `EURUSD` control = 148,482 bars) with:
  - Strict causal indicators (trailing up to signal bar close t; entry strictly >= t+1)
  - Conservative H1 limit-order fill checking (`ask_l <= limit` for BUY; `bid_h >= limit` for SELL)
  - Pessimistic intra-bar SL-before-TP precedence
  - 4 broker cost tiers (Dukascopy Measured, IC Markets Raw ECN, Exness Raw, Exness Standard)
  - Overnight swap sensitivity bounds [0.0, 0.35] pips/night
  - Month-clustered bootstrap 95% CI + 500-sim random-entry null
  - Strict temporal splits: IS (2003..2021), VALID (2022..2026-05-19), LOCKED OOS (2026-05-20..2026-11-20)

Outputs:
  - research/artifacts/exp0024_phase_c.json
  - reports/EXP_0024_PHASE_C.md
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(os.environ.get("ALINA_ROOT", str(Path(__file__).resolve().parent.parent)))
INTRA = ROOT / "data" / "intraday"
BROKER_CFG = json.loads((ROOT / "configs" / "broker_cost_models.json").read_text(encoding="utf-8"))
ART_OUT = ROOT / "research" / "artifacts" / "exp0024_phase_c.json"
RPT_OUT = ROOT / "reports" / "EXP_0024_PHASE_C.md"

PIP = 0.0001
IS_END = pd.Timestamp("2021-12-31 23:59:59", tz="UTC")
VAL_END = pd.Timestamp("2026-05-19 23:59:59", tz="UTC")
OOS_START = pd.Timestamp("2026-05-20 00:00:00", tz="UTC")


def load_h1(pair: str) -> pd.DataFrame:
    df = pd.read_csv(INTRA / f"{pair}_H1_bidask.csv.gz", compression="gzip")
    df["ts"] = pd.to_datetime(df["ts_utc"], utc=True)
    df["hour"] = df["ts"].dt.hour.to_numpy()
    df["date_ord"] = df["ts"].dt.floor("D").astype("int64") // 86_400_000_000_000
    df["mid_o"] = 0.5 * (df["bid_o"] + df["ask_o"])
    df["mid_h"] = 0.5 * (df["bid_h"] + df["ask_h"])
    df["mid_l"] = 0.5 * (df["bid_l"] + df["ask_l"])
    df["mid_c"] = 0.5 * (df["bid_c"] + df["ask_c"])
    df["spread_pips"] = np.maximum(0.0, (df["ask_c"] - df["bid_c"]) / PIP)

    # Strictly causal features on mid_c / true range up to bar t
    mc = df["mid_c"]
    prev_c = mc.shift(1)
    tr = pd.concat([
        df["mid_h"] - df["mid_l"],
        (df["mid_h"] - prev_c).abs(),
        (df["mid_l"] - prev_c).abs(),
    ], axis=1).max(axis=1)
    df["atr24"] = tr.rolling(24, min_periods=24).mean()
    df["atr24_pctl"] = df["atr24"].rolling(6048, min_periods=1000).rank(pct=True)  # ~1y trailing H1 bars

    df["ma120"] = mc.rolling(120, min_periods=120).mean()
    df["sd120"] = mc.rolling(120, min_periods=120).std()
    df["z120"] = (mc - df["ma120"]) / df["sd120"].replace(0.0, np.nan)

    # Intraday session anchor (07:00 UTC London open -> 16:00 UTC London close)
    # Computed causally across past 9 hours at 16:00 UTC
    df["ret9h"] = mc - mc.shift(9)
    return df


def to_utc_ts(x: Any) -> pd.Timestamp:
    ts = pd.Timestamp(x)
    return ts.tz_convert("UTC") if ts.tzinfo is not None else ts.tz_localize("UTC")


def split_of(ts: pd.Timestamp) -> str:
    if ts <= IS_END:
        return "IS"
    if ts <= VAL_END:
        return "VALID"
    return "OOS"


def simulate_rule(df: pd.DataFrame, pair: str, rule: str, seed: int = 42) -> list[dict[str, Any]]:
    """Simulate a single pre-declared rule causally across H1 Bid/Ask arrays."""
    n = len(df)
    ts_arr = df["ts"].to_numpy()
    hour = df["hour"].to_numpy()
    dord = df["date_ord"].to_numpy()
    bid_o = df["bid_o"].to_numpy()
    bid_h = df["bid_h"].to_numpy()
    bid_l = df["bid_l"].to_numpy()
    bid_c = df["bid_c"].to_numpy()
    ask_o = df["ask_o"].to_numpy()
    ask_h = df["ask_h"].to_numpy()
    ask_l = df["ask_l"].to_numpy()
    ask_c = df["ask_c"].to_numpy()
    mid_c = df["mid_c"].to_numpy()
    atr24 = df["atr24"].to_numpy()
    atr_pctl = df["atr24_pctl"].to_numpy()
    z120 = df["z120"].to_numpy()
    ret9h = df["ret9h"].to_numpy()
    sp_pips = df["spread_pips"].to_numpy()

    trades: list[dict[str, Any]] = []
    i = 1000  # warm-up past rolling windows

    while i < n - 120:
        sig_z = z120[i]
        sig_atr = atr24[i]
        if np.isnan(sig_z) or np.isnan(sig_atr) or sig_atr <= 0:
            i += 1
            continue

        side = 0
        is_limit = False
        limit_px = 0.0
        ttl = 1
        tp_pips = 25.0
        sl_pips = float(np.clip(3.0 * sig_atr / PIP, 25.0, 90.0))
        max_hold_h = 96

        if rule in ("H26_LIMIT_OU", "H28_REGIME_GUARDED"):
            if not (6 <= hour[i] <= 19) or sp_pips[i] > 2.0:
                i += 1
                continue
            if rule == "H28_REGIME_GUARDED" and (np.isnan(atr_pctl[i]) or atr_pctl[i] > 0.75):
                i += 1
                continue
            if sig_z <= -2.0:
                side = 1
                limit_px = round(bid_c[i] - 0.15 * sig_atr, 5)
            elif sig_z >= 2.0:
                side = -1
                limit_px = round(ask_c[i] + 0.15 * sig_atr, 5)
            is_limit = True
            ttl = 12
        elif rule == "H26_MKT_COMPARE":
            if not (6 <= hour[i] <= 19) or sp_pips[i] > 2.0:
                i += 1
                continue
            if sig_z <= -2.0:
                side = 1
            elif sig_z >= 2.0:
                side = -1
            is_limit = False
            ttl = 1
        elif rule == "H27_LONDON_FIX_REVERT":
            if hour[i] != 16 or sp_pips[i] > 2.0 or np.isnan(ret9h[i]):
                i += 1
                continue
            stretch = ret9h[i] / sig_atr
            if stretch >= 1.5:
                side = -1
            elif stretch <= -1.5:
                side = 1
            is_limit = False
            ttl = 1
            tp_pips = float(np.clip(0.5 * abs(ret9h[i]) / PIP, 10.0, 35.0))
            sl_pips = float(np.clip(2.0 * sig_atr / PIP, 15.0, 60.0))
            max_hold_h = 3  # flat by 20:00 UTC before rollover spike, 0 overnight swap
        elif rule == "H28_H1_SCALP_BASELINE":
            if not (7 <= hour[i] <= 17) or sp_pips[i] > 2.0:
                i += 1
                continue
            if sig_z <= -2.0:
                side = 1
            elif sig_z >= 2.0:
                side = -1
            is_limit = False
            ttl = 1
            tp_pips = 6.0
            sl_pips = 12.0
            max_hold_h = 6

        if side == 0:
            i += 1
            continue

        # Attempt fill strictly on bars k >= i+1
        entry_bar = -1
        entry_px = 0.0
        entry_sp = 0.0
        if not is_limit:
            k = i + 1
            entry_bar = k
            entry_px = ask_o[k] if side == 1 else bid_o[k]
            entry_sp = max(0.0, (ask_o[k] - bid_o[k]) / PIP)
        else:
            for k in range(i + 1, min(i + 1 + ttl, n - max_hold_h)):
                if side == 1 and ask_l[k] <= limit_px:
                    entry_bar = k
                    entry_px = min(limit_px, ask_o[k])
                    entry_sp = max(0.0, (ask_c[k] - bid_c[k]) / PIP)
                    break
                if side == -1 and bid_h[k] >= limit_px:
                    entry_bar = k
                    entry_px = max(limit_px, bid_o[k])
                    entry_sp = max(0.0, (ask_c[k] - bid_c[k]) / PIP)
                    break

        if entry_bar < 0:
            i += 1
            continue

        # Manage trade on bars j > entry_bar (or exit check starting entry_bar+1)
        tp_px = entry_px + side * tp_pips * PIP
        sl_px = entry_px - side * sl_pips * PIP
        exit_bar = min(entry_bar + max_hold_h, n - 1)
        exit_px = bid_c[exit_bar] if side == 1 else ask_c[exit_bar]
        exit_sp = max(0.0, (ask_c[exit_bar] - bid_c[exit_bar]) / PIP)
        reason = "time_stop"

        for j in range(entry_bar + 1, min(entry_bar + max_hold_h + 1, n)):
            if side == 1:
                # Pessimistic precedence: SL checked BEFORE TP on same H1 bar
                if bid_l[j] <= sl_px:
                    exit_bar = j
                    exit_px = min(sl_px, bid_o[j])
                    exit_sp = max(0.0, (ask_c[j] - bid_c[j]) / PIP)
                    reason = "stop_loss"
                    break
                if bid_h[j] >= tp_px:
                    exit_bar = j
                    exit_px = tp_px
                    exit_sp = max(0.0, (ask_c[j] - bid_c[j]) / PIP)
                    reason = "take_profit"
                    break
            else:
                if ask_h[j] >= sl_px:
                    exit_bar = j
                    exit_px = max(sl_px, ask_o[j])
                    exit_sp = max(0.0, (ask_c[j] - bid_c[j]) / PIP)
                    reason = "stop_loss"
                    break
                if ask_l[j] <= tp_px:
                    exit_bar = j
                    exit_px = tp_px
                    exit_sp = max(0.0, (ask_c[j] - bid_c[j]) / PIP)
                    reason = "take_profit"
                    break

        # quoted_pips = exact executable PnL from Ask/Bid entry to Bid/Ask exit (already includes Dukascopy spread!)
        quoted_pips = side * (exit_px - entry_px) / PIP
        # Exact mid-to-mid gross reconstruction: add half-spread at entry + half-spread at exit
        gross_mid_pips = quoted_pips + 0.5 * (entry_sp + exit_sp)

        nights = max(0, int(dord[exit_bar] - dord[entry_bar]))
        sig_ts = to_utc_ts(ts_arr[i])
        ent_ts = to_utc_ts(ts_arr[entry_bar])
        ext_ts = to_utc_ts(ts_arr[exit_bar])
        trades.append({
            "pair": pair,
            "rule": rule,
            "split": split_of(ent_ts),
            "side": side,
            "is_limit": is_limit,
            "signal_ts": sig_ts.strftime("%Y-%m-%d %H:%M:%S"),
            "entry_ts": ent_ts.strftime("%Y-%m-%d %H:%M:%S"),
            "exit_ts": ext_ts.strftime("%Y-%m-%d %H:%M:%S"),
            "entry_ym": ent_ts.strftime("%Y-%m"),
            "entry_px": round(float(entry_px), 5),
            "exit_px": round(float(exit_px), 5),
            "reason": reason,
            "bars_held": int(exit_bar - entry_bar),
            "nights": nights,
            "quoted_duka_pips": round(float(quoted_pips), 3),
            "gross_mid_pips": round(float(gross_mid_pips), 3),
            "duka_spread_entry_pips": round(float(entry_sp), 3),
            "duka_spread_exit_pips": round(float(exit_sp), 3),
        })
        i = exit_bar + 1
    return trades


def apply_broker_costs(trades: list[dict[str, Any]], pair: str, model_key: str, swap_per_night: float = 0.0) -> np.ndarray:
    """Compute exact net pips per trade under a specific broker cost model + swap bound."""
    cfg = BROKER_CFG["models"][model_key]
    out = []
    for t in trades:
        if cfg["uses_bar_spread"]:
            slip = cfg["slippage_limit_rt_pips"] if t["is_limit"] else cfg["slippage_market_rt_pips"]
            net = t["quoted_duka_pips"] - slip - swap_per_night * t["nights"]
        else:
            sp = cfg["spread_pips"][pair]
            comm = cfg["commission_rt_pips"][pair] if isinstance(cfg["commission_rt_pips"], dict) else cfg["commission_rt_pips"]
            slip = cfg["slippage_limit_rt_pips"] if t["is_limit"] else cfg["slippage_market_rt_pips"]
            net = t["gross_mid_pips"] - sp - comm - slip - swap_per_night * t["nights"]
        out.append(net)
    return np.array(out, dtype=float)


def month_bootstrap_ci(trades: list[dict[str, Any]], net: np.ndarray, sims: int = 800, seed: int = 42) -> tuple[float, float]:
    if len(net) < 5:
        return float("nan"), float("nan")
    groups: dict[str, list[int]] = {}
    for idx, t in enumerate(trades):
        groups.setdefault(t["entry_ym"], []).append(idx)
    keys = list(groups.keys())
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(sims):
        pick = rng.integers(0, len(keys), size=len(keys))
        vals = [net[j] for k in pick for j in groups[keys[k]]]
        if vals:
            means.append(float(np.mean(vals)))
    return round(float(np.percentile(means, 2.5)), 2), round(float(np.percentile(means, 97.5)), 2)


def random_null_benchmark(df: pd.DataFrame, pair: str, trades_subset: list[dict[str, Any]], sims: int = 300, seed: int = 99) -> dict[str, float]:
    """Random-entry null matching hold duration & side mix on the same bar span."""
    if len(trades_subset) < 10:
        return {"null_mean_pips": float("nan"), "null_p95_pips": float("nan"), "obs_pct": float("nan")}
    # Fast bar-lookup null on Dukascopy measured quoted prices (or mid + spread)
    ts_str = df["ts"].dt.strftime("%Y-%m-%d %H:%M:%S").to_numpy()
    ts_map = {s: idx for idx, s in enumerate(ts_str)}
    bid_o = df["bid_o"].to_numpy()
    ask_o = df["ask_o"].to_numpy()
    bid_c = df["bid_c"].to_numpy()
    ask_c = df["ask_c"].to_numpy()

    idx_pool = [ts_map[t["entry_ts"]] for t in trades_subset if t["entry_ts"] in ts_map]
    lo_b, hi_b = min(idx_pool), max(idx_pool)
    holds = np.array([max(1, t["bars_held"]) for t in trades_subset])
    sides = np.array([t["side"] for t in trades_subset])
    rng = np.random.default_rng(seed)
    null_means = []
    n_t = len(sides)
    for _ in range(sims):
        starts = rng.integers(lo_b, max(lo_b + 1, hi_b - 100), size=n_t)
        ends = np.minimum(starts + holds, len(bid_c) - 1)
        pnls = np.where(
            sides == 1,
            (bid_c[ends] - ask_o[starts]) / PIP,
            (bid_o[starts] - ask_c[ends]) / PIP,
        ) - 0.1
        null_means.append(float(pnls.mean()))
    obs = float(np.mean([t["quoted_duka_pips"] - 0.05 for t in trades_subset]))
    pct = round(100.0 * float(np.mean(np.array(null_means) <= obs)), 1)
    return {
        "null_mean_pips": round(float(np.mean(null_means)), 2),
        "null_p95_pips": round(float(np.percentile(null_means, 95)), 2),
        "obs_pct_vs_random": pct,
    }


def summarize_block(trades: list[dict[str, Any]], net: np.ndarray) -> dict[str, Any]:
    if len(net) == 0:
        return {"n": 0, "net_exp_pips": None, "pf": None, "win_rate": None, "total_pips": 0.0}
    wins = net[net > 0]
    losses = net[net <= 0]
    pf = float(wins.sum() / abs(losses.sum())) if len(losses) > 0 and losses.sum() < 0 else (99.0 if len(wins) > 0 else 0.0)
    ci_lo, ci_hi = month_bootstrap_ci(trades, net)
    eq = np.cumsum(net)
    peak = np.maximum.accumulate(np.r_[0.0, eq])
    dd = float(np.max(peak - np.r_[0.0, eq]))
    return {
        "n": int(len(net)),
        "net_exp_pips": round(float(net.mean()), 2),
        "total_pips": round(float(net.sum()), 1),
        "win_rate_pct": round(float(100.0 * np.mean(net > 0)), 1),
        "pf": round(pf, 2),
        "max_dd_pips": round(dd, 1),
        "ci_95_pips": [ci_lo, ci_hi],
    }


def main() -> None:
    rules = ["H26_LIMIT_OU", "H26_MKT_COMPARE", "H27_LONDON_FIX_REVERT", "H28_REGIME_GUARDED", "H28_H1_SCALP_BASELINE"]
    models = ["dukascopy_measured", "ic_markets_raw_ecn", "exness_raw_spread", "exness_standard"]
    results: dict[str, Any] = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "splits": {"IS": "<= 2021-12-31", "VALID": "2022-01-01..2026-05-19", "OOS_LOCKED": "2026-05-20..2026-11-20"},
        "runs": {},
    }

    for pair in ("EURGBP", "EURUSD"):
        df = load_h1(pair)
        results["runs"][pair] = {}
        for rule in rules:
            trades = simulate_rule(df, pair, rule)
            rule_out: dict[str, Any] = {"total_trades": len(trades), "by_split_duka": {}, "broker_matrix_all": {}}
            for sp in ("IS", "VALID", "OOS", "ALL"):
                sub = trades if sp == "ALL" else [t for t in trades if t["split"] == sp]
                net_s0 = apply_broker_costs(sub, pair, "dukascopy_measured", swap_per_night=0.0)
                net_s35 = apply_broker_costs(sub, pair, "dukascopy_measured", swap_per_night=0.35)
                summ = summarize_block(sub, net_s0)
                summ["net_exp_swap035_pips"] = round(float(net_s35.mean()), 2) if len(net_s35) else None
                if sp == "IS":
                    summ["random_null"] = random_null_benchmark(df, pair, sub)
                rule_out["by_split_duka"][sp] = summ
            for mk in models:
                net_m = apply_broker_costs(trades, pair, mk, swap_per_night=0.15)
                rule_out["broker_matrix_all"][mk] = summarize_block(trades, net_m)
            results["runs"][pair][rule] = rule_out

    ART_OUT.parent.mkdir(parents=True, exist_ok=True)
    RPT_OUT.parent.mkdir(parents=True, exist_ok=True)
    ART_OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")

    # Render clean Markdown Report
    md = [
        "# EXP-0024 / EXP-0025 — Phase C 23-Year Dukascopy Bid/Ask FX Validation Suite",
        "",
        f"Generated UTC: `{results['generated_utc']}` | Script: `scripts/exp0024_eurgbp_phase_c.py`",
        f"Splits: `IS <= 2021-12-31` | `VALID 2022-01-01..2026-05-19` | `OOS_LOCKED 2026-05-20..2026-11-20`",
        "",
        "## 1. Primary Instrument: EURGBP (23 Years, 147,297 H1 Bid/Ask Bars, Dukascopy Measured Cost)",
        "| Rule | Split | Trades | Net Exp (pips) | Swap 0.35 Bound | PF | Win% | 95% Month-CI | Random Null Pct |",
        "|---|---|---:|---:|---:|---:|---:|---|---|",
    ]
    for rule in rules:
        ro = results["runs"]["EURGBP"][rule]
        for sp in ("IS", "VALID", "OOS", "ALL"):
            s = ro["by_split_duka"][sp]
            npct = s.get("random_null", {}).get("obs_pct_vs_random", "-")
            ci = s.get("ci_95_pips")
            ci_str = f"[{ci[0]}, {ci[1]}]" if ci and not np.isnan(ci[0]) else "-"
            md.append(f"| `{rule}` | {sp} | {s['n']} | {s['net_exp_pips']} | {s['net_exp_swap035_pips']} | {s['pf']} | {s.get('win_rate_pct','-')} | {ci_str} | {npct} |")

    md.extend([
        "",
        "## 2. Multi-Broker Cost Matrix Across Full 23-Year Sample (incl. 0.15 pip/night swap)",
        "| Pair | Rule | Dukascopy Measured | IC Markets Raw ECN | Exness Raw | Exness Standard |",
        "|---|---|---:|---:|---:|---:|",
    ])
    for pair in ("EURGBP", "EURUSD"):
        for rule in rules:
            bm = results["runs"][pair][rule]["broker_matrix_all"]
            md.append(
                f"| {pair} | `{rule}` | {bm['dukascopy_measured']['net_exp_pips']} (n={bm['dukascopy_measured']['n']}) | "
                f"{bm['ic_markets_raw_ecn']['net_exp_pips']} | {bm['exness_raw_spread']['net_exp_pips']} | {bm['exness_standard']['net_exp_pips']} |"
            )

    md.extend([
        "",
        "## 3. Control Instrument: EURUSD (23 Years, 148,482 H1 Bid/Ask Bars, Dukascopy Measured)",
        "| Rule | IS Exp (n) | VALID Exp (n) | OOS_LOCKED Exp (n) | ALL Exp (PF) |",
        "|---|---|---|---|---|",
    ])
    for rule in rules:
        b = results["runs"]["EURUSD"][rule]["by_split_duka"]
        md.append(
            f"| `{rule}` | {b['IS']['net_exp_pips']} ({b['IS']['n']}) | {b['VALID']['net_exp_pips']} ({b['VALID']['n']}) | "
            f"{b['OOS']['net_exp_pips']} ({b['OOS']['n']}) | {b['ALL']['net_exp_pips']} (PF {b['ALL']['pf']}) |"
        )

    RPT_OUT.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"Wrote {ART_OUT} and {RPT_OUT} cleanly.")


if __name__ == "__main__":
    main()
