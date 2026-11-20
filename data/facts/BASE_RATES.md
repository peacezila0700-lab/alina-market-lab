# BASE RATES — what happened NEXT, given today's reading

Measured on this repo's own official data (SPY from Yahoo, VIX from Cboe, DIX/GEX from SqueezeMetrics, OFR FSI from the Office of Financial Research). Forward returns are simple, in percent, no costs. `n_eff` = non-overlapping observations — the honest sample size.

## VIX → next 21 trading days

| bucket | n | n_eff | median % | mean % | % positive | p10 % | p90 % | worst % |
|---|---|---|---|---|---|---|---|---|
| ALL (unconditional) | 6739 | 320 | +1.2 | +0.6 | 63 | -5.0 | +5.4 | -33.1 |
| 12-15 | 1549 | 73 | +0.9 | +0.5 | 62 | -3.1 | +3.6 | -28.9 |
| 15-20 | 2076 | 98 | +1.3 | +0.5 | 65 | -4.8 | +4.7 | -33.1 |
| 20-25 | 1280 | 60 | +0.8 | -0.0 | 56 | -7.0 | +5.8 | -29.5 |
| 25-30 | 648 | 30 | +2.3 | +1.2 | 64 | -6.5 | +7.7 | -24.6 |
| 30-40 | 430 | 20 | +3.2 | +2.2 | 73 | -5.0 | +9.1 | -30.5 |
| <12 | 564 | 26 | +0.9 | +0.6 | 66 | -2.7 | +3.2 | -8.2 |
| >=40 | 192 | 9 | +3.5 | +2.4 | 61 | -11.7 | +14.8 | -19.5 |

## VIX → next 252 trading days

| bucket | n | n_eff | median % | mean % | % positive | p10 % | p90 % | worst % |
|---|---|---|---|---|---|---|---|---|
| ALL (unconditional) | 6508 | 25 | +11.1 | +7.9 | 76 | -16.7 | +25.5 | -48.6 |
| 12-15 | 1521 | 6 | +11.8 | +10.5 | 87 | -1.8 | +20.8 | -19.6 |
| 15-20 | 1916 | 7 | +10.4 | +7.2 | 78 | -15.9 | +22.6 | -45.4 |
| 20-25 | 1252 | 4 | +6.3 | +0.5 | 56 | -25.2 | +24.9 | -48.6 |
| 25-30 | 635 | 2 | +10.0 | +4.5 | 61 | -22.7 | +30.8 | -47.5 |
| 30-40 | 428 | 1 | +19.2 | +16.6 | 80 | -11.9 | +39.0 | -41.5 |
| <12 | 564 | 2 | +10.1 | +8.3 | 86 | -4.1 | +16.2 | -12.4 |
| >=40 | 192 | 0 | +30.4 | +32.9 | 96 | +12.1 | +57.0 | -16.9 |

## DIX → next 21 trading days

| bucket | n | n_eff | median % | mean % | % positive | p10 % | p90 % | worst % |
|---|---|---|---|---|---|---|---|---|
| ALL (unconditional) | 6739 | 320 | +1.2 | +0.6 | 63 | -5.0 | +5.4 | -33.1 |
| nan | 251 | 11 | +0.9 | +0.2 | 55 | -5.8 | +5.5 | -16.5 |
| q1 | 753 | 35 | +1.2 | +0.9 | 62 | -3.5 | +4.7 | -24.6 |
| q2 | 715 | 34 | +1.3 | +1.0 | 68 | -3.8 | +4.8 | -28.7 |
| q3 | 654 | 31 | +1.5 | +0.8 | 68 | -3.3 | +4.7 | -33.1 |
| q4 | 724 | 34 | +1.7 | +1.2 | 70 | -4.1 | +5.3 | -25.1 |
| q5 | 793 | 37 | +2.1 | +1.5 | 70 | -5.1 | +6.6 | -18.0 |

## DIX → next 252 trading days

