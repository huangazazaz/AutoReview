# 🧬 BacktestLab Vibecoding 全流程记录

> **Vibecoding**：AI 辅助的极限编程方法论——从模糊想法到可运行系统，全程由自然语言驱动，AI 负责设计、编码、测试、修复。

---

## 目录

1. [什么是 Vibecoding](#1-什么是-vibecoding)
2. [本项目 Vibecoding 全景图](#2-本项目-vibecoding-全景图)
3. [阶段一：架构奠基](#3-阶段一架构奠基-2026-06-19)
4. [阶段二：图表增强](#4-阶段二图表增强-2026-06-20)
5. [阶段三：选股器体系](#5-阶段三选股器体系-2026-06-21)
6. [阶段四：组合引擎 + AI 双翼](#6-阶段四组合引擎--ai-双翼-2026-06-27)
7. [阶段五：AI 策略生成 + 组合整合](#7-阶段五ai-策略生成--组合整合-2026-06-28)
8. [阶段六：体验升级](#8-阶段六体验升级-2026-06-30--07-01)
9. [Vibecoding 方法论总结](#9-vibecoding-方法论总结)
10. [关键数据](#10-关键数据)

---

## 1. 什么是 Vibecoding

Vibecoding 是一种 **AI 原生开发范式**，其核心理念是：

> **开发者用自然语言描述"想要什么"，AI 负责转换、设计、编码、测试全流程。**

与传统编程的关键区别：

| 维度 | 传统开发 | Vibecoding |
|------|---------|------------|
| 输入 | 代码 | 自然语言意图 |
| 设计 | 手动画架构图 | AI 生成设计规约（Spec） |
| 计划 | 手动拆分任务 | AI 生成实现计划（Plan） |
| 编码 | 逐行手写 | AI 整块生成 |
| 测试 | 写完再补 | TDD：先写测试再生成实现 |
| 调试 | 肉眼查错 | AI 系统性诊断修复 |
| 审查 | 人工 Code Review | AI 交叉审查 |
| 文档 | 写完补文档 | 文档与代码同步生成 |

---

## 2. 本项目 Vibecoding 全景图

### 2.1 时间线

```
2026-06-19 ━━━ 2026-06-21 ━━━ 2026-06-27 ━━━ 2026-06-28 ━━━ 2026-06-30 ━━ 07-01
    │              │              │              │              │          │
  架构奠基      图表+选股     组合+AI双翼   AI策略+整合    体验升级    收尾打磨
  28 commits    20 commits    21 commits    18 commits    30 commits  2 commits
```

### 2.2 规模统计

| 指标 | 数值 |
|------|------|
| 总开发天数 | **12 天** |
| 总 Git 提交 | **119 commits** |
| Python 源文件 | **54 个**（`autotrade/`） |
| React/TS 源文件 | **25 个**（`web/src/`） |
| 单元/集成测试 | **25+ 测试文件** |
| 设计规约（Spec） | **10 份** |
| 实现计划（Plan） | **10 份** |
| 架构决策（ADR） | **4 份** |
| YAML 配置文件 | **28 份** |
| 策略实现 | **9 个**（含 1 个 AI 生成的测试策略） |
| 技术指标 | **6 个** |
| 数据源 | **3+1 个** |
| 选股器 | **2 个** |

### 2.3 开发方法论

整个开发过程严格遵循以下 Vibecoding 工作流：

```
用户意图 → [脑暴澄清] → 设计规约(Spec) → 架构决策(ADR) → 实现计划(Plan)
                                                              ↓
                                                          TDD 编码
                                                              ↓
                                                    Review → 修复 → 验证
```

每一步由 AI 独立完成，用户只负责：
1. **表达意图**（"我想做一个 A 股回测系统"）
2. **确认设计**（"这个架构 OK"）
3. **验收结果**（"跑一下看看效果"）

---

## 3. 阶段一：架构奠基（2026-06-19）

> **目标**：从零构建可运行的 MVP  
> **产出**：三层架构框架 + 回测引擎 + 2 个策略 + CLI  
> **提交**：28 commits

### 3.1 用户意图

用户表达了想做 **A 股量化回测系统** 的意图，AI 通过脑暴（Brainstorming）明确了：
- 市场范围：仅 A 股（含 T+1 约束）
- MVP 边界：信号生成 + 回测，不含实盘
- 数据源：AkShare（免费）+ Tushare（可选）
- 架构：自建轻量框架，不做 Backtrader/VB 的"配置员"

### 3.2 设计阶段

AI 产出了：

| 产出 | 文件 | 说明 |
|------|------|------|
| Spec | `docs/superpowers/specs/2026-06-19-autotrade-design.md` | 完整系统设计：分层架构、插件接口、数据流 |
| ADR-0001 | `docs/decisions/0001-scope-and-market.md` | 范围与市场选型决策 |
| ADR-0002 | `docs/decisions/0002-architecture-approach.md` | 架构方案选型（自建 vs Backtrader vs VectorBT） |
| ADR-0003 | `docs/decisions/0003-pluggable-design.md` | 插件化设计哲学 |
| ADR-0004 | `docs/decisions/0004-frontend-readiness.md` | 预留前端对接能力 |
| Plan | `docs/superpowers/plans/2026-06-19-autotrade-implementation.md` | 9 个任务，47 个需创建的文件清单 |

关键架构决策：
- **三层架构**：触发层 → 编排层 → 核心引擎层
- **一切皆插件**：DataSource/Indicator/Strategy/Reporter 均为 ABC 接口
- **回测引擎为唯一非插件**：A 股规则是硬约束，无需扩展
- **配置代码分离**：参数放 YAML，逻辑放 Python

### 3.3 实现阶段

AI 按 Plan 顺序逐步编码，每个任务独立完成：

| 任务 | 关键产出 |
|------|---------|
| 项目初始化 | `pyproject.toml`、包结构、`.gitignore` |
| 数据模型 | `Bar`、`Signal`、`Trade`、`Position`、`BacktestResult` 等 dataclass |
| 插件接口 | 5 个 ABC 基类（DataSource/Indicator/Strategy/Reporter） |
| 插件注册 | `registry.py` — 自动扫描包目录发现插件 |
| 回测引擎 | `backtester.py` — T+1、手续费、印花税、滑点、双向交易 |
| 配置系统 | `config.py` — YAML + 环境变量覆盖 |
| 数据源 | AkShare + Tushare + 本地 Parquet 缓存 |
| 技术指标 | MA、EMA、MACD、RSI、布林带（基于 pandas_ta） |
| 策略 | ma_cross（均线交叉）、macd_divergence（MACD 背离） |
| 报告 | Console（Rich 表格）、CSV、matplotlib 图表 |
| 编排引擎 | `engine.py` — analyze_stock / run_backtest |
| CLI | Click 命令行（analyze/backtest/scan/list） |
| 调度器 | APScheduler cron 定时任务 |
| 前端骨架 | `frontend/` — 原生 JS SPA 框架（router/api/icons） |

### 3.4 TDD 流程示例（回测引擎）

```
1. 先写测试（tests/unit/test_backtester.py）
   ├── test_buy_creates_position()       → 买入后应有持仓
   ├── test_cannot_sell_on_same_day()    → T+1 约束
   ├── test_commission_calculation()     → 佣金计算
   ├── test_stamp_duty_on_sell()         → 卖出印花税
   └── test_lot_size_rounding()          → 100 股整数倍

2. AI 写实现（autotrade/core/backtester.py）
   └── 按 Phase 1(卖出) → Phase 2(买入) 的日循环撮合

3. 跑测试 → 通过 ✅
```

---

## 4. 阶段二：图表增强（2026-06-20）

> **目标**：前端图表展示优化  
> **产出**：权益曲线叠加收盘价 + 买卖标记  
> **提交**：20 commits（含大量调试 commits）

### 4.1 用户意图

用户希望在权益曲线上叠加**股票收盘价走势**和**买卖信号标记**。

### 4.2 设计 → 实现

| 步骤 | 内容 |
|------|------|
| Spec | `docs/superpowers/specs/2026-06-20-stock-price-overlay-chart-design.md` |
| Plan | `docs/superpowers/plans/2026-06-20-stock-price-overlay-chart.md`（1 个任务） |
| 实现 | 后端新增 bars 数据返回 → 前端 ECharts 双 Y 轴叠加收盘价折线 + 散点买卖标记 |

### 4.3 Mini 调试过程

这个阶段展示了 Vibecoding 中常见的 **快速迭代调试** 模式：

```
feat: overlay closing price    → 添加功能
fix: date-keyed lookup        → 修复日期对齐
debug: diagnostic logging     → 添加诊断日志（定位问题）
fix: position: right yAxis    → 修复 Y 轴位置
debug: more trace logging     → 更多日志
fix: non-DatetimeIndex        → 修复日期索引格式
feat: buy/sell markers        → 添加买卖标记
fix: scatter on category axis → 修复散点坐标
fix: label formatter          → 修复标签显示
fix: simple [x,y] format      → 简化坐标格式
chore: remove debug logs      → 清理日志 ✅
```

**Vibecoding 调试特点**：
- AI 自主插入诊断日志定位问题
- 快速试错（平均 5-10 分钟一个 fix commit）
- 问题解决后自动清理调试代码

---

## 5. 阶段三：选股器体系（2026-06-21）

> **目标**：构建选股器（Screener）插件体系 + 两种实战选股器  
> **产出**：Screener ABC + HotMoney + Momentum 选股器  
> **提交**：20 commits

### 5.1 架构扩展

这是 Vibecoding 中**架构演进**的典型案例——在已有插件体系中增加新类型：

```
原有插件体系：                     新增：
DataSource                          Screener ← 第 5 种插件接口
Indicator                            ├── HotMoneyScreener
Strategy                             └── MomentumScreener
Reporter
```

AI 的做法：
1. 在 `interfaces.py` 新增 `Screener` ABC
2. 在 `registry.py` 增加 Screener 扫描逻辑
3. 在 `engine.py` 新增 `run_screener_backtest()` 编排函数
4. 保持向后兼容——旧代码零改动

### 5.2 双选股器实现

| 选股器 | 核心逻辑 | Spec | Plan |
|--------|---------|------|------|
| HotMoney | 趋势预筛选 + 3 信号源（回调/突破/确认）→ 每日最多 3 个标的 | `2026-06-21-hot-money-strategy-design.md` | `2026-06-21-hot-money-strategy.md`（7 任务） |
| Momentum | 7 因子加权评分（动量/回调/量能/均线/…）→ 每日 Top 10 | `2026-06-21-momentum-screener-design.md` | `2026-06-21-momentum-screener.md`（6 任务） |

### 5.3 策略迭代模式

HotMoney 策略经历了 4 个版本的快速迭代（V1→V2→V3→V4），展示了 Vibecoding 的 **实验驱动** 特性：

```
v1: 基础三门前出场
v2: + 趋势预筛选 + 3 信号源 + 激进出场
v3: + 动量范围过滤 + 宽出场 + 入场确认
v4: 回退激进过滤，回到可行的简单配置 ✅
```

每次迭代：用户反馈效果 → AI 调整参数/逻辑 → 重新回测验证。

---

## 6. 阶段四：组合引擎 + AI 双翼（2026-06-27）

> **目标**：构建组合级回测 + 引入 AI 能力  
> **产出**：PortfolioBacktester + AI Filter + Turtle 策略 + 做空支持  
> **提交**：21 commits

这是整个项目中**密度最高**的一天——3 个子项目并行推进。

### 6.1 组合回测引擎

| 步骤 | 文件 | 说明 |
|------|------|------|
| Spec | `2026-06-27-portfolio-backtest-design.md` | 真实账户模拟：多标的同时持仓、资金管理、市场环境感知 |
| Plan | `2026-06-27-portfolio-backtest.md`（12 任务） | 按日循环：选股→买→检查出场→记权益 |
| 实现 | `account.py` | PortfolioPosition、PortfolioTrade、Account（权益跟踪） |
| | `market_regime.py` | 基于选股器候选质量判断市场强弱 → 决定最大持仓数 |
| | `exit_manager.py` | 四门统一出场：移动止损、硬止损、时间止损、信号衰减 |
| | `portfolio_backtester.py` | 主循环编排（600+ 行） |

### 6.2 AI 标的筛选

| 步骤 | 文件 | 说明 |
|------|------|------|
| Spec | `2026-06-27-ai-filter-design.md` | TradingAgents 多智能体 LLM 评估标的 |
| Plan | `2026-06-27-ai-filter.md`（9 任务） | 符号标准化 → LLM Cache → 包装器 → 筛选管道 |
| 实现 | `ai/symbol_utils.py` | A 股代码转 yfinance 符号 |
| | `ai/llm_cache.py` | JSON 持久化 LLM 响应缓存 |
| | `ai/trading_agents_wrapper.py` | 懒加载 + 超时保护 + 错误恢复 |
| | `ai/ai_filter.py` | 管道：候选 → TradingAgents 评估 → 买入/增持才通过 |

### 6.3 海龟交易 + 做空

| 步骤 | 文件 | 说明 |
|------|------|------|
| Spec | `2026-06-27-turtle-strategy-design.md` | 经典 Turtle 系统：双通道突破 + ATR 仓位 |
| Plan | `2026-06-27-turtle-strategy-plan.md`（9 任务） | ATR 指标 → 模型扩展 → 做空支持 → Turtle 策略 |
| 实现 | `indicators/atr.py` | Wilder's smoothing ATR |
| | `models.py` 扩展 | Position/Signal/Trade 增加做空字段 |
| | `backtester.py` 扩展 | SELL_SHORT/BUY_TO_COVER 撮合 + 保证金 |
| | `strategies/turtle.py` | System1(20日) + System2(55日) 双向信号 |

---

## 7. 阶段五：AI 策略生成 + 组合整合（2026-06-28）

> **目标**：AI 生成策略代码 + 策略信号接入组合回测  
> **产出**：DeepSeek 策略生成器 + StrategySignalCache + 组合 UI  
> **提交**：18 commits

### 7.1 AI 策略生成器

```
用户说："当 MA5 上穿 MA20 且放量时买入"
                ↓
    ┌──────────────────────────┐
    │  StrategyGenerator       │
    │  (DeepSeek API)          │
    │                          │
    │  1. 构建 System Prompt   │
    │     (API 文档 + 示例)    │
    │  2. 发送用户提示词       │
    │  3. 解析 JSON 响应       │
    │  4. 生成 .py 策略代码    │
    │  5. 生成 .yaml 参数配置  │
    │  6. 动态导入 + 实例化   │
    │  7. 自动运行回测         │
    │  8. 返回代码 + 回测结果  │
    └──────────────────────────┘
```

**关键技术点**：
- 用 `importlib` 动态加载生成的代码并运行回测
- 策略名冲突时自动添加后缀
- 语法验证 + 错误反馈

**调试迭代**（这一天的 fix commits）：
```
fix: correct indicator class names in AI prompt
fix: bypass strategy registry for AI-generated strategy
fix: use correct indicator column names (ind_ prefix)
fix: pass YAML params when instantiating AI strategy
fix: robust instantiation with param fallback + E2E tests
```

### 7.2 策略驱动组合回测

| 步骤 | 说明 |
|------|------|
| Plan | `2026-06-28-strategy-portfolio-backtest.md`（6 任务） |
| StrategySignalCache | 预计算所有策略信号到 hash set，O(1) 查询 |
| trigger 字段 | PortfolioTrade 新增 trigger 区分 STRATEGY/EXIT_RULE |
| engine 整合 | 组合回测支持策略 BUY/SELL + 出场规则的混合驱动 |

### 7.3 前端页面搭建

新增 React/TS 组合回测页面 + 路由 + API 对接，包含选股器选择、策略参数、资金配置等表单。

---

## 8. 阶段六：体验升级（2026-06-30 ~ 07-01）

> **目标**：AI 对话式交互 + React 重写 + 全面 Bug 修复  
> **产出**：Chat UI + React SPA + 30+ 修复  
> **提交**：30 commits

### 8.1 AI 对话式改造

这是项目中 **最大的 UI 重构**：

| 步骤 | 说明 |
|------|------|
| Spec | `2026-06-30-ai-strategy-chat-redesign.md` — 多轮对话设计 |
| Plan | `2026-06-30-ai-strategy-chat-redesign.md`（11 任务） |
| SessionStore | 线程安全的内存会话管理（2h TTL + 自动清理） |
| Chat 端点 | `/ai/chat` POST + GET + DELETE |
| React 组件拆分 | ChatBubble → ChatInput → ChatMessages → ChatSessionList |
| AIStrategy 重构 | 从单次生成变为多轮对话模式 |

**组件拆分过程**（Vibecoding 典型的渐进式重构）：

```
AIStrategy.tsx (单体 800+ 行)
    ↓ 逐步提取
ChatBubble.tsx     → 单条消息气泡
ChatInput.tsx      → 输入框 + 示例提示
ChatMessages.tsx   → 消息列表 + 空状态 + 自动滚动
ChatSessionList.tsx → 会话列表
    ↓
AIStrategy.tsx (精简到 ~200 行，纯编排)
```

### 8.2 React 前端重写

原有的 `frontend/`（原生 JS）被整体重写为 `web/`（React + TypeScript）：

```
frontend/ (原生 JS)    →    web/ (React + TS)
─────────────────          ─────────────────
index.html                 index.html + main.tsx
js/router.js              React Router 6
js/api.js                 api/client.ts (typed)
js/views/*.js             pages/*.tsx (7 pages)
js/icons.js               components/Sidebar.tsx (inline SVG)
css/style.css             styles/global.css + layout.css
```

保留了`frontend/` 作为降级回退方案（当 React 未构建时 API 服务该目录）。

### 8.3 全面 Bug 修复（30 commits 中的大部分）

6 月 30 日下午至 7 月 1 日的密集修复期：

| 类别 | 修复内容 | Commits |
|------|---------|---------|
| 参数类型 | float→int 错误转换、bool 处理、JSON 数组解析 | 8 commits |
| 策略修复 | macd_divergence、trend_bb_rsi、three_gap_up_buy 参数 | 3 commits |
| SPA 路由 | FastAPI 托管 React SPA 的前端路由回退 | 5 commits |
| 依赖清理 | 替换 pandas_ta 为纯 pandas 实现 | 1 commit |
| 图表修复 | K 线图高度、居中对齐 | 3 commits |
| UI 细节 | react-select 暗色主题、下拉 z-index、loading 状态 | 3 commits |

---

## 9. Vibecoding 方法论总结

### 9.1 核心工作流

```
                     ┌─────────────┐
                     │  用户意图    │
                     │ "我想做..."  │
                     └──────┬──────┘
                            ↓
                     ┌─────────────┐
                     │  脑暴澄清    │ ← Brainstorming Skill
                     │ 范围/边界/   │
                     │ 关键决策     │
                     └──────┬──────┘
                            ↓
              ┌─────────────┴─────────────┐
              ↓                           ↓
       ┌─────────────┐            ┌─────────────┐
       │  设计规约    │            │  架构决策    │
       │  (Spec)     │            │  (ADR)      │
       │ 怎么做      │            │ 为什么      │
       └──────┬──────┘            └─────────────┘
              ↓
       ┌─────────────┐
       │  实现计划    │ ← Writing Plans Skill
       │  (Plan)     │   任务拆分 + 文件清单
       └──────┬──────┘
              ↓
       ┌─────────────┐
       │  TDD 编码   │ ← Test-Driven Development
       │  测试 → 实现 │   Subagent-Driven Development
       └──────┬──────┘
              ↓
       ┌─────────────┐
       │  Review     │ ← Requesting Code Review
       │  修复 → 验证 │   Verification Before Completion
       └──────┬──────┘
              ↓
       ┌─────────────┐
       │  完成 + 合并 │ ← Finishing a Development Branch
       └─────────────┘
```

### 9.2 关键方法论要素

#### 🎯 设计先行（Spec + ADR）

**不做即兴编码**。每个功能模块都先产出：
- **Spec**（设计规约）：描述做什么、怎么做、数据流、API 契约
- **ADR**（架构决策）：记录为什么这么做的权衡

这两个文档在后续 Review 和未来维护中提供完整的"为什么"上下文。

#### 📋 Plan 驱动编码

每个 Spec 对应一个 Plan，Plan 将设计拆解为 **独立可执行的任务**，每个任务有：
- 明确的目标描述
- 文件清单（创建/修改哪些文件）
- 依赖关系（先做什么后做什么）
- 验收标准

Plan 是 AI 执行时的"路线图"，确保不跑偏。

#### 🧪 TDD 不可跳过

**先写测试再写实现**是本项目最严格遵守的规则：

```
真实例子 — PortfolioBacktester 开发：
1. test_account.py            → Account 资金管理测试
2. account.py                 → Account 实现
3. test_portfolio_backtester.py → 组合回测全流程测试（18K）
4. portfolio_backtester.py    → 主引擎实现
5. 跑全部测试 → 通过 ✅
```

好处：
- 测试即文档：测试用例定义了组件的预期行为
- 重构安全网：30+ 测试文件保证后续改动不引入回归
- AI 生成更准确：有测试约束，AI 生成的代码更符合预期

#### 🔌 插件化架构天然适配 Vibecoding

"一切皆插件"的架构设计让增量开发极其高效：
- 添加新功能 = 添加新的插件文件
- 不影响已有代码（开闭原则）
- AI 只需关注新文件的正确性

#### 🤖 子代理并行开发（Subagent-Driven）

对于独立任务，使用多个 AI 子代理并行工作：

```
2026-06-27 的同日并行：
├── 子代理 A：PortfolioBacktester 实现
├── 子代理 B：TradingAgents AI Filter 实现
└── 子代理 C：Turtle 策略 + 做空支持
```

#### 🐛 系统性调试

遇到错误时，遵循 [Systematic Debugging](./.agents/skills/systematic-debugging/SKILL.md) 流程：
1. **复现**：精确复现 bug
2. **诊断**：插入诊断日志定位根因
3. **修复**：最小化改动修复
4. **验证**：跑测试 + 手动验证
5. **清理**：移除诊断代码

#### ✅ 验证再声称完成

严格遵循 [Verification Before Completion](./.agents/skills/verification-before-completion/SKILL.md)：
- 不凭"看起来应该没问题"声称完成
- 必须运行相关测试套件并看到通过
- 必须实际启动服务验证功能

### 9.3 本项目使用的 Superpowers 技能

| 技能 | 用途 | 使用阶段 |
|------|------|---------|
| Brainstorming | 澄清需求、确定边界 | 每个阶段开始前 |
| Writing Plans | 编写实现计划 | Spec 确认后 |
| Test-Driven Development | TDD 开发流程 | 编码阶段 |
| Subagent-Driven Development | 并行任务分发 | 独立任务执行 |
| Systematic Debugging | 系统性调试 | Bug 修复 |
| Requesting Code Review | 代码审查 | 功能完成后 |
| Receiving Code Review | 处理审查反馈 | Review 后 |
| Verification Before Completion | 完成前验证 | 每个阶段结束 |
| Finishing a Development Branch | 分支完成合并 | 阶段收尾 |
| UI Styling | 前端界面设计 | 前端开发 |
| Using Git Worktrees | 隔离工作空间 | 并行开发 |

### 9.4 文档体系的演进

```
docs/
├── decisions/         ← 4 个 ADR（架构决策记录）
│   ├── 0001-scope-and-market.md
│   ├── 0002-architecture-approach.md
│   ├── 0003-pluggable-design.md
│   └── 0004-frontend-readiness.md
│
├── superpowers/
│   ├── specs/         ← 10 个设计规约（功能级设计）
│   │   ├── 2026-06-19-autotrade-design.md
│   │   ├── 2026-06-21-hot-money-strategy-design.md
│   │   ├── ... (7 more)
│   │   └── 2026-06-30-ai-strategy-chat-redesign.md
│   │
│   └── plans/         ← 10 个实现计划（任务级拆分）
│       ├── 2026-06-19-autotrade-implementation.md
│       ├── 2026-06-21-hot-money-strategy.md
│       ├── ... (7 more)
│       └── 2026-06-30-ai-strategy-chat-redesign.md
│
├── api.md             ← API 参考文档
├── backend-startup.md ← 后端启动指南
└── frontend.md        ← 前端架构文档
```

### 9.5 Vibecoding 的优势与挑战

#### ✅ 优势

| 优势 | 本项目体现 |
|------|-----------|
| **极速开发** | 12 天从零到全栈量化系统，传统方式预估需 3-6 个月 |
| **设计完整性** | Spec + ADR 保证了架构的一致性，不会"写着写着就歪了" |
| **测试覆盖率** | TDD 强制约束下，核心模块测试覆盖充分 |
| **文档同步** | Spec/ADR/API 文档与代码同步生成，不会出现"没有文档" |
| **重构勇气** | 测试安全网 + AI 快速重写能力，让大规模重构（如 React 迁移）变得可行 |

#### ⚠️ 挑战

| 挑战 | 应对策略 |
|------|---------|
| AI 幻觉（生成不存在的 API） | TDD 约束 → 测试即真相 |
| 上下文丢失（长对话） | Spec/Plan 文档持久化 → 新会话可快速恢复上下文 |
| 类型不匹配（前端→后端） | TypeScript + Pydantic 双端类型约束 |
| 过度工程（AI 倾向于过度设计） | ADR + MVP 边界约束 → 明确"不做什么" |
| 调试效率（AI 定位 bug 可能绕弯路） | 系统性调试流程 + 诊断日志策略 |

---

## 10. 关键数据

### 10.1 代码量分布

| 层 | 文件数 | 代码行数（估算） |
|----|-------|-----------------|
| Python 核心 | 30+ | ~8,000 行 |
| Python AI 模块 | 6 | ~1,500 行 |
| Python API | 2 | ~1,500 行 |
| Python 测试 | 25+ | ~6,000 行 |
| React/TS 前端 | 25 | ~5,000 行 |
| YAML 配置 | 28 | ~1,000 行 |
| 文档（md） | 25+ | ~50,000 词 |
| **总计** | **140+** | **~22,000 行代码** |

### 10.2 Git 提交热力图

```
日期       commits  主要内容
2026-06-19   28     ████████████████████████████  架构奠基（MVP）
2026-06-20   20     ████████████████████          图表增强
2026-06-21   19     ███████████████████           选股器体系
2026-06-27   21     █████████████████████         组合引擎+AI+海龟
2026-06-28   18     ██████████████████            AI策略生成+组合整合
2026-06-30   30     ██████████████████████████████ 体验升级+Bug修复
2026-07-01    2     ██                             收尾打磨
```

### 10.3 测试覆盖

| 测试类别 | 文件数 | 主要覆盖 |
|---------|--------|---------|
| 单元测试 | 19 | backtester、portfolio、strategies、indicators、registry、config、ai |
| 集成测试 | 6 | engine、portfolio backtest、turtle、ai strategy、ai chat |
| 总计 | 25 | 核心引擎和 AI 模块覆盖充分 |

---

## 后记

BacktestLab 是一个完整的 Vibecoding 实践案例，证明了 **AI 辅助开发** 可以在极短时间内构建出架构良好、功能完整的全栈应用。

这不是"AI 替你写代码"，而是一种新的协作范式：
- **人**负责意图、判断、验收
- **AI** 负责设计、编码、测试、文档

12 天，119 个提交，140+ 个文件，22,000+ 行代码——这是一个人类开发者与 AI 协作者共同创造的成果。

---

<p align="center">
  <sub>🧬 Vibecoding — 让想法以代码的速度生长</sub>
</p>
