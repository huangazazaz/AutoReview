"""编排层集成测试（使用 fixture 数据，不依赖网络）。"""
import pytest
from datetime import date
from autotrade.core.models import Bar, BacktestConfig
from autotrade.core.engine import _bars_to_dataframe, analyze_stock
from autotrade.registry import init_registry


@pytest.fixture
def bars_from_fixture():
    """从 fixture CSV 加载数据。"""
    import pandas as pd
    df = pd.read_csv("tests/fixtures/000001_daily.csv")
    bars = []
    for _, row in df.iterrows():
        bars.append(Bar(
            symbol=row["symbol"],
            date=date.fromisoformat(str(row["date"])),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"]),
            amount=float(row["amount"]),
        ))
    return bars


class TestEngine:
    def test_bars_to_dataframe(self, bars_from_fixture):
        df = _bars_to_dataframe(bars_from_fixture)
        assert not df.empty
        assert "close" in df.columns
        assert len(df) == len(bars_from_fixture)

    def test_registry_initialized(self):
        """确保注册表能初始化。"""
        init_registry(force=True)
        from autotrade.registry import list_strategies, list_indicators
        strategies = list_strategies()
        indicators = list_indicators()
        assert "ma_cross" in strategies
