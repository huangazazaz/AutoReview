"""Tests for extended data models."""
import pytest
from dataclasses import dataclass
from datetime import date

from autotrade.core.models import (
    Bar, Signal, Trade, Position, BacktestConfig, BacktestResult,
)


class TestSignal:
    def test_signal_new_actions(self):
        """SELL_SHORT and BUY_TO_COVER are valid action types."""
        sig_long = Signal(symbol="000001", date=date(2025, 1, 1),
                          action="BUY", strength=1.0, reason="breakout")
        sig_short = Signal(symbol="000001", date=date(2025, 1, 1),
                           action="SELL_SHORT", strength=1.0, reason="breakdown")
        sig_cover = Signal(symbol="000001", date=date(2025, 1, 1),
                           action="BUY_TO_COVER", strength=1.0, reason="exit")
        sig_sell = Signal(symbol="000001", date=date(2025, 1, 1),
                          action="SELL", strength=1.0, reason="stop")
        assert sig_long.action == "BUY"
        assert sig_short.action == "SELL_SHORT"
        assert sig_cover.action == "BUY_TO_COVER"
        assert sig_sell.action == "SELL"

    def test_signal_defaults(self):
        sig = Signal(symbol="000001", date=date(2025, 1, 1), action="BUY")
        assert sig.strength == 1.0
        assert sig.reason == ""


class TestPosition:
    def test_position_long_short_tracking(self):
        pos = Position(symbol="000001")
        assert pos.long_qty == 0
        assert pos.short_qty == 0
        assert pos.long_avg_cost == 0.0
        assert pos.short_avg_cost == 0.0

    def test_position_net_qty(self):
        pos = Position(symbol="000001", long_qty=500, short_qty=200)
        assert pos.net_qty == 300

    def test_position_default_factory(self):
        pos = Position(symbol="000001")
        # Fields should be independent per instance
        pos2 = Position(symbol="000002")
        pos.long_qty = 100
        assert pos2.long_qty == 0


class TestBacktestConfig:
    def test_short_config_defaults(self):
        cfg = BacktestConfig()
        assert cfg.allow_short is False
        assert cfg.short_margin_ratio == 1.0
        assert cfg.short_interest_rate == 0.085

    def test_short_config_enabled(self):
        cfg = BacktestConfig(allow_short=True, short_margin_ratio=0.5)
        assert cfg.allow_short is True
        assert cfg.short_margin_ratio == 0.5


class TestTrade:
    def test_trade_new_actions(self):
        t1 = Trade(symbol="000001", date=date(2025, 1, 1), action="SELL_SHORT",
                   price=10.0, quantity=100, commission=5.0)
        t2 = Trade(symbol="000001", date=date(2025, 1, 1), action="BUY_TO_COVER",
                   price=9.0, quantity=100, commission=5.0, stamp_duty=0.9)
        assert t1.action == "SELL_SHORT"
        assert t2.action == "BUY_TO_COVER"
