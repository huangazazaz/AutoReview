"""Pre-compute strategy signals for fast date-keyed lookup."""
from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd

from autotrade.core.interfaces import Strategy
from autotrade.core.models import Signal

logger = logging.getLogger(__name__)


class StrategySignalCache:
    """Pre-compute strategy signals for all candidate stocks.

    Provides O(1) date-keyed lookup for BUY/SELL signals.

    Usage:
        cache = StrategySignalCache(strategy, market_data)
        if cache.has_buy("000001", some_date):
            ...
    """

    def __init__(self, strategy: Strategy, market_data: dict[str, pd.DataFrame]):
        """Build the signal cache.

        Args:
            strategy: Strategy instance with generate_signals().
            market_data: {symbol: OHLCV DataFrame} keyed by date index.
        """
        # _buy_dates[symbol] = set of dates with BUY signals
        self._buy_dates: dict[str, set[date]] = {}
        # _sell_dates[symbol] = set of dates with SELL signals
        self._sell_dates: dict[str, set[date]] = {}
        # _signals[symbol][date] = list of Signal objects
        self._signals: dict[str, dict[date, list[Signal]]] = {}

        self._build(strategy, market_data)

    # ---- Public API ----

    def has_buy(self, symbol: str, d: date, window: int = 1) -> bool:
        """Check if there's a BUY signal within ±window days of d.

        Args:
            symbol: Stock code.
            d: Reference date.
            window: Days tolerance (default 1 = ±1 day).

        Returns:
            True if a BUY signal exists in the window.
        """
        buy_set = self._buy_dates.get(symbol, set())
        if not buy_set:
            return False
        return self._date_in_window(d, buy_set, window)

    def has_sell(self, symbol: str, d: date, window: int = 0) -> bool:
        """Check if there's a SELL signal on exact date d.

        Args:
            symbol: Stock code.
            d: Reference date.
            window: Days tolerance (default 0 = exact match).

        Returns:
            True if a SELL signal exists in the window.
        """
        sell_set = self._sell_dates.get(symbol, set())
        if not sell_set:
            return False
        return self._date_in_window(d, sell_set, window)

    def get_signals_on(self, symbol: str, d: date) -> list[Signal]:
        """Get all signals for symbol on exact date d."""
        sym_signals = self._signals.get(symbol, {})
        return sym_signals.get(d, [])

    def __len__(self) -> int:
        """Number of symbols in the cache."""
        return len(self._signals)

    # ---- Internal ----

    def _build(self, strategy: Strategy, market_data: dict[str, pd.DataFrame]):
        """Compute signals for every symbol in market_data."""
        for symbol, df in market_data.items():
            try:
                # Compute required indicators
                df_copy = df.copy()
                for ind in strategy.required_indicators:
                    df_copy = ind.compute(df_copy)

                # Generate signals
                raw_signals = strategy.generate_signals(df_copy)

                # Fill symbol if empty
                for sig in raw_signals:
                    if not sig.symbol:
                        sig.symbol = symbol

                # Index by date
                self._index_signals(symbol, raw_signals)

            except Exception as e:
                logger.warning(
                    "Failed to compute signals for %s: %s", symbol, e
                )
                continue

        logger.info(
            "StrategySignalCache built: %d symbols, %d buy dates, %d sell dates",
            len(self._signals),
            sum(len(v) for v in self._buy_dates.values()),
            sum(len(v) for v in self._sell_dates.values()),
        )

    def _index_signals(self, symbol: str, signals: list[Signal]):
        """Index signals by date and action."""
        if symbol not in self._signals:
            self._signals[symbol] = {}
        if symbol not in self._buy_dates:
            self._buy_dates[symbol] = set()
        if symbol not in self._sell_dates:
            self._sell_dates[symbol] = set()

        for sig in signals:
            d = sig.date
            # Store signal
            self._signals[symbol].setdefault(d, []).append(sig)

            # Index by action
            if sig.action == "BUY":
                self._buy_dates[symbol].add(d)
            elif sig.action in ("SELL", "SELL_SHORT", "BUY_TO_COVER"):
                self._sell_dates[symbol].add(d)

    @staticmethod
    def _date_in_window(d: date, date_set: set[date], window: int) -> bool:
        """Check if any date in date_set falls within ±window of d."""
        if d in date_set:
            return True
        if window <= 0:
            return False
        for offset in range(1, window + 1):
            if (d + timedelta(days=offset)) in date_set:
                return True
            if (d - timedelta(days=offset)) in date_set:
                return True
        return False
