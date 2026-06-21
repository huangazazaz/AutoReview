# 游资超短线趋势策略设计

> **日期**:2026-06-21
> **目标**:60% 胜率 + 20% 整体平均收益(选股后实盘口径)
> **视角**:趋势交易游资(超短线,2-7 天持仓)

---

## 1. 背景与目标

### 1.1 现状

现有 4 个策略(`ma_cross` / `trend_bb_rsi` / `trend_ma_breakout` / `golden_filter`)均为**单股择时**思路:给定一只票在其上反复进出。450 只随机股票回测(2025-01-01 → 2026-06-18)结果:

| 策略 | 平均收益 | 正收益比例 | 平均胜率 |
|---|---|---|---|
| ma_cross | +10.3% | ~50% | ~33% |
| trend_bb_rsi | +1.3% | ~35% | 29.4% |
| trend_ma_breakout | +9.8% | ~51% | 33.5% |

所有策略胜率卡在 **~33%**,距离 60% 目标差距大。根因:对**垃圾票和好票一视同仁**,被迫吃所有震荡和假突破;止盈过贪(+30%/+40%)、止损滞后,盈亏不对称。

### 1.2 游资打法的根本区别

游资核心是 **先选股,后择时**。只在"已经表现出爆发力的票"上动手,不参与任何盘整。这与现有"单股择时"是本质不同的范式 —— 需要**横向比较全市场**(4700 只里挑前 N 只),塞不进现有单股 `Strategy.generate_signals(df)` 接口。

### 1.3 目标口径(已确认)

- **胜率 60%**:每只被选中并实际交易的票,其完整交易周期(建仓→清仓)中,盈利周期占比 ≥ 60%。
- **平均收益 20%**:每只被选中票的**累计回测收益**(3 年内所有交易加总)的平均值 ≥ 20%。非单笔收益(单笔游资超短线只能 5-15%)。
- **统计口径**:只统计被 Screener 选中并实际交易的票,4700 只里大部分不参与。

### 1.4 数据约束

缓存仅有 **OHLCV + 成交额**,无龙虎榜/资金流/盘口快照数据。所有"热度/资金"信号必须用**量价关系**代理(放量、量比、形态)。

---

## 2. 整体架构:两层式流程(§1)

### 2.1 架构图

```
┌─────────────────────────────────────────────────────┐
│  第一层: Screener 选股筛网 (新组件)                  │
│  输入: 全市场 4700 只票的 OHLCV + 当日日期           │
│  输出: 当日符合条件的 5-10 只候选票 (横向比较)       │
│  逻辑: 放量起涨 / 首阴反包 形态识别 + 强度排序        │
└──────────────────────┬──────────────────────────────┘
                       │ 候选票
                       ▼
┌─────────────────────────────────────────────────────┐
│  第二层: Strategy 单股择时 (复用现有接口)            │
│  输入: 被选中的某只票的 OHLCV (带指标列)             │
│  输出: BUY/SELL 信号 (进场后 2-7 天的持有与退出)     │
│  逻辑: 信号确认进场 + 快速止盈 + 严格止损           │
└─────────────────────────────────────────────────────┘
```

### 2.2 关键设计决策

1. **新增 `Screener` 插件类**(在 `interfaces.py` 加抽象基类),独立于 `Strategy`。职责:"比较 4700 只票,挑出当日候选"。
2. **`Strategy` 层只管被选中后的进出场**,复用现有 `Backtester` 撮合、T+1、仓位逻辑,**不改动核心引擎**。
3. **新增 `run_screener_backtest()` 编排函数**,先跑 Screener 选出每日候选,再对每只候选票跑 `analyze_stock()`。
4. **全市场扫描**:4700 票 × 725 天 × 8 列 ≈ 2700 万行,parquet + pandas 分块扫描,预计 1-3 分钟。回测只在选中票上精细回测。

### 2.3 为什么这样切分

- **职责单一**:`Screener` 答"今天买谁",`Strategy` 答"买了什么时候卖"。各自独立测试、调参。
- **复用现有撮合**:`Backtester` 的 A 股规则(T+1、100 股、印花税)成熟,不重写。
- **符合框架哲学**:现有项目是"数据→指标→策略→回测→报告"插件链,新增 `Screener` 是自然延伸。
- **可扩展**:以后换选股逻辑(如打板),只换 Screener,Strategy 不动。

