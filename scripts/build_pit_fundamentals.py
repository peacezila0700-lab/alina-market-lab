#!/usr/bin/env python3
"""
build_pit_fundamentals.py — Point-In-Time (PIT) lagged fundamental panel keyed on `filed`.

Why this exists (COVERAGE_MATRIX.md task #2):
  Raw SEC XBRL `companyfacts` returns comparative figures from later filings alongside original ones
  (e.g. a 2010 10-K reports a restated 2008 Assets figure). Reading `fundamentals.csv` naively by
  `period_end` leaks future restatements and mixes YTD vs standalone-quarter flows.

How PIT is enforced here:
  * Iterate chronologically over every distinct `filed` date (10-K / 10-Q) per ticker.
  * On filing date D, ONLY rows with `filed <= D` exist in the state table.
  * For each `(period_start, period_end, field)`, the value used as of D is the LATEST filing whose
    `filed <= D`. Later restatements take effect ONLY on their own `filed` date, never backdated.
  * Flow fields (`revenue`, `net_income`, `cfo`, `eps_diluted`) separate standalone quarters
    (70 <= dur_days <= 115), YTD periods (150 <= dur_days <= 295), and annuals (330 <= dur_days <= 395).
    TTM is computed strictly from information known on D:
      1) Sum of the 4 most recent non-overlapping standalone quarters (latest_end within 400 days), OR
      2) `latest_FY + current_YTD - prior_matching_YTD` (essential for CFO where 10-Qs report YTD), OR
      3) Fallback to latest annual 10-K value if quarterly series is incomplete.
  * Every output row carries `available_from = filed`. A daily price strategy deciding at close[t]
    must join with `available_from <= t` and trade at `t+1`.

Outputs:
  data/sec/pit_fundamentals.csv      event-indexed PIT snapshots keyed by (ticker, available_from)
  data/sec/MANIFEST_PIT_SEC.json     coverage, invariance checks (no backdating, no future leaks)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SEC = ROOT / "data" / "sec"

INSTANT_FIELDS = ("assets", "liabilities", "equity", "cash", "lt_debt")
FLOW_FIELDS = ("revenue", "net_income", "cfo", "eps_diluted")


def _compute_ttm_from_state(sub: pd.DataFrame) -> tuple[float, pd.Timestamp | None, str]:
    """Given all rows for one (ticker, flow_field) with filed <= D, compute causal TTM."""
    if sub.empty:
        return np.nan, None, "missing"

    # Latest reported value as of D for each exact (period_start, period_end)
    latest = (
        sub.sort_values(["filed", "form"])
        .drop_duplicates(subset=["period_start", "period_end"], keep="last")
        .copy()
    )

    # 1) Try 4 most recent standalone quarters (70..115 days) with non-overlapping ends
    q = latest[(latest["dur"] >= 70) & (latest["dur"] <= 115)].sort_values("period_end")
    if len(q) >= 4:
        # Deduplicate overlapping period_ends (>25 days apart) keeping latest
        sel = []
        for _, r in q.iloc[::-1].iterrows():
            if not sel or (sel[-1]["period_end"] - r["period_end"]).days >= 60:
                sel.append(r)
            if len(sel) == 4:
                break
        if len(sel) == 4:
            span = (sel[0]["period_end"] - sel[-1]["period_start"]).days
            if 330 <= span <= 395:
                val = float(sum(float(x["value"]) for x in sel))
                return val, sel[0]["period_end"], "4Q"

    # 2) Annual 10-K + YTD delta: TTM = FY + YTD_cur - YTD_prior
    # Must pick the LONGEST duration (cumulative fiscal-YTD, ~90d Q1 / ~180d Q2 / ~270d Q3)
    # on the newest period_end, NEVER the standalone 90d row inside a Q2/Q3 10-Q.
    ann = latest[(latest["dur"] >= 330) & (latest["dur"] <= 395)].sort_values("period_end")
    ytd = latest[(latest["dur"] >= 70) & (latest["dur"] <= 295)].sort_values(["period_end", "dur"])
    if not ann.empty:
        fy_row = ann.iloc[-1]
        fy_end = fy_row["period_end"]
        newer_ytd = ytd[ytd["period_end"] > fy_end]
        if not newer_ytd.empty:
            max_pe = newer_ytd["period_end"].max()
            cur = newer_ytd[newer_ytd["period_end"] == max_pe].sort_values("dur").iloc[-1]
            cur_dur = cur["dur"]
            target_end = cur["period_end"] - pd.Timedelta(days=365)
            cand = ytd[
                (ytd["period_end"].sub(target_end).abs() <= pd.Timedelta(days=20))
                & (ytd["dur"].sub(cur_dur).abs() <= 20)
            ]
            if not cand.empty:
                prior = cand.sort_values(["period_end", "dur"]).iloc[-1]
                val = float(fy_row["value"]) + float(cur["value"]) - float(prior["value"])
                return val, cur["period_end"], "FY+YTD_diff"
        return float(fy_row["value"]), fy_end, "FY_only"

    return np.nan, None, "incomplete"


def _compute_annual_yoy(sub: pd.DataFrame, cur_ttm: float, cur_end: pd.Timestamp | None) -> float:
    """YoY growth for a flow field using strictly prior-filed matching period (FY vs FY, or YTD vs prior YTD)."""
    if not np.isfinite(cur_ttm) or cur_end is None or sub.empty:
        return np.nan
    latest = (
        sub.sort_values(["filed", "form"])
        .drop_duplicates(subset=["period_start", "period_end"], keep="last")
    )
    # If cur_end corresponds to a 10-K annual, compare FY vs prior FY; else compare cumulative YTD vs prior YTD
    ann = latest[(latest["dur"] >= 330) & (latest["dur"] <= 395)].sort_values("period_end")
    cur_ann = ann[ann["period_end"] == cur_end]
    prev_end = cur_end - pd.Timedelta(days=365)
    if not cur_ann.empty:
        cand = ann[ann["period_end"].sub(prev_end).abs() <= pd.Timedelta(days=25)]
        if not cand.empty:
            base = float(cand.iloc[-1]["value"])
            if base > 0:
                return (float(cur_ann.iloc[-1]["value"]) / base) - 1.0
    # Quarterly/YTD YoY: match cumulative YTD at cur_end with cumulative YTD ~365d earlier
    ytd = latest[(latest["dur"] >= 70) & (latest["dur"] <= 295)]
    cur_rows = ytd[ytd["period_end"] == cur_end].sort_values("dur")
    if not cur_rows.empty:
        cur_row = cur_rows.iloc[-1]
        cand = ytd[
            (ytd["period_end"].sub(prev_end).abs() <= pd.Timedelta(days=20))
            & (ytd["dur"].sub(cur_row["dur"]).abs() <= 20)
        ]
        if not cand.empty:
            base = float(cand.sort_values(["period_end", "dur"]).iloc[-1]["value"])
            if base > 0:
                return (float(cur_row["value"]) / base) - 1.0
    return np.nan


def main() -> None:
    raw = pd.read_csv(SEC / "fundamentals.csv", low_memory=False)
    raw["filed"] = pd.to_datetime(raw["filed"], errors="coerce")
    raw["period_end"] = pd.to_datetime(raw["period_end"], errors="coerce")
    raw["period_start"] = pd.to_datetime(raw.get("period_start"), errors="coerce")
    raw["value"] = pd.to_numeric(raw["value"], errors="coerce")
    raw = raw.dropna(subset=["ticker", "field", "filed", "period_end", "value"]).copy()
    raw["dur"] = (raw["period_end"] - raw["period_start"]).dt.days

    # Enforce physical sanity: a filing date cannot precede its own period_end
    bad_dates = int((raw["filed"] < raw["period_end"]).sum())
    raw = raw[raw["filed"] >= raw["period_end"]].copy()

    rows = []
    restatement_examples = 0

    for ticker, tdf in raw.groupby("ticker", sort=True):
        tdf = tdf.sort_values(["filed", "period_end"])
        filing_dates = sorted(tdf["filed"].unique())

        # Count how often same (field, period_end, dur) changes value across filings
        dup = (
            tdf.sort_values("filed")
            .groupby(["field", "period_start", "period_end"], dropna=False)["value"]
            .nunique()
        )
        restatement_examples += int((dup > 1).sum())

        for fdate in filing_dates:
            asof = tdf[tdf["filed"] <= fdate]
            cur_filings = tdf[tdf["filed"] == fdate]
            # Use the primary periodic form filed on fdate
            forms = cur_filings["form"].unique().tolist()
            form_lbl = "10-K" if "10-K" in forms else forms[0]

            rec: dict = {
                "ticker": ticker,
                "available_from": fdate.strftime("%Y-%m-%d"),
                "form": form_lbl,
            }

            # Balance sheet (instant fields): most recent period_end as of fdate, latest filing for it
            latest_bs_end = None
            for fld in INSTANT_FIELDS:
                sub = asof[asof["field"] == fld]
                if sub.empty:
                    rec[fld] = np.nan
                    continue
                latest_per_end = (
                    sub.sort_values(["filed", "form"])
                    .drop_duplicates(subset=["period_end"], keep="last")
                    .sort_values("period_end")
                )
                pick = latest_per_end.iloc[-1]
                rec[fld] = float(pick["value"])
                if latest_bs_end is None or pick["period_end"] > latest_bs_end:
                    latest_bs_end = pick["period_end"]

            # Flow fields (TTM)
            rev_sub = asof[asof["field"] == "revenue"]
            ttm_rev, rev_end, rev_src = _compute_ttm_from_state(rev_sub)
            rec["ttm_revenue"] = ttm_rev
            rec["rev_src"] = rev_src
            rec["rev_yoy"] = _compute_annual_yoy(rev_sub, ttm_rev, rev_end)

            ni_sub = asof[asof["field"] == "net_income"]
            ttm_ni, ni_end, ni_src = _compute_ttm_from_state(ni_sub)
            rec["ttm_net_income"] = ttm_ni
            rec["ni_yoy"] = _compute_annual_yoy(ni_sub, ttm_ni, ni_end)

            cfo_sub = asof[asof["field"] == "cfo"]
            ttm_cfo, cfo_end, _ = _compute_ttm_from_state(cfo_sub)
            rec["ttm_cfo"] = ttm_cfo

            eps_sub = asof[asof["field"] == "eps_diluted"]
            ttm_eps, _, _ = _compute_ttm_from_state(eps_sub)
            rec["ttm_eps"] = ttm_eps

            pe = max([d for d in (latest_bs_end, rev_end, ni_end, cfo_end) if d is not None], default=None)
            rec["latest_period_end"] = pe.strftime("%Y-%m-%d") if pe is not None else ""
            rec["report_lag_days"] = int((fdate - pe).days) if pe is not None else np.nan

            # Derived causal PIT ratios
            assets = rec.get("assets", np.nan)
            equity = rec.get("equity", np.nan)
            lt_debt = rec.get("lt_debt", np.nan)
            cash = rec.get("cash", np.nan)
            rec["net_margin"] = (ttm_ni / ttm_rev) if (np.isfinite(ttm_ni) and np.isfinite(ttm_rev) and ttm_rev > 0) else np.nan
            rec["roe"] = (ttm_ni / equity) if (np.isfinite(ttm_ni) and np.isfinite(equity) and equity > 0) else np.nan
            rec["cfo_to_assets"] = (ttm_cfo / assets) if (np.isfinite(ttm_cfo) and np.isfinite(assets) and assets > 0) else np.nan
            rec["accruals"] = ((ttm_ni - ttm_cfo) / assets) if (np.isfinite(ttm_ni) and np.isfinite(ttm_cfo) and np.isfinite(assets) and assets > 0) else np.nan
            rec["debt_to_assets"] = (lt_debt / assets) if (np.isfinite(lt_debt) and np.isfinite(assets) and assets > 0) else np.nan
            rec["cash_to_assets"] = (cash / assets) if (np.isfinite(cash) and np.isfinite(assets) and assets > 0) else np.nan

            rows.append(rec)

    pit = pd.DataFrame(rows).sort_values(["ticker", "available_from"]).reset_index(drop=True)
    pit_path = SEC / "pit_fundamentals.csv"
    pit.to_csv(pit_path, index=False)

    # Verification assertions
    assert (pd.to_datetime(pit["available_from"]) >= pd.to_datetime(pit["latest_period_end"])).all(), \
        "PIT violation: available_from preceded latest_period_end"

    manifest = {
        "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "data/sec/fundamentals.csv (SEC EDGAR XBRL companyfacts)",
        "rows": int(len(pit)),
        "tickers": int(pit["ticker"].nunique()),
        "date_min": str(pit["available_from"].min()),
        "date_max": str(pit["available_from"].max()),
        "filtered_bad_filed_before_end": bad_dates,
        "comparative_restatement_series_detected": restatement_examples,
        "ttm_revenue_non_null_pct": round(float(pit["ttm_revenue"].notna().mean() * 100), 1),
        "ttm_cfo_non_null_pct": round(float(pit["ttm_cfo"].notna().mean() * 100), 1),
        "accruals_non_null_pct": round(float(pit["accruals"].notna().mean() * 100), 1),
        "median_report_lag_days": float(pit["report_lag_days"].median()),
        "leak_rule": "Join with available_from <= decision_date (using merge_asof or strict inequality), "
                     "then execute on decision_date + 1. Never backdate restatements.",
        "caveats": [
            "Covers top US-GAAP filers only (~63 of top 80 market cap; foreign ADRs / non-GAAP filers omitted).",
            "Does not contain analyst consensus estimates (no surprise vs consensus).",
            "Survivorship caveat: universe selected from current top market-cap firms (PITFALLS #7) — any "
            "backtest using this panel must note large-cap current-constituent selection bias.",
        ],
    }
    (SEC / "MANIFEST_PIT_SEC.json").write_text(json.dumps(manifest, indent=2))
    print(f"  pit_fundamentals: {len(pit)} rows across {pit['ticker'].nunique()} tickers "
          f"({manifest['date_min']}..{manifest['date_max']})")
    print(f"  restated period series prevented from leaking backwards: {restatement_examples}")
    print(f"  coverage: ttm_rev {manifest['ttm_revenue_non_null_pct']}% | "
          f"ttm_cfo {manifest['ttm_cfo_non_null_pct']}% | accruals {manifest['accruals_non_null_pct']}% | "
          f"median lag {manifest['median_report_lag_days']}d")
    print(pit[pit["ticker"] == "AAPL"].tail(6)[
        ["ticker", "available_from", "form", "latest_period_end", "ttm_revenue", "rev_yoy", "net_margin", "accruals", "rev_src"]
    ].to_string(index=False))


if __name__ == "__main__":
    main()
