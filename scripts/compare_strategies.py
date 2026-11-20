"""Compare documented strategy families on 27 years of official ECB reference rates.

Data: ECB Statistical Data Warehouse, daily, 1999-01-04 -> today (fix-to-fix reference rates).
Cross pairs are DERIVED from the three ECB series (documented, not invented):
    GBPUSD = EURUSD / EURGBP      GBPCHF = EURCHF / EURGBP      USDCHF = EURCHF / EURUSD

Rules compared (each is taken from published literature, not fitted here):
  TSMOM_12M   Moskowitz, Ooi & Pedersen (2012) "Time Series Momentum" — sign of 252d return,
              monthly rebalance.
  TSMOM_1M    same paper, 21d lookback, monthly rebalance.
  MA_50_200   classic long-horizon trend filter (Faber 2007 style), long/short, daily.
  MA_20_100   faster trend, long/short, daily.
  RANGE_FADE  the project's own H01 (z >= +2 vs MA50, 20d hold) — the control that failed.
  BUY_HOLD    always long (benchmark).
  RANDOM      random +/-1 position, same turnover rate as MA rules (benchmark).

Cost: 1.3 pips round trip, charged on every unit of position change
      (0.65 pip per side, converted to % of price at that date).
"""
import csv, os, json, datetime as dt
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data", "official")
REP = os.path.join(ROOT, "reports")
PIP = 0.0001
SPREAD_PIPS = 1.3
SPLIT = "2013-01-01"


def load_ecb():
    raw = {}
    for p in ("EURUSD", "EURGBP", "EURCHF"):
        rows = list(csv.DictReader(open(os.path.join(D, f"{p}_D.csv"))))
        raw[p] = {r["date"]: float(r["close"]) for r in rows}
    dates = sorted(set(raw["EURUSD"]) & set(raw["EURGBP"]) & set(raw["EURCHF"]))
    pairs = {p: np.array([raw[p][d] for d in dates]) for p in raw}
    pairs["GBPUSD"] = pairs["EURUSD"] / pairs["EURGBP"]
    pairs["GBPCHF"] = pairs["EURCHF"] / pairs["EURGBP"]
    pairs["USDCHF"] = pairs["EURCHF"] / pairs["EURUSD"]
    return dates, pairs


def sma(x, w):
    out = np.full(len(x), np.nan)
    c = np.cumsum(np.insert(x, 0, 0.0))
    out[w - 1:] = (c[w:] - c[:-w]) / w
    return out


def positions(rule, px):
    n = len(px)
    if rule.startswith("TSMOM"):
        w = 252 if rule.endswith("12M") else 21
        sig = np.zeros(n)
        for i in range(w, n):
            sig[i] = 1.0 if px[i] > px[i - w] else -1.0
        pos = np.zeros(n)
        last_month = None
        cur = 0.0
        for i, d in enumerate(dates_global):
            m = d[:7]
            if m != last_month:          # rebalance on the first trading day of the month
                cur = sig[i - 1] if i > 0 else 0.0
                last_month = m
            pos[i] = cur
        return pos
    if rule == "MA_50_200":
        f, s = sma(px, 50), sma(px, 200)
        return np.where(np.isnan(f - s), 0.0, np.where(f > s, 1.0, -1.0))
    if rule == "MA_20_100":
        f, s = sma(px, 20), sma(px, 100)
        return np.where(np.isnan(f - s), 0.0, np.where(f > s, 1.0, -1.0))
    if rule == "RANGE_FADE":
        ma = sma(px, 50)
        dev = px - ma
        sd = np.full(n, np.nan)
        for i in range(252, n):
            sd[i] = dev[i - 252:i].std(ddof=1)
        z = dev / sd
        pos = np.zeros(n)
        i = 260
        while i < n - 21:
            if not np.isnan(z[i]) and z[i] >= 2.0:
                pos[i + 1:i + 21] = -1.0
                i += 21
            else:
                i += 1
        return pos
    if rule == "BUY_HOLD":
        return np.ones(n)
    if rule == "RANDOM":
        rng = np.random.default_rng(101)
        p = rng.choice([-1.0, 1.0], size=n)
        return np.where(np.arange(n) < 200, 0.0, p)
    raise ValueError(rule)


