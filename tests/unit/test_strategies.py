"""策略单元测试。"""
import pytest
import pandas as pd
import numpy as np
from autotrade.strategies.ma_cross import MACrossStrategy
from autotrade.strategies.macd_divergence import MACDDivergenceStrategy
from autotrade.strategies.trend_bb_rsi import TrendBBRSIStrategy
from autotrade.strategies.trend_ma_breakout import TrendMABreakoutStrategy
from autotrade.indicators.ma import MA
from autotrade.indicators.macd import MACD
from autotrade.indicators.rsi import RSI
from autotrade.indicators.bollinger import BollingerBands


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


# ====================================================================
# TrendBBRSIStrategy 测试
# ====================================================================


@pytest.fixture
def trend_bb_rsi_buy_df():
    """构造满足四维共振买入条件的走势。

    80 天数据，前半段震荡，后半段构造上行趋势 + 回调 + 放量 + 动能转正。
    在第 55 天附近满足所有买入条件。
    """
    np.random.seed(99)
    dates = pd.date_range("2024-01-01", periods=80, freq="D")

    # 价格走势：前 30 天横盘（10 附近），中间抬升至 12，末尾小幅回调
    base = np.concatenate([
        np.full(30, 10.0),
        np.linspace(10, 12, 25),
        np.linspace(12, 11.5, 25),
    ])
    noise = np.random.randn(80) * 0.2
    close = base + noise
    close = np.clip(close, 8, 15)

    # 成交量：前 50 天平稳，第 52 天起放量
    volume = np.full(80, 1_000_000.0)
    volume[52:] = 2_000_000.0  # > 1.2× 均量

    # 手工构造 OHLCV
    df = pd.DataFrame({
        "close": close,
        "open": close - np.abs(np.random.randn(80)) * 0.1,
        "high": close + np.abs(np.random.randn(80)) * 0.15,
        "low": close - np.abs(np.random.randn(80)) * 0.15,
        "volume": volume,
    }, index=dates)

    # 计算所需指标
    bb = BollingerBands(period=20, std=2.0)
    rsi = RSI(period=14)
    macd = MACD(fast=12, slow=26, signal=9)
    df = bb.compute(df)
    df = rsi.compute(df)
    df = macd.compute(df)

    # 微调第 55 天使之精确满足买入条件
    idx_55 = dates[54]  # 0-based

    # 确保 close > bb_mid
    bb_mid = df.loc[idx_55, "ind_bb_middle_20"]
    df.loc[idx_55, "close"] = bb_mid * 1.02  # 略高于中轨

    # 确保 RSI 在 30-55 之间
    df.loc[idx_55, "ind_rsi_14"] = 45.0

    # 确保 MACD 柱状图 > 0 且 > 前一日
    df.loc[dates[53], "ind_macd_histogram"] = -0.05  # 前一天为负
    df.loc[idx_55, "ind_macd_histogram"] = 0.15       # 今天转正

    return df


@pytest.fixture
def trend_bb_rsi_sell_df():
    """构造触发卖出条件的走势（超买 + 回撤）。

    在第 45 天买入，第 60 天触发 RSI 超买卖出。
    """
    np.random.seed(77)
    dates = pd.date_range("2024-01-01", periods=80, freq="D")

    # 价格稳步上涨
    base = np.linspace(10, 16, 80)
    noise = np.random.randn(80) * 0.15
    close = base + noise
    close = np.clip(close, 8, 18)

    # 成交量：基底 1M，买入日放量至 2M
    volume = np.full(80, 1_000_000.0)
    volume[34] = 2_000_000.0   # 第 35 天放量

    df = pd.DataFrame({
        "close": close,
        "open": close - np.abs(np.random.randn(80)) * 0.1,
        "high": close + np.abs(np.random.randn(80)) * 0.15,
        "low": close - np.abs(np.random.randn(80)) * 0.15,
        "volume": volume,
    }, index=dates)

    bb = BollingerBands(period=20, std=2.0)
    rsi = RSI(period=14)
    macd = MACD(fast=12, slow=26, signal=9)
    df = bb.compute(df)
    df = rsi.compute(df)
    df = macd.compute(df)

    # 第 35 天：构造买入条件（趋势向上 + RSI 适中 + 放量 + MACD 转正）
    idx_35 = dates[34]
    bb_mid = df.loc[idx_35, "ind_bb_middle_20"]
    df.loc[idx_35, "close"] = bb_mid * 1.02
    df.loc[idx_35, "ind_rsi_14"] = 48.0
    df.loc[dates[33], "ind_macd_histogram"] = -0.03
    df.loc[idx_35, "ind_macd_histogram"] = 0.12

    # 第 60 天：RSI 超买触发卖出
    idx_60 = dates[59]
    df.loc[idx_60, "ind_rsi_14"] = 78.0

    return df