---

## 3. 第一层:Screener 选股筛网(§2)

游资只做两种确定性最高的形态,定义为两个独立信号源,任一触发即入选。

### 3.1 信号源 1:放量起涨(Volume Breakout)

所有条件当日(T 日)同时满足:

| 条件 | 阈值 | 含义 |
|---|---|---|
| C1 涨幅 | `close/prev_close - 1 ≥ 5%` | 当日大阳线 |
| C2 量能 | `volume / MA(vol,20) ≥ 2.0` | 放量 2 倍以上,主力进场 |
| C3 突破 | `close > max(high[-20:-1])` | 突破近 20 日最高价,脱离盘整 |
| C4 位置 | `close ≥ MA(close,60) × 0.95` | 60 日线上方附近,排除下降趋势反弹 |
| C5 非一字 | `(high - low) / prev_close ≥ 3%` | 当日有实体,非一字板 |

**设计依据**:
- C1+C2 = 量价齐升,主力进场最直接证据,纯量价可还原。
- C3 = 形态确认,横盘突破经典游资进场点。
- C4 = 趋势过滤,砍掉长期阴跌票。
- C5 = 可成交性过滤,排除一字涨停(回测失真)。

### 3.2 信号源 2:首阴反包(First-Yin Reversal)

| 条件 | 阈值 | 含义 |
|---|---|---|
| C1 前置强势 | 过去 10 日内至少 2 天涨幅 ≥5% | 确认强势股,非冷门票 |
| C2 首阴 | 昨日收阴(`close<open`)且跌幅 ≥2% | 上涨途中第一次回调 |
| C3 当日反包 | `close ≥ 昨日实体顶部` 且涨幅 ≥3% | 大阳吞阴,洗盘结束 |
| C4 量能 | `volume ≥ 昨日成交量` | 反包日不缩量 |
| C5 位置 | `close ≥ MA(close,20)` | 仍在均线上方,趋势未坏 |

**设计依据**:
- 游资"二次上车"确定性买点 —— 强势股首次洗盘结束,通常伴随二次主升。
- C1"前置强势"是关键过滤,排除冷门票的假反包。
- C2 只看**首阴**(第一次回调),第二次以后回调说明趋势已弱,不做。

### 3.3 当日候选池与排序

1. **合并去重**:同一只票当天触发两个信号只计一次。
2. **强度评分**(取前 N 只,默认 8):
   - 信号 1 得分 = `涨幅% × 0.5 + 量比 × 0.3 + 突破力度 × 0.2`
   - 信号 2 得分 = `反包涨幅% × 0.5 + 前置强势度 × 0.3 + 量能 × 0.2`
   - 按得分降序取前 N。

### 3.4 排除项(无论信号多强都不入选)

- ST / *ST 股
- 当日涨停且收一字(`open == high == close`)
- 上市不足 60 个交易日(指标不可靠)
- 当日停牌(`volume == 0`)

### 3.5 进场时机(零未来函数)

- Screener 用 **T 日收盘数据**识别形态 → 产出 **T 日 BUY 信号** → Backtester **T+1 开盘**成交(`fill_price="next_open"`)。
- 完全可成交,不掩盖强势票高开成本(真实游资成本)。

---

## 4. 第二层:Strategy 持仓与退出(§3)

这是把胜率从 33% 推到 60% 的关键。

### 4.1 核心原则

**截断亏损,让利润快跑(但不贪)**。现有策略止盈太贪(+30%/+40%)而止损滞后,盈亏不对称。游资相反:**快进快出,小赚多次**。

### 4.2 三道退出闸门(任一触发即清仓)

#### 闸门 1:移动止盈(Trailing Take-Profit)

| 触发条件 | 动作 |
|---|---|
| 持仓期最高涨幅 ≥ +8% | 启用移动止盈 |
| 此后从最高点回撤 ≥ 3% | 全部卖出 |

吃到起涨段最确定部分,不猜顶。平均盈利票赚 5-15%,不贪到 +30% 被反转吞噬。

#### 闸门 2:时间止损(Time Stop)— 游资灵魂

| 触发条件 | 动作 |
|---|---|
| 持仓满 3 个交易日 且 累计收益 < +3% | 全部卖出 |

