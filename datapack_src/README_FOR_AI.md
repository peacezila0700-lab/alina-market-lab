# ALINA DATAPACK v1 — read this first (≈700 tokens, saves you thousands)

## What this is
A self-contained research base built by an agent over ~10 sessions, for an AI trading system to
consume **without re-searching the internet**. It contains market data, positioning data,
volatility data, measured trading costs, calendars, an attention proxy, a catalogue of 332 free
EAs, and **every experiment run here with its verdict**.

## The one thing you must know
**No validated edge was found.** 168 screen tests, 144 free-EA family tests, 8 pre-registered
experiments -> all rejected or failed hold-out. One apparent Sharpe 1.72 was traced to a
look-ahead bug in this repo's own code. Treat every number here as *evidence*, not as a strategy.

## How to use this pack efficiently
1. Read `catalog.json` — each dataset has schema, rows, coverage, sha256, a 2-row preview,
   caveats, a `leak_rule`, and a grade. Decide from the catalog; only then open the CSV.
2. Read `results/experiments.jsonl` — 8 experiments, machine-readable. **Check here before
   testing any idea**: if it is in the list, it is already dead.
3. Read `knowledge/PITFALLS.md` before writing any backtest code. It will save you from the
   three bugs that produced every fake edge in this repo.
4. `cards/<dataset>.md` — 150–250 words per dataset if you need prose instead of JSON.

## Grades (trust level)
- **A** = official primary source (ECB, CFTC, CBOE, Federal Reserve). Use freely.
- **B** = computed here with a documented method (spreads, screens, verdicts). Use with the stated caveat.
- **C** = third-party, shape only. **Never** use for absolute levels or returns (Yahoo FX).

## Hard rules (violating these recreates known failures)
1. **Lag every position one bar.** `pnl[t] = pos[t-1] * ret[t]`. This bug alone invented a
   30% CAGR that did not exist.
2. **Charge costs on every position change**, using `data/spreads_measured_dukascopy` for FX.
   A wrong cost assumption flipped a verdict in this project: EURUSD is 0.3 pip on ECN,
   EURSEK is 48 pips.
3. **Use `available_from`, not `report_date`,** for COT (Tuesday as-of, Friday public).
4. **Never use Yahoo FX returns** (correlation with official fixes: 0.38–0.52). Use
   `fx_official_ecb_daily`.
5. **Report a null.** Every result needs a turnover-matched random control; otherwise you are
   measuring luck. Random selection loses ~0.3 Sharpe after costs — that is the sanity check.
6. **Never martingale.** 5 of 5 instruments in the grid/doubling test were wiped.

## What is missing / what to add next
Blocked sources (verified dead): FRED, BIS API, GDELT API (429), CBOE put/call ratio CSVs,
OECD SDMX, RBNZ, Stooq, Yahoo H1 beyond 730 days. See `knowledge/DATA_SOURCES.md` for the full
live/dead map with the endpoint patterns that DO work — that file alone saves hours of probing.

## Thai note (for the owner)
ถ้าให้ AI ตัวอื่นอ่าน pack นี้: บอกมันให้อ่าน `knowledge/WHAT_FAILED.md` และ `PITFALLS.md` ก่อน
อย่าเชื่อ Sharpe ตัวเลขไหนในชุดนี้ว่าเป็น edge — ทุกตัวถูกทดสอบแล้วและล้ม งานที่เหลือคือหาข้อมูล
ใหม่/ทดสอบไอเดียใหม่ ไม่ใช่ทำของเก่าให้สวยขึ้น
