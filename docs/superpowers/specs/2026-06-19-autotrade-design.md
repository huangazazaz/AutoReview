# AutoTrade 自动化交易（信号+回测）系统设计文档

- 状态: 已确认
- 日期: 2026-06-19
- 决策者: 用户 + ZCode

## 1. 概述

### 1.1 目标
构建一个面向 A 股市场的自动化交易**信号生成 + 回测**系统（MVP 不含真实下单），核心分析逻辑高度封装、可被多种触发方式（CLI / 定时 / 未来 Web API）复用。

### 1.2 MVP 范围

| ✅ MVP 包含 | ❌ MVP 不含（后续阶段） |
|-----------|---------------------|
| A 股日线数据获取（AkShare） | 分钟级/Tick 数据 |
| 技术指标（MA/MACD/RSI/布林） | 自定义复杂因子 |
| 2 个示例策略（均线交叉/MACD 背离） | 机器学习策略 |
| 回测引擎（T+1/手续费/分批仓位） | 真实下单 |
| 单股 + 批量 + 全市场回测 | 组合优化/资金分配 |
| 报告（终端/CSV/图表） | Web UI（仅预留接口） |
| CLI + 定时触发 | FastAPI 接口（仅预留目录） |
| 数据缓存 | 通知推送（webhook 占位） |

### 1.3 关键决策摘要
- 市场: 仅 A 股（T+1、涨跌停、100 股整数倍）
- 数据源: AkShare（默认）+ Tushare（可选），可插拔
- 语言/运行时: Python ≥ 3.10
- 策略类型: 技术指标策略
- 成交价: 可配（默认次日开盘价 / 可切当日收盘）
- 仓位规则: 按信号 strength 分批
- 架构: 自建轻量分层框架，全面插件化

详见 `docs/decisions/`。

## 2. 整体架构与分层

核心设计原则: **一切皆插件，触发层与核心解耦**。

```
┌─────────────────────────────────────────────────────────────┐
│  触发层 (Triggers)  ── 都是平等的"调用方"，可插拔              │
│   CLI (click)  │  定时任务(APScheduler)  │  未来: FastAPI Web │
└──────────────────────────┬──────────────────────────────────┘
                           │ 调用
┌──────────────────────────▼──────────────────────────────────┐
│  编排层 (Orchestration)  ── 不含业务逻辑，只做组装调度          │
│   单股分析  │  全市场批量回测  │  组合回测                       │
└──────────────────────────┬──────────────────────────────────┘
                           │ 依赖注入（插件）
┌──────────────────────────▼──────────────────────────────────┐
│  核心引擎层 (Core)  ── 纯逻辑，不关心数据来源/输出方式           │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌────────────────┐  │
│  │数据源     │→│指标计算   │→│策略引擎   │→│回测引擎         │  │
│  │DataSource│ │Indicator │ │Strategy  │ │Backtester      │  │
│  │(接口)    │ │(接口)    │ │(接口)    │ │(撮合/T+1/涨跌停)│  │
│  └──────────┘ └──────────┘ └──────────┘ └────────────────┘  │
│                           ↓                                 │
│                       ┌──────────┐                          │
│                       │报告生成   │                          │
│                       │Reporter  │                          │
│                       └──────────┘                          │
└─────────────────────────────────────────────────────────────┘
```

### 2.1 设计要点
1. **触发层与核心层完全解耦** —— CLI/定时/Web 都只是调用 `analyze_stock()` / `run_backtest()`，核心层不知道调用方是谁。这是"后续支持前端对接"的根基。
2. **每层用抽象基类(ABC)定义接口** —— DataSource、Indicator、Strategy、Reporter 都是接口，实现放各自目录。加新数据源 = 往 `datasources/` 加文件，零改动核心。
3. **编排层是粘合剂** —— 串联"取数据→算指标→跑策略→回测→出报告"，本身不含业务规则，便于不同触发方式复用。

## 3. 目录结构