def evaluate(px, pos, mask=None):
    ret = np.zeros(len(px))
    ret[1:] = px[1:] / px[:-1] - 1.0
    turn = np.zeros(len(px))
    turn[1:] = np.abs(np.diff(pos))
    cost = turn * (SPREAD_PIPS / 2) * PIP / px
    pnl = pos * ret - cost
    if mask is not None:
        pnl = pnl[mask]
    if len(pnl) < 50:
        return None
    eq = np.cumprod(1 + pnl)
    n = len(pnl)
    cagr = eq[-1] ** (252 / n) - 1
    vol = pnl.std(ddof=1) * np.sqrt(252)
    sharpe = pnl.mean() / pnl.std(ddof=1) * np.sqrt(252) if pnl.std(ddof=1) > 0 else 0
    dd = float(np.max(np.maximum.accumulate(eq) / eq - 1))
    return dict(cagr=round(float(cagr) * 100, 2), vol=round(float(vol) * 100, 2),
                sharpe=round(float(sharpe), 2), maxdd=round(dd * 100, 1),
                trades_per_yr=round(float(turn.sum() / 2 / (n / 252)), 1),
                hit=round(float((pnl != 0)[:].mean() * 100), 1),
                turnover_cost_pct=round(float(cost.sum() * 100), 2))


RULES = ["TSMOM_12M", "TSMOM_1M", "MA_50_200", "MA_20_100", "RANGE_FADE", "BUY_HOLD", "RANDOM"]

if __name__ == "__main__":
    dates_global, pairs = load_ecb()
    print(f"ECB dataset: {len(dates_global)} days, {dates_global[0]} -> {dates_global[-1]}, "
          f"{len(pairs)} pairs")
    pre = np.array([d < SPLIT for d in dates_global])
    post = ~pre
    results = {}
    for rule in RULES:
        per_pair = {}
        for p, px in pairs.items():
            pos = positions(rule, px)
            for label, m in (("full", None), ("pre2013", pre), ("post2013", post)):
                r = evaluate(px, pos, m)
                if r:
                    per_pair.setdefault(p, {})[label] = r
        # pooled: equal-weight average of pair returns
        pooled = {}
        for label, m in (("full", None), ("pre2013", pre), ("post2013", post)):
            pnls = []
            for p, px in pairs.items():
                pos = positions(rule, px)
                ret = np.zeros(len(px)); ret[1:] = px[1:] / px[:-1] - 1
                turn = np.zeros(len(px)); turn[1:] = np.abs(np.diff(pos))
                pnl = pos * ret - turn * (SPREAD_PIPS / 2) * PIP / px
                pnls.append(pnl[m] if m is not None else pnl)
            stacked = np.mean(pnls, axis=0)
            eq = np.cumprod(1 + stacked)
            pooled[label] = dict(cagr=round(float(eq[-1] ** (252 / len(stacked)) - 1) * 100, 2),
                                 sharpe=round(float(stacked.mean() / stacked.std(ddof=1) * np.sqrt(252)), 2),
                                 maxdd=round(float(np.max(np.maximum.accumulate(eq) / eq - 1)) * 100, 1))
        results[rule] = dict(per_pair=per_pair, pooled=pooled)
        print(f"{rule:11} pooled full: CAGR {pooled['full']['cagr']:>6}% "
              f"Sharpe {pooled['full']['sharpe']:>5} maxDD {pooled['full']['maxdd']:>6}% | "
              f"pre2013 Sharpe {pooled['pre2013']['sharpe']:>5} post2013 {pooled['post2013']['sharpe']:>5}")
    json.dump(results, open(os.path.join(REP, "strategy_comparison.json"), "w"), indent=2)
    print("wrote reports/strategy_comparison.json")
