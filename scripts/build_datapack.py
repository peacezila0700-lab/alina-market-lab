#!/usr/bin/env python3
"""Build ALINA_DATAPACK — a machine-consumable data pack for another AI to pick up and use.

Design goal (from the owner): an AI that connects to this pack must NOT have to re-search the
internet, and must NOT burn tokens re-deriving what is already known. So every dataset ships with:

  * the raw file (CSV) — the actual data
  * a catalog entry — schema, dtypes, coverage, provenance, checksum, leak rules, caveats,
    confidence grade, and a 2–3 row preview so a model can decide without loading the file
  * a human/AI card (cards/*.md) — 150–250 words: what it is, what it is NOT, how to join it
  * a global protocol file (README_FOR_AI.md) — what to trust, what to never do

Grades:  A = official primary source, measured or published   B = computed in this repo, method
documented   C = third-party, shape only, never for absolute levels or returns.

Outputs: dist/ALINA_DATAPACK/…  and  dist/ALINA_DATAPACK_v1.1.zip
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import zipfile
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "pack")   # NOT "dist": dist/ is excluded from workspace snapshots
PACK = os.path.join(DIST, "ALINA_DATAPACK")
RECORDED = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

# --------------------------------------------------------------------------- dataset registry
# src: path or glob relative to repo root. card: 1-2 sentences for the mini card.
DATASETS = [
    dict(id="fx_official_ecb_daily", src="data/official/*_ECB_D.csv", kind="prices",
         grade="A", title="Official ECB/derived FX daily fixes, 1999–2026",
         card="Daily reference rates published by the ECB at 14:15 CET. Ten USD/GBP/CHF/JPY/CAD/"
              "SEK/NOK/AUD/NZD lines quoted per EUR; GBPUSD is the arithmetic cross EURUSD/EURGBP "
              "(verified: level correlation 0.9995 vs Yahoo). Use these — not Yahoo — for FX levels "
              "AND returns.",
         caveats=["Reference rate, not a tradeable quote: no bid/ask.",
                  "No weekend bars. ECB publishes on TARGET business days.",
                  "GBPUSD is derived, not published directly."],
         use_for=["FX backtests needing correct returns", "cost modelling baselines"],
         leak_rule="Observation for date D is available after 14:15 CET on D. Do not use it for a fill on D."),
    dict(id="universe_daily_etf", src="data/universe/*.csv", kind="prices",
         grade="C", title="Yahoo daily OHLCV, 24 instruments across 7 classes, 2000–2026",
         card="Broad multi-asset panel: FX, metals, energy, indices, bonds, crypto, agri, plus SPY "
              "and VIXY. Good for cross-asset shape and for equity/ETF series (SPY, TLT, GLD-like). "
              "NOT usable for FX levels or returns: Yahoo FX daily returns correlate only 0.38–0.52 "
              "with official fixes (see pitfalls).",
         caveats=["Yahoo FX is a different daily snapshot than the ECB fix — returns decorrelate.",
                  "Contains bad prints up to 13.8% (EURUSD 2008-12-08).",
                  "VXX only from 2018 on Yahoo; use VIXY (2011+) for vol ETP work.",
                  "Adjusted prices differ from closes; column `adjclose` exists where available."],
         use_for=["index/ETF/metals/crypto research", "cross-asset correlations"],
         leak_rule="Close of day D is known at/after the US close. Do not fill at the same day's close."),
    dict(id="cot_weekly_cftc", src="data/cot/cot_weekly.csv", kind="positioning",
         grade="A", title="CFTC Commitments of Traders, weekly, 1986–2026, 24 contracts",
         card="Who holds the position: commercial hedgers vs non-commercial funds vs small traders, "
              "plus open interest, trader counts and top-4 concentration. This is the closest free "
              "proxy for 'what the big money is doing'. 35,936 contract-weeks.",
         caveats=["As-of Tuesday, published Friday 15:30 ET — the file carries BOTH dates. "
                  "Using report_date as if it were tradeable is a look-ahead bug.",
                  "Legacy report only; the disaggregated/TFF reports are separate CFTC datasets.",
                  "Contract continuity breaks: e.g. S&P 500 Consolidated starts 2010, earlier 'S&P 500 "
                  "STOCK INDEX' is a different contract.",
                  "Positioning is descriptive; it is not a signal until tested.",
                  "SIGN TRAP: contracts quoted in the foreign currency (JPY, CHF, CAD, MXN) invert the "
                  "USD pair's direction — net long JPY = short USDJPY."],
         use_for=["extreme-positioning studies", "sentiment/contrarian features", "regime filters"],
         leak_rule="Use `available_from` (Friday), never `report_date` (Tuesday)."),
    dict(id="cot_features_derived", src="data/cot/cot_features.csv", kind="features",
         grade="B", title="COT positioning features, pre-computed (z-score & 3y percentile)",
         card="Ready-to-join features from the COT panel so a consumer does not have to rebuild the "
              "classic 'COT index': net positioning as % of OI, its 156-week z-score and percentile "
              "rank, 4-week change, plus OI growth. Already lagged-safe (each row carries "
              "available_from).",
         caveats=["Percentile/z are computed on a trailing 156-week window (min 52) — the first year "
                  "of each instrument is NaN.",
                  "SIGN TRAP: for USDJPY, USDCHF and USDCAD the traded contract is the FOREIGN currency "
                  "(JPY/CHF/CAD). A net long JPY futures position is a SHORT USDJPY. Flip the sign "
                  "when mapping to a USD-quoted pair. Same applies to USDMXN.",
                  "Percent-of-OI is comparable across time and contracts; raw contract counts are not."],
         use_for=["contrarian positioning studies (idea I01/I02)", "regime filters", "lead-lag features"],
         leak_rule="Use available_from (Friday), never report_date (Tuesday)."),
    dict(id="vix_cboe_daily", src="data/official/VIX_CBOE_D.csv", kind="volatility",
         grade="A", title="CBOE VIX daily close, 1990–2026 (9,320 rows)",
         card="30-day implied volatility of the S&P 500. The reference series for the variance risk "
              "premium (VIX minus subsequent realised vol) and for global risk appetite.",
         caveats=["Close only (the source CSV has OHLC but this copy keeps close).",
                  "Implied vol, not a tradeable price; the tradeable proxies are VIX futures / VIXY."],
         use_for=["VRP research", "risk-regime features", "vol targeting"],
         leak_rule="Daily close; usable next session."),
    dict(id="skew_cboe_daily", src="data/options/SKEW.csv", kind="volatility",
         grade="A", title="CBOE SKEW index daily, 1990–2026 (9,274 rows)",
         card="Pricing of tail risk: how much more the market pays for deep OTM puts than a "
              "lognormal model implies. High SKEW = crash protection expensive. Complements VIX "
              "(which only measures the middle of the distribution).",
         caveats=["Index level is a relative measure, not a probability.",
                  "No intraday data; one value per day."],
         use_for=["tail-risk features", "put-demand proxies (VIX is silent on this)"],
         leak_rule="Daily close; usable next session."),
    dict(id="spreads_measured_dukascopy", src="data/spreads/*_hourly.csv", kind="costs",
         grade="B", title="MEASURED bid/ask spreads, 10 FX pairs, hourly, 2003–2025",
         card="Real quoted spreads computed from aligned bid and ask bars (ask − bid). Use this "
              "instead of guessing a cost assumption — in this project the guess was 10× too wide "
              "on EURUSD and 1.5× too narrow on EURSEK, which flipped a strategy verdict.",
         caveats=["One ECN venue (Dukascopy). A retail standard account is wider; a raw+commission "
                  "account is near these numbers plus commission.",
                  "Hourly snapshots, not tick-level; the true median spread is slightly tighter."],
         use_for=["cost models", "verdict sensitivity", "instrument selection by liquidity"],
         leak_rule="Cost is a property of the venue; using today's measured spread historically is a "
                   "mild forward bias — state it."),
    dict(id="fomc_decision_dates", src="data/events/fomc_dates.csv", kind="calendar",
         grade="A", title="FOMC decision dates 1994–2026 (205 dates)",
         card="Every FOMC policy decision date, parsed from the Federal Reserve's own file names "
              "(not from prose). Use to build event windows and to test event risk.",
         caveats=["Decision dates only — no press-conference-only or emergency meetings.",
                  "Parsing covers 1994+; 2021+ years live on the current calendar page."],
         use_for=["event studies", "avoiding entries into scheduled risk", "vol regime features"],
         leak_rule="Scheduled in advance — safe to use as a forward-known feature."),
    dict(id="econ_calendar_archive", src="data/events/ff_events.csv", kind="calendar",
         grade="C", title="Economic calendar archive, forward-collected from 2026-11",
         card="Scheduled macro releases with impact rating, forecast and previous value. The free "
              "feed serves only the current week, so this archive grows forward from 2026-11-20 — "
              "there is NO historical backfill available for free.",
         caveats=["Short history (starts 2026-11). Do not backtest on it yet.",
                  "Impact ratings are the vendor's, not a measured market reaction."],
         use_for=["live event guarding", "future event studies"],
         leak_rule="Forecast is published before the release; actual requires post-release data."),
    dict(id="attention_wikipedia_pageviews", src="data/events/attention/*.csv", kind="attention",
         grade="A", title="Public attention proxy — daily Wikipedia pageviews, 8 assets, 2016–2026",
         card="Daily English Wikipedia views per asset article. Measured result: attention improves "
              "the next-day volatility forecast on 6 of 8 assets (MAE) but NOT the portfolio Sharpe "
              "(0.64 → 0.63). Treat as a regime/diagnostic feature, never as a direction signal.",
         caveats=["Views are not sentiment — they cannot tell you the sign of the news.",
                  "Article choice is hand-made; a different article changes the series."],
         use_for=["vol regime features", "sizing inputs", "narrative checks"],
         leak_rule="A day's view count is only complete after that day ends."),
    dict(id="free_ea_catalog", src="data/free_eas/CATALOG.csv", kind="meta",
         grade="A", title="What the free EA ecosystem actually offers — 332 sources catalogued",
         card="240 MQL5 Code Base listings + 92 GitHub repos, tagged by strategy family. Companion "
              "result: 144 family-level tests show 6 of 144 beat a turnover-matched null (= chance).",
         caveats=["Titles/descriptions only, no code was executed — MQL5 cannot be compiled here.",
                  "Star counts and listings change over time; this is a snapshot."],
         use_for=["knowing what exists", "avoiding re-testing the same idea"],
         leak_rule="n/a"),
    dict(id="screen_24_assets_7_rules", src="research/artifacts/universe_screen.csv", kind="results",
         grade="B", title="168-test screen: 7 documented rules × 24 instruments, null-controlled",
         card="Every test charged costs and beaten against 300 random-permutation nulls. Contains the "
              "look-ahead-CORRECTED numbers (the earlier buggy version produced a fake Sharpe 1.72).",
         caveats=["Cost assumptions here were later superseded by measured spreads for FX.",
                  "maxDD above 100% = equity curve crossing zero (wipes), not a percentage.",
                  "Yahoo-based FX rows inherit the C-grade caveat."],
         use_for=["baseline comparisons", "knowing which families are dead"],
         leak_rule="n/a (results)"),
    dict(id="strategy_comparison_ecb_27y", src="reports/strategy_comparison.json", kind="results",
         grade="B", title="7 strategy families × 6 ECB pairs × 27 years, cost-charged",
         card="Trend, MA cross, TSMOM, range fade, buy&hold and a RANDOM control. Every trend family "
              "is flat-to-negative and worse after 2013; the random control loses (−0.32 Sharpe), "
              "which is the proof the cost model is actually applied.",
         caveats=["Pooled equal-weight across 6 pairs; individual pairs differ.",
                  "Costs = 1.3 pip assumption, later replaced by measured spreads."],
         use_for=["priors on FX rule performance", "sanity-checking a new FX backtest"],
         leak_rule="n/a (results)"),
    dict(id="fx_crosses_derived", src=["data/official/*_D.csv", "!data/official/*_ECB_D.csv", "!data/official/VIX*"], kind="prices",
         grade="B", title="Derived FX crosses (AUDCAD, EURNOK, ...) from ECB legs",
         card="Cross rates computed as leg1/leg2 of ECB official EUR-quoted rates (e.g. AUDCAD = "
              "AUDUSD/USDCAD). Used for the cross-sectional reversion work. Derived, so rounding and "
              "holiday misalignment of the two legs introduce small errors.",
         caveats=["A business day missing in one leg drops the cross for that date.",
                  "Derived, not an exchange quote: do not compare to a broker's level at the pip."],
         use_for=["cross-sectional FX work", "currency triangles"],
         leak_rule="Inherits the ECB 14:15 CET availability."),
    dict(id="prereg_and_reports", src="reports/*.md", kind="docs",
         grade="B", title="Full reports + pre-registrations + decision log (prose)",
         card="Every written report in the project: 8 experiment write-ups, pre-registration "
              "documents (written BEFORE the tests), the decision log D01–D12, hypothesis register, "
              "incident log QR-001..003. Load these only when you need the reasoning behind a "
              "verdict — the machine-readable version is in results/experiments.jsonl.",
         caveats=["Prose is verbose by design; prefer experiments.jsonl for bulk ingestion.",
                  "Some documents are milestone snapshots and were later superseded."],
         use_for=["auditing a verdict", "avoiding a repeated mistake"],
         leak_rule="n/a (documentation)"),
    dict(id="experiments_ledger", src="research/EXPERIMENT_LOG.csv", kind="results",
         grade="B", title="Every experiment run, with verdicts — the project's memory",
         card="8 pre-registered experiments (EXP-0001…0008) with hypothesis, data, cost model, "
              "metrics, robustness and final verdict. Read this FIRST: it prevents re-running dead "
              "ideas and shows exactly what was tested and how it failed.",
         caveats=["Verdicts are only as good as the pre-registration discipline behind them.",
                  "EXP-0006 is a re-score of EXP-0005 (same rules, measured costs) — not an "
                  "independent confirmation."],
         use_for=["avoiding duplicate work", "learning the failure modes", "meta-analysis"],
         leak_rule="n/a"),
]


def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def resolve(src) -> list[str]:
    """src may be a glob, a plain path, or a list where entries starting with '!' exclude."""
    import glob as g
    pats = src if isinstance(src, list) else [src]
    files: list[str] = []
    for pat in pats:
        if pat.startswith("!"):
            files = [f for f in files if not g.fnmatch.fnmatch(os.path.basename(f), os.path.basename(pat[1:]))]
        elif "*" in pat:
            files += [f for f in sorted(g.glob(os.path.join(ROOT, pat))) if os.path.isfile(f)]
        elif os.path.isfile(os.path.join(ROOT, pat)):
            files.append(os.path.join(ROOT, pat))
    return files


def profile(path) -> dict:
    files = resolve(path)
    if not files:
        return {"files": 0}
    total_rows, firsts, lasts, cols = 0, [], [], []
    sample = None
    for f in files:
        with open(f, newline="") as fh:
            rd = csv.reader(fh)
            try:
                header = next(rd)
            except StopIteration:
                continue
            cols = header
            n = 0
            first_row = None
            for row in rd:
                if not row:
                    continue
                n += 1
                if first_row is None:
                    first_row = row
            total_rows += n
        if sample is None and first_row is not None:
            sample = [header, first_row]
    if files and not files[0].lower().endswith((".csv", ".txt")):
        total_rows, cols, sample = None, [], None
    return {"files": len(files), "rows": total_rows, "columns": cols, "sample": sample}


def main() -> None:
    if os.path.isdir(PACK):
        shutil.rmtree(PACK)
    for sub in ("data", "cards", "knowledge", "code", "results"):
        os.makedirs(os.path.join(PACK, sub), exist_ok=True)

    catalog = {"pack": "ALINA_DATAPACK", "version": "1.1",
               "built_utc": RECORDED,
               "purpose": "A self-contained, machine-readable research base for an AI trading system: "
                          "market data, positioning, volatility, costs, calendars, attention, the "
                          "catalogue of free EAs, and every experiment this project ran with its verdict.",
               "grades": {"A": "official primary source", "B": "computed here, method documented",
                          "C": "third-party, shape only — never absolute levels or returns"},
               "datasets": []}

    for d in DATASETS:
        prof = profile(d["src"])
        if not prof.get("files"):
            print(f"  SKIP {d['id']} (no files)")
            continue
        dest_dir = os.path.join(PACK, "data", d["id"])
        os.makedirs(dest_dir, exist_ok=True)
        files = resolve(d["src"])
        entries = []
        for f in files:
            if not os.path.isfile(f):
                continue
            shutil.copy2(f, dest_dir)
            entries.append({"file": os.path.basename(f), "bytes": os.path.getsize(f),
                            "sha256": sha256(f)})
        entry = {"id": d["id"], "title": d["title"], "kind": d["kind"], "grade": d["grade"],
                 "path": f"data/{d['id']}/", "files": entries,
                 "rows_total": prof["rows"], "columns": prof["columns"],
                 "preview": prof["sample"],
                 "caveats": d["caveats"], "use_for": d["use_for"], "leak_rule": d["leak_rule"],
                 "card": f"cards/{d['id']}.md"}
        catalog["datasets"].append(entry)
        with open(os.path.join(PACK, "cards", f"{d['id']}.md"), "w") as fh:
            fh.write(f"# {d['id']} — {d['title']}\n\n"
                     f"**Grade {d['grade']}** · {prof['rows']} rows · {len(entries)} file(s) · "
                     f"columns: {', '.join(prof['columns'][:14]) or 'n/a'}\n\n"
                     f"{d['card']}\n\n"
                     f"**Use for:** {'; '.join(d['use_for'])}\n\n"
                     f"**Caveats:**\n" + "".join(f"- {c}\n" for c in d["caveats"]) +
                     f"\n**Leak / look-ahead rule:** {d['leak_rule']}\n")
        print(f"  {d['id']:34} {str(prof['rows'] or '-'):>7} rows  {len(entries)} files  grade {d['grade']}")

    with open(os.path.join(PACK, "catalog.json"), "w") as f:
        json.dump(catalog, f, indent=2)

    # ---- results json (all artifacts an AI may want to read quickly)
    for rel in ["research/artifacts/universe_screen.json", "reports/strategy_comparison.json",
                "research/artifacts/portfolio_donchian.json", "research/artifacts/event_study.json",
                "research/artifacts/attention_signal.json", "research/artifacts/h09_assumed.json",
                "research/artifacts/h09_ecn.json", "research/artifacts/h09_retail.json",
                "research/artifacts/h10_holdout.json", "research/artifacts/h11_vrp.json",
                "research/artifacts/free_ea_families_summary.json",
                "research/artifacts/cot_extremity.json", "reports/COT_EXTREMITY.md",
                "research/EXPERIMENT_LOG.csv", "research/HYPOTHESIS_REGISTER.csv",
                "data/cot/MANIFEST_COT.json", "data/events/MANIFEST_EVENTS.json",
                "data/universe/MANIFEST_UNIVERSE.json", "data/spreads/MEASURED_COSTS.json"]:
        src = os.path.join(ROOT, rel)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(PACK, "results", os.path.basename(rel)))

    # ---- code
    for sub in ("scripts", "ea", "alina_lab", "tests"):
        s = os.path.join(ROOT, sub)
        if os.path.isdir(s):
            shutil.copytree(s, os.path.join(PACK, "code", sub),
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "raw"))

    # ---- knowledge docs written by hand elsewhere
    for doc in ("README_FOR_AI.md", "DATA_SOURCES.md", "PITFALLS.md", "WHAT_FAILED.md",
                "IDEAS_TO_TEST.md", "GLOSSARY.md", "HOW_TO_BACKTEST.md"):
        s = os.path.join(ROOT, "datapack_src", doc)
        if os.path.exists(s):
            shutil.copy2(s, os.path.join(PACK, "knowledge", doc))

    # ---- experiments as jsonl (machine-readable)
    exp_csv = os.path.join(ROOT, "research", "EXPERIMENT_LOG.csv")
    if os.path.exists(exp_csv):
        with open(exp_csv, newline="") as f, open(os.path.join(PACK, "results", "experiments.jsonl"), "w") as o:
            for r in csv.DictReader(f):
                o.write(json.dumps(r, ensure_ascii=False) + "\n")

    # ---- top-level README (Thai, for the owner) + INDEX.csv (one lookup table)
    for doc in ("README_TH.md",):
        sdoc = os.path.join(ROOT, "datapack_src", doc)
        if os.path.exists(sdoc):
            shutil.copy2(sdoc, os.path.join(PACK, doc))
    import csv as _csv
    with open(os.path.join(PACK, "INDEX.csv"), "w", newline="") as fh:
        w = _csv.writer(fh)
        w.writerow(["path", "bytes", "sha256"])
        for base, _, fs in sorted(os.walk(PACK)):
            for fn in sorted(fs):
                if fn == "INDEX.csv":
                    continue
                fp = os.path.join(base, fn)
                w.writerow([os.path.relpath(fp, PACK), os.path.getsize(fp), sha256(fp)])

    # ---- zip
    zpath = os.path.join(DIST, "ALINA_DATAPACK_v1.1.zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for base, _, files in os.walk(PACK):
            for fn in files:
                p = os.path.join(base, fn)
                z.write(p, os.path.relpath(p, DIST))
    size = os.path.getsize(zpath)
    print(f"\nzip: {zpath}  ({size / 1e6:.1f} MB, {sum(len(f) for _, _, f in os.walk(PACK))} files)")
    with open(os.path.join(PACK, "catalog.json")) as f:
        cat = json.load(f)
    cat["zip_bytes"] = size
    with open(os.path.join(PACK, "catalog.json"), "w") as f:
        json.dump(cat, f, indent=2)


if __name__ == "__main__":
    main()