```
D:\AutoTrade\
├── autotrade/                      # 主包
│   ├── __init__.py
│   ├── core/                       # 核心引擎层（纯逻辑，无 IO）
│   │   ├── __init__.py
│   │   ├── interfaces.py           # 抽象基类: DataSource/Indicator/Strategy/Reporter
│   │   ├── models.py               # 数据模型: Bar/Signal/Trade/Position/BacktestResult
│   │   ├── backtester.py           # 回测引擎（撮合/T+1/涨跌停/手续费）
│   │   ├── engine.py               # 编排器: analyze_stock()/run_backtest()/run_universe()
│   │   └── config.py               # 配置加载（YAML/env）
│   │
│   ├── datasources/                # 插件: 数据源
│   │   ├── __init__.py             # 注册表（按名查找）
│   │   ├── akshare_ds.py           # 默认实现（AkShare，免费）
│   │   └── tushare_ds.py           # 可选实现（需 token）
│   │
│   ├── indicators/                 # 插件: 技术指标/选股因子
│   │   ├── __init__.py             # 自动发现并注册目录内所有指标
│   │   ├── ma.py                   # 均线类（MA/EMA）
│   │   ├── macd.py
│   │   ├── rsi.py
│   │   └── bollinger.py
│   │
│   ├── strategies/                 # 插件: 策略（组合指标成买卖规则）
│   │   ├── __init__.py
│   │   ├── ma_cross.py             # 示例: 均线交叉
│   │   └── macd_divergence.py      # 示例: MACD 背离
│   │
│   ├── reporters/                  # 插件: 报告输出
│   │   ├── __init__.py
│   │   ├── console.py              # 终端打印（rich）
│   │   ├── csv_reporter.py         # CSV 落盘
│   │   └── plot_reporter.py        # matplotlib 图表
│   │
│   ├── triggers/                   # 触发层（调用方）
│   │   ├── __init__.py
│   │   ├── cli.py                  # CLI 入口（click）
│   │   └── scheduler.py            # 定时任务（APScheduler）
│   │
│   ├── api/                        # 预留: 未来 Web API（FastAPI）
│   │   └── __init__.py             # MVP 阶段为空占位
│   │
│   └── registry.py                 # 插件注册表与发现机制
│
├── data/                           # 运行时数据（gitignore）
│   ├── cache/                      # 行情数据本地缓存（parquet）
│   ├── results/                    # 回测结果输出
│   └── logs/                       # 日志
│
├── config/                         # 用户配置
│   ├── settings.yaml               # 全局设置（手续费/滑点/默认数据源）
│   ├── scheduler.yaml              # 定时任务配置
│   └── strategies/                 # 策略参数（YAML，与代码分离）
│       └── ma_cross.yaml
│
├── tests/                          # 测试
│   ├── unit/                       # 单元测试
│   ├── integration/                # 集成测试
│   └── fixtures/                   # 固定测试行情数据
│
├── docs/
│   ├── decisions/                  # ADR 架构决策记录
│   └── superpowers/specs/          # 设计文档
│
└── pyproject.toml                  # 依赖与项目元信息
```

### 3.1 设计要点
1. **`core/` 完全纯逻辑** —— 不 import akshare/tushare/click，只依赖接口和 pandas。核心可被任何触发方式调用，易单测。
2. **插件目录自动发现** —— `indicators/__init__.py` 等用 `importlib` 自动扫描目录所有模块，符合接口的类注册到 `registry`。新增指标文件无需改注册代码。
3. **`config/strategies/` 参数与代码分离** —— 策略参数放 YAML，调整参数不改代码。前端对接时改 YAML 即可调参。
4. **`data/cache/` 本地缓存** —— 缓存到 parquet 既能加速重复回测，也能在网络故障时降级。
5. **`api/` 目录占位** —— 明确告知"未来这里是 FastAPI"，MVP 不实现但留好位置，后续接入零重构。

## 4. 核心接口与数据模型

### 4.1 数据模型 (`core/models.py`)

```python
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

@dataclass
class Signal:
    """策略在某一天产生的信号。"""
    symbol: str
    date: date
    action: str          # "BUY" | "SELL" | "HOLD"
    strength: float = 1.0  # 信号强度 0~1，供仓位管理用
    reason: str = ""       # 人类可读的理由（如"MA5上穿MA20"）

@dataclass
class Trade:
    """回测中实际成交的一笔交易。"""
    symbol: str
    date: date
    action: str          # "BUY" | "SELL"
    price: float         # 实际成交价（考虑滑点）
    quantity: int        # 成交股数（A股需100股整数倍）
    commission: float    # 手续费

@dataclass
class Position:
    """某时刻的持仓快照。"""
    symbol: str
    quantity: int
    avg_cost: float      # 持仓均价
    market_value: float  # 当前市值

@dataclass
class BacktestResult:
    """回测结果，传给 Reporter 输出。"""
    symbol: str
    trades: list[Trade]
    equity_curve: pd.Series    # 净值曲线（按日期）
    metrics: dict              # 收益率/胜率/最大回撤/夏普等
    signals: list[Signal]      # 产生的所有信号
```

