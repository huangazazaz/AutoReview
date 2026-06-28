# Strategy-Driven Portfolio Backtest — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fuse stock filtering (Screener + AI) with trading strategies in the portfolio backtester — strategies drive entry/exit signals, ExitManager provides safety net.

**Architecture:** New `StrategySignalCache` pre-computes strategy signals per stock. `PortfolioBacktester.run()` gets optional `signal_cache` parameter: strategy BUY confirms screener entries, strategy SELL exits positions before ExitManager fallback. Backward compatible — no strategy = current behavior.

**Tech Stack:** Python 3.11+, pandas, numpy, pytest, existing plugin architecture (Strategy/Screener ABCs)

**Spec:** `docs/superpowers/specs/2026-06-28-strategy-portfolio-backtest-design.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `autotrade/core/strategy_signal_cache.py` | **CREATE** | Pre-compute & index strategy signals |
| `autotrade/core/account.py:29-39` | MODIFY | Add `trigger` field to `PortfolioTrade` |
| `autotrade/core/portfolio_backtester.py:22-38` | MODIFY | Add strategy fields to config |
| `autotrade/core/portfolio_backtester.py:49-184` | MODIFY | Strategy-driven buy/sell in daily loop |
| `autotrade/core/engine.py:527-739` | MODIFY | Accept strategy params, build cache |
| `autotrade/triggers/cli.py:198-239` | MODIFY | New `--strategy` / `--strategy-params` CLI options |
| `autotrade/reporters/console.py` | MODIFY | Trigger column in portfolio output |
| `autotrade/reporters/plot_reporter.py` | MODIFY | Trigger-aware chart |
| `config/backtest/portfolio.yaml` | MODIFY | `strategy` / `strategy_params` fields |
| `tests/unit/test_strategy_signal_cache.py` | **CREATE** | Unit tests for cache |
| `tests/unit/test_portfolio_backtester_strategy.py` | **CREATE** | Unit tests for strategy-driven backtester |
| `tests/integration/test_portfolio_backtest.py` | MODIFY | Strategy-driven integration case |

---

### Task 1: Add `trigger` field to PortfolioTrade

**Files:**
- Modify: `autotrade/core/account.py:29-39`

- [ ] **Step 1: Add `trigger` field to PortfolioTrade dataclass**

Open `autotrade/core/account.py`. The `PortfolioTrade` dataclass currently sits at lines 29-39:

```python
@dataclass
class PortfolioTrade:
    """A completed buy-sell round trip."""
    symbol: str
    buy_date: date
    sell_date: date
    buy_price: float
    sell_price: float
    quantity: int
    pnl: float
    pnl_pct: float
```

Add `trigger: str = ""` after `pnl_pct`:

```python
@dataclass
class PortfolioTrade:
    """A completed buy-sell round trip."""
    symbol: str
    buy_date: date
    sell_date: date
    buy_price: float
    sell_price: float
    quantity: int
    pnl: float
    pnl_pct: float
    trigger: str = ""  # "strategy_buy" | "strategy_sell" | "trailing_stop" | ...
```

- [ ] **Step 2: Verify existing tests still pass**

Run: `pytest tests/unit/test_portfolio_backtester.py -v --tb=short`
Expected: All tests PASS (the new field has a default, so existing code is unaffected).

- [ ] **Step 3: Commit**

```bash
git add autotrade/core/account.py
git commit -m "feat: add trigger field to PortfolioTrade for strategy-driven exits"
```

---

### Task 2: Create StrategySignalCache

**Files:**
- Create: `autotrade/core/strategy_signal_cache.py`
- Create: `tests/unit/test_strategy_signal_cache.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_strategy_signal_cache.py`:

```python
"""Tests for StrategySignalCache."""
from datetime import date

import numpy as np
import pandas as pd
import pytest

