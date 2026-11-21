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

Outputs: dist/ALINA_DATAPACK/…  and  dist/ALINA_DATAPACK_v2.7.zip
"""
from __future__ import annotations

import csv
import gzip
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
    dict(id="dix_gex", src="data/alt/dix_gex.csv", kind="positioning",
         grade="B", title="Dark-pool index (DIX) + dealer gamma (GEX), daily 2011→2026",
         card="SqueezeMetrics publishes two things nobody else gives away free: DIX, the share of "
              "off-exchange volume that looks like retail buying (its complement is institutional "
              "selling), and GEX, modelled dealer gamma in $ per 1% index move. Positive GEX = dealers "
              "dampen moves (pinning); negative GEX = dealers amplify (trending, crash-prone).",
         caveats=["GEX is modelled from open interest under the long-call/short-put assumption — dealer "
                  "positioning is not observable, the sign can be wrong in unusual flow.",
                  "DIX is a share of off-exchange volume, not a dollar flow, and its definition is fixed "
                  "by the vendor.",
                  "Index-level only (SPX/SPY), no single-name or sector detail."],
         use_for=["regime/pinning analysis", "vol-of-vol features", "sizing overlays"],
         leak_rule="Published after the close for the same day; use t+1."),
    dict(id="ofr_financial_stress", src="data/alt/ofr_fsi.csv", kind="stress",
         grade="A", title="OFR Financial Stress Index + 5 sub-indices, daily 2000→2026",
         card="Official US Treasury-office stress gauge. 0 = historical average; positive = above-average "
              "stress. Sub-indices split credit, equity valuation, safe assets, funding and volatility, so "
              "you can see WHICH kind of stress is building instead of one blended number.",
         caveats=["Weekly-ish publication lag on some legs; not intraday.",
                  "Rescaled so the full history has zero mean — the level is only meaningful relative to "
                  "that history."],
         use_for=["early warning", "regime state", "risk gating"],
         leak_rule="Use the published date, not the observation date."),
    dict(id="policy_geopolitical_risk", src=["data/alt/epu_us_monthly.csv", "data/alt/gpr_monthly.csv"],
         kind="macro-risk", grade="A", title="Economic Policy Uncertainty (1900→) + Geopolitical Risk (1900→)",
         card="The two text-based risk indices most cited in academic macro trading: EPU counts newspaper "
              "articles about policy uncertainty, GPR counts geopolitical-risk coverage (threats vs acts). "
              "Both are genuinely independent of price data — the rarest property in a feature.",
         caveats=["Monthly frequency and published with a lag; use as a backdrop, never as a trigger.",
                  "Newspaper-count indices are sensitive to the newspaper set; revisions happen."],
         use_for=["regime backdrop", "tail-risk context", "long-horizon conditioning"],
         leak_rule="Month M value is only known after month M ends (publication lag of days)."),
    dict(id="physical_supply_eia", src=["data/alt/eia_crude_stocks_w.csv", "data/alt/eia_henryhub_w.csv"],
         kind="supply", grade="A", title="EIA weekly crude stocks (1982→) + Henry Hub gas (1997→)",
         card="The physical layer behind energy futures: weekly commercial crude inventories and the "
              "Henry Hub spot price. Inventories are the single biggest scheduled driver of crude, and "
              "they are measured, not derived from prices.",
         caveats=["Crude stocks release Wednesday 10:30 ET — the release is the event, the level is context.",
                  "Aggregate US stocks, not Cushing or product-specific; seasonality is strong."],
         use_for=["energy supply surprises", "inflation nowcast inputs", "seasonality studies"],
         leak_rule="Weekly, released Wednesday; the prior week's number is known."),
    dict(id="crypto_positioning_flows", src=["data/alt/okx_btc_funding.csv", "data/alt/okx_btc_long_short_ratio.csv"],
         kind="positioning", grade="A", title="Crypto perpetual funding + top-trader long/short ratio (OKX)",
         card="Exchange-published, free: 8-hourly funding rate (the price of leveraged long exposure — "
              "positive means longs pay shorts, i.e. crowded long) and the account-level long/short ratio. "
              "A crowding and carry measure in one number, available 24/7 with no reporting lag.",
         caveats=["Single venue (OKX); Binance blocks this sandbox IP and Bybit is CloudFront-blocked.",
                  "Only the last 100 funding points per call — history must be accumulated daily.",
                  "Account-count ratio, not notional exposure."],
         use_for=["crypto carry", "crowding/contrarian features", "24/7 regime"],
         leak_rule="Real-time; funding is known in advance for the next 8h window."),
    dict(id="deribit_btc_options", src=["data/alt/deribit_btc_chain_snapshot.csv",
                                        "data/alt/deribit_btc_term_structure.csv"],
         kind="volatility", grade="A", title="Deribit BTC option chain snapshot → IV term structure & skew",
         card="Full BTC option chain (strike × expiry) with mark IV, open interest and volume, plus the "
              "derived ATM IV term structure. The 25-delta put-vs-call IV gap in a 24/7 market is the "
              "purest fear gauge available for free anywhere.",
         caveats=["A SNAPSHOT, not history — must be collected daily to become a series.",
                  "Mark IV is venue-published, not a tradeable quote; OI is per-contract.",
                  "Crypto only in this pack; SPX chains are blocked from this sandbox (see DATA_SOURCES)."],
         use_for=["crypto tail pricing", "IV term-structure inversion detection", "risk-reversal features"],
         leak_rule="Real-time snapshot."),
    dict(id="base_rates_conditional", src="data/facts/base_rates.csv", kind="base-rates",
         grade="B", title="Conditional forward-return base rates (96 rows), measured in this repo",
         card="The probability layer: given a VIX bucket / DIX quintile / GEX sign / OFR-FSI bucket today, "
              "what did SPY do over the next 5/21/63/252 days — median, mean, % positive, p10/p90, worst. "
              "This is what 'buy fear' actually means numerically, computed from our own official data.",
         caveats=["Overlapping windows: `n_eff` (~n/horizon) is the honest independent sample; several "
                  "buckets have n_eff under 30 and are anecdotes (e.g. VIX>=40 at 252d).",
                  "Conditional distributions of the MARKET, not of a strategy — no costs, no timing.",
                  "96 rows = multiple looks; treat extremes as hypotheses to hold out, not findings."],
         use_for=["prior probabilities", "sanity-checking any claimed edge", "sizing by odds"],
         leak_rule="All buckets are trailing (rolling percentile or fixed level) — usable in real time."),
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
    dict(id="event_reaction_db", src=["data/events/event_calendar_full.csv", "data/events/event_stats.csv",
                                      "data/events/EVENT_STATS.md"],
         kind="events", grade="B", title="Event calendar (2,028 events) + measured reaction statistics",
         card="Every scheduled catalyst with an exact date — FOMC (205), Treasury coupon auctions (770, "
              "2010-2024, with bid-to-cover), monthly/quarterly option expiry, month-end, quarter-end, "
              "NFP (first-Friday rule) — plus the data-triggered families people actually fear: VIX first "
              "crossing 30, and daily moves > 2.5 sigma. For each type x asset x window it reports the "
              "measured forward distribution and the |move| ratio vs a random day.",
         caveats=["NFP dates are rule-derived (~90-95% exact). CPI is deliberately absent: BLS blocks this "
                  "sandbox and a wrong date poisons an event study.",
                  "VIX_ONSET30 / SHOCK_2.5SIG are only known at that day's close, so their forward window "
                  "starts the next day — do not trade the shock close in a backtest.",
                  "Forward returns are unlevered spot moves, no costs, no execution model."],
         use_for=["pre-writing event scenarios", "event-risk gating", "surprise studies"],
         leak_rule="Scheduled events are known in advance (safe as forward features); trigger events are not."),
    dict(id="collector_store", src="data/collect/*.csv", kind="live-store",
         grade="B", title="Daily collector store — accumulating history since 2026-11-20",
         card="The output of `scripts/collect_daily.py`: 16 free key-less sources upserted daily "
              "(DIX/GEX, OFR FSI, VIX, SKEW, OKX funding + long/short, Deribit chain, econ calendar, EIA "
              "inventories, EPU, GPR, Treasury auctions + yield curve, crypto 1H candles). This is the "
              "part nobody can Google later — option chains and funding rates only exist going forward.",
         caveats=["Starts 2026-11-20: short history. Value grows with time, not with more fetches.",
                  "Collection reliability is logged in collector_log.jsonl — check it before trusting gaps.",
                  "Some files are full-history refreshes (mode=replace), others append-only."],
         use_for=["building proprietary history", "live features", "verifying data availability"],
         leak_rule="Real-time snapshots; a snapshot taken intraday must be timestamped as such."),
    dict(id="news_headlines", src=["data/news/headlines.csv", "data/news/news_pressure.csv",
                                    "data/news/feed_status.json"],
         kind="news", grade="A", title="Multi-outlet news headlines with entity tags (append-only)",
         card="RSS from 15 outlets (BBC, Al Jazeera, WSJ, FT, CNBC, Investing, Seeking Alpha, MarketWatch, "
              "Fed, ECB, Bangkok Post) de-duplicated by URL hash, each headline tagged with the assets / "
              "countries / themes it mentions. Plus a daily numeric pressure series (headline counts per "
              "entity) so a quant layer has a feature without paying for sentiment.",
         caveats=["Counts are NOT sentiment: more headlines about oil says nothing about direction.",
                  "RSS gives the last ~20-60 items per outlet, so history starts when collection starts.",
                  "Entity tagging is regex and will miss synonyms; a local LLM should re-read the titles."],
         use_for=["narrative context for a local LLM", "attention/pressure features", "event confirmation"],
         leak_rule="A headline is known only when published; the collector timestamps harvest time."),
    dict(id="levels_support_resistance", src=["data/levels/levels_latest.csv", "data/levels/levels_history.csv",
                                              "data/levels/MANIFEST_LEVELS.json"],
         kind="technical", grade="B", title="Support/resistance and market structure, 28 instruments",
         card="Every level class turned into a number with a stated rule: prior day/week/month high-low-close, "
              "fractal swing points, classic floor-trader pivots, Bollinger envelope, ATR, 52-week extremes, "
              "and a volume/time-profile point of control with value-area edges. Levels are where stops and "
              "option strikes cluster — i.e. where price reacts.",
         caveats=["Volume profile is approximated from daily bars (no tick data exists for free); treat POC "
                  "as ±0.15 ATR.",
                  "These are reference points, not signals: no level rules have beaten a null in this repo yet."],
         use_for=["stop/target placement", "entry gating", "explaining intraday reaction levels"],
         leak_rule="All levels use data up to the prior close."),
    dict(id="vol_term_structure", src=["data/collect/vol_term_structure.csv",
                                      "data/collect/vol_stress_features.csv",
                                      "data/collect/vol_term_status.json",
                                      "data/facts/VOL_REGIME_BASE_RATES.md",
                                      "data/facts/vol_regime_base_rates.csv"],
         kind="volatility", grade="A",
         title="CBOE volatility term structure + derived stress features + regime base rates",
         card="VIX, VIX1D, VIX9D, VIX3M, VVIX and SKEW pulled daily from CBOE, with the derived curve "
              "features that actually carry information: slope_3m = VIX/VIX3M (>1 inverted = stress is "
              "now), slope_9d = VIX9D/VIX (>1 front-end panic), VVIX percentile (vol-of-vol), and an "
              "inversion-onset flag. Ships with VOL_REGIME_BASE_RATES.md: forward 5/21/63-day SPY return "
              "distributions conditioned on each curve state, with n_eff for every cell.",
         caveats=["VIX3M starts 2009-09, VIX9D 2011-01, VIX1D 2022-05 — the deep history is VIX only.",
                  "The curve states predict VARIANCE well (EXP-0015: forward-onset AUC 0.746) but an "
                  "exposure overlay built on them does NOT beat plain volatility targeting (EXP-0015 FAIL).",
                  "CBOE CSV layouts differ per file (some rows have no comma after the date) — the "
                  "fetcher parses with a regex on purpose."],
         use_for=["vol/regime conditioning priors", "gap-risk flagging", "variance forecasting"],
         leak_rule="VIX closes are stamped same-day; anything traded on them must use the next session."),
    dict(id="intraday_h1_bidask", src=["data/intraday/EURUSD_H1_bidask.csv.gz",
                                      "data/intraday/EURGBP_H1_bidask.csv.gz",
                                      "data/intraday/GBPUSD_H1_bidask.csv.gz",
                                      "data/intraday/EURCHF_H1_bidask.csv.gz",
                                      "data/intraday/USDJPY_H1_bidask.csv.gz",
                                      "data/intraday/XAUUSD_H1_bidask.csv.gz",
                                      "data/intraday/MANIFEST_H1_BIDASK.json",
                                      "data/facts/HOUR_OF_DAY_PROFILE.md",
                                      "data/facts/hour_of_day_profile.csv"],
         kind="intraday", grade="B",
         title="Hourly FX/metals with BOTH bid and ask, 2003-2026 (6 pairs, ~145k bars each)",
         card="The only free source of hourly quotes with two sides: Dukascopy chart/json3 fetched once "
              "per offer_side. Every bar carries its own measured spread, so costs are charged per bar "
              "instead of assumed. Ships with HOUR_OF_DAY_PROFILE.md — median spread and median high-low "
              "range for every hour of the UTC day, per pair, and the resulting movement-per-cost ratio.",
         caveats=["Dukascopy quotes are one broker's feed: a FLOOR, not a retail account. No commission, "
                  "no slippage.",
                  "Row layout is [ts, open, high, low, close, volume] — verified empirically; the binary "
                  "tick feed uses a different order.",
                  "Zero-volume (weekend flat) bars are dropped.",
                  "Direction is NOT tradable here: EXP-0017/0018 measured 5 hourly rules and 3 gated "
                  "variants, all fail at these spreads. Use the data for execution timing."],
         use_for=["execution timing and cost modelling", "hour-of-day risk profiles",
                  "intraday level validation", "latency studies"],
         leak_rule="Bar close is the decision point; fills happen in the next bar. Never fill on the same bar."),
    dict(id="treasury_curve_deep", src=["data/collect/treasury_yield_curve_full.csv"],
         kind="rates", grade="A",
         title="US Treasury daily yield curve, 1990 to today (9,228 days, 13 tenors)",
         card="Backfilled year by year from home.treasury.gov. This is the backbone for every carry, "
              "roll-down, curve-slope and recession-prior question — the daily collector only appended "
              "the latest row, so before this backfill the curve had 222 rows and could not support any "
              "real test.",
         caveats=["The published series is revised; it is not point-in-time. Do not use it as a "
                  "vintage-accurate macro feed.",
                  "Carry measured on ETF prices (TLT/IEF) is price-only — funds distribute monthly, so all "
                  "levels are pessimistic by roughly the coupon."],
         use_for=["term spread / carry tests", "recession priors", "bond duration sizing"],
         leak_rule="Published with a one-day lag; shift by one day before trading."),
    dict(id="okx_crypto_deep", src=["data/collect/okx_BTCUSDT_1h_deep.csv",
                                    "data/collect/okx_ETHUSDT_1h_deep.csv",
                                    "data/collect/okx_BTCUSDT_funding_deep.csv",
                                    "data/collect/okx_ETHUSDT_funding_deep.csv"],
         kind="crypto", grade="B",
         title="OKX perpetual BTC/ETH: 10,000 hourly bars + 280 funding settlements",
         card="Backfilled hourly candles (2025-09-30 onward) and the funding-rate history, which is the "
              "cleanest free measure of crypto leverage demand. Funding is the crypto analogue of carry: "
              "paying 6-7% annualised to be long perps is a crowded-long tax.",
         caveats=["Funding history depth is capped by the endpoint at ~3 months (280 settlements).",
                  "The funding endpoint needs the SWAP instrument id (BTC-USDT-SWAP); the spot id returns "
                  "code 51000. Candles use the spot id.",
                  "Hourly bars only reach back ~13 months, so no multi-cycle study is possible."],
         use_for=["crypto carry/leverage-crowding features", "hour-scale execution studies"],
         leak_rule="Candle ts is the bar OPEN time; funding settles every 8h (00:00/08:00/16:00 UTC)."),
    dict(id="broad_cross_section", src=["data/broad/*.csv"], kind="prices",
         grade="C", title="Broad research panel: 68 ETFs across sectors, countries, credit, commodities",
         card="The wide book: 11 US sectors, 16 country/EM ETFs, 10 credit/rates, 10 commodities, FX proxies, "
              "vol wrappers, crypto proxies and benchmarks — 362k daily rows total. This is where "
              "cross-sectional questions get statistical power (rank-and-hold tests need 50+ assets, not 5).",
         caveats=["ETFs inherit tracking/fee/liquidity distortions; they are proxies, not the underlying.",
                  "Yahoo closes for FX proxies are a different snapshot than official fixes (see PITFALLS).",
                  "Survivorship: only funds alive today are in the list."],
         use_for=["cross-sectional factor tests", "rotation studies", "regime breadth measures"],
         leak_rule="Daily close; use next session for fills."),
    dict(id="technical_indicators", src=["data/technicals/latest.csv",
                                        "data/technicals/history_wide.csv.gz",
                                        "data/technicals/MANIFEST_TECH.json"],
         kind="technical", grade="B",
         title="One canonical indicator stack: 209 instruments x 40 indicators, daily",
         card="SMA/EMA, RSI14, MACD(12,26,9), Bollinger(20,2) with %B and width, ATR14 and ATR%, ADX14 with"
              " +DI/-DI, Stochastics %K/%D, OBV slope, Donchian20 + position, Keltner20, z-score, returns"
              " 1/5/21/63d, realised vol 20/63d, distance to 52-week extremes, volume z-score. One row per"
              " instrument for the latest bar, plus a wide history for the 94 ETFs/indices.",
         caveats=["Volume-derived columns are NaN where the source file has no volume — that is 'no data', "
                  "not zero.",
                  "Wilder smoothing is implemented manually; expect small differences from TA-Lib.",
                  "These are indicator VALUES, not signals: EXP-0001 rejected 7 classic TA families on 24 "
                  "instruments against a permutation null."],
         use_for=["screener joins", "level/stop sizing", "consistent definitions across studies"],
         leak_rule="Computed on the close; a value from this table applies to the next bar."),
    dict(id="us_stock_panel", src=["data/stocks/*.csv", "data/stocks/MANIFEST_STOCKS.json"],
         kind="prices", grade="C",
         title="115 US single-stock daily series (10 years, Yahoo chart v8)",
         card="The largest companies by market cap, daily OHLC + adjusted close + volume. Exists so the "
              "fundamental layer and the screener have prices to attach to, and so cross-sectional tests "
              "are not limited to ETFs.",
         caveats=["Survivorship: this is today's list, so any cross-sectional result on it is biased up.",
                  "10-year history ceiling per symbol.",
                  "`close` is the raw print and `adjclose` is split/dividend adjusted — never mix them "
                  "inside one study."],
         use_for=["fundamental-price joins", "earnings reaction studies", "screening"],
         leak_rule="Daily close; fill next session. Do not use adjclose for a level, or close for a return "
                   "series across a split."),
    dict(id="sec_filings_fundamentals", src=["data/sec/company_tickers.csv", "data/sec/filings.csv",
                                             "data/sec/fundamentals.csv", "data/sec/MANIFEST_SEC.json"],
         kind="fundamental", grade="A",
         title="SEC filings + as-filed XBRL financial statements (top 60 US companies)",
         card="10,399 ticker-to-CIK mappings, the last 25 filings per covered company (10-K, 10-Q, 8-K, "
              "Form 4), and 56k XBRL observations for revenue, net income, diluted EPS, assets, "
              "liabilities, equity, cash, operating cash flow and long-term debt, with the FILING date on "
              "every row.",
         caveats=["As-filed but revision-free: no vintages, so fundamental backtests carry restatement bias. "
                  "Always use `filed` as available_from, never `period_end`.",
                  "Banks/insurers often lack a Revenues tag -> NaN, not wrong.",
                  "Form 4 rows are stored but NOT parsed into insider transactions yet (declared gap)."],
         use_for=["valuation ratios", "earnings-reaction studies", "screener joins", "insider-flow work"],
         leak_rule="A statement is known on `filed`, not on `period_end` (typically 30-60 days later)."),
    dict(id="congress_trades", src=["data/congress/ptrs_index.csv", "data/congress/congress_trades.csv",
                                     "data/congress/MANIFEST_CONGRESS.json",
                                     "research/THIRD_PARTY_REVIEW_day_trader_skill.md"],
         kind="fundamental", grade="A",
         title="US House congressional trades, parsed from Clerk PTR PDFs (6,365 transactions)",
         card="The index of every Periodic Transaction Report filed 2019-2026 (3,207 filings), plus parsed "
              "transactions from the most recent 700 PDFs: member, state/district, transaction type "
              "(purchase/sale), transaction date, NOTIFICATION date, FILING date, amount range, asset "
              "description, ticker guess and House asset-type code. Text extracted from PDFs with pypdf; "
              "the community S3 mirrors are dead, so the official documents are the only route.",
         caveats=["STOCK Act allows up to 45 days of disclosure lag: use filed_date as available_from, "
                  "never transaction_date.",
                  "Amounts are disclosure RANGES; amount_mid is an approximation, not a size.",
                  "[ST] in the description is an asset TYPE code, not a ticker — ticker_guess comes from "
                  "the (PAREN) field.",
                  "173 of 700 PDFs yielded no rows (layout variance); the manifest reports the gap.",
                  "House only; Senate eFD needs an interactive agreement and is not covered.",
                  "EXP-0019 tested this and FAILED the pre-declared bar (halves disagree: 0th vs 99.5th "
                  "percentile) — treat as raw material, not a signal."],
         use_for=["non-price information studies", "narrative context on a name",
                  "a long-run sample once the collector accumulates filings"],
         leak_rule="Known on filed_date only."),
    dict(id="insider_transactions", src=["data/sec/insider_transactions.csv",
                                          "data/sec/MANIFEST_INSIDER.json"],
         kind="fundamental", grade="A",
         title="Form 4 insider transactions, parsed from EDGAR XML (1,652 rows)",
         card="Every non-derivative transaction inside the Form 4 filings we hold: insider name, role "
              "(director/officer/10% owner), transaction date and FILING date, code (P purchase, S sale, "
              "A grant, M exercise, F tax), shares, price, dollar value and shares owned after. The only "
              "non-price information source in the pack that was collected before it was usable.",
         caveats=["Only Form 4s inside the last-25-filings window per covered company, so the panel is "
                  "short (35 purchases vs 969 sales — a real sample needs years of filings).",
                  "Use `filed` as available_from: Form 4 is filed up to 2 business days after the trade.",
                  "Grants (A) and option exercises (M) are NOT purchases; only P and S measure money flow.",
                  "No split adjustment; 172 of 748 filings could not be parsed (recorded in the manifest)."],
         use_for=["insider-cluster studies (needs more history first)", "narrative context on a name",
                  "sanity check on management behaviour"],
         leak_rule="Known on `filed`, never on `transaction_date`."),
    dict(id="stock_screener", src=["data/screener/nasdaq_all.csv", "data/screener/screener_latest.csv",
                                   "data/screener/MANIFEST_SCREENER.json"],
         kind="screener", grade="C",
         title="7,301-symbol screener with technicals and as-filed fundamentals joined",
         card="Every NYSE/Nasdaq symbol with market cap, sector, industry and country, joined to the "
              "indicator stack and to the XBRL fundamentals — with staleness columns (fund_age_days, "
              "filing_age_days) so a stale row can be rejected instead of silently trusted.",
         caveats=["Fundamental coverage is the top 60 names only; the rest carry NaN.",
                  "No composite score is provided on purpose — an untested score is a strategy in disguise.",
                  "Nasdaq's screener endpoint is unofficial and can change without notice."],
         use_for=["finding candidates for a specific question", "breadth by sector",
                  "checking whether a move had an earnings basis"],
         leak_rule="Snapshot; market cap changes every session."),
    dict(id="news_world", src=["data/news/headlines_world.csv", "data/news/news_world_pressure.csv",
                               "data/news/news_world_status.json"],
         kind="news", grade="B",
         title="Global news wire: 1,294 headlines, 425 outlets, 26 queries, 16 country editions",
         card="Google News RSS queried by topic (stock market, central bank, inflation, oil, bond yields, "
              "trade war, currency crisis, earnings surprise, banking stress, recession risk) and by "
              "country edition (US, UK, DE, FR, JP, CN, IN, BR, RU, TH, VN, ID, TR, MX, SA, ZA). Local "
              "language headlines included; entity-tagged with the same layer as the direct feeds.",
         caveats=["Unofficial endpoint: it rate-limits and drops editions without notice — every query "
                  "status is recorded in news_world_status.json.",
                  "Headlines only, no article bodies: sentiment must come from a local model reading titles.",
                  "De-duplicated by title hash, so the same story from three outlets counts once."],
         use_for=["narrative context", "country/cross-market attention", "event confirmation"],
         leak_rule="Known only when published; harvest time is recorded."),
    dict(id="macro_worldbank", src=["data/macro/wb_panel_long.csv", "data/macro/wb_latest.csv",
                                    "data/macro/MANIFEST_WB.json"],
         kind="macro", grade="A",
         title="World Bank macro panel: 22 economies x 9 indicators, 1990-2025",
         card="GDP growth, GDP, CPI inflation, unemployment, government debt, current account, lending "
              "rate, population and exports share, on one comparable definition set across 22 economies.",
         caveats=["Data lag 1-2 years and are revised: not point-in-time, use as a slow prior only.",
                  "ILO-modelled unemployment: cross-country comparability is approximate.",
                  "Newest-year values are frequently missing."],
         use_for=["country priors", "carry/funding context", "regime narratives for a local model"],
         leak_rule="Annual reference year; published in arrears, so never treat as known in real time."),
    dict(id="event_packs", src=["packs/*.json"], kind="brief", grade="B",
         title="Per-day event packs: one self-describing JSON per trading day (~35 KB)",
         card="Built by scripts/event_pack.py. For any date it assembles the calendar, a 17-instrument "
              "market snapshot (returns, realised vol, ATR, distance to MAs), the measured levels, the "
              "VIX-curve state with its conditioned base rates, carry (UST slopes, BTC funding), the "
              "headlines of a +/-N day window, and 'similar_days': the 12 nearest historical states with "
              "what actually happened over the next 5 and 21 days.",
         caveats=["similar_days neighbours come only from days strictly before the target date, but n=12 "
                  "is small: read the min/max spread, not the median.",
                  "The pack is context, not a signal file: nothing in it is a recommendation.",
                  "Levels/news only exist from the date collection started for those sources."],
         use_for=["per-day/per-event analysis by a local model", "replay studies", "explaining a move"],
         leak_rule="Every field is stamped with its as-of; a decision for date D may use data up to D-1 close."),
    dict(id="daily_briefs", src=["briefs/latest.md", "briefs/latest.json"], kind="brief",
         grade="B", title="Daily brief: the compressed state a local AI reads each morning",
         card="One small file that replaces the whole pack for daily use: current state (VIX percentile, "
              "SKEW, DIX/GEX regime, OFR stress, funding, COT extremes), the next 7 days of scheduled "
              "events, base-rate odds for the current state, support/resistance levels, the last 48h of "
              "entity-tagged headlines, hard flags, and pre-written scenario branches to pick from.",
         caveats=["It is a compression, not an analysis: it never predicts, it reports state and odds.",
                  "Regenerate with scripts/daily_brief.py after the collector runs."],
         use_for=["daily LLM context window", "event playbooks", "risk gating"],
         leak_rule="Inherits each input's lag; data_age_days states it per series."),
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
        # .gz members must be opened in binary and decompressed: opening them as text raises
        # UnicodeDecodeError (0x8b is the gzip magic) and killed a pack build once.
        opener = gzip.open if f.endswith(".gz") else open
        with opener(f, "rt", newline="") as fh:
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

    catalog = {"pack": "ALINA_DATAPACK", "version": "2.7",
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
    for rel in ["research/artifacts/cot_panel.json", "research/artifacts/event_conditional.json",
                "research/artifacts/auction_demand.json", "research/artifacts/cross_section.json", "research/artifacts/breadth_overlay.json", "research/artifacts/gex_vs_voltarget.json", "research/artifacts/vol_onset.json", "research/artifacts/bond_carry.json", "research/artifacts/fx_hourly.json", "research/artifacts/fx_hourly_sparse.json", "research/artifacts/congress_trades.json", "data/events/EVENT_STATS.md", "configs/universes.json", "data/facts/base_rates.csv", "data/facts/BASE_RATES.md",
                "data/alt/MANIFEST_ALT.json", "research/artifacts/universe_screen.json", "reports/strategy_comparison.json",
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
                "IDEAS_TO_TEST.md", "GLOSSARY.md", "HOW_TO_BACKTEST.md",
                "DECISION_INPUTS_ATLAS.md", "WHAT_THE_BOT_NEEDS.md", "OPERATING_MANUAL.md"):
        s = os.path.join(ROOT, "datapack_src", doc)
        if not os.path.exists(s):
            s = os.path.join(ROOT, "research", doc)          # atlas + plan live in research/
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
    zpath = os.path.join(DIST, "ALINA_DATAPACK_v2.7.zip")
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
