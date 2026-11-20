# ALINA MARKET LAB — PROJECT STATUS

**Date:** 2026-11-20 (UTC) · **Repo:** `peacezila0700-lab/alina-market-lab` (private, 14 commits)
**Phase:** research-only · **Money at risk: ZERO** · **Live trading: never enabled**

---

## 1. Gate dashboard

| gate | question | outcome | evidence |
|---|---|---|---|
| **0** Workspace audit | what can the agent actually do? | **PASS** | Drive write+read+delete tested on a real file; GitHub push verified; Python + network verified |
| **1** Foundation | can a fresh session resume itself? | **PASS** | `memory/*.md` + `docs/DECISION_LOG.md` (D01–D07) |
| **2** Market feasibility | is EURGBP D1/H1 viable on data? | **PASS with caveats** | 26y daily; spread measured 0.9 pip; **no broker-grade feed yet** |
| **3** Data pipeline & QC | is the data trustworthy? | **PASS after repairs** | 4,186 logged repairs; QC PASS on 5 datasets; `MANIFEST*.json` with sha256 |
| **4** Descriptive research | is the range behaviour real? | **PASS** | Hurst 0.358, VR60 0.516, 66% of days within ±2% of MA200 |
| **5** Hypotheses | are they falsifiable? | **PASS** | H01–H04 pre-registered before testing |
| **6** Baseline | does a rule run reproducibly? | **PASS** | `scripts/backtest_engine.py`, 13/13 unit tests |
| **7** Validation | is there an edge? | **FAILED — honest** | EXP-0001 + EXP-0002 → **H01 rejected** |
| 8+ | ML / news / paper / execution | **NOT STARTED** | correctly, nothing earned the right to proceed |

---

## 2. What is proven (with numbers)

1. **The range behaviour of EURGBP is real.** Hurst 0.358 vs EURUSD 0.500; variance ratio
   0.882 / 0.736 / 0.516 at 5 / 20 / 60 days; 65.7% of days within ±2% of the 200-day MA
   vs 41.0% for EURUSD. 26 years of data.
2. **Costs were never the killer.** Round-trip 1.3 pips against a 45.9-pip median daily range.
3. **The D1 z-score rule does not monetise it.** EXP-0002, 94 clean trades over 26 years ×
   5 pairs: +5.81 pips/trade, profit factor 1.06, CI [−52.55, +67.66], 2/5 pairs positive,
   indistinguishable from random entries (random mean +2.79, p95 +43.8).
4. **The effect flips sign across eras** (EURGBP −15.3 → +61.6 pips; CADCHF −50.9 → +76.3).
   That is the signature of noise, not mechanism.
5. **The infrastructure is trustworthy.** Next-bar fills, no look-ahead (tested by truncation),
   costs applied once, ledger reconciles, every repair logged and every dataset hashed.

## 3. What is rejected

- H01 (short EURGBP at z ≥ +2σ with MA-cross / time-stop exits) — **rejected**, not to be retuned.
- H02 (asymmetry) and H04 (horizon sweep) — deprioritised: they share the dead entry set.
- H03 (volatility filter) — filtering a non-existent edge cannot create one.

## 4. The finding that changes the design (new, 2026-11-20)

`reports/FEASIBILITY_MATH.md`:

| hold | spread+slip | swap @0.8 pip/night | total |
|---|---|---|---|
| 1 day | 1.3 | 0.8 | 2.1 |
| 20 days | 1.3 | 16.0 | **17.3** |

At a 20-day hold, **financing can be 12× the spread.** Break-even win rate on 20/20 targets
jumps from **53.2%** (no swap) to **72.0%** (15-day hold at 0.5 pip/night).
⇒ If this project continues, it should move to **shorter holds**, not longer — the opposite of
the direction implied by the 13.7-day half-life. This must be decided with the owner's real
broker numbers, not a placeholder.

## 5. Blocked (what I cannot do alone)

| blocker | why it matters | what unblocks it |
|---|---|---|
| **Broker spread + swap** | decides whether any rule can be profitable at all | owner: broker name + account type, or MT5 export |
| **Broker-grade price feed** | Yahoo has open==close in ~39% of bars → fill modelling is not credible | owner: MT5 History Center export (free, 5 min) |
| **Intraday data** | the only untouched sample left for a new test | same export (H1 or M15) |
| Dukascopy bulk feed | free 20y tick source, but HTTP 429 + TLS resets from this sandbox | retry later; not owner-dependent |

## 6. Ready to run the moment a file arrives

`scripts/validate_mt5_export.py` was built and self-tested against an MT5-format sample.
It parses tab/`<DATE><TIME>…<SPREAD>` exports, detects the broker's server-time format,
and reports spread by point/pip, gaps, duplicates and weekend bars.

**How to export (2 minutes, free):**
1. MT5 → **Tools → History Center** → symbol `EURGBP` → period **H1** (and `M15` if you want both)
2. Right-click the symbol in Market Watch → **Bars/History** → or in History Center select the
   range → **Export** → CSV
3. Save the file, upload it here (or drop it into the project's `data/inbox/`)
4. I run QC, re-derive the cost model, and the next experiment becomes measurable instead of guessed

## 7. What I recommend now (and why)

**Stop searching for an edge on Yahoo D1 data.** Two honest tests were run and both said no;
a third on the same data would only manufacture a prettier lie.

**Do this instead, in order:**
1. Get the MT5 export (owner, 2 minutes) → real spread + real fills + untouched intraday sample
2. Re-derive the cost model from that file, including swap per night
3. Then, and only then, pre-register one new hypothesis for **intraday mean reversion with short
   holds**, where 3–5 pip targets are not automatically eaten by financing
4. Never retune H01. The credibility of every future "yes" depends on this "no" staying honest.

## 8. Artifact index

```
memory/        MASTER_CONTEXT · CURRENT_STATE · MASTER_TASKS · SESSION_HANDOFF
docs/          STAGE0_AUDIT · PLAN_v1 · DECISION_LOG (D01–D07) · INCIDENT_LOG (QR-001)
               HYPOTHESIS_NOTES · RESEARCH (plan)
reports/       QC_D1 · RESEARCH_D1 · EXP_0001 · EXP_0002 · FEASIBILITY_MATH · PROJECT_STATUS
research/      HYPOTHESIS_REGISTER.csv · EXPERIMENT_LOG.csv · artifacts/EXP-000{1,2}_*
scripts/       fetch_yahoo_d1 · fetch_yahoo_full · build_canonical_d1 · qc_d1 ·
               descriptive_d1 · ingest_duka · backtest_engine · exp_0002_basket ·
               breakeven · validate_mt5_export
tests/         test_backtest_engine.py (13 tests, all passing)
```