from autotrade.core.interfaces import Strategy, Indicator
from autotrade.core.models import Signal
from autotrade.core.strategy_signal_cache import StrategySignalCache


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
    records = []
    for i in range(days):
        d = date(start_date.year, start_date.month, start_date.day + i)
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
        start = date(2024, 1, 2)
        market = {"000001": _make_df("000001", start, 5)}
        cache = StrategySignalCache(_BuyEveryDayStrategy(), market)

        d = date(2024, 1, 3)
        assert cache.has_buy("000001", d) is True

    def test_has_buy_with_window(self):
        """BUY signal within ±window days should match."""
        start = date(2024, 1, 2)
        market = {"000001": _make_df("000001", start, 5)}
        cache = StrategySignalCache(_BuyEveryDayStrategy(), market)

        # Day 3 has a BUY; check day 4 with window=1
        assert cache.has_buy("000001", date(2024, 1, 5), window=1) is True

    def test_has_buy_outside_window(self):
        """BUY signal outside window should NOT match."""
        start = date(2024, 1, 2)
        market = {"000001": _make_df("000001", start, 5)}
        cache = StrategySignalCache(_BuyEveryDayStrategy(), market)

        # Only days 2-6 have BUY; day 10 is outside window=1
        assert cache.has_buy("000001", date(2024, 1, 10), window=1) is False

    def test_has_sell_exact_date(self):
        """SELL signal on exact date should be found."""
        start = date(2024, 1, 2)
        market = {"000001": _make_df("000001", start, 5)}
        cache = StrategySignalCache(_SellOnDay3Strategy(), market)

        # Day 3 → index 3 → 4th trading day = Jan 5
        sell_date = date(2024, 1, 5)
        assert cache.has_sell("000001", sell_date) is True

    def test_has_sell_no_signal(self):
        """No SELL signal on a non-signal date."""
        start = date(2024, 1, 2)
        market = {"000001": _make_df("000001", start, 5)}
        cache = StrategySignalCache(_SellOnDay3Strategy(), market)

        # Jan 3 (day index 1) has no SELL
        assert cache.has_sell("000001", date(2024, 1, 3)) is False

    def test_empty_market_data(self):
        """Empty market data should produce empty cache without errors."""
        cache = StrategySignalCache(_BuyEveryDayStrategy(), {})
        assert cache.has_buy("000001", date(2024, 1, 1)) is False
        assert cache.has_sell("000001", date(2024, 1, 1)) is False

    def test_no_signal_strategy(self):
        """Strategy that never signals → all lookups return False."""
        start = date(2024, 1, 2)
        market = {"000001": _make_df("000001", start, 5)}
        cache = StrategySignalCache(_NoSignalStrategy(), market)

        for i in range(5):
            d = date(2024, 1, 2 + i)
            assert cache.has_buy("000001", d) is False
            assert cache.has_sell("000001", d) is False

    def test_unknown_symbol(self):
        """Unknown symbol returns False for all lookups."""
        start = date(2024, 1, 2)
        market = {"000001": _make_df("000001", start, 5)}
        cache = StrategySignalCache(_BuyEveryDayStrategy(), market)

        assert cache.has_buy("UNKNOWN", date(2024, 1, 3)) is False
        assert cache.has_sell("UNKNOWN", date(2024, 1, 3)) is False

    def test_get_signals_on(self):
        """get_signals_on returns the actual Signal objects for a given date."""
        start = date(2024, 1, 2)
        market = {"000001": _make_df("000001", start, 5)}
        cache = StrategySignalCache(_BuyEveryDayStrategy(), market)

        sigs = cache.get_signals_on("000001", date(2024, 1, 3))
        assert len(sigs) == 1
        assert sigs[0].action == "BUY"
        assert sigs[0].symbol == "000001"

    def test_signal_symbol_filled(self):
        """Strategy signals with empty symbol are filled from the lookup key."""
        start = date(2024, 1, 2)
        market = {"600519": _make_df("600519", start, 3)}
        cache = StrategySignalCache(_BuyEveryDayStrategy(), market)

        sigs = cache.get_signals_on("600519", date(2024, 1, 2))
        assert len(sigs) == 1
        assert sigs[0].symbol == "600519"

    def test_multiple_symbols(self):
        """Cache should handle multiple symbols independently."""
        start = date(2024, 1, 2)
        market = {
            "000001": _make_df("000001", start, 5),
            "000002": _make_df("000002", start, 5),
        }
        cache = StrategySignalCache(_BuyEveryDayStrategy(), market)

        assert cache.has_buy("000001", date(2024, 1, 3)) is True
        assert cache.has_buy("000002", date(2024, 1, 3)) is True
        assert cache.has_buy("000001", date(2024, 1, 3)) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_strategy_signal_cache.py -v --tb=short`
Expected: FAIL with `ModuleNotFoundError: No module named 'autotrade.core.strategy_signal_cache'`

- [ ] **Step 3: Implement StrategySignalCache**

Create `autotrade/core/strategy_signal_cache.py`:

```python
"""Pre-compute strategy signals for fast date-keyed lookup."""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Optional

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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_strategy_signal_cache.py -v --tb=short`
Expected: All 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add autotrade/core/strategy_signal_cache.py tests/unit/test_strategy_signal_cache.py
git commit -m "feat: add StrategySignalCache for pre-computing strategy signals"
```

---

### Task 3: Enhance PortfolioBacktester with strategy-driven logic

**Files:**
- Modify: `autotrade/core/portfolio_backtester.py`
- Create: `tests/unit/test_portfolio_backtester_strategy.py`

- [ ] **Step 1: Write failing tests for strategy-driven backtest behavior**

Create `tests/unit/test_portfolio_backtester_strategy.py`:

```python
"""Tests for strategy-driven PortfolioBacktester behavior."""
from datetime import date

import numpy as np
import pandas as pd

from autotrade.core.account import PortfolioPosition, PortfolioTrade
from autotrade.core.models import Signal
from autotrade.core.interfaces import Strategy
from autotrade.core.portfolio_backtester import (
    PortfolioBacktester, PortfolioBacktestConfig,
)
from autotrade.core.strategy_signal_cache import StrategySignalCache


# ---- Test Helpers ----

def _make_config(**kwargs) -> PortfolioBacktestConfig:
    defaults = {
        "start_date": date(2024, 1, 2),
        "end_date": date(2024, 1, 15),
        "initial_capital": 1_000_000.0,
        "cash_buffer": 0.05,
        "top_n_candidates": 10,
        "fill_price": "next_open",
        "commission_rate": 0.0,      # zero commission for deterministic tests
        "stamp_duty_rate": 0.0,
        "slippage": 0.0,
        "min_commission": 0.0,
        "lot_size": 100,
        "allow_t_plus_1": False,     # simplify: no T+1 lock
        "exit_rules": {
            "trailing_stop": {"enabled": False},
            "hard_stop": {"enabled": False},
            "time_stop": {"enabled": False},
            "signal_decay": {"enabled": False},
        },
        "market_regime": {
            "score_threshold": 0.0,
            "bullish_threshold": 0.9,
            "neutral_threshold": 0.9,
        },
    }
    defaults.update(kwargs)
    return PortfolioBacktestConfig(**defaults)


def _make_dates(start: date, days: int) -> list[date]:
    """Generate consecutive weekdays."""
    import datetime
    dates = []
    current = start
    while len(dates) < days:
        if current.weekday() < 5:
            dates.append(current)
        current += datetime.timedelta(days=1)
    return dates


def _make_market(symbols: list[str], dates: list[date],
                 base_prices: dict[str, float] | None = None) -> dict[str, pd.DataFrame]:
    """Build minimal market data with flat prices."""
    base = base_prices or {}
    market = {}
    for sym in symbols:
        price = base.get(sym, 10.0)
        records = []
        for d in dates:
            records.append({
                "date": d, "open": price, "high": price * 1.02,
                "low": price * 0.98, "close": price,
                "volume": 1_000_000, "amount": price * 1_000_000,
            })
        df = pd.DataFrame(records)
        df.set_index("date", inplace=True)
        market[sym] = df
    return market


# ---- Strategy for testing ----

class _AlwaysBuyStrategy(Strategy):
    """BUY signal every day for every stock."""
    name = "always_buy"
    required_indicators = []

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        signals = []
        for idx in df.index:
            d = idx.date() if hasattr(idx, "date") else idx
            signals.append(Signal(symbol="", date=d, action="BUY",
                                  strength=0.5, reason="always"))
        return signals


class _SellAfter2DaysStrategy(Strategy):
    """SELL on the 3rd trading day (index 2)."""
    name = "sell_after_2"
    required_indicators = []

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        signals = []
        for i, idx in enumerate(df.index):
            d = idx.date() if hasattr(idx, "date") else idx
            if i == 2:
                signals.append(Signal(symbol="", date=d, action="SELL",
                                      strength=1.0, reason="sell day 3"))
        return signals


class _BuyDay2OnlyStrategy(Strategy):
    """BUY only on 2nd trading day (index 1)."""
    name = "buy_day2"
    required_indicators = []

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        signals = []
        for i, idx in enumerate(df.index):
            d = idx.date() if hasattr(idx, "date") else idx
            if i == 1:
                signals.append(Signal(symbol="", date=d, action="BUY",
                                      strength=0.5, reason="buy day 2"))
        return signals


# ---- Tests ----

class TestPortfolioBacktesterStrategyBuy:
    """Tests for strategy-confirmed buy logic."""

    def test_strategy_buy_confirms_entry(self):
        """With strategy signals, screener candidate + BUY → position opened."""
        dates = _make_dates(date(2024, 1, 2), 10)
        market = _make_market(["000001"], dates)
        cache = StrategySignalCache(_AlwaysBuyStrategy(), market)

        config = _make_config()
        bt = PortfolioBacktester(config)

        screener = {d: [("000001", 0.8, "strong")] for d in dates}
        result = bt.run(market, screener, signal_cache=cache)

        assert len(result.trades) >= 1
        buy_trades = [t for t in result.trades if t.trigger == "strategy_buy"]
        assert len(buy_trades) >= 1

    def test_no_strategy_buy_skips_candidate(self):
        """Without strategy BUY signal, screener candidate is skipped."""
        dates = _make_dates(date(2024, 1, 2), 10)
        market = _make_market(["000001"], dates)
        cache = StrategySignalCache(_BuyDay2OnlyStrategy(), market)

        config = _make_config()
        bt = PortfolioBacktester(config)

        # Day 1 (Jan 2) has no BUY from _BuyDay2OnlyStrategy
        screener = {d: [("000001", 0.8, "strong")] for d in dates}
        result = bt.run(market, screener, signal_cache=cache)

        # Should still have trades (from day 2 BUY signal, bought on day 3)
        strategy_buys = [t for t in result.trades if t.trigger == "strategy_buy"]
        # Verify buys only happen on dates with strategy confirmation
        for t in strategy_buys:
            assert cache.has_buy(t.symbol, t.buy_date, window=1)

    def test_backward_compat_no_cache(self):
        """Without signal_cache, behavior is identical to current (screener-only)."""
        dates = _make_dates(date(2024, 1, 2), 10)
        market = _make_market(["000001"], dates)

        config = _make_config()
        bt = PortfolioBacktester(config)

        screener = {d: [("000001", 0.8, "strong")] for d in dates}
        result = bt.run(market, screener, signal_cache=None)

        # Should have trades from screener-only entries
        assert len(result.trades) >= 1
        # All trades should have trigger="screener" (not "strategy_buy")
        for t in result.trades:
            assert t.trigger != "strategy_buy"


class TestPortfolioBacktesterStrategySell:
    """Tests for strategy-driven sell logic."""

    def test_strategy_sell_exits_position(self):
        """Strategy SELL signal should exit the position."""
        dates = _make_dates(date(2024, 1, 2), 10)
        market = _make_market(["000001"], dates)
        cache = StrategySignalCache(_SellAfter2DaysStrategy(), market)

        config = _make_config()
        bt = PortfolioBacktester(config)

        screener = {d: [("000001", 0.8, "strong")] for d in dates}
        result = bt.run(market, screener, signal_cache=cache)

        sell_trades = [t for t in result.trades if t.trigger == "strategy_sell"]
        assert len(sell_trades) >= 1

    def test_exit_manager_fallback_when_no_strategy_sell(self):
        """When strategy has no SELL, ExitManager can still trigger."""
        dates = _make_dates(date(2024, 1, 2), 10)
        market = _make_market(["000001"], dates)
        cache = StrategySignalCache(_AlwaysBuyStrategy(), market)  # no sells

        config = _make_config(
            exit_rules={
                "trailing_stop": {"enabled": False},
                "hard_stop": {"enabled": True, "loss_pct": 0.01},
                "time_stop": {"enabled": False},
                "signal_decay": {"enabled": False},
            },
        )
        bt = PortfolioBacktester(config)

        screener = {d: [("000001", 0.8, "strong")] for d in dates}
        result = bt.run(market, screener, signal_cache=cache)

        # Should have hard_stop exits since price never rises
        hard_stops = [t for t in result.trades if t.trigger == "hard_stop"]
        assert len(hard_stops) >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_portfolio_backtester_strategy.py -v --tb=short`
