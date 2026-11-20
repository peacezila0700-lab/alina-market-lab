# OPERATING MANUAL — how to run this every day (for the owner and his local AI)

This is the part that turns the pack from a dataset into a system. Read it once; then it is three
commands a day.

## 1. What runs, in order, and why

```
scripts/collect_daily.py      # ① pull everything free, append to history (idempotent, ~2-3 min)
  ├─ fetch_news.py            #    headlines from 15 outlets + entity tags + daily counts
  ├─ build_levels.py          #    support/resistance, pivots, profiles, ATR for 28 instruments
  ├─ build_event_db.py        #    re-build the event calendar (FOMC, auctions, OPEX, NFP rule, shocks)
  └─ daily_brief.py           #    compress EVERYTHING into briefs/latest.{json,md}
scripts/build_datapack.py     # ② (weekly) rebuild ALINA_DATAPACK_*.zip for Drive
```

Only step ①② matter for daily use. Step ② weekly is enough.

**Cron (one line, on any Linux box or a $5 VPS):**
```
15 22 * * * cd /path/to/alina_lab && python3 scripts/collect_daily.py >> data/collect/cron.log 2>&1
30 22 * * 0 cd /path/to/alina_lab && python3 scripts/build_datapack.py >> data/collect/cron.log 2>&1
```
22:15 UTC = after the US close, before the Asian open — the moment when the most data has settled.

## 2. What the local AI should be fed, and in what order

| Priority | File | Size | Why |
|---|---|---|---|
| 1 | `briefs/latest.md` | ~6 KB (~1.5k tokens) | The whole day in one read: state, events, odds, levels, headlines, flags, scenario branches |
| 2 | `knowledge/README_FOR_AI.md` | ~4 KB | The rules that prevent it from re-creating known failures |
| 3 | `knowledge/PITFALLS.md` | ~6 KB | The 12 traps, including two found today |
| 4 | `results/experiments.jsonl` | ~10 KB | What is already dead, so it does not re-test it |
| 5 | `catalog.json` | ~40 KB | Only when it needs a dataset it has not loaded before |
| — | any CSV | 10 KB–40 MB | Load on demand, never wholesale |

**Do not feed the whole pack into a context window.** Read `latest.md`, then open one or two datasets
by id from `catalog.json`. The catalog carries row counts, coverage, caveats and a 2-row preview
precisely so the model can decide *without* loading the file.

## 3. The daily loop the model should follow

1. Read `briefs/latest.md`.
2. Note the flags (VIX ≥ 30, negative gamma, stress, events inside 7 days).
3. For each instrument it may trade, pull its row from `data/levels/levels_latest.csv` and place the
   invalidation beyond a *measured* level (prior day low, pivot, value-area edge), not a round number.
4. Look up the base rate for the current state in `briefs/latest.json → base_rates`. If the median
   forward return is not clearly different from unconditional and `n_effective` is small, do nothing.
5. Write down which scenario branch it took (from `scenarios`) **before** the outcome is known.
6. Log the decision; next day compare against the branch's measured odds.

## 4. What is already known to fail (do not rebuild)

| Idea | Result |
|---|---|
| 7 classic technical families on 24 instruments | 6/144 beat a permutation null = chance |
| Martingale/grid | 5 of 5 instruments wiped |
| COT positioning percentile (single + pooled panel) | panel t = 0.16, R² = 0.000 → closed |
| Event-conditional direction (OPEX/FOMC/month-end/VIX-onset) | interaction flips sign OOS → closed |
| Treasury auction demand → bonds/equities | fails pre-declared bar → closed |
| 12-1 momentum, 1M reversal, 5D reversal on 68 ETFs | none beats the turnover-matched null |
| Variance risk premium (short vol) | Sharpe +0.69, worst 12m −103.7% |
| Attention (Wikipedia) as direction | improves vol forecasts, not returns |

## 5. What is still open, in priority order

1. **Breadth/regime measures** (share of ETFs above their 200-day average, credit-vs-equity
   divergence, DIX/GEX regime) used as *sizing* inputs rather than direction — untested here.
2. **Event reaction asymmetry**: the event DB shows variance effects (FOMC 1.09×, NFP 1.33× on bonds)
   but no sign effect; the next honest test is an *options* expression (straddle-like), which needs a
   chain source we do not have yet.
3. **Cross-asset carry book** (FX carry from official rates + crypto funding): documented Sharpe 0.5–0.9
   in the literature across nine asset classes, and our components are already collected.
4. **Intraday FX** with measured hourly bid/ask (Dukascopy route), one-bar decision latency. The cost
   ceiling says FX only, not crypto (0.26 bp vs 20 bp).

## 6. Non-negotiables (they are the reason this project has zero fake edges)

- Lag every position one bar; charge measured costs on every turn.
- Every result needs a null that preserves turnover, a date split, and a written prior.
- Count the trials. 12 experiments and ~500 sub-tests have produced 0 validated edges — that is a
  *clean* book, not a failed one. Keep it clean.
