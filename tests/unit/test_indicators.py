"""指标计算单元测试。"""
import pytest
import pandas as pd
import numpy as np
from autotrade.indicators.ma import MA, EMA
from autotrade.indicators.macd import MACD
from autotrade.indicators.rsi import RSI
from autotrade.indicators.bollinger import BollingerBands


@pytest.fixture
def sample_df():
    """生成 60 天的模拟价格数据。"""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    close = 10 + np.cumsum(np.random.randn(60) * 0.1)
    return pd.DataFrame({
        "open": close + np.random.randn(60) * 0.05,
        "high": close + np.abs(np.random.randn(60)) * 0.1,
        "low": close - np.abs(np.random.randn(60)) * 0.1,
        "close": close,
        "volume": np.random.randint(1e6, 1e7, 60),
    })


class TestIndicators:
    def test_ma_compute(self, sample_df):
        ma = MA(period=5)
        result = ma.compute(sample_df)
        assert "ind_ma_5" in result.columns
        assert result["ind_ma_5"].notna().sum() > 0

    def test_ma_longer_than_period(self, sample_df):
        """前 period-1 个值应为 NaN。"""
        ma = MA(period=20)
        result = ma.compute(sample_df)
        assert pd.isna(result["ind_ma_20"].iloc[:19]).all()
        assert result["ind_ma_20"].iloc[19] is not None

    def test_ema_compute(self, sample_df):
        ema = EMA(period=14)
        result = ema.compute(sample_df)
        assert "ind_ema_14" in result.columns

    def test_macd_compute(self, sample_df):
        macd = MACD()
        result = macd.compute(sample_df)
        assert "ind_macd_macd" in result.columns
        assert "ind_macd_signal" in result.columns
        assert "ind_macd_histogram" in result.columns

    def test_rsi_compute(self, sample_df):
        rsi = RSI(period=14)
        result = rsi.compute(sample_df)
        assert "ind_rsi_14" in result.columns
        # RSI 值应在 0~100 之间
        valid = result["ind_rsi_14"].dropna()
        assert (valid >= 0).all()
        assert (valid <= 100).all()

    def test_bollinger_compute(self, sample_df):
        bb = BollingerBands(period=20)
        result = bb.compute(sample_df)
        assert "ind_bb_upper_20" in result.columns
        assert "ind_bb_middle_20" in result.columns
        assert "ind_bb_lower_20" in result.columns
        # 上轨 >= 中轨 >= 下轨
        mid = result["ind_bb_middle_20"].dropna()
        upper = result["ind_bb_upper_20"].dropna()
        lower = result["ind_bb_lower_20"].dropna()
        assert (upper >= mid).all()
        assert (mid >= lower).all()

    def test_idempotent(self, sample_df):
        """多次 compute 应保持结果一致。"""
        ma = MA(period=5)
        result1 = ma.compute(sample_df)
        result2 = ma.compute(result1)
        pd.testing.assert_frame_equal(result1, result2)