Expected: FAIL — tests reference features not yet implemented (trigger values, signal_cache parameter).

- [ ] **Step 3: Enhance PortfolioBacktestConfig with strategy fields**

Open `autotrade/core/portfolio_backtester.py`. Modify the `PortfolioBacktestConfig` dataclass (lines 22-38). Add three new fields after `market_regime`:

```python
@dataclass
class PortfolioBacktestConfig:
    """Configuration for a portfolio backtest run."""
    start_date: date
    end_date: date
    initial_capital: float = 1_000_000.0
    cash_buffer: float = 0.05
    top_n_candidates: int = 50
    fill_price: str = "next_open"
    commission_rate: float = 0.0003
    stamp_duty_rate: float = 0.001
    slippage: float = 0.001
    min_commission: float = 5.0
    lot_size: int = 100
    allow_t_plus_1: bool = True
    exit_rules: dict = field(default_factory=dict)
    market_regime: dict = field(default_factory=dict)
    strategy_name: str | None = None       # NEW
    strategy_params: dict | None = None    # NEW
    strategy_buy_window: int = 1           # NEW
```

- [ ] **Step 4: Enhance PortfolioBacktester.run() signature**

Change the `run()` method signature (line 64) to accept `signal_cache`:

```python
def run(
    self,
    market_data: dict[str, pd.DataFrame],
    screener_results: dict[date, list[tuple[str, float, str]]],
    signal_cache: StrategySignalCache | None = None,  # NEW
) -> PortfolioBacktestResult:
```

Add the import at the top of the file (after existing imports):

```python
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from autotrade.core.strategy_signal_cache import StrategySignalCache
```

Actually, to avoid circular imports, use a lazy import or just import normally since strategy_signal_cache doesn't import from portfolio_backtester:

In the imports section (around line 10), add:

```python
from autotrade.core.strategy_signal_cache import StrategySignalCache
```

Change the type hint to use `Optional`:

```python
def run(
    self,
    market_data: dict[str, pd.DataFrame],
    screener_results: dict[date, list[tuple[str, float, str]]],
    signal_cache: "StrategySignalCache | None" = None,
) -> PortfolioBacktestResult:
```

- [ ] **Step 5: Enhance morning SELL logic**

In the daily loop (around lines 116-136), insert strategy sell check before ExitManager. Find the block that starts with:

```python
            # --- Morning: check exits (unlocked positions) ---
            prev_screener = screener_results.get(prev_date, []) if prev_date else []
            for symbol in list(account.positions.keys()):
                pos = account.positions[symbol]
                # T+1 lock check
                if (self.config.allow_t_plus_1 and pos.locked_until
                        and today <= pos.locked_until):
                    continue

                price = opens.get(symbol)
                if price is None:
                    continue

                # Update highest close
                if price > pos.highest_close_since_entry:
                    pos.highest_close_since_entry = price

                triggers = self.exit_manager.check(
                    pos, price, today, prev_screener, prev_date or today,
                )
                if triggers:
                    self._execute_sell(account, pos, price, today, triggers)
```

Replace with (inserting strategy sell check + trigger recording):

```python
            # --- Morning: check exits (unlocked positions) ---
            prev_screener = screener_results.get(prev_date, []) if prev_date else []
            for symbol in list(account.positions.keys()):
                pos = account.positions[symbol]
                # T+1 lock check
                if (self.config.allow_t_plus_1 and pos.locked_until
                        and today <= pos.locked_until):
                    continue

                price = opens.get(symbol)
                if price is None:
                    continue

                # Update highest close
                if price > pos.highest_close_since_entry:
                    pos.highest_close_since_entry = price

                # --- NEW: Check strategy SELL signals first ---
                strategy_sold = False
                if signal_cache is not None:
                    if signal_cache.has_sell(symbol, today):
                        self._execute_sell(
                            account, pos, price, today, ["strategy_sell"],
                        )
                        strategy_sold = True

                if strategy_sold:
                    continue  # already sold, skip ExitManager

                # --- Existing: ExitManager fallback ---
                triggers = self.exit_manager.check(
                    pos, price, today, prev_screener, prev_date or today,
                )
                if triggers:
                    self._execute_sell(account, pos, price, today, triggers)
```

