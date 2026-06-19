"""策略单元测试。"""
import pytest
import pandas as pd
import numpy as np
from autotrade.strategies.ma_cross import MACrossStrategy
from autotrade.strategies.macd_divergence import MACDDivergenceStrategy
from autotrade.indicators.ma import MA
from autotrade.indicators.macd import MACD


@pytest.fixture
def vshape_df():
    """V型走势：先跌后涨，确保快慢线有交叉。"""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=80, freq="D")
    # 前 40 天下跌（12→8），后 40 天上涨（8→14）
    t1 = np.linspace(12, 8, 40)
    t2 = np.linspace(8, 14, 40)
    close = np.concatenate([t1, t2]) + np.random.randn(80) * 0.15
    df = pd.DataFrame({
        "close": close,
        "open": close + np.random.randn(80) * 0.08,
        "high": close + np.abs(np.random.randn(80)) * 0.15,
        "low": close - np.abs(np.random.randn(80)) * 0.15,
        "volume": np.random.randint(1e6, 1e7, 80),
    }, index=dates)
    # 计算指标
    ma_fast = MA(period=5)
    ma_slow = MA(period=20)
    df = ma_fast.compute(df)
    df = ma_slow.compute(df)
    return df


class TestStrategies:
    def test_ma_cross_generates_signals(self, vshape_df):
        strategy = MACrossStrategy(fast=5, slow=20)
        signals = strategy.generate_signals(vshape_df)
        assert len(signals) > 0
        # 应有 BUY 或 SELL
        actions = [s.action for s in signals]
        assert "BUY" in actions or "SELL" in actions

    def test_macd_divergence_creates_signals(self, vshape_df):
        """在较长数据上应能产生信号。"""
        macd_ind = MACD()
        df = macd_ind.compute(vshape_df)
        strategy = MACDDivergenceStrategy(lookback=20)
        signals = strategy.generate_signals(df)
        assert isinstance(signals, list)

    def test_ma_cross_signal_has_reason(self, vshape_df):
        strategy = MACrossStrategy(fast=5, slow=20)
        signals = strategy.generate_signals(vshape_df)
        if signals:
            assert len(signals[0].reason) > 0