选的是**已启动的强势票**,正常 T+1 就应涨。3 天没动静 = 判断错误或主力撤退,不耗在不动 的票上。这是把胜率推高到 60% 的**隐性主力**:把横盘磨人票提前清掉,不让它拖成大亏。

#### 闸门 3:硬止损(Hard Stop)

| 触发条件 | 动作 |
|---|---|
| 累计收益 ≤ -5% | 全部卖出 |

A 股强势票 -5% 通常意味着形态破位。截断在 -5%,单笔最大亏损可控。

### 4.3 三闸门协同流程图

```
进场(T+1 开盘) → 每日检查三闸门:
  
  ┌─ 收益 ≤ -5%? ──────→ 闸门3: 硬止损,记小亏出场
  │
  ├─ 持仓≥3天 且 收益<+3%? → 闸门2: 时间止损,平手/小亏出场
  │                            (腾出资金,不拖累胜率)
  │
  └─ 最高涨幅≥+8%? 
       ├─ 是 → 启用移动止盈
       │       └─ 回撤≥3%? → 闸门1: 锁利出场(赚 5-15%)
       └─ 否 → 继续持有,等下一交易日
```

### 4.4 预期胜率/收益拆解

基于 §3 选出的强势票,预估每 10 笔交易分布:

| 场景 | 占比 | 单笔收益 | 贡献 |
|---|---|---|---|
| 强势票吃到起涨段(移动止盈) | 60% | +8% ~ +15% | 拉高胜率+收益 |
| 3 天没动,时间止损平手 | 20% | -1% ~ +2% | 不拖累 |
| 形态判断错,硬止损 | 20% | -5% | 控制亏损 |

- **胜率** ≈ 60-65%(移动止盈部分 + 部分时间止损小赚)
- **单笔平均** ≈ `0.6×10% + 0.2×0.5% + 0.2×(-5%)` ≈ +5%
- **整体收益**:游资高频(每月 4-8 笔),3 年复利累积,被选中票累计收益平均 ≥ 20% 可达。

### 4.5 阈值调整说明

三闸门阈值(trailing_activate 0.08 / trailing_drawdown 0.03 / time_stop_days 3 / time_stop_min_gain 0.03 / stop_loss 0.05)为初始值,后续根据回测结果调整。

---

## 5. 仓位管理 + 衔接(§4)

### 5.1 回测口径:单股独立满仓 + 汇总

现有 `Backtester` 是单股的(`max_positions=1`)。两个方案:

| 方案 | 评价 |
|---|---|
| 改造 Backtester 支持组合 | 侵入大,重写成熟代码,违背"不动核心"原则 |
| **单股独立满仓回测 + 汇总(采用)** | 零侵入,胜率口径最干净,符合"选股后实盘口径" |

**采用单股独立回测**。每只被选中票 3 年内被选 N 次、做 N 笔交易,统计这些笔的胜率和该票累计收益。组合层面分仓是实盘资金管理,不影响策略信号质量评估。

### 5.2 衔接数据流

```
run_screener_backtest(start, end):
│
├─ 1. 加载全市场 OHLCV (4700 票 × 全部日期,parquet 批量读)
│
├─ 2. Screener.scan(market_df)
│     算 MA/量比/突破列 → 形态识别 → 强度排序
│     输出: selection = { date: [(symbol, score, signal_type), ...] }
│
├─ 3. 反转索引: symbol_to_entry_dates = { symbol: [date1, date2, ...] }
│     (曾被选中的票,去重后通常几百只)
│
├─ 4. 对每只被选中 symbol:
│     strategy = HotMoneyStrategy(allowed_entry_dates=symbol_to_entry_dates[symbol])
│     result = analyze_stock(symbol, "hot_money", start, end, strategy_params=...)
│     复用现有 Backtester 撮合(T+1/100股/印花税)
│
└─ 5. 聚合所有 result → 统计整体胜率、平均收益、收益分布
```

### 5.3 职责切分(关键)

| 组件 | 职责 | 需要的指标 |
|---|---|---|
| **Screener** | 横向选股:算 MA/量比/突破 → 形态识别 → 强度排序 → 输出选中日期 | MA(20), MA(60), 量比, 突破幅度 |
| **Strategy** | 单股择时:**只在 allowed_entry_dates 发 BUY**,其余日子只检查三闸门发 SELL | **无**(三闸门全靠 close + 内部状态) |

