"""回测引擎单元测试（重点：撮合/T+1/手续费/仓位）。"""
import pytest
from datetime import date
from autotrade.core.models import (
    Bar, Signal, Trade, BacktestConfig, BacktestResult,
)
from autotrade.core.backtester import Backtester


@pytest.fixture
def sample_bars():
    """生成一组模拟日线数据（10个交易日）。"""
    return [
        Bar(symbol="000001", date=date(2024, 1, i), open=10.0, high=10.5,
            low=9.8, close=10.2 + i * 0.1, volume=1e6, amount=1e7)
        for i in range(2, 12)  # 1月2日 到 1月11日（跳过元旦假期）
    ]


@pytest.fixture
def default_config():
    return BacktestConfig(initial_capital=100_000.0)


class TestBacktester:
    def test_no_signals_no_trades(self, sample_bars, default_config):
        """无信号时应无交易。"""
        bt = Backtester(default_config)
        result = bt.run([], sample_bars)
        assert len(result.trades) == 0
        assert result.metrics["total_trades"] == 0
        assert result.metrics["total_return_pct"] == 0.0

    def test_buy_signal_creates_trade(self, sample_bars, default_config):
        """买入信号应产生一笔交易（使用默认次日开盘价成交）。"""
        bt = Backtester(default_config)
        signals = [Signal(symbol="000001", date=date(2024, 1, 2),
                          action="BUY", strength=1.0)]
        result = bt.run(signals, sample_bars)
        assert len(result.trades) == 1
        assert result.trades[0].action == "BUY"
        assert result.trades[0].quantity > 0

    def test_t_plus_1_rejects_same_day_sell(self, sample_bars, default_config):
        """T+1：当日买入后当日再发出卖出信号，应被忽略。"""
        bt = Backtester(default_config)
        signals = [
            Signal(symbol="000001", date=date(2024, 1, 2), action="BUY", strength=1.0),
            Signal(symbol="000001", date=date(2024, 1, 2), action="SELL", strength=1.0),
        ]
        result = bt.run(signals, sample_bars)
        # 买入成功，卖出被拒绝（T+1）
        buy_trades = [t for t in result.trades if t.action == "BUY"]
        sell_trades = [t for t in result.trades if t.action == "SELL"]
        assert len(buy_trades) == 1
        assert len(sell_trades) == 0

    def test_t_plus_1_allow_next_day_sell(self, sample_bars, default_config):
        """T+1：次日卖出应成功。"""
        bt = Backtester(default_config)
        signals = [
            Signal(symbol="000001", date=date(2024, 1, 2), action="BUY", strength=1.0),
            Signal(symbol="000001", date=date(2024, 1, 3), action="SELL", strength=1.0),
        ]
        result = bt.run(signals, sample_bars)
        sell_trades = [t for t in result.trades if t.action == "SELL"]
        assert len(sell_trades) == 1

    def test_stamp_duty_only_on_sell(self, sample_bars, default_config):
        """买入不扣印花税，卖出扣千一印花税。"""
        bt = Backtester(default_config)
        signals = [
            Signal(symbol="000001", date=date(2024, 1, 2), action="BUY", strength=1.0),
            Signal(symbol="000001", date=date(2024, 1, 3), action="SELL", strength=1.0),
        ]
        result = bt.run(signals, sample_bars)
        buy = [t for t in result.trades if t.action == "BUY"][0]
        sell = [t for t in result.trades if t.action == "SELL"][0]
        assert buy.stamp_duty == 0.0
        assert sell.stamp_duty > 0.0

    def test_lot_rounding(self, sample_bars, default_config):
        """买入股数应向下取整到 100 的倍数。"""
        bt = Backtester(default_config)
        signals = [Signal(symbol="000001", date=date(2024, 1, 2),
                          action="BUY", strength=1.0)]
        result = bt.run(signals, sample_bars)
        assert result.trades[0].quantity % 100 == 0

    def test_slippage_applied(self, sample_bars, default_config):
        """滑点千一时买入价 = 信号价 × 1.001。"""
        config = BacktestConfig(slippage=0.001, fill_price="close")
        bt = Backtester(config)
        # 信号日期为 1月2日，成交价为当日 close
        signals = [Signal(symbol="000001", date=date(2024, 1, 2),
                          action="BUY", strength=1.0)]
        result = bt.run(signals, sample_bars)
        # bars[0] 对应 1月2日
        expected_price = sample_bars[0].close * 1.001
        assert abs(result.trades[0].price - expected_price) < 0.001

    def test_min_commission(self, sample_bars):
        """单笔最低佣金 5 元。"""
        config = BacktestConfig(initial_capital=2000.0, commission_rate=0.0003,
                                min_commission=5.0, fill_price="close")
        bt = Backtester(config)
        signals = [Signal(symbol="000001", date=date(2024, 1, 2),
                          action="BUY", strength=1.0)]
        result = bt.run(signals, sample_bars)
        assert result.trades[0].commission >= 5.0

    def test_equity_curve_generated(self, sample_bars, default_config):
        """应有净值曲线，长度为 bars 数 + 1（含初始）。"""
        bt = Backtester(default_config)
        signals = [Signal(symbol="000001", date=date(2024, 1, 2),
                          action="BUY", strength=1.0)]
        result = bt.run(signals, sample_bars)
        assert result.equity_curve is not None
        assert len(result.equity_curve) == len(sample_bars) + 1  # 含日期0（初始）

    def test_multiple_buy_sell_cycle(self, sample_bars, default_config):
        """完整的买卖循环后，资金应变化。"""
        bt = Backtester(default_config)
        signals = [
            Signal(symbol="000001", date=date(2024, 1, 2), action="BUY", strength=1.0),
            Signal(symbol="000001", date=date(2024, 1, 5), action="SELL", strength=1.0),
        ]
        result = bt.run(signals, sample_bars)
        assert len(result.trades) == 2
        assert result.metrics["total_return_pct"] != 0.0
