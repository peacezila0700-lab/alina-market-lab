# MULTI-ASSET SCREEN + PORTFOLIO — corrected results after QR-002

**Status: this report replaces the multi-asset numbers quoted in the previous commit. Those numbers were produced by code with a same-bar look-ahead and are wrong.**

- Universe: 24 instruments across 7 classes (FX, metals, energy, indices, bonds, crypto, agri), 2000–2026
- Data: Yahoo daily closes (`data/universe/`, 3,299–6,829 bars per instrument)
- Rules: 7 documented rules (`MA_20_100`, `MA_50_200`, `DONCHIAN_55`, `TSMOM_6M`, `TSMOM_12M`, `Z_FADE`, `BUY_HOLD`) = 168 tests
- Cost: per-class assumed spread charged on every position change (fx 0.015%, metal 0.03%, index 0.02%, bond 0.03%, energy 0.06%, crypto 0.08%, ag 0.10%) — **assumptions, not measured**
- Null control: 300 random signal permutations per test with matched turnover; `null_pct` = percentile of the real Sharpe inside the random distribution (100 = beat every random draw)

## What the bug did

`pnl[i] = pos[i] * ret[i]` let each rule hold today's position for the move that had already happened. Fix: `pnl[i] = pos[i-1] * ret[i]`. One line. It deleted most of the "edge":

| | buggy (previous commit) | corrected |
|---|---:|---:|
| Best single test, BTC DONCHIAN_55 null_pct | 95–100 on nearly all 24 assets | mid-pack, mostly 73–98 |
| DONCH_30 portfolio | **Sharpe 1.72, CAGR +30.7%** | **Sharpe 0.37, CAGR +4.9%** |
| DONCH_55 portfolio | Sharpe 1.04, CAGR +17.0% | Sharpe 0.20, CAGR +1.9% |
| DONCH_100 portfolio | Sharpe 0.67, CAGR +10.1% | Sharpe 0.30, CAGR +3.7% |
| Equal-weight buy & hold | Sharpe 0.70, CAGR +11.6% | Sharpe 0.70, CAGR +11.6% (unchanged — no timing) |

**Every Donchian portfolio loses to plain equal-weight buy & hold.** The "breakout edge across all assets" was the bug. Regression test `test_position_must_be_lagged_no_lookahead` now guards it (14/14 pass), and `compare_strategies.py` had the same defect and was re-run as well (conclusion unchanged there: FX rules are ≈0 after costs).

## Best rule per asset (corrected, full sample)

| Asset | Best rule | Sharpe | CAGR | null_pct | buy & hold Sharpe | rule − B&H |
|---|---|---:|---:|---:|---:|---:|
| AUDUSD | Z_FADE | 0.27 | +0.8% | 93 | 0.01 | **+0.26** |
| BTC | TSMOM_12M | 0.81 | +33.5% | 96 | 0.78 | +0.03 |
| COPPER | MA_20_100 | 0.30 | +4.6% | 95 | 0.39 | −0.09 |
| CORN | DONCHIAN_55 | 0.16 | +0.5% | 84 | 0.27 | −0.11 |
| DAX | TSMOM_6M | 0.27 | +3.5% | 93 | 0.33 | −0.06 |
| DXY | MA_20_100 | 0.17 | +1.0% | 83 | 0.06 | +0.11 |
| ETH | MA_20_100 | 0.44 | +6.7% | 90 | 0.53 | −0.09 |
| EURUSD | DONCHIAN_55 | 0.08 | +0.3% | 73 | 0.02 | +0.06 |
| FTSE | Z_FADE | 0.31 | +1.1% | 98 | 0.18 | **+0.13** |
| GBPUSD | Z_FADE | 0.15 | +0.3% | 78 | −0.08 | **+0.23** |
| GOLD | TSMOM_12M | 0.55 | +8.6% | 100 | 0.64 | −0.09 |
| HSI | TSMOM_6M | 0.24 | +2.9% | 91 | 0.16 | +0.08 |
| IEF | TSMOM_12M | 0.12 | +0.6% | 76 | 0.10 | +0.02 |
| NASDAQ100 | TSMOM_12M | 0.45 | +8.4% | 99 | 0.40 | +0.05 |
| NATGAS | Z_FADE | 0.10 | −1.2% | 74 | 0.29 | −0.19 |
| NIKKEI | MA_50_200 | 0.22 | +2.3% | 89 | 0.30 | −0.08 |
| PLATINUM | Z_FADE | 0.02 | −0.6% | 55 | 0.31 | −0.29 |
| SILVER | MA_50_200 | 0.30 | +4.6% | 95 | 0.41 | −0.11 |
| SP500 | MA_50_200 | 0.33 | +4.5% | 96 | 0.40 | −0.07 |
| TLT | MA_20_100 | 0.26 | +2.7% | 92 | 0.07 | **+0.19** |
| USDCAD | TSMOM_6M | 0.09 | +0.4% | 70 | 0.07 | +0.02 |
| USDJPY | TSMOM_12M | 0.33 | +3.1% | 98 | 0.20 | **+0.13** |
| WHEAT | Z_FADE | −0.02 | −1.4% | 44 | 0.27 | −0.29 |
| WTI | MA_50_200 | 0.08 | −5.4% | 64 | 0.30 | −0.22 |

