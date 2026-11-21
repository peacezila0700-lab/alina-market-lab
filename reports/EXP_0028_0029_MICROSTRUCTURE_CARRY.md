# EXP-0028 & EXP-0029 — Workstream B: Microstructure, Carry, Basis & Cross-Venue Audit

Generated UTC: `2026-11-21T11:33:06+00:00`

## Part 1 (`EXP-0028`): 23-Year Official FX Rate-Differential Carry + H1 Bid-Ask Timing (`2003–2026`)
### EURGBP (`147,297` H1 bars | `2003-08-03..2026-11-20`)
- **Best Liquid Hour (UTC):** `09:00` (`0.9` pips) | **Worst Rollover Hour:** `20:00` (`2.6` pips) -> `21:00 UTC / 14:00 UTC` spread ratio = **2.4x**
| Swap Markup Haircut | IS (2003–15) Sharpe | VALID (2016–21) Sharpe | OOS (2022–26) Sharpe | ALL Sharpe | ALL MaxDD |
|---|---:|---:|---:|---:|---:|
| `markup_0.00_pips_night` | +0.012 | +0.145 | +0.408 | +0.140 | -18.9% |
| `markup_0.25_pips_night` | -0.119 | +0.073 | +0.209 | +0.006 | -21.53% |
  - *Circular-Shift Null (0.25p/night):* OOS `97.0%` | ALL `53.0%`
| `markup_0.50_pips_night` | -0.251 | +0.001 | +0.010 | -0.128 | -24.48% |
### EURUSD (`148,482` H1 bars | `2003-05-04..2026-11-20`)
- **Best Liquid Hour (UTC):** `04:00` (`0.4` pips) | **Worst Rollover Hour:** `21:00` (`1.6` pips) -> `21:00 UTC / 14:00 UTC` spread ratio = **4.0x**
| Swap Markup Haircut | IS (2003–15) Sharpe | VALID (2016–21) Sharpe | OOS (2022–26) Sharpe | ALL Sharpe | ALL MaxDD |
|---|---:|---:|---:|---:|---:|
| `markup_0.00_pips_night` | -0.164 | -0.101 | +0.065 | -0.089 | -36.05% |
| `markup_0.25_pips_night` | -0.201 | -0.190 | -0.040 | -0.154 | -37.8% |
  - *Circular-Shift Null (0.25p/night):* OOS `2.5%` | ALL `3.0%`
| `markup_0.50_pips_night` | -0.238 | -0.278 | -0.145 | -0.219 | -40.67% |

## Part 2 (`EXP-0029`): Deribit Hourly Funding Carry & OKX Cross-Venue Post-Cost Audit (`2024–2026`)
### Data Adequacy Matrix
- **`deribit_funding_perp_1h`:** `ADEQUATE (25,284h, 2024-01-01..2026-11-21)`
- **`okx_perp_index_1h`:** `PARTIAL (10,000h, 2025-09-30..2026-11-20)`
- **`okx_funding_8h`:** `INADEQUATE (280 rows / ~93 days API cap)`
- **`binance_bybit`:** `UNAVAILABLE (Sandbox HTTP 451 / 403)`

### Deribit BTC Hedged Cash-and-Carry (`25,284` 1H bars | IS mean funding `8.29%` vs OOS `3.84%`)
| Entry/Exit Rule | Trades | Time In Market | Cost Tier | IS Sharpe | OOS Sharpe | OOS CAGR | MaxDD |
|---|---:|---:|---|---:|---:|---:|---:|
| `entry_8pct_exit_2pct` | 71 | 38.8% | `Gross_Zero_Cost` | +0.255 | +0.011 | +0.30% | -15.47% |
| `entry_8pct_exit_2pct` | 71 | 38.8% | `Maker_2bp_leg_5pct_Borrow` | +0.130 | -0.149 | -4.17% | -24.04% |
| `entry_8pct_exit_2pct` | 71 | 38.8% | `Taker_5bp_leg_8pct_Borrow` | +0.002 | -0.318 | -8.89% | -34.47% |
| `entry_15pct_exit_5pct` | 48 | 20.8% | `Gross_Zero_Cost` | +0.106 | +0.153 | +2.48% | -14.85% |
| `entry_15pct_exit_5pct` | 48 | 20.8% | `Maker_2bp_leg_5pct_Borrow` | -0.002 | +0.035 | +0.57% | -20.95% |
| `entry_15pct_exit_5pct` | 48 | 20.8% | `Taker_5bp_leg_8pct_Borrow` | -0.117 | -0.095 | -1.54% | -28.64% |

### Deribit ETH Hedged Cash-and-Carry (`25,284` 1H bars | IS mean funding `5.51%` vs OOS `1.74%`)
| Entry/Exit Rule | Trades | Time In Market | Cost Tier | IS Sharpe | OOS Sharpe | OOS CAGR | MaxDD |
|---|---:|---:|---|---:|---:|---:|---:|
| `entry_8pct_exit_2pct` | 54 | 24.7% | `Gross_Zero_Cost` | +0.098 | +0.038 | +1.32% | -24.99% |
| `entry_8pct_exit_2pct` | 54 | 24.7% | `Maker_2bp_leg_5pct_Borrow` | +0.014 | -0.051 | -1.76% | -31.73% |
| `entry_8pct_exit_2pct` | 54 | 24.7% | `Taker_5bp_leg_8pct_Borrow` | -0.074 | -0.151 | -5.20% | -39.23% |
| `entry_15pct_exit_5pct` | 31 | 11.9% | `Gross_Zero_Cost` | +0.139 | -0.044 | -0.58% | -17.11% |
| `entry_15pct_exit_5pct` | 31 | 11.9% | `Maker_2bp_leg_5pct_Borrow` | +0.061 | -0.091 | -1.19% | -19.36% |
| `entry_15pct_exit_5pct` | 31 | 11.9% | `Taker_5bp_leg_8pct_Borrow` | -0.022 | -0.145 | -1.90% | -22.33% |

### Cross-Venue `OKX vs Deribit` BTC Perp Basis & Funding
- **1H Price Overlap:** `10,000` hours (`2025-09-30 04:00:00+00:00..2026-11-20 19:00:00+00:00`)
- **Spread Distribution:** median `3.65 bps`, 95th `|spread|` = `12.89 bps`, 99th = `16.9 bps`, max = `127.52 bps`
- **8H Funding Overlap:** `280` rows (`OKX 5.8%` vs `Deribit 4.19%` APR)
- **Verdict:** `NOT_ARBITRAGE: 95th percentile cross-venue perp spread (12.89 bps) is below 2-exchange taker round-trip execution + spread + slippage cost (~24–32 bps), and OKX public funding history covers only ~93 days (insufficient for multi-regime validation).`
