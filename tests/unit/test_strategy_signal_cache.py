"""Tests for StrategySignalCache."""
from datetime import date

import numpy as np
import pandas as pd
import pytest

from autotrade.core.interfaces import Strategy, Indicator
from autotrade.core.models import Signal


class _MockIndicator(Indicator):
    """Indicator that does nothing (pass-through)."""
    name = "mock_ind"

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        return df


class _BuyEveryDayStrategy(Strategy):
    """Strategy that generates a BUY every single day."""
    name = "buy_every_day"
    required_indicators = []

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        signals = []
        for idx in df.index:
            d = idx.date() if hasattr(idx, "date") else idx
            signals.append(Signal(symbol="", date=d, action="BUY",
                                  strength=0.8, reason="test buy"))
        return signals


class _SellOnDay3Strategy(Strategy):
    """Strategy that generates SELL only on day index 3 (4th day)."""
    name = "sell_on_day3"
    required_indicators = []

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        signals = []
        for i, idx in enumerate(df.index):
            d = idx.date() if hasattr(idx, "date") else idx
            if i == 3:
                signals.append(Signal(symbol="", date=d, action="SELL",
                                      strength=1.0, reason="test sell"))
        return signals


class _NoSignalStrategy(Strategy):
    """Strategy that never generates signals."""
    name = "no_signal"
    required_indicators = []

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        return []


def _make_df(symbol: str, start_date: date, days: int) -> pd.DataFrame:
    """Create a minimal OHLCV DataFrame for testing."""
    import datetime
    records = []
    for i in range(days):
        d = start_date + datetime.timedelta(days=i)
        records.append({
            "date": d, "open": 10.0, "high": 10.5, "low": 9.5,
            "close": 10.0, "volume": 1000000, "amount": 10000000,
        })
    df = pd.DataFrame(records)
    df.set_index("date", inplace=True)
    return df


