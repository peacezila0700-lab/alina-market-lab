# WHAT FAILED — evidence, not opinion

Read this before spending a single token on a "new" idea. Tally at the time of writing:
**8 pre-registered experiments, 168 screen tests, 144 free-EA family tests, 0 validated edges.**

## Closed with numbers

| # | Idea | Result | Verdict |
|---|---|---|---|
| EXP-0001 | Long-only trend (10-month TSMOM) on 24 assets | Sharpe ~0.3 net, DD > 40%, fails 2013+ | REJECTED |
| EXP-0002 | Single-asset screen, 7 documented rules × 24 assets | best family flat; 22/24 "profitable" was a look-ahead artefact | REJECTED (bug) |
| EXP-0003 | Same, look-ahead corrected, 300-null permutation | no family beats null | REJECTED |
| EXP-0004 | Donchian breakout portfolio | positive but < null on most configs | REJECTED |
| EXP-0005 | XS mean-reversion G10 (equal-weight, 5-day) at assumed 1.3 pip | Sharpe +2.10 / +1.38 depending on window | PROVISIONAL (costs too optimistic) |
| EXP-0006 | EXP-0005 re-scored with MEASURED spreads | ECN +0.07 Sharpe (~breakeven); retail −0.08 | REJECTED |
| EXP-0007 | HK/TW/JP equity-index momentum, 2016–2021 hold-out | in-sample +0.413 -> hold-out **+0.126** | FAILED |
| EXP-0008 | Variance risk premium (short vol via VIX vs realised) | H11b Sharpe +0.694, worst 12 m **−103.7%** | REJECTED (crash risk) |

## Family sweep over the free-EA ecosystem (144 tests)
Mean Sharpe vs null by family, 24 instruments each:

| Family | Mean Sharpe | Instruments beating null (of 24) |
|---|---|---|
| BOLL_FADE | +0.04 | 1 |
| ICHIMOKU | +0.04 | 2 |
| RSI_FADE | +0.01 | 0 |
| STOCH_FADE | −0.03 | 1 |
| MACD | −0.04 | 1 |
| SUPERTREND | −0.61 | 0 |

6 of 144 beat the null; chance alone predicts 7.2. **No family edge.**

## Also dead / not worth retrying
- **Attention (Wikipedia pageviews) as a directional signal.** It improves next-day *volatility*
  forecasts (MAE better on 6 of 8 assets) but the portfolio Sharpe went 0.64 -> 0.63. Information
  ≠ tradeable edge.
- **Event-window trading around FOMC.** Move clustering exists but is not directional after costs.
- **Multi-timeframe intraday confirmation** (H1/H4 + ADX/GARCH/VWAP/confluence filters): 2-month
  window, all variants ≈ 0. Cannot be validated on free data (Yahoo H1 limited to 730 days,
  Dukascopy tick feed 503).
- **Kalman/OU pairs trading across 8 assets:** Gaussian log-likelihood gain (28.1) did not survive
  cost-per-round-trip; mean half-life 3.2 days is too slow for the spread width available.
- **Martingale/grid EA family:** see PITFALLS #9 — 5 of 5 accounts wiped.

## What this means for the next AI
The failure pattern is consistent: **any signal that survives in-sample dies on (a) measured costs,
(b) a genuine hold-out, or (c) a permutation null.** Design accordingly — pre-register, charge real
costs, hold data out, and compare against a turnover-matched random control. The value left is not
in retesting these; it is in new data sources and in position/flow information (COT, options
skew, dealer gamma) that is not in the price series at all.

### Session 2026-11-20 (widest panel yet) — 5 more, all rejected
| # | Idea | Verdict | One-line reason |
|---|---|---|---|
| EXP-0010 | Event-conditional direction (FOMC / OPEX / month-end / VIX crossing 30) | FAIL | The interaction is significant in-sample and flips sign out-of-sample. Events change the variance, not the sign (SPY FOMC day = 1.09x a random day). |
| EXP-0011 | Treasury auction demand (bid-to-cover z, dealer share) -> TLT/IEF/SPY | FAIL | No term passes |t|>=2 in-sample with an OOS confirmation. Information is already in the auction-day yield move. |
| EXP-0012 | Cross-sectional momentum 12-1, 1M reversal, 5D reversal on 68 ETFs | FAIL | Momentum 78.5th pct, 1M reversal 93rd pct of the turnover-matched null, 5D reversal negative. |
| EXP-0013 | Market-state exposure overlay (breadth, credit, vol level, dispersion, gamma) | FAIL | Best overlay (gamma) hit the 100th percentile in-sample but only the 90th OOS; nothing cleared the bar. |
| EXP-0014 | Dealer gamma overlay vs plain volatility targeting | FAIL | The gamma increment is +0.067 Sharpe IS (88.5th pct) and +0.041 OOS (74th pct) — inside the null. Gamma is vol targeting with a label. |

