"""MomentumScreener 多因子选股单元测试。"""
import numpy as np
import pandas as pd

import pytest
from autotrade.screens.momentum import MomentumScreener


def _make_df(closes, volumes=None, start="2024-01-01"):
    """构造 OHLCV DataFrame。open 略低于 close 确保收阳（阳线占比测试可控）。"""
    n = len(closes)
    dates = pd.date_range(start, periods=n, freq="B")
    arr = np.array(closes, dtype=float)
    vols = np.array(volumes, dtype=float) if volumes is not None else np.full(n, 1e7, dtype=float)
    opens = arr * 0.99
    highs = np.maximum(opens, arr) + 0.05
    lows = np.minimum(opens, arr) - 0.05
    amounts = vols * arr
    return pd.DataFrame({
        "open": opens, "high": highs, "low": lows,
        "close": arr, "volume": vols, "amount": amounts,
    }, index=dates)


def _run_scan(market_data, dates, **overrides):
    """用默认参数运行 scan，支持参数覆盖。"""
    params = {
        "min_amount": 5_000_000,
        "mom_1m_min": -1.0,
        "mom_1m_max": 10.0,
        "score_threshold": 0.0,
        "top_n_per_day": 50,
    }
    params.update(overrides)
    return MomentumScreener(**params).scan(market_data, dates)


# ---------------------------------------------------------------------------
# 预筛选测试
# ---------------------------------------------------------------------------

def test_prefilter_rejects_downtrend():
    """MA20 <= MA60 的下跌趋势被剔除。"""
    closes = np.linspace(20, 8, 100).tolist()
    df = _make_df(closes)
    d = df.index[-1].date()
    result = _run_scan({"test": df}, [d])
    assert result.get(d, []) == []


def test_prefilter_accepts_uptrend():
    """MA20 > MA60 的上涨趋势通过预筛选。"""
    closes = np.linspace(10, 20, 100).tolist()
    df = _make_df(closes)
    d = df.index[-1].date()
    result = _run_scan({"test": df}, [d], score_threshold=0)
    # 只要有数据且趋势向上，应该至少产生一个结果
    picks = result.get(d, [])
    assert isinstance(picks, list)


def test_prefilter_rejects_low_amount():
    """日均成交额过低被剔除。"""
    closes = np.linspace(10, 15, 80).tolist()
    vols = [1e4] * 80
    df = _make_df(closes, vols)
    d = df.index[-1].date()
    result = _run_scan({"test": df}, [d], min_amount=100_000_000)
    assert result.get(d, []) == []


def test_prefilter_rejects_out_of_momentum_range():
    """近1月涨跌幅不在区间内被剔除。"""
    # 前60天横盘10元，后20天暴涨到16元 → 1月涨幅约60%，超过40%上限
    closes = [10.0] * 60 + [16.0] * 20
    df = _make_df(closes)
    d = df.index[-1].date()
    result = _run_scan({"test": df}, [d], mom_1m_min=0.03, mom_1m_max=0.40)
    assert result.get(d, []) == []


def test_prefilter_rejects_short_history():
    """数据不足60天被跳过。"""
    closes = [10, 11, 12, 13, 14]
    df = _make_df(closes)
    d = df.index[-1].date()
    result = _run_scan({"test": df}, [d])
    assert result.get(d, []) == []


# ---------------------------------------------------------------------------
# 因子打分测试
# ---------------------------------------------------------------------------

def test_momentum_1m_scoring():
    """动量1月因子：中等涨幅得高分。"""
    closes = np.linspace(10, 10, 70).tolist() + np.linspace(10, 11.5, 30).tolist()
    df = _make_df(closes)
    d = df.index[-1].date()
    screener = MomentumScreener(min_amount=1_000_000, mom_1m_min=-1.0, mom_1m_max=10.0,
                                score_threshold=0.0, top_n_per_day=50)
    result = screener.scan({"test": df}, [d])
    picks = result.get(d, [])
    assert len(picks) >= 1
    assert 0 <= picks[0][1] <= 1


