# INCIDENT LOG

## QR-001 — Rate-limited days were recorded as "empty", not "failed"
- **Date/time (UTC):** 2026-11-20 ~15:30
- **Component:** `scripts/ingest_duka.py` v1
- **What happened:** Dukascopy started returning HTTP 429. v1 lumped 429 with "404 no data",
  logged `empty`, and advanced the state file. 48 days were marked complete with **0 rows** written.
- **Impact:** data loss was **silent** — a later session would believe 2025-11-01..12-26 was ingested.
  No dataset was published, no analysis used it, so no downstream result is affected.
- **Root cause:** no distinction between transport failure and genuine absence of data;
  no global rate limit; state advanced even when the fetch failed.
- **Fix (v2, same file):**
  1. explicit status per fetch: OK / MISSING(404) / RATE_LIMITED(429) / ERROR
  2. global token bucket, default 0.8 req/s (`DUKA_RPS` env)
  3. RATE_LIMITED/ERROR → job **stops**, state **not advanced** (resume-safe)
  4. rows written only when bars were actually decoded
- **Verified:** 429 reproduced with curl (5/5 requests), block is source-side.
- **Lesson (project rule):** a day is "done" only when an artifact proves it. Absence of data
  must be an explicit, recorded fact — never an inference from a failed request.

## QR-002 — Same-bar position in the screen/portfolio P&L: a look-ahead that faked an edge
- **Date/time (UTC):** 2026-11-20 ~19:10
- **Component:** `scripts/screen_universe.py` (`pnl_of`), `scripts/portfolio_donchian.py` (`pnl_series`)
- **What happened:** the position array was multiplied by the **same-bar** return:
  `pnl[i] = pos[i] * ret[i]`. But `pos[i]` is computed from data up to and including
  close *i*, while `ret[i]` is the move that already happened *i-1 → i*. The strategy
  was therefore allowed to hold today's position for yesterday→today's move.
- **Impact (large):** the 168-test universe screen published in the previous commit is
  **invalid**. It showed DONCHIAN_55 beating 95–100% of random nulls on almost all 24
  assets and a DONCH_30 portfolio at **Sharpe 1.72 / CAGR 30.7%**. After the one-bar lag
  the same code gives **Sharpe 0.20–0.37 / CAGR 1.9–4.9%**, i.e. **worse than the
  equal-weight buy & hold benchmark (0.70 / 11.6%)**. The "edge" was the bug.
- **Root cause:** the engine used for every prior FX experiment (`backtest_engine.py`)
  shifts the signal correctly; the new universe scripts were written separately and
  re-implemented P&L from scratch without that lag. No cross-check against the tested engine.
- **Fix:** `lag = np.r_[0.0, pos[:-1]]` in both scripts; all 168 screen results and the
  portfolio JSON regenerated. Regression test added:
  `test_position_must_be_lagged_no_lookahead` (suite now **14/14 pass**).
- **Lesson (project rule, now binding):** never re-implement P&L outside the tested engine.
  Any new script must either import `backtest_engine` or reproduce its lag and pass the
  regression test **before** reporting numbers. Screens are not results until a
  deliberately-wrong benchmark (random null) and a lag test both pass.