class TestTrendBBRSI:
    """布林带 + RSI + MACD + 量能 多因子策略测试。"""

    def test_buy_signal_generated(self, trend_bb_rsi_buy_df):
        """四维共振条件满足时应产生 BUY 信号。"""
        strategy = TrendBBRSIStrategy(vol_factor=1.2)
        signals = strategy.generate_signals(trend_bb_rsi_buy_df)

        buy_signals = [s for s in signals if s.action == "BUY"]
        assert len(buy_signals) > 0, (
            f"Expected at least one BUY signal, "
            f"got {len(signals)} signals: "
            f"{[(s.action, s.reason) for s in signals]}"
        )
        for s in buy_signals:
            assert s.strength == 1.0
            assert "BB回调买入" in s.reason

    def test_sell_signal_on_rsi_overbought(self, trend_bb_rsi_sell_df):
        """RSI 超买应触发卖出。"""
        strategy = TrendBBRSIStrategy()
        signals = strategy.generate_signals(trend_bb_rsi_sell_df)

        sell_signals = [s for s in signals if s.action == "SELL"]
        assert len(sell_signals) > 0, (
            f"Expected at least one SELL signal, "
            f"got signals: {[(s.action, s.reason) for s in signals]}"
        )
        # 应包含 RSI 超买卖出
        rsi_sells = [s for s in sell_signals if "RSI超买" in s.reason]
        assert len(rsi_sells) > 0, f"Expected RSI overbought SELL, got: {[s.reason for s in sell_signals]}"

    def test_no_signals_on_empty_df(self):
        """空 DataFrame 应返回空列表。"""
        df = pd.DataFrame()
        strategy = TrendBBRSIStrategy()
        signals = strategy.generate_signals(df)
        assert signals == []

    def test_no_signals_without_indicators(self, vshape_df):
        """未计算所需指标的 DataFrame 应返回空信号。"""
        strategy = TrendBBRSIStrategy()
        signals = strategy.generate_signals(vshape_df)
        assert signals == []

    def test_default_constructor_works(self, trend_bb_rsi_buy_df):
        """默认参数构造应正常工作。"""
        strategy = TrendBBRSIStrategy()
        assert strategy.bb_period == 20
        assert strategy.bb_std == 2.0
        assert strategy.rsi_period == 14
        assert strategy.rsi_buy_low == 30
        assert strategy.rsi_buy_high == 55
        assert strategy.rsi_sell == 75
        assert strategy.stop_loss == 0.07
        assert strategy.trailing_stop == 0.10
        assert len(strategy.take_profit_levels) == 2
        assert len(strategy.required_indicators) == 3
        signals = strategy.generate_signals(trend_bb_rsi_buy_df)
        assert isinstance(signals, list)

    def test_custom_params(self, trend_bb_rsi_buy_df):
        """自定义参数应正确设置。"""
        strategy = TrendBBRSIStrategy(
            bb_period=10,
            rsi_period=7,
            rsi_buy_low=25,
            rsi_buy_high=50,
            rsi_sell=70,
            stop_loss=0.05,
            trailing_stop=0.08,
            take_profit_levels=[[0.10, 0.5], [0.20, 0.5]],
        )
        assert strategy.bb_period == 10
        assert strategy.rsi_period == 7
        assert strategy.stop_loss == 0.05
        assert strategy.trailing_stop == 0.08
        assert len(strategy.take_profit_levels) == 2
        signals = strategy.generate_signals(trend_bb_rsi_buy_df)
        assert isinstance(signals, list)

    def test_stop_loss_triggers(self):
        """止损条件应触发全仓卖出。"""
        np.random.seed(42)
        dates = pd.date_range("2024-01-01", periods=60, freq="D")

        # 构造价格：先买入，然后暴跌触发止损
        close = np.concatenate([
            np.linspace(10, 10.5, 25),   # 缓慢上涨（买入）
            np.linspace(10.5, 6.5, 35),  # 暴跌
        ])
        # 成交量：基底 1M，买入日放量至 2M
        volume = np.full(60, 1_000_000.0)
        volume[19] = 2_000_000.0  # 第 20 天放量

        df = pd.DataFrame({
            "close": close,
            "open": close,
            "high": close,
            "low": close,
            "volume": volume,
        }, index=dates)

        bb = BollingerBands(period=20, std=2.0)
        rsi = RSI(period=14)
        macd = MACD(fast=12, slow=26, signal=9)
        df = bb.compute(df)
        df = rsi.compute(df)
        df = macd.compute(df)

        # 第 20 天构造买入（RSI 适中、放量、MACD 转正、趋势向上）
        idx20 = dates[19]
        df.loc[idx20, "ind_rsi_14"] = 45.0
        df.loc[dates[18], "ind_macd_histogram"] = -0.02
        df.loc[idx20, "ind_macd_histogram"] = 0.10
        bb_mid20 = df.loc[idx20, "ind_bb_middle_20"]
        df.loc[idx20, "close"] = bb_mid20 * 1.02

        strategy = TrendBBRSIStrategy(stop_loss=0.07)
        signals = strategy.generate_signals(df)

        sell_signals = [s for s in signals if s.action == "SELL"]
        assert len(sell_signals) > 0
        # 至少有一个止损信号
        stop_signals = [s for s in sell_signals if "止损" in s.reason]
        assert len(stop_signals) > 0, f"No stop-loss signals, got: {[s.reason for s in sell_signals]}"

    def test_take_profit_partial_sell(self, trend_bb_rsi_buy_df):
        """阶梯止盈应产生部分卖出信号（strength < 1）。"""
        strategy = TrendBBRSIStrategy(
            take_profit_levels=[[0.05, 0.3], [0.10, 0.3]],
        )
        signals = strategy.generate_signals(trend_bb_rsi_buy_df)

        tp_signals = [s for s in signals if "阶梯止盈" in s.reason]
        # 不一定触发（取决于价格走势），但若触发则强度应 < 1
        for s in tp_signals:
            assert s.strength < 1.0, f"Take-profit should be partial, got strength={s.strength}"
            assert s.action == "SELL"


