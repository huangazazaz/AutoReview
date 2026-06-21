"""游资策略单元测试：三闸门出场状态机。"""
import numpy as np
import pandas as pd

from autotrade.strategies.hot_money import HotMoneyStrategy


def _make_bar_df(closes, start="2024-01-01"):
    """构造 OHLCV DataFrame, index 为日期, close 按给定序列。"""
    dates = pd.date_range(start, periods=len(closes), freq="D")
    closes_arr = np.array(closes, dtype=float)
    df = pd.DataFrame({
        "open": closes_arr,
        "high": closes_arr + 0.1,
        "low": closes_arr - 0.1,
        "close": closes_arr,
        "volume": 1e6,
    }, index=dates)
    return df


# ---------- 闸门3: 硬止损 -5% ----------
def test_hard_stop_loss():
    """进场后跌破 -5% 应触发硬止损 SELL。"""
    df = _make_bar_df([10.0, 9.4, 9.0])  # 进场后 -6%
    entry_dates = [df.index[0].date()]
    strat = HotMoneyStrategy(allowed_entry_dates=entry_dates)
    sigs = strat.generate_signals(df)
    actions = [(s.action, s.date, s.reason) for s in sigs]
    assert any(a == "BUY" for a, _, _ in actions)
    sell_reasons = [r for a, _, r in actions if a == "SELL"]
    assert any("止损" in r for r in sell_reasons)


# ---------- 闸门2: 时间止损（3天未达+3%）----------
def test_time_stop():
    """持仓 3 天且收益 < +3% 应触发时间止损。"""
    df = _make_bar_df([10.0, 10.0, 10.0, 10.0, 10.0])
    entry_dates = [df.index[0].date()]
    strat = HotMoneyStrategy(allowed_entry_dates=entry_dates)
    sigs = strat.generate_signals(df)
    sell_reasons = [s.reason for s in sigs if s.action == "SELL"]
    assert any("时间" in r for r in sell_reasons)


# ---------- 闸门1: 移动止盈（+8%启动, 回撤3%）----------
def test_trailing_take_profit():
    """涨到 +8% 后回撤 3% 应触发移动止盈。"""
    df = _make_bar_df([10.0, 10.9, 10.5])
    entry_dates = [df.index[0].date()]
    strat = HotMoneyStrategy(allowed_entry_dates=entry_dates)
    sigs = strat.generate_signals(df)
    sell_reasons = [s.reason for s in sigs if s.action == "SELL"]
    assert any("止盈" in r for r in sell_reasons)


# ---------- 不在 allowed_entry_dates 不进场 ----------
def test_no_entry_outside_allowed_dates():
    """不在 allowed_entry_dates 的日子不应进场。"""
    df = _make_bar_df([10.0, 11.0, 12.0])
    entry_dates = []  # 空, 任何日子都不进场
    strat = HotMoneyStrategy(allowed_entry_dates=entry_dates)
    sigs = strat.generate_signals(df)
    assert all(s.action != "BUY" for s in sigs)


# ---------- 阈值可配置 ----------
def test_custom_thresholds():
    """自定义阈值应生效: 把 stop_loss 调到 -2%, 轻微下跌即止损。"""
    df = _make_bar_df([10.0, 9.7, 9.5])  # 第1天 -3%
    entry_dates = [df.index[0].date()]
    strat = HotMoneyStrategy(
        allowed_entry_dates=entry_dates, stop_loss=0.02,
    )
    sigs = strat.generate_signals(df)
    sell_reasons = [s.reason for s in sigs if s.action == "SELL"]
    assert any("止损" in r for r in sell_reasons)
