# DECISION INPUTS ATLAS — what a person actually uses to decide a trade, layer by layer

Compiled 2026-11-20 from: (a) published practitioner frameworks (institutional macro desks, global
macro funds, quant funds), (b) the academic literature that those desks actually cite, and (c) this
repo's own measurements (`data/facts/base_rates.csv`). Every "free source" line was tested from this
sandbox — `[OK]` = fetched successfully, `[DEAD]` = verified failure, exact endpoints in
`knowledge/DATA_SOURCES.md`.

**Reading order for an AI:** L1 regime → L2 what is priced → L3 who is positioned → L4 flows/liquidity
→ L5 stress/credit → L6 volatility/tails → L7 calendar/catalysts → L8 fundamentals → L9 real economy
supply → L10 narrative/attention → L11 technicals as *structure only* → L12 execution/costs.
Then P (probability principles) and E (what makes an edge special).

A note that saves a lot of money: **L1–L6 describe the environment; they rarely trade by themselves.**
The tradeable part is almost always a *mismatch* between what is priced (L2) and what is likely
(L1/L7/L9), with positioning (L3) telling you how violently that mismatch would resolve.

---

## L1. REGIME — growth / inflation / liquidity / policy

**What desks actually do.** Name the regime before looking at any chart: growth accelerating or
decelerating × inflation rising or falling × liquidity easing or tightening. Bridgewater's "economic
machine", the four-quadrant framework (growth/inflation), and every "institutional macro" write-up say
the same thing: the same data point means opposite things in different regimes [1][5][9]. A strong
payroll print is bullish when the Fed is on hold and bearish when the Fed is behind the curve.

**The mechanics that matter.** Regime determines (i) the sign of the growth→asset mapping, (ii) cross-
asset correlation (equities/bonds hedge each other in a low-inflation regime and stop hedging in an
inflation shock), (iii) which factor works (momentum/quality in slowdowns, small-cap/value in early
recovery).

**Numbers worth carrying.** Equity/bond correlation flipped positive in 2022 and stayed there for
quarters — the single most expensive regime error of the decade for 60/40 allocators. Regime models
built on growth+inflation+policy beat single-indicator rules in most published tests, but they are
slow and they whipsaw at turning points, which is precisely when being early is expensive.

**Encode as:** 4-8 continuous state variables (not labels) — PMI/ISM new-orders level & 3-month change,
CPI/PCE momentum, policy-rate expectation delta (from futures), real yield, credit impulse, dollar
trend — then either a 2-D regime map (growth vs inflation score) or a 3-state HMM on their first PCs.

**Free sources:** ECB/Eurostat `[OK]`, World Bank `[OK]`, ONS `[OK]`, Treasury yield curve `[OK]`,
Fed H.15 `[OK]`, OECD SDMX `[DEAD 403]`, IMF datamapper `[DEAD 403]`, FRED `[DEAD timeout]`.
Practical workaround: build regime variables from *market prices* (yield curve, breakevens, DXY) plus
the official agencies that do answer (ECB, ONS, Eurostat, World Bank, Treasury).

**How it fails:** regime labels are revised, they lag by construction, and the market prices the next
regime before the data confirms it. Use regimes to size and to gate, never to predict the next print.

---

## L2. WHAT IS ALREADY PRICED — the "no edge if it's priced" rule

**What desks actually do.** Before treating a view as a trade, they check market-implied expectations:
policy path from money-market futures, breakevens for inflation, credit spreads for default, implied
vol for uncertainty, FX forwards for differentials, COT for positioning [6]. A correct view with
nothing left to reprice is not a trade.

**Numbers.** Futures-implied policy paths, mapped to probabilities (FedWatch-style), have historically
been well-calibrated at horizons of 1–3 meetings and poorly calibrated beyond ~6 months (the market
front-runs and then re-prices). That asymmetry is the exploitable part: fade the far-dated path, respect
the near-dated one.

**Encode as:** for each asset, `implied_expectation` vs `your_estimate` → the trade is the *difference*,
sized by how much of the difference is already in the price. Practical proxies on free data: yield-curve
slope, VIX level vs realised vol, put/call or skew, futures basis, carry.

