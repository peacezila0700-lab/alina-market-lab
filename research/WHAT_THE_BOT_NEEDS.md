# WHAT THE BOT STILL NEEDS — gap analysis + ranked plan

Written 2026-11-20, after the decision-inputs research (`DECISION_INPUTS_ATLAS.md`) and the new data
harvest (`data/alt/`, `data/facts/`). This is the "so what do we actually build" document.

## 0. Where we are

| Have | Count / coverage | Grade |
|---|---|---|
| Price data | 24 instruments (Yahoo) + 10 official FX (ECB, 1999→) | A/C |
| Positioning | COT 24 contracts 1986→2026 (35,936 wks), DIX/GEX 2011→ (3,913 d), OKX funding/LSR | A |
| Volatility/tails | VIX 1990→, SKEW 1990→, Deribit BTC IV chain (snapshot) | A |
| Stress | OFR FSI daily 2000→ (5 sub-indices) | A |
| Policy risk | EPU monthly 1900→, GPR monthly 1900→ | A |
| Physical supply | EIA weekly crude stocks 1982→, Henry Hub 1997→ | A |
| Costs | measured bid/ask, 10 FX pairs, hourly, 2003→2025 | B |
| Calendar | FOMC 205 dates, forward-collected econ calendar | A/C |
| Attention | Wikimedia pageviews 8 assets, 2016→, GDELT | A |
| Base rates | 96 conditional forward-return rows from our own data | B |
| Verdicts | 8 experiments + 320 sub-tests, 0 validated edges | B |

**The honest read: we have more data than most retail bots, and still no edge.** That is the correct
diagnosis, and it means the next work is not "more data" in general — it is data that is *different in
kind* from price, plus a decision layer that knows what to do with disagreement.

## 1. The seven real gaps

1. **No "what is priced" layer.** We have prices and positions, but nothing that computes the market's
   implied expectation (policy path, implied vol vs realised, futures basis, breakevens) and compares it
   with a model estimate. Without this, every signal is a direction bet with no reference point.
2. **No event-reaction database.** We have a calendar (205 FOMC dates) but not the *reaction statistics*:
   what SPX/FX did in the 1/5/20 days after a surprise of size X in event type Y. That is the most
   repeatable professional process (pre-written scenarios), and it is cheap to build.
3. **No options-flow history.** Put/call is dead on Cboe; DIX/GEX is index-level only; we have a single
   Deribit snapshot. Equity-level gamma/wall analysis exists but needs a chain source (options: Cboe
   delayed quotes blocked here, Yahoo needs a crumb token — solvable, untested).
4. **No cross-asset regime state.** We have the inputs (curve, dollar, vol, credit, positioning) but no
   single regime object every strategy can condition on.
5. **No execution/risk integration in the loop.** EA exists, lint-passed, never compiled; the governor
   logic is unit-tested (21/21) but not wired to live data.
6. **No "portfolio of ideas" layer.** Everything is tested one-idea-at-a-time. A real system needs a
   book: several weak-but-uncorrelated signals, sized by risk contribution, with a hard ruin constraint.
7. **No continuous collection.** Half our new data is a snapshot; only value comes from *accumulating*
   (funding rates, option chains, calendar, inventories). A collector that runs daily is worth more than
   any single dataset.

## 2. Proposed architecture (6 layers, each independently testable)

```
L0  COLLECT   scheduled pullers → raw store → manifest/checksums     (runs daily, cheap)
L1  NORMALISE point-in-time alignment, leak-safe lag columns, units  (already partly done)
L2  FEATURES  regime / priced-in / positioning / stress / supply      (build from L1)
L3  SIGNALS   pre-registered families, each with null + hold-out      (the science)
L4  BOOK      combine signals by risk contribution, ruin constraint   (the engineering)
L5  GOVERNOR  daily loss cap, permanent DD latch, spread gate, size   (already written for MT5)
```
Key discipline: **a signal only enters L3 with a written prior, a null control, and a date split.**
Everything else stays in the sandbox.

## 3. Ranked backlog (prior = my honest probability that this produces something usable)

| # | Item | Why it matters | Prior | Cost | Status |
|---|---|---|---|---|---|
| B1 | **Event-reaction database** (surprise → 1/5/20d returns, per asset class) | The one process every desk runs daily; we have the calendar, need reaction stats | 45% | 1 session | not started |
| B2 | **Priced-in layer** (implied path vs realised, VRP, basis, breakeven proxy) | Turns direction bets into mispricing bets | 40% | 1–2 sessions | partially (VIX only) |
| B3 | **Daily collector** (funding, option chain, inventories, calendar, DIX/GEX, FSI) | Compounding dataset nobody else has; snapshot → history | 40% | 1 session + cron | not started (single-shot fetch works) |
| B4 | **Pooled COT panel test** (24 contracts, FE, clustered SE, 70/30 split) | Only path to making the positioning-momentum hint real | 30% | 1 session | data ready, test not started |
| B5 | **Regime state object** (growth/inflation/liquidity/stress → 4 continuous scores) | Everything else conditions on it | 30% | 1 session | inputs ready |
| B6 | **Equity options chain** (OI by strike → walls, pinning, 0DTE) | Gamma/pinning is the most-watched intraday mechanic | 25% | 1–2 sessions | blocked: need crumb/chain route |
| B7 | **Cross-asset carry book** (FX carry + crypto funding + futures basis) | Sharpe 0.5–0.9 documented across 9 asset classes; crash risk manageable | 25% | 2 sessions | components ready |
| B8 | **Fundamentals/revisions** (SEC XBRL, SUE, insider Form-4) | Works only for single names; not needed for FX/futures | 20% | 2 sessions | not started |
| B9 | **Text/tone layer** (CB statements, GDELT volume, EPU) | Attention predicts vol, not direction — use for sizing | 15% | 1–2 sessions | data ready |
| B10 | **Live EA wiring** (MT5, paper mode first) | Only matters after L3 produces something | 10% | 1 session | EA written, never compiled |

## 4. What I would do in the next three moves (recommendation)

1. **B1 event-reaction database.** Highest prior, cheapest, and it upgrades every future test: instead of
   "does rule X work", you ask "does rule X work *around events*", which is where the data actually has
   structure. Needs only the calendar we already have plus price history.
2. **B3 daily collector.** Everything we harvested today becomes 10× more valuable in 6 months of daily
   accumulation. Cheap to write, zero marginal cost, and it is genuinely not something you can Google.
3. **B4 pooled COT panel.** The only hypothesis currently alive in this project. Either kill it properly
   or keep it — right now it is Schrödinger's edge.

## 5. What I need from the owner (decisions, not opinions)

- **Universe:** keep the 24-instrument multi-asset panel, or narrow to the 3–5 instruments with the best
  measured liquidity and deepest data? Breadth gives statistical power; narrowness gives realistic costs.
- **Horizon:** are we building something that holds for days-weeks (positioning/macro/event) or
  minutes-hours (intraday, needs tick data and latency we cannot get for free)? They are different bots.
- **Hold-out budget:** I keep burning sample. Suggest: freeze 2025-01-01 → 2026-11-20 as the final
  hold-out and never touch it until a candidate exists.

## 6. Standing truth to keep in the README of anything we ship

168 screen tests + 144 family tests + 8 experiments + 59 COT tests = **0 validated edges**. Data breadth is
not an edge; discipline (costs, hold-out, nulls, pre-registration) is what turns data into one.