- [ ] **Step 6: Enhance evening BUY logic**

In the daily loop (around lines 145-159), insert strategy BUY filter. Find this block:

```python
            # --- Evening: plan buys for next day ---
            if max_positions > 0:
                slots = max_positions - len(account.positions)
                if slots > 0:
                    held = set(account.positions.keys())
                    available = [
                        (s, sc, t) for s, sc, t in today_candidates
                        if s not in held
                    ][:self.config.top_n_candidates]

                    picks = available[:slots]
                    if picks:
                        pending_buys = self._plan_buys(
                            picks, account.cash, opens,
                        )
```

Replace with:

```python
            # --- Evening: plan buys for next day ---
            if max_positions > 0:
                slots = max_positions - len(account.positions)
                if slots > 0:
                    held = set(account.positions.keys())
                    available = [
                        (s, sc, t) for s, sc, t in today_candidates
                        if s not in held
                    ][:self.config.top_n_candidates]

                    # --- NEW: Filter to strategy-confirmed candidates ---
                    if signal_cache is not None:
                        window = self.config.strategy_buy_window
                        available = [
                            (s, sc, t) for s, sc, t in available
                            if signal_cache.has_buy(s, today, window=window)
                        ]

                    picks = available[:slots]
                    if picks:
                        pending_buys = self._plan_buys(
                            picks, account.cash, opens,
                        )
```

- [ ] **Step 7: Update _execute_buy to record trigger**

Find `_execute_buy` method (around lines 204-247). The `PortfolioTrade` is created in `_execute_sell`, but for buys we need to record the trigger. The buy trigger info needs to be stored for later use when the position is sold. The simplest approach: store the trigger on the `PortfolioPosition`.

First add a `trigger` field to `PortfolioPosition` in `account.py` (lines 9-17):

```python
@dataclass
class PortfolioPosition:
    """A single holding in the portfolio."""
    symbol: str
    entry_date: date
    entry_price: float
    quantity: int
    highest_close_since_entry: float
    locked_until: Optional[date] = None  # T+1: cannot sell before this date
    entry_trigger: str = ""              # NEW: how this position was entered
```

Then in `_execute_buy`, pass the trigger. Modify the position creation (around line 239-247):

```python
        # Determine entry trigger
        entry_trigger = "strategy_buy" if signal_cache is not None else "screener"

        position = PortfolioPosition(
            symbol=buy.symbol,
            entry_date=today,
            entry_price=fill_price,
            quantity=quantity,
            highest_close_since_entry=fill_price,
            locked_until=locked_until,
            entry_trigger=entry_trigger,
        )
```

Wait — `_execute_buy` doesn't have access to `signal_cache`. Let me adjust: we need a simpler approach. Let's pass the trigger info through the `PendingBuy` dataclass.

Add `trigger` to `PendingBuy` in `account.py` (lines 43-46):

```python
@dataclass
class PendingBuy:
    """A buy order planned for the next trading day."""
    symbol: str
    quantity: int
    trigger: str = ""  # NEW: "strategy_buy" or "screener"
```

Then in `_execute_buy`, use `buy.trigger`:

```python
        position = PortfolioPosition(
            symbol=buy.symbol,
            entry_date=today,
            entry_price=fill_price,
            quantity=quantity,
            highest_close_since_entry=fill_price,
            locked_until=locked_until,
            entry_trigger=buy.trigger,
        )
```

And in `_execute_sell`, pass `pos.entry_trigger` to the `PortfolioTrade`:

```python
        trade = PortfolioTrade(
            symbol=position.symbol,
            buy_date=position.entry_date,
            sell_date=today,
            buy_price=position.entry_price,
            sell_price=fill_price,
            quantity=quantity,
            pnl=round(pnl, 2),
            pnl_pct=round(pnl_pct, 4),
            trigger=triggers[0] if triggers else pos.entry_trigger,
        )
```

And in `_plan_buys`, set the trigger on PendingBuy objects. Modify `_plan_buys` (around lines 279-305) — add `trigger` parameter or determine from context. Since `_plan_buys` is called from `run()` where we know whether `signal_cache` is present, let's pass it:

Change `_plan_buys` signature:

```python
    def _plan_buys(
        self,
        picks: list[tuple[str, float, str]],
        cash: float,
        opens: dict[str, float],
        trigger: str = "screener",  # NEW
    ) -> list[PendingBuy]:
```

And in the PendingBuy creation (line 303):

```python
            if qty > 0:
                pending.append(PendingBuy(symbol=symbol, quantity=qty, trigger=trigger))
```

Then in `run()`, when calling `_plan_buys`:

```python
                        buy_trigger = "strategy_buy" if signal_cache is not None else "screener"
                        pending_buys = self._plan_buys(
                            picks, account.cash, opens, trigger=buy_trigger,
                        )
```

