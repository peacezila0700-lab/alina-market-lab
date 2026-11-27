# Daily Risk Radar — Specification & Latest Reading

> **RISK MONITORING TOOL ONLY — Not a buy/sell signal generator or proof of trading edge. Phase C Kill Point remains active (0 validated directional edges across 54 experiments).**

Generated UTC: `2026-11-27T23:24:50+00:00` | Overall Risk Classification: **`HIGH`** | Fresh Panels: `5/9`

## 1. Panel Status, Data Sources, Freshness & Thresholds
| Panel | Last Updated | Age (d) | Freshness | Risk Class | Key Metrics | Warning |
|---|---|---:|---|---|---|---|
| `vol_term_structure` | `2026-11-27` | 0 | `FRESH` | **LOW** | `{"vix": NaN, "slope_3m": NaN, "slope_9d": NaN, "vvix_pct": 0.784}` | none |
| `ofr_fsi` | `2026-11-25` | 2 | `FRESH` | **LOW** | `{"ofr_fsi": -0.796, "credit": -0.755, "volatility_sub": 0.606}` | none |
| `equity_vol_dd` | `2026-11-27` | 0 | `FRESH` | **HIGH** | `{"spy_close": 728.32, "rv20_pct": 32.4, "rv63_pct": 19.87, "dd_52w_pct": -6.52}` | none |
| `support_resistance` | `2026-11-21` | 6 | `STALE_WARNING` | **MODERATE** | `{"instruments": [{"instrument": "BTC", "close": 57808.3906, "s1": 55932.7956, "r1": 59382.7643,` | Levels snapshot is 6d old (regenerate build_levels) |
| `calendar_7d` | `2026-11-27` | 0 | `FRESH` | **MODERATE** | `{"upcoming_7d_count": 2, "events": [{"date": "2026-11-30", "event": "MONTH_END", "detail": "las` | Note: ECB/BoE 2027 dates require annual calendar extension after Dec 2026. |
| `macro_rates` | `2026-11-20` | 7 | `STALE_WARNING` | **LOW** | `{"ecb_dfr": 2.5, "boe_rate": 4.0, "fed_rate_proxy": 3.88, "diff_boe_ecb_dfr": 1.5, "diff_fed_ec` | CB rates stale (7d) |
| `news_stress` | `2026-11-27T23:23:46` | 0 | `FRESH` | **ELEVATED** | `{"feeds_ok": 16, "feeds_total": 16, "unique_headlines": 1195, "stress_keyword_hits": 105}` | none |
| `crypto_funding_basis` | `2026-11-21` | 6 | `STALE_WARNING` | **LOW** | `{"deribit_btc_24h_apr_pct": -2.88, "deribit_btc_index": 58820.48, "okx_btc_24h_apr_pct": -0.46}` | none |
| `equity_short_insider_breadth` | `2026-11-20` | 7 | `STALE_WARNING` | **MODERATE** | `{"regsho_mkt_short_ratio": 0.4612, "regsho_ma5": 0.4745, "regsho_surge_5v60": -0.0242, "regsho_` | FINRA RegSHO stale (7d old) |

## 2. Calibrated Risk Meta-Labeling (`Task 3 + EXP-0030/0031`, Offline Sizing & Monitor Only)
- **As-Of Date:** `2026-11-27` | **Causal Train Cutoff (`-31d` Purge+Embargo):** `2026-09-15`
- **Calibrated Probabilities (`HGBC + Platt`):** `P(VolOnset_21d) = 0.0291` | `P(TailStress_21d) = 0.3502` | `P(TB_NonDirStress_21d) = 0.3502`
- **Stationary Macro/Vol State:** `OFR_FSI_z252=2.153`, `GPR_z252=-0.384`, `d_Fed_63d=0.25`, `VIX=28.29`, `Slope3M=1.076`, `RV21=31.59%`
- **Defensive Sizing Reference (`EXP-0031`):** `VolTarget12%=38.0%` × `MetaThrottle=0.945` -> **`Equity=35.9%` / `Cash Buffer=64.1%`**

## 3. FX Intraday Rollover & Cost-Shock Guard (`EXP-0030 Track B`)
- **`EURGBP H1` Last Bar:** `2026-11-20T18:00:00+00:00` | Spread `0.8 pips` (`z72=-0.16`) | In 6h Rollover Hazard (`16–23 UTC`): `True`

## 4. Crypto Daily Trend Regime & VolTarget25% Monitor (`EXP-0041 + EXP-0043`, Monitoring Reference)
- **`BTC-USD` As-Of `2026-11-27`:** Close `$59,754.67` | `SMA(50)=$74,240.11` (`Above=False`) | `TrendEns(20..120)=0.00` | `RV21=44.13%` | `19-Coin Breadth >SMA50`: `1/19 (5.3%)`
- **Vol-Targeted Reference (`VT25%`):** `TrendEns x VT25 = 0.0%` (`SMA50 x VT25 = 0.0%`) | Cash/EFFR `100.0%`

## 5. Active Risk Alerts
- **[HIGH] `equity_vol_dd`:** SPY RV20=32.4%, 52w DD=-6.5%
- **[MODERATE] `equity_short_insider_breadth`:** FINRA RegSHO mkt short ratio=0.461 (z60=-2.02)

## 6. Missing Data / Staleness Warnings
- support_resistance: freshness=STALE_WARNING (age=6d)
- macro_rates: freshness=STALE_WARNING (age=7d)
- crypto_funding_basis: freshness=STALE_WARNING (age=6d)
- equity_short_insider_breadth: freshness=STALE_WARNING (age=7d)