**Free sources:** Treasury yields `[OK]`, SOFR/EFFR from the NY Fed `[OK]`, CME FedWatch `[DEAD, IP-blocked]`
→ compute implied probabilities yourself from short-rate futures or use the NY Fed's published
probabilities page. `frankfurter.app` `[OK]` for FX spot (ECB-based, tiny payload).

---

## L3. WHO IS POSITIONED — crowding, and why it dominates

**What desks actually do.** Positioning data decides *how* a view pays, not *whether* it is right:
CFTC COT (weekly), options OI & skew, futures OI, prime-brokerage net exposure, ETF holdings changes,
13F for the equity side [4][6]. Crowded trades resolve violently; uncrowded ones drift.

**Numbers from this repo (verified, non-overlapping samples).** Extreme COT positioning does **not**
mean-revert on average: 59 tests across 24 contracts → **0** hits consistent with the contrarian read,
while 3 hits pointed *with* the crowd (EURUSD funds extremely long → +1.06% over 4 weeks, t≈3.0;
GOLD +2.1% over 8 weeks). The folklore ("fade the funds") is not supported by this data; positioning
momentum is the more interesting lead and remains untested properly.

**Other body-positioning facts worth knowing.** SqueezeMetrics DIX (dark-pool buy/sell imbalance) shows
a monotone relation with 1-month forward SPY returns in our own sample: bottom quintile median +1.17%,
top quintile +2.09% (`data/facts/base_rates.csv`). Dealer-gamma sign flips the character of the tape:
negative GEX quarters show higher forward returns *and* fatter right tails (+2.66% mean vs +0.87%,
p90 +10.3% vs +4.9%) — the "amplification" regime, which is where crashes and squeezes both live.

**Encode as:** z-scores and percentile ranks per instrument, plus *change* (who is adding, not who holds),
plus concentration (top-4 share), plus a crowding composite across COT + options + ETF flows. Always
`available_from`, never as-of date.

**Free sources:** CFTC Socrata `[OK]`, SqueezeMetrics DIX/GEX `[OK]`, OKX long/short + funding `[OK]`,
Deribit option chain (skew) `[OK]`, Nasdaq short interest `[OK]`, SEC 13F/XBRL `[OK, needs contact UA]`,
FINRA short volume `[DEAD without key]`, Binance `[BLOCKED from this IP]`.

---

## L4. FLOWS AND LIQUIDITY PLUMBING

**What desks actually do.** Track where cash *must* go: central-bank balance sheets, TGA, reverse repo,
bank reserves, Treasury issuance/settlement, fund flows, buybacks, index rebalances, month-end/quarter-end
windows. The trade is often mechanical, not directional: "who needs to buy at 15:55 on quarter-end".

**The canonical composite.** Net liquidity = Fed assets − TGA − RRP. Its *change* has historically led
risk assets more reliably than its level; the 2023-24 pattern (balance-sheet shrinkage offset by RRP
drain and TGA drawdown) is the textbook example [2]. Stress hierarchy to watch, in order: EFFR−IORB > +8bp
on a non-quarter-end day → reserves scarce; SOFR−IORB > +10bp sustained → repo stress; SOFR > EFFR →
dealer balance sheet is the binding constraint; SRF take-up > $5bn → system at the ceiling [1].

**Encode as:** weekly deltas (not levels) of net liquidity, reserves, TGA, RRP; a repo-stress z-score;
an issuance calendar feature (heavy bill supply = liquidity drain); ETF flow z-scores.

**Free sources:** NY Fed SOFR/EFFR API `[OK]`, Treasury Fiscal Data API (auctions, cash balance) `[OK]`,
Treasury yield curve CSV `[OK]`, Fed H.4.1/H.8 pages `[OK as HTML/CSV]`, FRED `[DEAD]` → use Treasury and
NY Fed directly. RRP daily levels are published by the NY Fed under markets API (path works with the
right resource name; verify per call).

**How it fails:** net liquidity is a crude accounting identity; it has had long stretches of zero
correlation. Use it as a slow tide, not a timing tool.

---

## L5. STRESS AND CREDIT — the early-warning layer