And in the force-close at end (line 164-171), pass "end_of_period":

```python
                self._execute_sell(account, pos, price, trading_dates[-1],
                                   ["end_of_period"])
```

This already works since `_execute_sell` receives `triggers` list.

- [ ] **Step 8: Run unit tests**

Run: `pytest tests/unit/test_portfolio_backtester_strategy.py -v --tb=short`
Expected: All tests PASS.

Run: `pytest tests/unit/test_portfolio_backtester.py -v --tb=short`
Expected: All existing tests still PASS (backward compat).

- [ ] **Step 9: Commit**

```bash
git add autotrade/core/portfolio_backtester.py autotrade/core/account.py tests/unit/test_portfolio_backtester_strategy.py
git commit -m "feat: add strategy-driven buy/sell logic to PortfolioBacktester"
```

---

### Task 4: Integrate strategy into engine.run_portfolio_backtest()

**Files:**
- Modify: `autotrade/core/engine.py:527-739`

- [ ] **Step 1: Add strategy params to run_portfolio_backtest()**

Open `autotrade/core/engine.py`. Modify the function signature around lines 527-535:

```python
def run_portfolio_backtest(
    screener_name: str = "momentum_screener",
    start: Optional[date] = None,
    end: Optional[date] = None,
    symbols: str | list[str] = "all",
    datasource_name: str = FAILOVER_NAME,
    screener_params: dict[str, Any] | None = None,
    strategy_name: str | None = None,          # NEW
    strategy_params: dict[str, Any] | None = None,  # NEW
    strategy_buy_window: int = 1,              # NEW
    reporter_names: tuple[str, ...] = ("console",),
) -> dict[str, Any]:
```

Update the docstring to mention new params:

```python
    """组合级回测: 单账户多持仓 + Screener 每日选股 + 统一出场。

    流程:
      1. 加载配置 (config/backtest/portfolio.yaml)
      2. 加载全市场 OHLCV 数据
      3. 预计算 Screener 每日候选
      4. (NEW) 可选: 构建策略信号缓存
      5. 运行 PortfolioBacktester 逐日模拟
      6. 输出报告

    Args:
        screener_name: 选股筛选器名称。
        start/end: 回测区间，None 则从配置读取。
        symbols: "all" 用全市场，或代码列表。
        screener_params: Screener 参数覆盖。
        strategy_name: 策略名 (如 "turtle")。None = 纯 Screener 模式。
        strategy_params: 策略参数覆盖。
        strategy_buy_window: 策略 BUY 信号匹配窗口 (天)。
        reporter_names: 报告输出方式。

    Returns:
        汇总字典。
    """
```

- [ ] **Step 2: Build StrategySignalCache after AI filter step**

Find the AI filter block (around lines 613-650). After it (before "构建回测配置"), add strategy cache construction. Insert after line 650 (`logger.info("AI 过滤器已禁用")`):

```python
    # ---- 3c. 构建策略信号缓存 (NEW) ----
    signal_cache = None
    if strategy_name:
        from autotrade.core.strategy_signal_cache import StrategySignalCache

        strategy_cls = get_strategy(strategy_name)
        if strategy_cls is None:
            logger.error("策略 '%s' 未注册", strategy_name)
            return {"error": f"Strategy '{strategy_name}' not found"}

        sp = strategy_params
        if sp is None:
            # Try loading from YAML config
            sp = get_strategy_params(strategy_name).get("params", {}) or {}
        strategy = _instantiate_strategy(strategy_cls, sp)

        logger.info("构建策略信号缓存 (策略=%s, 股票数=%d)...",
                    strategy_name, len(market_data))
        try:
            signal_cache = StrategySignalCache(strategy, market_data)
            logger.info("策略信号缓存构建完成: %d 只股票有信号", len(signal_cache))
        except Exception as e:
            logger.error("构建策略信号缓存失败: %s", e)
            return {"error": f"Strategy signal cache build failed: {e}"}
```

- [ ] **Step 3: Pass signal_cache + strategy config to backtester**

Find where `PortfolioBacktestConfig` is constructed (around lines 656-671). Add strategy fields:

After the line:
```python
    bt_config = PortfolioBacktestConfig(
        start_date=start,
        end_date=end,
        ...
    )
```

Add the three new fields before the closing `)`:

```python
    bt_config = PortfolioBacktestConfig(
        start_date=start,  # type: ignore[arg-type]
        end_date=end,  # type: ignore[arg-type]
        initial_capital=float(cfg.get("initial_capital", 1_000_000)),
        cash_buffer=float(cfg.get("cash_buffer", 0.05)),
        top_n_candidates=top_n,
        fill_price=str(cfg.get("fill_price", "next_open")),
        commission_rate=float(cfg.get("commission_rate", 0.0003)),
        stamp_duty_rate=float(cfg.get("stamp_duty_rate", 0.001)),
        slippage=float(cfg.get("slippage", 0.001)),
        min_commission=float(cfg.get("min_commission", 5.0)),
        lot_size=int(cfg.get("lot_size", 100)),
        allow_t_plus_1=bool(cfg.get("allow_t_plus_1", True)),
        exit_rules=exit_rules,
        market_regime=market_regime_cfg,
        strategy_name=strategy_name,           # NEW
        strategy_params=strategy_params,       # NEW
        strategy_buy_window=strategy_buy_window,  # NEW
    )
```

