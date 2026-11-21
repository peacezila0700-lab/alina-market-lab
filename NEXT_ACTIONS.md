# ALINA Market Lab — Next Actions

Last Updated UTC: `2026-11-21` (`v2.19`)

## 1. Monthly / Daily Quota-Aware Cloud Continuation (No KYC, Personal Research Only)
1. **Expand Delisted US Equity Sample (`Tiingo` remaining monthly quota: `455/500` symbols):**
   - `137` historical S&P 500 removals (`>= 2015`) matched in `data/tiingo/supported_tickers.csv.gz`, of which `30` are already pulled in `data/stocks_delisted_tiingo/`. Batch the remaining `~107` S&P 500 delisted names (`<= 45/hr` pacing) + match their SEC EDGAR CIKs to expand `EXP-0032` past `400+` firms.
2. **Thai `.BK` Long History Decision (`EODHD Free = 1-year cap`):**
   - EODHD Free truncates `.BK` & `.INDX` CSVs to trailing 1 year (`241` bars). For 10–20 year survivorship-free SET backtests, evaluate EODHD All-World (`$19.99/mo` personal) or SETSMART/broker exports rather than burning daily free calls on `.BK`.
3. **Optional Telegram Integration (Deferred per User):**
   - When ready to turn on daily push notifications, configure `TELEGRAM_BOT_TOKEN` & `TELEGRAM_CHAT_ID` in GitHub Actions Secrets (`scripts/telegram_bot.py --dry-run` already tested).
4. **Keep Phase C Kill Point Locked:**
   - Maintain `AlinaRiskGovernor.mq5` at `SIG_NONE` / `MODE_PAPER` and Phase D ML **PARKED**. Never commit `.env` or API keys to git or Google Drive archives (`data/LICENSE_SCOPE.md`).
