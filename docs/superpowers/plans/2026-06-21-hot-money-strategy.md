# 游资超短线策略 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现游资超短线趋势策略(Screener 选股 + Strategy 三闸门择时),目标 60% 胜率 + 20% 整体平均收益。

**Architecture:** 两层式 —— 新增 `Screener` 插件类做全市场横向选股(放量起涨+首阴反包),复用现有 `Strategy`/`Backtester` 做单股择时(三闸门出场)。新增 `run_screener_backtest()` 编排函数串联两层,不改 `Backtester` 核心。

**Tech Stack:** Python 3, pandas, pandas_ta, pytest, pyyaml, parquet(本地数据)

**Spec:** `docs/superpowers/specs/2026-06-21-hot-money-strategy-design.md`

---

## File Structure

| 文件 | 责任 | 动作 |
|---|---|---|
| `autotrade/core/interfaces.py` | 新增 `Screener` 抽象基类 | 改 |
| `autotrade/registry.py` | 新增 Screener 注册表 + 自动发现 | 改 |
| `autotrade/screens/__init__.py` | 包初始化 | 新 |
| `autotrade/screens/hot_money.py` | 游资选股:放量起涨+首阴反包 | 新 |
| `autotrade/strategies/hot_money.py` | 三闸门出场状态机 | 新 |
| `autotrade/core/engine.py` | 新增 `run_screener_backtest()` | 改 |
| `config/strategies/hot_money.yaml` | Strategy 三闸门阈值 | 新 |
| `config/screens/hot_money.yaml` | Screener 形态阈值 | 新 |
| `tests/unit/test_hot_money.py` | Screener + Strategy 单元测试 | 新 |

**现有接口契约(不可破坏):**
- `Strategy.__init__(self)` 在基类中存在,子类构造可加参数(见 `trend_ma_breakout.py:47`、`macd_divergence.py:30`)。
- `Strategy.generate_signals(df) -> list[Signal]`,引擎会自动填充 `signal.symbol`(见 `engine.py:78-80`)。
- `_instantiate_strategy(strategy_cls, params)` 支持 `strategy_cls(**params)`(见 `engine.py:251-255`)。
- `_split_cycles(trades)` 按持仓周期拆分计算胜率(见 `backtester.py:209-238`)。
- 注册表通过 `pkgutil.iter_modules` 自动发现包目录下所有非抽象子类(见 `registry.py:36-57`)。
- 信号 `date` 字段:若 df.index 是 `DatetimeIndex`,循环里 `df.index[idx]` 是 `pd.Timestamp`;Strategy 内部要兼容。

---

## Task 1: 新增 Screener 抽象基类

**Files:**
- Modify: `autotrade/core/interfaces.py`

- [ ] **Step 1: 在 interfaces.py 末尾追加 Screener 抽象基类**

在 `autotrade/core/interfaces.py` 文件**末尾**(Reporter 类之后)追加:

```python
class Screener(ABC):
    """选股筛网插件:横向比较全市场,每日选出候选票。

    与 Strategy 的区别:
    - Strategy 是"给定一只票在其上择时"(纵向),接收单股 df。
    - Screener 是"比较全市场挑出当日候选"(横向),接收 {symbol: df} 字典。
    - 职责切分:Screener 答"今天买谁",Strategy 答"买了什么时候卖"。
    """

    name: str = "base"
    required_indicators: list[Indicator] = []

    def __init__(self):
        self.required_indicators = []

    @abstractmethod
    def scan(self, market_data: dict[str, pd.DataFrame],
             dates: list[date]) -> dict[date, list[tuple[str, float, str]]]:
        """扫描全市场,逐日选出候选票。

        Args:
            market_data: {symbol: OHLCV DataFrame},每个 df 已算好 required_indicators。
                每个 DataFrame 的 index 为日期(DatetimeIndex 或 date 序列),
                含 open/high/low/close/volume 列 + ind_xxx 指标列。
            dates: 待扫描的交易日列表(升序)。

        Returns:
            {date: [(symbol, score, signal_type), ...]}
            每日按 score 降序排列的候选列表,signal_type 为 "breakout"/"reversal"。
        """
```

- [ ] **Step 2: 在 interfaces.py 顶部补全 date 导入**

检查文件顶部 `from datetime import date` 是否存在;若 `date` 未导入,补上。当前文件第 6 行已有 `from datetime import date`,无需改动 —— 先读文件确认。

- [ ] **Step 3: 验证语法**

Run: `python -c "from autotrade.core.interfaces import Screener; print('OK')"`
Expected: 输出 `OK`

- [ ] **Step 4: Commit**

```bash
git add autotrade/core/interfaces.py
git commit -m "feat: add Screener abstract base class for cross-market stock screening"
```

---

## Task 2: 注册表支持 Screener 自动发现

**Files:**
- Modify: `autotrade/registry.py`

- [ ] **Step 1: 写失败测试 —— 注册表能发现 Screener**

Create `tests/unit/test_screener_registry.py`:

```python
"""Screener 注册表测试。"""
import importlib
import sys


def test_screener_registry_discovers_plugins():
    """注册表应能自动发现 autotrade.screens 包下的 Screener 子类。"""
    # 先确保包可被导入(后续 Task 会创建真实 screener)
    # 这里只验证 registry 接口存在且不报错
    from autotrade.registry import _screens, init_registry
    init_registry(force=True)
    # _screens 应该是 dict
    assert isinstance(_screens, dict)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/unit/test_screener_registry.py -v`
Expected: FAIL —— `ImportError: cannot import name '_screens'`

- [ ] **Step 3: 实现 —— registry.py 增加 Screener 支持**

在 `autotrade/registry.py` 中,做以下**三处**修改:

**(a) 导入 Screener 并新增存储 dict**(修改第 15 行附近):

把
```python
from autotrade.core.interfaces import DataSource, Indicator, Reporter, Strategy
```
改为:
```python
from autotrade.core.interfaces import (
    DataSource, Indicator, Reporter, Screener, Strategy,
)
```

在第 21 行 `_reporters: dict[str, type[Reporter]] = {}` **之后**新增:
```python
_screens: dict[str, type[Screener]] = {}
```

**(b) init_registry 清空 + 发现 screens**(修改 `init_registry` 函数,约第 60-76 行):

在 `_reporters.clear()` 之后新增 `_screens.clear()`;
在 `_discover_plugins("autotrade.reporters", Reporter, _reporters)` 之后新增:
```python
    _discover_plugins("autotrade.screens", Screener, _screens)
```

**(c) 新增 register/get/list 函数**(在文件末尾,`get_all_strategies` 之后追加):