**6 of 24 assets** have any rule beating their own buy & hold by more than 0.10 Sharpe — and 4 of those 6 are **mean-reversion (`Z_FADE`) on AUDUSD, GBPUSD, FTSE** or `MA_20_100` on bonds/DXY. Trend rules (Donchian, TSMOM, MA crossovers) mostly **underperform just holding the asset**.

The highest raw Sharfes in the whole screen (BTC 0.78, GOLD 0.64, ETH 0.53 buy & hold) are **asset beta, not strategy**. You get them by owning the asset through a bull market, with crypto drawdowns over 500% on the un-levered curve.

## Portfolio construction

Equal weight across all instruments with data on that day (average 17.1 active, 22 at the end), daily rebalance, one-bar lagged positions, costs charged on position change.

| Portfolio | CAGR | Vol | Sharpe | maxDD | worst year |
|---|---:|---:|---:|---:|---:|
| DONCH_30 (rebalance daily) | +4.89% | 16.3% | 0.37 | 54.3% | −12.7% |
| DONCH_55 | +1.89% | 16.6% | 0.20 | 128.2% | −16.4% |
| DONCH_100 | +3.69% | 16.3% | 0.30 | 156.9% | −30.7% |
| **Equal-weight buy & hold** | **+11.56%** | 17.8% | **0.70** | 66.9% | −31.3% |

Yearly DONCH_55 tells the same story: the only strong years are trend-heavy macro years (2016 +28%, 2017 +32%, 2020 +30%, 2021 +34%, 2022 +14%) and everything else is noise or loss (−16.7% 2018, −17.5% 2019, −10.4% 2023, −15.7% 2025, −8.9% 2026 YTD).

maxDD above 100% is the un-levered equity curve crossing zero — read it as "account wiped".

## Honest verdict

1. The multi-asset Donchian result **does not survive** a correct lag. D10 stands: **buy & hold is the bar**, and no breakout portfolio here beats it.
2. The screen did surface two consistent, repeatable *directions* worth a deliberate test, both **mean-reversion, not trend**: FX majors (AUDUSD, GBPUSD) and FTSE. That is consistent with the earlier FX `RANGE_FADE` +0.13 post-2013 finding. This is the one thread with independent corroboration.
3. Data caveat: Yahoo contains bad prints up to 13.8% (EURUSD 2008-12-08), so absolute FX levels here are shape-only. Any confirmation run must use ECB (1999+, official) or Bank of Canada / SNB for the crosses ECB does not publish.

## Next actions this points to

- **A1** — Build a dedicated mean-reversion test on the 6 ECB pairs + FTSE/AUDUSD/GBPUSD with a proper null and walk-forward split. Pre-register it before running.
- **A2** — Measure real spreads (T18) before believing any cost-charged result on 0.1–0.3 Sharpe edges.
- **A3** — Event/news layer (the owner's standing request): macro calendar to test *why* these windows are mean-reverting.

_Artifacts: `research/artifacts/universe_screen.{csv,json}`, `research/artifacts/portfolio_donchian.json`. Regenerate with `scripts/screen_universe.py` and `scripts/portfolio_donchian.py`._