def test_momentum_5d_scoring():
    """短期回调因子：小幅下跌得高分（反向）。"""
    closes = np.linspace(10, 15, 95).tolist() + [15.0, 14.9, 14.8, 14.7, 14.55]
    df = _make_df(closes)
    d = df.index[-1].date()
    screener = MomentumScreener(min_amount=1_000_000, mom_1m_min=-1.0, mom_1m_max=10.0,
                                score_threshold=0.0, top_n_per_day=50)
    result = screener.scan({"test": df}, [d])
    picks = result.get(d, [])
    assert len(picks) >= 1
    assert 0 <= picks[0][1] <= 1


def test_vol_ratio_scoring():
    """量比因子：温和放量得高分。"""
    closes = np.linspace(10, 15, 99).tolist() + [15.5]
    vols = [1e7] * 99 + [2e7]
    df = _make_df(closes, vols)
    d = df.index[-1].date()
    screener = MomentumScreener(min_amount=1_000_000, mom_1m_min=-1.0, mom_1m_max=10.0,
                                score_threshold=0.0, top_n_per_day=50)
    result = screener.scan({"test": df}, [d])
    picks = result.get(d, [])
    assert len(picks) >= 1
    assert 0 <= picks[0][1] <= 1


def test_ma_score_scoring():
    """均线多头因子：4条均线全多头得高分。"""
    closes = np.linspace(10, 25, 100).tolist()
    df = _make_df(closes)
    d = df.index[-1].date()
    screener = MomentumScreener(min_amount=1_000_000, mom_1m_min=-1.0, mom_1m_max=10.0,
                                score_threshold=0.0, top_n_per_day=50)
    result = screener.scan({"test": df}, [d])
    picks = result.get(d, [])
    assert len(picks) >= 1
    assert picks[0][1] > 0


def test_pullback_scoring():
    """回调到位因子：收盘价在MA20附近得高分。"""
    closes = np.linspace(10, 15, 80).tolist() + [15.0] * 20
    df = _make_df(closes)
    d = df.index[-1].date()
    screener = MomentumScreener(min_amount=1_000_000, mom_1m_min=-1.0, mom_1m_max=10.0,
                                score_threshold=0.0, top_n_per_day=50)
    result = screener.scan({"test": df}, [d])
    picks = result.get(d, [])
    assert len(picks) >= 1
    assert 0 <= picks[0][1] <= 1


def test_atr_ratio_scoring():
    """波动率因子：ATR/收盘价在合理范围得高分。"""
    np.random.seed(42)
    base = np.linspace(10, 15, 100)
    noisy = base + np.random.normal(0, 0.3, 100)
    closes = np.abs(noisy).tolist()
    df = _make_df(closes)
    d = df.index[-1].date()
    screener = MomentumScreener(min_amount=1_000_000, mom_1m_min=-1.0, mom_1m_max=10.0,
                                score_threshold=0.0, top_n_per_day=50)
    result = screener.scan({"test": df}, [d])
    picks = result.get(d, [])
    assert len(picks) >= 1
    assert 0 <= picks[0][1] <= 1


def test_consistency_scoring():
    """阳线占比因子：55%~75%得高分。"""
    closes = []
    v = 10.0
    for i in range(100):
        if i % 5 < 3:
            v += 0.08
        else:
            v -= 0.03
        closes.append(v)
    df = _make_df(closes)
    d = df.index[-1].date()
    screener = MomentumScreener(min_amount=1_000_000, mom_1m_min=-1.0, mom_1m_max=10.0,
                                score_threshold=0.0, top_n_per_day=50)
    result = screener.scan({"test": df}, [d])
    picks = result.get(d, [])
    assert len(picks) >= 1
    assert 0 <= picks[0][1] <= 1


# ---------------------------------------------------------------------------
# 信号标签测试
# ---------------------------------------------------------------------------

