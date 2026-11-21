# ALINA Market Lab — Next Actions

Last Updated UTC: `2026-11-21` (`v2.22`)

## 1. Concluded Research & Operational Mode
1. **Core Open-Data Research Backlog Complete (`EXP-0001..0048`, `55` Hypotheses):** All internal datasets plus all 5 major free institutional/no-KYC online sources (`19-coin spot + 4.9y UM OI/L-S`, `FRED Net Liquidity`, `20y CFTC Disaggregated COT`, `63y Ken French FF5+Mom`, and `54` bulk SEC Form 13F zips `2013q2–2026q3`) have been ingested cleanly and tested without lookahead or survivorship bias.
2. **Active Defensive Monitoring (`EXP-0033` + `EXP-0041` + `EXP-0043`):**
   - Run `python3 scripts/collect_daily.py`, `python3 scripts/risk_radar.py`, and `python3 scripts/build_dashboard.py` on schedule to monitor Equity `VolTarget12% x RiskMeta(23f) -> BIL` and Crypto `TrendEns/SMA50 x VolTarget25% -> EFFR` plus 19-coin market breadth (`>SMA50`).
3. **Optional Future External Additions (User Gemini Plus Link Sourcing / Institutional Feeds):**
   - Any newly sourced external direct dataset (e.g., genuine corporate credit/option skew surface, intraday L2/orderbook, or historical institutional futures/option tick data) must undergo the exact same pre-registered Phase C survival gates (OOS, realistic cost/slippage, survivorship audit, circular/ticker permutation `>=95%/Bonferroni`) before altering `AlinaRiskGovernor.mq5` (`SIG_NONE` / `MODE_PAPER`).
   - Configure `TELEGRAM_BOT_TOKEN` & `TELEGRAM_CHAT_ID` in GitHub Secrets when ready for live push alerts (`scripts/telegram_bot.py --dry-run` verified).
