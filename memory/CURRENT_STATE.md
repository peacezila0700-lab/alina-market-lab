# CURRENT STATE — 2026-11-20 (v2.1, after EXP-0014)

## Focus
Data + code + experiments for a downstream AI. App frozen. Two stacked universes: 24-instrument
research panel + 5-instrument execution book (EURUSD, EURGBP, EURCHF, GBPUSD, GOLD — cheapest measured
spreads), plus a 68-ETF cross-section for statistical power.

## Shipped this session (v2.1)
- **News** `scripts/fetch_news.py` → 294 headlines / 15 feeds, entity tags, per-day pressure counts.
- **Levels** `scripts/build_levels.py` → 28 instruments: pivots, prior D/W levels, value areas, ATR.
- **Broad panel** `scripts/fetch_broad_panel.py` → 68 symbols / 362,836 rows / 38 MB.
- **Daily brief** `scripts/daily_brief.py` → `briefs/latest.{json,md}` — the entry file for the local
  AI (~1.5k tokens: state, 7-day calendar, base rates, levels, 48h headlines, flags, scenario branches).
- **EXP-0010..0014, all FAIL** (event-conditional, auction demand, cross-section, breadth overlay,
  gamma-vs-vol-targeting). Full text in `research/EXPERIMENT_LOG.csv` + `research/artifacts/`.
- **`datapack_src/OPERATING_MANUAL.md`** — cron lines, the daily loop, what never to rebuild.
- **`PITFALLS.md` #11–14** — the four null-design traps found this session (static null, mask copies,
  shift-null vs vol targeting, sizing vs signal).
- Pack **v2.1**: 34 datasets / 328 files / 17.5 MB. Upload to Drive pending rate limit at time of
  writing; v2.0 is live as `1AX6goRuhPCEWu8fPrTJPFQwy1lO2hT-s` until v2.1 replaces it.

## The two lessons that matter for the next session
1. **Scheduled events do not move the tape more than a random day** (|move| 1.09x for FOMC, 1.33x for
   NFP on bonds). Only crisis onset does (1.65–1.75x). Build onset detectors, not calendars.
2. **State variables move volatility, not expected return.** Overlays cut drawdown (−27% vs −51%) but
   not CAGR, and the gamma overlay is indistinguishable from plain vol targeting. Use them for size.

## Measured highlights (do not re-derive)
- FOMC day |SPY move| is only **1.09×** a random day (TLT 1.15×) — the meeting matters far less
  than the narrative suggests. NFP (rule) hits bonds harder: TLT 1.33×.
- OPEX day SPY mean −0.170%, only **42.6% positive**; month-end −0.045% / 45.1% positive.
- Treasury auction days are *calmer* than average (SPY |move| 0.88×).
- VIX first crossing 30: SPY same-day median +0.60%, forward 5d mean +1.03%.
- SHOCK (>2.5σ) days: d5 mean −0.02% but median +0.437% — the mean is dragged by 2008/2020.

## Verified / not verified
- Free intraday: OKX 1H/1m crypto candles work with deep history (BTC/ETH to ~2020). Dukascopy
  **1MIN is now 403** (1HOUR still OK). Yahoo 5m restricted (422). No free real-time feed → an
  hour-level bot is only realistic on crypto, or on FX with hourly bars and pessimistic latency.
- EA still never compiled. Governor logic unit-tested 21/21.

## Next
1. Wire the collector to a daily schedule (cron) — the store is the moat.
2. Event-conditional signal tests (the event DB exists now; nothing has been tested against it).
3. Auction demand (bid-to-cover z) → forward bond/equity returns; data is in hand.