```python
def register_screener(name: str, cls: type[Screener]) -> None:
    _screens[name] = cls


def get_screener(name: str) -> type[Screener]:
    if not _initialized:
        init_registry()
    if name not in _screens:
        raise KeyError(
            f"Screener '{name}' not found. Available: {list(_screens)}"
        )
    return _screens[name]


def list_screens() -> list[str]:
    if not _initialized:
        init_registry()
    return list(_screens)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/unit/test_screener_registry.py -v`
Expected: PASS

- [ ] **Step 5: 验证现有注册表测试未破坏**

Run: `python -m pytest tests/unit/test_registry.py -v`
Expected: PASS(所有原有测试通过)

- [ ] **Step 6: Commit**

```bash
git add autotrade/registry.py tests/unit/test_screener_registry.py
git commit -m "feat: add Screener registry support with auto-discovery"
```

---

## Task 3: HotMoneyStrategy 三闸门状态机(TDD)

这是 §3 的核心。先写策略,因为它最独立(只依赖 close + 状态),且 Screener 产出的 `allowed_entry_dates` 是它的输入。

**Files:**
- Create: `autotrade/strategies/hot_money.py`
- Test: `tests/unit/test_hot_money.py`(本任务只写 Strategy 部分)

- [ ] **Step 1: 写失败测试 —— 三闸门各触发一次**

Create `tests/unit/test_hot_money.py`:

```python
"""游资策略单元测试:三闸门出场状态机。"""
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from autotrade.strategies.hot_money import HotMoneyStrategy


def _make_bar_df(closes, start="2024-01-01"):
    """构造 OHLCV DataFrame,index 为日期,close 按给定序列。

    open=close, high=close+0.1, low=close-0.1, volume=1e6。
    """
    dates = pd.date_range(start, periods=len(closes), freq="D")
    closes = np.array(closes, dtype=float)
    df = pd.DataFrame({
        "open": closes,
        "high": closes + 0.1,
        "low": closes - 0.1,
        "close": closes,
        "volume": 1e6,
    }, index=dates)
    return df


# ---------- 闸门3:硬止损 -5% ----------
def test_hard_stop_loss():
    """进场后跌破 -5% 应触发硬止损 SELL。"""
    df = _make_bar_df([10.0, 9.4, 9.0])  # 进场后 -6%
    entry_dates = [df.index[0].date()]
    strat = HotMoneyStrategy(allowed_entry_dates=entry_dates)
    sigs = strat.generate_signals(df)
    actions = [(s.action, s.date, s.reason) for s in sigs]
    # 应有 BUY(第0天) + SELL(止损)
    assert any(a == "BUY" for a, _, _ in actions)
    sell_reasons = [r for a, _, r in actions if a == "SELL"]
    assert any("止损" in r for r in sell_reasons)


# ---------- 闸门2:时间止损(3天未达+3%) ----------
def test_time_stop():
    """持仓 3 天且收益 < +3% 应触发时间止损。"""
    # 进场 10.0,之后横盘微跌,第3天(close≈10.0,收益 0% < 3%)
    df = _make_bar_df([10.0, 10.0, 10.0, 10.0, 10.0])
    entry_dates = [df.index[0].date()]
    strat = HotMoneyStrategy(allowed_entry_dates=entry_dates)
    sigs = strat.generate_signals(df)
    sell_reasons = [s.reason for s in sigs if s.action == "SELL"]
    assert any("时间" in r for r in sell_reasons)


# ---------- 闸门1:移动止盈(+8%启动,回撤3%) ----------
def test_trailing_take_profit():
    """涨到 +8% 后回撤 3% 应触发移动止盈。"""
    # 进场 10.0 → 涨到 10.9(+9%,触发启动)→ 回撤到 10.5(回撤约 3.7%)
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
    entry_dates = []  # 空,任何日子都不进场
    strat = HotMoneyStrategy(allowed_entry_dates=entry_dates)
    sigs = strat.generate_signals(df)
    assert all(s.action != "BUY" for s in sigs)


# ---------- 阈值可配置 ----------
def test_custom_thresholds():
    """自定义阈值应生效:把 stop_loss 调到 -2%,轻微下跌即止损。"""
    df = _make_bar_df([10.0, 9.7, 9.5])  # 第1天 -3%
    entry_dates = [df.index[0].date()]
    strat = HotMoneyStrategy(
        allowed_entry_dates=entry_dates, stop_loss=0.02,
    )
    sigs = strat.generate_signals(df)
    sell_reasons = [s.reason for s in sigs if s.action == "SELL"]
    assert any("止损" in r for r in sell_reasons)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/unit/test_hot_money.py -v`
Expected: FAIL —— `ModuleNotFoundError: No module named 'autotrade.strategies.hot_money'`

- [ ] **Step 3: 实现 HotMoneyStrategy**

Create `autotrade/strategies/hot_money.py`:

```python
"""游资超短线择时策略 — 三闸门出场状态机。

本策略是"选股后择时"架构的第二层,只负责被选中后的进出场:
- 进场:仅在 allowed_entry_dates(由 Screener 选出的日期)发 BUY,满仓。
- 出场:三道闸门任一触发即清仓(快速止盈 + 严格止损)。

三闸门(任一触发即 SELL):
  闸门1 移动止盈: 最高涨幅≥trailing_activate 后,
                  从最高点回撤≥trailing_drawdown 即锁利。
  闸门2 时间止损: 持仓满 time_stop_days 且收益<time_stop_min_gain 即离场。
  闸门3 硬止损:   收益≤-stop_loss 即清仓。

注意:进场形态判断(放量起涨/首阴反包)在 Screener 层完成,
      本策略不重算,required_indicators 为空(只需 close + 状态)。

设计详见 docs/superpowers/specs/2026-06-21-hot-money-strategy-design.md §4。
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from autotrade.core.interfaces import Strategy
from autotrade.core.models import Signal


class HotMoneyStrategy(Strategy):
    """游资超短线:三闸门出场状态机。"""

    name = "hot_money"

    def __init__(
        self,
        allowed_entry_dates: list[date] | None = None,
        trailing_activate: float = 0.08,
        trailing_drawdown: float = 0.03,
        time_stop_days: int = 3,
        time_stop_min_gain: float = 0.03,
        stop_loss: float = 0.05,
    ):
        self.allowed_entry_dates = set(allowed_entry_dates or [])
        self.trailing_activate = trailing_activate
        self.trailing_drawdown = trailing_drawdown
        self.time_stop_days = time_stop_days
        self.time_stop_min_gain = time_stop_min_gain
        self.stop_loss = stop_loss
        self.name = "hot_money"
        # 三闸门只需 close + 状态,无需指标
        self.required_indicators = []

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        signals: list[Signal] = []
        if "close" not in df.columns:
            return signals

        # 持仓状态
        entry_price: float | None = None
        entry_idx: int = 0
        highest_price: float = 0.0
        trailing_active: bool = False

        for idx in range(len(df)):
            current_close = float(df.iloc[idx]["close"])
            if pd.isna(current_close):
                continue
            current_date = df.index[idx]
            # df.index 可能是 DatetimeIndex(Timestamp)或 date
            today = current_date.date() if hasattr(current_date, "date") else current_date

            in_position = entry_price is not None

            # ---- 空仓:检查是否在允许进场日 ----
            if not in_position:
                if today in self.allowed_entry_dates:
                    signals.append(Signal(
                        symbol="",
                        date=current_date,
                        action="BUY",
                        strength=1.0,
                        reason="游资信号进场",
                    ))
                    entry_price = current_close
                    entry_idx = idx
                    highest_price = current_close
                    trailing_active = False
                    # 进场当天不立即检查出场,继续下一日
                    continue

            # ---- 持仓:检查三闸门 ----
            if in_position:
                # 更新最高价
                if current_close > highest_price:
                    highest_price = current_close

                gain = (current_close - entry_price) / entry_price
                highest_gain = (highest_price - entry_price) / entry_price
                days_held = idx - entry_idx

                # 闸门1 启动条件:最高涨幅达标
                if highest_gain >= self.trailing_activate:
                    trailing_active = True

                # 闸门3:硬止损(最高优先级,先判断)
                if gain <= -self.stop_loss:
                    signals.append(Signal(
                        symbol="",
                        date=current_date,
                        action="SELL",
                        strength=1.0,
                        reason=f"硬止损({gain:.1%})",
                    ))
                    entry_price = None
                    highest_price = 0.0
                    trailing_active = False
                    continue

                # 闸门1:移动止盈(已启动且回撤达标)
                if trailing_active:
                    drawdown_from_high = (current_close - highest_price) / highest_price
                    if drawdown_from_high <= -self.trailing_drawdown:
                        signals.append(Signal(
                            symbol="",
                            date=current_date,
                            action="SELL",
                            strength=1.0,
                            reason=f"移动止盈(+{highest_gain:.1%}→{gain:.1%})",
                        ))
                        entry_price = None
                        highest_price = 0.0
                        trailing_active = False
                        continue

                # 闸门2:时间止损
                if days_held >= self.time_stop_days and gain < self.time_stop_min_gain:
                    signals.append(Signal(
                        symbol="",
                        date=current_date,
                        action="SELL",
                        strength=1.0,
                        reason=f"时间止损({days_held}天 +{gain:.1%})",
                    ))
                    entry_price = None
                    highest_price = 0.0
                    trailing_active = False
                    continue

        return signals
```

- [ ] **Step 4: 运行测试确认通过**

Run: `python -m pytest tests/unit/test_hot_money.py -v`
Expected: 5 个测试全部 PASS

**注意**:如果 `test_trailing_take_profit` 失败,检查三闸门优先级 —— 硬止损必须先于移动止盈判断,因为涨到 +9% 后回撤到 +5% 时,gain=+5% > -5%,不会触发硬止损,逻辑正确。若失败,审查 `highest_gain` 与 `trailing_active` 的交互。

- [ ] **Step 5: 确认策略被注册表发现**

Run:
```
python -c "from autotrade.registry import init_registry, list_strategies; init_registry(force=True); print('hot_money' in list_strategies())"
```
Expected: `True`

- [ ] **Step 6: Commit**

```bash
git add autotrade/strategies/hot_money.py tests/unit/test_hot_money.py
git commit -m "feat: add HotMoneyStrategy three-gate exit state machine"
```

---

## Task 4: HotMoneyScreener 选股筛网(TDD)

实现 §3 的两个信号源 + 强度排序。这是策略最复杂的部分,分多个测试驱动。

**Files:**
- Create: `autotrade/screens/__init__.py`
- Create: `autotrade/screens/hot_money.py`
- Test: append to `tests/unit/test_hot_money.py`

- [ ] **Step 1: 写失败测试 —— 信号源1放量起涨被识别**

在 `tests/unit/test_hot_money.py` **末尾**追加测试:

```python
# ============================================================
# Screener 测试
# ============================================================
from autotrade.screens.hot_money import HotMoneyScreener


def _make_market(symbol, closes, volumes=None, start="2024-01-01"):
    """构造单股 OHLCV DataFrame,默认 volume=1e6。"""
    n = len(closes)
    dates = pd.date_range(start, periods=n, freq="D")
    closes = np.array(closes, dtype=float)
    if volumes is None:
        volumes = np.full(n, 1e6)
    else:
        volumes = np.array(volumes, dtype=float)
    # open=前一日close(近似),high/low 包裹实体
    opens = np.concatenate([[closes[0]], closes[:-1]])
    highs = np.maximum(opens, closes) + 0.05
    lows = np.minimum(opens, closes) - 0.05
    df = pd.DataFrame({
        "open": opens, "high": highs, "low": lows,
        "close": closes, "volume": volumes,
    }, index=dates)
    return df


def _run_screener(market_data, dates_to_scan, **params):
    """辅助:用默认参数构造 screener 并扫描。"""
    screener = HotMoneyScreener(**params)
    return screener.scan(market_data, dates_to_scan)


def test_breakout_signal_detected():
    """放量起涨:最后一日大涨+放量+突破20日高点 → 应被选中。"""
    # 60 天平稳在 10 元附近(volume=1e6),最后一日放量涨到 11(+10%,量比=5)
    closes = [10.0] * 60
    closes[-1] = 11.0
    volumes = [1e6] * 60
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
    """量比不足(<2)的涨幅不应触发放量起涨。"""
    closes = [10.0] * 60
    closes[-1] = 11.0
    volumes = [1e6] * 60
    volumes[-1] = 1.5e6  # 量比 1.5 < 2
    df = _make_market("000002", closes, volumes)
    market = {"000002": df}
    scan_date = df.index[-1].date()
    result = _run_screener(market, [scan_date])
    # 不应被选中(该日 result 为空列表或该 date 不在 result 中)
    assert result.get(scan_date, []) == []


def test_breakout_rejected_below_trend_ma():
    """远在 60 日均线下方的反弹不应触发(排除下降趋势)。"""
    # 前 60 天从 15 一路跌到 8,最后一日反弹到 8.4(+5%),但仍远低于 MA60
    closes = np.linspace(15, 8, 60).tolist()
    closes[-1] = 8.4
    volumes = [1e6] * 60
    volumes[-1] = 5e6
    df = _make_market("000003", closes, volumes)
    market = {"000003": df}
    scan_date = df.index[-1].date()
    result = _run_screener(market, [scan_date])
    assert result.get(scan_date, []) == []


def test_reversal_signal_detected():
    """首阴反包:前 10 天有 2 天大涨 → 首阴 → 次日反包 → 应选中。"""
    # 构造:平稳 → 第50、52天大涨(+5%) → 第58天首阴(-3%) → 第59天反包(+5%)
    closes = [10.0] * 60
    closes[50] = 10.5  # +5%
    closes[51] = 10.5
    closes[52] = 11.0  # 约 +4.8%
    closes[53] = 11.0
    closes[58] = 10.67  # 首阴:-3%
    closes[59] = 11.20  # 反包:+5%
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
    # 构造 3 只都触发放量起涨的票,不同涨幅
    for i, gain in enumerate([0.06, 0.08, 0.10]):
        sym = f"00000{i+1}"
        closes = [10.0] * 60
        closes[-1] = 10.0 * (1 + gain)
        volumes = [1e6] * 60
        volumes[-1] = 5e6
        market[sym] = _make_market(sym, closes, volumes)
        if dates_to_scan is None:
            dates_to_scan = [market[sym].index[-1].date()]
    result = _run_screener(market, dates_to_scan, max_picks=2)
    picks = result[dates_to_scan[0]]
    assert len(picks) == 2
    # score 应降序
    assert picks[0][1] >= picks[1][1]


def test_excludes_short_history():
    """上市不足 min_history_days 的票应被排除。"""
    closes = [10.0, 11.0]  # 仅 2 天,不足 60
    volumes = [1e6, 5e6]
    df = _make_market("000009", closes, volumes)
    market = {"000009": df}
    scan_date = df.index[-1].date()
    result = _run_screener(market, [scan_date])
    assert result.get(scan_date, []) == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `python -m pytest tests/unit/test_hot_money.py -v -k "breakout or reversal or max_picks or short_history"`
Expected: FAIL —— `ModuleNotFoundError: No module named 'autotrade.screens'`

- [ ] **Step 3: 创建 screens 包初始化文件**

Create `autotrade/screens/__init__.py`:

```python
"""选股筛网插件 —— 横向比较全市场,每日选出候选票。"""
from autotrade.registry import (
    get_screener, list_screens, register_screener,
)
```

- [ ] **Step 4: 实现 HotMoneyScreener**

Create `autotrade/screens/hot_money.py`:

```python
"""游资选股筛网 — 放量起涨 + 首阴反包。

两个信号源,任一触发即入选:
  信号1 放量起涨(Volume Breakout): 大涨 + 放量 + 突破近期高点 + 多头位置。
  信号2 首阴反包(First-Yin Reversal): 强势股首次回调收阴后,次日大阳反包。

逐日扫描全市场,按强度评分降序取前 max_picks 只。

设计详见 docs/superpowers/specs/2026-06-21-hot-money-strategy-design.md §3。
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from autotrade.core.interfaces import Screener


def _sma(series: pd.Series, period: int) -> pd.Series:
    """简单移动平均(不依赖外部库)。"""
    return series.rolling(window=period, min_periods=period).mean()


class HotMoneyScreener(Screener):
    """游资选股:放量起涨 + 首阴反包。"""

    name = "hot_money_screener"

    def __init__(
        self,
        max_picks: int = 8,
        ma_period: int = 20,
        trend_ma_period: int = 60,
        breakout_lookback: int = 20,
        breakout_min_gain: float = 0.05,
        breakout_volume_ratio: float = 2.0,
        breakout_min_body: float = 0.03,
        reversal_lookback_strong_days: int = 10,
        reversal_strong_count: int = 2,
        reversal_strong_gain: float = 0.05,
        reversal_first_yin_drop: float = 0.02,
        reversal_gain: float = 0.03,
        exclude_min_history_days: int = 60,
    ):
        self.max_picks = max_picks
        self.ma_period = ma_period
        self.trend_ma_period = trend_ma_period
        self.breakout_lookback = breakout_lookback
        self.breakout_min_gain = breakout_min_gain
        self.breakout_volume_ratio = breakout_volume_ratio
        self.breakout_min_body = breakout_min_body
        self.reversal_lookback_strong_days = reversal_lookback_strong_days
        self.reversal_strong_count = reversal_strong_count
        self.reversal_strong_gain = reversal_strong_gain
        self.reversal_first_yin_drop = reversal_first_yin_drop
        self.reversal_gain = reversal_gain
        self.exclude_min_history_days = exclude_min_history_days
        self.name = "hot_money_screener"
        # Screener 内部自算 MA/量比,不依赖引擎预计算(因为要批量横向比较)
        self.required_indicators = []

    def scan(
        self,
        market_data: dict[str, pd.DataFrame],
        dates: list[date],
    ) -> dict[date, list[tuple[str, float, str]]]:
        """逐日扫描,返回每日候选(按 score 降序)。"""
        result: dict[date, list[tuple[str, float, str]]] = {}

        for scan_date in dates:
            candidates: list[tuple[str, float, str]] = []
            for symbol, df in market_data.items():
                scored = self._evaluate(symbol, df, scan_date)
                if scored is not None:
                    candidates.append(scored)
            # 按 score 降序,取前 max_picks
            candidates.sort(key=lambda x: x[1], reverse=True)
            result[scan_date] = candidates[: self.max_picks]

        return result

    def _evaluate(
        self, symbol: str, df: pd.DataFrame, scan_date: date,
    ) -> tuple[str, float, str] | None:
        """评估单只票在 scan_date 的信号。返回 (symbol, score, type) 或 None。"""
        if len(df) < self.exclude_min_history_days:
            return None

        # 定位 scan_date 在 df 中的位置
        idx = self._index_of_date(df, scan_date)
        if idx is None or idx < 1:
            return None

        close = df["close"]
        open_ = df["open"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        # 当日数据(用 iloc,避免索引歧义)
        c_today = float(close.iloc[idx])
        c_prev = float(close.iloc[idx - 1])
        o_today = float(open_.iloc[idx])
        h_today = float(high.iloc[idx])
        l_today = float(low.iloc[idx])
        v_today = float(volume.iloc[idx])

        # ---- 排除项:停牌(volume==0)、一字板 ----
        if v_today <= 0:
            return None
        body_range = (h_today - l_today) / c_prev if c_prev > 0 else 0
        is_one_word = abs(h_today - l_today) < 1e-6
        if is_one_word:
            return None

        # ---- 信号1:放量起涨 ----
        breakout = self._check_breakout(
            c_today, c_prev, o_today, h_today, l_today, v_today,
            high, volume, close, idx,
        )
        if breakout is not None:
            return (symbol, breakout, "breakout")

        # ---- 信号2:首阴反包 ----
        reversal = self._check_reversal(
            close, open_, volume, idx,
        )
        if reversal is not None:
            return (symbol, reversal, "reversal")

        return None

    def _check_breakout(
        self, c_today, c_prev, o_today, h_today, l_today, v_today,
        high_series, volume_series, close_series, idx,
    ) -> float | None:
        """信号1:放量起涨。返回 score 或 None。"""
        gain = (c_today - c_prev) / c_prev if c_prev > 0 else 0
        # C1 涨幅
        if gain < self.breakout_min_gain:
            return None
        # C2 量比(当日量 / 过去 ma_period 均量)
        vol_start = max(0, idx - self.ma_period)
        vol_ma = float(volume_series.iloc[vol_start:idx].mean()) if idx > 0 else 0
        if vol_ma <= 0:
            return None
        vol_ratio = v_today / vol_ma
        if vol_ratio < self.breakout_volume_ratio:
            return None
        # C3 突破近 breakout_lookback 日最高价(不含当日)
        lb_start = max(0, idx - self.breakout_lookback)
        recent_high = float(high_series.iloc[lb_start:idx].max())
        if c_today <= recent_high:
            return None
        # C4 位置:close ≥ MA(trend_ma_period) × 0.95
        if idx < self.trend_ma_period:
            return None
        trend_ma = float(close_series.iloc[idx - self.trend_ma_period:idx].mean())
        if trend_ma <= 0:
            return None
        if c_today < trend_ma * 0.95:
            return None
        # C5 非一字(实体幅度)
        body = (h_today - l_today) / c_prev if c_prev > 0 else 0
        if body < self.breakout_min_body:
            return None

        # 强度评分:涨幅×0.5 + 量比×0.3 + 突破力度×0.2
        breakout_strength = (c_today - recent_high) / recent_high if recent_high > 0 else 0
        score = gain * 0.5 + min(vol_ratio, 5.0) * 0.3 + breakout_strength * 0.2
        return score

    def _check_reversal(
        self, close_series, open_series, volume_series, idx,
    ) -> float | None:
        """信号2:首阴反包。scan_date=idx 当天是反包日,idx-1 是首阴日。"""
        if idx < self.reversal_lookback_strong_days + 1:
            return None

        # 反包日(今天)= idx
        c_today = float(close_series.iloc[idx])
        c_prev = float(close_series.iloc[idx - 1])
        o_today = float(open_series.iloc[idx])
        o_prev = float(open_series.iloc[idx - 1])
        v_today = float(volume_series.iloc[idx])
        v_prev = float(volume_series.iloc[idx - 1])

        # C3 反包:今日收阳且涨幅 ≥ reversal_gain,且收盘 ≥ 昨日实体顶部
        reversal_gain = (c_today - c_prev) / c_prev if c_prev > 0 else 0
        yesterday_body_top = max(o_prev, c_prev)
        if reversal_gain < self.reversal_gain:
            return None
        if c_today < yesterday_body_top:
            return None
        if c_today <= o_today:
            return None  # 必须收阳

        # C2 首阴:昨日收阴且跌幅 ≥ first_yin_drop
        yin_drop = (c_prev - o_prev) / o_prev if o_prev > 0 else 0
        if o_prev <= c_prev:
            return None  # 昨日不是阴线
        if yin_drop < self.reversal_first_yin_drop:
            return None

        # C4 量能:今日量 ≥ 昨日量
        if v_today < v_prev:
            return None

        # C1 前置强势:过去 lookback_strong_days 天内(不含首阴和反包日)
        #    至少 strong_count 天涨幅 ≥ strong_gain
        lookback_start = idx - self.reversal_lookback_strong_days - 1
        lookback_end = idx - 1  # 不含首阴日(idx-1)?——含 idx-1 之前的窗口
        # 窗口:[idx-lookback_strong_days-1, idx-2],即首阴前 N 天
        win_start = max(0, idx - self.reversal_lookback_strong_days - 1)
        win_end = idx - 1  # 首阴日(idx-1)本身不算强势日
        strong_days = 0
        for j in range(win_start, win_end):
            if j < 1:
                continue
            d_gain = (float(close_series.iloc[j]) - float(close_series.iloc[j - 1])) / float(close_series.iloc[j - 1])
            if d_gain >= self.reversal_strong_gain:
                strong_days += 1
        if strong_days < self.reversal_strong_count:
            return None

        # C5 位置:今日 close ≥ MA(ma_period)
        if idx < self.ma_period:
            return None
        ma = float(close_series.iloc[idx - self.ma_period:idx].mean())
        if c_today < ma:
            return None

        # 强度评分:反包涨幅×0.5 + 前置强势度×0.3 + 量能×0.2
        strength_ratio = v_today / v_prev if v_prev > 0 else 1
        score = reversal_gain * 0.5 + min(strong_days / 3, 1) * 0.3 + min(strength_ratio, 2) * 0.2
        return score

    @staticmethod
    def _index_of_date(df: pd.DataFrame, target: date) -> int | None:
        """在 df.index 中定位 target date。兼容 Timestamp/date 索引。"""
        idx_arr = df.index
        for i, val in enumerate(idx_arr):
            d = val.date() if hasattr(val, "date") else val
            if d == target:
                return i
        return None
```

- [ ] **Step 5: 运行 Screener 测试确认通过**

Run: `python -m pytest tests/unit/test_hot_money.py -v -k "breakout or reversal or max_picks or short_history"`
Expected: 6 个测试全部 PASS

- [ ] **Step 6: 验证 Screener 被注册表发现**

Run:
```
python -c "from autotrade.registry import init_registry, list_screens; init_registry(force=True); print('hot_money_screener' in list_screens())"
```
Expected: `True`

- [ ] **Step 7: 运行全部 hot_money 测试确认无回归**

Run: `python -m pytest tests/unit/test_hot_money.py -v`
Expected: 全部 PASS(Strategy 5 个 + Screener 6 个)

- [ ] **Step 8: Commit**

```bash
git add autotrade/screens/__init__.py autotrade/screens/hot_money.py tests/unit/test_hot_money.py
git commit -m "feat: add HotMoneyScreener with breakout + reversal signals"
```

---

## Task 5: 配置文件

**Files:**
- Create: `config/strategies/hot_money.yaml`
- Create: `config/screens/hot_money.yaml`

- [ ] **Step 1: 创建 Strategy 配置**

Create `config/strategies/hot_money.yaml`:

```yaml
# 游资超短线策略 — 三闸门出场状态机
# 进场由 Screener 决定(allowed_entry_dates),本配置只管出场阈值。
# 阈值为初始值,后续根据回测结果调整。
strategy: hot_money
params:
  # 闸门1: 移动止盈 — 最高涨幅达阈值后,回撤指定幅度即锁利
  trailing_activate: 0.08      # 启用移动止盈的最低涨幅
  trailing_drawdown: 0.03      # 启用后从最高点回撤幅度即卖出

  # 闸门2: 时间止损 — 持仓N天未达预期收益即离场
  time_stop_days: 3            # 最大持仓天数
  time_stop_min_gain: 0.03     # N天内收益低于此值则离场

  # 闸门3: 硬止损
  stop_loss: 0.05
```

- [ ] **Step 2: 创建 Screener 配置**

Create `config/screens/hot_money.yaml`:

```yaml
# 游资选股筛网 — 放量起涨 + 首阴反包
# 形态阈值,后续根据回测调整。
screen: hot_money_screener
params:
  max_picks: 8                 # 每日最多选 N 只
  ma_period: 20                # 均线/量比周期
  trend_ma_period: 60          # 趋势过滤均线
  breakout_lookback: 20        # 突破回看天数

  # 信号1: 放量起涨
  breakout_min_gain: 0.05      # 当日最小涨幅
  breakout_volume_ratio: 2.0   # 最小量比
  breakout_min_body: 0.03      # 最小实体幅度(过滤一字板)

  # 信号2: 首阴反包
  reversal_lookback_strong_days: 10   # 前置强势回看天数
  reversal_strong_count: 2            # 该区间内≥5%涨幅天数
  reversal_strong_gain: 0.05          # 强势日涨幅阈值
  reversal_first_yin_drop: 0.02       # 首阴最小跌幅
  reversal_gain: 0.03                 # 反包日最小涨幅

  # 排除项
  exclude_min_history_days: 60        # 最少上市天数
```

- [ ] **Step 3: 验证 YAML 可被加载**

Run:
```
python -c "import yaml; s=yaml.safe_load(open('config/strategies/hot_money.yaml',encoding='utf-8')); print(s['strategy'], s['params']['stop_loss'])"
```
Expected: `hot_money 0.05`

- [ ] **Step 4: Commit**

```bash
git add config/strategies/hot_money.yaml config/screens/hot_money.yaml
git commit -m "feat: add hot_money strategy and screener config files"
```

---

## Task 6: engine.py 新增 run_screener_backtest()

这是串联两层的编排函数。复用现有 `analyze_stock()` 做单股回测。

**Files:**
- Modify: `autotrade/core/engine.py`

- [ ] **Step 1: 阅读现有 engine.py 关键函数**

先确认这些已存在的辅助(本任务复用,不重写):
- `analyze_stock(symbol, strategy_name, start, end, datasource_name, backtest_config, strategy_params, stock_name)` — 第 33 行
- `build_datasource_from_name(name)` — 从 datasource_factory 导入(第 21 行)
- `_summarize(results)` — 第 258 行
- `LocalDataSource(data_dir)` — 从 `autotrade.dataSources.local_ds` 导入

`run_screener_backtest` 逻辑:
1. 用 `LocalDataSource` 直接读 parquet(不经网络,全市场批量加载)
2. 对每只票加载 OHLCV,存入 `{symbol: df}`
3. 构造 `HotMoneyScreener`,调用 `scan(market_data, dates)`
4. 反转 selection:`{symbol: [date1, date2, ...]}`
5. 对每只选中 symbol,调用 `analyze_stock`,strategy_params 注入 `allowed_entry_dates`
6. 调用 `_summarize` 聚合

- [ ] **Step 2: 在 engine.py 顶部新增导入**

在 `autotrade/core/engine.py` 第 24 行附近(`from autotrade.core.models import ...` 之后)新增:

```python
from autotrade.dataSources.local_ds import LocalDataSource
```

并在 registry 导入块(第 25-28 行)新增:

```python
from autotrade.registry import (
    get_datasource, get_indicator, get_reporter, get_screener,
    get_strategy, init_registry, list_strategies,
)
```

(即把 `get_screener` 加入现有 import)

- [ ] **Step 3: 在 engine.py 末尾追加 run_screener_backtest 函数**

在 `autotrade/core/engine.py` **文件末尾**(`_summarize` 函数之后)追加:

```python
def _load_market_data(
    symbols: list[str],
    start: date,
    end: date,
    data_dir: str = "data/daily",
) -> dict[str, pd.DataFrame]:
    """批量加载全市场 OHLCV 到 {symbol: DataFrame}。

    直接读本地 parquet,不经网络。DataFrame index 为 DatetimeIndex。
    """
    ds = LocalDataSource(data_dir=data_dir)
    market: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        try:
            bars = ds.get_bars(sym, start, end)
            if bars:
                market[sym] = _bars_to_dataframe(bars)
        except Exception as e:
            logger.debug("加载 %s 失败: %s", sym, e)
    return market


def _load_screener_params(screener_name: str) -> dict[str, Any]:
    """加载 config/screens/<screener_name>.yaml 的参数。"""
    cfg_path = Path(__file__).resolve().parent.parent.parent / "config" / "screens" / f"{screener_name}.yaml"
    if not cfg_path.exists():
        return {}
    import yaml
    with open(cfg_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("params", {}) or {}


def _invert_selection(
    selection: dict[date, list[tuple[str, float, str]]],
) -> dict[str, list[date]]:
    """反转 {date: [(symbol,...)]} 为 {symbol: [date,...]}。"""
    inverted: dict[str, list[date]] = {}
    for d, picks in selection.items():
        for sym, _score, _type in picks:
            inverted.setdefault(sym, []).append(d)
    return inverted


def run_screener_backtest(
    screener_name: str,
    strategy_name: str,
    start: date,
    end: date,
    symbols: str | list[str] = "all",
    datasource_name: str = FAILOVER_NAME,
    screener_params: dict[str, Any] | None = None,
    strategy_params: dict[str, Any] | None = None,
    reporter_names: tuple[str, ...] = ("console",),
    stock_names: dict[str, str] | None = None,
) -> dict[str, Any]:
    """游资两段式回测:先选股,再对选中票单股择时回测。

    流程:
      1. 加载全市场 OHLCV
      2. Screener.scan() → 每日候选 {date: [(symbol, score, type)]}
      3. 反转为 {symbol: [entry_dates]}
      4. 对每只选中 symbol 调 analyze_stock(strategy_params 含 allowed_entry_dates)
      5. 聚合统计

    Args:
        screener_name: 选股筛网名(如 "hot_money_screener")。
        strategy_name: 择时策略名(如 "hot_money")。
        start/end: 回测区间。
        symbols: "all" 用全市场,或代码列表。
        screener_params: Screener 参数,None 则从 YAML 加载。
        strategy_params: Strategy 出场参数(None 则 YAML),
            allowed_entry_dates 会被自动注入(覆盖用户值)。
    """
    init_registry()

    # ---- 1. 解析 symbols + 加载全市场数据 ----
    resolved = _resolve_symbols(symbols, datasource_name)
    if not resolved:
        return {"error": "No symbols to analyze", "results": []}

    market_data = _load_market_data(resolved, start, end)
    if not market_data:
        return {"error": "No market data loaded", "results": []}

    # 交易日序列(取所有票日期的并集,升序)
    all_dates: set[date] = set()
    for df in market_data.values():
        for v in df.index:
            d = v.date() if hasattr(v, "date") else v
            all_dates.add(d)
    scan_dates = sorted(all_dates)

    # ---- 2. 选股 ----
    s_params = screener_params
    if s_params is None:
        s_params = _load_screener_params(screener_name)
    screener_cls = get_screener(screener_name)
    screener = screener_cls(**s_params)
    selection = screener.scan(market_data, scan_dates)

    # ---- 3. 反转 ----
    symbol_to_entry_dates = _invert_selection(selection)
    logger.info(
        "Screener 选中 %d 只票,共 %d 个进场日",
        len(symbol_to_entry_dates),
        sum(len(v) for v in symbol_to_entry_dates.values()),
    )

    if not symbol_to_entry_dates:
        return {"error": "Screener selected no stocks", "results": []}

    # ---- 4. 对选中票单股回测 ----
    names = stock_names or {}
    results_list: list[BacktestResult] = []
    for sym, entry_dates in symbol_to_entry_dates.items():
        # 合并出场参数 + 注入 allowed_entry_dates
        merged_params: dict[str, Any] = {}
        if strategy_params:
            merged_params.update(strategy_params)
        merged_params["allowed_entry_dates"] = entry_dates
        try:
            result = analyze_stock(
                sym, strategy_name, start, end,
                datasource_name, None, merged_params,
                stock_name=names.get(sym, ""),
            )
            results_list.append(result)
        except Exception as e:
            logger.error("回测 %s 失败: %s", sym, e)
            results_list.append(BacktestResult(
                symbol=sym, stock_name=names.get(sym, ""),
                metrics={"error": str(e)},
            ))

    # ---- 5. 报告 + 汇总 ----
    for result in results_list:
        for rep_name in reporter_names:
            try:
                reporter_cls = get_reporter(rep_name)
                reporter = reporter_cls() if isinstance(reporter_cls, type) else reporter_cls
                reporter.render(result)
            except Exception as e:
                logger.error("Reporter '%s' 失败: %s", rep_name, e)

    summary = _summarize(results_list)
    summary["screener"] = screener_name
    summary["selection_count"] = len(symbol_to_entry_dates)
    return summary
```

- [ ] **Step 4: 验证语法 + 导入**

Run:
```
python -c "from autotrade.core.engine import run_screener_backtest, _load_market_data, _invert_selection; print('OK')"
```
Expected: `OK`

- [ ] **Step 5: 写端到端集成测试(小样本)**

Append to `tests/unit/test_hot_money.py`:

```python
# ============================================================
# 端到端:run_screener_backtest 集成测试(合成数据,临时缓存)
# ============================================================
import os
import tempfile
from datetime import date as _date


def _seed_parquet(symbol, df, data_dir):
    """把合成 df 写入临时 parquet 缓存目录,供 LocalDataSource 读取。"""
    import pandas as pd
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
    """用合成数据走通:选股 → 回测 → 汇总。"""
    from autotrade.core import engine
    from autotrade.core.engine import run_screener_backtest

    tmp = tempfile.mkdtemp()
    # 构造 2 只票:000001 触发放量起涨,000002 平淡不触发
    closes_a = [10.0] * 60
    closes_a[-1] = 11.0
    volumes_a = [1e6] * 60
    volumes_a[-1] = 5e6
    df_a = _make_market("000001", closes_a, volumes_a)
    _seed_parquet("000001", df_a, tmp)

    df_b = _make_market("000002", [10.0] * 60, [1e6] * 60)
    _seed_parquet("000002", df_b, tmp)

    # 让 LocalDataSource 用临时目录
    monkeypatch.setattr(
        "autotrade.core.engine.LocalDataSource",
        lambda data_dir="data/daily": __import__(
            "autotrade.dataSources.local_ds", fromlist=["LocalDataSource"]
        ).LocalDataSource(data_dir=tmp),
    )

    start = _date(2024, 1, 1)
    end = _date(2024, 3, 1)
    summary = run_screener_backtest(
        screener_name="hot_money_screener",
        strategy_name="hot_money",
        start=start, end=end,
        symbols=["000001", "000002"],
    )

    # 000001 应被选中并回测;000002 不触发,不参与
    assert "error" not in summary
    assert summary["selection_count"] >= 1
    syms = [r["symbol"] for r in summary["results"]]
    assert "000001" in syms
```

- [ ] **Step 6: 运行集成测试**

Run: `python -m pytest tests/unit/test_hot_money.py::test_run_screener_backtest_end_to_end -v`
Expected: PASS

**调试提示**:若失败,常见原因:
- `_resolve_symbols` 把 `["000001","000002"]` 当字符串拆分 —— 检查它是否对 list 直接返回(见 `engine.py:223-224`)。
- 策略 `allowed_entry_dates` 注入后,进场日与 Screener scan_date 不匹配 —— 检查日期类型(date vs Timestamp),`_invert_selection` 输出的应是 `date` 对象。

- [ ] **Step 7: 运行全部测试确认无回归**

Run: `python -m pytest tests/unit/ -v`
Expected: 全部 PASS

- [ ] **Step 8: Commit**

```bash
git add autotrade/core/engine.py tests/unit/test_hot_money.py
git commit -m "feat: add run_screener_backtest orchestration for two-tier hot-money strategy"
```

---

## Task 7: 全样本回测验证(业务验收)

用真实缓存数据验证 60% 胜率 + 20% 收益目标。

**Files:**
- Create: `scripts/backtest_hot_money.py`(临时验证脚本,非核心代码)

- [ ] **Step 1: 创建验证脚本**

Create `scripts/backtest_hot_money.py`:

```python
"""游资策略全样本回测验证脚本。

