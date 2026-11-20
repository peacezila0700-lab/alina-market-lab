# CURRENT STATE — 2026-11-20 (v2.2, after EXP-0016)

## Focus
Data + code + experiments for a downstream AI. App frozen. Two stacked universes: 24-instrument
research panel + 5-instrument execution book (EURUSD, EURGBP, EURCHF, GBPUSD, GOLD), plus a 68-ETF
cross-section, a CBOE volatility term structure and a 36-year Treasury curve for conditioning.

## Drive (live)
- **v2.2 `1JEWD5dbkYVIISo4JA5ts9oijnwK4GYmk`** — 38 datasets / 355 files / 19.8 MB. Current.
- v2.1, v2.0, v1.3, v1.2, v1.1 all trashed. Local `pack/` deleted after each upload.

## Shipped this session
- News (294 headlines/15 feeds), levels (28 instruments), 68-ETF broad panel (38 MB), daily brief.
- **CBOE term structure**: VIX/VIX1D/VIX9D/VIX3M/VVIX/SKEW + derived slope_3m, slope_9d, vvix_pct,
  inversion onset flag; `VOL_REGIME_BASE_RATES.md` with n_eff per cell.
- **Treasury curve backfill 1990–2026** (9,228 days, 37 year-requests) — was 222 rows before.
- **OKX deep**: 10,000 hourly bars + 280 funding settlements per symbol (endpoint caps both).
- **EXP-0010..0016, all FAIL.** 16 experiments, 0 validated edges.
- `OPERATING_MANUAL.md`, `PITFALLS.md` #11–16, `WHAT_FAILED.md` (11 rejects), register H16–H19 rejected.

## The taxonomy to carry forward (2 sentences)
**Variance is forecastable, direction is not.** Term structure predicts a vol onset (AUC 0.746, Brier
+0.168) yet an overlay built on it loses to free vol targeting by −0.28 Sharpe OOS; state variables cut
drawdown (gamma −27% vs −51%, bond carry halves 2022-26 losses) but never add mean return per exposure.

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
