#!/usr/bin/env python3
"""
EXP-0022 / H24 — Standalone Point-In-Time (PIT) SEC Fundamental Anomalies at Quarterly Horizon (63d).

Pre-registered question (H24):
  Tested standalone at a quarterly (63-trading-day) horizon using strictly lagged, non-restated
  SEC XBRL data (`data/sec/pit_fundamentals.csv` keyed on `available_from = filed`), do accounting
  quality / cashflow signals beat a turnover-matched null net of 5 bp/side costs?

Pre-registered arms (4 mechanisms, Bonferroni bar = 98.75th percentile):
  1. F_NEG_ACCRUALS : -(ttm_ni - ttm_cfo) / assets  (Sloan cash-backed earnings quality)
  2. F_CFO_ASSETS   : ttm_cfo / assets              (operating cashflow profitability)
  3. F_REV_YOY      : rev_yoy                       (fundamental revenue momentum)
  4. F_QUALITY_COMP : equal-weight rank composite(cfo_to_assets, -accruals, -debt_to_assets, net_margin)

Anti-leakage & validation protocol (PITFALLS #1, #7, #11, #12):
  * Causal PIT join: for rebalance close[t], only filings with available_from <= t are visible.
  * Execution lag: rebalance weights decided at close[t] execute at close[t+1] (earn t+2..t+1+63).
  * Costs: 5 bp/side (base) and 10 bp/side (2x stress) on sum(|Δw|).
  * Null: 200 fixed whole-sample ticker permutations (turnover-matched).
  * Split: 70/30 by date (2017-01..2026-11).
  * PASS bar: >=98.75th pct in BOTH IS and OOS at 5 bp/side, positive at 10 bp/side, and Long-Only
    Top Quintile beats Equal-Weight Buy&Hold of the same 62-stock PIT universe in both halves.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "research" / "artifacts" / "pit_fundamentals_exp.json"

COST_BASE = 0.0005
COST_2X = 0.0010
N_NULL = 200
REB_STEP = 63


def cs_rank(df: pd.DataFrame) -> pd.DataFrame:
    return df.rank(axis=1, pct=True) - 0.5


def main() -> None:
    pit = pd.read_csv(ROOT / "data" / "sec" / "pit_fundamentals.csv")
    pit["available_from"] = pd.to_datetime(pit["available_from"])
    pit_syms = sorted(pit["ticker"].unique())

    prices = {}
    for sym in pit_syms:
        p = ROOT / "data" / "stocks" / f"{sym}.csv"
        if not p.exists():
            continue
        df = pd.read_csv(p)
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").drop_duplicates("date")
        col = "adjclose" if "adjclose" in df.columns else "close"
        prices[sym] = pd.Series(pd.to_numeric(df[col], errors="coerce").values, index=df["date"])

    px = pd.DataFrame(prices).sort_index().ffill(limit=3)
    dates = px.index
    syms = px.columns
    ret1 = px.pct_change(fill_method=None)

    fields = ["accruals", "cfo_to_assets", "rev_yoy", "debt_to_assets", "net_margin"]
    panels = {c: pd.DataFrame(np.nan, index=dates, columns=syms) for c in fields}
    for sym, sub in pit.groupby("ticker"):
        if sym not in syms:
            continue
        sub = sub.sort_values("available_from").drop_duplicates("available_from", keep="last").set_index("available_from")
        al = sub[fields].reindex(dates.union(sub.index)).sort_index().ffill().reindex(dates)
        for c in fields:
            panels[c][sym] = al[c]

    scores_map = {
        "F_NEG_ACCRUALS": -panels["accruals"],
        "F_CFO_ASSETS": panels["cfo_to_assets"],
        "F_REV_YOY": panels["rev_yoy"],
        "F_QUALITY_COMP": (
            cs_rank(panels["cfo_to_assets"])
            + cs_rank(-panels["accruals"])
            + cs_rank(-panels["debt_to_assets"])
            + cs_rank(panels["net_margin"])
        ) / 4.0,
    }

    start_pos = 30  # ~Jan 2017 once panel settles
    split_pos = start_pos + int(0.70 * (len(dates) - start_pos))
    reb_indices = list(range(start_pos, len(dates) - 2, REB_STEP))

    def build_w(sc_df: pd.DataFrame, mode: str = "ls") -> pd.DataFrame:
        W = np.zeros((len(dates), len(syms)), dtype=float)
        reb_targets = {}
        for i in reb_indices:
            s = sc_df.iloc[i].values
            valid = np.isfinite(s)
            nv = int(valid.sum())
            w = np.zeros(len(syms), dtype=float)
            if nv >= 20:
                q = max(5, nv // 5)
                top = np.argsort(np.where(valid, s, -np.inf))[-q:]
                bot = np.argsort(np.where(valid, s, np.inf))[:q]
                if mode == "ls":
                    w[top] = 1.0 / q
                    w[bot] = -1.0 / q
                else:
                    w[top] = 1.0 / q
            reb_targets[i + 1] = w  # fill at t+1 close
        cur = np.zeros(len(syms), dtype=float)
        for i in range(len(dates)):
            if i in reb_targets:
                cur = reb_targets[i]
            W[i] = cur
        return pd.DataFrame(W, index=dates, columns=syms)

    def eval_w(w_df: pd.DataFrame, cost: float) -> dict:
        W = w_df.values
        R = np.nan_to_num(ret1.values, nan=0.0)
        g = np.sum(W[:-1] * R[1:], axis=1)
        t = np.sum(np.abs(W[1:] - W[:-1]), axis=1)
        n = g - cost * t

        def _st(ga, na, ta):
            sd = float(np.std(na, ddof=1))
            sh = float(np.mean(na) / sd * np.sqrt(252)) if sd > 0 else 0.0
            sh_g = float(np.mean(ga) / np.std(ga, ddof=1) * np.sqrt(252)) if np.std(ga, ddof=1) > 0 else 0.0
            eq = np.cumprod(1.0 + na)
            yrs = len(na) / 252.0
            cagr = float((eq[-1] ** (1.0 / yrs) - 1.0) * 100.0) if np.all(eq > 0) else -100.0
            mdd = float(((eq / np.maximum.accumulate(eq)) - 1.0).min() * 100.0) if np.all(eq > 0) else -100.0
            return {
                "sharpe_net": round(sh, 3),
                "sharpe_gross": round(sh_g, 3),
                "cagr_net_pct": round(cagr, 2),
                "maxdd_pct": round(mdd, 2),
                "ann_turn": round(float(np.mean(ta) * 252.0), 2),
            }

        return {
            "IS": _st(g[start_pos:split_pos - 1], n[start_pos:split_pos - 1], t[start_pos:split_pos - 1]),
            "OOS": _st(g[split_pos - 1:], n[split_pos - 1:], t[split_pos - 1:]),
        }

    def null_pct(w_df: pd.DataFrame, cost: float, seed: int = 11) -> tuple[float, float]:
        rng = np.random.default_rng(seed)
        W = w_df.values
        R = np.nan_to_num(ret1.values, nan=0.0)
        t = np.sum(np.abs(W[1:] - W[:-1]), axis=1)
        obs = eval_w(w_df, cost)
        sh_is, sh_oos = np.empty(N_NULL), np.empty(N_NULL)
        for k in range(N_NULL):
            Wp = W[:, rng.permutation(len(syms))]
            n = np.sum(Wp[:-1] * R[1:], axis=1) - cost * t
            a, b = n[start_pos:split_pos - 1], n[split_pos - 1:]
            sh_is[k] = float(np.mean(a) / np.std(a, ddof=1) * np.sqrt(252)) if np.std(a, ddof=1) > 0 else 0.0
            sh_oos[k] = float(np.mean(b) / np.std(b, ddof=1) * np.sqrt(252)) if np.std(b, ddof=1) > 0 else 0.0
        return (
            round(float((sh_is < obs["IS"]["sharpe_net"]).mean() * 100.0), 1),
            round(float((sh_oos < obs["OOS"]["sharpe_net"]).mean() * 100.0), 1),
        )

    ew_w = pd.DataFrame(1.0 / len(syms), index=dates, columns=syms)
    ew = eval_w(ew_w, 0.0)
    print(f"PIT Universe: {len(syms)} firms, {len(dates)} days | split {dates[split_pos]:%Y-%m-%d}")
    print(f"PIT62_EW Buy&Hold: IS Sharpe {ew['IS']['sharpe_net']} ({ew['IS']['cagr_net_pct']}%/yr) | "
          f"OOS Sharpe {ew['OOS']['sharpe_net']} ({ew['OOS']['cagr_net_pct']}%/yr)")

    arms_out = {}
    any_pass = False
    for name, sc_df in scores_map.items():
        w_ls = build_w(sc_df, "ls")
        w_lo = build_w(sc_df, "lo")
        ev5 = eval_w(w_ls, COST_BASE)
        ev10 = eval_w(w_ls, COST_2X)
        ev_lo = eval_w(w_lo, COST_BASE)
        p_is, p_oos = null_pct(w_ls, COST_BASE)
        plo_is, plo_oos = null_pct(w_lo, COST_BASE)
        passed = (
            p_is >= 98.75 and p_oos >= 98.75
            and ev5["IS"]["sharpe_net"] > 0 and ev5["OOS"]["sharpe_net"] > 0
            and ev10["IS"]["sharpe_net"] > 0 and ev10["OOS"]["sharpe_net"] > 0
            and ev_lo["IS"]["sharpe_net"] > ew["IS"]["sharpe_net"]
            and ev_lo["OOS"]["sharpe_net"] > ew["OOS"]["sharpe_net"]
        )
        if passed:
            any_pass = True
        arms_out[name] = {
            "ls_5bp": {"IS": ev5["IS"], "OOS": ev5["OOS"], "null_pct_IS": p_is, "null_pct_OOS": p_oos},
            "ls_10bp": {"IS": ev10["IS"], "OOS": ev10["OOS"]},
            "lo_topq_5bp": {"IS": ev_lo["IS"], "OOS": ev_lo["OOS"], "null_pct_IS": plo_is, "null_pct_OOS": plo_oos},
            "pass_bar": passed,
        }
        print(f"  {name:16s} LS 5bp | IS {ev5['IS']['sharpe_net']:+.3f} (pct {p_is:4.1f}) | "
              f"OOS {ev5['OOS']['sharpe_net']:+.3f} (pct {p_oos:4.1f}) | LO OOS {ev_lo['OOS']['sharpe_net']:+.3f} (pct {plo_oos:4.1f}) | PASS={passed}")

    verdict = "PASS" if any_pass else "FAIL"
    OUT_JSON.write_text(json.dumps({
        "exp_id": "EXP-0022",
        "hyp_id": "H24",
        "run_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "universe": f"{len(syms)} US large-cap GAAP firms with PIT SEC data",
        "date_range": f"{dates[start_pos]:%Y-%m-%d}..{dates[-1]:%Y-%m-%d}",
        "is_oos_split": dates[split_pos].strftime("%Y-%m-%d"),
        "ew_benchmark": ew,
        "arms": arms_out,
        "verdict": verdict,
    }, indent=2))
    print(f"\nEXP-0022 verdict: {verdict} -> {OUT_JSON}")


if __name__ == "__main__":
    main()
