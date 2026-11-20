"""Unit tests for the EXP-0001 backtest engine.

The purpose is not coverage for its own sake: these tests exist to prove the engine
cannot peek at the future, cannot fill on the signal bar, and cannot hide costs.
Run: python3 -m unittest discover -s tests -v
"""
import os, sys, unittest, datetime as dt
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts"))
import backtest_engine as be


def synth(n=420, seed=3):
    """Deterministic pseudo-random walk with a deliberate run-up at bar 300."""
    rng = np.random.default_rng(seed)
    c = 0.85 + np.cumsum(rng.normal(0, 0.0006, n))
    c[300:320] += np.linspace(0.004, 0.02, 20)          # push z above +2
    o = np.r_[c[0], c[:-1]]
    h = np.maximum(o, c) + 0.0008
    l = np.minimum(o, c) - 0.0008
    d = [dt.date(2020, 1, 1) + dt.timedelta(days=i) for i in range(n)]
    return d, o, h, l, c


class TestTiming(unittest.TestCase):
    def setUp(self):
        self.d, self.o, self.h, self.l, self.c = synth()
        self.ma, self.z, self.a = be.build_signals(self.d, self.o, self.h, self.l, self.c)
        self.trades = be.run_strategy(self.d, self.o, self.h, self.l, self.c,
                                      self.z, self.ma, self.a)

    def test_produces_trades(self):
        self.assertGreater(len(self.trades), 0, "synthetic series should trigger at least one entry")

    def test_entry_is_next_bar_open(self):
        for t in self.trades:
            i = self.d.index(dt.date.fromisoformat(t["signal_date"]))
            self.assertEqual(t["entry_date"], self.d[i + 1].isoformat(),
                             "entry must be on the bar AFTER the signal bar")
            self.assertAlmostEqual(t["entry_px"], round(float(self.o[i + 1]), 5), places=5)

    def test_no_overlapping_positions(self):
        for a, b in zip(self.trades, self.trades[1:]):
            self.assertLess(a["exit_date"], b["entry_date"])

    def test_stop_is_not_worse_than_declared(self):
        """A short can never lose more than the stop distance plus costs on the stop bar."""
        for t in self.trades:
            if t["reason"] == "stop_loss":
                self.assertAlmostEqual(t["exit_px"], t["stop_px"], places=5)

    def test_costs_are_always_subtracted(self):
        for t in self.trades:
            self.assertAlmostEqual(t["net_pips"], round(t["gross_pips"] - t["cost_pips"], 2),
                                   places=2)
            self.assertGreaterEqual(t["cost_pips"], be.SPREAD + 2 * be.SLIP - 1e-9)


class TestNoLookAhead(unittest.TestCase):
    def test_signal_unchanged_when_future_is_removed(self):
        d, o, h, l, c = synth()
        ma_f, z_f, a_f = be.build_signals(d, o, h, l, c)
        k = 350
        ma_t, z_t, a_t = be.build_signals(d[:k], o[:k], h[:k], l[:k], c[:k])
        np.testing.assert_allclose(z_f[260:k], z_t[260:k], rtol=0, atol=1e-12,
                                   err_msg="z at bar t must not depend on bars > t")
        np.testing.assert_allclose(ma_f[260:k], ma_t[260:k], rtol=0, atol=1e-12)

    def test_rolling_mean_is_trailing(self):
        x = np.arange(1.0, 11.0)
        m = be.rolling_mean(x, 3)
        self.assertTrue(np.isnan(m[1]))
        self.assertAlmostEqual(m[2], 2.0)          # (1+2+3)/3
        self.assertAlmostEqual(m[9], 9.0)          # (8+9+10)/3

    def test_future_price_change_does_not_change_past_signals(self):
        d, o, h, l, c = synth()
        _, z1, _ = be.build_signals(d, o, h, l, c)
        c2 = c.copy()
        c2[380:] *= 1.10                            # shock the far future only
        _, z2, _ = be.build_signals(d, o, h, l, c2)
        np.testing.assert_allclose(z1[250:379], z2[250:379], atol=1e-12)


class TestForwardFillAndLedger(unittest.TestCase):
    def test_ledger_equals_metrics_total(self):
        d, o, h, l, c = synth()
        ma, z, a = be.build_signals(d, o, h, l, c)
        tr = be.run_strategy(d, o, h, l, c, z, ma, a)
        m = be.metrics(tr, len(d))
        self.assertAlmostEqual(sum(t["net_pips"] for t in tr), m["total"], places=1)

    def test_time_stop_respected(self):
        d, o, h, l, c = synth()
        ma, z, a = be.build_signals(d, o, h, l, c)
        tr = be.run_strategy(d, o, h, l, c, z, ma, a, max_hold=10)
        for t in tr:
            self.assertLessEqual(t["bars_held"], 11, "nothing may exceed the time stop")

    def test_empty_trades_metrics_are_nan(self):
        m = be.metrics([], 100)
        self.assertTrue(np.isnan(m["net_exp"]))

    def test_bootstrap_ci_brackets_mean(self):
        net = np.array([10, -5, 7, 12, -3, 8, 4, -6, 9, 11, -2, 6, 3, -4, 5, 15])
        lo, hi = be.block_bootstrap_ci(net)
        self.assertLess(lo, net.mean())
        self.assertGreater(hi, net.mean())


class TestSplits(unittest.TestCase):
    def test_no_trade_leaks_across_blocks(self):
        d, o, h, l, c = synth()
        ma, z, a = be.build_signals(d, o, h, l, c)
        tr = be.run_strategy(d, o, h, l, c, z, ma, a)
        sp = be.split_trades(tr)
        total = sum(len(v) for v in sp.values())
        self.assertEqual(total, len(tr), "every trade must land in exactly one block")
        for name, (a0, b0) in be.BLOCKS.items():
            for t in sp[name]:
                self.assertTrue(a0 <= t["entry_date"] <= b0)


if __name__ == "__main__":
    unittest.main(verbosity=2)


def test_position_must_be_lagged_no_lookahead():
    """QR-002 regression: pnl[i] must use pos[i-1]; same-bar position = look-ahead."""
    import numpy as np
    from scripts.screen_universe import pnl_of  # noqa

    px = np.array([100.0, 100.0, 110.0, 110.0])
    pos = np.array([0.0, 1.0, 1.0, 1.0])  # signal fires at bar 1 close
    r = pnl_of(px, pos, 0.0)
    # return 100->110 happens on bar 2; only a lagged position may capture it
    assert abs(r[1]) < 1e-12, "bar 1 must earn nothing: signal not yet held"
    assert abs(r[2] - 0.10) < 1e-12, "bar 2 must earn the 10% move from lagged pos"
