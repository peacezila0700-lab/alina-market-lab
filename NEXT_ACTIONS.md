# ALINA Market Lab — Next Actions

Last Updated UTC: `2026-11-21`

## 1. Immediate User Actions (Mobile Alerts & Optional MQL5 Manual Expansion)
1. **Configure GitHub Repository Secrets** (`Settings -> Secrets and variables -> Actions`):
   - `TELEGRAM_BOT_TOKEN` (from `@BotFather`)
   - `TELEGRAM_CHAT_ID` (your numeric Telegram user ID — enforces owner allowlist in `telegram_bot.py`)
   - *(Optional)* `GEMINI_API_KEY` or `GROQ_API_KEY` (for Thai/English free-text Q&A in Telegram via `ask.py`)
2. **Trigger `ALINA Daily Pipeline (Phone & Cloud)`** once manually via GitHub Actions `Run workflow` to confirm live Telegram delivery of `Risk Radar + dashboard/alina_today.html`.
3. *(Optional, Residential PC/Browser)* Follow `scripts/BATCH5_MQL5_COLAB_GUIDE.md` if you want to pull any of the `201` IP-blocked `mql5.com` archives manually into `data/ea_kb/sources_batch5_manual/`.

## 2. Next Engineering & Research Priorities (Strict Phase C / Risk-Engineering Scope)
1. **Integrate Calibrated Stationary Meta-Labeling into Daily Risk Radar (`Workstream D + Task 3`):**
   - Wire the Task 3 stationary `252d`-z/delta feature pipeline (`ofr_fsi_z252`, `d_fed_63`, `gpr_z252`, `VIX` term structure, `HAR`) and expanding purged Platt `HGBC` (`target_vol_onset` / `target_tail_stress` / `TB_NonDirStress`) as an informational probability panel (`ECE ~ 0.04–0.06`) inside `scripts/risk_radar.py`, cleanly replacing static heuristic throttles. *(Strictly monitoring & offline sizing only — never auto-trades.)*
2. **Eliminate Survivorship Bias on SEC PIT (`Workstream A1 Follow-Up`):**
   - Pull delisted/historical US-GAAP CIKs + matched delisting returns before drawing any portfolio conclusions on `F_NEG_ACCRUALS`.
3. **Add `test_workstreams.py` & Integrity Regression Checks for Batch 6 + `EXP-0030`:**
   - Keep `Batch 6` license isolation (`GPL-3.0` vs `MIT`/`Apache-2.0` vs quarantined `UNSPECIFIED`) enforced in `data/ea_kb/batch6_provenance_audit.json` if adding future Batch 7 execution/risk libraries (`EarnForex/AutoTrading-Scheduler`, `EarnForex/Spread`, `quantopian/empyrical`/`pyfolio`).
4. **Calendar & Universe Maintenance:**
   - Patch `econ_calendar` URL fallback (`26/27 -> 27/27`) and restore Yahoo fallback for `SET_TH` (`^SET.BK` returned `1` bar on `2026-11-21`).
5. **Preserve Phase C Kill Point Rules:**
   - Keep `AlinaRiskGovernor.mq5` at `SIG_NONE` / `MODE_PAPER` and Phase D ML **PARKED**. Do **NOT** deploy live or demo capital unless an independent, survivorship-free, non-directional-risk-checked or post-cost-positive hypothesis clears every pre-registered OOS + permutation bar.
