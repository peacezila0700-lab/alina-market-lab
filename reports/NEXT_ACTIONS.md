# ALINA Market Lab — Next Actions

Last Updated UTC: `2026-11-21` (`v2.21`)

## 1. Concluded Research & Operational Mode
1. **Research Backlog Exhausted (`EXP-0001..0042`):** All structural, macro, fundamental, microstructure, cross-asset ETF, yield-curve/auction, and seasonal/overnight hypotheses available across ALINA's `26`-year datasets have been tested without lookahead or survivorship bias. Do not data-mine rejected directions (`H01..H43, H45`).
2. **Active Defensive Monitoring (`EXP-0033` + `EXP-0041`):**
   - Run `python3 scripts/collect_daily.py`, `python3 scripts/risk_radar.py`, and `python3 scripts/build_dashboard.py` on schedule (or GitHub Actions) to track Equity `VolTarget12% x RiskMeta -> BIL` and Crypto `TrendEns/SMA50 x VolTarget25% -> EFFR` allocations (`dashboard/alina_today.html`).
3. **Optional Future Cloud Additions:**
   - Configure `TELEGRAM_BOT_TOKEN` & `TELEGRAM_CHAT_ID` in GitHub Secrets when ready for automated push alerts (`scripts/telegram_bot.py --dry-run` verified).
   - Keep `BTC.csv` updated in `scripts/collect_daily.py` alongside `SPY.csv` so `crypto_trend_overlay` remains `FRESH`.
   - Maintain `AlinaRiskGovernor.mq5` at `SIG_NONE` / `MODE_PAPER` and Phase D ML **PARKED** unless genuinely orthogonal institutional data (e.g., broker-level L2 / options skew / new market regime) warrants a clean pre-registered hypothesis.
