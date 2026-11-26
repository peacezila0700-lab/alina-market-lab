# Daily Risk Radar — Specification & Latest Reading

> **RISK MONITORING TOOL ONLY — Not a buy/sell signal generator or proof of trading edge. Phase C Kill Point remains active (0 validated directional edges across 54 experiments).**

Generated UTC: `2026-11-26T23:27:10+00:00` | Overall Risk Classification: **`HIGH`** | Fresh Panels: `6/9`

## 1. Panel Status, Data Sources, Freshness & Thresholds
| Panel | Last Updated | Age (d) | Freshness | Risk Class | Key Metrics | Warning |
|---|---|---:|---|---|---|---|
| `vol_term_structure` | `2026-11-25` | 1 | `FRESH` | **HIGH** | `{"vix": 28.29, "slope_3m": 1.076, "slope_9d": 1.047, "vvix_pct": 0.874}` | none |
| `ofr_fsi` | `2026-11-24` | 2 | `FRESH` | **LOW** | `{"ofr_fsi": -1.141, "credit": -0.785, "volatility_sub": 0.331}` | none |
| `equity_vol_dd` | `2026-11-25` | 1 | `FRESH` | **HIGH** | `{"spy_close": 716.7, "rv20_pct": 31.64, "rv63_pct": 19.57, "dd_52w_pct": -8.01}` | none |
| `support_resistance` | `2026-11-21` | 5 | `FRESH` | **MODERATE** | `{"instruments": [{"instrument": "BTC", "close": 57808.3906, "s1": 55932.7956, "r1": 59382.7643,` | none |
| `calendar_7d` | `2026-11-26` | 0 | `FRESH` | **MODERATE** | `{"upcoming_7d_count": 1, "events": [{"date": "2026-11-30", "event": "MONTH_END", "detail": "las` | Note: ECB/BoE 2027 dates require annual calendar extension after Dec 2026. |
| `macro_rates` | `2026-11-20` | 6 | `STALE_WARNING` | **LOW** | `{"ecb_dfr": 2.5, "boe_rate": 4.0, "fed_rate_proxy": 3.88, "diff_boe_ecb_dfr": 1.5, "diff_fed_ec` | CB rates stale (6d) |
| `news_stress` | `2026-11-26T23:26:03` | 0 | `FRESH` | **ELEVATED** | `{"feeds_ok": 16, "feeds_total": 16, "unique_headlines": 1060, "stress_keyword_hits": 98}` | none |
| `crypto_funding_basis` | `2026-11-21` | 5 | `STALE_WARNING` | **LOW** | `{"deribit_btc_24h_apr_pct": -2.88, "deribit_btc_index": 58820.48, "okx_btc_24h_apr_pct": -0.46}` | none |
| `equity_short_insider_breadth` | `2026-11-20` | 6 | `STALE_WARNING` | **MODERATE** | `{"regsho_mkt_short_ratio": 0.4612, "regsho_ma5": 0.4745, "regsho_surge_5v60": -0.0242, "regsho_` | FINRA RegSHO stale (6d old) |

## 2. Calibrated Risk Meta-Labeling (`Task 3 + EXP-0030/0031`, Offline Sizing & Monitor Only)
- **As-Of Date:** `2026-11-25` | **Causal Train Cutoff (`-31d` Purge+Embargo):** `2026-09-14`
- **Calibrated Probabilities (`HGBC + Platt`):** `P(VolOnset_21d) = 0.0316` | `P(TailStress_21d) = 0.3472` | `P(TB_NonDirStress_21d) = 0.3472`
- **Stationary Macro/Vol State:** `OFR_FSI_z252=1.633`, `GPR_z252=-0.385`, `d_Fed_63d=0.25`, `VIX=28.29`, `Slope3M=1.076`, `RV21=30.93%`
- **Defensive Sizing Reference (`EXP-0031`):** `VolTarget12%=38.8%` × `MetaThrottle=0.948` -> **`Equity=36.8%` / `Cash Buffer=63.2%`**

## 3. FX Intraday Rollover & Cost-Shock Guard (`EXP-0030 Track B`)
- **`EURGBP H1` Last Bar:** `2026-11-20T18:00:00+00:00` | Spread `0.8 pips` (`z72=-0.16`) | In 6h Rollover Hazard (`16–23 UTC`): `True`

## 4. Crypto Daily Trend Regime & VolTarget25% Monitor (`EXP-0041 + EXP-0043`, Monitoring Reference)
- **`BTC-USD` As-Of `2026-11-26`:** Close `$60,412.81` | `SMA(50)=$74,676.91` (`Above=False`) | `TrendEns(20..120)=0.00` | `RV21=44.19%` | `19-Coin Breadth >SMA50`: `1/19 (5.3%)`
- **Vol-Targeted Reference (`VT25%`):** `TrendEns x VT25 = 0.0%` (`SMA50 x VT25 = 0.0%`) | Cash/EFFR `100.0%`

## 5. Active Risk Alerts
- **[HIGH] `vol_term_structure`:** VIX/VIX3M inverted at 1.076 (>1.00)
- **[HIGH] `equity_vol_dd`:** SPY RV20=31.6%, 52w DD=-8.0%
- **[MODERATE] `equity_short_insider_breadth`:** FINRA RegSHO mkt short ratio=0.461 (z60=-2.02)

## 6. Missing Data / Staleness Warnings
- macro_rates: freshness=STALE_WARNING (age=6d)
- crypto_funding_basis: freshness=STALE_WARNING (age=5d)
- equity_short_insider_breadth: freshness=STALE_WARNING (age=6d)
