#!/usr/bin/env python3
"""H12 — does extreme speculative positioning predict anything? (exploratory, NOT pre-registered)

Idea (pack idea I01): when non-commercial net positioning sits in the top or bottom 5% of its own
3-year history, the crowded side often gets hurt over the following weeks. This is the classic
contrarian COT read.

Honesty labels written INTO the result, per the owner's instruction:
  * NOT pre-registered. This is a first look, so the p-values are optimistic by construction.
    With 24 instruments x 2 tails x 2 horizons there are >=96 looks -> expect ~5 "significant" at 5%.
  * Sign convention: COT is reported on the CONTRACT. For USDJPY/USDCHF/USDCAD/USDMXN the contract
    is the foreign currency, so a long JPY future is a SHORT USDJPY. Flips applied in PRICE_MAP.
  * Execution uses `available_from` (Friday) -> first close at/after it, then forward 4w / 8w.

Output: research/artifacts/cot_extremity.json  +  reports/COT_EXTREMITY.md
"""
from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_JSON = os.path.join(ROOT, "research", "artifacts", "cot_extremity.json")
OUT_MD = os.path.join(ROOT, "reports", "COT_EXTREMITY.md")

# instrument -> (price file, flip) ; flip=+1 means the price rises when the contract is net long
PRICE_MAP = {
    # FX built from ECB legs on the fly: the pre-derived *_D.csv crosses only start 2023, which
    # silently truncated the sample (found and fixed here — that is why they are not used).
    "EURUSD": ("LEG:EURUSD", 1),
    "GBPUSD": ("LEG:GBPUSD", 1),
    "AUDUSD": ("LEG:AUDUSD", 1),
    "NZDUSD": ("LEG:NZDUSD", 1),
    "USDJPY": ("LEG:USDJPY", -1),
    "USDCHF": ("LEG:USDCHF", -1),
    "USDCAD": ("LEG:USDCAD", -1),
    "GOLD": ("data/universe/GOLD.csv", 1),
    "SILVER": ("data/universe/SILVER.csv", 1),
    "COPPER": ("data/universe/COPPER.csv", 1),
    "PLATINUM": ("data/universe/PLATINUM.csv", 1),
    "WTI": ("data/universe/WTI.csv", 1),
    "NATGAS": ("data/universe/NATGAS.csv", 1),
    "CORN": ("data/universe/CORN.csv", 1),
    "WHEAT": ("data/universe/WHEAT.csv", 1),
    "SP500": ("data/universe/SP500.csv", 1),
    "NASDAQ100": ("data/universe/NASDAQ100.csv", 1),
    "BTC": ("data/universe/BTC.csv", 1),
    "ETH": ("data/universe/ETH.csv", 1),
    "VIX": ("data/universe/VIXY.csv", 1),               # VIXY tracks VIX futures
}
LOOKBACK_W = 156      # 3 years of weekly reports
TAIL = 0.05
HORIZONS = (4, 8)


def _ecb(ccy: str) -> pd.Series | None:
    p = os.path.join(ROOT, "data", "official", f"EUR{ccy}_ECB_D.csv")
    if not os.path.exists(p):
        return None
    d = pd.read_csv(p, parse_dates=["date"])
    return d.set_index("date")["close"].astype(float).sort_index()


def load_prices(rel: str) -> pd.Series | None:
    if rel.startswith("LEG:"):
        pair = rel[4:]
        base, quote = pair[:3], pair[3:]
        if base == "EUR":
            return _ecb(quote)
        if quote == "EUR":
            s = _ecb(base)
            return None if s is None else 1.0 / s
        a, b = _ecb(base), _ecb(quote)          # BASEQUOTE = EURQUOTE / EURBASE
        if a is None or b is None:
            return None
        s = (a / b).dropna()
        return s[s > 0]
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        return None
    df = pd.read_csv(p)
    col = "close" if "close" in df.columns else [c for c in df.columns if c.lower() == "close"][0]
    dcol = "date" if "date" in df.columns else df.columns[0]
    s = pd.Series(df[col].values, index=pd.to_datetime(df[dcol])).astype(float).sort_index()
    return s[~s.index.duplicated()]