| bucket | n | n_eff | median % | mean % | % positive | p10 % | p90 % | worst % |
|---|---|---|---|---|---|---|---|---|
| ALL (unconditional) | 6508 | 25 | +11.1 | +7.9 | 76 | -16.7 | +25.5 | -48.6 |
| nan | 251 | 0 | +13.2 | +12.2 | 96 | +1.4 | +21.7 | -3.7 |
| q1 | 677 | 2 | +13.6 | +12.8 | 86 | -2.4 | +26.9 | -19.7 |
| q2 | 653 | 2 | +14.2 | +13.2 | 89 | -0.4 | +25.7 | -21.0 |
| q3 | 609 | 2 | +14.3 | +12.6 | 84 | -4.9 | +26.4 | -20.6 |
| q4 | 688 | 2 | +14.8 | +13.0 | 83 | -5.5 | +27.0 | -20.1 |
| q5 | 781 | 3 | +15.6 | +15.0 | 84 | -6.4 | +32.2 | -20.2 |

## GEX_sign → next 21 trading days

| bucket | n | n_eff | median % | mean % | % positive | p10 % | p90 % | worst % |
|---|---|---|---|---|---|---|---|---|
| ALL (unconditional) | 6739 | 320 | +1.2 | +0.6 | 63 | -5.0 | +5.4 | -33.1 |
| negative | 347 | 16 | +3.3 | +2.7 | 71 | -5.0 | +10.2 | -24.6 |
| positive | 3542 | 168 | +1.4 | +0.9 | 67 | -4.0 | +4.9 | -33.1 |

## GEX_sign → next 252 trading days

| bucket | n | n_eff | median % | mean % | % positive | p10 % | p90 % | worst % |
|---|---|---|---|---|---|---|---|---|
| ALL (unconditional) | 6508 | 25 | +11.1 | +7.9 | 76 | -16.7 | +25.5 | -48.6 |
| negative | 338 | 1 | +16.6 | +17.4 | 87 | -3.5 | +34.2 | -17.1 |
| positive | 3320 | 13 | +14.2 | +12.9 | 86 | -2.7 | +26.5 | -21.0 |

## OFR_FSI → next 21 trading days

| bucket | n | n_eff | median % | mean % | % positive | p10 % | p90 % | worst % |
|---|---|---|---|---|---|---|---|---|
| ALL (unconditional) | 6739 | 320 | +1.2 | +0.6 | 63 | -5.0 | +5.4 | -33.1 |
| -0.5-0 | 338 | 16 | +1.2 | +0.2 | 62 | -5.8 | +5.2 | -19.5 |
| 0-0.5 | 271 | 12 | +2.2 | +1.0 | 70 | -5.8 | +5.7 | -17.9 |
| 0.5-1.5 | 491 | 23 | +2.0 | +1.1 | 68 | -5.2 | +5.9 | -18.0 |
| <-0.5 | 3903 | 185 | +1.2 | +0.8 | 66 | -3.4 | +4.4 | -33.1 |
| >=1.5 | 1736 | 82 | +0.8 | +0.3 | 55 | -8.0 | +7.9 | -30.5 |

## OFR_FSI → next 252 trading days

| bucket | n | n_eff | median % | mean % | % positive | p10 % | p90 % | worst % |
|---|---|---|---|---|---|---|---|---|
| ALL (unconditional) | 6508 | 25 | +11.1 | +7.9 | 76 | -16.7 | +25.5 | -48.6 |
| -0.5-0 | 332 | 1 | +12.2 | +13.2 | 90 | +0.1 | +29.3 | -43.1 |
| 0-0.5 | 270 | 1 | +13.4 | +12.4 | 90 | -0.3 | +28.2 | -45.4 |
| 0.5-1.5 | 491 | 1 | +11.8 | +10.6 | 86 | -3.2 | +23.9 | -42.7 |
| <-0.5 | 3679 | 14 | +11.4 | +10.1 | 84 | -5.7 | +23.4 | -35.2 |
| >=1.5 | 1736 | 6 | +1.5 | +0.8 | 50 | -30.2 | +30.7 | -48.6 |

## How to use this without fooling yourself

- A bucket with `n_eff` under ~30 is an anecdote. Do not build a rule on it.
- The unconditional row is the benchmark. If the bucket median is not visibly different *and* the sample is big enough, there is no signal.
- These are conditional distributions of the market, not of a strategy. A strategy also pays the spread and the timing of entry, which usually eats the difference.
- Multiple buckets × factors × horizons = a lot of looks. Treat the extremes as hypotheses, then test them with a hold-out, exactly like the other experiments in this repo.