**进场逻辑全归 Screener,Strategy 只管出场**。理由:
1. 避免重复计算(进场形态只算一次)。
2. Strategy 极简(`required_indicators = []`),纯状态机,好测好调。
3. 职责纯净,各自独立调参。
4. `allowed_entry_dates` 通过构造参数注入。**注意**:它与 YAML 阈值不同 —— 是 Screener 运行时算出的数据。实现时 `run_screener_backtest` 把它合并进 `strategy_params` dict 传给 `_instantiate_strategy`,后者已支持 `strategy_cls(**params)`(见 `engine.py:253`),`HotMoneyStrategy.__init__` 需显式接收 `allowed_entry_dates: list[date]` 参数。

### 5.4 Strategy generate_signals 伪代码

```python
def generate_signals(self, df):
    for each day:
        if 空仓 and today in self.allowed_entry_dates:
            emit BUY(strength=1.0)        # 满仓进场
            记录 entry_price, entry_day, highest
        if 持仓:
            更新 highest
            # 闸门3 硬止损
            if (close-entry)/entry ≤ -0.05: emit SELL(1.0); 清状态
            # 闸门2 时间止损
            elif 持仓天数≥3 and 收益<+0.03: emit SELL(1.0); 清状态
            # 闸门1 移动止盈
            elif 最高涨幅≥+0.08 and (close-highest)/highest≤-0.03:
                emit SELL(1.0); 清状态
    return signals
```

进场和出场不在同一天冲突(Backtester 先卖后买)。

### 5.5 满仓进出,不分批

超短线持仓仅 2-7 天,分批摊成本无意义,反而稀释起涨段收益。进场 `strength=1.0`,出场 `strength=1.0`,每个交易周期是一次干净的满仓往返。

### 5.6 实盘资金管理建议(非回测)

回测单股满仓为统计纯度。实盘建议(写进文档,不进回测逻辑):
- 总资金分 3-5 份,同时持 3-5 只,每只 20-33%。
- 当日 Screener 选出超过持仓空位的票,按强度评分取舍。

### 5.7 被选中票的回测区间

一只票可能在 2025-03 被选一次、2025-08 又被选一次。对其跑**完整 3 年区间**回测(Strategy 只在被选日子进场,其余空仓):
- 一只票 3 年内产生多笔交易,`_split_cycles` 自然拆成多个周期。
- 胜率按周期算,收益按该票 3 年累计算。
- 保留"没被选中时空仓"的真实资金占用信息。

---

## 6. 文件结构与集成(§5)

### 6.1 新增文件清单

```
autotrade/
├── core/
│   └── interfaces.py          # [改] 新增 Screener 抽象基类
├── screens/                   # [新] 选股筛网插件目录(对标 strategies/)
│   ├── __init__.py            # [新] 注册 hot_money_screener
│   └── hot_money.py           # [新] 游资选股:放量起涨+首阴反包
├── strategies/
│   └── hot_money.py           # [新] 游资择时:三闸门出场状态机
└── core/
    └── engine.py              # [改] 新增 run_screener_backtest()

config/
├── strategies/
│   └── hot_money.yaml         # [新] Strategy 出场参数(三闸门阈值)
└── screens/                   # [新]
    └── hot_money.yaml         # [新] Screener 选股参数(形态阈值+前N)

tests/unit/
└── test_hot_money.py          # [新] 单元测试

docs/superpowers/specs/
└── 2026-06-21-hot-money-strategy-design.md  # 本文档
```

### 6.2 Screener 抽象基类(interfaces.py 新增)

```python
class Screener(ABC):
    """选股筛网插件:横向比较全市场,每日选出候选票。"""
    name: str = "base"
    required_indicators: list[Indicator] = []

    def __init__(self):
        self.required_indicators = []

    @abstractmethod
    def scan(self, market_data: dict[str, pd.DataFrame],
             dates: list[date]) -> dict[date, list[tuple[str, float, str]]]:
        """扫描全市场。

        Args:
            market_data: {symbol: OHLCV DataFrame},每个 df 已算好所需指标。
            dates: 待扫描的交易日列表。
        Returns:
            {date: [(symbol, score, signal_type), ...]} 每日按 score 降序的候选。
        """
```

`scan` 接收**已算好指标的 DataFrame**(编排层先批量算好),Screener 只做形态判断和横向排序。