# ====================================================================
# TrendMABreakoutStrategy 测试（金叉 + RSI 择时过滤）
# ====================================================================


@pytest.fixture
def trend_ma_breakout_buy_df():
    """构造满足金叉 + RSI 甜区买入条件的走势。

    60 天数据：前 30 天下跌，后 30 天上涨形成金叉。
    在金叉日设置 RSI 在 35-65 之间。
    """
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=60, freq="D")

    # 前 30 天下跌（12→8），后 30 天上涨（8→14）
    t1 = np.linspace(12, 8, 30)
    t2 = np.linspace(8, 14, 30)
    close = np.concatenate([t1, t2]) + np.random.randn(60) * 0.2
    close = np.clip(close, 6, 16)

    df = pd.DataFrame({
        "close": close,
        "open": close + np.random.randn(60) * 0.08,
        "high": close + np.abs(np.random.randn(60)) * 0.15,
        "low": close - np.abs(np.random.randn(60)) * 0.15,
        "volume": np.random.randint(1e6, 5e6, 60),
    }, index=dates)

    # 计算所需指标
    ma_fast = MA(period=5)
    ma_slow = MA(period=20)
    rsi = RSI(period=14)
    df = ma_fast.compute(df)
    df = ma_slow.compute(df)
    df = rsi.compute(df)

    # 找到金叉日并设置 RSI 在甜区
    for i in range(30, 55):
        prev_fast = df.iloc[i - 1]["ind_ma_5"]
        prev_slow = df.iloc[i - 1]["ind_ma_20"]
        curr_fast = df.iloc[i]["ind_ma_5"]
        curr_slow = df.iloc[i]["ind_ma_20"]
        if prev_fast <= prev_slow and curr_fast > curr_slow:
            # 金叉日，设置 RSI = 50（甜区中间）
            df.loc[dates[i], "ind_rsi_14"] = 50.0
            break

    return df