### 4.2 插件接口 (`core/interfaces.py`)

```python
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
    name: str           # 指标名，如 "ma"
    params: dict        # 参数，如 {"period": 20}

    @abstractmethod
    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        """输入含 OHLCV 列的 df，返回追加了指标列的 df。"""

class Strategy(ABC):
    """策略插件：声明所需指标，在含指标 DataFrame 上产生 Signal 序列。"""
    name: str
    required_indicators: list[Indicator]  # 编排层据此先算好指标列

    @abstractmethod
    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        """df 是已计算好所需指标的 DataFrame；返回每日信号。"""

class Reporter(ABC):
    """报告插件：消费 BacktestResult，输出到不同媒介。"""
    @abstractmethod
    def render(self, result: BacktestResult) -> None:
        """输出报告（终端/CSV/图表）。"""
```

### 4.3 回测配置与撮合规则

```python
@dataclass
class BacktestConfig:
    """回测撮合配置。"""
    initial_capital: float = 100_000.0     # 初始资金
    fill_price: str = "next_open"          # "next_open" | "close"
    commission_rate: float = 0.0003        # 佣金费率（万三）
    stamp_duty_rate: float = 0.001         # 印花税（仅卖出千一）
    slippage: float = 0.001                # 滑点（千一）
    min_commission: float = 5.0            # 单笔最低佣金 5 元
    lot_size: int = 100                    # A 股一手 100 股
    allow_t_plus_1: bool = True            # T+1：当日买入次日才能卖
    position_sizing: str = "strength"      # "full" | "strength"
    max_positions: int = 1                 # 最大同时持仓股票数
```

**撮合规则**:
- **成交价**: 默认次日开盘价（避免未来函数），可配置为当日收盘价。
- **仓位管理** (`position_sizing="strength"`): 信号 `strength=0.5` → 用当前可用资金 50% 买入 / 卖出当前持仓 50%。
- **股数取整**: 买入股数向下取整到 `lot_size`(100) 的倍数。
- **T+1 约束**: 每笔买入记录"可卖日期 = 买入日 + 1 交易日"，卖出时校验。
- **手续费**: 佣金 = max(amount × commission_rate, min_commission)；卖出额外收 stamp_duty_rate 印花税。
- **滑点**: 买入成交价 = 信号价 × (1+slippage)；卖出成交价 = 信号价 × (1-slippage)。

**关键设计点**:
1. 统一数据格式 `Bar` —— 核心层永远不碰数据源原始 API。
2. 指标输出固定列名 `ind_<name>_<field>` —— 策略和前端都能稳定按列名取值。
3. `Signal.reason` 字段 —— 信号带"为什么买"，利于调试和前端解释。
4. 接口只定义"做什么"，不定义"怎么做"。
5. 回测引擎非插件 —— A 股撮合规则是硬约束，不应被替换；但参数可配置。

## 5. 编排层与数据流

### 5.1 三个核心编排函数 (`core/engine.py`)

```python
def analyze_stock(symbol, strategy_name, start, end,
                  datasource="akshare", config=None) -> BacktestResult:
    """单股分析+回测。最基础入口，被其他所有触发方式复用。"""
    ds = registry.get_datasource(datasource)
    strategy = registry.get_strategy(strategy_name)
    bars = _get_bars_with_cache(ds, symbol, start, end)
    df = _bars_to_dataframe(bars)                  # list[Bar] → DataFrame
    for ind in strategy.required_indicators:       # 先算好策略所需的指标列
        df = ind.compute(df)                       # 逐列追加 ind_<name>_<field>
    signals = strategy.generate_signals(df)        # 策略在含指标 df 上出信号
    result = backtester.run(signals, bars, config) # 逐日撮合
    return result

def analyze_universe(symbols, strategy_name, start, end,
                     datasource="akshare", config=None) -> list[BacktestResult]:
    """批量回测一组股票。"""
    return [analyze_stock(s, strategy_name, start, end, datasource, config)
            for s in symbols]

def run_backtest(strategy_name, symbols="all", start=None, end=None,
                 datasource="akshare", config=None,
                 reporters=("console",)) -> dict:
    """顶层入口：支持单股/多股，渲染报告，返回汇总。"""
    symbols = _resolve_symbols(symbols)
    results = (analyze_stock(...) if len(symbols)==1
               else analyze_universe(symbols, ...))
    for r in results:
        for rep_name in reporters:
            registry.get_reporter(rep_name).render(r)
    return _summarize(results)
```

