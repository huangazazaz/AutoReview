"""游资策略 v2 单元测试。"""
import numpy as np
import pandas as pd

from autotrade.strategies.hot_money import HotMoneyStrategy
from autotrade.screens.hot_money import HotMoneyScreener


def _make_df(closes, volumes=None, start="2024-01-01"):
    """构造 OHLCV DataFrame, index 为 DatetimeIndex。"""
    n = len(closes)
    dates = pd.date_range(start, periods=n, freq="D")
    arr = np.array(closes, dtype=float)
    vols = np.array(volumes, dtype=float) if volumes is not None else np.full(n, 1e6)
    opens = np.concatenate([[arr[0]], arr[:-1]])
    highs = np.maximum(opens, arr) + 0.05
    lows = np.minimum(opens, arr) - 0.05
    return pd.DataFrame({
        "open": opens, "high": highs, "low": lows,
        "close": arr, "volume": vols,
        "amount": vols * arr,
    }, index=dates)


# ==================== Strategy 测试 ====================

def test_hard_stop_loss():
    df = _make_df([10.0, 9.4, 9.0])
    s = HotMoneyStrategy(allowed_entry_dates=[df.index[0].date()])
    sigs = s.generate_signals(df)
    assert any("止损" in sig.reason for sig in sigs if sig.action == "SELL")


def test_time_stop():
    df = _make_df([10.0] * 10)
    s = HotMoneyStrategy(allowed_entry_dates=[df.index[0].date()])
    sigs = s.generate_signals(df)
    assert any("时间" in sig.reason for sig in sigs if sig.action == "SELL")


def test_trailing_take_profit():
    # 进场 10.0 → 涨到 10.6 (+6%, 启动移动止盈) → 回撤到 10.38 (-2.1%)
    df = _make_df([10.0, 10.6, 10.38])
    s = HotMoneyStrategy(allowed_entry_dates=[df.index[0].date()])
    sigs = s.generate_signals(df)
    assert any("止盈" in sig.reason for sig in sigs if sig.action == "SELL")


def test_no_entry_outside_allowed():
    df = _make_df([10.0, 11.0, 12.0])
    s = HotMoneyStrategy(allowed_entry_dates=[])
    assert all(sig.action != "BUY" for sig in s.generate_signals(df))


def test_custom_thresholds():
    df = _make_df([10.0, 9.7, 9.5])
    s = HotMoneyStrategy(allowed_entry_dates=[df.index[0].date()], stop_loss=0.02)
    sigs = s.generate_signals(df)
    assert any("止损" in sig.reason for sig in sigs if sig.action == "SELL")


def test_trend_break_exit():
    """趋势破坏 MA20 < MA60 应触发离场。"""
    # 构造下跌走势: MA20 下穿 MA60
    closes = np.linspace(20, 10, 150).tolist()
    df = _make_df(closes)
    s = HotMoneyStrategy(allowed_entry_dates=[df.index[60].date()])
    sigs = s.generate_signals(df)
    assert any("趋势破坏" in sig.reason for sig in sigs if sig.action == "SELL")


# ==================== Screener 测试 ====================

def _make_trend_df(closes, volumes=None, start="2024-01-01"):
    """构造带 MA 列的 DataFrame，用于 screener 测试。
    如果未指定 volumes，最后一天自动放量（触发信号所需）。"""
    from autotrade.screens.hot_money import _sma
    n = len(closes)
    dates = pd.date_range(start, periods=n, freq="D")
    arr = np.array(closes, dtype=float)
    if volumes is None:
        vols = np.full(n, 5e6, dtype=float)
        vols[-1] = 15e6  # 最后一天放量 3 倍
    else:
        vols = np.array(volumes, dtype=float)
    opens = np.concatenate([[arr[0]], arr[:-1]])
    highs = np.maximum(opens, arr) + 0.05
    lows = np.minimum(opens, arr) - 0.05
    df = pd.DataFrame({
        "open": opens, "high": highs, "low": lows,
        "close": arr, "volume": vols, "amount": vols * arr,
    }, index=dates)
    df["_ma_fast"] = _sma(df["close"], 20)
    df["_ma_mid"] = _sma(df["close"], 60)
    df["_ma_slow"] = _sma(df["close"], 120)
    df["_amount_ma"] = _sma(df["amount"], 20)
    return df


def _run_scan(market_data, dates, **params):
    return HotMoneyScreener(**params).scan(market_data, dates)


def test_prefilter_rejects_downtrend():
    """下跌趋势的票应被预过滤排除。"""
    closes = np.linspace(20, 8, 200).tolist()  # 长期下跌
    df = _make_trend_df(closes)
    d = df.index[-1].date()
    result = _run_scan({"test": df}, [d])
    assert result.get(d, []) == []


def test_pullback_signal():
    """趋势多头 + 回踩 MA20 + 放量反弹 → pullback 信号。"""
    closes = np.linspace(10, 15, 200).tolist()
    closes[197] = 15.0
    closes[198] = 14.8   # 回踩
    closes[199] = 15.1   # 反弹
    vols = [5e6] * 200
    vols[199] = 10e6     # 放量
    df = _make_trend_df(closes, vols)
    d = df.index[-1].date()
    result = _run_scan({"test": df}, [d])
    picks = result.get(d, [])
    assert len(picks) >= 1
    assert picks[0][2] in ("pullback", "breakout", "strength")


def test_breakout_signal():
    """趋势多头 + 突破 10 日高点 → breakout 信号。"""
    closes = np.linspace(10, 15, 200).tolist()
    closes[-1] = 15.5
    vols = [5e6] * 200
    vols[-1] = 10e6
    df = _make_trend_df(closes, vols)
    d = df.index[-1].date()
    result = _run_scan({"test": df}, [d])
    picks = result.get(d, [])
    assert len(picks) >= 1
    assert picks[0][2] in ("pullback", "breakout", "strength")


def test_max_picks():
    """多只票只取 max_picks 只。"""
    market = {}
    for i in range(3):
        closes = np.linspace(10, 15, 200).tolist()
        # 最后一天制造明显涨幅，触发信号
        closes[-2] = closes[-3]  # 倒数第二天平
        closes[-1] = closes[-2] * (1.05 + i * 0.02)  # +5%, +7%, +9%
        df = _make_trend_df(closes)
        market[f"s{i}"] = df
    d = list(market.values())[0].index[-1].date()
    result = _run_scan(market, [d], max_picks=2)
    assert len(result.get(d, [])) == 2
    assert result[d][0][1] >= result[d][1][1]  # 按 score 降序


def test_excludes_short_history():
    closes = [10.0, 11.0] * 2
    df = _make_trend_df(closes)
    d = df.index[-1].date()
    result = _run_scan({"test": df}, [d])
    assert result.get(d, []) == []
