# CURRENT STATE — 2026-11-20 (v2.3, after EXP-0018)

## Focus
Data + code + experiments for a downstream AI. App frozen. Stacked universes: 24-instrument research
panel, 5-instrument execution book, 68-ETF cross-section, CBOE term structure, 36-year Treasury curve,
and now 23 years of hourly FX with BOTH bid and ask.

## Drive (live)
- **v2.3 `1NYWjvtc8wmTMpLOXUulkTSJwPD7tGDpp`** — 39 datasets / 371 files / 39.7 MB. Current.
- v2.2, v2.1, v2.0 and older all trashed. Local `pack/` deleted after each upload.

## Shipped this session (chronological)
1. News (294/15 feeds), levels (28 instr), 68-ETF panel, daily brief → v2.0/2.1
2. EXP-0010..0012 (events, auctions, cross-section) → all FAIL
3. EXP-0013/0014 (breadth overlays, gamma vs vol targeting) → FAIL
4. CBOE term structure + VOL_REGIME_BASE_RATES + Treasury 1990-2026 backfill (9,228 rows) + OKX deep;
   EXP-0015 (onset: AUC 0.746 but loses to vol targeting) / EXP-0016 (bond carry) → FAIL → v2.2
5. **Dukascopy hourly bid+ask, 6 pairs, 2003-2026, ~145k bars each** + HOUR_OF_DAY_PROFILE;
   EXP-0017 (5 hourly rules, net Sharpe −0.4..−10.8) / EXP-0018 (gating, breakeven multiple 0.03-0.29)
   → FAIL → v2.3

## Tally
18 experiments, 168 screen, 144 family, 59 COT, 0 validated edges. Every failure is in
`WHAT_FAILED.md` with the reason; every trap is in `PITFALLS.md` (#1-#17).

## The three sentences that carry the whole project
**Variance is forecastable, direction is not.** State variables cut drawdown (gamma −27% vs −51%, bond
carry halves 2022-26 losses) but never add mean return per unit of exposure, and the one real hourly FX
edge (+0.19 bp/hour gross reversal) is smaller than the 0.34 bp/hour spread it must cross.

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
