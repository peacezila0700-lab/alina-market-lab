# ALINA Market Lab — Next Actions

Last Updated UTC: `2026-11-21T11:40:00Z`

## 1. Immediate User Actions (To Activate Automated Mobile Alerts & Optional MQL5 Expansion)
1. **Configure GitHub Repository Secrets** (takes ~2 minutes in GitHub Web UI -> `Settings -> Secrets and variables -> Actions`):
   - `TELEGRAM_BOT_TOKEN` (from `@BotFather`)
   - `TELEGRAM_CHAT_ID` (your personal numeric Telegram user ID — enforces owner allowlist in `telegram_bot.py`)
   - *(Optional)* `GEMINI_API_KEY` or `GROQ_API_KEY` (for Thai/English free-text Q&A in Telegram via `ask.py`)
2. **Trigger `ALINA Daily Pipeline (Phone & Cloud)`** once manually via GitHub Actions `Run workflow` to confirm live Telegram delivery of `Risk Radar + dashboard/alina_today.html` on your phone.
3. *(Optional, Residential PC/Browser)* Follow `scripts/BATCH5_MQL5_COLAB_GUIDE.md` if you wish to download any of the `201` IP-blocked `mql5.com` archives manually into `data/ea_kb/sources_batch5_manual/`.

## 2. Next Engineering & Research Priorities (Strict Phase C / Monitoring Scope)
1. **Eliminate Survivorship Bias on SEC PIT (`Workstream A1 Follow-Up`):**
   - Pull delisted/historical US-GAAP CIKs (e.g., SEC historical `companyfacts.zip` or historical S&P500/Russell additions/deletions log) + match delisting returns before drawing any portfolio conclusions on `F_NEG_ACCRUALS`.
2. **Rolling Variance Calibration on Risk Radar (`Workstream A2 Follow-Up`):**
   - Replace fixed IS Logistic/Ridge parameters with expanding quarterly probability calibration (isotonic/Platt) so `OOS Brier Skill` aligns with the `0.7212` `OOS Vol-Onset AUC`.
3. **Calendar & FiscalData Endpoint Refresh (`Workstream D Maintenance`):**
   - Patch `econ_calendar` URL fallback in `collect_daily.py` (`26/27 -> 27/27`) and ingest 2027 `FOMC`/`ECB`/`BoE` schedules once central banks publish December 2026 calendars.
4. **Stay Strictly Within Phase C Kill Point Rules:**
   - Do **NOT** deploy live capital, demo accounts, or ML rescue models on price-only strategies unless an independent, non-price, survivorship-free, post-cost, multi-regime hypothesis passes every pre-registered bar.
