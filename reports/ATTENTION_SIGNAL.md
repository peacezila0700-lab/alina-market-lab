# ATTENTION AS A SIGNAL — does free news data beat plain volatility clustering?

Attention = daily English Wikipedia pageviews per asset (free, no key, back to 2016). Forecast target = tomorrow's absolute return. **The baseline is trailing 20-day mean absolute return**, i.e. pure volatility clustering. Attention only matters if it beats that.

## A/B — out-of-sample forecast of tomorrow's |move|

| Asset | baseline MAE | +attention MAE | ΔMAE | baseline R² | +attention R² | ΔR² |
|---|---:|---:|---:|---:|---:|---:|
| BTC | 1.6725% | 1.709% | +0.03650 | 0.0705 | 0.0685 | -0.0020 |
| COPPER | 0.8053% | 0.7449% | -0.06040 | 0.1026 | -0.0143 | -0.1169 |
| ETH | 2.1925% | 2.0913% | -0.10120 | 0.0297 | 0.0131 | -0.0166 |
| EURUSD | 0.2889% | 0.2164% | -0.07250 | 0.0485 | 0.0146 | -0.0339 |
| GOLD | 0.5405% | 0.5171% | -0.02340 | 0.0865 | 0.1049 | +0.0184 |
| SP500 | 0.5416% | 0.5311% | -0.01050 | 0.2141 | 0.1296 | -0.0845 |
| USDJPY | 0.3062% | 0.2594% | -0.04680 | 0.0401 | 0.0517 | +0.0116 |
| WTI | 1.1705% | 1.2796% | +0.10910 | 0.1522 | 0.1775 | +0.0253 |

Attention lowers the forecast error on **6 of 8** assets. The gains are small in absolute terms — attention is a weak second-order signal, not a new sense.

## C — rank correlation (outlier-safe)

| Asset | attention vs same-day |ret| | attention vs **next-day** |ret| |
|---|---:|---:|
| BTC | 0.214 | 0.164 |
| COPPER | -0.024 | -0.021 |
| ETH | 0.191 | 0.141 |
| EURUSD | 0.031 | 0.035 |
| GOLD | 0.067 | 0.043 |
| SP500 | 0.061 | 0.035 |
| USDJPY | 0.056 | 0.066 |
| WTI | 0.128 | 0.068 |

## D — does it change a portfolio?

Equal-weight, 10% vol target, weekly rebalance, size capped at 3x, 3bp per unit turnover, same 24 assets and dates both times.

| Sizing forecast | CAGR | Sharpe | maxDD |
|---|---:|---:|---:|
| realized_only | 2.64% | 0.64 | 11.2% |
| realized_plus_attention | 2.62% | 0.63 | 11.2% |


## Verdict — read this before using any of the above

- **Attention is not an edge.** It improves the next-day volatility forecast on 6 of 8 assets in MAE terms, but on squared-error (R²) it helps only 3 of 8, and the marginal magnitude is small. It is a *slightly better volatility estimate*, not a direction signal.
- **In a portfolio it adds nothing.** Vol-targeting with realized vol scores Sharpe 0.64; adding the attention multiplier gives 0.63 — a rounding-level change, i.e. noise.
- **What it IS good for:** explaining. The event study (`reports/EVENT_LAYER.md`) shows FOMC days really do carry bigger moves (S&P +17bp, t=2.84) and attention spikes flag high-volatility regimes — useful for *sizing and narration*, not for entries.
- Honest status: **attention layer = diagnostic, not strategy.** No live trading on this.

_Generated 2026-11-20T16:54:55Z by `scripts/attention_signal.py`._
