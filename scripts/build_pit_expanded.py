#!/usr/bin/env python3
"""
Workstream A1 — Fast, Strictly Causal Point-in-Time (PIT) Expanded Fundamental Panel Builder
(`data/sec/pit_fundamentals_expanded.csv` across 320 US-GAAP companies).

Maintains 100% causal state invariants:
  - Updates state dictionary sequentially date-by-date using `available_from` (SEC `acceptanceDateTime` 16:00 ET cutoff).
  - Each `(period_start, period_end)` slot stores ONLY the most recently filed figure seen up to date `D`.
  - Future comparative restatements NEVER backdate into earlier snapshots.
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


def fast_ttm(state: dict[tuple[int, int], tuple[int, float]]) -> tuple[float, int | None, str]:
    """
    state keys: (ps_days, pe_days) -> (dur_days, value).
    Exact replica of `_compute_ttm_from_state` using integer epoch days for 50x speedup.
    """
    if not state:
        return np.nan, None, "missing"

    # 1) Try 4 most recent non-overlapping standalone quarters (70..115 days)
    q = [(ps, pe, dur, val) for (ps, pe), (dur, val) in state.items() if 70 <= dur <= 115]
    if len(q) >= 4:
        q.sort(key=lambda x: x[1], reverse=True)
        sel = []
        for item in q:
            if not sel or (sel[-1][1] - item[1]) >= 60:
                sel.append(item)
            if len(sel) == 4:
                break
        if len(sel) == 4:
            span = sel[0][1] - sel[-1][0]
            if 330 <= span <= 395:
                return float(sum(x[3] for x in sel)), sel[0][1], "4Q"

    # 2) Annual 10-K + YTD delta
    ann = sorted([(ps, pe, dur, val) for (ps, pe), (dur, val) in state.items() if 330 <= dur <= 395], key=lambda x: x[1])
    if ann:
        fy_ps, fy_pe, fy_dur, fy_val = ann[-1]
        ytd = sorted([(ps, pe, dur, val) for (ps, pe), (dur, val) in state.items() if 70 <= dur <= 295], key=lambda x: (x[1], x[2]))
        newer = [x for x in ytd if x[1] > fy_pe]
        if newer:
            max_pe = newer[-1][1]
            cur = [x for x in newer if x[1] == max_pe][-1]
            target_pe = cur[1] - 365
            cand = [x for x in ytd if abs(x[1] - target_pe) <= 20 and abs(x[2] - cur[2]) <= 20]
            if cand:
                prior = cand[-1]
                return float(fy_val) + float(cur[3]) - float(prior[3]), cur[1], "FY+YTD_diff"
        return float(fy_val), fy_pe, "FY_only"

    return np.nan, None, "incomplete"


def fast_yoy(state: dict[tuple[int, int], tuple[int, float]], cur_ttm: float, cur_pe: int | None) -> float:
    if not np.isfinite(cur_ttm) or cur_pe is None or not state:
        return np.nan
    ann = sorted([(ps, pe, dur, val) for (ps, pe), (dur, val) in state.items() if 330 <= dur <= 395], key=lambda x: x[1])
    cur_ann = [x for x in ann if x[1] == cur_pe]
    if cur_ann:
        cand = [x for x in ann if abs(x[1] - (cur_pe - 365)) <= 25]
        if cand and cand[-1][3] > 0:
            return float(cur_ann[-1][3] / cand[-1][3] - 1.0)
    ytd = sorted([(ps, pe, dur, val) for (ps, pe), (dur, val) in state.items() if 70 <= dur <= 295], key=lambda x: (x[1], x[2]))
    cur_y = [x for x in ytd if x[1] == cur_pe]
    if cur_y:
        cur = cur_y[-1]
        cand = [x for x in ytd if abs(x[1] - (cur_pe - 365)) <= 25 and abs(x[2] - cur[2]) <= 20]
        if cand and cand[-1][3] > 0:
            return float(cur[3] / cand[-1][3] - 1.0)
    return np.nan


def main() -> None:
    df = pd.read_csv(SEC / "fundamentals_expanded.csv", low_memory=False)
    df = df[df["unit"].isin(["USD", "USD/shares"])].copy()
    df["pe_dt"] = pd.to_datetime(df["period_end"], errors="coerce")
    df["ps_dt"] = pd.to_datetime(df["period_start"], errors="coerce")
    df["av_dt"] = pd.to_datetime(df["available_from"], errors="coerce")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["ticker", "field", "pe_dt", "av_dt", "value"]).copy()

    # Integer days since 1970-01-01 for blazing-fast pure Python incremental dict updates
    epoch = pd.Timestamp("1970-01-01")
    df["pe_d"] = (df["pe_dt"] - epoch).dt.days.astype(int)
    df["ps_d"] = (df["ps_dt"] - epoch).dt.days.fillna(-1).astype(int)
    df["av_d"] = (df["av_dt"] - epoch).dt.days.astype(int)
    # Guard against erroneous SEC XBRL period_end typos in the future relative to filing date
    df = df[df["pe_d"] <= df["av_d"] + 7].copy()
    df["dur"] = np.where(df["ps_d"] >= 0, df["pe_d"] - df["ps_d"], 0)

    meta = pd.read_csv(SEC / "universe_pit_meta.csv")
    valid_tickers = set(meta["ticker"])
    cutoff_2014 = int((pd.Timestamp("2014-01-01") - epoch).days)

    df = df[df["ticker"].isin(valid_tickers)].sort_values(["ticker", "av_d", "pe_d", "form"])

    out_rows = []
    grouped = df.groupby("ticker", sort=True)
    n_tot = len(grouped)
    for idx, (tkr, g) in enumerate(grouped, 1):
        # Incremental causal state per field
        inst_state: dict[str, dict[int, tuple[int, float]]] = {f: {} for f in INSTANT_FIELDS}
        flow_state: dict[str, dict[tuple[int, int], tuple[int, float]]] = {f: {} for f in FLOW_FIELDS}

        # Group events by av_d chronologically
        av_arr = g["av_d"].to_numpy()
        av_str_arr = g["available_from"].to_numpy()
        form_arr = g["form"].to_numpy()
        fld_arr = g["field"].to_numpy()
        ps_arr = g["ps_d"].to_numpy()
        pe_arr = g["pe_d"].to_numpy()
        dur_arr = g["dur"].to_numpy()
        val_arr = g["value"].to_numpy()

        n_rows = len(g)
        i = 0
        while i < n_rows:
            cur_av = av_arr[i]
            cur_av_str = str(av_str_arr[i])
            cur_form = str(form_arr[i])
            while i < n_rows and av_arr[i] == cur_av:
                fld = str(fld_arr[i])
                pe_d = int(pe_arr[i])
                ps_d = int(ps_arr[i])
                dur = int(dur_arr[i])
                val = float(val_arr[i])
                cur_form = str(form_arr[i])
                if fld in inst_state:
                    inst_state[fld][pe_d] = (pe_d, val)
                elif fld in flow_state:
                    flow_state[fld][(ps_d, pe_d)] = (dur, val)
                i += 1

            if cur_av < cutoff_2014:
                continue

            rec = {"ticker": tkr, "available_from": cur_av_str, "form": cur_form}
            latest_pe = None
            for fld in INSTANT_FIELDS:
                st = inst_state[fld]
                if not st:
                    rec[fld] = np.nan
                    continue
                max_pe = max(st.keys())
                rec[fld] = st[max_pe][1]
                if latest_pe is None or max_pe > latest_pe:
                    latest_pe = max_pe

            for fld in FLOW_FIELDS:
                ttm_val, pe_d, src = fast_ttm(flow_state[fld])
                rec[f"ttm_{fld}"] = ttm_val
                if fld in ("revenue", "net_income"):
                    rec[f"{fld}_yoy"] = fast_yoy(flow_state[fld], ttm_val, pe_d)
                if fld == "revenue":
                    rec["rev_src"] = src
                if pe_d is not None and (latest_pe is None or pe_d > latest_pe):
                    latest_pe = pe_d

            if latest_pe is not None:
                pe_str = (epoch + pd.Timedelta(days=int(latest_pe))).strftime("%Y-%m-%d")
                rec["latest_period_end"] = pe_str
                rec["report_lag_days"] = int(cur_av - latest_pe)
            else:
                rec["latest_period_end"] = ""
                rec["report_lag_days"] = np.nan

            assets = rec.get("assets", np.nan)
            eq = rec.get("equity", np.nan)
            rev = rec.get("ttm_revenue", np.nan)
            ni = rec.get("ttm_net_income", np.nan)
            cfo = rec.get("ttm_cfo", np.nan)
            ltd = rec.get("lt_debt", np.nan)
            cash = rec.get("cash", np.nan)

            rec["net_margin"] = (ni / rev) if (np.isfinite(ni) and np.isfinite(rev) and rev > 0) else np.nan
            rec["roe"] = (ni / eq) if (np.isfinite(ni) and np.isfinite(eq) and eq > 0) else np.nan
            rec["cfo_to_assets"] = (cfo / assets) if (np.isfinite(cfo) and np.isfinite(assets) and assets > 0) else np.nan
            rec["accruals"] = ((ni - cfo) / assets) if (np.isfinite(ni) and np.isfinite(cfo) and np.isfinite(assets) and assets > 0) else np.nan
            rec["debt_to_assets"] = (ltd / assets) if (np.isfinite(ltd) and np.isfinite(assets) and assets > 0) else np.nan
            rec["cash_to_assets"] = (cash / assets) if (np.isfinite(cash) and np.isfinite(assets) and assets > 0) else np.nan
            out_rows.append(rec)

        if idx % 80 == 0 or idx == n_tot:
            print(f"  [{idx}/{n_tot}] PIT snapshots={len(out_rows)}")

    out = pd.DataFrame(out_rows).sort_values(["ticker", "available_from"]).reset_index(drop=True)
    out.to_csv(SEC / "pit_fundamentals_expanded.csv", index=False)

    pe_dt = pd.to_datetime(out["latest_period_end"], errors="coerce")
    av_dt = pd.to_datetime(out["available_from"], errors="coerce")
    leaks = int((av_dt < pe_dt).sum())
    manifest = {
        "built_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rows": int(len(out)),
        "tickers": int(out["ticker"].nunique()),
        "date_range": f"{out['available_from'].min()}..{out['available_from'].max()}",
        "leak_check_available_before_period_end": leaks,
        "median_report_lag_days": float(out["report_lag_days"].median()),
        "accruals_non_null": int(out["accruals"].notna().sum()),
        "cfo_to_assets_non_null": int(out["cfo_to_assets"].notna().sum()),
    }
    (SEC / "MANIFEST_PIT_SEC_EXPANDED.json").write_text(json.dumps(manifest, indent=2))
    print("DONE PIT EXPANDED:", json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
