# H12 — COT extreme positioning (exploratory)

**Status: EXPLORATORY, not pre-registered.** With 59 tests at 5% you expect ~3.0 false positives, so read the table as a map of where to look next, not as evidence.

Definition: `noncomm_net_pct_oi_pct156` in its top/bottom 5% over a trailing 156-week window; entry at the first close on/after the COT publication date (Friday); forward 4- and 8-week price return, sign-adjusted so `+` = the direction the contrarian view would have wanted.

**Headline:** 59 tests, 0 match the contrarian sign with |t|>=2 (chance would give ~3.0) -> **no contrarian evidence**.

## Strongest results (|t| desc)

| instrument | horizon | state | n | mean fwd | unconditional | edge | t |
|---|---|---|---|---|---|---|---|
| VIX | 4w | net_short_extreme | 23 | -12.604% | -6.403% | -6.201% | -3.18 |
| EURUSD | 4w | net_long_extreme | 39 | +1.100% | +0.037% | +1.063% | +2.99 |
| EURUSD | 8w | net_long_extreme | 18 | +1.783% | +0.058% | +1.726% | +2.19 |
| NATGAS | 4w | net_long_extreme | 37 | -1.022% | +3.348% | -4.370% | -1.95 |
| GOLD | 8w | net_long_extreme | 30 | +2.495% | +0.442% | +2.053% | +1.91 |
| NATGAS | 8w | net_long_extreme | 17 | -6.013% | +0.768% | -6.780% | -1.89 |
| GOLD | 8w | net_short_extreme | 21 | -1.458% | +0.442% | -1.900% | -1.88 |
| SILVER | 8w | net_long_extreme | 22 | -2.739% | +0.597% | -3.337% | -1.71 |
| CORN | 4w | net_long_extreme | 30 | +3.513% | +0.282% | +3.232% | +1.63 |
| GBPUSD | 8w | net_long_extreme | 18 | +1.640% | +0.788% | +0.852% | +1.55 |
| USDJPY | 4w | net_long_extreme | 46 | -0.278% | +0.455% | -0.733% | -1.51 |
| USDJPY | 8w | net_long_extreme | 24 | -0.096% | +1.222% | -1.319% | -1.51 |

## Honest read

- The spread of t-stats across instruments is what matters, not the best one. A real positioning effect should show up in *several* contracts with the same sign and a coherent economic story (commercials on the other side).
- Direction note: most |t|>=2 hits here point the SAME way as the crowd (momentum), not against it. That is the opposite of the folklore read, and it is the more interesting lead: 'funds keep pressing a winning trade for 4-8 weeks'.
- Instrument-specific results with |t| between 2 and 3 in a 36-test sweep are noise candidates. Anything worth keeping must be re-tested on a held-out date range and pooled cross-sectionally.
- Next step if pursued: pool all contracts into one panel regression with instrument fixed effects and time-clustered standard errors, then split 70/30 by date.
