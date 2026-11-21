# ALINA Market Lab — Research Log (`EXP-0001..0029`)

Last Updated UTC: `2026-11-21T11:40:00Z`

## Chronological Summary
- **`EXP-0001..0023` (Stages 1–9 Baseline):** Tested FX daily/H1 technicals, trend/mean-reversion, COT, macro/events, US ML equities (`112` stocks), Thai SET64 ML/momentum, baseline SEC PIT (`62` firms), and 1H OKX crypto (`9,999` bars). **Result:** `0` validated directional edges (`FAIL` on OOS + permutation/cost walls).
- **`EXP-0024 & EXP-0025` (Phase C Kill Point):** Tested KB-derived passive limit OU (`H26`), London-NY fix exhaustion (`H27`), and regime/spread-guarded OU vs H1 scalping (`H28`) on 23-year Dukascopy `EURGBP` (`147,297` H1 bars) and `EURUSD` (`148,482` H1 bars) across 4 public broker cost tiers. **Result:** `FAIL` across all rules and brokers -> **Phase C Kill Point triggered** (Phase D ML & Live/Demo trading parked).

## Phase 2 Research Continuation (`EXP-0026..0029`)
### `EXP-0026` — Workstream A1: SEC EDGAR PIT Fundamentals Expanded (`N=317` US-GAAP Firms)
- **Hypothesis (`H29`):** Expanding Sloan Cash Accruals (`F_NEG_ACCRUALS`) from `62` to `>=300` US-GAAP firms with strict SEC `acceptanceDateTime` 16:00 ET cutoff clears the `99.0th` percentile turnover-matched null in both IS (`2016–2021`) and OOS (`2022–2026`).
- **Evidence Quality:** `317` companies, `15,073` causal PIT snapshots, `0` pre-period leaks (`rop` XBRL typo caught and dropped). *Known Limitation:* Current Nasdaq market-cap screener introduces survivorship bias (missing delisted companies).
- **Results (`10 bp/side`):** `F_NEG_ACCRUALS` IS `+0.943` (`99.0%`) / OOS `+0.525` (`90.0%`); `5 bp` ALL `+0.746`; `20 bp` OOS `+0.494`; Large/Mid OOS `+0.442 / +0.541`; `F_SECTOR_NEUT_ACCRUALS` OOS `+0.204` (`74.5%`); `F_CFO_ASSETS` OOS `-0.691`; `F_QUALITY_COMP` OOS `-0.726`. BH FDR `False/False`.
- **Conclusion:** Economic signal is structurally real relative to price-only EAs, yet **FAILS** strict Bonferroni promotion bar and lacks delisted-firm adjustment.

### `EXP-0027` — Workstream A2: Macro, Central Bank & Volatility Event Intelligence (`2009–2026`)
- **Hypothesis (`H30`):** Macro rates (`ECB`, `BoE`, `NYFed EFFR`), `COT`, `VIX` term structure, `OFR FSI`, lagged `GPR`, and `FOMC/BoE/ECB` events add OOS skill for volatility, regimes, and risk sizing even without directional return alpha.
- **Results:**
  - *Directional (OOS `>=2021-01-01`):* **FAIL** (`SPY 5d +0.153`, `40.0%` shift; `SPY 21d +0.821`, `90.5%`; `EURGBP 5d -0.423`, `24.0%`).
  - *Volatility (OOS):* Vol-Expansion Onset **AUC = `0.7212`**, forward 21d RV correlation **`+0.4271`** (level `R² = -0.021`). Event-day `|move|` ratios: `BoE` **`1.573x`**, `FOMC` **`1.187x`**.
  - *Regimes:* Inverted `VIX/VIX3M > 1.0` produces **`38.12%`** realized SPY vol vs **`13.56%`** normal; `OFR FSI > 0` **`26.36%`** vs **`12.90%`**.
  - *Risk-Sizing:* Causal 12% Vol-Targeting cuts SPY IS MaxDD **`-34.10% -> -16.57%`** and OOS MaxDD **`-25.36% -> -16.18%`** (`ALL Sharpe +0.739` vs `+0.726` Buy & Hold).
- **Conclusion:** Promote to **Workstream D Risk Radar**; zero directional alpha claim.

### `EXP-0028` — Workstream B1: 23-Year Official FX Carry + H1 Bid-Ask Timing (`2003–2026`)
- **Results:**
  - *Spread Microstructure:* `20:00–21:00 UTC` rollover costs **`2.4x`** (`EURGBP`: `2.6` vs `0.9` pips) and **`4.0x`** (`EURUSD`: `1.6` vs `0.4` pips) normal London/NY liquidity.
  - *Carry Net of Costs:* Zero-markup 23y `EURGBP` carry Sharpe is `+0.140` (`-18.9%` MaxDD), falling to `+0.006` (`-21.53%` MaxDD) at `0.25` pips/night retail swap markup and `-0.128` at `0.50` pips/night (`EURUSD` `-0.089` to `-0.219`).
- **Conclusion:** **FAIL** for retail carry trading; **KEEP** rollover spread-avoidance insight.

### `EXP-0029` — Workstream B2: Deribit `25,284` 1H Funding/Basis & OKX Cross-Venue Audit (`2024–2026`)
- **Results:**
  - *Deribit Cash-and-Carry:* Mean BTC funding fell from `8.29%` (IS) to `3.84%` (OOS) and ETH from `5.51%` to `1.74%`. Under realistic Maker (`14 bp RT + 5% APR borrow`) and Taker (`32 bp RT + 8% APR borrow`) costs + `1h` lag + perp-vs-index basis MtM swings, ALL OOS ETH tiers (`-0.051..-0.151`) and nearly all BTC tiers (`-0.095..-0.318`, `MaxDD -21%..-39%`) lose money (`15%->5%` Maker BTC barely `+0.035` / `+0.57%` CAGR).
  - *Cross-Venue `OKX vs Deribit`:* Over `10,000` overlapping 1H bars (`2025-09..2026-11`), 95th `|spread|` is **`12.89 bps`** (below `24–32 bps` 2-exchange taker round-trip execution cost), and OKX public funding caps at `93` days (`280` rows).
- **Conclusion:** **NOT ARBITRAGE / FAIL**.

### Workstream C — EA KB Batch 5 (`118` GitHub Headers + `5`-Archetype Scan)
- **Verified Fact:** `2,100` source files verified on disk (`sqlite_integrity == ok`), `1,322` duplicate relations tracked. Structural archetypes across corpus: `multi_currency` (`126`), `basket_trading` (`37`), `hedging` (`278`), `vol_breakout` (`204`), `icustom_usage` (`99`).