### 6.3 hot_money.yaml(Strategy 配置)— 三闸门阈值

```yaml
strategy: hot_money
params:
  # 闸门1: 移动止盈
  trailing_activate: 0.08      # 启用移动止盈的最低涨幅
  trailing_drawdown: 0.03      # 启用后从最高点回撤幅度即卖出

  # 闸门2: 时间止损
  time_stop_days: 3            # 最大持仓天数
  time_stop_min_gain: 0.03     # N天内收益低于此值则离场

  # 闸门3: 硬止损
  stop_loss: 0.05
```

### 6.4 hot_money.yaml(Screener 配置)— 形态阈值

```yaml
screen: hot_money_screener
params:
  max_picks: 8                 # 每日最多选 N 只
  ma_period: 20                # 均线/量比周期
  trend_ma_period: 60          # 趋势过滤均线
  breakout_lookback: 20        # 突破回看天数

  # 信号1: 放量起涨
  breakout:
    min_gain: 0.05             # 当日最小涨幅
    volume_ratio: 2.0          # 最小量比
    min_body: 0.03             # 最小实体幅度(过滤一字板)

  # 信号2: 首阴反包
  reversal:
    lookback_strong_days: 10   # 前置强势回看天数
    strong_count: 2            # 该区间内≥5%涨幅天数
    strong_gain: 0.05          # 强势日涨幅阈值
    first_yin_drop: 0.02       # 首阴最小跌幅
    reversal_gain: 0.03        # 反包日最小涨幅

  # 排除项
  exclude:
    min_history_days: 60       # 最少上市天数
```

### 6.5 run_screener_backtest()(engine.py 新增)

```python
def run_screener_backtest(
    screener_name: str,
    strategy_name: str,
    start: date, end: date,
    datasource_name: str = FAILOVER_NAME,
    screener_params: dict | None = None,
    strategy_params: dict | None = None,
    reporter_names: tuple[str, ...] = ("console",),
    stock_names: dict[str, str] | None = None,
) -> dict[str, Any]:
    """游资两段式回测:先选股,再对选中票单股择时回测。"""
    # 1. 全市场加载数据 + 批量算指标
    # 2. screener.scan() → selection {date: [(symbol,score,type)]}
    # 3. 反转索引 symbol_to_entry_dates
    # 4. 对每只选中 symbol: analyze_stock(strategy_params={"allowed_entry_dates": [...]})
    # 5. 聚合统计(胜率/平均收益/分布)
```

### 6.6 Registry 注册

- `screens/__init__.py` 注册 `hot_money_screener` → `HotMoneyScreener`
- `strategies` 注册体系注册 `hot_money` → `HotMoneyStrategy`
- CLI 新增触发入口(后续 plan 阶段细化)

### 6.7 测试策略

`test_hot_money.py` 覆盖:
1. **Screener 单元测试**:构造已知形态合成 OHLCV,断言放量起涨/首阴反包被正确识别、冷门票被排除。
2. **Strategy 单元测试**:构造带 `allowed_entry_dates` 的合成行情,断言三闸门各自触发条件下的 SELL 信号。
3. **无未来函数验证**:Screener 只用 T 日及之前数据,Strategy 进场在 T+1。

### 6.8 不改动的部分(明确边界)

- ❌ 不改 `Backtester`(单股撮合逻辑成熟)
- ❌ 不改现有 4 个策略
- ❌ 不改现有 `run_backtest()` / `analyze_stock()` 签名(新增 `run_screener_backtest`)
- ❌ 不改前端(回测结果走现有 `BacktestResult` / `Reporter`,前端自然兼容)

---

## 7. 验收标准

### 7.1 功能验收

- [ ] `HotMoneyScreener.scan()` 正确识别放量起涨 + 首阴反包形态
- [ ] `HotMoneyStrategy.generate_signals()` 三闸门各自正确触发
- [ ] `run_screener_backtest()` 端到端跑通(全市场选股 → 选中票回测 → 聚合)
- [ ] 无未来函数:Screener T 日识别,T+1 进场
- [ ] 单元测试全部通过

### 7.2 业务验收(目标口径)

在随机抽样股票组上(如现有 450 只随机组)回测:
- [ ] 被选中并实际交易的票,平均胜率 ≥ 60%
- [ ] 被选中票的平均累计收益 ≥ 20%
- [ ] 无未来函数,结果可复现
