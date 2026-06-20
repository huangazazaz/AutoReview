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


@pytest.fixture
def bottom_divergence_df():
    """构造底背离走势：手动设定价格与 MACD 以精确测试检测逻辑。

    60 天数据，前 30 天已经过，后 30 天为检测窗口。
    在第 50 天构造底背离：价格新低但 MACD 高于前低。
    """
    np.random.seed(123)
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    # 基础随机价格
    close = 10 + np.cumsum(np.random.randn(60) * 0.15)
    df = pd.DataFrame({
        "close": close,
        "open": close + np.random.randn(60) * 0.08,
        "high": close + np.abs(np.random.randn(60)) * 0.12,
        "low": close - np.abs(np.random.randn(60)) * 0.12,
        "volume": np.random.randint(1e6, 1e7, 60),
    }, index=dates)

    # 直接注入 MACD 列，精确控制背离条件
    macd_vals = np.linspace(-0.8, 0.3, 60) + np.random.randn(60) * 0.02
    # 第 49 天：构造底背离
    #   - 在 [20, 49] 窗口内，前低在 day 30（close=8.0, macd=-0.6）
    #   - day 49：close=7.5（新低）, macd=-0.2（高于 -0.6）
    df.loc[dates[30], "close"] = 8.0
    macd_vals[30] = -0.6
    df.loc[dates[49], "close"] = 7.5
    macd_vals[49] = -0.2

    df["ind_macd_macd"] = macd_vals
    df["ind_macd_signal"] = macd_vals - 0.1
    df["ind_macd_histogram"] = 0.1
    return df


@pytest.fixture
def top_divergence_df():
    """构造顶背离走势：手动设定价格与 MACD 以精确测试检测逻辑。

    60 天数据，在第 50 天构造顶背离：价格新高但 MACD 低于前高。
    """
    np.random.seed(456)
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    close = 10 + np.cumsum(np.random.randn(60) * 0.15)
    df = pd.DataFrame({
        "close": close,
        "open": close + np.random.randn(60) * 0.08,
        "high": close + np.abs(np.random.randn(60)) * 0.12,
        "low": close - np.abs(np.random.randn(60)) * 0.12,
        "volume": np.random.randint(1e6, 1e7, 60),
    }, index=dates)

    macd_vals = np.linspace(0.3, -0.5, 60) + np.random.randn(60) * 0.02
    # 第 49 天：构造顶背离
    #   - 在 [20, 49] 窗口内，前高在 day 30（close=12.0, macd=0.2）
    #   - day 49：close=13.0（新高）, macd=0.05（低于 0.2）
    df.loc[dates[30], "close"] = 12.0
    macd_vals[30] = 0.2
    df.loc[dates[49], "close"] = 13.0
    macd_vals[49] = 0.05

    df["ind_macd_macd"] = macd_vals
    df["ind_macd_signal"] = macd_vals - 0.1
    df["ind_macd_histogram"] = 0.1
    return df


class TestStrategies:
    def test_ma_cross_generates_signals(self, vshape_df):
        strategy = MACrossStrategy(fast=5, slow=20)
        signals = strategy.generate_signals(vshape_df)
        assert len(signals) > 0
        # 应有 BUY 或 SELL
        actions = [s.action for s in signals]
        assert "BUY" in actions or "SELL" in actions

    def test_macd_divergence_returns_list(self, vshape_df):
        """基本冒烟测试：确保策略返回 list 类型。"""
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


class TestMACDDivergence:
    """MACD 背离策略专项测试。"""

    def test_custom_macd_params(self, bottom_divergence_df):
        """使用自定义 MACD 参数应能正常工作。"""
        macd_ind = MACD(fast=6, slow=13, signal=5)
        df = macd_ind.compute(bottom_divergence_df)
        strategy = MACDDivergenceStrategy(
            fast=6, slow=13, signal=5, lookback=30,
            buy_strength=0.5, sell_strength=0.9,
        )
        signals = strategy.generate_signals(df)
        assert isinstance(signals, list)
        # 验证指标列存在
        assert "ind_macd_macd" in df.columns

    def test_custom_strength_values(self, bottom_divergence_df):
        """信号强度应使用配置值。"""
        macd_ind = MACD()
        df = macd_ind.compute(bottom_divergence_df)
        strategy = MACDDivergenceStrategy(
            lookback=30, buy_strength=0.5, sell_strength=0.9,
        )
        signals = strategy.generate_signals(df)
        for s in signals:
            if s.action == "BUY":
                assert s.strength == 0.5, f"Expected buy_strength=0.5, got {s.strength}"
            elif s.action == "SELL":
                assert s.strength == 0.9, f"Expected sell_strength=0.9, got {s.strength}"

    def test_bottom_divergence_detected(self, bottom_divergence_df):
        """底背离走势中应检测到 BUY 信号。"""
        macd_ind = MACD()
        df = macd_ind.compute(bottom_divergence_df)
        strategy = MACDDivergenceStrategy(lookback=30)
        signals = strategy.generate_signals(df)

        buy_signals = [s for s in signals if s.action == "BUY"]
        assert len(buy_signals) > 0, (
            f"Expected at least one BUY signal for bottom divergence, "
            f"got {len(signals)} total signals: "
            f"{[(s.action, s.reason, s.date) for s in signals]}"
        )
        for s in buy_signals:
            assert s.reason == "MACD底背离"
            assert 0 < s.strength <= 1.0

    def test_top_divergence_detected(self, top_divergence_df):
        """顶背离走势中应检测到 SELL 信号。"""
        macd_ind = MACD()
        df = macd_ind.compute(top_divergence_df)
        strategy = MACDDivergenceStrategy(lookback=30)
        signals = strategy.generate_signals(df)

        sell_signals = [s for s in signals if s.action == "SELL"]
        assert len(sell_signals) > 0, (
            f"Expected at least one SELL signal for top divergence, "
            f"got {len(signals)} total signals: "
            f"{[(s.action, s.reason, s.date) for s in signals]}"
        )
        for s in sell_signals:
            assert s.reason == "MACD顶背离"
            assert 0 < s.strength <= 1.0

    def test_no_signals_on_empty_df(self):
        """空 DataFrame 不应抛异常。"""
        df = pd.DataFrame()
        strategy = MACDDivergenceStrategy()
        signals = strategy.generate_signals(df)
        assert signals == []

    def test_no_signals_without_macd_column(self, vshape_df):
        """未计算 MACD 指标的 DataFrame 应返回空信号。"""
        strategy = MACDDivergenceStrategy()
        signals = strategy.generate_signals(vshape_df)
        assert signals == []

    def test_default_constructor_works(self, vshape_df):
        """默认参数构造策略应正常工作（向后兼容）。"""
        macd_ind = MACD()
        df = macd_ind.compute(vshape_df)
        strategy = MACDDivergenceStrategy()  # 全部默认值
        assert strategy.lookback == 30
        assert strategy.buy_strength == 0.8
        assert strategy.sell_strength == 0.8
        assert strategy.fast == 12
        assert strategy.slow == 26
        assert strategy.signal == 9
        signals = strategy.generate_signals(df)
        assert isinstance(signals, list)
