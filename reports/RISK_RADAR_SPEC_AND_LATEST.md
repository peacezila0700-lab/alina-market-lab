# Daily Risk Radar — Specification & Latest Reading

> **RISK MONITORING TOOL ONLY — Not a buy/sell signal generator or proof of trading edge. Phase C Kill Point remains active (0 validated directional edges across 54 experiments).**

Generated UTC: `2026-11-23T23:22:37+00:00` | Overall Risk Classification: **`HIGH`** | Fresh Panels: `9/9`

## 1. Panel Status, Data Sources, Freshness & Thresholds
| Panel | Last Updated | Age (d) | Freshness | Risk Class | Key Metrics | Warning |
|---|---|---:|---|---|---|---|
| `vol_term_structure` | `2026-11-23` | 0 | `FRESH` | **ELEVATED** | `{"vix": NaN, "slope_3m": NaN, "slope_9d": NaN, "vvix_pct": 0.915}` | none |
| `ofr_fsi` | `2026-11-19` | 4 | `FRESH` | **LOW** | `{"ofr_fsi": -1.259, "credit": -0.841, "volatility_sub": 0.328}` | none |
| `equity_vol_dd` | `2026-11-23` | 0 | `FRESH` | **HIGH** | `{"spy_close": 722.29, "rv20_pct": 31.88, "rv63_pct": 19.61, "dd_52w_pct": -7.29}` | none |
| `support_resistance` | `2026-11-21` | 2 | `FRESH` | **MODERATE** | `{"instruments": [{"instrument": "BTC", "close": 57808.3906, "s1": 55932.7956, "r1": 59382.7643,` | none |
| `calendar_7d` | `2026-11-23` | 0 | `FRESH` | **MODERATE** | `{"upcoming_7d_count": 2, "events": [{"date": "2026-11-23", "event": "SHOCK_2.5SIG", "detail": "` | Note: ECB/BoE 2027 dates require annual calendar extension after Dec 2026. |
| `macro_rates` | `2026-11-20` | 3 | `FRESH` | **LOW** | `{"ecb_dfr": 2.5, "boe_rate": 4.0, "fed_rate_proxy": 3.88, "diff_boe_ecb_dfr": 1.5, "diff_fed_ec` | none |
| `news_stress` | `2026-11-23T23:21:33` | 0 | `FRESH` | **ELEVATED** | `{"feeds_ok": 16, "feeds_total": 16, "unique_headlines": 597, "stress_keyword_hits": 45}` | none |
| `crypto_funding_basis` | `2026-11-21` | 2 | `FRESH` | **LOW** | `{"deribit_btc_24h_apr_pct": -2.88, "deribit_btc_index": 58820.48, "okx_btc_24h_apr_pct": -0.46}` | none |
| `equity_short_insider_breadth` | `2026-11-20` | 3 | `FRESH` | **MODERATE** | `{"regsho_mkt_short_ratio": 0.4612, "regsho_ma5": 0.4745, "regsho_surge_5v60": -0.0242, "regsho_` | none |

## 2. Calibrated Risk Meta-Labeling (`Task 3 + EXP-0030/0031`, Offline Sizing & Monitor Only)
- **As-Of Date:** `2026-11-23` | **Causal Train Cutoff (`-31d` Purge+Embargo):** `2026-09-10`
- **Calibrated Probabilities (`HGBC + Platt`):** `P(VolOnset_21d) = 0.0519` | `P(TailStress_21d) = 0.3877` | `P(TB_NonDirStress_21d) = 0.3877`
- **Stationary Macro/Vol State:** `OFR_FSI_z252=1.483`, `GPR_z252=-0.385`, `d_Fed_63d=0.25`, `VIX=35.89`, `Slope3M=1.16`, `RV21=31.26%`
- **Defensive Sizing Reference (`EXP-0031`):** `VolTarget12%=38.4%` × `MetaThrottle=0.904` -> **`Equity=34.7%` / `Cash Buffer=65.3%`**

## 3. FX Intraday Rollover & Cost-Shock Guard (`EXP-0030 Track B`)
- **`EURGBP H1` Last Bar:** `2026-11-20T18:00:00+00:00` | Spread `0.8 pips` (`z72=-0.16`) | In 6h Rollover Hazard (`16–23 UTC`): `True`

## 4. Crypto Daily Trend Regime & VolTarget25% Monitor (`EXP-0041 + EXP-0043`, Monitoring Reference)
- **`BTC-USD` As-Of `2026-11-23`:** Close `$61,425.61` | `SMA(50)=$76,162.83` (`Above=False`) | `TrendEns(20..120)=0.00` | `RV21=52.23%` | `19-Coin Breadth >SMA50`: `1/19 (5.3%)`
- **Vol-Targeted Reference (`VT25%`):** `TrendEns x VT25 = 0.0%` (`SMA50 x VT25 = 0.0%`) | Cash/EFFR `100.0%`

## 5. Active Risk Alerts
- **[ELEVATED] `vol_term_structure`:** VVIX percentile elevated at 0.91 (>=0.90)
- **[HIGH] `equity_vol_dd`:** SPY RV20=31.9%, 52w DD=-7.3%
- **[MODERATE] `equity_short_insider_breadth`:** FINRA RegSHO mkt short ratio=0.461 (z60=-2.02)

## 6. Missing Data / Staleness Warnings
- None.