- [ ] **Step 4: Pass signal_cache to backtester.run()**

Change the `backtester.run()` call (around line 674):

```python
    result = backtester.run(market_data, selection, signal_cache=signal_cache)
```

- [ ] **Step 5: Verify existing integration test still passes**

Run: `pytest tests/integration/test_portfolio_backtest.py::test_portfolio_backtest_small_scale -v --tb=short`
Expected: PASS (no strategy → backward compat).

- [ ] **Step 6: Commit**

```bash
git add autotrade/core/engine.py
git commit -m "feat: integrate strategy signal cache into run_portfolio_backtest"
```

---

### Task 5: Enhance CLI with strategy options

**Files:**
- Modify: `autotrade/triggers/cli.py:198-239`

- [ ] **Step 1: Add CLI options to portfolio-backtest command**

Open `autotrade/triggers/cli.py`. Modify the `portfolio_backtest_cmd` function decorators (lines 198-207) to add strategy options:

```python
@cli.command("portfolio-backtest")
@click.option("--screener", "-s", default="momentum_screener",
              help="选股筛选器名称")
@click.option("--strategy", default=None,
              help="策略名 (如 turtle, ma_cross)。不指定则纯 Screener 模式")
@click.option("--strategy-params", default=None,
              help="策略参数 JSON 字符串 (如 '{\"allow_short\": false}')")
@click.option("--start", default=None, help="开始日期 YYYY-MM-DD（默认从配置读取）")
@click.option("--end", default=None, help="结束日期 YYYY-MM-DD（默认从配置读取）")
@click.option("--symbols", default="all", help="股票代码列表，'all' 表示全市场")
@click.option("--reporter", "-r", "reporters", multiple=True,
              default=["console", "plot"],
              help="报告输出方式 (console, csv, plot)")
@click.pass_context
def portfolio_backtest_cmd(ctx, screener, strategy, strategy_params, start, end,
                           symbols, reporters):
    """组合级回测: 单账户多持仓 + 每日选股 + 统一出场。

    基于 config/backtest/portfolio.yaml 配置，从全市场筛选候选股，
    按信号强度分仓买入，统一出场规则管理风险。

    \b
    策略驱动模式示例:
      autotrade portfolio-backtest --strategy turtle
      autotrade portfolio-backtest --strategy turtle --strategy-params '{"allow_short": false}'
    """
```

- [ ] **Step 2: Parse strategy_params JSON and pass to engine**

Modify the function body (lines 214-239). Replace with:

```python
    from autotrade.core.engine import run_portfolio_backtest

    start_date = _parse_date(start)
    end_date = _parse_date(end)

    # Parse strategy params JSON if provided
    sp = None
    if strategy_params:
        try:
            sp = json.loads(strategy_params)
        except json.JSONDecodeError as e:
            click.echo(f"策略参数 JSON 解析失败: {e}", err=True)
            return

    click.echo(f"\n{'='*60}")
    click.echo(f"  组合回测")
    click.echo(f"  筛选器: {screener}")
    if strategy:
        click.echo(f"  策略:   {strategy}")
        if sp:
            click.echo(f"  策略参数: {sp}")
    click.echo(f"  区间: {start or '从配置读取'} → {end or '从配置读取'}")
    click.echo(f"  股票池: {symbols}")
    click.echo(f"{'='*60}\n")

    result = run_portfolio_backtest(
        screener_name=screener,
        start=start_date,
        end=end_date,
        symbols=symbols,
        strategy_name=strategy,
        strategy_params=sp,
        reporter_names=tuple(reporters),
    )

    if "error" in result:
        click.echo(f"\n  ✗ 回测失败: {result['error']}", err=True)
    else:
        click.echo(f"\n  ✓ 回测完成")
        if "output_dir" in result:
            click.echo(f"  结果目录: {result['output_dir']}")
```

- [ ] **Step 3: Verify CLI help works**

Run: `python -m autotrade.triggers.cli portfolio-backtest --help`
Expected: Shows new `--strategy` and `--strategy-params` options.

- [ ] **Step 4: Commit**

```bash
git add autotrade/triggers/cli.py
git commit -m "feat: add --strategy and --strategy-params CLI options to portfolio-backtest"
```

---

### Task 6: Enhance Reporters

**Files:**
- Modify: `autotrade/reporters/plot_reporter.py` (render_portfolio method)

- [ ] **Step 1: Add trigger breakdown to plot reporter metrics**

Open `autotrade/reporters/plot_reporter.py`. In the `render_portfolio` method (lines 87-165), after the metrics summary (line 165), add trigger statistics. After the `print(f"  Total Trades:     {metrics.get('total_trades', 0)}")` line, add:

```python
            # Trigger breakdown (NEW)
            if hasattr(result, 'trades') and result.trades:
                from collections import Counter
                trigger_counts = Counter(t.trigger for t in result.trades if t.trigger)
                if trigger_counts:
                    print("\n  ── Exit Triggers ──")
                    for trigger, count in trigger_counts.most_common():
                        print(f"  {trigger}:  {count}")
```

- [ ] **Step 2: Add trigger column to trades CSV export in engine.py**

