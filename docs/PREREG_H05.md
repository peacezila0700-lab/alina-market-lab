# PRE-REGISTRATION — H05 (intraday fade, no overnight)

**Written and committed BEFORE the experiment was run.** Timestamp in git history is the proof.

## Why this hypothesis exists

EXP-0002 rejected the D1 rule. `reports/FEASIBILITY_MATH.md` then showed financing (swap) can
reach 12× the spread at a 20-day hold, moving the break-even win rate from 53.2% to 72.0%.
Conclusion: **if the range behaviour is exploitable at all, the hold must be short enough that
swap is zero by construction.** Intraday-only positions achieve exactly that.

This is a different mechanism in a different sample — not a rescue of H01.

## Frozen rule (no tuning after this commit)

| element | value | reason |
|---|---|---|
| instrument | EURGBP | same screened instrument (D01) |
| control | EURUSD, identical rule | replication inside the same experiment |
| data | H1, Yahoo 730d (`EURGBP_H1.csv`) | never used for any test before EXP-0003 |
| signal | z = (close − MA20) / sd(close − MA20, trailing 252 bars) at bar close | same ±2σ convention as H01, adapted window (20 H1 bars ≈ 1 trading day) |
| entry | z ≥ +2.0 → short at next bar open | identical timing discipline as EXP-0001 |
| entry cutoff | no entries at or after 19:00 UTC | avoid rollover spread and thin liquidity |
| exit 1 | close < MA20 → exit next bar open | reverted |
| exit 2 | forced flat at the 21:00 UTC bar close | **no overnight position ⇒ no swap** |
| exit 3 | stop at entry + 3×ATR(20) | same as H01 |
| cost | 1.3 pips round trip (0.9 spread + 0.2×2 slippage) | measured for D1; H1 spread not measured — declared limitation |
| one position at a time | yes | same as H01 |

## Splits (declared in advance)

| block | window | role |
|---|---|---|
| IS | 2024-02-05 → 2025-12-31 | mechanics only |
| VALIDATION | 2026-01-01 → 2026-05-31 | first honest test |
| OOS LOCKED | 2026-06-01 → 2026-11-20 | touched once, at the end |

## Rejection criteria (fixed now)

Reject H05 if any of:
1. validation-block net expectancy ≤ 0, or
2. block-bootstrap 95% CI of validation net expectancy includes 0, or
3. performance is inside the random-entry benchmark band (p5–p95), or
4. EURUSD control disagrees in sign with EURGBP on the same rule.

## Known limitations accepted before running

- **2 years only** (vendor ceiling). At most 2–3 volatility regimes. A pass here would be weak
  evidence; a fail here is still informative because the rule needs only ~1 day of exposure.
- **No spread data.** Cost is assumed. If the broker's real spread is 2.0 pips instead of 1.3,
  the expected value shifts by 0.7 pips per trade — enough to matter at these targets.
- **Data was already touched generically** (ATR/spread sizing in H1 QC), but no H1 outcome was
  ever examined before this commit.