class TestTrendMABreakout:
    """金叉 + RSI 择时过滤策略测试。"""

    def test_buy_on_golden_cross_with_rsi_sweet_spot(self, trend_ma_breakout_buy_df):
        """RSI 在甜区时的金叉应产生 BUY。"""
        strategy = TrendMABreakoutStrategy(rsi_low=35, rsi_high=65)
        signals = strategy.generate_signals(trend_ma_breakout_buy_df)

        buy_signals = [s for s in signals if s.action == "BUY"]
        assert len(buy_signals) > 0, (
            f"Expected BUY signal on golden cross with RSI sweet spot, "
            f"got {len(signals)} signals"
        )
        for s in buy_signals:
            assert "金叉" in s.reason
            assert "RSI" in s.reason

    def test_no_buy_when_rsi_too_low(self, trend_ma_breakout_buy_df):
        """RSI 低于下限时金叉不应买入。"""
        # 手动设置 RSI 为 20（低于下限 35）
        rsi_col = "ind_rsi_14"
        for i in range(30, 55):
            prev_fast = trend_ma_breakout_buy_df.iloc[i - 1]["ind_ma_5"]
            prev_slow = trend_ma_breakout_buy_df.iloc[i - 1]["ind_ma_20"]
            curr_fast = trend_ma_breakout_buy_df.iloc[i]["ind_ma_5"]
            curr_slow = trend_ma_breakout_buy_df.iloc[i]["ind_ma_20"]
            if prev_fast <= prev_slow and curr_fast > curr_slow:
                trend_ma_breakout_buy_df.iloc[i, trend_ma_breakout_buy_df.columns.get_loc(rsi_col)] = 20.0
                break

        strategy = TrendMABreakoutStrategy(rsi_low=35, rsi_high=65)
        signals = strategy.generate_signals(trend_ma_breakout_buy_df)

        buy_signals = [s for s in signals if s.action == "BUY"]
        assert len(buy_signals) == 0, (
            f"Expected NO BUY when RSI=20 (below lower bound), "
            f"got {len(buy_signals)} BUY signals"
        )

    def test_no_buy_when_rsi_too_high(self, trend_ma_breakout_buy_df):
        """RSI 高于上限时金叉不应买入。"""
        rsi_col = "ind_rsi_14"
        for i in range(30, 55):
            prev_fast = trend_ma_breakout_buy_df.iloc[i - 1]["ind_ma_5"]
            prev_slow = trend_ma_breakout_buy_df.iloc[i - 1]["ind_ma_20"]
            curr_fast = trend_ma_breakout_buy_df.iloc[i]["ind_ma_5"]
            curr_slow = trend_ma_breakout_buy_df.iloc[i]["ind_ma_20"]
            if prev_fast <= prev_slow and curr_fast > curr_slow:
                trend_ma_breakout_buy_df.iloc[i, trend_ma_breakout_buy_df.columns.get_loc(rsi_col)] = 75.0
                break

        strategy = TrendMABreakoutStrategy(rsi_low=35, rsi_high=65)
        signals = strategy.generate_signals(trend_ma_breakout_buy_df)

        buy_signals = [s for s in signals if s.action == "BUY"]
        assert len(buy_signals) == 0, (
            f"Expected NO BUY when RSI=75 (above upper bound), "
            f"got {len(buy_signals)} BUY signals"
        )

    def test_no_signals_on_empty_df(self):
        """空 DataFrame 应返回空列表。"""
        strategy = TrendMABreakoutStrategy()
        signals = strategy.generate_signals(pd.DataFrame())
        assert signals == []

    def test_no_signals_without_indicators(self, vshape_df):
        """未计算指标的 DataFrame 应返回空。"""
        strategy = TrendMABreakoutStrategy()
        signals = strategy.generate_signals(vshape_df)
        assert signals == []

    def test_default_constructor(self):
        """默认参数应正确设置。"""
        strategy = TrendMABreakoutStrategy()
        assert strategy.fast == 5
        assert strategy.slow == 20
        assert strategy.rsi_low == 30
        assert strategy.rsi_high == 60
        assert strategy.stop_loss == 0.05
        assert strategy.batch_entry is True
        assert len(strategy.batches) == 1  # default [1.0]
        assert len(strategy.take_profit_levels) == 1  # default [(0.15, 1.0)]
        assert len(strategy.drawdown_rules) == 1  # default trend_end
        assert len(strategy.required_indicators) == 3  # MA(5) + MA(20) + RSI(14)

    def test_stop_loss_and_death_cross_exit(self):
        """止损和死叉应产生卖出信号。"""
        np.random.seed(99)
        dates = pd.date_range("2024-01-01", periods=80, freq="D")

        # 构造数据：先形成金叉入场，然后快速下跌触发止损
        close = np.concatenate([
            np.linspace(10, 9, 25),     # 下跌
            np.linspace(9, 11, 10),     # 上涨形成金叉
            np.linspace(11, 7, 45),     # 暴跌触发止损
        ])
        df = pd.DataFrame({
            "close": close,
            "open": close,
            "high": close,
            "low": close,
            "volume": np.full(80, 1_000_000),
        }, index=dates)

        ma_fast = MA(period=5)
        ma_slow = MA(period=20)
        rsi = RSI(period=14)
        df = ma_fast.compute(df)
        df = ma_slow.compute(df)
        df = rsi.compute(df)

        # 找到金叉日，设置 RSI 在甜区
        for i in range(25, 40):
            pf = df.iloc[i - 1]["ind_ma_5"]
            ps = df.iloc[i - 1]["ind_ma_20"]
            cf = df.iloc[i]["ind_ma_5"]
            cs = df.iloc[i]["ind_ma_20"]
            if not pd.isna(pf) and not pd.isna(ps) and pf <= ps and cf > cs:
                df.loc[dates[i], "ind_rsi_14"] = 50.0
                break

        strategy = TrendMABreakoutStrategy(stop_loss=0.05)
        signals = strategy.generate_signals(df)

        sell_signals = [s for s in signals if s.action == "SELL"]
        assert len(sell_signals) > 0, f"Expected sell signals, got {[(s.action, s.reason) for s in signals]}"

    def test_batch_entry_and_take_profit(self, trend_ma_breakout_buy_df):
        """分批买入和阶梯止盈应正确触发。"""
        strategy = TrendMABreakoutStrategy(
            rsi_low=35, rsi_high=65,
            batch_entry=True,
            batches=[0.6, 0.2, 0.2],
            batch_triggers=[0.0, 0.05, 0.1],
            take_profit_levels=[[0.08, 0.3], [0.15, 0.3]],
        )
        signals = strategy.generate_signals(trend_ma_breakout_buy_df)
        assert isinstance(signals, list)

        # 应有买入信号
        buy_signals = [s for s in signals if s.action == "BUY"]
        assert len(buy_signals) > 0