**What this session actually learned (more valuable than the failures):**
1. The scheduled calendar does not move the tape more than a random day. Only crisis onset does
   (|move| 1.65–1.75x). Stop building calendar strategies; build onset detectors.
2. Volatility, not direction, is the exploitable dimension for state variables. Sizing overlays
   reliably cut drawdown (gamma overlay: −27% vs −51% buy-and-hold) without adding expected return.
3. Null design is the whole game. Two null bugs in this session would have produced two false passes
   (see PITFALLS #11, #12), and one seemingly perfect result was vol targeting in disguise (#13).

### Same session, second sweep (term structure + carry) — 2 more, both rejected
| # | Idea | Verdict | One-line reason |
|---|---|---|---|
| EXP-0015 | CBOE term structure (VIX/VIX3M, VIX9D/VIX, VVIX) forecasts a vol onset | FAIL (predictable, not tradeable) | Forward-8d onset AUC 0.746 and Brier skill +0.168 — real skill — but the exposure overlay loses to plain vol targeting by −0.28 Sharpe OOS. |
| EXP-0016 | Treasury curve slope pays duration via carry/roll-down | FAIL | No term clears the 98.75th-percentile bar in both IS and OOS. It does halve the 2022-26 bond drawdown — risk avoidance, not alpha. |

**The taxonomy this produced (use it to frame every future idea):**
- **Variance IS forecastable.** Term structure predicts a vol onset with AUC 0.75, and vol clustering is
  the most robust effect in all of finance. Claims about variance need Brier skill / AUC / calibration.
- **Direction is NOT.** 16 experiments, ~500 sub-tests, zero directional edges that survive a
  turnover-matched null plus a vol-targeting benchmark. Claims about direction need excess Sharpe over
  vol targeting, a date split, and a shift null — and nothing else counts.
### Hour-scale FX, tested properly for the first time — 2 more, both rejected
| # | Idea | Verdict | One-line reason |
|---|---|---|---|
| EXP-0017 | 5 classic hourly rules on 6 pairs with real bid/ask (2003-2026, ~145k bars each) | FAIL | Pooled net Sharpe ranges −0.4 to −10.8. 1-hour reversal has a real GROSS edge of +0.19 bp/hour and pays 0.34 bp/hour in spread. |
| EXP-0018 | Sparse gating (big moves only / London-NY overlap / both) | FAIL | Gating halves the loss and never flips it. Breakeven cost multiple 0.03-0.29: spreads must be 3-30x tighter than Dukascopy quotes. |

**What the hour-scale data is still good for** (this is the constructive part): `HOUR_OF_DAY_PROFILE.md`
gives the measured spread and high-low range for every hour of the UTC day, per pair. EURUSD quotes
0.40-0.50 pips with a 50-65x range/spread ratio in the London-NY overlap and 6-11x at the 21-23 UTC
rollover. Use it for execution timing, stop placement and instrument choice — not for direction.
### Congressional trade disclosures — FAIL, but kept open (EXP-0019, 2026-11-21)
First experiment on genuinely non-price information: 6,365 parsed House PTR transactions, 1,137 with a
complete 21-day forward window on a 61-name large-cap panel. In-sample the purchases did *worse* than
random dates in the same stocks (0th percentile); out-of-sample they did better (99.5th percentile).
The two halves disagree completely, so the bar is not met and no edge is claimed.
**The lesson is about study design:** a report that showed only the out-of-sample window would have
announced a 99.5th-percentile congressional edge. It is also not a proof of "no effect" — a 16-month
sample in one selloff cannot settle it, so H21 stays open instead of being closed.

### Purged walk-forward ML on US & Thai stocks — FAIL (EXP-0020, EXP-0021, 2026-11-21)
Directly tested whether training real tabular ML models (`Ridge`, `HistGradientBoosting`) to rank stocks
and find entry timing works better than hand-coded rules, with zero target overlap and 1-bar execution
lag:
- **EXP-0020 (112 US large caps + macro/vol/DIX-GEX + PIT SEC fundamentals, 5 bp/side):** All 5 ML arms
  failed the 99th-percentile turnover-matched null (L/S OOS Sharpe −0.115 to +0.360, 76th–89th pct).
  On long-only top quintile, every ML model (+0.63 to +0.96 OOS Sharpe) lost to plain equal-weight
  buy-and-hold (+1.39). Adding causal point-in-time fundamentals (`pit_fundamentals.csv`) did not lift OOS.
- **EXP-0021 (64 Thai SET stocks, 27 bp/side retail cost = 16.8 bp Cash Balance fee+VAT + ~10 bp spread):**
  Classic 5-day reversal loses −2.37 / −1.70 Sharpe (breakeven +4.9 bp/side vs 16.8 bp fee floor).
  Walk-forward ML (`Ridge`, `HGB`) looked great in-sample (100.0th / 99.5th pct, Sharpe +0.64 / +0.21)
  and **flipped negative out-of-sample** (−0.37 / −0.29 Sharpe, 57.5th / 68th pct).

**Why this matters:** Throwing ML at daily price/technical features — even with lagged macro and SEC
fundamentals — does not create an alpha signal when the underlying features lack net edge after costs.

### Standalone PIT SEC anomalies & 1H OKX crypto — FAIL (EXP-0022, EXP-0023, 2026-11-21)
- **EXP-0022 (62 US GAAP large caps, quarterly 63d rebalance on non-restated `pit_fundamentals.csv`, 5 bp/side):**
  Tested 4 fundamental mechanisms standalone (`F_NEG_ACCRUALS` Sloan accruals, `F_CFO_ASSETS`, `F_REV_YOY`,
  `F_QUALITY_COMP`). Sloan accruals was positive across both halves (IS +0.624 / OOS +0.947, 93.5th / 92.0th pct,
  long-only OOS +2.015 vs EW +1.830), falling short of the 98.75th-pct power bar on a 62-firm universe.
- **EXP-0023 (OKX BTCUSDT + ETHUSDT 1H, 9,999 confirmed bars, 5–10 bp/side):**
  ETH-BTC 24h spread reversion had genuine gross Sharpe (+1.604 IS / +2.389 OOS, breakeven 2.62–3.06 bp/side)
  but flipped negative at 5 bp maker (−1.510 OOS) and 10 bp taker (−4.431 / −5.290).

### 23-Year Dukascopy H1 Bid/Ask & EA KB Blueprint Strategies — FAIL (EXP-0024, EXP-0025, 2026-11-21)
Following EA KB Batch 4 synthesis (`reports/EA_KB_ALPHA_RISK_BLUEPRINT.md`), tested passive limit OU (`H26`),
London-NY fix reversion (`H27`), and trailing-vol compression + max-spread guardrails (`H28`) against market
entries and H1 scalping across **23 years of real quoted Dukascopy H1 bid/ask bars** (`147,297` EURGBP + `148,482`
EURUSD, live `.bi5` cross-verified) and **4 public broker cost tiers** (Dukascopy Measured, IC Markets Raw ECN,
Exness Raw, Exness Standard) + `[0, 0.35]` pip/night swap bounds:
- **EXP-0024 (`H26` / `H27`):** On 23-year EURGBP, `H26_LIMIT_OU` saved `+0.78` pips/trade vs `H26_MKT_COMPARE`
  (−1.60 vs −2.38 pips ALL, confirming passive limit execution cuts spread drag), yet stayed negative across IS
  (−1.80, n=1,826), VALID (−0.48, n=386), and OOS_LOCKED (−4.28, n=30). `H27_LONDON_FIX_REVERT` lost in every
  split (−2.25 / −2.25 / −1.81, PF 0.56). On control EURUSD, `H26_LIMIT_OU` looked positive in 2022–2026
  (+0.32 VALID / +7.70 OOS) ONLY because 18.4y IS (2003–2021, n=2,131) lost −3.71 pips (ALL −2.75).
- **EXP-0025 (`H28` + H1 Scalp + 4-Broker Stress):** `H28_REGIME_GUARDED` posted VALID +1.08 (CI [−1.56, +3.31])
  before failing IS (−1.84) and OOS_LOCKED (−4.93, ALL −1.41). `H28_H1_SCALP_BASELINE` failed catastrophically
  (EURGBP −3.35 PF 0.47, 0.0th null pct; EURUSD −5.86 PF 0.33), empirically locking Decision `D02`. **Every
  rule remained negative across all 4 broker models** (even Exness Raw: −1.06 to −3.07 pips on EURGBP).
  **Phase C Kill Point enforced:** Phase D ML and demo/live EA deployment remain PARKED; `AlinaRiskGovernor.mq5`
  stays `SIG_NONE` / `MODE_PAPER`.

- **EXP-0023 (OKX BTCUSDT + ETHUSDT 9,999 confirmed 1H bars, 2025-10..2026-11, 10 bp/side taker):**
  `CR_PAIR_ETH_BTC` (24h spread reversion) showed genuine gross Sharpe (+1.604 IS / +2.389 OOS, breakeven
  +2.62 / +3.06 bp/side) that was wiped out by OKX taker fees (−4.43 / −5.29 net at 10 bp; −1.51 at 5 bp maker).
  Matches the hourly FX cost wall in EXP-0017/0018.


