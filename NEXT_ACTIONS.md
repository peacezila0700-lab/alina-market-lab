# ALINA Market Lab — Next Actions

Last Updated UTC: `2026-11-21` (`v2.20`)

## 1. Monthly / Daily Quota-Aware Cloud Continuation (No KYC, Personal Research Only)
1. **Optional Remaining Delisted S&P 500 Tail (`Tiingo` remaining monthly quota: `410/500` symbols):**
   - `70` clean delisted symbols (`68` SEC XBRL) are now stored and already demonstrated monotonic collapse of accrual alpha (`EXP-0034`, `+0.729 -> +0.453`). Any additional `~18` historical S&P 500 deletions (`2015–2018` M&A like `DISCK`, `VIAB`, `VIAC`, `CSRA`) may be appended in future months (`<= 45/hr`) strictly for archive completeness rather than alpha rescue.
2. **Thai `.BK` Long History Decision (`EODHD Free = 1-year cap`):**
   - EODHD Free truncates `.BK` & `.INDX` CSVs to trailing 1 year (`241` bars). For 10–20 year survivorship-free SET backtests, evaluate EODHD All-World (`$19.99/mo` personal) or SETSMART/broker exports rather than burning daily free calls on `.BK`.
3. **Optional Telegram & Automated Daily Refresh (Deferred per User):**
   - When ready for push notifications, configure `TELEGRAM_BOT_TOKEN` & `TELEGRAM_CHAT_ID` in GitHub Actions Secrets (`scripts/telegram_bot.py --dry-run` verified). Add `finra_regsho_market_daily.csv` daily fetch into `scripts/collect_daily.py` if daily automated Panel 9 updates are desired.
4. **Keep Phase C Kill Point Locked:**
   - Maintain `AlinaRiskGovernor.mq5` at `SIG_NONE` / `MODE_PAPER` and Phase D ML **PARKED**. Never commit `.env` or API keys to git or Google Drive archives (`data/LICENSE_SCOPE.md`).
