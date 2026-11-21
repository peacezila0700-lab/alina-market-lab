# PITFALLS — the bugs that made this project see fake edges

Written because an AI inheriting this repo will make the same mistakes. Each item cost real time
and produced at least one false positive.

## 1. Look-ahead via unlagged positions (the big one)
`pnl[t] = pos[t] * ret[t]` where `ret[t] = close[t]/close[t-1]-1` means you trade at `close[t]`
using information that only exists at `close[t]`, then collect the move into `close[t]`.
Effect measured here: an EMA-cross screen showed **CAGR 30.0%, Sharpe 1.72, 22/24 instruments
profitable**. With `pos[t-1]` the same code gave CAGR 4.0%, 10/24 profitable. The rule is:

```
ret[t]      = close[t]/close[t-1] - 1
pos[t]      = f(info up to and including close[t])
pnl[t]      = pos[t-1] * ret[t] - cost * |pos[t-1] - pos[t-2]|
```

A position that flips at the close can only earn the *next* bar.

## 2. Diagnosing look-ahead incorrectly
A cheap detector: if a 1-bar lag barely changes the result, the look-ahead was not the problem.
Here, lagging changed CAGR from 30% to 4% — ratio > 5x is a strong tell.

## 3. Wrong cost assumption (verdict-flipping)
- Assumed 1.3 pip round-turn on all FX. Reality (measured, ECN): EURUSD 0.3 pips, EURSEK **48 pips**.
- Consequence: XS mean-reversion on G10 looked like a **Sharpe 1.38, +22.5%** opportunity at the
  assumed cost; at retail costs it was **−0.08 Sharpe**; at ECN costs it was **+0.07, ~breakeven**.
- Lesson: cost is not a constant, it is a per-instrument, per-hour measurement. Always run the
  verdict at *two* cost levels (ECN and retail) and report both.

## 4. Zero-crossing equity curves corrupt metrics
When an equal-weight basket's equity crosses zero, `cagr` and `maxdd` become `nan` or absurd
(>100%, or 1e6 %). Always clip/mark `RUINED` instead of reporting the ratio.

## 5. Month-end bucketing
Grouping by `year-month` looks fine until the last group has 3 days: the compounded monthly return
is then not comparable. Check `len(months)` vs the date span before trusting an equity curve.

## 6. Reusing a tested sample as a "new" test
EXP-0006 re-scored EXP-0005 with better costs. That is a cost-model correction, **not** independent
confirmation. Hold-out data must be genuinely unseen (EXP-0007 used 2016–2021 held out and the
prior in-sample result failed: +0.413 → +0.126 Sharpe).

## 7. Survivorship / listing bias in the free-EA and ETF universes
The 332 free EAs are what is *listed today*; dead products were delisted. Do not compute
"average EA performance" from that list. Same for ETFs: `VIXY` exists, `VXX` on Yahoo only from 2018.

## 8. COT date confusion
`report_date` = Tuesday as-of. Public release = Friday 15:30 ET. Using Tuesday in a daily backtest
gives 3 extra days of hindsight per week — it looks great and is 100% fake.

## 9. Martingale looks brilliant until it doesn't
A grid/martingale (fade 1 ATR, double, 6 levels, TP 0.5 ATR) produced **positive equity curves for
months** and a 97%+ win rate. Final equity: EURUSD 0.825, SP500 0.938, GOLD 0.938, BTC 0.976,
NIKKEI 0.951 — **5 of 5 wiped**. If a strategy's win rate is >90%, you are long tail risk.

## 10. "Statistical significance" from many trials
168 screen tests × 14 metrics = thousands of numbers. At 5% you expect ~8 false positives. This
project's rule: report how many of N instruments beat the null vs how many were expected by chance
(6 of 144 observed vs 7.2 expected = nothing found).

## 11. A permutation null that changes turnover proves nothing
First version of EXP-0012 (68-ETF cross-section) shuffled the asset labels **every week**. That makes
the null portfolio reshuffle constantly, so it pays enormous costs and posts Sharpe ≈ −1.0 while the
real strategy holds persistent positions and posts ≈ +0.06. The "edge" was pure turnover, not
information: every factor looked like a pass.
**Fix:** hold ONE fixed label permutation for the whole sample. Then the null portfolio has the same
holding persistence (same turnover) as the real strategy, and only the signal→asset link is destroyed.
With the turnover-matched null, none of the three factors beat their p95 — the honest result.

## 12. Boolean-mask assignment does not mutate numpy arrays
`row[mask]` returns a COPY. `rng.shuffle(row[mask])` shuffles the copy and silently changes nothing,
so every "permutation" equals the original and the null has zero dispersion. Use
`idx = np.where(mask)[0]; arr[idx] = arr[rng.permutation(idx)]`. This bug hid for two runs and made a
null look impossibly tight.

## 13. A timing overlay will beat a shift-null for free — compare it to vol targeting
EXP-0013 shifted each exposure series circularly to build the null. Shifting preserves the *fraction*
of days at each weight but destroys the alignment with the market's volatility cycle. Any rule that is
heavier in calm periods and lighter in volatile periods then looks spectacular (the GEX overlay hit the
100th percentile of 200 shifts in-sample). But volatility targeting, built with no market information at
all, gets almost the same Sharpe (EXP-0014: 0.70 vs 0.77 IS; 0.63 vs 0.67 OOS; the gamma increment's
percentile is 88.5 in-sample and 74 out-of-sample — inside the null).
**Rule:** any test of an exposure/sizing signal must include a *vol-targeting* arm with matched average
exposure (w = target/realised_vol, look-ahead-free, clipped) as the benchmark, and the statistic must be
Sharpe(signal) − Sharpe(voltarget). Beating buy-and-hold is not evidence; beating vol targeting might be.

