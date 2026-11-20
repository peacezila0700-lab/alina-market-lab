"""Tests for the Python mirror of the EA risk governor."""
from alina_lab.governor import Governor, GovernorConfig


def test_size_scales_with_risk_budget():
    g = Governor(GovernorConfig(max_risk_per_trade_pct=2.0))
    g.start(10_000)
    # 1.5 x ATR 1.0 stop, tick 0.01, tick value $1 per point -> $150 loss per lot
    lots = g.size(10_000, atr=1.0, tick_value=1.0, tick_size=0.01)
    assert abs(lots - 1.33) < 0.011, lots          # 200 / 150 = 1.333 -> 1.33 after step


def test_size_halves_when_atr_doubles():
    g = Governor()
    g.start(10_000)
    a = g.size(10_000, atr=1.0, tick_value=1.0, tick_size=0.01)
    b = g.size(10_000, atr=2.0, tick_value=1.0, tick_size=0.01)
    assert abs(a / b - 2.0) < 0.05, (a, b)


def test_size_never_grows_after_losses():
    """The anti-martingale property, asserted rather than promised."""
    g = Governor()
    eq = 10_000.0
    g.start(eq)
    prev = None
    for loss in (0, 500, 500, 1000):
        eq -= loss
        g.new_day(eq)
        s = g.size(eq, atr=1.0, tick_value=1.0, tick_size=0.01)
        if prev is not None:
            assert s <= prev + 1e-9, f"size grew after a loss: {prev} -> {s}"
        prev = s


def test_daily_loss_stop_blocks_entries():
    g = Governor(GovernorConfig(max_daily_loss_pct=3.0))
    g.start(10_000)
    ok, why = g.check(9_500, spread_points=5)
    assert not ok and "daily loss" in why, why


def test_drawdown_latch_is_permanent():
    g = Governor(GovernorConfig(max_drawdown_pct=20.0))
    g.start(10_000)
    ok, _ = g.check(7_900, spread_points=5)
    assert not ok
    # equity recovers fully, but the latch must stay closed until manual reset
    ok, why = g.check(11_000, spread_points=5)
    assert not ok and "HALTED" in why


def test_spread_guard_blocks_expensive_entries():
    g = Governor(GovernorConfig(max_spread_points=30))
    g.start(10_000)
    ok, why = g.check(10_000, spread_points=45)
    assert not ok and "spread" in why


def test_normal_conditions_allow_trading():
    g = Governor()
    g.start(10_000)
    ok, why = g.check(10_050, spread_points=8)
    assert ok and why == "OK"
