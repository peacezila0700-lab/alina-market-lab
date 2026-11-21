# ALINA Market Lab — Active Blockers & Data Gaps

Last Updated UTC: `2026-11-21T11:40:00Z`

All blockers are documented factually without fabricating synthetic backfill or bypassing website controls.

| ID | Component | Severity | Root Cause (Verified) | Mitigation / Current State |
|---|---|---|---|---|
| **BLK-001** | **Phase C Kill Point** | Governance | `0/29` experiments passed pre-registered promotion rules (`EXP-0001..0029`) | **Hard Policy:** Phase D ML, Live Trading & Demo Trading remain parked. Only research, data hygiene & risk monitoring run. |
| **BLK-002** | **Telegram Workflows (`GitHub Secrets`)** | High (User Action) | `TELEGRAM_BOT_TOKEN` & `TELEGRAM_CHAT_ID` (plus optional `GEMINI_API_KEY`/`GROQ_API_KEY`) are not yet populated in GitHub Repository Secrets (`3` poller runs exited cleanly as no-ops). | Pipeline & Risk Radar dry-runs verified 100% locally. User needs to add secrets in GitHub Repo Settings -> Secrets and variables -> Actions. |
| **BLK-003** | **201 MQL5 Archives (`Batch 5`)** | High (External IP) | `mql5.com` returns `HTTP 403` to automated datacenter/cloud egress IPs. | Preserved `blocked` cleanly without WAF bypass. Provided `scripts/BATCH5_MQL5_COLAB_GUIDE.md` for legal local/browser/residential retrieval & safe import. |
| **BLK-004** | **24 External Vendor SDK Headers** | Low | Proprietary/non-GitHub SDK includes (`AZ-INVEST`, `FXBlue`, etc.) are outside public git trees. | Tagged `deferred_external_sdk` cleanly (`0` impact on `118/119` GitHub dependencies). |
| **BLK-005** | **SEC PIT Survivorship Bias (`EXP-0026`)** | High (Data Gap) | Nasdaq active screener (`top 420`) excludes bankrupt/delisted historical firms (e.g., SIVB, BBBY, older delistings). | Documented explicitly as a caveat in `EXP_0026_SEC_PIT_300PLUS.md`. Delisted SEC CIK list needed for true unconditional equity testing. |
| **BLK-006** | **Binance (`451`) & Bybit (`403`) + OKX `93d` Cap** | High (API Cap) | Binance FAPI returns HTTP `451`; Bybit returns HTTP `403`; OKX public `funding-rate-history` truncates at ~`93` days (`280` 8h rows). | Used 2.9y Deribit 1H (`25,284` rows) as primary crypto dataset; documented OKX 93d gap; never fabricated missing history. |
| **BLK-007** | **FX Retail Broker Historical Swap Curves** | Medium (Data Gap) | No free historical retail broker overnight swap-point archive over `2003–2026`. | Used official CB rates (`ECB`, `BoE`, `NYFed EFFR`) bounded by explicit `[0.00, 0.25, 0.50]` pips/night retail swap-markup sensitivity (`EXP-0028`). |
| **BLK-008** | **`econ_calendar` & `^SET.BK` Daily Yahoo** | Low | `collect_daily.py` logged `1` HTTP `404` on `econ_calendar` next-week feed (`26/27` OK); Yahoo `^SET.BK` exposes only `1` historical bar. | `event_calendar_full.csv` + `26` universe tickers cover FOMC/macro; `SET_EW.csv` (`64` SET stocks) covers Thai index cleanly. |
| **BLK-009** | **ECB/BoE Scheduled Dates Post-Dec 2026** | Low (Future) | `event_calendar_full.csv` covers FOMC/CB dates through end-2026; 2027 dates not yet published/ingested. | Warning emitted inside `risk_radar.py` (`calendar_7d` panel) until 2027 central bank calendars are published. |
