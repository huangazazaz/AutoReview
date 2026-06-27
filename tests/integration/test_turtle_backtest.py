"""Integration test: Turtle strategy + Backtester end-to-end."""
import pandas as pd
import numpy as np
from datetime import date, timedelta

from autotrade.core.models import Bar, Signal, BacktestConfig
from autotrade.core.backtester import Backtester
from autotrade.strategies.turtle import TurtleTraderStrategy


def _generate_market_data(symbol="000001", n_days=200, trend="up"):
    """Generate realistic daily bars with a clear trend."""
    np.random.seed(123)
    dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(n_days)]

    if trend == "up":
        drift = 0.001
    elif trend == "down":
        drift = -0.001
    else:
        drift = 0.0

    returns = np.random.normal(drift, 0.02, n_days)
    prices = 10.0 * np.exp(np.cumsum(returns))

    bars = []
    for i, (d, close) in enumerate(zip(dates, prices)):
        daily_range = close * np.random.uniform(0.01, 0.03)
        bars.append(Bar(
            symbol=symbol, date=d,
            open=float(close * (1 + np.random.uniform(-0.005, 0.005))),
            high=float(close + daily_range / 2),
            low=float(close - daily_range / 2),
            close=float(close),
            volume=float(np.random.randint(50000, 200000)),
            amount=float(close * np.random.randint(50000, 200000)),
        ))

    # Build DataFrame for strategy (with ATR pre-computed)
    df = pd.DataFrame({
        "high": [b.high for b in bars],
        "low": [b.low for b in bars],
        "close": [b.close for b in bars],
        "volume": [b.volume for b in bars],
    }, index=[b.date for b in bars])

    import pandas_ta as ta
    df["ind_atr_20"] = ta.atr(df["high"], df["low"], df["close"], length=20)

    return bars, df


class TestTurtleIntegration:
    def test_turtle_long_backtest_on_uptrend(self):
        """Turtle strategy on uptrend should produce BUY signals and trades."""
        bars, df = _generate_market_data(n_days=200, trend="up")

        strategy = TurtleTraderStrategy(
            use_system1=True, use_system2=False,
            allow_long=True, allow_short=False,
            max_units=4,
        )
        signals = strategy.generate_signals(df)
        for s in signals:
            s.symbol = "000001"

        cfg = BacktestConfig(
            initial_capital=100_000,
            fill_price="next_open",
            allow_short=False,
            position_sizing="strength",
        )
        bt = Backtester(cfg)
        result = bt.run(signals, bars)

        assert len(result.trades) > 0, "Expected at least some trades"
        assert result.equity_curve is not None
        assert len(result.equity_curve) > 1
        assert "total_return_pct" in result.metrics
        assert "sharpe_ratio" in result.metrics
        print(f"Long-only: return={result.metrics['total_return_pct']:.2f}%, "
              f"sharpe={result.metrics['sharpe_ratio']:.4f}, "
              f"trades={result.metrics['total_trades']}")

    def test_turtle_bidirectional_backtest(self):
        """Turtle strategy with long+short on uptrend market."""
        bars, df = _generate_market_data(n_days=200, trend="up")

        strategy = TurtleTraderStrategy(
            use_system1=True, use_system2=False,
            allow_long=True, allow_short=True,
            max_units=4,
        )
        signals = strategy.generate_signals(df)
        for s in signals:
            s.symbol = "000001"

        cfg = BacktestConfig(
            initial_capital=100_000,
            fill_price="next_open",
            allow_short=True,
            short_margin_ratio=1.0,
            position_sizing="strength",
        )
        bt = Backtester(cfg)
        result = bt.run(signals, bars)

        assert len(result.trades) > 0
        actions = set(t.action for t in result.trades)
        assert "BUY" in actions, "Expected BUY trades"
        print(f"Bidirectional: return={result.metrics['total_return_pct']:.2f}%, "
              f"sharpe={result.metrics['sharpe_ratio']:.4f}, "
              f"trades={result.metrics['total_trades']}")

    def test_turtle_full_dual_system(self):
        """Both System 1 and System 2 enabled."""
        bars, df = _generate_market_data(n_days=300, trend="up")

        strategy = TurtleTraderStrategy(
            use_system1=True, use_system2=True,
        )
        signals = strategy.generate_signals(df)
        for s in signals:
            s.symbol = "000001"

        cfg = BacktestConfig(
            initial_capital=100_000,
            fill_price="next_open",
            position_sizing="strength",
        )
        bt = Backtester(cfg)
        result = bt.run(signals, bars)

        assert len(result.trades) > 0
        buy_signals = [s for s in signals if s.action == "BUY"]
        sys1_buys = sum(1 for s in buy_signals if "sys1" in s.reason.lower())
        sys2_buys = sum(1 for s in buy_signals if "sys2" in s.reason.lower())
        print(f"System1 buys: {sys1_buys}, System2 buys: {sys2_buys}")
        assert sys1_buys + sys2_buys > 0

    def test_turtle_metrics_are_valid(self):
        """All metrics should be in valid ranges."""
        bars, df = _generate_market_data(n_days=200, trend="up")

        strategy = TurtleTraderStrategy(
            use_system1=True, use_system2=False,
        )
        signals = strategy.generate_signals(df)
        for s in signals:
            s.symbol = "000001"

        cfg = BacktestConfig(
            initial_capital=100_000,
            fill_price="next_open",
            position_sizing="strength",
        )
        bt = Backtester(cfg)
        result = bt.run(signals, bars)

        m = result.metrics
        assert isinstance(m["total_return_pct"], (int, float))
        assert 0 <= m["win_rate"] <= 100
        assert m["max_drawdown_pct"] <= 0
        assert np.isfinite(m["sharpe_ratio"])
        print(f"Metrics: return={m['total_return_pct']:.2f}%, "
              f"win_rate={m['win_rate']:.1f}%, "
              f"max_dd={m['max_drawdown_pct']:.2f}%, "
              f"sharpe={m['sharpe_ratio']:.4f}")
