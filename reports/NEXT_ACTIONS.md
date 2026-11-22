# ALINA Market Lab — Next Actions

Last Updated UTC: `2026-11-22` (`v2.23`)

## 1. Concluded Research & Operational Mode
1. **Institutional Public Catalog Backlog Complete (`EXP-0001..0054`, `64` Hypotheses):** Every internal dataset plus all accessible datasets in `Institutional Quant Public Datasets Catalog.md` (`CoinMetrics`, `DeFiLlama`, `CFTC Crypto COT`, `Forex Factory`, `Philly Fed SPF`, `55y CRSP-reconciled PIT S&P 500`, `Options IV Surface`, `SET50/TFEX S50 1m`, `S&P 500 Earnings Transcripts`, `100% PIT SEC XBRL Buybacks`, `Zero-Truncation SEC 8-Ks`, `Deep Sea Freight PPI`, alongside `v2.22`'s `19-Coin Crypto`, `Net Liquidity`, `Commodity COT`, `Ken French 63y`, and `SEC 13F`) has been ingested cleanly and Phase-C audited without lookahead, survivorship, split-basis, or archive-truncation errors.
2. **Active Defensive Monitoring (`EXP-0033` + `EXP-0041` + `EXP-0043`):**
   - Run `python3 scripts/fetch_universe.py`, `python3 scripts/collect_daily.py`, `python3 scripts/risk_radar.py`, and `python3 scripts/build_dashboard.py` on schedule to monitor Equity `VolTarget12% x RiskMeta(23f) -> BIL` and Crypto `TrendEns/SMA50 x VolTarget25% -> EFFR` plus 19-coin breadth (`>SMA50`).
3. **Optional Future External Additions:**
   - Any newly sourced paid/institutional feed (e.g., proprietary L2 orderbook, corporate CDS/loan spreads, or true survivorship-free single-stock intraday tick data) must pass the exact same pre-registered Phase-C falsification standards (PIT zero-leak, unadjusted/split-matched scaling, full archive pagination, realistic slippage, permutation `>=95%`) before touching `AlinaRiskGovernor.mq5` (`SIG_NONE` / `MODE_PAPER`).
   - Configure `TELEGRAM_BOT_TOKEN` & `TELEGRAM_CHAT_ID` in GitHub Secrets when ready for live push alerts (`scripts/telegram_bot.py --dry-run` verified).