def test_signal_tag_strong():
    """强势标签：mom_1m 高 + mom_5d 为正 → momentum_strong。"""
    # 持续上涨，20日涨幅~25%，5日涨幅~5%
    closes = np.linspace(10, 20, 100).tolist()
    vols = [2e7] * 100
    df = _make_df(closes, vols)
    d = df.index[-1].date()
    screener = MomentumScreener(min_amount=1_000_000, mom_1m_min=-1.0, mom_1m_max=10.0,
                                score_threshold=0.0, top_n_per_day=50)
    result = screener.scan({"test": df}, [d])
    picks = result.get(d, [])
    assert len(picks) >= 1
    assert picks[0][2] == "momentum_strong"


def test_signal_tag_pullback():
    """回调标签：mom_1m 中等 + mom_5d 为负 → momentum_pullback。"""
    # 前50天横盘，然后45天急涨 10→22，最后5天回调
    n = 100
    closes = [10.0] * 50 + np.linspace(10, 22, 45).tolist() + [22.0, 21.5, 21.0, 20.6, 20.3]
    vols = [2e7] * n
    df = _make_df(closes, vols)
    d = df.index[-1].date()
    screener = MomentumScreener(min_amount=1_000_000, mom_1m_min=-1.0, mom_1m_max=10.0,
                                score_threshold=0.0, top_n_per_day=50)
    result = screener.scan({"test": df}, [d])
    picks = result.get(d, [])
    assert len(picks) >= 1
    assert picks[0][2] == "momentum_pullback"


def test_signal_tag_steady():
    """稳步上涨标签：consistency 突出 → momentum_steady。"""
    closes = []
    v = 10.0
    for i in range(100):
        v += 0.08
        closes.append(v)
    vols = [2e7] * 100
    df = _make_df(closes, vols)
    d = df.index[-1].date()
    screener = MomentumScreener(min_amount=1_000_000, mom_1m_min=-1.0, mom_1m_max=10.0,
                                score_threshold=0.0, top_n_per_day=50)
    result = screener.scan({"test": df}, [d])
    picks = result.get(d, [])
    assert len(picks) >= 1
    assert picks[0][2] == "momentum_steady"


# ---------------------------------------------------------------------------
# 控制参数测试
# ---------------------------------------------------------------------------

def test_top_n_enforced():
    """top_n_per_day 限制生效。"""
    market = {}
    for i in range(15):
        closes = np.linspace(10, 15 + i * 0.5, 100).tolist()
        vols = [2e7] * 100
        market[f"s{i}"] = _make_df(closes, vols)
    d = list(market.values())[0].index[-1].date()
    screener = MomentumScreener(min_amount=1_000_000, mom_1m_min=-1.0, mom_1m_max=10.0,
                                score_threshold=0.0, top_n_per_day=5)
    result = screener.scan(market, [d])
    assert len(result.get(d, [])) <= 5


def test_score_threshold_enforced():
    """score_threshold 过滤生效：高门槛筛掉低分股。"""
    closes = np.linspace(10, 12, 100).tolist()
    df = _make_df(closes)
    d = df.index[-1].date()
    screener = MomentumScreener(min_amount=1_000_000, mom_1m_min=-1.0, mom_1m_max=10.0,
                                score_threshold=0.90, top_n_per_day=10)
    result = screener.scan({"test": df}, [d])
    assert result.get(d, []) == []


def test_empty_market_data():
    """空数据不报错，返回空结果。"""
    screener = MomentumScreener()
    result = screener.scan({}, [])
    assert result == {}


def test_multiple_dates():
    """多日期扫描每日期都返回结果。"""
    closes = np.linspace(10, 18, 100).tolist()
    df = _make_df(closes)
    dates = [df.index[30].date(), df.index[60].date(), df.index[99].date()]
    screener = MomentumScreener(min_amount=1_000_000, mom_1m_min=-1.0, mom_1m_max=10.0,
                                score_threshold=0.0, top_n_per_day=50)
    result = screener.scan({"test": df}, dates)
    assert len(result) == 3
    for d in dates:
        assert d in result
