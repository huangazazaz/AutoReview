"""Tests for backtester short selling support."""
import pandas as pd
from datetime import date, timedelta

from autotrade.core.models import Bar, Signal, BacktestConfig
from autotrade.core.backtester import Backtester


def _make_bars(symbol="000001", start_price=10.0, n=30):
    """Generate n days of simple OHLCV bars."""
    bars = []
    prices = [start_price + i * 0.1 for i in range(n)]
    for i, p in enumerate(prices):
        bars.append(Bar(
            symbol=symbol,
            date=date(2025, 1, 1) + timedelta(days=i),
            open=p, high=p + 0.05, low=p - 0.05, close=p,
            volume=100000, amount=p * 100000,
        ))
    return bars


class TestBacktesterShort:
    def test_short_entry_and_cover_basic(self):
        """Short and cover produce expected trade actions."""
        cfg = BacktestConfig(
            initial_capital=100_000, fill_price="close",
            allow_short=True, short_margin_ratio=1.0,
            position_sizing="full",
        )
        bt = Backtester(cfg)
        bars = _make_bars(start_price=10.0, n=20)

        signals = [
            Signal(symbol="000001", date=bars[10].date, action="SELL_SHORT",
                   strength=1.0, reason="breakdown"),
            Signal(symbol="000001", date=bars[15].date, action="BUY_TO_COVER",
                   strength=1.0, reason="exit"),
        ]

        result = bt.run(signals, bars)
        trades = result.trades
        assert len(trades) == 2
        assert trades[0].action == "SELL_SHORT"
        assert trades[1].action == "BUY_TO_COVER"

    def test_short_entry_requires_allow_short(self):
        """Short signals ignored when allow_short=False."""
        cfg = BacktestConfig(
            initial_capital=100_000, fill_price="close",
            allow_short=False,
        )
        bt = Backtester(cfg)
        bars = _make_bars(n=20)

        signals = [
            Signal(symbol="000001", date=bars[10].date, action="SELL_SHORT",
                   strength=1.0, reason="breakdown"),
        ]

        result = bt.run(signals, bars)
        short_trades = [t for t in result.trades if t.action == "SELL_SHORT"]
        assert len(short_trades) == 0

    def test_short_cover_profit_calculation(self):
        """Short at 15, cover at 10 → profit."""
        cfg = BacktestConfig(
            initial_capital=100_000, fill_price="close",
            allow_short=True, short_margin_ratio=1.0,
            position_sizing="full",
        )
        bt = Backtester(cfg)

        bars = []
        for i in range(20):
            p = 15.0 if i < 5 else (15.0 - (i - 5) * 0.5)
            bars.append(Bar(
                symbol="000001",
                date=date(2025, 1, 1) + timedelta(days=i),
                open=p, high=p, low=p, close=p,
                volume=100000, amount=p * 100000,
            ))

        signals = [
            Signal(symbol="000001", date=bars[5].date, action="SELL_SHORT",
                   strength=1.0, reason="breakdown"),
            Signal(symbol="000001", date=bars[15].date, action="BUY_TO_COVER",
                   strength=1.0, reason="exit"),
        ]

        result = bt.run(signals, bars)
        final_equity = result.equity_curve.iloc[-1]
        assert final_equity > 100_000, f"Expected profit, got equity={final_equity}"

    def test_simultaneous_long_and_short(self):
        """Can hold long and short positions simultaneously."""
        cfg = BacktestConfig(
            initial_capital=100_000, fill_price="close",
            allow_short=True, short_margin_ratio=1.0,
            position_sizing="strength",
        )
        bt = Backtester(cfg)
        bars = _make_bars(n=30)

        signals = [
            Signal(symbol="000001", date=bars[5].date, action="BUY",
                   strength=0.5, reason="long entry"),
            Signal(symbol="000001", date=bars[10].date, action="SELL_SHORT",
                   strength=0.5, reason="short entry"),
            Signal(symbol="000001", date=bars[20].date, action="SELL",
                   strength=1.0, reason="exit long"),
            Signal(symbol="000001", date=bars[25].date, action="BUY_TO_COVER",
                   strength=1.0, reason="exit short"),
        ]

        result = bt.run(signals, bars)
        actions = [t.action for t in result.trades]
        assert "BUY" in actions
        assert "SELL_SHORT" in actions
        assert "SELL" in actions
        assert "BUY_TO_COVER" in actions

    def test_margin_insufficient_blocks_short(self):
        """When margin ratio is high, second short is blocked."""
        cfg = BacktestConfig(
            initial_capital=2000, fill_price="close",
            allow_short=True, short_margin_ratio=1.5,
            position_sizing="full",
        )
        bt = Backtester(cfg)
        bars = _make_bars(start_price=10.0, n=20)

        signals = [
            Signal(symbol="000001", date=bars[5].date, action="SELL_SHORT",
                   strength=1.0, reason="first short"),
            Signal(symbol="000001", date=bars[6].date, action="SELL_SHORT",
                   strength=1.0, reason="second short — should fail"),
        ]

        result = bt.run(signals, bars)
        short_trades = [t for t in result.trades if t.action == "SELL_SHORT"]
        assert len(short_trades) == 1, f"Expected 1 short, got {len(short_trades)}"
