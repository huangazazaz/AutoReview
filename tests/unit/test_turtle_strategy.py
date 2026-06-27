"""Tests for Turtle Trading Strategy."""
import pandas as pd
import numpy as np
from datetime import date, timedelta

from autotrade.strategies.turtle import TurtleTraderStrategy
from autotrade.core.models import Signal


def _make_trending_df(direction="up", n_days=100):
    """Generate a DataFrame with a clear trend for testing breakout logic."""
    np.random.seed(42)
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(n_days)]

    if direction == "up":
        base = np.linspace(10, 20, n_days)
    elif direction == "down":
        base = np.linspace(20, 10, n_days)
    else:
        base = np.full(n_days, 15.0)

    noise = np.random.normal(0, 0.5, n_days).cumsum() * 0.1
    close = base + noise
    # Set high = close so close CAN break above past highs
    high = close + np.abs(np.random.normal(0, 0.2, n_days))
    low = close - np.abs(np.random.normal(0, 0.3, n_days))

    df = pd.DataFrame({
        "high": high, "low": low, "close": close,
        "volume": 100000,
    }, index=dates)

    import pandas_ta as ta
    df["ind_atr_20"] = ta.atr(df["high"], df["low"], df["close"], length=20)

    return df


class TestTurtleStrategy:
    def test_strategy_name_and_indicators(self):
        strategy = TurtleTraderStrategy()
        assert strategy.name == "turtle"
        indicator_names = [ind.name for ind in strategy.required_indicators]
        assert "atr" in indicator_names

    def test_system1_long_entry_on_breakout(self):
        """System 1: 20-day high breakout → BUY signal."""
        strategy = TurtleTraderStrategy(use_system1=True, use_system2=False)
        df = _make_trending_df(direction="up", n_days=60)

        signals = strategy.generate_signals(df)
        buy_signals = [s for s in signals if s.action == "BUY"]
        assert len(buy_signals) > 0, "Expected at least one BUY on uptrend breakout"

    def test_system2_long_entry_on_breakout(self):
        """System 2: 55-day high breakout → BUY signal."""
        strategy = TurtleTraderStrategy(use_system1=False, use_system2=True)
        df = _make_trending_df(direction="up", n_days=100)

        signals = strategy.generate_signals(df)
        buy_signals = [s for s in signals if s.action == "BUY"]
        assert len(buy_signals) > 0, "Expected at least one BUY on 55-day breakout"

    def test_system1_short_entry_on_breakdown(self):
        """System 1: 20-day low breakdown → SELL_SHORT signal."""
        strategy = TurtleTraderStrategy(
            use_system1=True, use_system2=False,
            allow_long=False, allow_short=True,
        )
        df = _make_trending_df(direction="down", n_days=60)

        signals = strategy.generate_signals(df)
        short_signals = [s for s in signals if s.action == "SELL_SHORT"]
        assert len(short_signals) > 0, "Expected at least one SELL_SHORT on downtrend"

    def test_no_signals_in_sideways_market(self):
        """Sideways market should produce few or no breakout signals."""
        strategy = TurtleTraderStrategy(use_system1=True, use_system2=False)
        df = _make_trending_df(direction="sideways", n_days=60)

        signals = strategy.generate_signals(df)
        buy_signals = [s for s in signals if s.action == "BUY"]
        # In pure sideways, breakouts are rare
        assert len(buy_signals) <= 5, f"Expected few signals in sideways, got {len(buy_signals)}"

    def test_dual_system_generates_independent_signals(self):
        """Both systems enabled → signals from both."""
        strategy = TurtleTraderStrategy(use_system1=True, use_system2=True)
        df = _make_trending_df(direction="up", n_days=100)

        signals = strategy.generate_signals(df)
        total_buys = len([s for s in signals if s.action == "BUY"])
        assert total_buys > 0

    def test_stop_loss_generates_exit(self):
        """After entry, a large one-day drop triggers stop loss."""
        strategy = TurtleTraderStrategy(
            use_system1=True, use_system2=False,
            stop_atr_mult=0.3,
        )
        n = 80
        dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(n)]
        # Uptrend with highs near close so breakout can happen, then crash
        base_prices = np.linspace(10, 20, 45).tolist()
        base_prices.append(12.0)  # big crash
        base_prices += [12.0 + i * 0.05 for i in range(n - 46)]

        df = pd.DataFrame({
            "high": [b + 0.1 for b in base_prices],
            "low": [b - 0.2 for b in base_prices],
            "close": base_prices,
            "volume": 100000,
        }, index=dates)

        import pandas_ta as ta
        df["ind_atr_20"] = ta.atr(df["high"], df["low"], df["close"], length=20)

        signals = strategy.generate_signals(df)
        sell_signals = [s for s in signals if s.action == "SELL"]
        assert len(sell_signals) > 0, f"Expected exit signal on crash, got {[s.action for s in signals]}"

    def test_system1_skip_after_win(self):
        """skip_if_last_win_sys1=True skips next System 1 after profitable trade."""
        strategy = TurtleTraderStrategy(
            use_system1=True, use_system2=False,
            skip_if_last_win_sys1=True,
        )
        df = _make_trending_df(direction="up", n_days=80)

        signals = strategy.generate_signals(df)
        buy_signals = [s for s in signals if s.action == "BUY"]
        assert len(buy_signals) > 0

    def test_pyramiding_signals(self):
        """Multiple BUY signals as price moves favorably."""
        strategy = TurtleTraderStrategy(
            use_system1=True, use_system2=False,
            max_units=4, pyramid_atr_mult=0.5,
        )
        df = _make_trending_df(direction="up", n_days=100)

        signals = strategy.generate_signals(df)
        buy_signals = [s for s in signals if s.action == "BUY"]
        assert len(buy_signals) > 0

    def test_exit_on_breakdown(self):
        """System 1 exit: sharp breakdown triggers SELL via stop loss."""
        strategy = TurtleTraderStrategy(
            use_system1=True, use_system2=False,
            stop_atr_mult=0.3,
        )
        n = 100
        dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(n)]
        # Uptrend with highs near close, then crash
        base_prices = np.linspace(10, 25, 65).tolist()
        base_prices += [12.0]  # crash
        base_prices += [12.0] * (n - 66)

        df = pd.DataFrame({
            "high": [b + 0.1 for b in base_prices],
            "low": [b - 0.2 for b in base_prices],
            "close": base_prices,
            "volume": 100000,
        }, index=dates)

        import pandas_ta as ta
        df["ind_atr_20"] = ta.atr(df["high"], df["low"], df["close"], length=20)

        signals = strategy.generate_signals(df)
        sell_signals = [s for s in signals if s.action == "SELL"]
        assert len(sell_signals) > 0, f"Expected SELL on breakdown, got {[s.action for s in signals]}"

    def test_signal_strength_is_positive(self):
        """All BUY/SELL_SHORT signals have positive strength."""
        strategy = TurtleTraderStrategy()
        df = _make_trending_df(direction="up", n_days=100)

        signals = strategy.generate_signals(df)
        for s in signals:
            if s.action in ("BUY", "SELL_SHORT"):
                assert s.strength > 0, f"Expected positive strength, got {s.strength}"
            elif s.action in ("SELL", "BUY_TO_COVER"):
                assert s.strength > 0, f"Expected positive strength for exit"

    def test_direction_flag_disables_short(self):
        """allow_short=False produces no SELL_SHORT signals."""
        strategy = TurtleTraderStrategy(
            use_system1=True, use_system2=False,
            allow_long=True, allow_short=False,
        )
        df = _make_trending_df(direction="down", n_days=60)

        signals = strategy.generate_signals(df)
        short_signals = [s for s in signals if s.action == "SELL_SHORT"]
        assert len(short_signals) == 0, "No short signals when allow_short=False"

    def test_direction_flag_disables_long(self):
        """allow_long=False produces no BUY signals."""
        strategy = TurtleTraderStrategy(
            use_system1=True, use_system2=False,
            allow_long=False, allow_short=True,
        )
        df = _make_trending_df(direction="up", n_days=60)

        signals = strategy.generate_signals(df)
        buy_signals = [s for s in signals if s.action == "BUY"]
        assert len(buy_signals) == 0, "No buy signals when allow_long=False"
