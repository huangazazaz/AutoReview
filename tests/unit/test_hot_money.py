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


# ============================================================
# Screener 测试
# ============================================================
from autotrade.screens.hot_money import HotMoneyScreener


def _make_market(symbol, closes, volumes=None, start="2024-01-01"):
    """构造单股 OHLCV DataFrame, 默认 volume=1e6。"""
    n = len(closes)
    dates = pd.date_range(start, periods=n, freq="D")
    closes_arr = np.array(closes, dtype=float)
    if volumes is None:
        volumes_arr = np.full(n, 1e6)
    else:
        volumes_arr = np.array(volumes, dtype=float)
    opens = np.concatenate([[closes_arr[0]], closes_arr[:-1]])
    highs = np.maximum(opens, closes_arr) + 0.05
    lows = np.minimum(opens, closes_arr) - 0.05
    df = pd.DataFrame({
        "open": opens, "high": highs, "low": lows,
        "close": closes_arr, "volume": volumes_arr,
    }, index=dates)
    return df


def _run_screener(market_data, dates_to_scan, **params):
    """辅助: 用默认参数构造 screener 并扫描。"""
    screener = HotMoneyScreener(**params)
    return screener.scan(market_data, dates_to_scan)


def test_breakout_signal_detected():
    """放量起涨: 最后一日大涨+放量+突破20日高点 → 应被选中。"""
    closes = [10.0] * 100
    closes[-1] = 11.0
    volumes = [1e6] * 100
    volumes[-1] = 5e6
    df = _make_market("000001", closes, volumes)
    market = {"000001": df}
    scan_date = df.index[-1].date()
    result = _run_screener(market, [scan_date])
    assert scan_date in result
    picks = result[scan_date]
    assert len(picks) == 1
    sym, score, sig_type = picks[0]
    assert sym == "000001"
    assert sig_type == "breakout"
    assert score > 0


def test_breakout_rejected_low_volume():
    """量比不足（<2）的涨幅不应触发放量起涨。"""
    closes = [10.0] * 100
    closes[-1] = 11.0
    volumes = [1e6] * 100
    volumes[-1] = 1.5e6  # 量比 1.5 < 2
    df = _make_market("000002", closes, volumes)
    market = {"000002": df}
    scan_date = df.index[-1].date()
    result = _run_screener(market, [scan_date])
    assert result.get(scan_date, []) == []


def test_breakout_rejected_below_trend_ma():
    """远在 60 日均线下方的反弹不应触发（排除下降趋势）。"""
    closes = np.linspace(15, 8, 100).tolist()
    closes[-1] = 8.4
    volumes = [1e6] * 100
    volumes[-1] = 5e6
    df = _make_market("000003", closes, volumes)
    market = {"000003": df}
    scan_date = df.index[-1].date()
    result = _run_screener(market, [scan_date])
    assert result.get(scan_date, []) == []


def test_reversal_signal_detected():
    """首阴反包: 前10天有2天大涨 → 首阴 → 次日反包 → 应选中。"""
    closes = [10.0] * 100
    closes[90] = 10.5  # +5%
    closes[91] = 10.5
    closes[92] = 11.03  # +5% from 10.5 (≥5%)
    closes[93] = 11.0
    closes[94] = 11.0
    closes[95] = 11.0
    closes[96] = 11.0
    closes[97] = 11.0
    closes[98] = 10.67  # 首阴: -3%
    closes[99] = 11.20  # 反包: +5%
    df = _make_market("000004", closes)
    market = {"000004": df}
    scan_date = df.index[-1].date()
    result = _run_screener(market, [scan_date])
    picks = result.get(scan_date, [])
    assert len(picks) == 1
    sym, score, sig_type = picks[0]
    assert sym == "000004"
    assert sig_type == "reversal"


def test_max_picks_limit():
    """多只票触发时应按 score 降序只取 max_picks 只。"""
    market = {}
    dates_to_scan = None
    for i, gain in enumerate([0.06, 0.08, 0.10]):
        sym = f"00000{i + 1}"
        closes = [10.0] * 100
        closes[-1] = 10.0 * (1 + gain)
        volumes = [1e6] * 100
        volumes[-1] = 5e6
        market[sym] = _make_market(sym, closes, volumes)
        if dates_to_scan is None:
            dates_to_scan = [market[sym].index[-1].date()]
    result = _run_screener(market, dates_to_scan, max_picks=2)
    picks = result[dates_to_scan[0]]
    assert len(picks) == 2
    assert picks[0][1] >= picks[1][1]


def test_excludes_short_history():
    """上市不足 min_history_days 的票应被排除。"""
    closes = [10.0, 11.0]  # 仅 2 天, 不足 60
    volumes = [1e6, 5e6]
    df = _make_market("000009", closes, volumes)
    market = {"000009": df}
    scan_date = df.index[-1].date()
    result = _run_screener(market, [scan_date])
    assert result.get(scan_date, []) == []


# ============================================================
# 端到端: run_screener_backtest 集成测试（合成数据, 临时缓存）
# ============================================================
import os
import tempfile
from datetime import date as _date


def _seed_parquet(symbol, df, data_dir):
    """把合成 df 写入临时 parquet 缓存目录, 供 LocalDataSource 读取。"""
    out = pd.DataFrame({
        "symbol": symbol,
        "date": df.index,
        "open": df["open"].values,
        "high": df["high"].values,
        "low": df["low"].values,
        "close": df["close"].values,
        "volume": df["volume"].values,
        "amount": df["volume"].values * df["close"].values,
    })
    out["date"] = pd.to_datetime(out["date"])
    os.makedirs(data_dir, exist_ok=True)
    out.to_parquet(os.path.join(data_dir, f"{symbol}.parquet"), index=False)


def test_run_screener_backtest_end_to_end(monkeypatch):
    """用合成数据走通: 选股 → 回测 → 汇总。"""
    from autotrade.dataSources.local_ds import LocalDataSource as _LocalDS

    tmp = tempfile.mkdtemp()
    # 构造 2 只票: 000001 触发放量起涨, 000002 平淡不触发
    closes_a = [10.0] * 100
    closes_a[-1] = 11.0
    volumes_a = [1e6] * 100
    volumes_a[-1] = 5e6
    df_a = _make_market("000001", closes_a, volumes_a)
    _seed_parquet("000001", df_a, tmp)

    df_b = _make_market("000002", [10.0] * 100, [1e6] * 100)
    _seed_parquet("000002", df_b, tmp)

    # 让所有 LocalDataSource 都用临时目录
    def _local_ds_factory(data_dir="data/daily"):
        return _LocalDS(data_dir=tmp)

    monkeypatch.setattr(
        "autotrade.core.engine.LocalDataSource",
        _local_ds_factory,
    )
    # analyze_stock 通过 build_datasource_from_name 获取数据源,
    # 它内部 build_failover_datasource 会尝试 local→tushare→akshare。
    # 我们直接 patch 整个 build_datasource_from_name 返回 local。
    from autotrade.core import engine as engine_mod
    monkeypatch.setattr(
        engine_mod,
        "build_datasource_from_name",
        lambda name=None, config=None: _LocalDS(data_dir=tmp),
    )

    from autotrade.core.engine import run_screener_backtest

    start = _date(2024, 1, 1)
    end = _date(2024, 4, 15)
    summary = run_screener_backtest(
        screener_name="hot_money_screener",
        strategy_name="hot_money",
        start=start, end=end,
        symbols=["000001", "000002"],
        reporter_names=(),
    )

    assert "error" not in summary
    assert summary["selection_count"] >= 1
    syms = [r["symbol"] for r in summary["results"]]
    assert "000001" in syms