**What desks actually do.** Credit leads equity at turning points: HY spreads widen before stocks crack,
CP and repo spreads flag funding stress, sovereign CDS flags country risk, the excess bond premium is the
pricing-of-risk part of credit spreads. Financial conditions indices (OFR FSI, Chicago Fed NFCI, Goldman
FCI) compress this into one number [1][3].

**Numbers.** OFR FSI is published with five sub-indices on a scale where 0 = historical average; the
2019 repo squeeze and March 2020 both registered in the funding and volatility legs *before* the equity
damage was complete. Our own table: OFR FSI > 1.5 bucket has a materially worse 21-day distribution
than the unconditional row (see `BASE_RATES.md`).

**Encode as:** level + 4-week change of a stress composite; credit-equity divergence (spreads widening
while stocks flat is the classic warning); funding z-score.

**Free sources:** OFR FSI CSV `[OK]` (5 sub-indices, daily, 2000→), Treasury yield curve `[OK]`,
NY Fed rates API `[OK]`, ECB/Credit via national sources. ICE BofA HY OAS via FRED `[DEAD]`.

---

## L6. VOLATILITY AND THE TAILS

**What desks actually do.** Trade the *price of risk*, not just direction: VIX vs realised (variance risk
premium), skew/SKEW (tail pricing), term structure (contango/backwardation = the market's own fear curve),
gamma positioning, dispersion, cross-asset vol ratios.

**Numbers from our data.** VIX ≥ 40 → median +30.4% over the next 12 months, 96% of observations positive;
VIX 20–25 is the worst bucket (median +6.3%, 56% positive) — the "complacent but not calm" zone. Buying
fear works *on average over a year* but the 21-day worst case in that bucket is −19.5%: the payoff is
asymmetric in time, so it needs a horizon and a size that can survive the interim. Our own H11 test showed
the reverse trade (short vol) has Sharpe +0.69 and a worst 12-month of −103.7%: not survivable.

**Encode as:** VRP = IV − subsequent RV (ex-ante: IV − EWMA RV), term-structure slope, skew, vol-of-vol,
realised-return asymmetry, and a "tail budget" in the sizing layer.

**Free sources:** CBOE VIX/SKEW history `[OK]`, VIX3M/VIX9D `[OK]`, Deribit crypto IV chain `[OK]`,
VIX futures COT `[OK]`. CBOE put/call CSVs `[DEAD, returns HTML with status 200]`.

---

## L7. CALENDAR AND CATALYSTS — when the market must re-price

**What desks actually do.** Pre-write scenarios for every scheduled event: CPI, NFP, PCE, ISM, FOMC,
ECB/BOJ, OPEC, quarterly refunding, index rebalances, option expiries (monthly/quarterly/0DTE), elections,
and known geopolitical dates. The edge is not the forecast, it is the *pre-committed response* to each
outcome — this is the single most repeatable professional habit [6][8].

**Numbers.** Realised vol clusters around scheduled releases; option-implied moves for event days are
systematically *above* realised (the event premium you pay for protection). Post-event drift is the
cleanest exploitable pattern when a surprise is large and the positioning was one-sided.

**Encode as:** an event table with `datetime, asset, consensus, prior, surprise_sigma, implied_move`;
features = days-to-event, event type, surprise z, and *post-event* drift windows. Our repo already has
205 FOMC decision dates (1994→2026) and a forward-collected calendar from 2026-11.

**Free sources:** Fed calendar pages `[OK]`, `ff_calendar_thisweek.json` `[OK, current week only]`,
BLS/BEA release schedules `[OK as pages]`, Nasdaq earnings calendar API `[OK]`.

---

## L8. FUNDAMENTALS — for anything with a balance sheet

**What desks actually do.** Rank on revisions, not levels: earnings-revision breadth, surprise history
(SUE), accruals, gross profitability, quality (low leverage, stable margins), valuation versus own
history, and — crucially — *what is already in the price*. Insider buying and buyback announcements are
the most informative single events.

**Numbers.** Post-earnings-announcement drift remains one of the most robust anomalies (decades of
out-of-sample evidence, strongest in small caps and after large surprises); revision momentum works at
1–3 month horizons and decays after. Value + quality beats either alone; value alone has had two
decade-scale drawdowns.

**Encode as:** point-in-time fundamentals (`data.sec.gov` XBRL company facts `[OK]`), revision breadth,
SUE = (actual − consensus)/σ, accruals, and a surprise×positioning interaction.

**Free sources:** SEC XBRL & submissions `[OK]`, Nasdaq short interest `[OK]`, EDGAR full-text search
`[OK]`. Consensus estimates are paid; the free proxy is realised-vs-prior-trend surprise.

---

## L9. THE REAL ECONOMY AND PHYSICAL SUPPLY (where non-price information lives)

**What desks actually do.** For commodities and for inflation, the physical layer beats the financial
layer: inventories, rig counts, refinery runs, shipping rates, port congestion, weather, crop conditions,
harvest progress, export inspections. This is the most defensible "special" data because it is
*measured*, not derived from prices.

**Numbers.** Weekly EIA crude stocks (Wednesday 10:30 ET) move crude more than most macro prints; USDA
WASDE (monthly) resets grain curves; Baltic Dry/Freightos indices lead global trade momentum by weeks.

**Encode as:** inventory surprise vs seasonal norm, days-of-cover, rig-count change, freight z-score,
weather anomalies. All are *forward-known* (schedules) and *non-price*.

**Free sources:** EIA xls/csv hist endpoints `[OK]` (crude stocks, Henry Hub, weekly), EIA v2 API
`[needs free key]`, weather.gov `[OK]`, USDA QuickStats `[needs free key]`, WASDE text `[moved; check
usda.gov/oce/commodity/wasde current path]`, Baltic `[paid]`.

---

## L10. NARRATIVE AND ATTENTION

**What desks actually do.** Measure the *attention* the market is paying, not the sentiment it claims:
search volumes, news counts, Wikipedia pageviews, social volume, and the tone of official communication
(central-bank language changes).

**Numbers from this repo.** Wikipedia pageviews improve next-day volatility forecasts on 6 of 8 assets
but do **not** improve portfolio Sharpe (0.64 → 0.63): attention predicts *activity*, not *direction*.
GDELT works again from this sandbox `[OK]` and gives article-volume timelines per query — a free,
global, per-topic attention series.

**Encode as:** attention z-score as a vol/size input, tone-shift on central-bank documents, and
narrative-crowding (share of articles about a theme) as a contrarian *timing* overlay at best.

**Free sources:** Wikimedia pageviews `[OK]`, GDELT DOC 2.0 `[OK today, 429-prone]`, Reddit `[DEAD 403]`,
Alternative.me Fear&Greed (crypto) `[OK]`, Hacker News Algolia `[OK]`.

---

## L11. TECHNICALS — structure, not prophecy

**What desks actually do.** Use price structure to *manage* a position: where the invalidation is, where
liquidity sits, where the stop cluster is, what the range is. Technicians who survive treat it as risk
geometry, not as forecasting [9].

**Numbers from this repo.** 7 classic rule families × 24 instruments, cost-charged and null-controlled:
**no family beats the permutation null** (best BOLL_FADE +0.04 mean Sharpe; SuperTrend −0.61). The famous
"30% CAGR" from the early version of our own code was a 1-bar look-ahead artefact (30% → 4% once lagged).

**Encode as:** support/resistance from volume profile and prior swing points, realised-vol bands, gap
statistics, and as *stop placement* rules. Never as a standalone alpha source without a null control.

---

## L12. EXECUTION AND COSTS — where most strategies actually die

**What desks actually do.** Measure, per instrument and per hour: spread, commission, slippage, market
impact, borrow, funding/swap, and the cost of crossing at the close. Then they refuse to trade anything
where the expected edge is not ≥2–3× round-turn cost.

**Numbers from this repo.** Measured ECN spreads: EURUSD 0.3 pips, EURSEK 48 pips — a 160× range within
"G10 FX". The XS mean-reversion study went from **Sharpe +2.10 (assumed cost) → +0.07 (ECN) → −0.08
(retail)**. Costs alone flipped the verdict. Any backtest output without measured cost is fiction.

**Encode as:** a cost table keyed by instrument × session, and a hard "edge must be ≥ 2× cost" gate.

**Free sources:** Dukascopy freeserv bid/ask `[OK]`, exchange fee schedules `[OK as pages]`,
our own measured file `data/spreads/MEASURED_COSTS.json`.

---

# P. PROBABILITY AND DECISION PRINCIPLES (the part most retail bots skip)

1. **Base rate first, story second.** Ask "what happens after states like this" before "why now". Our
   `base_rates.csv` exists for exactly this.
2. **Update, don't predict.** Bayes: posterior ∝ prior × likelihood. In practice: carry a *distribution*
   per asset, widen it on events, shrink it on evidence. A signal that changes the distribution slightly
   is worth more than a confident wrong forecast.
3. **Positioning sets the payoff shape, not the direction.** Same view, different crowding = different
   P&L distribution (§L3).
4. **Payoff asymmetry > hit rate.** A 40% win-rate with 3:1 payoff beats a 70% win-rate with 0.5:1.
   Martingale inverts this and always ends at −100% (5 of 5 in our test).
5. **Risk of ruin is the only hard constraint.** Kelly fraction assumes you know the edge; nobody does,
   so trade 1/4 to 1/2 Kelly, and cap by worst-case loss, not by expected value.
6. **Regime-conditional everything.** A rule that works in all regimes usually means you never checked.
7. **Pre-commit invalidation.** Decide the exit before entry; "being early" and "being wrong" are the
   same P&L until the invalidation holds.
8. **Count your trials.** 20 variants tested ⇒ the best one's p-value is not 0.05. Correct or hold out.
9. **The market pays for being right about the *next* repricing, not about the truth.** Timing is part
   of the thesis.
10. **Survive first.** Any strategy whose worst 12 months is −100% is not a strategy, it is a countdown
    (ours: short-vol Sharpe +0.69, worst 12m −103.7%).

# E. WHAT MAKES AN EDGE "SPECIAL" (not google-able)

An edge is special when at least one of these is true — this is the filter for anything new:
1. **The data is measured, not derived.** Physical inventories, actual bid/ask, actual positioning:
   nobody's blog can compute it for you.
2. **It is forward-known but under-watched.** Schedules, index rebalances, expiries, issuance calendars,
   weather, planting dates.
3. **It is a constraint, not a prediction.** Forced sellers/buyers (margin calls, rebalances, quarter-end,
   option hedging, redemption cycles) create mechanical flow.
4. **It is a second-order consequence.** Not "CPI hot" but "CPI hot ⇒ front-end repricing ⇒ 2s10s
   flattening ⇒ bank equities underperform".
5. **It is the interaction, not the indicator.** Positioning × catalyst × valuation. One indicator is a
   hobby; the interaction of three is a strategy.
6. **It survives cost, hold-out, and a null.** Otherwise it is not special, it is just unpublished.

---

## Sources cited above (practitioner/research, for the next AI to go deeper)
[1] Lighthouse Macro, "Plumbing: the invisible infrastructure" — repo/SOFR/TGA stress hierarchy.
[2] Macro Lighthouse, "Liquidity plumbing" — net liquidity = Fed assets − TGA − RRP.
[3] OFR Financial Stress Index documentation.
[4] Acadia, "What hedge funds actually need from data vendors" — per-strategy data needs.
[5] MRKT Edge, "Institutional macro for traders" — regime → catalyst → transmission → expression.
[6] MRKT Edge, "Macro trade ideas" — priced-in check, crowded-consensus checklist, COT timing.
[7] KenMacro, "Macro trading" — curve regime, calendar, asset map.
[8] Brunnermeier/Nagel/Pedersen (2008); Koijen/Moskowitz/Pedersen/Vrugt (2018) "Carry" — carry across 9
asset classes, Sharpe 0.5–0.9, negative skew in FX/commodities/credit.
[9] The ITPM trader, "How hedge fund traders find their best trades" — technicals last, for structure.
[10] Cboe/Deribit documentation for GEX and IV surfaces; SqueezeMetrics public methodology.
