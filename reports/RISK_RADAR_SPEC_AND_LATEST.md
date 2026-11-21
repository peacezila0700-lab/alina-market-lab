# Daily Risk Radar — Specification & Latest Reading

> **RISK MONITORING TOOL ONLY — Not a buy/sell signal generator or proof of trading edge. Phase C Kill Point remains active (0 validated directional edges across 29 experiments).**

Generated UTC: `2026-11-21T11:38:25+00:00` | Overall Risk Classification: **`HIGH`** | Fresh Panels: `8/8`

## 1. Panel Status, Data Sources, Freshness & Thresholds
| Panel | Last Updated | Age (d) | Freshness | Risk Class | Key Metrics | Warning |
|---|---|---:|---|---|---|---|
| `vol_term_structure` | `2026-11-20` | 1 | `FRESH` | **HIGH** | `{"vix": 35.89, "slope_3m": 1.16, "slope_9d": 1.135, "vvix_pct": 0.996}` | none |
| `ofr_fsi` | `2026-11-18` | 3 | `FRESH` | **LOW** | `{"ofr_fsi": -1.387, "credit": -0.853, "volatility_sub": 0.24}` | none |
| `equity_vol_dd` | `2026-11-20` | 1 | `FRESH` | **ELEVATED** | `{"spy_close": 689.81, "rv20_pct": 26.26, "rv63_pct": 17.05, "dd_52w_pct": -11.46}` | none |
| `support_resistance` | `2026-11-21` | 0 | `FRESH` | **MODERATE** | `{"instruments": [{"instrument": "BTC", "close": 57808.3906, "s1": 55932.7956, "r1": 59382.7643,` | none |
| `calendar_7d` | `2026-11-21` | 0 | `FRESH` | **LOW** | `{"upcoming_7d_count": 0, "events": []}` | Note: ECB/BoE 2027 dates require annual calendar extension after Dec 2026. |
| `macro_rates` | `2026-11-20` | 1 | `FRESH` | **LOW** | `{"ecb_dfr": 2.5, "boe_rate": 4.0, "fed_rate_proxy": 3.88, "diff_boe_ecb_dfr": 1.5, "diff_fed_ec` | none |
| `news_stress` | `2026-11-21T11:37:27` | 0 | `FRESH` | **ELEVATED** | `{"feeds_ok": 16, "feeds_total": 16, "unique_headlines": 418, "stress_keyword_hits": 31}` | none |
| `crypto_funding_basis` | `2026-11-21` | 0 | `FRESH` | **LOW** | `{"deribit_btc_24h_apr_pct": -2.88, "deribit_btc_index": 58820.48, "okx_btc_24h_apr_pct": -0.46}` | OKX public funding API limited to ~93d; Binance (HTTP 451) & Bybit (HTTP 403) blocked in sandbox. |

## 2. Active Risk Alerts
- **[HIGH] `vol_term_structure`:** VIX/VIX3M inverted at 1.160 (>1.00)
- **[ELEVATED] `vol_term_structure`:** VVIX percentile elevated at 1.00 (>=0.90)
- **[ELEVATED] `equity_vol_dd`:** SPY RV20=26.3%, 52w DD=-11.5%

## 3. Missing Data / Staleness Warnings
- None.
