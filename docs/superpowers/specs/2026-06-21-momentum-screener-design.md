# MomentumScreener 设计文档

> 日期：2026-06-21  
> 状态：已确认  
> 分支：dev/autotrade-mvp

---

## 1. 目标

新建一个 Screener 插件 `momentum_screener`，从全市场挑选「最近一个月走势好 + 当前可入场」的股票。既识别强势追入机会，也识别回调买入机会。

纯技术面因子（量价数据），与现有 `HotMoneyScreener` 并存，用户可按需选择。

---

## 2. 架构

### 2.1 新增文件

```
autotrade/screens/momentum.py          # MomentumScreener 主模块
config/screens/momentum_screener.yaml  # 因子权重与参数配置
tests/unit/test_screener_momentum.py   # 单元测试
```

### 2.2 类设计

```
MomentumScreener(Screener)
├── name = "momentum_screener"
│   # 注：引擎不对 Screener 预计算 required_indicators，
│   #   所有指标通过 pandas_ta 在 _prefilter / _score 中内联计算
│
├── __init__(**params)              # 从 YAML 加载所有权重和阈值
│
├── scan(market_data, dates)        # 主入口，两阶段框架
│   ├── _prefilter(df, date)        # 阶段1: 快速剔除不合格股票
│   └── _score(df, date)            # 阶段2: 多因子加权打分
│       ├── _calc_momentum_1m(df)   # 近1月涨跌幅 (20交易日)
│       ├── _calc_momentum_5d(df)   # 近5日涨跌幅
│       ├── _calc_vol_ratio(df)     # 量比: 当日量 / 20日均量
│       ├── _calc_ma_score(df)      # 均线多头排列程度
│       ├── _calc_pullback(df)      # 距MA20偏离度
│       ├── _calc_atr_ratio(df)     # 波动率: ATR(20) / 收盘价
│       └── _calc_consistency(df)   # 近20日阳线占比
│
└── _classify_signal(scores)        # 根据因子分打标签
```

### 2.3 与 HotMoneyScreener 的区别

| 维度 | HotMoneyScreener | MomentumScreener |
|------|-----------------|-----------------|
| 选股逻辑 | 预筛选 → 独立信号打分 | 预筛选 → 因子加权总分 |
| 信号类型 | 3种信号 (pullback/breakout/strength) | 1个综合分 + 标签 |
| 输出 | `[(symbol, score, signal_type)]` | `[(symbol, total_score, tag)]` |
| 因子数 | ~5个（内联计算） | 7个（模块化方法） |
| 时间窗口 | 60日动量为主 | 聚焦20~30个交易日 |

---

## 3. 因子设计

### 3.1 预筛选（快速剔除）

