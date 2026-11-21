#!/usr/bin/env python3
"""
EXP-0023 / H25 — Crypto 1H Momentum, Reversal, Breakout & BTC-ETH Spread on 9,999 Confirmed OKX Bars.

Pre-registered question (H25):
  Across 9,999 confirmed 1-hour OKX candles (`2025-09-30..2026-11-20`) for BTCUSDT and ETHUSDT, do
  four classic intraday/swing crypto mechanisms beat a turnover-matched circular-shift null after
  real OKX fees and 1-bar execution delay?

Pre-registered arms (4 mechanisms, Bonferroni bar = 98.75th percentile):
  1. CR_REV_4H       : 4h short-term reversal (z-scored over 72h, continuous clipped [-1, 1], pooled BTC+ETH)
  2. CR_MOM_24H      : 24h momentum trend (sign of 24h return, re-evaluated every 4h, pooled BTC+ETH)
  3. CR_BREAK_48H    : 48h Donchian channel breakout (+1 above 48h high, -1 below 48h low, pooled)
  4. CR_PAIR_ETH_BTC : 24h relative spread reversion (long laggard / short leader on 24h diff, rebal 4h)

Costs & execution discipline (PITFALLS #1, #15, #17):
  * Decision from confirmed bars <= t -> execution at t+1 close -> return earned t+2 onward (`pos.shift(2)`).
  * Base cost: 10 bp/side (0.10% OKX VIP0 taker = 20 bp round-turn) + Maker lower bound: 5 bp/side.
  * Null: 200 circular shifts of the executed position series per asset (preserves exact turnover).
  * Split: 70/30 by timestamp; PASS bar requires >=98.75th pct in BOTH IS & OOS at 10 bp/side (and positive at 5 bp).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "research" / "artifacts" / "crypto_1h.json"

COST_TAKER = 0.0010   # 10 bp/side
COST_MAKER = 0.0005   # 5 bp/side
N_NULL = 200
HOURS_PER_YEAR = 24.0 * 365.0


def load_okx(sym: str) -> pd.Series:
    df = pd.read_csv(ROOT / "data" / "collect" / f"okx_{sym}_1h_deep.csv")
    df = df[df["confirm"] == 1].copy()
    df["ts"] = pd.to_datetime(df["ts"])
    df = df.sort_values("ts").drop_duplicates("ts")
    return pd.Series(pd.to_numeric(df["c"], errors="coerce").values, index=df["ts"], name=sym)


def eval_pos(w_exec: pd.DataFrame, ret1: pd.DataFrame, start_i: int, split_i: int, cost: float) -> dict:
    """w_exec[t] was decided at <= t-1 close and takes effect at t close -> earns ret1[t+1]."""
    W = w_exec.values
    R = np.nan_to_num(ret1.values, nan=0.0)
    gross = np.sum(W[:-1] * R[1:], axis=1)
    turn = np.sum(np.abs(W[1:] - W[:-1]), axis=1)
    net = gross - cost * turn

    def _st(g, n, t):
        sd_n = float(np.std(n, ddof=1))
        sd_g = float(np.std(g, ddof=1))
        sh_n = float(np.mean(n) / sd_n * np.sqrt(HOURS_PER_YEAR)) if sd_n > 0 else 0.0
        sh_g = float(np.mean(g) / sd_g * np.sqrt(HOURS_PER_YEAR)) if sd_g > 0 else 0.0
        mt = float(np.mean(t))
        be_bp = float(np.mean(g) / mt * 1e4) if mt > 0 else 0.0
        return {
            "sharpe_net": round(sh_n, 3),
            "sharpe_gross": round(sh_g, 3),
            "ann_turn": round(mt * HOURS_PER_YEAR, 1),
            "breakeven_bp_side": round(be_bp, 2),
        }

    return {
        "IS": _st(gross[start_i:split_i - 1], net[start_i:split_i - 1], turn[start_i:split_i - 1]),
        "OOS": _st(gross[split_i - 1:], net[split_i - 1:], turn[split_i - 1:]),
    }


def circ_null(w_exec: pd.DataFrame, ret1: pd.DataFrame, start_i: int, split_i: int, cost: float, seed: int = 19) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    W = w_exec.values
    R = np.nan_to_num(ret1.values, nan=0.0)
    obs = eval_pos(w_exec, ret1, start_i, split_i, cost)
    sh_is, sh_oos = np.empty(N_NULL), np.empty(N_NULL)
    n_rows = W.shape[0]
    for k in range(N_NULL):
        shift = int(rng.integers(48, n_rows - 48))
        Wp = np.roll(W, shift, axis=0)
        turn = np.sum(np.abs(Wp[1:] - Wp[:-1]), axis=1)
        net = np.sum(Wp[:-1] * R[1:], axis=1) - cost * turn
        a, b = net[start_i:split_i - 1], net[split_i - 1:]
        sh_is[k] = float(np.mean(a) / np.std(a, ddof=1) * np.sqrt(HOURS_PER_YEAR)) if np.std(a, ddof=1) > 0 else 0.0
        sh_oos[k] = float(np.mean(b) / np.std(b, ddof=1) * np.sqrt(HOURS_PER_YEAR)) if np.std(b, ddof=1) > 0 else 0.0
    return (
        round(float((sh_is < obs["IS"]["sharpe_net"]).mean() * 100.0), 1),
        round(float((sh_oos < obs["OOS"]["sharpe_net"]).mean() * 100.0), 1),
    )


def main() -> None:
    btc = load_okx("BTCUSDT")
    eth = load_okx("ETHUSDT")
    px = pd.concat([btc, eth], axis=1).dropna()
    ret1 = px.pct_change(fill_method=None)
    dates = px.index

    start_i = 100
    split_i = start_i + int(0.70 * (len(dates) - start_i))
    print(f"OKX 1H panel: {len(dates)} bars | {dates[start_i]}..{dates[-1]} | split {dates[split_i]}")

    # Build raw decision signals at bar close t (later shifted +1 so execution happens at t+1 close)
    r4 = px.pct_change(4, fill_method=None)
    vol72 = ret1.rolling(72).std() * 2.0
    sig_rev4 = -(r4 / vol72.replace(0, np.nan)).clip(-1, 1).fillna(0.0) * 0.5
    # Only update every 4h to avoid paying spread hourly
    mask4 = pd.Series(np.arange(len(dates)) % 4 == 0, index=dates)
    sig_rev4_step = sig_rev4.where(mask4).ffill().fillna(0.0)

    r24 = px.pct_change(24, fill_method=None)
    sig_mom24 = np.sign(r24).where(mask4).ffill().fillna(0.0) * 0.5

    hi48 = px.rolling(48).max().shift(1)
    lo48 = px.rolling(48).min().shift(1)
    br = pd.DataFrame(np.nan, index=dates, columns=px.columns)
    br[px > hi48] = 0.5
    br[px < lo48] = -0.5
    sig_break48 = br.ffill().fillna(0.0)

    diff24 = (px["ETHUSDT"].pct_change(24) - px["BTCUSDT"].pct_change(24)).fillna(0.0)
    z_diff = (diff24 / diff24.rolling(168).std().replace(0, np.nan)).clip(-1, 1).fillna(0.0)
    sig_pair = pd.DataFrame({
        "BTCUSDT": z_diff * 0.5,
        "ETHUSDT": -z_diff * 0.5,
    }, index=dates).where(mask4).ffill().fillna(0.0)

    arms = {
        "CR_REV_4H": sig_rev4_step,
        "CR_MOM_24H": sig_mom24,
        "CR_BREAK_48H": sig_break48,
        "CR_PAIR_ETH_BTC": sig_pair,
    }

    bh = eval_pos(pd.DataFrame(0.5, index=dates, columns=px.columns), ret1, start_i, split_i, 0.0)
    print(f"50/50 BTC+ETH Buy&Hold: IS Sharpe {bh['IS']['sharpe_net']:+.3f} | OOS Sharpe {bh['OOS']['sharpe_net']:+.3f}")

    res = {}
    any_pass = False
    for name, raw_sig in arms.items():
        w_exec = raw_sig.shift(1).fillna(0.0)  # 1-bar execution lag
        ev_taker = eval_pos(w_exec, ret1, start_i, split_i, COST_TAKER)
        ev_maker = eval_pos(w_exec, ret1, start_i, split_i, COST_MAKER)
        p_is, p_oos = circ_null(w_exec, ret1, start_i, split_i, COST_TAKER)
        passed = (
            p_is >= 98.75 and p_oos >= 98.75
            and ev_taker["IS"]["sharpe_net"] > 0 and ev_taker["OOS"]["sharpe_net"] > 0
            and ev_maker["IS"]["sharpe_net"] > 0 and ev_maker["OOS"]["sharpe_net"] > 0
        )
        if passed:
            any_pass = True
        res[name] = {
            "taker_10bp": {"IS": ev_taker["IS"], "OOS": ev_taker["OOS"], "null_pct_IS": p_is, "null_pct_OOS": p_oos},
            "maker_5bp": {"IS": ev_maker["IS"], "OOS": ev_maker["OOS"]},
            "pass_bar": passed,
        }
        print(f"  {name:16s} 10bp | IS {ev_taker['IS']['sharpe_net']:+.3f} (gross {ev_taker['IS']['sharpe_gross']:+.3f}, "
              f"pct {p_is:4.1f}, BE {ev_taker['IS']['breakeven_bp_side']:+.2f}bp) | "
              f"OOS {ev_taker['OOS']['sharpe_net']:+.3f} (gross {ev_taker['OOS']['sharpe_gross']:+.3f}, "
              f"pct {p_oos:4.1f}, BE {ev_taker['OOS']['breakeven_bp_side']:+.2f}bp) | "
              f"5bp OOS={ev_maker['OOS']['sharpe_net']:+.3f} | PASS={passed}")

    verdict = "PASS" if any_pass else "FAIL"
    OUT_JSON.write_text(json.dumps({
        "exp_id": "EXP-0023",
        "hyp_id": "H25",
        "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "universe": "OKX BTCUSDT + ETHUSDT 1H confirmed bars",
        "bars": len(dates),
        "date_range": f"{dates[start_i]}..{dates[-1]}",
        "is_oos_split": str(dates[split_i]),
        "bh_benchmark": bh,
        "arms": res,
        "verdict": verdict,
    }, indent=2))
    print(f"\nEXP-0023 verdict: {verdict} -> {OUT_JSON}")


if __name__ == "__main__":
    main()
