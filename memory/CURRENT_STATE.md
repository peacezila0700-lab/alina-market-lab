# CURRENT STATE — 2026-11-20 (after B1/B3/B4)

## Focus
Data + code + experiments for a downstream AI. App frozen. Two books: 24-instrument research
universe + 5-instrument execution universe (EURUSD, EURGBP, EURCHF, GBPUSD, GOLD — the cheapest
measured spreads). Promotion rule in `configs/universes.json`.

## Shipped this session
- **B1 event DB** `data/events/event_calendar_full.csv` — 2,028 events, 8 types: FOMC 205,
  Treasury coupon auctions 770 (with bid-to-cover, 2010–2024), OPEX 264, month-end 264,
  quarter-end 88, NFP-rule 264, VIX_ONSET30 73, SHOCK_2.5SIG 159. Stats in `event_stats.csv` +
  `EVENT_STATS.md`.
- **B3 collector** `scripts/collect_daily.py` — 16/16 free key-less sources, upsert + log.
  First run: 39,087 rows in `data/collect/`. Run daily; value is the accumulation.
- **B4 COT panel** `scripts/test_cot_panel.py` → **EXP-0009 FAILS** (β=+0.00047, clustered t=0.16,
  R²=0.000 in-sample; OOS t=−0.56). Hypothesis H12 closed in BOTH directions.
- Pack **v1.3** uploaded: 8.2 MB, 232 files, 26 datasets, id `1MQ7ioUcr-yyN67F_yFT_Yw0D7slpUlN8`.
  v1.2 trashed. Local `pack/` deleted after upload (rebuild with `scripts/build_datapack.py`).

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
