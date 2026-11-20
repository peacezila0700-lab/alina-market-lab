# PRE-REGISTRATION — H06 (intraday breakout after volatility compression)

**Committed BEFORE the run.** `docs/PREREG_H05.md` and `reports/EXP_0003.md` are the prior art.

## Why the mirror image of H05

H05 (fade the spike) failed with the stop-loss as the main leak (23 stop-outs of 114).
The structurally opposite bet is: **when volatility is compressed, the next expansion is
directional and persists for the session.** That is a momentum premise, not a reversion one.

Intraday-only is kept deliberately: **no overnight ⇒ no swap**, which
`reports/FEASIBILITY_MATH.md` showed is the dominant cost at multi-day holds.

## Frozen rule — no tuning after this commit

| element | value |
|---|---|
| instrument / control | EURGBP primary · EURUSD identical rule |
| data | H1 (same file as EXP-0003) |
| compression filter | ATR(20) at bar t ≤ 33rd percentile of ATR(20) over the trailing 500 bars |
| breakout level | highest high of the previous 20 bars (long) / lowest low (short), excluding bar t |
| signal | close(t) > level → long; close(t) < level → short |
| entry | next bar open |
| entry cutoff | none at/after 19:00 UTC |
| stop | entry ∓ 1.5 × ATR(20) |
| exit 1 | close crosses back through MA20 against the position → next bar open |
| exit 2 | **forced flat at the 21:00 UTC bar close (no overnight)** |
| cost | 1.3 pips round trip (assumed; H1 spread not measured) |
| one position at a time | yes |

## Splits (same as EXP-0003, declared in advance)

IS 2024-02-05→2025-12-31 · VALIDATION 2026-01-01→2026-05-31 · OOS LOCKED 2026-06-01→2026-11-20

## Acceptance / rejection (stricter than H05, because this dataset has now hosted two experiments)

**Accept only if ALL of:**
1. validation net expectancy > 0 **and** its 95% day-cluster CI excludes 0
2. OOS net expectancy has the same sign as validation
3. EURUSD control has the same sign as EURGBP in validation
4. validation expectancy is outside the random-entry p5–p95 band

Anything else = reject. Multiple-testing disclosure: 2nd hypothesis on the same H1 sample.
