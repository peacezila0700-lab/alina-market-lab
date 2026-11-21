# ALINA Market Lab — Next Actions

Last Updated UTC: `2026-11-21`

## 1. Immediate User Actions (Outside Sandbox — Required for GitHub & Telegram)
1. **Push Local Bundle `v2.18` to GitHub `main`** *(sandbox has no GitHub connector or push token)*:
   Download `ALINA_LAB_v2.18.bundle` from `/home/user/exports/` or `ALINA_DATAPACK_v2.18_DELTA.zip` on Google Drive and run:
   ```bash
   git fetch ALINA_LAB_v2.18.bundle HEAD:main
   git push origin main
   ```
2. **Configure GitHub Repository Secrets** (`Settings -> Secrets and variables -> Actions`):
   - `TELEGRAM_BOT_TOKEN` (from `@BotFather`)
   - `TELEGRAM_CHAT_ID` (your personal numeric Telegram user ID)
   - *(Optional)* `GEMINI_API_KEY` or `GROQ_API_KEY`
3. **Trigger `ALINA Daily Pipeline (Phone & Cloud)`** once via GitHub Actions `Run workflow` to verify live Telegram delivery of the updated `13 KB` `dashboard/alina_today.html` + calibrated Risk Radar.

## 2. Next Research & Engineering Priorities (Strict Phase C Scope)
1. **Eliminate Survivorship Bias on SEC PIT (`BLK-005` / `Workstream A1`):**
   - Pull delisted/historical US-GAAP CIKs + matched delisting returns before drawing any portfolio conclusions on `F_NEG_ACCRUALS`.
2. **Calendar & Universe Maintenance:**
   - Patch `econ_calendar` URL fallback (`26/27 -> 27/27`), ingest 2027 `FOMC`/`ECB`/`BoE` calendars once released in Dec 2026, and maintain Yahoo `SET_TH` fallback (`^SET.BK` returned `1` bar).
3. **Optional EA KB Batch 7 (`MIT` / `Apache-2.0` / `201` MQL5 Manual):**
   - Pull remaining permissive risk/calendar modules (`EarnForex/AutoTrading-Scheduler`, `EarnForex/Spread`, `quantopian/pyfolio` & `empyrical`) or run `scripts/BATCH5_MQL5_COLAB_GUIDE.md` from a residential IP.
4. **Keep Phase C Kill Point Locked:**
   - Maintain `AlinaRiskGovernor.mq5` at `SIG_NONE` / `MODE_PAPER` and Phase D ML **PARKED** until an independent, survivorship-free, post-cost hypothesis clears every pre-registered bar.
