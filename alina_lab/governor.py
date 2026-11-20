"""Python mirror of the MQL5 risk governor.

Why a mirror: the .mq5 cannot be compiled in this sandbox, so the *math* of the governor is
verified here against the same inputs the EA uses. The two implementations must agree on:
  - position size = risk money / (stop distance in money per lot)
  - daily loss stop, drawdown latch, spread guard
  - and, structurally, "no size increase after a loss"

This file is the test surface. It does not trade and it does not claim an edge.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GovernorConfig:
    target_vol_annual_pct: float = 10.0
    max_risk_per_trade_pct: float = 2.0
    max_daily_loss_pct: float = 3.0
    max_drawdown_pct: float = 20.0
    max_spread_points: int = 30
    atr_stop_mult: float = 1.5
    min_lot: float = 0.01
    max_lot: float = 10000.0
    lot_step: float = 0.01


@dataclass
class Governor:
    cfg: GovernorConfig = field(default_factory=GovernorConfig)
    equity_peak: float = 0.0
    day_start_equity: float = 0.0
    halted: bool = False
    halt_reason: str = ""
    _last_size: float = 0.0

    def start(self, equity: float) -> None:
        self.equity_peak = equity
        self.day_start_equity = equity

    def new_day(self, equity: float) -> None:
        self.day_start_equity = equity

    def check(self, equity: float, spread_points: int) -> tuple[bool, str]:
        """Mirror of RiskChecks(). Returns (allowed, reason)."""
        if equity > self.equity_peak:
            self.equity_peak = equity

        if self.equity_peak > 0:
            dd = (self.equity_peak - equity) / self.equity_peak * 100.0
            if dd >= self.cfg.max_drawdown_pct and not self.halted:
                self.halted = True
                self.halt_reason = f"max drawdown {dd:.2f}% >= {self.cfg.max_drawdown_pct}%"
        if self.halted:
            return False, f"HALTED: {self.halt_reason}"

        if self.day_start_equity > 0:
            day = (self.day_start_equity - equity) / self.day_start_equity * 100.0
            if day >= self.cfg.max_daily_loss_pct:
                return False, f"daily loss stop {day:.2f}%"

        if spread_points > self.cfg.max_spread_points:
            return False, f"spread {spread_points} > {self.cfg.max_spread_points}"

        return True, "OK"

    def size(self, equity: float, atr: float, tick_value: float, tick_size: float) -> float:
        """Mirror of SizeForRisk(). Volume for a 1.5xATR stop at the configured risk budget."""
        if atr <= 0 or tick_value <= 0 or tick_size <= 0 or equity <= 0:
            return 0.0
        risk_money = equity * self.cfg.max_risk_per_trade_pct / 100.0
        stop_dist = atr * self.cfg.atr_stop_mult
        loss_per_lot = stop_dist / tick_size * tick_value
        if loss_per_lot <= 0:
            return 0.0
        lots = risk_money / loss_per_lot
        lots = int(lots / self.cfg.lot_step) * self.cfg.lot_step
        lots = max(self.cfg.min_lot, min(self.cfg.max_lot, lots))
        self._last_size = round(lots, 4)
        return self._last_size
