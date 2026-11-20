# STRATEGY COMPARISON — documented methods on 27 years of official data

- **Data:** ECB Statistical Data Warehouse, daily reference rates, **1999-01-04 → 2026-11-20**, 7,141 days
- **Pairs (6):** EURUSD, EURGBP, EURCHF from ECB; GBPUSD, GBPCHF, USDCHF **derived** as documented crosses
  (GBPUSD = EURUSD/EURGBP etc. — arithmetic, not invention)
- **Cost:** 1.3 pips round trip charged on every unit of position change (0.65 pip per side)
- **Portfolio:** equal weight across the 6 pairs
- **Source quality note:** the same cross-check found Yahoo's EURUSD **13.84% off ECB on 2008-12-08**
  (Yahoo 1.4918 vs ECB 1.2854) → ECB is now the canonical long-history source.

## 1. Headline table (net of cost, 1999–2026)

| rule | literature | CAGR | Sharpe | max DD | Sharpe pre-2013 | Sharpe post-2013 |
|---|---|---|---|---|---|---|
| **TSMOM 12M — Moskowitz/Ooi/Pedersen (2012)** | — | -0.18% | -0.01 | 35.9% | 0.11 | -0.18 |
| **TSMOM 1M — same paper, short lookback** | — | -0.16% | -0.01 | 26.6% | 0.1 | -0.14 |
| **MA 50/200 trend (classic, Faber-style)** | — | 0.42% | 0.11 | 25.6% | 0.27 | -0.11 |
| **MA 20/100 trend (faster)** | — | 0.63% | 0.15 | 21.0% | 0.3 | -0.05 |
| **RANGE_FADE — our own H01 (control)** | — | -0.05% | -0.03 | 7.6% | -0.16 | 0.12 |
| **BUY & HOLD (benchmark)** | — | -0.81% | -0.21 | 41.1% | -0.17 | -0.25 |
| **RANDOM position (benchmark)** | — | -2.21% | -0.6 | 90.2% | -0.52 | -0.69 |

## 2. What the numbers say

**1. Every documented trend rule is flat-to-slightly-positive after cost.**
   MA 20/100 is the best at Sharpe 0.15 (CAGR +0.63%). TSMOM 12M — the most cited FX momentum
   result — comes out at Sharpe −0.01 on this sample.

**2. The decay is the real story.** Every trend rule was mildly positive before 2013 and
   negative after (MA 20/100: 0.30 → −0.05; MA 50/200: 0.27 → −0.11). This matches the
   industry-wide decline of FX trend following after the GFC, not a coding error.

**3. Our own range-fade rule flips sign exactly the same way** (−0.16 → +0.12).
   Third independent confirmation that the z-score effect is regime noise, not edge.

**4. The random benchmark loses 2.21%/yr** with the same turnover. That is the cost drag the
   real rules have to overcome — and it proves the pipeline charges costs properly. If the
   random benchmark had come out near zero, I would distrust the whole comparison.

**5. Buy & hold 6 FX pairs vs USD loses (CAGR −0.81%)** — unsurprising over a period of
   general dollar strength; it is included so that 'flat' strategies have context.

## 3. Per-pair Sharpe, full period (best and worst pair per rule)

| rule | best pair | Sharpe | worst pair | Sharpe | dispersion |
|---|---|---|---|---|---|
| TSMOM_12M | EURCHF | 0.25 | EURUSD | -0.14 | 0.39 |
| TSMOM_1M | EURUSD | 0.32 | EURCHF | -0.22 | 0.54 |
| MA_50_200 | EURCHF | 0.26 | USDCHF | -0.01 | 0.27 |
| MA_20_100 | EURUSD | 0.32 | USDCHF | -0.05 | 0.37 |
| RANGE_FADE | GBPUSD | 0.29 | EURUSD | -0.3 | 0.59 |
| BUY_HOLD | EURGBP | 0.11 | EURCHF | -0.29 | 0.4 |
| RANDOM | GBPUSD | -0.18 | EURCHF | -0.43 | 0.25 |

## 4. Why this comparison is not the last word

- **Reference rates are fixes, not tradeable prices.** ECB publishes one rate per day (~14:15 CET).
  No bid/ask, no intraday path. A real trend system trades at a price and pays a spread; this
  dataset cannot capture slippage or execution timing.
- **Cost is assumed** (1.3 pips). At institutional futures costs (≈0.2–0.5 pip equivalent) the
  trend rules would look better — that is precisely why the literature reports significance on
  futures data and retail traders rarely reproduce it.
- **Monthly rebalancing** for TSMOM understates turnover (and therefore cost), while daily MA
  rules overstate it. Both are reported with turnover in the JSON.
- **6 pairs, all USD/EUR-centric.** No carry, no EM, no cross-sectional ranking (which is where
  the documented FX premia mostly live).

## 5. What I would test next, if the owner wants more (all still free, no new cost)

| idea | data needed | why it is worth one session |
|---|---|---|
| **Carry** (Lustig–Roussanov–Verdelhan 2011) | policy/deposit rates per currency (ECB, BoE, SNB, RBA publish free) | the only FX premium with a persistent economic mechanism (interest differential) |
| **Cross-sectional momentum/value ranking** across many pairs | more pairs (RBA/BoC/SNB APIs) | the documented premia are cross-sectional, not time-series; our tests were all time-series |
| **Trend with volatility targeting** | same data | scales positions, does not change direction — cheap to test |
| **Session/hour effects** | intraday with real spread | needs broker data; cannot be done on fixes |

## 6. Bottom line

On 27 years of central-bank data, with honest cost accounting, **none of the documented FX
daily strategies produces a meaningful net Sharpe**. The measured edge is not absent because
the code is wrong — the random benchmark proves costs are applied — it is absent because
a 1.3-pip cost on a fix-to-fix series with ~0.5% daily volatility leaves almost nothing.

**The next honest step is carry or cross-sectional testing, not another single-pair rule.**
