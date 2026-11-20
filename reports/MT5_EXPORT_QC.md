# MT5 EXPORT QC — TEST_EURGBP_H1

Generated: 2026-11-20T15:45:09+00:00

## Shape

| check | value |
|---|---|
| bars | 600 |
| first timestamp | 2024-01-01 00:00:00 |
| last timestamp | 2024-01-25 23:00:00 |
| timestamp format | broker **server time** (not converted) |
| duplicate timestamps | 0 |
| weekend bars | 144 |
| OHLC violations | 0 |
| bars with open == close | 4 (0.7%) |
| median step between bars | 60 min |
| gaps > 5x median step | 0 |

## Spread (this is the number the project has been missing)

| metric | value |
|---|---|
| bars with spread reported | 600 |
| median | **10.0 points** |
| mean | 10.0 points |
| p90 | 14.0 points |
| p99 | 14.0 points |
| max | 14.0 points |

> 1 point = 0.00001 on 5-digit pairs; 10 points = 1.0 pip. Divide by 10 to compare with the 0.9 pip Dukascopy median used so far.

## Verdict

- NOTE: 144 weekend bars — decide policy (keep/drop) before use