| 条件 | 阈值 | 目的 |
|------|------|------|
| 排除 ST/*ST | 硬编码，读取 `data/a_stock_list.csv` | 防雷 |
| 近20日日均成交额 > `min_amount` | 默认 5000万 | 剔除流动性差的僵尸股 |
| MA20 > MA60 | 硬编码，通过 pandas_ta 内联计算 MA(20) 和 MA(60) | 中期趋势必须向上 |
| 近1月涨跌幅在区间内 | `mom_1m_min` ~ `mom_1m_max`，默认 3%~40% | 有趋势但不过热 |

### 3.2 七大打分因子

每个因子输出 0~1 标准化分，最后加权求和。总分范围 0~1。

| # | 因子 | 计算方式 | 打分逻辑 | 默认权重 |
|---|------|----------|----------|---------|
| 1 | **动量强度** `mom_1m` | `close / close[-20] - 1` | S曲线：5%~25% 得高分，<3% 和 >40% 衰减 | 20% |
| 2 | **短期回调** `mom_5d` | `close / close[-5] - 1` | 反向：-5%~0% 得高分，< -8% 降分 | 15% |
| 3 | **量能确认** `vol_ratio` | `volume / volume_ma_20` | 1.0~2.0 得高分（温和放量），<0.6 和 >3 降分 | 15% |
| 4 | **均线多头** `ma_score` | MA5>MA10>MA20>MA60 满足条数 | 4条=1.0, 3条=0.7, 2条=0.4, ≤1=0.1 | 15% |
| 5 | **回调到位** `pullback` | `(close - ma_20) / ma_20` | 距MA20在 -2%~+5% 得高分 | 15% |
| 6 | **波动适中** `atr_ratio` | `ATR(20) / close` | 2%~5% 得高分 | 10% |
| 7 | **稳步上涨** `consistency` | 近20日阳线占比 | 55%~75% 得高分 | 10% |

> 每个因子使用分段线性或 S 曲线映射到 0~1。S 曲线用 `1 / (1 + exp(-k * (x - center)))` 形式。

### 3.3 信号标签

总分 ≥ 阈值（默认 0.65）的股票入选，按因子特征打标签：

- `"momentum_strong"` — 总分高 + mom_1m 高 + mom_5d 为正（强势追入型）
- `"momentum_pullback"` — 总分高 + mom_1m 中等 + mom_5d 为负（回调买入型）
- `"momentum_steady"` — 总分高 + consistency 突出（稳步上涨型）

---

## 4. 数据流

### 4.1 扫描流程

```
scan(market_data: dict[str, DataFrame], dates: list[date])
│
├─ for each date in dates:
│   ├─ 初始化当日候选池 = []
│   ├─ for each (symbol, df) in market_data:
│   │   ├─ df_slice = df[df.index <= date].tail(60)    # 截取到当日的数据
│   │   ├─ _prefilter(df_slice, date)                   # 通过则继续
│   │   ├─ total_score, tag = _score(df_slice, date)    # 打分
│   │   └─ if total_score >= score_threshold:
│   │       候选池.append((symbol, total_score, tag))
│   │
│   ├─ 候选池按 total_score 降序排列
│   └─ result[date] = 候选池[:top_n_per_day]
│
└─ return result
```

### 4.2 与策略配对

直接复用 `HotMoneyStrategy`（它接受 `allowed_entry_dates` 注入入口日期）：

```python
engine.run_screener_backtest(
    screener_name="momentum_screener",
    strategy_name="hot_money",
    start_date=date(2025, 1, 1),
    end_date=date(2025, 6, 1),
)
```

不需要为它写独立策略。

### 4.3 配置加载

引擎已有 `_load_screener_params()` 方法，自动读取 `config/screens/{screener_name}.yaml` 中 `params:` 节，传给 `__init__`。无需修改引擎代码。

---

## 5. YAML 配置

```yaml
# config/screens/momentum_screener.yaml
params:
  # 预筛选
  min_amount: 50000000
  mom_1m_min: 0.03
  mom_1m_max: 0.40

  # 因子权重 (总和应为1.0)
  weight_mom_1m: 0.20
  weight_mom_5d: 0.15
  weight_vol_ratio: 0.15
  weight_ma_score: 0.15
  weight_pullback: 0.15
  weight_atr_ratio: 0.10
  weight_consistency: 0.10

  # 入选控制
  score_threshold: 0.65
  top_n_per_day: 10
```

---

## 6. 测试计划

### 6.1 单元测试

`tests/unit/test_screener_momentum.py`：

| 测试用例 | 覆盖内容 |
|----------|---------|
| `test_prefilter_st` | ST 股票被正确剔除 |
| `test_prefilter_amount` | 低成交额股票被剔除 |
| `test_prefilter_trend` | MA20 <= MA60 的股票被剔除 |
| `test_prefilter_momentum_range` | 涨跌幅不在区间内被剔除 |
| `test_score_range` | 总分始终在 0~1 之间 |
| `test_score_higher_for_good_setup` | 典型好结构的股票得分高于差结构 |
| `test_momentum_1m_scoring` | 动量因子打分正确性 |
| `test_momentum_5d_scoring` | 回调因子打分正确性（反向） |
| `test_vol_ratio_scoring` | 量能因子打分正确性 |
| `test_ma_score_scoring` | 均线排列打分正确性 |
| `test_pullback_scoring` | 偏离度打分正确性 |
| `test_atr_ratio_scoring` | 波动率打分正确性 |
| `test_consistency_scoring` | 阳线占比打分正确性 |
| `test_signal_tag_strong` | 强势标签正确分配 |
| `test_signal_tag_pullback` | 回调标签正确分配 |
| `test_signal_tag_steady` | 稳步上涨标签正确分配 |
| `test_top_n_enforced` | top_n_per_day 限制生效 |
| `test_empty_market_data` | 空数据不报错，返回空结果 |
| `test_insufficient_history` | 数据不足60天时正常降级处理 |

### 6.2 集成测试

- 用真实股票数据跑一次完整 `scan()`，验证不报错、有合理输出
- 用 `run_screener_backtest` 端到端跑一次，验证与策略配对正常

---

## 7. 边界情况与降级处理

| 场景 | 处理方式 |
|------|---------|
| 股票上市不足20天 | 跳过该股票（预筛选不通过） |
| 上市不足60天 | MA60 取可用数据，均线排列因子降权 |
| 某指标因数据不足无法计算 | 该因子返回 0 分（不影响其他因子） |
| 当日停牌（成交量为0） | 跳过 |
| 全市场无股票通过预筛选 | 返回空列表，不报错 |

---

## 8. 不做的

- 不写独立的 MomentumStrategy（复用 HotMoneyStrategy）
- 不引入基本面因子（纯量价）
- 不修改引擎代码（完全用现有接口）
- 不做日频因子（每日一根Bar即可）
- 不引入形态识别（复杂度超出当前范围）

---

## 9. 自审清单

- [x] 无 TBD / TODO 占位符
- [x] 架构与功能描述一致
- [x] 范围聚焦，单模块交付
- [x] 因子定义明确、可量化
- [x] 边界情况有明确处理
- [x] 测试计划与需求对齐