### 5.2 数据流（单股回测）

```
触发方(CLI/定时/Web)
    │  调用 run_backtest(strategy="ma_cross", symbol="000001", ...)
    ▼
engine.run_backtest()
    1. registry 解析插件名 → DataSource/Strategy/Reporter
    2. _resolve_symbols("000001") → ["000001"]
    3. analyze_stock:
       ① _get_bars_with_cache (cache 命中→读 parquet / 未命中→ds.get_bars→存 parquet)
          → list[Bar]
       ② 编排层把 list[Bar] 转 pd.DataFrame，调 strategy 所需的 Indicator.compute()
          逐列追加指标 → 含指标的 DataFrame
       ③ strategy.generate_signals(df)  (在已算好指标的 df 上出信号)
          → list[Signal]
       ④ backtester.run(signals, bars, config)  (逐日撮合)
          → BacktestResult{trades, equity, metrics}
    4. reporters 链式渲染 result
    5. return 汇总
```

### 5.3 缓存策略

- 缓存按 symbol 粒度存 parquet（列存、压缩、读取快）。
- **增量更新**而非全量重取 —— 只取缓存缺失部分，节省 AkShare 调用。
- 缓存对结果正确性无影响（损坏/清空只是变慢），严格符合"缓存透明"原则。

### 5.4 触发方式复用

| 触发方式 | 调用 | 复用核心 |
|---------|------|---------|
| CLI 手动 | `cli.py` → `run_backtest(...)` | 100% |
| 定时任务 | `scheduler.py` → `run_backtest(...)` | 100% |
| 未来 Web API | `api/main.py` → `run_backtest(...)` | 100% |

三种触发器都只是"参数从哪来"（命令行/cron/HTTP 请求体）的区别，**核心编排函数完全相同**。

## 6. CLI 与定时触发设计

### 6.1 CLI 子命令 (`triggers/cli.py`，click)

```bash
# 单股分析
autotrade analyze --symbol 000001 --strategy ma_cross \
    --start 2024-01-01 --end 2024-12-31 --datasource akshare --reporters console,plot

# 批量回测
autotrade backtest --strategy ma_cross --symbols "000001,600519" \
    --start 2024-01-01 --end 2024-12-31 --reporters console,csv

# 全市场扫描
autotrade scan --strategy ma_cross --universe all --end 2024-12-31 --top 10

# 列出可用插件
autotrade list strategies
autotrade list indicators
autotrade list datasources

# 复看历史结果
autotrade show --result data/results/000001_20240101_20241231.json

# 手动触发一次定时任务
autotrade run-scheduled daily-scan
```

| 子命令 | 场景 | 调用核心函数 |
|--------|------|------------|
| `analyze` | 单股快速验证 | `engine.analyze_stock()` |
| `backtest` | 指定股票池批量 | `engine.run_backtest(symbols=[...])` |
| `scan` | 全市场扫描找标的 | `engine.run_backtest(symbols="all")` |
| `list` | 自省（看有哪些插件） | `registry.list_*()` |
| `show` | 复看历史结果 | 读 `data/results/` |
| `run-scheduled` | 手动触发定时任务 | `scheduler.run_now()` |

### 6.2 定时触发 (`triggers/scheduler.py`，APScheduler)

定时任务本质是"把 CLI 命令参数预先存到配置，到点自动跑"。配置驱动：

