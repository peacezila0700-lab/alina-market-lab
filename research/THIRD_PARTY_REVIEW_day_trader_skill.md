# THIRD-PARTY REVIEW — `day-trader-skill` (Jake Schincariol, MIT)

Reviewed 2026-11-21 from the source, not from the article (`devkub.net/articles/day-trader-skill-claude-code`).
Repo: `github.com/Jakeschincariol/day-trader-skill` — 11 Claude Code skills + Python scripts, MIT licence,
no API keys, ~4.6k lines of code, with a real test suite (`tests/`, 66 tests, fixtures recorded offline).

**Verdict: keep two things, ignore six, and do not treat any of it as evidence.** The engineering craft is
good — completed-bar logic, offline replay fixtures, explicit clock handling in New York time — but the
project deliberately ships *plumbing without statistics*, and one component (Time Machine) produces a
number that will mislead exactly the user it is aimed at.

## What the 11 skills actually do

| Skill | What it does | Keep? |
|---|---|---|
| `trader-scanner` | Downloads the Nasdaq Trader symbol directory, then Yahoo 5-min "spark" quotes in batches, and finds **opening-range breakouts**: range = first N minutes, signal = a *completed* bar closing above the range high | **logic yes** (see below), as a definition to reuse |
| `trader-entry` / `trader-exit` | Bar-by-bar entry timing, stop/target placement, 1R framing | concepts yes, no new information |
| `trader-budget` / `trader-risk` | Position sizing from account and max loss; a config file of limits with a PASS/BLOCK gate | **concept yes** — we already have `scripts/governor.py` (21/21 tests) doing the same job |
| `trader-broker` | Writes a bracket order; paper by default, requires typed `yes` | no — we have no broker and will not add one |
| `trader-timemachine` | 10,000 block-bootstrap replays of a 5-minute intraday path, plus "the same setup on past days" | **no — see the flaw below** |
| `trader-news` | Yahoo RSS + SEC 8-K for watchlist names | no — our `fetch_news.py` + `fetch_news_world.py` cover 425 outlets |
| `trader-analyst` | SEC companyfacts → what changed in the report | no — our XBRL layer is the same route with 60 companies already parsed |
| `trader-alerts` | Price/stop/target/close alerts | no |
| `trader-pelosi` | Parses House Clerk **PTR PDFs** into congressional trades | **data yes** — ported (see below) |

## The flaw worth naming: the Time Machine has no costs

`timemachine.py` re-samples 5-minute bars into 10,000 synthetic sessions and reports the distribution of
outcomes for a given entry/stop/target. There is **no commission, no spread, no slippage, no borrow cost**
anywhere in the simulation (grep for `commission|slippage|spread` returns nothing). For a day-trading
tool this is not a detail, it is the entire result:

* US equity round-trip all-in cost is roughly 0.02–0.15% of notional for a liquid name at retail, and an
  ORB strategy trades 1–3 times a day. Over a 1R risk of 0.5–1.0%, a 0.05% cost is 5–10% of the risk
  budget per trade — enough to move a break-even hit-rate from 50% to ~55%.
* This repo already measured the same wall twice: hourly FX gross edge +0.19 bp/hour died to a 0.34 bp
  spread (EXP-0017), and any hourly rule that trades every bar pays the spread 24 times a day
  (`PITFALLS.md` #17).

**So: a Time Machine distribution is a GROSS distribution.** Quoting it next to a real account is the
single most expensive mistake a beginner can make with this toolkit. If you use it, subtract cost ×
expected trades from every replay first.

## The other structural limits (not bugs — scope)
1. **US equities only**, and intraday history is capped by Yahoo at 60 days of 5-minute bars, so the
   "replay past days" half of the Time Machine has a 60-day memory.
2. **No point-in-time discipline**: the scanner's universe is today's symbol directory, so every replay is
   survivorship-biased by construction.
3. **It generates setups, never tests them.** Nothing in the repo computes a hit rate against a null, and
   there is no date-split validation. That is a philosophical difference from this project, not a defect.
4. **The 45-day disclosure lag** on PTRs is acknowledged in its own docs (good) — the trades are history,
   never a live signal.

## What I actually ported into this workspace

| From the review | What exists now |
|---|---|
| House Clerk PTR route | `scripts/fetch_congress_trades.py` → `data/congress/ptrs_index.csv` (every PTR filing 2019-2026) + `data/congress/congress_trades.csv` (parsed transactions with amount ranges, filing dates, asset type codes). Endpoint and PDF text extraction verified; the community S3 mirrors are dead (403), so the official PDFs are the only route |
| The ORB definition | recorded here as the canonical rule: range = first 15 minutes of the regular session; signal = first *completed* 5-minute bar whose **close** is above the range high; no intrabar triggers. Any future intraday equity test must use this definition, not a variant invented on the spot |
| The risk-gate idea | already covered by `scripts/governor.py` + `scripts/lint_mq5.py`; nothing to add |
| Clock discipline (NY time, DST, half-days) | adopted into the notes for any future intraday study: the exchange clock, not UTC, defines bars |

## What this review changes about our own work
Nothing about the strategy conclusions. It does confirm two habits worth keeping: **completed-bar
signals** (their scanner does this properly) and **offline replay fixtures** (their tests run without the
network — ours do not, which is a genuine weakness in our collector-heavy design).