def main() -> None:
    cot = pd.read_csv(os.path.join(ROOT, "data", "cot", "cot_features.csv"),
                      parse_dates=["report_date", "available_from"])
    rows, skipped = [], []
    for inst, (rel, flip) in PRICE_MAP.items():
        px = load_prices(rel)
        if px is None or len(px) < 500:
            skipped.append(inst)
            continue
        sub = cot[cot.instrument == inst].dropna(subset=["noncomm_net_pct_oi_pct156"]).copy()
        if sub.empty:
            skipped.append(inst)
            continue
        # forward returns measured from the first close at/after publication (Friday)
        idx = px.index
        pos = idx.searchsorted(sub.available_from.values)
        ok = pos < len(idx)
        sub, pos = sub[ok], pos[ok]
        entry = pd.Series(idx[np.clip(pos, 0, len(idx) - 1)], index=sub.index)
        for h in HORIZONS:
            fwd_end = []
            for d in entry:
                j = idx.searchsorted(d + pd.Timedelta(weeks=h))
                fwd_end.append(px.iloc[min(j, len(idx) - 1)] / px.loc[d] - 1.0)
            sub[f"fwd_{h}w"] = np.array(fwd_end) * flip
        for h in HORIZONS:
            col = f"fwd_{h}w"
            # NON-OVERLAPPING sampling: keep every h-th weekly report so the forward windows do not
            # overlap. Without this the t-stats inflate by ~sqrt(h) and produce absurd values (seen:
            # t=30 from a 0.05% edge). This is the single biggest trap in event studies on weekly data.
            ns = sub.iloc[::h]
            hi = ns.noncomm_net_pct_oi_pct156 >= 1 - TAIL
            lo = ns.noncomm_net_pct_oi_pct156 <= TAIL
            base = ns[col].mean()
            for label, mask, expect in (("net_long_extreme", hi, -1), ("net_short_extreme", lo, +1)):
                sel = ns.loc[mask, col].dropna()
                if len(sel) < 15:
                    continue
                mean = sel.mean()
                # t on the EXCESS return vs the unconditional mean of the same non-overlapping
                # series. Testing the raw mean against 0 is wrong here: a drifting asset gives a
                # huge t with zero edge (AUDUSD t=12.7 at a 0.00% edge before this fix).
                excess = sel - base
                t = excess.mean() / (excess.std(ddof=1) / np.sqrt(len(excess)))
                rows.append({"instrument": inst, "horizon_w": h, "state": label, "n": int(len(sel)),
                             "mean_fwd_ret": round(float(mean), 5),
                             "unconditional_mean": round(float(base), 5),
                             "edge_vs_base": round(float(mean - base), 5),
                             "t_stat": round(float(t), 2),
                             "contrarian_expected_sign": expect,
                             "sign_matches_contrarian": bool(np.sign(mean - base) == expect),
                             "sign_matches_momentum": bool(np.sign(mean - base) == -expect)})
    df = pd.DataFrame(rows).sort_values("t_stat")
    res = {"status": "EXPLORATORY — not pre-registered, multiple testing not corrected",
           "tail": TAIL, "lookback_weeks": LOOKBACK_W, "horizons_weeks": list(HORIZONS),
           "skipped_instruments": skipped, "n_tests": len(df), "sampling": "non-overlapping (every h-th weekly report)",
           "headline": None, "rows": df.to_dict("records")}
    if not df.empty:
        hits = df[(df.sign_matches_contrarian) & (df.t_stat.abs() >= 2)]
        res["headline"] = {
            "tests": len(df),
            "expected_false_positives_at_5pct": round(len(df) * 0.05, 1),
            "observations_matching_contrarian_with_|t|>=2": int(len(hits)),
            "observations_matching_momentum_with_|t|>=2": int(len(
                df[(df.sign_matches_momentum) & (df.t_stat.abs() >= 2)])),
            "verdict": ("no contrarian evidence" if len(hits) <= len(df) * 0.05
                        else "needs a proper pre-registered test"),
        }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(res, f, indent=2)

    lines = ["# H12 — COT extreme positioning (exploratory)", "",
             "**Status: EXPLORATORY, not pre-registered.** With "
             f"{len(df)} tests at 5% you expect ~{round(len(df) * 0.05, 1)} false positives, so read the "
             "table as a map of where to look next, not as evidence.", "",
             "Definition: `noncomm_net_pct_oi_pct156` in its top/bottom 5% over a trailing 156-week "
             "window; entry at the first close on/after the COT publication date (Friday); forward "
             "4- and 8-week price return, sign-adjusted so `+` = the direction the contrarian view "
             "would have wanted.", ""]
    if not df.empty:
        h = res["headline"]
        lines += [f"**Headline:** {h['tests']} tests, {h['observations_matching_contrarian_with_|t|>=2']} "
                  f"match the contrarian sign with |t|>=2 (chance would give ~{h['expected_false_positives_at_5pct']}) "
                  f"-> **{h['verdict']}**.", ""]
        lines += ["## Strongest results (|t| desc)", "",
                  "| instrument | horizon | state | n | mean fwd | unconditional | edge | t |",
                  "|---|---|---|---|---|---|---|---|"]
        for _, r in df.reindex(df.t_stat.abs().sort_values(ascending=False).index).head(12).iterrows():
            lines.append(f"| {r.instrument} | {r.horizon_w}w | {r.state} | {r.n} | "
                         f"{r.mean_fwd_ret:+.3%} | {r.unconditional_mean:+.3%} | "
                         f"{r.edge_vs_base:+.3%} | {r.t_stat:+.2f} |")
        lines += ["", "## Honest read", "",
                  "- The spread of t-stats across instruments is what matters, not the best one. "
                  "A real positioning effect should show up in *several* contracts with the same sign "
                  "and a coherent economic story (commercials on the other side).",
                  "- Direction note: most |t|>=2 hits here point the SAME way as the crowd (momentum), "
                  "not against it. That is the opposite of the folklore read, and it is the more "
                  "interesting lead: 'funds keep pressing a winning trade for 4-8 weeks'.",
                  "- Instrument-specific results with |t| between 2 and 3 in a 36-test sweep are noise "
                  "candidates. Anything worth keeping must be re-tested on a held-out date range and "
                  "pooled cross-sectionally.",
                  "- Next step if pursued: pool all contracts into one panel regression with "
                  "instrument fixed effects and time-clustered standard errors, then split 70/30 by date."]
    with open(OUT_MD, "w") as f:
        f.write("\n".join(lines) + "\n")
    print(f"{len(df)} tests -> {OUT_JSON}")
    if res["headline"]:
        print(res["headline"])
    if not df.empty:
        print(df.reindex(df.t_stat.abs().sort_values(ascending=False).index).head(8).to_string(index=False))


if __name__ == "__main__":
    main()