```yaml
# config/scheduler.yaml
jobs:
  - name: daily-scan
    cron: "30 15 * * 1-5"        # 周一到周五 15:30
    command:
      type: scan
      strategy: ma_cross
      universe: all
      top: 20
    reporters: [console, csv]
    on_complete:
      - notify: webhook           # MVP 占位

  - name: weekly-review
    cron: "0 18 * * 5"
    command:
      type: backtest
      strategy: macd_divergence
      symbols: "from:last_week_worst_10"
```

调度器把 YAML 配置翻译成对 engine 的调用（纯转译，无逻辑）；`run_now(job_name)` 支持手动立即触发。

### 6.3 关键设计点
1. CLI 和定时任务共用同一份"命令描述" —— 定时 `command` 字段与 CLI 参数一一对应，保证两种触发方式参数语义一致。
2. `list` 子命令是插件化自省入口 —— 加完指标/策略文件，`autotrade list` 即可见。
3. `run-scheduled` 打通手动与定时 —— 定时任务随时可手动触发一次，利于调试。

## 7. 配置、测试、依赖与交付

### 7.1 三层配置（优先级低→高）

```
config/settings.yaml          ← 默认配置（提交 git）
        ↑ 覆盖
环境变量 AUTOTRADE_*           ← 部署/CI 覆盖
        ↑ 覆盖
config/strategies/*.yaml      ← 策略参数（独立管理）
```

```yaml
# config/settings.yaml
datasource:
  default: akshare
  tushare:
    token: ""
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

```yaml
# config/strategies/ma_cross.yaml
strategy: ma_cross
params:
  fast: 5
  slow: 20
  stop_loss: 0.05
  take_profit: 0.15
```

### 7.2 测试体系（测试金字塔）

```
tests/
├── unit/                        # 单元测试（快、隔离、最多）
│   ├── test_models.py
│   ├── test_backtester.py       # 撮合/T+1/手续费逻辑（重点）
│   ├── test_indicators.py
│   ├── test_strategies.py
│   └── test_registry.py
├── integration/                 # 集成测试
│   └── test_engine.py
└── fixtures/                    # 固定测试数据（不依赖网络）
    ├── 000001_daily.csv
    └── expected_signals.json
```

**测试关键点**:
1. `fixtures/` 是回测正确性基石 —— 固定历史行情 + 期望结果，任何撮合/指标改动立刻发现回归。绝不依赖网络。
2. 回测引擎是单测重中之重 —— 每个规则都有用例：
   - 当日买入当日卖出应被拒绝（T+1）
   - 卖出扣千一印花税、买入不扣
   - 买入股数向下取整到 100 倍数
   - 滑点千一时买入价 = 信号价 × 1.001
3. 数据源测试用 mock —— 真实 AkShare 调用标 `@pytest.mark.live`，默认跳过。

### 7.3 依赖清单 (`pyproject.toml`)

```toml
[project]
name = "autotrade"
requires-python = ">=3.10"
dependencies = [
    "pandas>=2.0", "numpy>=1.24", "pyyaml>=6.0",
    "click>=8.1", "apscheduler>=3.10",
    "akshare>=1.10", "pandas-ta>=0.3.14b",
    "pyarrow>=14.0", "rich>=13.0",
]

[project.optional-dependencies]
tushare = ["tushare>=1.2.89"]
plot = ["matplotlib>=3.7"]
api = ["fastapi>=0.104", "uvicorn"]
dev = ["pytest>=7.4", "pytest-cov>=4.1", "pytest-mock>=3.12", "ruff>=0.1"]

[project.scripts]
autotrade = "autotrade.triggers.cli:cli"
autotrade-scheduler = "autotrade.triggers.scheduler:main"
```

**依赖选择说明**:
- `pandas-ta` 而非 `TA-Lib` —— TA-Lib C 底层需编译，Windows 安装麻烦；pandas-ta 纯 Python，`pip install` 即可。
- `rich` —— 终端表格/进度条，全市场扫描必备。
- API 依赖 optional —— MVP 不装 FastAPI，未来 `pip install autotrade[api]`。

## 8. 后续演进路径

- **阶段 2**: FastAPI Web API（`api/` 目录已预留），前端对接
- **阶段 3**: 通知推送（webhook/邮件/微信）
- **阶段 4**: 真实下单接入（券商接口，需严谨风控）
- **阶段 5**: 组合优化、机器学习策略

每个后续阶段都在现有插件化架构上扩展，不推翻重写。
