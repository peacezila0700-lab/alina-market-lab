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