用法: python scripts/backtest_hot_money.py
从 config/groups/随机组.yaml 读取股票池(450 只),跑全样本回测,
输出胜率/收益分布,验收 60% 胜率 + 20% 收益目标。
"""
import json
from datetime import date
from pathlib import Path

import yaml

from autotrade.core.engine import run_screener_backtest


def load_group_symbols(yaml_path: str) -> list[str]:
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    # 兼容两种格式:list 或 {stocks: [...]}
    if isinstance(data, list):
        return [str(s) for s in data]
    stocks = data.get("stocks") or data.get("symbols") or []
    return [str(s) for s in stocks]


def main():
    group_path = "config/groups/随机组.yaml"
    symbols = load_group_symbols(group_path)
    print(f"加载股票池: {len(symbols)} 只")

    summary = run_screener_backtest(
        screener_name="hot_money_screener",
        strategy_name="hot_money",
        start=date(2025, 1, 1),
        end=date(2026, 6, 18),
        symbols=symbols,
        reporter_names=(),
    )

    if "error" in summary:
        print(f"错误: {summary['error']}")
        return

    # 统计
    results = [r for r in summary["results"] if "error" not in r]
    win_rates = [r.get("win_rate", 0) for r in results]
    returns = [r.get("return_pct", 0) for r in results]
    avg_win = sum(win_rates) / len(win_rates) if win_rates else 0
    avg_ret = sum(returns) / len(returns) if returns else 0

    print(f"\n===== 游资策略回测结果 =====")
    print(f"选中并回测: {summary.get('selection_count', 0)} 只")
    print(f"有效结果: {len(results)} 只")
    print(f"平均胜率: {avg_win:.1f}%  (目标 ≥60%)")
    print(f"平均收益: {avg_ret:.2f}%  (目标 ≥20%)")
    print(f"胜率≥60%的票: {sum(1 for w in win_rates if w >= 60)}")
    print(f"收益≥20%的票: {sum(1 for r in returns if r >= 20)}")

    # 保存结果
    out_path = Path("data/results/hot_money_result.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存: {out_path}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 先确认随机组.yaml 格式**

Run:
```
python -c "import yaml; d=yaml.safe_load(open('config/groups/随机组.yaml',encoding='utf-8')); print(type(d), list(d.keys()) if isinstance(d,dict) else len(d))"
```
观察输出。若是 `{stocks: [...]}` 或 `{symbols: [...]}` 格式,脚本已兼容;若是嵌套 dict(代码→名称),需调整 `load_group_symbols`。

**若格式是 `{板块: {代码: 名称}}` 嵌套**,把 `load_group_symbols` 改为:
```python
def load_group_symbols(yaml_path: str) -> list[str]:
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if isinstance(data, list):
        return [str(s) for s in data]
    # 嵌套 dict:取所有键(代码)
    syms = []
    for k, v in data.items():
        if isinstance(v, dict):
            syms.extend(v.keys())
        elif isinstance(v, list):
            syms.extend(v)
        else:
            syms.append(str(k))
    return [str(s) for s in syms]
```

- [ ] **Step 3: 运行全样本回测**

Run: `python scripts/backtest_hot_money.py`
Expected: 输出平均胜率/收益。耗时预计 2-5 分钟(全市场加载 + 选股 + 选中票回测)。

- [ ] **Step 4: 分析结果,决定是否调参**

观察输出:
- 若 **胜率 < 60%**:信号过滤不够严,收紧 Screener 阈值(如 `breakout_min_gain` 0.05→0.06、`breakout_volume_ratio` 2.0→2.5)或收紧 Strategy(`time_stop_days` 3→2)。
- 若 **收益 < 20%**:止盈太早或止损太宽,放宽 `trailing_activate` 0.08→0.10 或 `trailing_drawdown` 0.03→0.05。
- 若 **选中票太少**(<50 只):放宽 Screener 阈值。
- 若 **选中票太多但胜率低**:收紧 Screener。

调参后重跑,迭代直到接近目标。**每次调参修改 YAML,重跑脚本,记录结果。**

- [ ] **Step 5: 在配置文件头部记录最终回测结果**

把回测得到的胜率/收益/选中数等关键数字,以注释形式更新到 `config/screens/hot_money.yaml` 和 `config/strategies/hot_money.yaml` 文件头部(参照现有 `trend_ma_breakout.yaml` 的注释格式,记录 "回测结果(随机组 N 只,日期区间):胜率 X% / 收益 Y%")。

- [ ] **Step 6: Commit**

```bash
git add scripts/backtest_hot_money.py config/strategies/hot_money.yaml config/screens/hot_money.yaml
git commit -m "test: validate hot-money strategy against full sample, tune thresholds"
```

---

## Self-Review

**1. Spec coverage:**
- §2 两层架构 → Task 1(Screener 基类)+ Task 6(run_screener_backtest)✓
- §3.1 放量起涨 → Task 4 `_check_breakout` ✓
- §3.2 首阴反包 → Task 4 `_check_reversal` ✓
- §3.3 强度排序 + max_picks → Task 4 `scan` + `test_max_picks_limit` ✓
- §3.4 排除项(ST 在数据层无名称信息暂略;一字板/停牌/次新 → Task 4 `exclude_min_history_days` + 一字/停牌检查)✓
  - **注**:ST 排除需股票名称,缓存 parquet 无此列。若需 ST 过滤,在 Task 4 `_evaluate` 加 symbol 前缀判断(沪市 ST 无固定代码规则),或在脚本层用 `data/a_stock_list.csv` 过滤。作为已知限制,留待实盘扩展。
- §3.5 T 日识别/T+1 进场 → 复用 Backtester `next_open` ✓
- §4 三闸门 → Task 3 ✓
- §5 单股满仓 + allowed_entry_dates 注入 → Task 6 ✓
- §6 文件结构 → Task 1/2/3/4/5/6 ✓
- §6.5 run_screener_backtest → Task 6 ✓
- §6.7 测试 → Task 3/4/6 ✓
- §7 验收 → Task 7 ✓

**2. Placeholder scan:** 无 TODO/TBD。Task 7 Step 4 是"调参迭代"指导,非 placeholder —— 它给出了具体的调参方向和判断标准。

**3. Type consistency:**
- `HotMoneyStrategy.__init__(allowed_entry_dates, trailing_activate, trailing_drawdown, time_stop_days, time_stop_min_gain, stop_loss)` — Task 3 定义,Task 6 通过 `merged_params["allowed_entry_dates"]` 注入,YAML(Task 5)只提供其余 5 个参数 ✓
- `HotMoneyScreener.__init__(max_picks, ma_period, ...)` — Task 4 定义,Task 6 通过 `_load_screener_params` 从 YAML 加载 ✓
- `Screener.scan(market_data, dates) -> {date: [(symbol, score, type)]}` — Task 1 定义,Task 4 实现,Task 6 调用 ✓
- `get_screener(name)` — Task 2 定义,Task 6 调用 ✓

**关键审查点**:
- Task 6 Step 5 集成测试用 `monkeypatch` 替换 `LocalDataSource`,确保不依赖真实缓存即可验证编排逻辑 ✓
- Task 4 `_evaluate` 的 scan_date 定位用 `_index_of_date` 兼容 Timestamp/date 索引 ✓
- Task 3 进场日检查用 `today in self.allowed_entry_dates`,其中 `today` 已 `.date()` 归一化 ✓

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-21-hot-money-strategy.md`. Two execution options:

**1. Subagent-Driven (recommended)** - 每个 Task 派发独立 subagent,任务间 review,快速迭代

**2. Inline Execution** - 在当前会话内逐 Task 执行,带检查点

**Which approach?**
