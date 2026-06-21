"""游资策略 v2 单元测试。"""
import numpy as np
import pandas as pd

from autotrade.strategies.hot_money import HotMoneyStrategy
from autotrade.screens.hot_money import HotMoneyScreener


def _make_df(closes, volumes=None, start="2024-01-01"):
    """构造 OHLCV DataFrame，open 略低于 close（确保收阳）。"""
    n = len(closes)
    dates = pd.date_range(start, periods=n, freq="D")
    arr = np.array(closes, dtype=float)
    vols = np.array(volumes, dtype=float) if volumes is not None else np.full(n, 1e6)
    opens = np.concatenate([[arr[0] * 0.99], arr[:-1] * 0.99])
    highs = np.maximum(opens, arr) + 0.05
    lows = np.minimum(opens, arr) - 0.05
    return pd.DataFrame({
        "open": opens, "high": highs, "low": lows,
        "close": arr, "volume": vols, "amount": vols * arr,
    }, index=dates)


# ============ Strategy tests (entry must close > open) ============

def test_hard_stop_loss():
    # 进场日上涨 10.0→10.1，然后跌到 9.3 (-7%, 触发默认 -7% 止损)
    df = _make_df([10.0, 10.1, 9.3])
    s = HotMoneyStrategy(allowed_entry_dates=[df.index[0].date()])
    sigs = s.generate_signals(df)
    assert any("止损" in sig.reason for sig in sigs if sig.action == "SELL")


def test_time_stop():
    df = _make_df([10.0, 10.05, 10.05, 10.04, 10.05, 10.05, 10.04, 10.05])
    s = HotMoneyStrategy(allowed_entry_dates=[df.index[0].date()])
    sigs = s.generate_signals(df)
    assert any("时间" in sig.reason for sig in sigs if sig.action == "SELL")


def test_trailing_take_profit():
    # 进场 10.0 → 涨到 11.5 (+15%, 启动移动止盈) → 回撤到 10.9 (-5.2%)
    df = _make_df([10.0, 11.5, 10.9])
    s = HotMoneyStrategy(allowed_entry_dates=[df.index[0].date()])
    sigs = s.generate_signals(df)
    assert any("止盈" in sig.reason for sig in sigs if sig.action == "SELL")


def test_no_entry_outside_allowed():
    df = _make_df([10.0, 11.0, 12.0])
    s = HotMoneyStrategy(allowed_entry_dates=[])
    assert all(sig.action != "BUY" for sig in s.generate_signals(df))


def test_custom_thresholds():
    df = _make_df([10.0, 10.05, 9.7])
    s = HotMoneyStrategy(allowed_entry_dates=[df.index[0].date()], stop_loss=0.02)
    sigs = s.generate_signals(df)
    assert any("止损" in sig.reason for sig in sigs if sig.action == "SELL")


def test_trend_break_exit():
    """趋势破坏 MA20 < MA60（在软止损都关闭时触发）。"""
    closes = []
    for i in range(200):
        if i < 60:  closes.append(10.0 + i * 0.02)
        else:       closes.append(closes[-1] - 0.005)
    df = _make_df(closes)
    # 关掉所有价格止损，只留趋势破坏
    s = HotMoneyStrategy(
        allowed_entry_dates=[df.index[40].date()],
        stop_loss=0.50, time_stop_days=200, time_stop_min_gain=-0.50,
        trailing_activate=5.0,
    )
    sigs = s.generate_signals(df)
    assert any("趋势破坏" in sig.reason for sig in sigs if sig.action == "SELL")


# ============ Screener tests ============

def _make_trend_df(closes, volumes=None, start="2024-01-01"):
    from autotrade.screens.hot_money import _sma
    n = len(closes)
    dates = pd.date_range(start, periods=n, freq="D")
    arr = np.array(closes, dtype=float)
    if volumes is None:
        vols = np.full(n, 5e6, dtype=float)
        vols[-1] = 15e6  # 最后一天放量
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
    p = {"momentum_min": -1.0, "momentum_max": 10.0}  # 测试中不过滤动量
    p.update(params)
    return HotMoneyScreener(**p).scan(market_data, dates)


def test_prefilter_rejects_downtrend():
    closes = np.linspace(20, 8, 200).tolist()
    df = _make_trend_df(closes)
    d = df.index[-1].date()
    result = _run_scan({"test": df}, [d])
    assert result.get(d, []) == []


def test_pullback_signal():
    closes = np.linspace(10, 15, 200).tolist()
    closes[197] = 15.0; closes[198] = 14.8; closes[199] = 15.1
    vols = [5e6] * 200; vols[199] = 10e6
    df = _make_trend_df(closes, vols)
    d = df.index[-1].date()
    picks = _run_scan({"test": df}, [d]).get(d, [])
    assert len(picks) >= 1
    assert picks[0][2] in ("pullback", "breakout", "strength")


def test_breakout_signal():
    closes = np.linspace(10, 15, 200).tolist(); closes[-1] = 15.5
    vols = [5e6] * 200; vols[-1] = 10e6
    df = _make_trend_df(closes, vols)
    d = df.index[-1].date()
    picks = _run_scan({"test": df}, [d]).get(d, [])
    assert len(picks) >= 1


def test_max_picks():
    market = {}
    for i in range(3):
        closes = np.linspace(10, 15, 200).tolist()
        closes[-2] = closes[-3]
        closes[-1] = closes[-2] * (1.05 + i * 0.02)
        market[f"s{i}"] = _make_trend_df(closes)
    d = list(market.values())[0].index[-1].date()
    picks = _run_scan(market, [d], max_picks=2).get(d, [])
    assert len(picks) == 2


def test_excludes_short_history():
    closes = [10.0, 11.0] * 2
    df = _make_trend_df(closes)
    d = df.index[-1].date()
    assert _run_scan({"test": df}, [d]).get(d, []) == []