## 14. Sizing overlays change volatility, not expected return — decide which one you are testing
Across EXP-0013 the six "market state" overlays moved Sharpe only through the second moment. Max
drawdown improved (gamma −28.5% vs buy-and-hold) while CAGR barely moved. If a study's claim is
"better risk-adjusted return", check whether the *mean* return per unit exposure changed at all; if not,
the finding is a risk-management result and belongs in the sizing layer, not in the signal layer.

## 15. Same-bar weights and coincident labels: the day EXP-0015 printed Sharpe 1.98
The first run of the onset test read: in-sample Sharpe 1.983, out-of-sample 2.276, both at the 100th
percentile of the null. Three bugs had to be fixed before the honest answer appeared:
1. **Weights were applied to the same bar as the features.** The feature set ended with the day-t
   realised-vol percentile and VIX, and the weight w_t was multiplied by return_t. Set weights at the
   close, earn the *next* day: `w = w.shift(1)`. This alone is worth ~1.5 Sharpe of imaginary edge.
2. **The label was coincident, not forward.** `ON1 = VIX>30 and prior VIX<=28` shares the same close
   as the features, so AUC 0.924 measured autocorrelation, not forecasting. The label must be "an
   onset occurs within the next H days" (`fwd()` using a reversed rolling max shifted by -1).
3. **The null only covered the arm, not the mechanism.** Even with a valid label, a variance-based
   overlay must be compared to vol targeting (PITFALLS #13), which is what finally killed it.
After the fixes: AUC 0.665/0.746, and Δ vs vol targeting −0.278 out-of-sample → FAIL.
**Checklist before every timer run:** (a) every weight enters with a lag, (b) every label is measured
strictly after the decision, (c) the benchmark arm is a mechanism-free equivalent, (d) the null keeps
the strategy's turnover. Four checks, four fake edges prevented in this repo alone.

## 16. A mean-reverting *price* into a *level* problem: the recovered Sharpe pattern
In EXP-0015/0016 the honest results share a shape: the state variable forecasts volatility
(AUC 0.67–0.75) or cuts drawdown (bond carry halves the 2022–26 loss) but does not raise the mean
return per unit of exposure. That is not a failed project, it is a taxonomy: **variance is
forecastable, direction is not.** Every future idea should say up front which of the two it claims,
because they need completely different evidence (Brier/AUC for variance; excess Sharpe vs vol
targeting and a turnover-matched null for direction).

## 17. Always-on intraday rules pay the spread 24 times a day — measure per bar, not on average
EXP-0017 measured a *positive* gross edge in 1-hour FX reversal (+0.188 bp/hour) and still lost 7.8
Sharpe net, because an always-on rule round-trips every hour and the spread alone costs 0.342 bp/hour.
Two rules follow:
1. **Charge cost on |Δposition| for every bar, using that bar's own measured spread** — never a single
   average spread, because the rollover hours (21-23 UTC) quote several times wider than the London
   session and any rule that trades through them is charged more than the average implies.
2. **Report the breakeven cost multiple** = gross mean return / cost drag. If it is below 1, the idea
   needs cheaper execution, not a better filter; EXP-0018's gated variants came in at 0.03-0.29 while
   still looking "less bad", which is exactly how a dead idea keeps a researcher busy for months.

## 18. `.git/config` is not persisted — the remote and the identity disappear between sessions
The workspace snapshot deliberately excludes `.git/config`, `.git-credentials` and `.netrc`. The first
symptom is `fatal: empty ident name` on commit, the second is `git remote -v` returning nothing, so a
`git push` looks like it worked while pushing to a URL that no longer exists.
**Always do this first in a new session:**
```
bash scripts/gh_push.sh --check        # reattaches origin from ~/.alina/git_token
git -c user.name="ALINA Agent" -c user.email="alina.lab.contact@gmail.com" commit -m "..."
bash scripts/gh_push.sh
```
Then verify with `git fetch <url> main && git log --oneline -1 FETCH_HEAD`.

## 19. The local git history silently diverges from the remote — check before you push
Three sessions in a row, `git push` was rejected with "fetch first" while the local log *looked* fine.
The cause: the sandbox snapshot restores the working tree and most of `.git`, but not `.git/config`, and a
newer base commit from the remote was never fetched — so local commits were being stacked on an older
history and every push was a non-fast-forward.
**Procedure that always works (and never loses the work):**
```
URL=https://x-access-token:$(cat ~/.alina/git_token)@github.com/<org>/<repo>.git
git fetch -q $URL main
git merge-base --is-ancestor FETCH_HEAD HEAD && echo "fast-forward ok" || echo "DIVERGED"
# if diverged, keep the WORKING TREE (it is the source of truth) and re-commit on top of the remote:
git branch -f backup-$(date +%H%M) HEAD
git reset --soft FETCH_HEAD
git -c user.name="…" -c user.email="…" commit -m "…"     # diff vs the real remote base
git push $URL HEAD:main
git fetch -q $URL main && git log --oneline -1 FETCH_HEAD # verify
```
Never `git pull` into this repo: the working tree carries gigabytes of regenerated data and a merge will
produce conflicts in every CSV. `reset --soft` + one fresh commit is the safe path.
