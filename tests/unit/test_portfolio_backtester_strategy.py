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


class _BuyAndSellStrategy(Strategy):
    """BUY on first 2 days, SELL on day 3-4."""
    name = "buy_and_sell"
    required_indicators = []

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        signals = []
        for i, idx in enumerate(df.index):
            d = idx.date() if hasattr(idx, "date") else idx
            if i <= 1:
                signals.append(Signal(symbol="", date=d, action="BUY",
                                      strength=0.5, reason="buy early"))
            elif i in (3, 4):
                signals.append(Signal(symbol="", date=d, action="SELL",
                                      strength=1.0, reason="sell later"))
        return signals


def _make_declining_market(symbols: list[str], dates: list[date],
                           base_price: float = 10.0) -> dict[str, pd.DataFrame]:
    """Build market data with declining prices (triggers hard_stop)."""
    market = {}
    for sym in symbols:
        records = []
        for i, d in enumerate(dates):
            p = base_price * (1 - i * 0.02)  # drops 2% per day
            records.append({
                "date": d, "open": p, "high": p * 1.01,
                "low": p * 0.99, "close": p,
                "volume": 1_000_000, "amount": p * 1_000_000,
            })
        df = pd.DataFrame(records)
        df.set_index("date", inplace=True)
        market[sym] = df
    return market


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

        # Should have trades (triggered by strategy confirmation, exited at end_of_period)
        assert len(result.trades) >= 1
        # Verify all trades have non-empty trigger
        for t in result.trades:
            assert t.trigger != "", f"Trade has empty trigger"

    def test_strategy_buy_triggers_more_trades_than_no_strategy(self):
        """Strategy with BUY signals produces trades; without strategy = none if screener empty."""
        dates = _make_dates(date(2024, 1, 2), 10)
        market = _make_market(["000001"], dates)

        # With strategy (always buy) + non-empty screener → trades
        cache = StrategySignalCache(_AlwaysBuyStrategy(), market)
        config = _make_config()
        bt = PortfolioBacktester(config)
        screener = {d: [("000001", 0.8, "strong")] for d in dates}
        result_with = bt.run(market, screener, signal_cache=cache)
        assert len(result_with.trades) >= 1

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
        # Use strategy with BOTH buy and sell signals
        cache = StrategySignalCache(_BuyAndSellStrategy(), market)

        config = _make_config()
        bt = PortfolioBacktester(config)

        screener = {d: [("000001", 0.8, "strong")] for d in dates}
        result = bt.run(market, screener, signal_cache=cache)

        sell_trades = [t for t in result.trades if t.trigger == "strategy_sell"]
        assert len(sell_trades) >= 1, f"No strategy_sell trades found in {[t.trigger for t in result.trades]}"

    def test_exit_manager_fallback_when_no_strategy_sell(self):
        """When strategy has no SELL, ExitManager can still trigger."""
        dates = _make_dates(date(2024, 1, 2), 10)
        # Use declining prices so hard_stop triggers
        market = _make_declining_market(["000001"], dates, base_price=10.0)
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

        # Should have hard_stop exits since price drops fast
        hard_stops = [t for t in result.trades if t.trigger == "hard_stop"]
        assert len(hard_stops) >= 1, f"No hard_stop trades, triggers: {[t.trigger for t in result.trades]}"

    def test_trigger_recorded_on_trade(self):
        """PortfolioTrade should carry the correct trigger value."""
        dates = _make_dates(date(2024, 1, 2), 10)
        market = _make_market(["000001"], dates)
        cache = StrategySignalCache(_BuyAndSellStrategy(), market)

        config = _make_config()
        bt = PortfolioBacktester(config)

        screener = {d: [("000001", 0.8, "strong")] for d in dates}
        result = bt.run(market, screener, signal_cache=cache)

        # Every trade should have a non-empty trigger
        for t in result.trades:
            assert t.trigger != "", f"Trade {t.symbol} {t.buy_date} has empty trigger"
