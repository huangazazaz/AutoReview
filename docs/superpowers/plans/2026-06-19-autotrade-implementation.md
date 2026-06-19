# AutoTrade 自动化交易系统 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现一个面向 A 股的自动化交易信号+回测系统 MVP，含完整的分层架构、插件化组件和 CLI 触发。

**Architecture:** 自建轻量三层框架（触发层 → 编排层 → 核心引擎层），四类核心组件（DataSource / Indicator / Strategy / Reporter）全部接口化、目录化、自动发现。回测引擎（Backtester）为内置硬约束，不参与插件化。

**Tech Stack:** Python ≥ 3.10, pandas, numpy, pyyaml, click, apscheduler, akshare, pandas-ta, rich, matplotlib, pyarrow

---

## 文件结构总览

### 需创建的文件清单

| 文件 | 职责 | 依赖 |
|------|------|------|
| `pyproject.toml` | 项目元信息与依赖声明 | 无 |
| `autotrade/__init__.py` | 包初始化 | 无 |
| `autotrade/core/__init__.py` | 核心包初始化 | 无 |
| `autotrade/core/models.py` | Bar/Signal/Trade/Position/BacktestResult/BacktestConfig 数据模型 | 无 |
| `autotrade/core/interfaces.py` | DataSource/Indicator/Strategy/Reporter ABC 接口 | models |
| `autotrade/core/backtester.py` | 回测引擎（撮合/T+1/涨跌停/手续费/仓位） | models |
| `autotrade/core/config.py` | 配置加载（YAML + 环境变量覆盖） | 无 |
| `autotrade/core/engine.py` | 编排器（analyze_stock/run_backtest/analyze_universe） | core/*, registry, plugins |
| `autotrade/registry.py` | 插件注册表与自动发现 | interfaces |
| `autotrade/datasources/__init__.py` | 数据源注册表 | registry |
| `autotrade/datasources/akshare_ds.py` | AkShare 数据源实现 | core/interfaces |
| `autotrade/datasources/tushare_ds.py` | Tushare 数据源实现（可选） | core/interfaces |
| `autotrade/indicators/__init__.py` | 指标自动发现与注册 | registry |
| `autotrade/indicators/ma.py` | 均线指标（MA/EMA）| core/interfaces |
| `autotrade/indicators/macd.py` | MACD 指标 | core/interfaces |
| `autotrade/indicators/rsi.py` | RSI 指标 | core/interfaces |
| `autotrade/indicators/bollinger.py` | 布林带指标 | core/interfaces |
| `autotrade/strategies/__init__.py` | 策略自动发现与注册 | registry |
| `autotrade/strategies/ma_cross.py` | 均线交叉策略 | core/interfaces, indicators |
| `autotrade/strategies/macd_divergence.py` | MACD 背离策略 | core/interfaces, indicators |
| `autotrade/reporters/__init__.py` | 报告输出注册表 | registry |
| `autotrade/reporters/console.py` | 终端报告（rich 表格） | core/interfaces |
| `autotrade/reporters/csv_reporter.py` | CSV 报告 | core/interfaces |
| `autotrade/reporters/plot_reporter.py` | 图表报告（matplotlib） | core/interfaces |
| `autotrade/triggers/__init__.py` | 触发层初始化 | 无 |
| `autotrade/triggers/cli.py` | CLI 入口（click） | engine, registry |
| `autotrade/triggers/scheduler.py` | 定时任务（APScheduler） | engine, config |
| `autotrade/api/__init__.py` | 未来 Web API 占位 | 无 |
| `config/settings.yaml` | 全局默认配置 | 无 |
| `config/scheduler.yaml` | 定时任务配置 | 无 |
| `config/strategies/ma_cross.yaml` | 均线交叉策略参数 | 无 |
| `data/.gitkeep` | 数据目录占位 | 无 |
| `.gitignore` | Git 忽略规则 | 无 |
| `tests/__init__.py` | 测试包初始化 | 无 |
| `tests/unit/__init__.py` | 单元测试包初始化 | 无 |
| `tests/integration/__init__.py` | 集成测试包初始化 | 无 |
| `tests/fixtures/__init__.py` | 测试数据占位 | 无 |
| `tests/unit/test_models.py` | 数据模型测试 | core/models |
| `tests/unit/test_backtester.py` | 回测引擎测试（重点） | core/backtester |
| `tests/unit/test_indicators.py` | 指标计算测试 | indicators |
| `tests/unit/test_strategies.py` | 策略测试 | strategies |
| `tests/unit/test_registry.py` | 注册表测试 | registry |
| `tests/integration/test_engine.py` | 编排层集成测试 | core/engine |
| `tests/fixtures/000001_daily.csv` | 固定行情测试数据 | 无 |

---

### Task 1: 项目初始化与基础结构

**Files:**
- Create: `pyproject.toml`
- Create: `autotrade/__init__.py`
- Create: `autotrade/core/__init__.py`
- Create: `autotrade/core/models.py`
- Create: `autotrade/core/interfaces.py`
- Create: `autotrade/api/__init__.py`
- Create: `autotrade/datasources/__init__.py`
- Create: `autotrade/indicators/__init__.py`
- Create: `autotrade/strategies/__init__.py`
- Create: `autotrade/reporters/__init__.py`
- Create: `autotrade/triggers/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/unit/__init__.py`
- Create: `tests/integration/__init__.py`
- Create: `tests/fixtures/__init__.py`
- Create: `.gitignore`
- Create: `data/.gitkeep`

- [ ] **Step 1: 创建 pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "autotrade"
version = "0.1.0"
description = "A股自动化交易信号生成与回测系统"
requires-python = ">=3.10"
dependencies = [
    "pandas>=2.0",
    "numpy>=1.24",
    "pyyaml>=6.0",
    "click>=8.1",
    "apscheduler>=3.10",
    "akshare>=1.10",
    "pandas-ta>=0.3.14b",
    "pyarrow>=14.0",
    "rich>=13.0",
]

[project.optional-dependencies]
tushare = ["tushare>=1.2.89"]
plot = ["matplotlib>=3.7"]
api = ["fastapi>=0.104", "uvicorn"]
dev = ["pytest>=7.4", "pytest-cov>=4.1", "pytest-mock>=3.12", "ruff>=0.1"]

[project.scripts]
autotrade = "autotrade.triggers.cli:cli"
autotrade-scheduler = "autotrade.triggers.scheduler:main"

[tool.setuptools.packages.find]
include = ["autotrade", "autotrade.*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]

[tool.ruff]
line-length = 100
target-version = "py310"
```

- [ ] **Step 2: 创建包初始化文件和占位符**

```python
# autotrade/__init__.py
"""AutoTrade: A股自动化交易信号生成与回测系统."""
__version__ = "0.1.0"
```

```python
# autotrade/core/__init__.py
"""核心引擎层 —— 纯逻辑，不关心数据来源/输出方式。"""
```

```python
# autotrade/api/__init__.py
"""预留：未来 Web API（FastAPI）。MVP 阶段为空占位。"""
```

```python
# autotrade/datasources/__init__.py
"""数据源插件注册表。"""
from autotrade.registry import register_datasource, get_datasource, list_datasources
```

```python
# autotrade/indicators/__init__.py
"""指标插件 —— 自动发现并注册目录内所有指标。"""
from autotrade.registry import register_indicator, get_indicator, list_indicators
# 自动发现将在 registry 初始化时统一触发
```

```python
# autotrade/strategies/__init__.py
"""策略插件 —— 组合指标成买卖规则。"""
from autotrade.registry import register_strategy, get_strategy, list_strategies
```

```python
# autotrade/reporters/__init__.py
"""报告输出插件注册表。"""
from autotrade.registry import register_reporter, get_reporter, list_reporters
```

```python
# autotrade/triggers/__init__.py
"""触发层 —— CLI / 定时任务 / 未来 Web API。"""
```

```python
# tests/__init__.py
"""AutoTrade 测试套件。"""
```

```python
# tests/unit/__init__.py
```

```python
# tests/integration/__init__.py
```

```python
# tests/fixtures/__init__.py
```

```
# .gitignore
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.venv/
venv/
data/cache/
data/results/
data/logs/
*.parquet
*.csv
config/settings.local.yaml
.env
*.egg
.pytest_cache/
.ruff_cache/
```

```bash
# 创建 data/.gitkeep
touch data/.gitkeep
```

- [ ] **Step 3: 创建数据模型 core/models.py**

```python
"""数据模型：Bar / Signal / Trade / Position / BacktestResult / BacktestConfig。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import pandas as pd


@dataclass
class Bar:
    """单根K线（日线）。所有数据源的统一输出格式。"""
    symbol: str          # 股票代码，如 "000001"
    date: date           # 交易日期
    open: float
    high: float
    low: float
    close: float
    volume: float        # 成交量（股）
    amount: float        # 成交额（元）

    def __post_init__(self):
        for field_name in ("open", "high", "low", "close", "volume", "amount"):
            val = getattr(self, field_name)
            if val is not None:
                setattr(self, field_name, float(val))


@dataclass
class Signal:
    """策略在某一天产生的信号。"""
    symbol: str
    date: date
    action: str          # "BUY" | "SELL" | "HOLD"
    strength: float = 1.0  # 信号强度 0~1，供仓位管理用
    reason: str = ""       # 人类可读的理由（如 "MA5上穿MA20"）


@dataclass
class Trade:
    """回测中实际成交的一笔交易。"""
    symbol: str
    date: date
    action: str          # "BUY" | "SELL"
    price: float         # 实际成交价（考虑滑点）
    quantity: int        # 成交股数（A股需100股整数倍）
    commission: float    # 手续费
    stamp_duty: float = 0.0  # 印花税（仅卖出时产生）


@dataclass
class Position:
    """某时刻的持仓快照。"""
    symbol: str
    quantity: int = 0
    avg_cost: float = 0.0     # 持仓均价
    market_value: float = 0.0  # 当前市值


@dataclass
class BacktestConfig:
    """回测撮合配置。"""
    initial_capital: float = 100_000.0     # 初始资金
    fill_price: str = "next_open"          # "next_open" | "close"
    commission_rate: float = 0.0003        # 佣金费率（万三）
    stamp_duty_rate: float = 0.001         # 印花税（仅卖出千一）
    slippage: float = 0.001               # 滑点（千一）
    min_commission: float = 5.0           # 单笔最低佣金 5 元
    lot_size: int = 100                   # A 股一手 100 股
    allow_t_plus_1: bool = True           # T+1：当日买入次日才能卖
    position_sizing: str = "strength"     # "full" | "strength"
    max_positions: int = 1                # 最大同时持仓股票数


@dataclass
class BacktestResult:
    """回测结果，传给 Reporter 输出。"""
    symbol: str
    trades: list[Trade] = field(default_factory=list)
    equity_curve: Optional[pd.Series] = None  # 净值曲线（按日期）
    metrics: dict = field(default_factory=dict)  # 收益率/胜率/最大回撤/夏普等
    signals: list[Signal] = field(default_factory=list)  # 产生的所有信号

    def __post_init__(self):
        if self.metrics is None:
            self.metrics = {}
```

- [ ] **Step 4: 创建核心接口 core/interfaces.py**

```python
"""插件抽象基类：DataSource / Indicator / Strategy / Reporter。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Optional

import pandas as pd

from autotrade.core.models import Bar, BacktestResult, Signal


class DataSource(ABC):
    """数据源插件：把外部数据统一成 Bar 序列。"""

    @abstractmethod
    def get_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        """获取指定股票在日期范围内的日线数据（前复权）。"""

    @abstractmethod
    def list_symbols(self) -> list[str]:
        """列出全市场股票代码（用于全市场回测）。"""


class Indicator(ABC):
    """指标插件：在含 Bar 列的 DataFrame 上追加指标列。
    输入输出都是 DataFrame，便于多个指标链式追加（列名 ind_<name>_<field>）。"""
    name: str = "base"           # 指标名，如 "ma"
    params: dict = {}            # 参数，如 {"period": 20}

    @abstractmethod
    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """输入含 OHLCV 列的 df，返回追加了指标列的 df。"""


class Strategy(ABC):
    """策略插件：声明所需指标，在含指标 DataFrame 上产生 Signal 序列。"""
    name: str = "base"
    required_indicators: list[Indicator] = []  # 编排层据此先算好指标列

    def __init__(self):
        self.required_indicators = []

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        """df 是已计算好所需指标的 DataFrame；返回每日信号列表。"""


class Reporter(ABC):
    """报告插件：消费 BacktestResult，输出到不同媒介。"""

    @abstractmethod
    def render(self, result: BacktestResult) -> None:
        """输出报告（终端/CSV/图表）。"""
```

- [ ] **Step 5: 验证基础结构**

Run:
```bash
cd D:\AutoTrade
python -c "from autotrade.core.models import Bar, Signal, Trade, Position, BacktestConfig, BacktestResult; print('Models OK')"
python -c "from autotrade.core.interfaces import DataSource, Indicator, Strategy, Reporter; print('Interfaces OK')"
python -c "import autotrade; print(f'Package OK, version={autotrade.__version__}')"
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: init project structure with models and interfaces"
```

---

### Task 2: 插件注册表与自动发现机制

**Files:**
- Create: `autotrade/registry.py`

- [ ] **Step 1: 实现 registry.py**

```python
"""插件注册表与自动发现机制。

支持四类插件：DataSource / Indicator / Strategy / Reporter。
每类维护一个 name → class 的 dict。
Auto-discover: 扫描 plugindir 下所有 .py 模块，找出符合接口的类。
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Optional

from autotrade.core.interfaces import DataSource, Indicator, Strategy, Reporter

# 注册表存储
_datasources: dict[str, type[DataSource]] = {}
_indicators: dict[str, type[Indicator]] = {}
_strategies: dict[str, type[Strategy]] = {}
_reporters: dict[str, type[Reporter]] = {}

# 初始化标志
_initialized = False


def _discover_plugins(package_name: str, base_class: type,
                      registry: dict[str, type]) -> None:
    """扫描指定包下所有模块，找出 base_class 的子类并注册。"""
    try:
        package = importlib.import_module(package_name)
    except ImportError:
        return  # 包不存在，跳过

    prefix = package.__name__ + "."
    for importer, modname, ispkg in pkgutil.iter_modules(
        package.__path__, prefix
    ):
        try:
            module = importlib.import_module(modname)
        except Exception as e:
            continue  # 跳过加载失败的模块

        for name, obj in inspect.getmembers(module, inspect.isclass):
            if (issubclass(obj, base_class) and obj is not base_class
                    and not inspect.isabstract(obj)):
                # 获取实例以读取 name 属性
                try:
                    instance = obj() if base_class in (Indicator, Strategy) else obj
                    key = instance.name if hasattr(instance, 'name') else name.lower()
                except Exception:
                    key = name.lower()
                registry[key] = obj


def init_registry(force: bool = False) -> None:
    """初始化注册表：扫描所有插件目录。"""
    global _initialized
    if _initialized and not force:
        return
    _initialized = True

    # 清空并重新发现
    _datasources.clear()
    _indicators.clear()
    _strategies.clear()
    _reporters.clear()

    _discover_plugins("autotrade.datasources", DataSource, _datasources)
    _discover_plugins("autotrade.indicators", Indicator, _indicators)
    _discover_plugins("autotrade.strategies", Strategy, _strategies)
    _discover_plugins("autotrade.reporters", Reporter, _reporters)


# --- 注册（手动注册，供插件 __init__ 使用）---

def register_datasource(name: str, cls: type[DataSource]) -> None:
    _datasources[name] = cls

def register_indicator(name: str, cls: type[Indicator]) -> None:
    _indicators[name] = cls

def register_strategy(name: str, cls: type[Strategy]) -> None:
    _strategies[name] = cls

def register_reporter(name: str, cls: type[Reporter]) -> None:
    _reporters[name] = cls


# --- 查询 ---

def get_datasource(name: str) -> type[DataSource]:
    if not _initialized:
        init_registry()
    if name not in _datasources:
        raise KeyError(f"DataSource '{name}' not found. Available: {list(_datasources)}")
    return _datasources[name]

def get_indicator(name: str) -> type[Indicator]:
    if not _initialized:
        init_registry()
    if name not in _indicators:
        raise KeyError(f"Indicator '{name}' not found. Available: {list(_indicators)}")
    return _indicators[name]

def get_strategy(name: str) -> type[Strategy]:
    if not _initialized:
        init_registry()
    if name not in _strategies:
        raise KeyError(f"Strategy '{name}' not found. Available: {list(_strategies)}")
    return _strategies[name]

def get_reporter(name: str) -> type[Reporter]:
    if not _initialized:
        init_registry()
    if name not in _reporters:
        raise KeyError(f"Reporter '{name}' not found. Available: {list(_reporters)}")
    return _reporters[name]


# --- 列表 ---

def list_datasources() -> list[str]:
    if not _initialized:
        init_registry()
    return list(_datasources)

def list_indicators() -> list[str]:
    if not _initialized:
        init_registry()
    return list(_indicators)

def list_strategies() -> list[str]:
    if not _initialized:
        init_registry()
    return list(_strategies)

def list_reporters() -> list[str]:
    if not _initialized:
        init_registry()
    return list(_reporters)


# --- 批量获取 ---

def get_all_strategies() -> dict[str, type[Strategy]]:
    if not _initialized:
        init_registry()
    return dict(_strategies)
```

- [ ] **Step 2: 编写单元测试 tests/unit/test_registry.py**

```python
"""插件注册表单元测试。"""
import pytest
from autotrade.registry import (
    init_registry, list_datasources, list_indicators,
    list_strategies, list_reporters, get_datasource,
    get_indicator, get_strategy, get_reporter,
)


class TestRegistry:
    def test_init_and_list(self):
        """初始化后至少能列出各类型插件（即使为空目录也应有空列表）。"""
        init_registry(force=True)
        assert isinstance(list_datasources(), list)
        assert isinstance(list_indicators(), list)
        assert isinstance(list_strategies(), list)
        assert isinstance(list_reporters(), list)

    def test_get_nonexistent_raises(self):
        """获取不存在的插件应抛 KeyError。"""
        init_registry(force=True)
        with pytest.raises(KeyError):
            get_datasource("nonexistent")
        with pytest.raises(KeyError):
            get_indicator("nonexistent")
        with pytest.raises(KeyError):
            get_strategy("nonexistent")
        with pytest.raises(KeyError):
            get_reporter("nonexistent")
```

- [ ] **Step 3: 运行测试**

```bash
cd D:\AutoTrade
pip install -e ".[dev]"
pytest tests/unit/test_registry.py -v
```
Expected: 2 passed

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: add plugin registry with auto-discovery"
```

---

### Task 3: 回测引擎（核心业务逻辑）

**Files:**
- Create: `autotrade/core/backtester.py`

- [ ] **Step 1: 编写回测引擎 tests/unit/test_backtester.py**

```python
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
        config = BacktestConfig(initial_capital=1000.0, commission_rate=0.0003,
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
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd D:\AutoTrade
pytest tests/unit/test_backtester.py -v
```
Expected: ImportError / ModuleNotFoundError (backtester not yet created)

- [ ] **Step 3: 实现 backtester.py**

```python
"""回测引擎（撮合/T+1/涨跌停/手续费/仓位管理）。

核心设计：
- 非插件 —— A 股撮合规则是硬约束，不应被替换；但参数可配置。
- 逐日模拟：遍历每个交易日，检查信号 → 执行交易 → 更新持仓 → 记录净值。
- 成交价默认次日开盘价（避免未来函数），可配置为当日收盘价。
"""

from __future__ import annotations

from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

from autotrade.core.models import (
    Bar, BacktestConfig, BacktestResult, Position, Signal, Trade,
)


class Backtester:
    """回测引擎，负责逐日撮合、持仓管理、资金计算。"""

    def __init__(self, config: BacktestConfig):
        self.config = config

    def run(self, signals: list[Signal], bars: list[Bar]) -> BacktestResult:
        """运行回测。

        Args:
            signals: 策略产生的信号列表（已按日期排序）。
            bars: 日线数据列表（已按日期排序）。

        Returns:
            BacktestResult 包含成交记录、净值曲线、汇总指标。
        """
        if not bars:
            return BacktestResult(
                symbol=signals[0].symbol if signals else "",
                metrics={"error": "No bar data"},
            )

        symbol = bars[0].symbol
        signal_map: dict[date, list[Signal]] = {}
        for s in signals:
            signal_map.setdefault(s.date, []).append(s)

        # 按日期排序的 bar 列表
        bars_sorted = sorted(bars, key=lambda b: b.date)
        bar_dates = [b.date for b in bars_sorted]
        date_to_bar = {b.date: b for b in bars_sorted}

        # 状态初始化
        cash = self.config.initial_capital
        position = Position(symbol=symbol)
        trades: list[Trade] = []
        equity_series: list[float] = [cash]  # 净值序列
        dates_series: list[date] = [bar_dates[0]] if bar_dates else []

        # 买入锁定（T+1）：记录可卖日期
        can_sell_after: Optional[date] = None

        for i, bar in enumerate(bars_sorted):
            today = bar.date
            daily_signals = signal_map.get(today, [])

            # 处理当天的信号（先买后卖，避免先卖空）
            buy_signals = [s for s in daily_signals if s.action == "BUY"]
            sell_signals = [s for s in daily_signals if s.action == "SELL"]

            # --- 执行卖出 ---
            for sig in sell_signals:
                if position.quantity <= 0:
                    continue
                if self.config.allow_t_plus_1 and can_sell_after and today < can_sell_after:
                    continue  # T+1 锁定中，不能卖

                # 确定成交价
                fill_price = self._get_fill_price(sig, bar, bars_sorted, i, is_buy=False)
                if fill_price is None:
                    continue

                # 滑点（卖出成交价降低）
                actual_price = fill_price * (1 - self.config.slippage)

                # 计算卖出数量（按 strength 比例）
                quantity = self._compute_sell_quantity(position, sig.strength)
                if quantity <= 0:
                    continue

                amount = actual_price * quantity
                commission = max(amount * self.config.commission_rate,
                                 self.config.min_commission)
                stamp_duty = amount * self.config.stamp_duty_rate

                trade = Trade(
                    symbol=symbol, date=today, action="SELL",
                    price=round(actual_price, 2),
                    quantity=quantity,
                    commission=round(commission, 2),
                    stamp_duty=round(stamp_duty, 2),
                )
                trades.append(trade)
                cash += amount - commission - stamp_duty
                position.quantity -= quantity
                if position.quantity <= 0:
                    position.avg_cost = 0.0
                position.market_value = position.quantity * actual_price

            # --- 执行买入 ---
            for sig in buy_signals:
                # 确定成交价
                fill_price = self._get_fill_price(sig, bar, bars_sorted, i, is_buy=True)
                if fill_price is None:
                    continue

                # 滑点（买入成交价提高）
                actual_price = fill_price * (1 + self.config.slippage)

                # 计算买入数量
                quantity = self._compute_buy_quantity(cash, actual_price, sig.strength)
                if quantity <= 0:
                    continue

                amount = actual_price * quantity
                commission = max(amount * self.config.commission_rate,
                                 self.config.min_commission)

                trade = Trade(
                    symbol=symbol, date=today, action="BUY",
                    price=round(actual_price, 2),
                    quantity=quantity,
                    commission=round(commission, 2),
                )
                trades.append(trade)
                cash -= amount + commission

                # 更新持仓均价
                total_cost = position.avg_cost * position.quantity + amount
                position.quantity += quantity
                position.avg_cost = total_cost / position.quantity if position.quantity > 0 else 0
                position.market_value = position.quantity * actual_price

                # T+1 锁定
                if self.config.allow_t_plus_1:
                    # 找到下一个交易日
                    if i + 1 < len(bars_sorted):
                        can_sell_after = bars_sorted[i + 1].date

            # 更新市值的每日估值
            position.market_value = position.quantity * bar.close
            total_equity = cash + position.market_value
            equity_series.append(total_equity)
            dates_series.append(today)

        # 构建结果
        result = BacktestResult(
            symbol=symbol,
            trades=trades,
            signals=signals,
            equity_curve=pd.Series(equity_series, index=dates_series),
            metrics=self._compute_metrics(trades, equity_series, dates_series),
        )
        return result

    def _get_fill_price(self, sig: Signal, bar: Bar,
                        bars_sorted: list[Bar], idx: int,
                        is_buy: bool) -> Optional[float]:
        """获取成交价。"""
        if self.config.fill_price == "close":
            return bar.close
        elif self.config.fill_price == "next_open":
            # 次日开盘价
            if idx + 1 < len(bars_sorted):
                return bars_sorted[idx + 1].open
            else:
                return None  # 最后一天无下一日数据
        return bar.close

    def _compute_buy_quantity(self, cash: float, price: float,
                              strength: float) -> int:
        """计算买入股数（A股规则：100股整数倍，按 strength 比例）。"""
        if cash <= 0 or price <= 0:
            return 0

        if self.config.position_sizing == "strength":
            available = cash * strength
        else:
            available = cash

        max_shares = int(available / price)
        # 向下取整到 lot_size 的倍数
        quantity = (max_shares // self.config.lot_size) * self.config.lot_size
        return quantity

    def _compute_sell_quantity(self, position: Position, strength: float) -> int:
        """计算卖出股数。"""
        if position.quantity <= 0:
            return 0
        if self.config.position_sizing == "strength":
            quantity = int(position.quantity * strength)
        else:
            quantity = position.quantity
        # 向下取整到 lot_size 的倍数
        quantity = (quantity // self.config.lot_size) * self.config.lot_size
        return max(0, quantity)

    def _compute_metrics(self, trades: list[Trade],
                         equity_series: list[float],
                         dates: list[date]) -> dict:
        """计算回测汇总指标。"""
        if not trades or len(equity_series) < 2:
            return {
                "total_trades": len(trades),
                "total_return_pct": 0.0,
                "win_rate": 0.0,
                "max_drawdown_pct": 0.0,
                "sharpe_ratio": 0.0,
            }

        initial_capital = equity_series[0]
        final_equity = equity_series[-1]
        total_return_pct = (final_equity - initial_capital) / initial_capital * 100

        # 胜率：按买卖配对计算
        buy_trades = [t for t in trades if t.action == "BUY"]
        sell_trades = [t for t in trades if t.action == "SELL"]
        # 简化：按顺序配对
        wins = 0
        total_pairs = min(len(buy_trades), len(sell_trades))
        for i in range(total_pairs):
            buy = buy_trades[i]
            sell = sell_trades[i]
            if sell.price > buy.price:
                wins += 1
        win_rate = (wins / total_pairs * 100) if total_pairs > 0 else 0.0

        # 最大回撤
        equity_arr = np.array(equity_series)
        peak = np.maximum.accumulate(equity_arr)
        drawdown = (peak - equity_arr) / peak * 100
        max_drawdown_pct = float(np.max(drawdown))

        # 夏普比率（简化：用日收益率，无风险利率=0）
        if len(equity_series) > 1:
            returns = pd.Series(equity_series).pct_change().dropna()
            if returns.std() > 0:
                sharpe = float(returns.mean() / returns.std() * np.sqrt(252))
            else:
                sharpe = 0.0
        else:
            sharpe = 0.0

        return {
            "initial_capital": initial_capital,
            "final_equity": round(final_equity, 2),
            "total_trades": len(trades),
            "buy_trades": len(buy_trades),
            "sell_trades": len(sell_trades),
            "total_return_pct": round(total_return_pct, 2),
            "win_rate": round(win_rate, 2),
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "sharpe_ratio": round(sharpe, 4),
        }
```

- [ ] **Step 4: 运行测试验证通过**

```bash
cd D:\AutoTrade
pytest tests/unit/test_backtester.py -v
```
Expected: 10 passed (or similar, count actual test methods)

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: implement backtesting engine with T+1/commission/slippage"
```

---

### Task 4: 配置加载

**Files:**
- Create: `autotrade/core/config.py`
- Create: `config/settings.yaml`

- [ ] **Step 1: 编写配置加载单元测试 tests/unit/test_config.py**

```python
"""配置加载单元测试。"""
import os
import pytest
import tempfile
from autotrade.core.config import load_config, get_config


class TestConfig:
    def test_load_defaults(self):
        """加载默认配置应返回合理的默认值。"""
        config = load_config()
        assert config["backtest"]["initial_capital"] == 100000
        assert config["backtest"]["commission_rate"] == 0.0003
        assert config["datasource"]["default"] == "akshare"
        assert config["cache"]["enabled"] is True

    def test_env_override(self):
        """环境变量应覆盖配置。"""
        os.environ["AUTOTRADE_BACKTEST_INITIAL_CAPITAL"] = "99999"
        os.environ["AUTOTRADE_DATASOURCE_DEFAULT"] = "tushare"
        config = load_config()
        assert config["backtest"]["initial_capital"] == 99999
        assert config["datasource"]["default"] == "tushare"
        # 清理环境变量
        del os.environ["AUTOTRADE_BACKTEST_INITIAL_CAPITAL"]
        del os.environ["AUTOTRADE_DATASOURCE_DEFAULT"]
```

- [ ] **Step 2: 实现 config.py 与 settings.yaml**

```python
"""配置加载（YAML + 环境变量覆盖）。

优先级（低 → 高）:
1. config/settings.yaml          ← 默认配置（提交 git）
2. 环境变量 AUTOTRADE_*           ← 部署/CI 覆盖
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

# 项目根目录（AutoTrade 上级的上级？pyproject.toml 在项目根）
# 通过 autotrade 包自身位置推导
_CONFIG_DIR: Path = Path(__file__).resolve().parent.parent.parent / "config"
_DEFAULT_CONFIG_PATH: Path = _CONFIG_DIR / "settings.yaml"

# 默认配置（硬编码 fallback）
_DEFAULT_SETTINGS: dict[str, Any] = {
    "datasource": {
        "default": "akshare",
        "tushare": {"token": ""},
    },
    "cache": {
        "enabled": True,
        "dir": "data/cache",
    },
    "backtest": {
        "initial_capital": 100000,
        "fill_price": "next_open",
        "commission_rate": 0.0003,
        "stamp_duty_rate": 0.001,
        "slippage": 0.001,
        "min_commission": 5.0,
        "lot_size": 100,
        "allow_t_plus_1": True,
        "position_sizing": "strength",
        "max_positions": 1,
    },
    "paths": {
        "results_dir": "data/results",
        "cache_dir": "data/cache",
    },
    "logging": {
        "level": "INFO",
        "file": "data/logs/autotrade.log",
    },
}

_config_cache: dict[str, Any] | None = None


def _load_yaml_config(path: Path) -> dict[str, Any]:
    """从 YAML 文件加载配置，文件不存在时返回空字典。"""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _apply_env_overrides(config: dict[str, Any]) -> dict[str, Any]:
    """应用 AUTOTRADE_* 环境变量覆盖。

    环境变量名规则：AUTOTRADE_SECTION_KEY
    例: AUTOTRADE_BACKTEST_INITIAL_CAPITAL → config["backtest"]["initial_capital"]
    """
    prefix = "AUTOTRADE_"
    for env_key, env_val in os.environ.items():
        if not env_key.startswith(prefix):
            continue
        parts = env_key[len(prefix):].lower().split("_")
        if len(parts) < 2:
            continue

        # 尝试转为数值类型
        try:
            if "." in env_val:
                env_val = float(env_val)
            else:
                env_val = int(env_val)
        except ValueError:
            pass  # 保持字符串

        # 导航到配置深层位置
        target = config
        for part in parts[:-1]:
            if part not in target:
                target[part] = {}
            target = target[part]
        target[parts[-1]] = env_val

    return config


def load_config(path: Path | None = None, force_reload: bool = False) -> dict[str, Any]:
    """加载配置（含优先级叠加）。

    Args:
        path: 配置文件路径，默认 config/settings.yaml。
        force_reload: 忽略缓存强制重新加载。

    Returns:
        合并后的配置字典。
    """
    global _config_cache
    if _config_cache is not None and not force_reload:
        return _config_cache

    config = dict(_DEFAULT_SETTINGS)

    # 加载 YAML 文件覆盖
    yaml_path = path or _DEFAULT_CONFIG_PATH
    yaml_config = _load_yaml_config(yaml_path)
    _deep_merge(config, yaml_config)

    # 环境变量覆盖
    config = _apply_env_overrides(config)

    _config_cache = config
    return config


def _deep_merge(base: dict, override: dict) -> None:
    """深度合并字典（override 覆盖 base）。"""
    for key, val in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(val, dict):
            _deep_merge(base[key], val)
        else:
            base[key] = val


def get_config() -> dict[str, Any]:
    """获取当前配置（快捷方式）。"""
    return load_config()


def get_backtest_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """从配置中提取回测子配置。"""
    cfg = config or load_config()
    return cfg.get("backtest", {})


def get_strategy_params(strategy_name: str) -> dict[str, Any]:
    """加载 config/strategies/<strategy_name>.yaml 的策略参数。"""
    path = _CONFIG_DIR / "strategies" / f"{strategy_name}.yaml"
    return _load_yaml_config(path)
```

- [ ] **Step 3: 创建 config/settings.yaml**

```yaml
# AutoTrade 全局配置文件
datasource:
  default: akshare
  tushare:
    token: ""  # 使用 Tushare 时在此填入 token

cache:
  enabled: true
  dir: data/cache

backtest:
  initial_capital: 100000
  fill_price: next_open
  commission_rate: 0.0003
  stamp_duty_rate: 0.001
  slippage: 0.001
  min_commission: 5.0
  lot_size: 100
  allow_t_plus_1: true
  position_sizing: strength
  max_positions: 1

paths:
  results_dir: data/results
  cache_dir: data/cache

logging:
  level: INFO
  file: data/logs/autotrade.log
```

- [ ] **Step 4: 运行测试**

```bash
cd D:\AutoTrade
pytest tests/unit/test_config.py -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: configuration loading with YAML and env overrides"
```

---

### Task 5: AkShare 数据源实现

**Files:**
- Create: `autotrade/datasources/akshare_ds.py`
- Create: `tests/fixtures/000001_daily.csv`

- [ ] **Step 1: 实现 AkShare 数据源**

```python
"""AkShare 数据源实现（默认，免费）。

使用 AkShare API 获取 A 股日线数据，输出统一 Bar 格式。
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

import pandas as pd

from autotrade.core.interfaces import DataSource
from autotrade.core.models import Bar

logger = logging.getLogger(__name__)


class AkShareDataSource(DataSource):
    """基于 AkShare 的数据源。"""

    name = "akshare"

    def __init__(self, auto_adjust: bool = True):
        self.auto_adjust = auto_adjust

    def get_bars(self, symbol: str, start: date, end: date) -> list[Bar]:
        """获取 A 股日线数据（前复权）。"""
        import akshare as ak

        # AkShare 股票代码格式：sh000001 / sz000001 / 或 000001（自动检测）
        try:
            df = ak.stock_zh_a_hist(
                symbol=symbol,
                period="daily",
                start_date=start.strftime("%Y%m%d"),
                end_date=end.strftime("%Y%m%d"),
                adjust="qfq" if self.auto_adjust else "",  # 前复权
            )
        except Exception as e:
            logger.error("AkShare get_bars failed for %s: %s", symbol, e)
            return []

        if df is None or df.empty:
            return []

        # 映射 AkShare 列到 Bar
        bars = []
        for _, row in df.iterrows():
            try:
                bar = Bar(
                    symbol=symbol,
                    date=row["日期"].date() if isinstance(row["日期"], datetime) else row["日期"],
                    open=float(row["开盘"]),
                    high=float(row["最高"]),
                    low=float(row["最低"]),
                    close=float(row["收盘"]),
                    volume=float(row["成交量"]),
                    amount=float(row["成交额"]),
                )
                bars.append(bar)
            except Exception as e:
                logger.warning("Skipping row for %s: %s", symbol, e)
                continue

        return bars

    def list_symbols(self) -> list[str]:
        """列出全市场股票代码。"""
        import akshare as ak
        try:
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                return df["代码"].tolist()
        except Exception as e:
            logger.error("AkShare list_symbols failed: %s", e)
        return []
```

- [ ] **Step 2: 创建测试 fixtures 数据**

创建 `tests/fixtures/000001_daily.csv`，包含 000001（平安银行）2024年1月 的部分日线数据：
```csv
symbol,date,open,high,low,close,volume,amount
000001,2024-01-02,9.20,9.28,9.10,9.25,85000000,785000000
000001,2024-01-03,9.22,9.30,9.15,9.18,72000000,665000000
000001,2024-01-04,9.16,9.25,9.12,9.20,68000000,628000000
000001,2024-01-05,9.18,9.22,9.05,9.08,92000000,840000000
000001,2024-01-08,9.06,9.15,8.98,9.02,88000000,798000000
000001,2024-01-09,9.04,9.20,9.00,9.15,76000000,695000000
000001,2024-01-10,9.12,9.18,9.06,9.10,65000000,592000000
000001,2024-01-11,9.08,9.28,9.06,9.25,89000000,815000000
000001,2024-01-12,9.22,9.35,9.18,9.30,78000000,720000000
000001,2024-01-15,9.28,9.32,9.20,9.22,70000000,648000000
```

- [ ] **Step 3: 运行简单验证**

```bash
cd D:\AutoTrade
python -c "
import pandas as pd
df = pd.read_csv('tests/fixtures/000001_daily.csv')
print(f'Loaded {len(df)} bars')
print(df.head())
"
```
Expected: 10 bars loaded

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: add akshare datasource and test fixtures"
```

---

### Task 6: 指标插件实现（MA / MACD / RSI / 布林带）

**Files:**
- Create: `autotrade/indicators/ma.py`
- Create: `autotrade/indicators/macd.py`
- Create: `autotrade/indicators/rsi.py`
- Create: `autotrade/indicators/bollinger.py`

- [ ] **Step 1: 实现 MA 指标**

```python
"""均线指标（MA/EMA）。

输出列:
- ind_ma_{period}: 简单移动平均线
- ind_ema_{period}: 指数移动平均线
"""

from __future__ import annotations

import pandas as pd
import pandas_ta as ta

from autotrade.core.interfaces import Indicator


class MA(Indicator):
    name = "ma"
    params = {"period": 20}

    def __init__(self, period: int = 20, mode: str = "sma"):
        self.period = period
        self.mode = mode
        self.name = "ma"
        self.params = {"period": period, "mode": mode}

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        col = f"ind_ma_{self.period}"
        if col in df.columns:
            return df

        if self.mode == "ema":
            df[col] = ta.ema(df["close"], length=self.period)
        else:
            df[col] = ta.sma(df["close"], length=self.period)
        return df


class EMA(Indicator):
    name = "ema"
    params = {"period": 20}

    def __init__(self, period: int = 20):
        self.period = period
        self.name = "ema"
        self.params = {"period": period}

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        col = f"ind_ema_{self.period}"
        if col in df.columns:
            return df
        df[col] = ta.ema(df["close"], length=self.period)
        return df
```

- [ ] **Step 2: 实现 MACD 指标**

```python
"""MACD 指标。

输出列:
- ind_macd_macd: MACD 快线
- ind_macd_signal: 信号线
- ind_macd_histogram: 柱状图（macd - signal）
"""

from __future__ import annotations

import pandas as pd
import pandas_ta as ta

from autotrade.core.interfaces import Indicator


class MACD(Indicator):
    name = "macd"
    params = {"fast": 12, "slow": 26, "signal": 9}

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        self.fast = fast
        self.slow = slow
        self.signal = signal
        self.name = "macd"
        self.params = {"fast": fast, "slow": slow, "signal": signal}

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        if "ind_macd_macd" in df.columns:
            return df
        result = ta.macd(df["close"], fast=self.fast, slow=self.slow, signal=self.signal)
        if result is not None:
            df["ind_macd_macd"] = result.iloc[:, 0]
            df["ind_macd_signal"] = result.iloc[:, 1]
            df["ind_macd_histogram"] = result.iloc[:, 2]
        return df
```

- [ ] **Step 3: 实现 RSI 指标**

```python
"""RSI 指标。

输出列:
- ind_rsi_{period}: 相对强弱指标
"""

from __future__ import annotations

import pandas as pd
import pandas_ta as ta

from autotrade.core.interfaces import Indicator


class RSI(Indicator):
    name = "rsi"
    params = {"period": 14}

    def __init__(self, period: int = 14):
        self.period = period
        self.name = "rsi"
        self.params = {"period": period}

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        col = f"ind_rsi_{self.period}"
        if col in df.columns:
            return df
        df[col] = ta.rsi(df["close"], length=self.period)
        return df
```

- [ ] **Step 4: 实现布林带指标**

```python
"""布林带（Bollinger Bands）指标。

输出列:
- ind_bb_upper_{period}: 上轨
- ind_bb_middle_{period}: 中轨（SMA）
- ind_bb_lower_{period}: 下轨
- ind_bb_width_{period}: 带宽
"""

from __future__ import annotations

import pandas as pd
import pandas_ta as ta

from autotrade.core.interfaces import Indicator


class BollingerBands(Indicator):
    name = "bb"
    params = {"period": 20, "std": 2}

    def __init__(self, period: int = 20, std: float = 2.0):
        self.period = period
        self.std = std
        self.name = "bb"
        self.params = {"period": period, "std": std}

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        if f"ind_bb_upper_{self.period}" in df.columns:
            return df
        result = ta.bbands(df["close"], length=self.period, std=self.std)
        if result is not None:
            df[f"ind_bb_upper_{self.period}"] = result.iloc[:, 0]
            df[f"ind_bb_middle_{self.period}"] = result.iloc[:, 1]
            df[f"ind_bb_lower_{self.period}"] = result.iloc[:, 2]
            # 计算带宽
            mid = df[f"ind_bb_middle_{self.period}"]
            upper = df[f"ind_bb_upper_{self.period}"]
            lower = df[f"ind_bb_lower_{self.period}"]
            df[f"ind_bb_width_{self.period}"] = (upper - lower) / mid
        return df
```

- [ ] **Step 5: 编写指标单元测试 tests/unit/test_indicators.py**

```python
"""指标计算单元测试。"""
import pytest
import pandas as pd
import numpy as np
from datetime import date
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
```

- [ ] **Step 6: 运行测试**

```bash
cd D:\AutoTrade
pytest tests/unit/test_indicators.py -v
```
Expected: 7 passed

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: implement MA/MACD/RSI/Bollinger indicators"
```

---

### Task 7: 策略插件实现（均线交叉 + MACD 背离）

**Files:**
- Create: `autotrade/strategies/ma_cross.py`
- Create: `autotrade/strategies/macd_divergence.py`
- Create: `config/strategies/ma_cross.yaml`

- [ ] **Step 1: 实现均线交叉策略**

```python
"""均线交叉策略。

规则:
- 快线上穿慢线 → BUY 信号（strength=1.0）
- 快线下穿慢线 → SELL 信号（strength=1.0）
- 否则 → HOLD

参数（来自 config/strategies/ma_cross.yaml）:
  fast: 5
  slow: 20
  stop_loss: 0.05
  take_profit: 0.15
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from autotrade.core.interfaces import Strategy
from autotrade.core.models import Signal
from autotrade.indicators.ma import MA


class MACrossStrategy(Strategy):
    name = "ma_cross"
    required_indicators = [MA(period=5), MA(period=20)]

    def __init__(self, fast: int = 5, slow: int = 20,
                 stop_loss: float = 0.05, take_profit: float = 0.15):
        self.fast = fast
        self.slow = slow
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.name = "ma_cross"
        self.required_indicators = [MA(period=fast), MA(period=slow)]

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        signals: list[Signal] = []
        fast_col = f"ind_ma_{self.fast}"
        slow_col = f"ind_ma_{self.slow}"

        if fast_col not in df.columns or slow_col not in df.columns:
            return signals

        fast_series = df[fast_col]
        slow_series = df[slow_col]

        # 前 self.slow 天无信号（指标尚未稳定）
        prev_fast = None
        prev_slow = None
        entry_price: float | None = None

        for idx, (i, row) in enumerate(df.iterrows()):
            current_fast = fast_series.loc[i]
            current_slow = slow_series.loc[i]

            if pd.isna(current_fast) or pd.isna(current_slow):
                prev_fast = current_fast
                prev_slow = current_slow
                continue

            if prev_fast is not None and prev_slow is not None:
                if not pd.isna(prev_fast) and not pd.isna(prev_slow):
                    # 金叉：快线上穿慢线
                    if prev_fast <= prev_slow and current_fast > current_slow:
                        signals.append(Signal(
                            symbol="",  # 由编排层填充
                            date=row.get("date", df.index[idx]) if isinstance(df.index[idx], date) else df.index[idx],
                            action="BUY",
                            strength=1.0,
                            reason=f"MA{self.fast}上穿MA{self.slow}",
                        ))
                        entry_price = float(row.get("close", current_fast))

                    # 死叉：快线下穿慢线
                    elif prev_fast >= prev_slow and current_fast < current_slow:
                        signals.append(Signal(
                            symbol="",
                            date=row.get("date", df.index[idx]) if isinstance(df.index[idx], date) else df.index[idx],
                            action="SELL",
                            strength=1.0,
                            reason=f"MA{self.fast}下穿MA{self.slow}",
                        ))
                        entry_price = None

                    # 止损/止盈检查（基于当前持仓）
                    if entry_price is not None:
                        current_price = float(row.get("close", current_fast))
                        pnl_pct = (current_price - entry_price) / entry_price
                        if pnl_pct <= -self.stop_loss:
                            signals.append(Signal(
                                symbol="",
                                date=row.get("date", df.index[idx]) if isinstance(df.index[idx], date) else df.index[idx],
                                action="SELL",
                                strength=1.0,
                                reason=f"止损({pnl_pct:.1%})",
                            ))
                            entry_price = None
                        elif self.take_profit > 0 and pnl_pct >= self.take_profit:
                            signals.append(Signal(
                                symbol="",
                                date=row.get("date", df.index[idx]) if isinstance(df.index[idx], date) else df.index[idx],
                                action="SELL",
                                strength=1.0,
                                reason=f"止盈({pnl_pct:.1%})",
                            ))
                            entry_price = None

            prev_fast = current_fast
            prev_slow = current_slow

        return signals
```

- [ ] **Step 2: 创建策略参数 YAML**

```yaml
# config/strategies/ma_cross.yaml
strategy: ma_cross
params:
  fast: 5
  slow: 20
  stop_loss: 0.05
  take_profit: 0.15
```

- [ ] **Step 3: 实现 MACD 背离策略**

```python
"""MACD 背离策略。

规则:
- 底背离（价格新低 + MACD 未新低）→ BUY
- 顶背离（价格新高 + MACD 未新高）→ SELL
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from autotrade.core.interfaces import Strategy
from autotrade.core.models import Signal
from autotrade.indicators.macd import MACD


class MACDDivergenceStrategy(Strategy):
    name = "macd_divergence"
    required_indicators = [MACD()]

    def __init__(self, lookback: int = 30):
        self.lookback = lookback
        self.name = "macd_divergence"
        self.required_indicators = [MACD()]

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        signals: list[Signal] = []

        if "ind_macd_macd" not in df.columns:
            return signals

        macd = df["ind_macd_macd"]
        close = df["close"] if "close" in df.columns else None

        if close is None:
            return signals

        for idx in range(self.lookback, len(df)):
            lookback_df = df.iloc[idx - self.lookback: idx + 1]
            lookback_close = close.iloc[idx - self.lookback: idx + 1]
            lookback_macd = macd.iloc[idx - self.lookback: idx + 1]

            if lookback_macd.isna().any():
                continue

            current_close = lookback_close.iloc[-1]
            current_macd = lookback_macd.iloc[-1]
            min_close_idx = lookback_close.idxmin()
            min_macd_at_price_low = lookback_macd.loc[min_close_idx]

            max_close_idx = lookback_close.idxmax()
            max_macd_at_price_high = lookback_macd.loc[max_close_idx]

            current_date = df.index[idx] if not isinstance(df.index[idx], date) else df.index[idx]

            # 底背离：价格新低但 MACD 未新低
            if (current_close == lookback_close.min() and
                    current_macd > min_macd_at_price_low):
                signals.append(Signal(
                    symbol="",
                    date=current_date,
                    action="BUY",
                    strength=0.8,
                    reason="MACD底背离",
                ))

            # 顶背离：价格新高但 MACD 未新高
            if (current_close == lookback_close.max() and
                    current_macd < max_macd_at_price_high):
                signals.append(Signal(
                    symbol="",
                    date=current_date,
                    action="SELL",
                    strength=0.8,
                    reason="MACD顶背离",
                ))

        return signals
```

- [ ] **Step 4: 编写策略单元测试 tests/unit/test_strategies.py**

```python
"""策略单元测试。"""
import pytest
import pandas as pd
import numpy as np
from autotrade.strategies.ma_cross import MACrossStrategy
from autotrade.strategies.macd_divergence import MACDDivergenceStrategy
from autotrade.indicators.ma import MA
from autotrade.indicators.macd import MACD


@pytest.fixture
def trending_up_df():
    """持续上涨趋势（快线始终在慢线上方，但初始交叉有信号）。"""
    np.random.seed(42)
    dates = pd.date_range("2024-01-01", periods=60, freq="D")
    close = 10 + np.linspace(0, 5, 60) + np.random.randn(60) * 0.2
    df = pd.DataFrame({
        "close": close,
        "open": close + np.random.randn(60) * 0.1,
        "high": close + 0.3,
        "low": close - 0.3,
        "volume": np.random.randint(1e6, 1e7, 60),
    }, index=dates)
    # 计算指标
    ma_fast = MA(period=5)
    ma_slow = MA(period=20)
    df = ma_fast.compute(df)
    df = ma_slow.compute(df)
    return df


class TestStrategies:
    def test_ma_cross_generates_signals(self, trending_up_df):
        strategy = MACrossStrategy(fast=5, slow=20)
        signals = strategy.generate_signals(trending_up_df)
        assert len(signals) > 0
        # 应有 BUY 或 SELL
        actions = [s.action for s in signals]
        assert "BUY" in actions or "SELL" in actions

    def test_macd_divergence_creates_signals(self, trending_up_df):
        """在较长数据上应能产生信号。"""
        # 先用 MACD 计算
        macd_ind = MACD()
        df = macd_ind.compute(trending_up_df)
        strategy = MACDDivergenceStrategy(lookback=15)
        signals = strategy.generate_signals(df)
        # 至少返回信号列表（可能为空）
        assert isinstance(signals, list)

    def test_ma_cross_signal_has_reason(self, trending_up_df):
        strategy = MACrossStrategy(fast=5, slow=20)
        signals = strategy.generate_signals(trending_up_df)
        if signals:
            assert len(signals[0].reason) > 0
```

- [ ] **Step 5: 运行测试**

```bash
cd D:\AutoTrade
pytest tests/unit/test_strategies.py -v
```
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: implement MA cross and MACD divergence strategies"
```

---

### Task 8: 报告插件实现（Console / CSV / Plot）

**Files:**
- Create: `autotrade/reporters/console.py`
- Create: `autotrade/reporters/csv_reporter.py`
- Create: `autotrade/reporters/plot_reporter.py`

- [ ] **Step 1: 实现终端报告（rich）**

```python
"""终端报告输出（rich 表格）。"""

from __future__ import annotations

from autotrade.core.interfaces import Reporter
from autotrade.core.models import BacktestResult


class ConsoleReporter(Reporter):
    """在终端以 rich 表格形式输出回测结果。"""

    name = "console"

    def render(self, result: BacktestResult) -> None:
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel

        console = Console()

        # 标题
        console.print(Panel.fit(f"[bold]回测结果: {result.symbol}", border_style="blue"))

        # 汇总指标
        metrics_table = Table(title="汇总指标", show_header=True, header_style="bold cyan")
        metrics_table.add_column("指标", style="dim")
        metrics_table.add_column("值")

        if result.metrics:
            for key, val in result.metrics.items():
                if isinstance(val, float):
                    metrics_table.add_row(key, f"{val:.2f}")
                else:
                    metrics_table.add_row(key, str(val))

        console.print(metrics_table)

        # 交易记录
        if result.trades:
            trades_table = Table(title=f"交易记录 ({len(result.trades)} 笔)",
                                 show_header=True, header_style="bold green")
            trades_table.add_column("日期")
            trades_table.add_column("方向")
            trades_table.add_column("价格")
            trades_table.add_column("数量")
            trades_table.add_column("佣金")
            trades_table.add_column("印花税")

            for t in result.trades:
                trades_table.add_row(
                    str(t.date),
                    t.action,
                    f"{t.price:.2f}",
                    str(t.quantity),
                    f"{t.commission:.2f}",
                    f"{t.stamp_duty:.2f}" if t.stamp_duty else "-",
                )

            console.print(trades_table)

        # 信号摘要
        if result.signals:
            from rich.text import Text
            buy_count = sum(1 for s in result.signals if s.action == "BUY")
            sell_count = sum(1 for s in result.signals if s.action == "SELL")
            hold_count = sum(1 for s in result.signals if s.action == "HOLD")
            console.print(f"[dim]信号: {buy_count} BUY / {sell_count} SELL / {hold_count} HOLD[/dim]")

        console.print()  # 空行
```

- [ ] **Step 2: 实现 CSV 报告**

```python
"""CSV 报告输出。"""

from __future__ import annotations

import csv
import os
from pathlib import Path

from autotrade.core.interfaces import Reporter
from autotrade.core.models import BacktestResult


class CSVReporter(Reporter):
    """将回测结果输出为 CSV 文件。"""

    name = "csv"

    def __init__(self, output_dir: str = "data/results"):
        self.output_dir = output_dir

    def render(self, result: BacktestResult) -> str:
        """输出 CSV 并返回文件路径。"""
        os.makedirs(self.output_dir, exist_ok=True)

        # 指标文件
        metrics_path = os.path.join(
            self.output_dir,
            f"{result.symbol}_metrics.csv"
        )
        with open(metrics_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["metric", "value"])
            for key, val in (result.metrics or {}).items():
                writer.writerow([key, val])

        # 交易记录文件
        trades_path = os.path.join(
            self.output_dir,
            f"{result.symbol}_trades.csv"
        )
        with open(trades_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "action", "price", "quantity",
                             "commission", "stamp_duty"])
            for t in result.trades:
                writer.writerow([
                    t.date, t.action, t.price, t.quantity,
                    t.commission, t.stamp_duty,
                ])

        # 净值曲线
        if result.equity_curve is not None:
            equity_path = os.path.join(
                self.output_dir,
                f"{result.symbol}_equity.csv"
            )
            result.equity_curve.to_csv(equity_path, header=["equity"])

        return metrics_path
```

- [ ] **Step 3: 实现图表报告（matplotlib）**

```python
"""图表报告输出（matplotlib）。"""

from __future__ import annotations

import os

from autotrade.core.interfaces import Reporter
from autotrade.core.models import BacktestResult


class PlotReporter(Reporter):
    """生成回测图表（净值曲线、买卖点标注）。"""

    name = "plot"

    def __init__(self, output_dir: str = "data/results", show: bool = False):
        self.output_dir = output_dir
        self.show = show

    def render(self, result: BacktestResult) -> str:
        """生成图表并保存到文件，返回文件路径。"""
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates

        os.makedirs(self.output_dir, exist_ok=True)

        fig, axes = plt.subplots(2, 1, figsize=(12, 8), gridspec_kw={"height_ratios": [3, 1]})

        # 净值曲线 + 买卖点
        ax1 = axes[0]
        if result.equity_curve is not None:
            ax1.plot(result.equity_curve.index, result.equity_curve.values,
                     label="Equity", color="blue", linewidth=1.5)
            ax1.fill_between(result.equity_curve.index, result.equity_curve.values,
                             alpha=0.1, color="blue")

        # 标注买卖点
        buy_dates = [t.date for t in result.trades if t.action == "BUY"]
        sell_dates = [t.date for t in result.trades if t.action == "SELL"]

        if buy_dates and result.equity_curve is not None:
            buy_vals = [result.equity_curve.get(d, None) for d in buy_dates]
            buy_vals = [v for v in buy_vals if v is not None]
            if buy_vals:
                ax1.scatter(buy_dates[:len(buy_vals)], buy_vals,
                           color="red", marker="^", s=80, label="BUY", zorder=5)

        if sell_dates and result.equity_curve is not None:
            sell_vals = [result.equity_curve.get(d, None) for d in sell_dates]
            sell_vals = [v for v in sell_vals if v is not None]
            if sell_vals:
                ax1.scatter(sell_dates[:len(sell_vals)], sell_vals,
                           color="green", marker="v", s=80, label="SELL", zorder=5)

        ax1.set_title(f"{result.symbol} 回测净值曲线")
        ax1.set_ylabel("净值")
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
        ax1.xaxis.set_major_locator(mdates.WeekdayLocator())

        # 回撤曲线
        ax2 = axes[1]
        if result.equity_curve is not None:
            peak = result.equity_curve.cummax()
            drawdown = (peak - result.equity_curve) / peak * 100
            ax2.fill_between(drawdown.index, drawdown.values, 0,
                             color="red", alpha=0.3, label="Drawdown")
            ax2.plot(drawdown.index, drawdown.values, color="red", linewidth=1)
            ax2.set_ylabel("回撤 (%)")
            ax2.set_xlabel("日期")
            ax2.grid(True, alpha=0.3)
            ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
            ax2.xaxis.set_major_locator(mdates.WeekdayLocator())

        plt.tight_layout()
        filepath = os.path.join(self.output_dir, f"{result.symbol}_backtest.png")
        plt.savefig(filepath, dpi=150, bbox_inches="tight")

        if self.show:
            plt.show()
        else:
            plt.close()

        return filepath
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: implement console/CSV/plot reporters"
```

---

### Task 9: 编排引擎

**Files:**
- Create: `autotrade/core/engine.py`

- [ ] **Step 1: 实现编排引擎**

```python
"""编排层 —— 串联数据获取 → 指标计算 → 策略信号 → 回测 → 报告。

核心函数:
- analyze_stock(): 单股分析+回测，最基础入口
- analyze_universe(): 批量回测一组股票
- run_backtest(): 顶层入口，支持单股/多股/全市场，渲染报告
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from autotrade.core.backtester import Backtester
from autotrade.core.config import get_backtest_config, load_config
from autotrade.core.interfaces import DataSource, Indicator, Reporter, Strategy
from autotrade.core.models import BacktestConfig, BacktestResult, Signal
from autotrade.registry import (
    get_datasource, get_indicator, get_reporter, get_strategy,
    init_registry, list_strategies,
)

logger = logging.getLogger(__name__)


def analyze_stock(
    symbol: str,
    strategy_name: str,
    start: date,
    end: date,
    datasource_name: str = "akshare",
    backtest_config: Optional[BacktestConfig] = None,
    strategy_params: Optional[dict] = None,
) -> BacktestResult:
    """单股分析+回测。最基础入口，被其他所有触发方式复用。

    Args:
        symbol: 股票代码。
        strategy_name: 策略名。
        start: 开始日期。
        end: 结束日期。
        datasource_name: 数据源名。
        backtest_config: 回测配置，None 则从全局配置加载。
        strategy_params: 策略参数，None 则从 YAML 加载。

    Returns:
        BacktestResult 包含成交记录、净值曲线、汇总指标。
    """
    # 1. 获取插件
    ds_cls = get_datasource(datasource_name)
    ds = ds_cls() if isinstance(ds_cls, type) else ds_cls

    strategy_cls = get_strategy(strategy_name)
    strategy = _instantiate_strategy(strategy_cls, strategy_params)

    # 2. 获取行情数据
    bars = ds.get_bars(symbol, start, end)
    if not bars:
        logger.warning("No bar data for %s from %s to %s", symbol, start, end)
        return BacktestResult(symbol=symbol, metrics={"error": "No data"})

    # 3. list[Bar] → DataFrame
    df = _bars_to_dataframe(bars)

    # 4. 计算指标
    for ind in strategy.required_indicators:
        df = ind.compute(df)

    # 5. 生成信号（填充 symbol）
    raw_signals = strategy.generate_signals(df)
    for sig in raw_signals:
        if not sig.symbol:
            sig.symbol = symbol

    # 6. 回测撮合
    config = backtest_config or _make_backtest_config()
    backtester = Backtester(config)
    result = backtester.run(raw_signals, bars)
    result.signals = raw_signals

    logger.info(
        "Analyzed %s with %s: %d trades, return %.2f%%",
        symbol, strategy_name, len(result.trades),
        result.metrics.get("total_return_pct", 0.0),
    )

    return result


def analyze_universe(
    symbols: list[str],
    strategy_name: str,
    start: date,
    end: date,
    datasource_name: str = "akshare",
    backtest_config: Optional[BacktestConfig] = None,
    strategy_params: Optional[dict] = None,
) -> list[BacktestResult]:
    """批量回测一组股票。"""
    results: list[BacktestResult] = []
    for symbol in symbols:
        try:
            result = analyze_stock(
                symbol, strategy_name, start, end,
                datasource_name, backtest_config, strategy_params,
            )
            results.append(result)
        except Exception as e:
            logger.error("Failed to analyze %s: %s", symbol, e)
            results.append(BacktestResult(
                symbol=symbol,
                metrics={"error": str(e)},
            ))
    return results


def run_backtest(
    strategy_name: str,
    symbols: str | list[str] = "all",
    start: Optional[date] = None,
    end: Optional[date] = None,
    datasource_name: str = "akshare",
    backtest_config: Optional[BacktestConfig] = None,
    strategy_params: Optional[dict] = None,
    reporter_names: tuple[str, ...] = ("console",),
) -> dict[str, Any]:
    """顶层入口：支持单股/多股/全市场，渲染报告，返回汇总。

    Args:
        strategy_name: 策略名。
        symbols: 股票代码列表，"all" 表示全市场。
        start: 开始日期。
        end: 结束日期。
        datasource_name: 数据源名。
        backtest_config: 回测配置。
        strategy_params: 策略参数。
        reporter_names: 报告输出方式列表。

    Returns:
        汇总字典。
    """
    # 确保注册表已初始化
    init_registry()

    # 解析日期
    if end is None:
        end = date.today()
    if start is None:
        start = date(end.year - 1, end.month, end.day)  # 默认一年

    # 解析符号
    resolved_symbols = _resolve_symbols(symbols, datasource_name)

    if not resolved_symbols:
        return {"error": "No symbols to analyze", "results": []}

    # 运行回测
    if len(resolved_symbols) == 1:
        result = analyze_stock(
            resolved_symbols[0], strategy_name, start, end,
            datasource_name, backtest_config, strategy_params,
        )
        results_list = [result]
    else:
        results_list = analyze_universe(
            resolved_symbols, strategy_name, start, end,
            datasource_name, backtest_config, strategy_params,
        )

    # 渲染报告
    for result in results_list:
        for rep_name in reporter_names:
            try:
                reporter_cls = get_reporter(rep_name)
                reporter = reporter_cls() if isinstance(reporter_cls, type) else reporter_cls
                reporter.render(result)
            except Exception as e:
                logger.error("Reporter '%s' failed: %s", rep_name, e)

    # 汇总
    summary = _summarize(results_list)
    return summary


def _bars_to_dataframe(bars) -> pd.DataFrame:
    """将 list[Bar] 转为 DataFrame。"""
    records = []
    for bar in bars:
        records.append({
            "date": bar.date,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
            "amount": bar.amount,
        })
    df = pd.DataFrame(records)
    if "date" in df.columns and not df.empty:
        df.set_index("date", inplace=True)
    return df


def _resolve_symbols(symbols: str | list[str],
                     datasource_name: str = "akshare") -> list[str]:
    """解析符号参数为列表。"""
    if isinstance(symbols, list):
        return symbols
    if symbols == "all":
        ds_cls = get_datasource(datasource_name)
        ds = ds_cls() if isinstance(ds_cls, type) else ds_cls
        return ds.list_symbols()
    return [s.strip() for s in symbols.split(",") if s.strip()]


def _make_backtest_config() -> BacktestConfig:
    """从全局配置创建 BacktestConfig。"""
    cfg = load_config()
    bc = get_backtest_config(cfg)
    return BacktestConfig(
        initial_capital=float(bc.get("initial_capital", 100000)),
        fill_price=str(bc.get("fill_price", "next_open")),
        commission_rate=float(bc.get("commission_rate", 0.0003)),
        stamp_duty_rate=float(bc.get("stamp_duty_rate", 0.001)),
        slippage=float(bc.get("slippage", 0.001)),
        min_commission=float(bc.get("min_commission", 5.0)),
        lot_size=int(bc.get("lot_size", 100)),
        allow_t_plus_1=bool(bc.get("allow_t_plus_1", True)),
        position_sizing=str(bc.get("position_sizing", "strength")),
        max_positions=int(bc.get("max_positions", 1)),
    )


def _instantiate_strategy(strategy_cls: type, params: Optional[dict] = None) -> Strategy:
    """实例化策略，应用参数。"""
    if params:
        return strategy_cls(**params)
    return strategy_cls()


def _summarize(results: list[BacktestResult]) -> dict[str, Any]:
    """汇总多个回测结果。"""
    valid = [r for r in results if r.metrics and "error" not in r.metrics]
    errors = [r for r in results if r.metrics and "error" in r.metrics]

    summary = {
        "total": len(results),
        "success": len(valid),
        "failed": len(errors),
        "results": [],
    }

    if valid:
        returns = [r.metrics.get("total_return_pct", 0) for r in valid]
        summary["avg_return_pct"] = round(sum(float(r) for r in returns) / len(returns), 2)
        summary["positive_count"] = sum(1 for r in returns if float(r) > 0)
        summary["negative_count"] = sum(1 for r in returns if float(r) <= 0)

    for r in valid:
        summary["results"].append({
            "symbol": r.symbol,
            "trades": len(r.trades),
            "return_pct": r.metrics.get("total_return_pct", 0),
            "sharpe": r.metrics.get("sharpe_ratio", 0),
        })

    return summary
```

- [ ] **Step 2: 编写集成测试 tests/integration/test_engine.py**

```python
"""编排层集成测试（使用 fixture 数据，不依赖网络）。"""
import pytest
from datetime import date
from autotrade.core.models import BacktestConfig
from autotrade.core.engine import _bars_to_dataframe, analyze_stock
from autotrade.registry import init_registry


@pytest.fixture
def bars_from_fixture():
    """从 fixture CSV 加载数据。"""
    import pandas as pd
    df = pd.read_csv("tests/fixtures/000001_daily.csv")
    from autotrade.core.models import Bar
    bars = []
    for _, row in df.iterrows():
        bars.append(Bar(
            symbol=row["symbol"],
            date=row["date"] if isinstance(row["date"], date) else date.fromisoformat(str(row["date"])),
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
        assert "ma" in indicators or "macd" in indicators
```

- [ ] **Step 3: 运行测试**

```bash
cd D:\AutoTrade
pytest tests/integration/test_engine.py -v
```
Expected: 2 passed

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: implement orchestration engine"
```

---

### Task 10: CLI 触发层

**Files:**
- Create: `autotrade/triggers/cli.py`

- [ ] **Step 1: 实现 CLI**

```python
"""CLI 入口（click）。

子命令:
- analyze: 单股快速验证
- backtest: 指定股票池批量
- scan: 全市场扫描找标的
- list: 自省（看有哪些插件）
- show: 复看历史结果
- run-scheduled: 手动触发定时任务

Usage:
    autotrade analyze --symbol 000001 --strategy ma_cross --start 2024-01-01
    autotrade list strategies
    autotrade scan --strategy ma_cross --top 10
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import click

from autotrade.core.config import load_config, get_strategy_params
from autotrade.core.engine import run_backtest
from autotrade.registry import (
    init_registry, list_datasources, list_indicators,
    list_strategies, list_reporters,
)

logger = logging.getLogger(__name__)


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="显示调试日志")
def cli(verbose: bool):
    """AutoTrade: A股自动化交易信号生成与回测系统。"""
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    init_registry()


@cli.command()
@click.option("--symbol", required=True, help="股票代码，如 000001")
@click.option("--strategy", "strategy_name", required=True, help="策略名")
@click.option("--start", default=None, help="开始日期 (YYYY-MM-DD)")
@click.option("--end", default=None, help="结束日期 (YYYY-MM-DD)")
@click.option("--datasource", default=None, help="数据源 (默认 akshare)")
@click.option("--reporters", default="console", help="报告输出方式，逗号分隔")
def analyze(symbol: str, strategy_name: str, start: Optional[str],
            end: Optional[str], datasource: Optional[str],
            reporters: str):
    """分析单只股票（含回测）。"""
    _run_and_report(
        strategy_name=strategy_name,
        symbols=symbol,
        start=start,
        end=end,
        datasource=datasource,
        reporters=reporters,
    )


@cli.command()
@click.option("--strategy", "strategy_name", required=True, help="策略名")
@click.option("--symbols", required=True, help="股票代码列表，逗号分隔")
@click.option("--start", default=None, help="开始日期 (YYYY-MM-DD)")
@click.option("--end", default=None, help="结束日期 (YYYY-MM-DD)")
@click.option("--datasource", default=None, help="数据源 (默认 akshare)")
@click.option("--reporters", default="console", help="报告输出方式，逗号分隔")
def backtest(strategy_name: str, symbols: str, start: Optional[str],
             end: Optional[str], datasource: Optional[str],
             reporters: str):
    """批量回测多只股票。"""
    _run_and_report(
        strategy_name=strategy_name,
        symbols=symbols,
        start=start,
        end=end,
        datasource=datasource,
        reporters=reporters,
    )


@cli.command()
@click.option("--strategy", "strategy_name", required=True, help="策略名")
@click.option("--universe", default="all", help="股票池 (默认 all 全市场)")
@click.option("--end", default=None, help="结束日期 (YYYY-MM-DD)")
@click.option("--datasource", default=None, help="数据源 (默认 akshare)")
@click.option("--top", default=20, type=int, help="只显示前 N 名")
@click.option("--min-trades", default=1, type=int, help="最少交易次数")
def scan(strategy_name: str, universe: str, end: Optional[str],
         datasource: Optional[str], top: int, min_trades: int):
    """全市场扫描，按收益率排序。"""
    start = None  # 默认一年
    if end:
        end_date = date.fromisoformat(end)
    else:
        end_date = date.today()

    summary = _run_and_report(
        strategy_name=strategy_name,
        symbols=universe,
        start=None,
        end=end,
        datasource=datasource,
        reporters="console",
    )

    if summary and "results" in summary:
        # 排序显示
        sorted_results = sorted(
            summary["results"],
            key=lambda r: float(r.get("return_pct", 0)),
            reverse=True,
        )
        filtered = [r for r in sorted_results
                    if int(r.get("trades", 0)) >= min_trades][:top]

        click.echo(f"\n=== Top {top} 结果 ===")
        click.echo(f"{'排名':<6} {'代码':<10} {'收益率%':<12} {'交易次数':<10} {'夏普':<10}")
        click.echo("-" * 50)
        for idx, r in enumerate(filtered, 1):
            click.echo(
                f"{idx:<6} {r['symbol']:<10} "
                f"{float(r['return_pct']):<12.2f} "
                f"{int(r['trades']):<10} "
                f"{float(r.get('sharpe', 0)):<10.4f}"
            )


@cli.command()
@click.argument("component", type=click.Choice(["strategies", "indicators",
                                                  "datasources", "reporters"]))
def list_plugins(component: str):
    """列出可用插件。"""
    registry_map = {
        "strategies": ("策略", list_strategies()),
        "indicators": ("指标", list_indicators()),
        "datasources": ("数据源", list_datasources()),
        "reporters": ("报告", list_reporters()),
    }

    label, items = registry_map[component]
    click.echo(f"\n可用 {label} ({len(items)}):")
    if items:
        for item in items:
            click.echo(f"  • {item}")
    else:
        click.echo("  (空)")


@cli.command()
@click.option("--result", required=True, help="结果文件路径 (.json)")
def show(result: str):
    """复看历史结果。"""
    path = Path(result)
    if not path.exists():
        click.echo(f"文件不存在: {result}", err=True)
        return

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    click.echo(f"\n回测结果: {data.get('symbol', 'unknown')}")
    for key, val in data.get("metrics", {}).items():
        click.echo(f"  {key}: {val}")


def _parse_date(date_str: Optional[str]) -> Optional[date]:
    """解析日期字符串。"""
    if not date_str:
        return None
    return date.fromisoformat(date_str)


def _run_and_report(strategy_name: str, symbols: str,
                    start: Optional[str], end: Optional[str],
                    datasource: Optional[str],
                    reporters: str = "console") -> dict:
    """统一执行入口。"""
    config = load_config()
    ds = datasource or config.get("datasource", {}).get("default", "akshare")
    reporter_list = [r.strip() for r in reporters.split(",") if r.strip()]

    # 加载策略参数
    strategy_params = get_strategy_params(strategy_name)

    summary = run_backtest(
        strategy_name=strategy_name,
        symbols=symbols,
        start=_parse_date(start),
        end=_parse_date(end),
        datasource_name=ds,
        reporter_names=tuple(reporter_list),
        strategy_params=strategy_params.get("params") if strategy_params else None,
    )

    # 输出汇总
    if summary and "avg_return_pct" in summary:
        click.echo(
            f"\n汇总: 成功 {summary['success']}/{summary['total']}, "
            f"平均收益率 {summary['avg_return_pct']:.2f}%, "
            f"正收益 {summary.get('positive_count', 0)} 只"
        )

    return summary
```

- [ ] **Step 2: 验证 CLI 可运行**

```bash
cd D:\AutoTrade
pip install -e .
autotrade --help
autotrade list strategies
autotrade list indicators
```
Expected: help 信息正常显示

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "feat: implement CLI with click commands"
```

---

### Task 11: 定时任务触发层

**Files:**
- Create: `autotrade/triggers/scheduler.py`
- Create: `config/scheduler.yaml`

- [ ] **Step 1: 实现调度器**

```python
"""定时任务触发（APScheduler）。

将 YAML 配置中的定时任务翻译为对 engine 的调用。
支持手动触发: autotrade run-scheduled <job_name>
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any, Optional

import yaml
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.schedulers.background import BackgroundScheduler

from autotrade.core.config import load_config
from autotrade.core.engine import run_backtest
from autotrade.registry import init_registry

logger = logging.getLogger(__name__)

_SCHEDULER_CONFIG_PATH = None  # 可在 init 时设置


def load_scheduler_config(path: Optional[str] = None) -> dict[str, Any]:
    """加载定时任务配置。"""
    from pathlib import Path
    if path is None:
        import autotrade
        pkg_dir = Path(autotrade.__file__).resolve().parent
        path = str(pkg_dir.parent / "config" / "scheduler.yaml")
    _SCHEDULER_CONFIG_PATH = path

    config_path = Path(path)
    if not config_path.exists():
        return {"jobs": []}

    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {"jobs": []}


def setup_scheduler(config: Optional[dict] = None,
                    background: bool = False) -> BackgroundScheduler:
    """设置并启动 APScheduler。

    Args:
        config: 任务配置字典，None 则从文件加载。
        background: True 用 BackgroundScheduler，False 用 BlockingScheduler。

    Returns:
        APScheduler 实例。
    """
    if config is None:
        config = load_scheduler_config()

    if background:
        scheduler = BackgroundScheduler()
    else:
        scheduler = BlockingScheduler()

    jobs_config = config.get("jobs", [])
    if not jobs_config:
        logger.warning("No scheduled jobs configured.")
        return scheduler

    for job_cfg in jobs_config:
        job_name = job_cfg.get("name", "unnamed")
        cron_expr = job_cfg.get("cron", "")
        command = job_cfg.get("command", {})
        reporters = job_cfg.get("reporters", ["console"])

        if not cron_expr or not command:
            logger.warning("Skipping job '%s': incomplete config", job_name)
            continue

        try:
            # 解析 cron 表达式: "30 15 * * 1-5"
            parts = cron_expr.strip().split()
            if len(parts) != 5:
                logger.warning("Invalid cron expression for job '%s': %s",
                               job_name, cron_expr)
                continue

            minute, hour, day, month, day_of_week = parts

            scheduler.add_job(
                func=_execute_job,
                trigger="cron",
                args=[command, reporters],
                id=job_name,
                name=job_name,
                minute=minute,
                hour=hour,
                day=day,
                month=month,
                day_of_week=day_of_week,
                replace_existing=True,
            )
            logger.info("Scheduled job '%s': %s", job_name, cron_expr)

        except Exception as e:
            logger.error("Failed to schedule job '%s': %s", job_name, e)

    return scheduler


def run_now(job_name: str) -> None:
    """立即执行一个定时任务（用于手动触发）。"""
    config = load_scheduler_config()
    for job_cfg in config.get("jobs", []):
        if job_cfg.get("name") == job_name:
            command = job_cfg.get("command", {})
            reporters = job_cfg.get("reporters", ["console"])
            _execute_job(command, reporters)
            return
    logger.error("Job '%s' not found in scheduler config", job_name)


def _execute_job(command: dict, reporters: list[str]) -> None:
    """执行一个任务（将配置翻译为 engine 调用）。"""
    init_registry()

    cmd_type = command.get("type", "backtest")
    strategy = command.get("strategy", "ma_cross")
    universe = command.get("universe", "all")
    symbols = command.get("symbols", "all")
    top = command.get("top", 20)
    datasource = command.get("datasource", "akshare")

    end = date.today()

    if cmd_type == "scan":
        logger.info("Scheduled scan: strategy=%s, universe=%s, top=%d",
                     strategy, universe, top)
        run_backtest(
            strategy_name=strategy,
            symbols=universe,
            end=end,
            datasource_name=datasource,
            reporter_names=tuple(reporters),
        )
    elif cmd_type == "backtest":
        logger.info("Scheduled backtest: strategy=%s, symbols=%s",
                     strategy, symbols)
        run_backtest(
            strategy_name=strategy,
            symbols=symbols,
            end=end,
            datasource_name=datasource,
            reporter_names=tuple(reporters),
        )
    elif cmd_type == "analyze":
        symbol = command.get("symbol", "000001")
        logger.info("Scheduled analyze: strategy=%s, symbol=%s",
                     strategy, symbol)
        run_backtest(
            strategy_name=strategy,
            symbols=symbol,
            end=end,
            datasource_name=datasource,
            reporter_names=tuple(reporters),
        )


def main():
    """调度器主入口（供 console_scripts 使用）。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    scheduler = setup_scheduler(background=False)
    try:
        scheduler.start()
    except KeyboardInterrupt:
        logger.info("Scheduler stopped by user")
```

- [ ] **Step 2: 创建 scheduler.yaml**

```yaml
# AutoTrade 定时任务配置
jobs:
  - name: daily-scan
    cron: "30 15 * * 1-5"        # 周一到周五 15:30
    command:
      type: scan
      strategy: ma_cross
      universe: all
      top: 20
    reporters: [console, csv]

  - name: weekly-review
    cron: "0 18 * * 5"           # 每周五 18:00
    command:
      type: backtest
      strategy: macd_divergence
      symbols: "000001,600519"
    reporters: [console, csv]
```

- [ ] **Step 3: 验证导入**

```bash
cd D:\AutoTrade
python -c "from autotrade.triggers.scheduler import setup_scheduler, load_scheduler_config; print('Scheduler OK')"
```
Expected: Scheduler OK

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: implement scheduler trigger with APScheduler"
```

---

### Task 12: 完整端到端验证

- [ ] **Step 1: 安装全部依赖**

```bash
cd D:\AutoTrade
pip install -e ".[dev,plot]"
```

- [ ] **Step 2: 运行全部单元测试**

```bash
cd D:\AutoTrade
pytest tests/unit/ -v
```
Expected: all unit tests pass

- [ ] **Step 3: 运行集成测试**

```bash
cd D:\AutoTrade
pytest tests/integration/ -v
```
Expected: integration tests pass

- [ ] **Step 4: 验证 CLI 全命令**

```bash
cd D:\AutoTrade
autotrade --help
autotrade list strategies
autotrade list indicators
autotrade list datasources
autotrade list reporters
```
Expected: 所有命令正常输出

- [ ] **Step 5: Commit 最终版本**

```bash
git add -A
git commit -m "chore: finalize MVP implementation"
```

---

## 实现顺序总结

| Task | 组件 | 依赖 | 文件数 |
|------|------|------|--------|
| 1 | 项目初始化 + models + interfaces | 无 | ~18 |
| 2 | 插件注册表 registry | Task 1 | 1 |
| 3 | 回测引擎 backtester | Task 1 | 1 |
| 4 | 配置加载 config | 无 | 2 |
| 5 | AkShare 数据源 | Task 1, 2 | 1 |
| 6 | 指标插件（MA/MACD/RSI/BB） | Task 1, 2 | 4 |
| 7 | 策略插件（均线交叉/MACD背离） | Task 1, 2, 6 | 2 |
| 8 | 报告插件（Console/CSV/Plot） | Task 1, 2 | 3 |
| 9 | 编排引擎 engine | All above | 1 |
| 10 | CLI 触发层 | Task 2, 9 | 1 |
| 11 | 定时任务触发层 | Task 2, 9 | 1 |
| 12 | 端到端验证 | All | 0 |