class TestStrategySignalCache:
    """Unit tests for StrategySignalCache."""

    def test_has_buy_exact_date(self):
        """BUY signal on exact date should be found."""
        from autotrade.core.strategy_signal_cache import StrategySignalCache
        start = date(2024, 1, 2)
        market = {"000001": _make_df("000001", start, 5)}
        cache = StrategySignalCache(_BuyEveryDayStrategy(), market)

        d = date(2024, 1, 3)
        assert cache.has_buy("000001", d) is True

    def test_has_buy_with_window(self):
        """BUY signal within ±window days should match."""
        from autotrade.core.strategy_signal_cache import StrategySignalCache
        start = date(2024, 1, 2)
        market = {"000001": _make_df("000001", start, 5)}
        cache = StrategySignalCache(_BuyEveryDayStrategy(), market)

        # Day 3 (Jan 4) has a BUY; check day 4 (Jan 5) with window=1
        assert cache.has_buy("000001", date(2024, 1, 5), window=1) is True

    def test_has_buy_outside_window(self):
        """BUY signal outside window should NOT match."""
        from autotrade.core.strategy_signal_cache import StrategySignalCache
        start = date(2024, 1, 2)
        market = {"000001": _make_df("000001", start, 5)}
        cache = StrategySignalCache(_BuyEveryDayStrategy(), market)

        # Only days 2-6 have BUY; day 10 is outside window=1
        assert cache.has_buy("000001", date(2024, 1, 10), window=1) is False

    def test_has_sell_exact_date(self):
        """SELL signal on exact date should be found."""
        from autotrade.core.strategy_signal_cache import StrategySignalCache
        start = date(2024, 1, 2)
        market = {"000001": _make_df("000001", start, 5)}
        cache = StrategySignalCache(_SellOnDay3Strategy(), market)

        # Day index 3 = Jan 5 (start Jan 2: i=0→Jan2, i=1→Jan3, i=2→Jan4, i=3→Jan5)
        sell_date = date(2024, 1, 5)
        assert cache.has_sell("000001", sell_date) is True

    def test_has_sell_no_signal(self):
        """No SELL signal on a non-signal date."""
        from autotrade.core.strategy_signal_cache import StrategySignalCache
        start = date(2024, 1, 2)
        market = {"000001": _make_df("000001", start, 5)}
        cache = StrategySignalCache(_SellOnDay3Strategy(), market)

        # Jan 3 (day index 1) has no SELL
        assert cache.has_sell("000001", date(2024, 1, 3)) is False

    def test_empty_market_data(self):
        """Empty market data should produce empty cache without errors."""
        from autotrade.core.strategy_signal_cache import StrategySignalCache
        cache = StrategySignalCache(_BuyEveryDayStrategy(), {})
        assert cache.has_buy("000001", date(2024, 1, 1)) is False
        assert cache.has_sell("000001", date(2024, 1, 1)) is False

    def test_no_signal_strategy(self):
        """Strategy that never signals → all lookups return False."""
        from autotrade.core.strategy_signal_cache import StrategySignalCache
        start = date(2024, 1, 2)
        market = {"000001": _make_df("000001", start, 5)}
        cache = StrategySignalCache(_NoSignalStrategy(), market)

        for i in range(5):
            d = date(2024, 1, 2 + i)
            assert cache.has_buy("000001", d) is False
            assert cache.has_sell("000001", d) is False

    def test_unknown_symbol(self):
        """Unknown symbol returns False for all lookups."""
        from autotrade.core.strategy_signal_cache import StrategySignalCache
        start = date(2024, 1, 2)
        market = {"000001": _make_df("000001", start, 5)}
        cache = StrategySignalCache(_BuyEveryDayStrategy(), market)

        assert cache.has_buy("UNKNOWN", date(2024, 1, 3)) is False
        assert cache.has_sell("UNKNOWN", date(2024, 1, 3)) is False

    def test_get_signals_on(self):
        """get_signals_on returns the actual Signal objects for a given date."""
        from autotrade.core.strategy_signal_cache import StrategySignalCache
        start = date(2024, 1, 2)
        market = {"000001": _make_df("000001", start, 5)}
        cache = StrategySignalCache(_BuyEveryDayStrategy(), market)

        sigs = cache.get_signals_on("000001", date(2024, 1, 3))
        assert len(sigs) == 1
        assert sigs[0].action == "BUY"
        assert sigs[0].symbol == "000001"

    def test_signal_symbol_filled(self):
        """Strategy signals with empty symbol are filled from the lookup key."""
        from autotrade.core.strategy_signal_cache import StrategySignalCache
        start = date(2024, 1, 2)
        market = {"600519": _make_df("600519", start, 3)}
        cache = StrategySignalCache(_BuyEveryDayStrategy(), market)

        sigs = cache.get_signals_on("600519", date(2024, 1, 2))
        assert len(sigs) == 1
        assert sigs[0].symbol == "600519"

    def test_multiple_symbols(self):
        """Cache should handle multiple symbols independently."""
        from autotrade.core.strategy_signal_cache import StrategySignalCache
        start = date(2024, 1, 2)
        market = {
            "000001": _make_df("000001", start, 5),
            "000002": _make_df("000002", start, 5),
        }
        cache = StrategySignalCache(_BuyEveryDayStrategy(), market)

        assert cache.has_buy("000001", date(2024, 1, 3)) is True
        assert cache.has_buy("000002", date(2024, 1, 3)) is True

    def test_len(self):
        """__len__ returns number of symbols in cache."""
        from autotrade.core.strategy_signal_cache import StrategySignalCache
        start = date(2024, 1, 2)
        market = {
            "000001": _make_df("000001", start, 5),
            "000002": _make_df("000002", start, 5),
        }
        cache = StrategySignalCache(_BuyEveryDayStrategy(), market)
        assert len(cache) == 2

        empty_cache = StrategySignalCache(_BuyEveryDayStrategy(), {})
        assert len(empty_cache) == 0
