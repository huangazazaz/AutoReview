# 🧪 BacktestLab — A股量化回测系统

> **AI 驱动的 A 股量化交易信号生成与回测平台**  
> 一切皆插件 · 三层架构 · AI 策略生成 · 全栈 Web UI  
> 🌐 **在线地址：[http://39.106.56.174:8080](http://39.106.56.174:8080)**

[![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.104+-009688?logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18.3-61DAFB?logo=react)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.5-3178C6?logo=typescript)](https://www.typescriptlang.org/)
[![ECharts](https://img.shields.io/badge/ECharts-5.5-AA344D?logo=apacheecharts)](https://echarts.apache.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](./LICENSE)

---

## 📖 目录

- [项目简介](#项目简介)
- [核心特性](#核心特性)
- [系统架构](#系统架构)
- [技术栈](#技术栈)
- [快速开始](#快速开始)
- [项目结构](#项目结构)
- [API 概览](#api-概览)
- [内置策略](#内置策略)
- [插件系统](#插件系统)
- [AI 能力](#ai-能力)
- [文档索引](#文档索引)

---

## 项目简介

**BacktestLab** 是一个面向 **中国 A 股市场** 的量化交易信号生成与回测系统。从数据获取、技术指标计算、策略信号生成、到回测撮合和结果可视化，提供完整的量化研究流水线。

系统采用 **自建轻量三层架构**（触发层 → 编排层 → 核心引擎层），核心组件全部 **插件化**（DataSource / Indicator / Strategy / Screener / Reporter），通过 Python 包的自动发现机制实现零配置扩展。

### 作品名称由来

> **Backtest**（回测）+ **Lab**（实验室）= 量化回测实验室

这个名字反映了系统的定位：**一个专注于 A 股策略回测研究的实验平台**，你可以在这里自由地设计策略、调整参数、验证想法，就像在实验室里做实验一样。

---

## 核心特性

### 🧩 全面插件化
- **5 类插件接口**：DataSource、Indicator、Strategy、Screener、Reporter
- 添加新策略只需在对应目录放入 Python 文件，系统自动发现
- 回测引擎为唯一不可插件的硬约束（A 股规则固定）

### 📊 完整回测引擎
- **T+1 制度**（买入当日不可卖出）
- **真实成本模拟**：佣金 0.03%、印花税 0.1%（卖出）、滑点 0.1%
- **灵活仓位**：按信号强度分批（strength）或全仓（full）
- **双向交易**：支持做多 + 融券做空
- **成交价可配**：次日开盘价（避免前视偏差）/ 当日收盘价

### 🎯 组合级回测
- 多标的同步持仓模拟（最多 3 个同时持仓）
- **市场环境感知**：根据筛选器候选质量动态调整持仓数
- **四维出场规则**：移动止损、硬止损、时间止损、信号衰减
- 实盘级资金管理：现金缓冲、每日买卖计划

### 🤖 AI 驱动
- **自然语言生成策略**：用中文描述交易想法，AI（DeepSeek）自动生成完整 Python 策略代码 + YAML 配置
- **多轮对话优化**：通过聊天界面与 AI 反复打磨策略参数
- **即时回测验证**：AI 生成的策略自动运行回测，立刻看到效果
- **AI 筛选增强**：TradingAgents 多智能体 LLM 辅助筛选标的

### 🎨 全栈 Web UI
- **React + TypeScript SPA**：现代化前端架构，组件化设计
- **ECharts 交互图表**：K 线图、权益曲线、回撤图、排行榜
- **暗色金融主题**：CSS 变量驱动的设计系统
- **响应式布局**：桌面/平板/手机自适应
- **7 个功能页面**：仪表盘、单股分析、批量回测、组合回测、AI 策略、K 线查询、分组管理

### 🔧 多触发方式
| 触发方式 | 入口 | 适用场景 |
|---------|------|---------|
| Web API | `start.bat` / `start.sh` | 日常交互使用 |
| CLI | `cli.bat` / `python -m autotrade.triggers.cli` | 快速命令行分析 |
| 定时调度 | APScheduler | 收盘后自动扫描 |

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│  触发层 (Triggers)                                           │
│  CLI (Click)  │  定时任务 (APScheduler)  │  FastAPI Web API  │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  编排层 (Orchestration)  — 纯组装调度，不含业务逻辑             │
│  analyze_stock()  │  run_backtest()  │  run_portfolio_backtest()│
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  核心引擎层 (Core)                                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐  │
│  │ DataSource│→ │Indicator │→ │Strategy  │→ │Backtester  │  │
│  │ (插件)    │  │ (插件)    │  │ (插件)    │  │ (内置)      │  │
│  └──────────┘  └──────────┘  └──────────┘  └─────┬──────┘  │
│                                                   │         │
│  ┌──────────┐  ┌──────────┐              ┌───────▼───────┐  │
│  │ Screener │  │ ExitMgr  │              │   Reporter    │  │
│  │ (插件)    │  │ (内置)    │              │   (插件)       │  │
│  └──────────┘  └──────────┘              └───────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 设计原则

| 原则 | 说明 |
|------|------|
| **一切皆插件** | DataSource / Indicator / Strategy / Screener / Reporter 均为 ABC 接口，通过文件系统自动发现 |
| **触发-核心解耦** | CLI、调度器、Web API 都是平等的"调用方"，调用同一套核心 API |
| **配置-代码分离** | 所有参数存于 YAML 文件，前端和 CLI 均可参数调优，无需改代码 |
| **数据源主备降级** | 本地缓存 → Tushare（主力）→ AKShare（备用），自动 fallover |

---

## 技术栈

### 后端

| 组件 | 技术 | 说明 |
|------|------|------|
| 语言 | Python 3.10+ | 类型注解、dataclasses |
| Web 框架 | FastAPI + Uvicorn | 自动生成 Swagger 文档 |
| 数据处理 | pandas + numpy | 向量化计算 |
| 数据存储 | PyArrow / Parquet | 本地 K 线缓存 |
| CLI | Click | 命令行参数解析 |
| 定时任务 | APScheduler | Cron 表达式调度 |
| 终端美化 | Rich | 彩色表格输出 |
| 图表 | matplotlib | 权益曲线/回撤图 |
| 配置 | PyYAML | 策略参数、系统设置 |

### 前端

| 组件 | 技术 | 说明 |
|------|------|------|
| 框架 | React 18 + TypeScript | 类型安全的 SPA |
| 构建 | Vite 5 | 极速 HMR |
| 路由 | React Router 6 | 客户端路由 |
| 图表 | ECharts 5.5 | K 线/权益/回撤/排行 |
| UI 组件 | react-select | 可搜索多选下拉框 |
| 样式 | CSS Custom Properties | 暗色金融主题 |

### AI

| 组件 | 技术 | 说明 |
|------|------|------|
| 策略生成 | DeepSeek API (OpenAI SDK) | 自然语言→Python 策略代码 |
| 标的筛选 | TradingAgents | 多智能体 LLM 分析 |

### 数据源

| 数据源 | 类型 | 说明 |
|------|------|------|
| AKShare | 免费公开 | 东方财富数据，无需 token |
| Tushare Pro | 专业付费 | 高质量数据，需注册 token |
| 本地 Parquet | 缓存 | 从网络源自动缓存，加速重复查询 |

---

## 快速开始

### 环境要求

- **Python** ≥ 3.10
- **Node.js** ≥ 18（前端开发需要）
- **网络**：需访问 A 股公开数据源

### 1. 克隆与安装

```bash
git clone https://github.com/huangazazaz/BacktestLab.git
cd BacktestLab

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装 Python 依赖
pip install -e ".[api,plot]"
```

### 2. 下载数据

```bash
# 下载全市场 A 股近 3 年日线数据（约 15-30 分钟）
python scripts/download_stocks.py
```

### 3. 启动服务

**Windows**：双击 `start.bat`

**macOS / Linux**：
```bash
./start.sh
```

启动后访问：
- 🖥️ **Web 界面**：http://localhost:8080
- 📚 **API 文档**：http://localhost:8080/docs
- ❤️ **健康检查**：http://localhost:8080/health

> 🌐 **已部署**：在线使用可直接访问 **[http://39.106.56.174:8080](http://39.106.56.174:8080)**

### 4. 前端开发（可选）

```bash
cd web
npm install
npm run dev        # 开发服务器 → http://localhost:5173
npm run build      # 构建 → web/dist/（API 自动服务）
```

### 5. CLI 快速使用

```bash
# 单股回测
cli.bat analyze --symbol 600522 --strategy ma_cross --period 1y

# 批量回测
cli.bat backtest --strategy ma_cross --group 自选 --period 6m

# 查看可用策略
cli.bat list strategies
```

---

## 项目结构

```
AutoReview/
├── autotrade/                    # 🐍 Python 主包
│   ├── api/                      #   FastAPI 服务器
│   │   ├── server.py             #     路由 + 请求模型（1200+ 行）
│   │   └── __main__.py           #     入口：python -m autotrade.api
│   ├── core/                     #   核心引擎层
│   │   ├── engine.py             #     编排器（analyze_stock / run_backtest）
│   │   ├── backtester.py         #     单股回测撮合引擎
│   │   ├── portfolio_backtester.py #  组合级回测引擎
│   │   ├── account.py            #     资金账户管理
│   │   ├── exit_manager.py       #     出场规则（移动止损/硬止损/时间/信号衰减）
│   │   ├── market_regime.py      #     市场环境感知
│   │   ├── strategy_signal_cache.py # 策略信号预计算缓存
│   │   ├── interfaces.py         #     插件 ABC 接口
│   │   ├── models.py             #     数据模型（Bar/Signal/Trade/Position）
│   │   ├── config.py             #     配置加载（YAML + 环境变量覆盖）
│   │   └── datasource_factory.py #     数据源主备降级链
│   ├── dataSources/              #   数据源插件（3+1 个）
│   ├── indicators/               #   技术指标插件（6 个）
│   ├── strategies/               #   策略插件（9 个）
│   ├── screens/                  #   选股器插件（2 个）
│   ├── reporters/                #   报告输出插件（3 个）
│   ├── ai/                       #   AI 模块
│   │   ├── strategy_generator.py #     DeepSeek 策略代码生成
│   │   ├── ai_filter.py          #     TradingAgents 标的筛选
│   │   ├── session_store.py      #     聊天会话管理
│   │   └── llm_cache.py          #     LLM 响应缓存
│   ├── triggers/                 #   触发入口
│   │   ├── cli.py                #     Click CLI
│   │   └── scheduler.py          #     APScheduler 定时任务
│   └── registry.py               #   插件自动发现与注册
├── web/                          # ⚛️ React SPA 前端
│   ├── src/
│   │   ├── pages/                #     7 个页面组件
│   │   ├── components/           #     共享组件（Sidebar/Layout/Chat/…）
│   │   ├── api/                  #     API 客户端
│   │   ├── hooks/                #     自定义 Hooks（useECharts/useApp）
│   │   └── types/                #     TypeScript 类型定义
│   ├── vite.config.ts
│   └── package.json
├── frontend/                     # 📄 静态前端（回退方案）
│   ├── index.html
│   ├── css/style.css             #     2112 行 FinTech 暗色主题
│   └── js/                       #     原生 JS 模块（router/api/views）
├── config/                       # ⚙️ 配置文件
│   ├── settings.yaml             #     全局系统设置
│   ├── scheduler.yaml            #     定时任务定义
│   ├── strategies/               #     策略参数（8 个 YAML）
│   ├── screens/                  #     选股器参数（2 个 YAML）
│   ├── groups/                   #     股票分组（16 个 YAML）
│   └── backtest/                 #     回测配置
├── docs/                         # 📚 文档
│   ├── api.md                    #     REST API 完整参考
│   ├── backend-startup.md        #     后端启动详细指南
│   ├── frontend.md               #     前端架构说明
│   ├── decisions/                #     架构决策记录（4 个 ADR）
│   └── superpowers/              #     设计规约与实现计划
│       ├── plans/                #         10 个实现计划
│       └── specs/                #         10 个设计规约
├── tests/                        # 🧪 测试（45+ 文件）
│   ├── unit/                     #     单元测试（19 文件）
│   ├── integration/              #     集成测试（6 文件）
│   └── fixtures/                 #     测试数据
├── data/                         # 💾 运行时数据
│   ├── daily/                    #     日线 Parquet 缓存
│   ├── cache/                    #     元数据缓存
│   ├── results/                  #     回测结果输出
│   └── logs/                     #     运行日志
├── scripts/                      # 🔧 工具脚本
│   ├── download_stocks.py        #     全市场数据下载
│   ├── export_stock_list.py      #     股票列表导出
│   ├── backtest_hot_money.py     #     热门资金策略验证
│   └── run_portfolio_backtest.py #     组合回测启动
├── start.bat / start.sh          # 🚀 一键启动脚本
├── cli.bat                       # 💻 CLI 快捷入口
└── README.md                     # 📖 本文件
```

---

## API 概览

### REST API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/health` | 健康检查 |
| `POST` | `/analyze` | 单股回测分析（含完整交易记录和权益曲线） |
| `POST` | `/backtest` | 批量回测（多股票/分组，返回排行榜） |
| `POST` | `/portfolio-backtest` | 组合级回测（选股器+策略+资金管理） |
| `POST` | `/bars` | 日线 OHLCV 数据查询 |
| `GET` | `/strategies` | 列出所有策略及其参数 schema |
| `GET` | `/datasources` | 列出可用数据源 |
| `GET` | `/cache/stocks` | 本地缓存股票列表（分页） |
| `GET/POST/PUT/DELETE` | `/groups[/{id}]` | 股票分组 CRUD |
| `POST` | `/ai/generate-strategy` | AI 生成策略+自动回测 |
| `POST` | `/ai/chat` | AI 多轮对话优化策略 |
| `GET/DELETE` | `/ai/chat/{id}` | 聊天会话管理 |
| `POST` | `/strategies/save` | 保存 AI 生成的策略到文件 |
| `DELETE` | `/strategies/{name}` | 删除策略 |

> 📚 完整 API 文档：启动服务后访问 `http://localhost:8080/docs`（Swagger UI）
> 📄 详见：[docs/api.md](./docs/api.md)

---

## 内置策略

| 策略名 | 类型 | 核心逻辑 |
|--------|------|---------|
| `ma_cross` | 均线交叉 | MA 金叉买入，分批金字塔加仓，阶梯止盈，回撤规则 |
| `macd_divergence` | MACD 背离 | 检测 MACD 与价格的顶底背离信号 |
| `ma_cross_macd` | 均线+MACD | MA 金叉 + MACD 柱状图>0 动量确认 |
| `golden_filter` | 多重过滤 | MA 交叉 + 放量 + RSI<70 + 收盘>布林中轨 |
| `turtle` | 海龟交易 | 双通道突破（20/55 日），ATR 波动率仓位，N 止损 |
| `trend_bb_rsi` | 趋势共振 | 布林趋势 + RSI 区域 + 量能确认 + MACD 动量，四维共振 |
| `trend_ma_breakout` | 趋势突破 | MA 金叉 + RSI 甜点区（30-60）过滤 |
| `hot_money` | 游资打板 | 筛选器驱动进场，四门出场（移动止损/时间/硬止损/趋势破位） |
| `three_gap_up_buy` | 三跳空 | 连续 3 日跳空高开的强势追涨模式 |

---

## 插件系统

### 如何添加自定义策略

1. 在 `autotrade/strategies/` 下新建 `.py` 文件
2. 继承 `autotrade.core.interfaces.Strategy` 基类
3. 设置 `name` 和 `required_indicators` 属性
4. 实现 `generate_signals(self, df) -> list[Signal]` 方法
5. 在 `config/strategies/` 下创建对应的 `.yaml` 参数文件
6. **重启服务器** — 系统自动发现新策略 ✅

```python
# autotrade/strategies/my_strategy.py
from ..core.interfaces import Strategy, Signal

class MyStrategy(Strategy):
    name = "my_strategy"
    required_indicators = ["MA(20)", "RSI(14)"]

    def generate_signals(self, df):
        signals = []
        for i in range(1, len(df)):
            if df['ind_ma_20'].iloc[i] > df['ind_ma_20'].iloc[i-1]:
                signals.append(Signal(
                    date=str(df.index[i]),
                    action="BUY",
                    strength=0.5,
                    reason="MA20 拐头向上"
                ))
        return signals
```

### 插件接口一览

| 接口 | 核心方法 | 自动发现目录 |
|------|---------|-------------|
| `DataSource` | `get_bars(symbol, start, end)` | `autotrade/dataSources/` |
| `Indicator` | `compute(df) -> DataFrame` | `autotrade/indicators/` |
| `Strategy` | `generate_signals(df) -> list[Signal]` | `autotrade/strategies/` |
| `Screener` | `scan(market_data, dates) -> dict` | `autotrade/screens/` |
| `Reporter` | `render(result: BacktestResult)` | `autotrade/reporters/` |

---

## AI 能力

### 自然语言生成策略

在 Web 界面点击「AI 策略」，用自然语言描述你的交易想法，AI 会：

1. 📝 生成完整的 Python 策略类代码
2. ⚙️ 生成对应的 YAML 参数配置
3. 🧪 自动运行回测验证
4. 📊 即时展示回测结果

**示例提示词**：
> "当 5 日均线上穿 20 日均线，且成交量大于前 5 日均量的 1.5 倍时买入，跌破 10 日均线时卖出"

### 多轮对话打磨

通过聊天界面与 AI 反复优化策略，例如：
- "把止损从 5% 改成 8%"
- "增加一个 RSI < 30 的买入条件"
- "回测一下最近一年的效果"

### AI 标的筛选（组合回测增强）

组合回测中可启用 AI 二次筛选：TradingAgents 多智能体基于基本面、技术面、情绪面、新闻面综合评估每个候选标的，只保留"买入"评级的股票进入回测。

---

## 文档索引

| 文档 | 说明 |
|------|------|
| [README.md](./README.md) | 项目总览（本文件） |
| [USER_GUIDE.md](./USER_GUIDE.md) | 用户使用手册 |
| [VIBECODING.md](./VIBECODING.md) | Vibecoding 开发全流程记录 |
| [docs/api.md](./docs/api.md) | REST API 完整参考 |
| [docs/backend-startup.md](./docs/backend-startup.md) | 后端启动与配置指南 |
| [docs/frontend.md](./docs/frontend.md) | 前端架构文档 |
| [docs/decisions/](./docs/decisions/) | 架构决策记录（ADR） |
| [docs/superpowers/specs/](./docs/superpowers/specs/) | 设计规约文档 |
| [docs/superpowers/plans/](./docs/superpowers/plans/) | 实现计划文档 |

---

## 路线图

- [x] MVP：信号生成 + 回测 + CLI + 定时任务（2026-06-19）
- [x] 前端 SPA：仪表盘、单股分析、批量回测、K 线查询、分组管理
- [x] 图表增强：权益曲线叠加 K 线、回撤图、排行榜
- [x] 游资策略：HotMoney 选股器 + 四门出场逻辑
- [x] 动量选股器：7 因子加权评分
- [x] 海龟交易系统：双通道突破 + ATR 波动率仓位
- [x] 组合回测：多标的同步持仓 + 资金管理
- [x] AI 策略生成：DeepSeek 自然语言 → Python 代码
- [x] React SPA 重写：TypeScript + React Router + ECharts
- [x] AI 多轮对话：策略聊天优化界面
- [ ] 分钟级数据支持
- [ ] 更多策略模板（网格、套利）
- [ ] 策略参数优化（遗传算法/网格搜索）
- [ ] Docker 一键部署
- [ ] 实盘信号推送（企业微信/钉钉）

---

<p align="center">
  <sub>Built with ❤️ using Vibecoding — 2026.06</sub>
</p>
