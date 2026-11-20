# PRE-REGISTRATION AMENDMENT 1 — H09 panel P1 was defective

**Filed after the first run of EXP-0005, before re-running. No result from the replacement panel
has been seen.** The failed-run numbers are kept and published; nothing is deleted.

## What happened

`docs/PREREG_H09.md` fixed P1 "FX8" as EURUSD, EURGBP, EURCHF, AUDUSD, AUDNZD, AUDCAD, AUDCHF,
AUDEUR, described as "ECB / RBA official daily, 1999".

That description was **wrong about coverage**, and I did not verify it before registering:

| Instrument (official file) | Rows | Actual span |
|---|---:|---|
| EURUSD, EURGBP, EURCHF | 7,141 | 1999-01-04 → 2026-11-20 |
| AUDUSD, AUDEUR, AUDNZD, AUDCAD, AUDCHF | **977** | **2023-01-03 → 2026-11-20** |

The RBA f11.1 feed only serves a truncated window (already noted in the source map, and I still
registered the panel on it). Consequence: P1's cross-section was **all-8 instrument only from 2023**,
a 3.9-year sample, on a test registered as a 27-year test. The P1 verdict is therefore **INVALID —
neither a pass nor a fail**. Publishing it as a fail would be as dishonest as publishing it as a pass.

## Amendment (registered now, before running)

**P1R "EUR9"** replaces P1 for H09a:

- Instruments: **EURUSD, EURJPY, EURGBP, EURCHF, EURCAD, EURSEK, EURNOK, EURAUD, EURNZD**
  (all quoted as units of foreign currency per EUR)
- Source: ECB `EXR/D.{CCY}.EUR.SP00.A`, verified **7,203 rows each, all starting 1999-01-04**
- Span: 1999-01 → 2026-11, all 9 instruments live the whole time

Everything else is unchanged and stays locked: k=2 primary, tercile legs (3 vs 3 of 9),
dollar-neutral, weekly Friday, costs charged on lagged turnover at fx 0.013%, 5-year rolling
windows stepped 1 year, 1000-sim random-selection null, criteria A1–A4 identical.

P2 "MULTI12" is unchanged and its result stands as reported (its Yahoo data does cover 2000+ for
every leg except EURUSD, which starts 2003 — a shorter but honest span; already disclosed).

## Additional disclosure on H09b

H09b (single-asset z-fade) was run on AUDUSD using the same defective file: **977 bars, 2023–2026.**
A Sharpe of 1.03 on 3.9 years, chosen from a cluster of 4 tested assets, is exactly the kind of
number this project treats as noise until proven otherwise. H09b will now also be evaluated with
the **full A1–A4 criteria** (5-year walk-forward windows, 2× cost), and any H09b number derived
from the truncated AUD files will be labelled **"short sample, not evidence"** in the report.

## Rule restated

No parameter, tercile, cost, window or criterion is changed by this amendment. Only a broken input
is replaced, and the fix is made on the basis of **data coverage verified by row counts and first
dates** — not on the basis of results.

_Registered 2026-11-20 by Alina Research Agent._
