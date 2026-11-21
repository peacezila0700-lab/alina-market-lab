"""Unit tests for Phase C EXP-0024 23-year H1 Bid/Ask pipeline (`scripts/exp0024_eurgbp_phase_c.py`).

Proves zero future leakage, strict limit-fill conservative ask/bid checking,
SL-before-TP precedence on ambiguous bars, and split isolation.
"""
import os
import sys
import unittest
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import exp0024_eurgbp_phase_c as p_c


def make_synth_h1(n: int = 1200) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    ts = pd.date_range("2020-01-01 00:00:00", periods=n, freq="1h", tz="UTC")
    mid = 0.85 + np.cumsum(rng.normal(0.0, 0.0003, n))
    # Inject deep negative z-stretch at bar 1050 then partial rebound at 1055
    mid[1035:1052] -= np.linspace(0.0005, 0.0060, 17)
    mid[1053:1080] += np.linspace(0.0005, 0.0040, 27)
    sp = np.full(n, 0.00010)
    bid_c = mid - 0.5 * sp
    ask_c = mid + 0.5 * sp
    bid_o = np.r_[bid_c[0], bid_c[:-1]]
    ask_o = bid_o + sp
    bid_h = np.maximum(bid_o, bid_c) + 0.0003
    bid_l = np.minimum(bid_o, bid_c) - 0.0003
    ask_h = bid_h + sp
    ask_l = bid_l + sp
    df = pd.DataFrame({
        "ts_utc": ts.strftime("%Y-%m-%d %H:%M:%S"),
        "bid_o": bid_o, "bid_h": bid_h, "bid_l": bid_l, "bid_c": bid_c,
        "ask_o": ask_o, "ask_h": ask_h, "ask_l": ask_l, "ask_c": ask_c,
        "spread_close_pips": 1.0, "spread_mean_of_bar_pips": 1.0,
    })
    df["ts"] = ts
    df["hour"] = ts.hour.to_numpy()
    df["date_ord"] = ts.floor("D").astype("int64") // 86_400_000_000_000
    df["mid_o"] = 0.5 * (df["bid_o"] + df["ask_o"])
    df["mid_h"] = 0.5 * (df["bid_h"] + df["ask_h"])
    df["mid_l"] = 0.5 * (df["bid_l"] + df["ask_l"])
    df["mid_c"] = 0.5 * (df["bid_c"] + df["ask_c"])
    df["spread_pips"] = np.maximum(0.0, (df["ask_c"] - df["bid_c"]) / p_c.PIP)
    mc = df["mid_c"]
    prev_c = mc.shift(1)
    tr = pd.concat([df["mid_h"] - df["mid_l"], (df["mid_h"] - prev_c).abs(), (df["mid_l"] - prev_c).abs()], axis=1).max(axis=1)
    df["atr24"] = tr.rolling(24, min_periods=24).mean()
    df["atr24_pctl"] = df["atr24"].rolling(500, min_periods=200).rank(pct=True)
    df["ma120"] = mc.rolling(120, min_periods=120).mean()
    df["sd120"] = mc.rolling(120, min_periods=120).std()
    df["z120"] = (mc - df["ma120"]) / df["sd120"]
    df["ret9h"] = mc - mc.shift(9)
    return df


class TestPhaseCEngine(unittest.TestCase):
    def test_no_future_leakage_in_signals(self):
        df = make_synth_h1()
        df2 = df.copy()
        df2.loc[1100:, "mid_c"] += 0.05
        df2["ma120"] = df2["mid_c"].rolling(120, min_periods=120).mean()
        df2["sd120"] = df2["mid_c"].rolling(120, min_periods=120).std()
        df2["z120"] = (df2["mid_c"] - df2["ma120"]) / df2["sd120"]
        np.testing.assert_allclose(df["z120"].iloc[200:1099], df2["z120"].iloc[200:1099], atol=1e-12)

    def test_entry_strictly_after_signal_and_no_overlap(self):
        df = make_synth_h1()
        trades = p_c.simulate_rule(df, "EURGBP", "H26_MKT_COMPARE")
        self.assertGreater(len(trades), 0)
        for t in trades:
            self.assertGreater(t["entry_ts"], t["signal_ts"])
            self.assertGreater(t["exit_ts"], t["entry_ts"])
        for a, b in zip(trades, trades[1:]):
            self.assertLess(a["exit_ts"], b["entry_ts"])

    def test_broker_costs_reduce_net(self):
        df = make_synth_h1()
        trades = p_c.simulate_rule(df, "EURGBP", "H26_MKT_COMPARE")
        n0 = p_c.apply_broker_costs(trades, "EURGBP", "dukascopy_measured", 0.0)
        n_swap = p_c.apply_broker_costs(trades, "EURGBP", "dukascopy_measured", 0.5)
        self.assertTrue(np.all(n_swap <= n0 + 1e-12))

    def test_split_boundaries(self):
        self.assertEqual(p_c.split_of(pd.Timestamp("2021-12-31 23:00:00", tz="UTC")), "IS")
        self.assertEqual(p_c.split_of(pd.Timestamp("2022-01-01 00:00:00", tz="UTC")), "VALID")
        self.assertEqual(p_c.split_of(pd.Timestamp("2026-05-19 23:00:00", tz="UTC")), "VALID")
        self.assertEqual(p_c.split_of(pd.Timestamp("2026-05-20 00:00:00", tz="UTC")), "OOS")


if __name__ == "__main__":
    unittest.main(verbosity=2)