The trades CSV is exported in `run_portfolio_backtest()` (engine.py lines 710-724). Add `trigger` to the export:

Find:
```python
    if result.trades:
        trades_df = pd.DataFrame([
            {
                "symbol": t.symbol,
                "buy_date": t.buy_date,
                "sell_date": t.sell_date,
                "buy_price": t.buy_price,
                "sell_price": t.sell_price,
                "quantity": t.quantity,
                "pnl": t.pnl,
                "pnl_pct": t.pnl_pct,
            }
            for t in result.trades
        ])
```

Add `"trigger": t.trigger`:

```python
    if result.trades:
        trades_df = pd.DataFrame([
            {
                "symbol": t.symbol,
                "buy_date": t.buy_date,
                "sell_date": t.sell_date,
                "buy_price": t.buy_price,
                "sell_price": t.sell_price,
                "quantity": t.quantity,
                "pnl": t.pnl,
                "pnl_pct": t.pnl_pct,
                "trigger": t.trigger,
            }
            for t in result.trades
        ])
```

- [ ] **Step 3: Verify existing tests still pass**

Run: `pytest tests/unit/ -v --tb=short`
Expected: All existing unit tests PASS.

- [ ] **Step 4: Commit**

```bash
git add autotrade/reporters/plot_reporter.py autotrade/core/engine.py
git commit -m "feat: add trigger breakdown to plot reporter and CSV export"
```

---

### Task 7: Update portfolio config YAML

**Files:**
- Modify: `config/backtest/portfolio.yaml`

- [ ] **Step 1: Add strategy fields to config**

Open `config/backtest/portfolio.yaml`. After the `ai_filter` section (end of file), add:

```yaml
  # 策略驱动 (可选 — 不配置则使用纯 Screener 模式)
  strategy: ""                    # 策略名，如 "turtle", "ma_cross"
  strategy_params: {}            # 策略参数覆盖 (留空使用 YAML 默认值)
  strategy_buy_window: 1         # BUY 信号匹配窗口 (±N 天)
```

- [ ] **Step 2: Commit**

```bash
git add config/backtest/portfolio.yaml
git commit -m "feat: add strategy fields to portfolio backtest config"
```

---

### Task 8: Integration test for strategy-driven mode

**Files:**
- Modify: `tests/integration/test_portfolio_backtest.py`

- [ ] **Step 1: Add strategy-driven integration test**

Open `tests/integration/test_portfolio_backtest.py`. Add a new test function after the existing one:

```python
def test_portfolio_backtest_with_strategy():
    """Run a 1-month portfolio backtest with Turtle strategy driving signals."""
    init_registry()

    result = run_portfolio_backtest(
        screener_name="momentum_screener",
        strategy_name="turtle",
        strategy_params={
            "use_system1": True,
            "use_system2": False,
            "allow_long": True,
            "allow_short": False,
        },
        start=date(2025, 1, 2),
        end=date(2025, 1, 31),
        symbols=["000001", "000002", "600000", "600036", "601318"],
        reporter_names=(),
    )

    # Should not error
    assert "error" not in result, f"Strategy backtest failed: {result.get('error')}"

    # Should have metrics
    metrics = result.get("metrics", {})
    assert "total_return_pct" in metrics
    assert "sharpe_ratio" in metrics

    # Trade count should be non-negative
    assert result.get("trade_count", -1) >= 0

    print(f"Strategy integration test passed: {metrics}")
```

- [ ] **Step 2: Run integration tests**

Run: `pytest tests/integration/test_portfolio_backtest.py -v --tb=short`
Expected: Both tests PASS (screener-only + strategy-driven).

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_portfolio_backtest.py
git commit -m "test: add strategy-driven portfolio backtest integration test"
```

---

### Task 9: Final verification — run full test suite

- [ ] **Step 1: Run all unit tests**

```bash
pytest tests/unit/ -v --tb=short
```
Expected: All tests PASS.

- [ ] **Step 2: Run all integration tests**

```bash
pytest tests/integration/ -v --tb=short
```
Expected: All tests PASS.

- [ ] **Step 3: Final commit if any cleanups needed**

```bash
git status
```

---

## Summary of Changes

| # | File | Lines Changed |
|---|---|---|
| 1 | `autotrade/core/account.py` | +3 fields (trigger on PortfolioTrade, entry_trigger on PortfolioPosition, trigger on PendingBuy) |
| 2 | `autotrade/core/strategy_signal_cache.py` | ~130 lines NEW |
| 3 | `autotrade/core/portfolio_backtester.py` | +3 config fields, ~30 lines new logic in run(), _execute_buy/_execute_sell/_plan_buys changes |
| 4 | `autotrade/core/engine.py` | +3 params, ~20 lines cache construction |
| 5 | `autotrade/triggers/cli.py` | +2 options, JSON parsing |
| 6 | `autotrade/reporters/plot_reporter.py` | +6 lines trigger stats |
| 7 | `config/backtest/portfolio.yaml` | +3 lines |
| 8 | `tests/unit/test_strategy_signal_cache.py` | ~180 lines NEW |
| 9 | `tests/unit/test_portfolio_backtester_strategy.py` | ~200 lines NEW |
| 10 | `tests/integration/test_portfolio_backtest.py` | +25 lines |
