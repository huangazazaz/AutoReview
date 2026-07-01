# 📘 BacktestLab 用户使用手册

> 从零开始掌握 BacktestLab：安装、配置、回测、AI 策略生成  
> 🌐 **在线使用：[http://39.106.56.174:8080](http://39.106.56.174:8080)**

---

## 目录

1. [快速入门](#1-快速入门)
2. [Web 界面详解](#2-web-界面详解)
3. [CLI 命令行使用](#3-cli-命令行使用)
4. [策略配置与调参](#4-策略配置与调参)
5. [股票分组管理](#5-股票分组管理)
6. [AI 策略生成](#6-ai-策略生成)
7. [组合回测](#7-组合回测)
8. [数据管理](#8-数据管理)
9. [定时任务](#9-定时任务)
10. [常见问题](#10-常见问题)

---

## 1. 快速入门

### 1.1 安装与启动

#### 第一步：环境准备

确保已安装：
- **Python** ≥ 3.10（[下载](https://www.python.org/downloads/)）
- **Node.js** ≥ 18（可选，仅前端开发需要）

#### 第二步：安装依赖

```bash
# 进入项目目录
cd BacktestLab

# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# 安装依赖
pip install -e ".[api,plot]"
```

#### 第三步：下载数据

首次使用需要下载 A 股历史日线数据：

```bash
python scripts/download_stocks.py
```

> ⏱️ 下载全市场近 3 年数据约需 **15-30 分钟**  
> 💡 数据保存在 `data/daily/` 目录，后续回测无需重新下载

#### 第四步：启动服务

**Windows**：双击 `start.bat`

**macOS/Linux**：
```bash
./start.sh
```

**手动启动**：
```bash
python -m autotrade.api
```

> ✅ 看到 `Uvicorn running on http://0.0.0.0:8080` 即启动成功

#### 第五步：打开界面

浏览器访问：**http://localhost:8080**

> 🌐 如果部署在远程服务器上，可直接访问 **http://39.106.56.174:8080** 使用在线版。

---

### 1.2 第一次回测（5 分钟上手）

1. 点击左侧导航 **「单股分析」**
2. 选择股票：输入 `600519`（贵州茅台）
3. 选择策略：保持默认 `ma_cross`
4. 选择周期：`1y`（最近一年）
5. 点击 **「开始分析」**
6. 查看结果：收益率、胜率、夏普比率、交易明细

---

## 2. Web 界面详解

### 2.1 仪表盘 `#/`

系统首页，展示整体状态：

| 信息 | 说明 |
|------|------|
| 🟢 API 状态 | 绿色=在线，红色=离线 |
| 📊 策略数量 | 当前可用策略总数 |
| 💾 数据源数量 | 已注册的数据源 |
| 📁 分组数量 | 已配置的股票分组 |

下方提供 4 个快捷入口卡片，直达各功能页面。

---

### 2.2 单股分析 `#/analyze`

**功能**：对单只股票运行指定策略的回测，查看详细的交易记录和图表。

**参数说明**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|:---:|------|
| 股票代码 | 下拉搜索框 | ✅ | 支持输入搜索，自动补全本地缓存的股票 |
| 策略 | 下拉选择 | ✅ | 可选所有已注册策略 |
| 周期 | 快捷选择 | ❌ | `1y`=1年 / `6m`=6月 / `3m`=3月 / `20d`=20天 / `60t`=60交易日 |
| 数据源 | 下拉选择 | ❌ | 默认自动（主备降级） |
| 开始/结束日期 | 日期选择 | ❌ | 精确日期优先于快捷周期 |
| 策略参数 | 动态面板 | ❌ | 点击展开可覆盖策略默认参数 |

**结果解读**：

| 指标 | 含义 | 好/坏 |
|------|------|-------|
| 总收益率 | 期末相对期初的收益 | >0 越好 |
| 胜率 | 盈利周期数 / 总周期数 | >50% 较优 |
| 最大回撤 | 权益曲线从峰到谷的最大跌幅 | 绝对值越小越好 |
| 夏普比率 | 风险调整后收益 | >1 可接受，>2 优秀 |

**图表**：
- **权益曲线**：K 线图形式的资产变化，绿色箭头=买入，红色箭头=卖出
- **回撤曲线**：灰色区域显示回撤深度
- **交易明细表**：每笔交易的日期、方向、价格、数量、原因

---

### 2.3 批量回测 `#/backtest`

**功能**：对多只股票同时回测同一策略，生成排行榜对比。

**两种输入模式**：

| 模式 | 操作 | 适用场景 |
|------|------|---------|
| 按代码 | 输入逗号分隔的股票代码 | 临时测试几只特定股票 |
| 按分组 | 选择预设股票分组 | 测试已分类的股票池 |

**结果展示**：
- **统计摘要**：总股票数、成功率、平均收益、最佳/最差表现
- **收益柱状图**：横向排列，绿色=正收益，红色=负收益
- **排行榜表格**：可排序（收益/回撤/夏普/胜率/交易数），前三名有金银铜牌
- **点击行**：跳转到该股票的单股分析页面

---

### 2.4 K 线数据 `#/bars`

**功能**：查看股票的原始日线 OHLCV 数据。

**交互功能**：
- 点击 K 线图上的蜡烛 → 右侧统计卡片更新为该日数据
- 对应表格行高亮
- 「回到最新」按钮恢复最新数据

---

### 2.5 分组管理 `#/groups`

**功能**：管理股票分组（创建、编辑、删除）。

**操作流程**：
1. 左侧列表点击分组名 → 右侧显示详情
2. 「新建分组」→ 填写分组 ID、名称、添加股票
3. 「编辑」→ 修改名称和股票列表
4. 「删除」→ 确认后删除

---

### 2.6 组合回测 `#/portfolio`

**功能**：模拟真实账户，同时持有多个标的，由选股器每天推荐候选，策略决定进出场。

**核心概念**：
- **选股器（Screener）**：每天从全市场筛选最优标的
- **出场管理**：四种出场规则保护资金
  - 移动止损：从持仓最高点回落 X% 卖出
  - 硬止损：亏损超过 X% 强制卖出
  - 时间止损：持有超过 X 天强制卖出
  - 信号衰减：排名跌出前 N 名卖出
- **市场环境**：根据候选质量动态调整最大持仓数（1-3 只）

---

### 2.7 AI 策略 `#/ai-strategy`

详见 [第 6 节 — AI 策略生成](#6-ai-策略生成)

---

## 3. CLI 命令行使用

### 3.1 基本命令

```bash
# Windows 用户
cli.bat <命令> [参数...]

# 所有平台
python -m autotrade.triggers.cli <命令> [参数...]
```

### 3.2 可用命令

```bash
# 单股分析
cli.bat analyze --symbol 600522 --strategy ma_cross --period 1y

# 批量回测（指定代码）
cli.bat backtest --strategy ma_cross --symbols "600522,000001,600036"

# 批量回测（按分组）
cli.bat backtest --strategy macd_divergence --group 自选 --period 6m

# 全市场扫描（Top N）
cli.bat scan --strategy ma_cross --top 20

# 组合回测
cli.bat portfolio-backtest --config config/backtest/portfolio.yaml

# 查看列表
cli.bat list strategies       # 可用策略
cli.bat list datasources      # 可用数据源
cli.bat list indicators       # 可用指标
cli.bat list-groups           # 股票分组

# 查看历史结果
cli.bat show --strategy ma_cross --period 1y
```

### 3.3 常用参数

| 参数 | 说明 | 示例 |
|------|------|------|
| `--symbol` | 股票代码 | `--symbol 000001` |
| `--symbols` | 多股票（逗号分隔） | `--symbols "600519,000858"` |
| `--strategy` | 策略名称 | `--strategy turtle` |
| `--period` | 快捷周期 | `--period 6m` |
| `--start / --end` | 精确日期 | `--start 2025-01-01 --end 2025-12-31` |
| `--group` | 股票分组 | `--group 科技` |
| `--datasource` | 数据源 | `--datasource akshare` |
| `--top` | 扫描取前 N | `--top 10` |

---

## 4. 策略配置与调参

### 4.1 参数配置方式

策略参数支持三种修改方式，优先级从低到高：

1. **YAML 配置文件**（默认值）
2. **Web 前端策略参数面板**（单次覆盖）
3. **环境变量**（全局覆盖）

### 4.2 通过 YAML 配置

编辑 `config/strategies/<策略名>.yaml`：

```yaml
# config/strategies/ma_cross.yaml
entry:
  fast_period: 5        # 快线周期
  slow_period: 20       # 慢线周期
  batch_count: 3        # 分批次数
  batch_size_pct: 0.33  # 每批仓位比例

exit:
  take_profit_levels:   # 阶梯止盈
    - pct: 0.15         # 涨 15% 卖 30%
      ratio: 0.3
    - pct: 0.30         # 涨 30% 卖 50%
      ratio: 0.5
  stop_loss_pct: 0.08   # 止损线 8%
  death_cross: true     # 死叉全平
```

### 4.3 通过 Web 前端调参

1. 进入「单股分析」或「批量回测」
2. 点击「策略参数」展开面板
3. 修改参数值
4. 点击「开始分析」— 本次回测使用覆盖后的参数

### 4.4 策略参数说明（通用）

| 参数类别 | 常见参数 | 说明 |
|---------|---------|------|
| 入场 | `fast_period`, `slow_period` | MA 均线周期 |
| 入场 | `batch_count`, `batch_size_pct` | 分批建仓次数和比例 |
| 入场 | `rsi_threshold` | RSI 过滤阈值 |
| 入场 | `volume_ratio` | 放量倍数要求 |
| 出场 | `take_profit_levels` | 阶梯止盈 [涨幅%, 卖出比例] |
| 出场 | `stop_loss_pct` | 止损线 |
| 出场 | `trailing_stop_active_pct` | 移动止损激活线 |
| 出场 | `trailing_stop_drawdown_pct` | 移动止损回撤幅度 |
| 出场 | `time_stop_days` | 持仓最大天数 |
| 出场 | `death_cross` | 死叉全平开关 |
| 仓位 | `position_sizing` | `strength`(按信号强度) 或 `full`(全仓) |

---

## 5. 股票分组管理

### 5.1 什么是分组

分组是一组有共同特征的股票集合，例如：
- `科技` — 100 只 AI、芯片、5G、信创股票
- `自选` — 个人关注的几只股票
- `银行` — 银行板块

### 5.2 创建分组

**方式一：Web 界面**
1. 进入「分组管理」
2. 点击「新建分组」
3. 填写 ID、名称、逐行添加股票代码和名称
4. 保存

**方式二：YAML 文件**

在 `config/groups/` 下创建 `.yaml` 文件：

```yaml
# config/groups/新能源.yaml
id: 新能源
name: 新能源
symbols:
  - code: "300750"
    name: 宁德时代
  - code: "002594"
    name: 比亚迪
  - code: "601012"
    name: 隆基绿能
```

> 📂 文件名可以是中文，如 `科技.yaml`、`自选.yaml`

### 5.3 使用分组

- **回测**：在批量回测中选择「按分组」模式
- **CLI**：`cli.bat backtest --group 科技 --strategy ma_cross`

---

## 6. AI 策略生成

### 6.1 什么是 AI 策略生成

用自然语言描述你的交易想法，AI 自动：
1. 编写完整的 Python 策略代码
2. 生成参数配置文件
3. 运行回测验证效果
4. 展示回测结果

### 6.2 如何使用

1. 点击左侧「AI 策略」
2. 在输入框用中文描述你的策略想法
3. 发送后 AI 开始生成
4. 查看生成结果和回测数据
5. 可继续对话修改策略参数

### 6.3 提示词示例

**简单示例**：
> "当 5 日均线上穿 20 日均线时买入，下穿时卖出"

**详细示例**：
> "设计一个趋势跟踪策略：
> - 入场：MA10 上穿 MA30，同时成交量大于 20 日均量的 1.5 倍
> - 止损：买入价的 5%
> - 止盈：分两档，涨 10% 卖一半，涨 20% 全卖
> - 过滤：RSI < 70 时才允许买入"

**修改已有策略**：
> "把止损从 5% 改成 8%，增加一个持仓超过 10 天强制卖出的规则"

### 6.4 多轮对话

生成策略后可以继续对话优化：
- "帮我加一个布林带收窄的过滤条件"
- "回测周期改成最近 2 年看看效果"
- "把这个策略保存下来"

### 6.5 保存与使用

- 「保存策略」→ 写入 `autotrade/strategies/` 和 `config/strategies/`
- 保存后可在单股分析、批量回测中直接选用
- 可在分组管理中「删除」不再需要的 AI 策略

---

## 7. 组合回测

### 7.1 什么是组合回测

不同于单股/批量回测（每只股票独立），组合回测模拟**一个真实账户同时持有多只股票**的场景。

### 7.2 工作流程

```
每天收盘后：
  ┌──────────────────────────────────────────────┐
  │ 1. 选股器扫描全市场 → 选出 N 个候选标的        │
  │ 2. 市场环境感知 → 决定明天最多买几只（0-3）     │
  │ 3. （可选）AI 二次筛选 → TradingAgents 评估    │
  └──────────────────────────────────────────────┘
                      ↓
每天开盘时：
  ┌──────────────────────────────────────────────┐
  │ 4. 执行昨天的买入计划                          │
  │ 5. 检查现有持仓的出场条件（策略卖出 + 四门规则）  │
  │ 6. 更新账户权益                                │
  └──────────────────────────────────────────────┘
```

### 7.3 配置方式

编辑 `config/backtest/portfolio.yaml`：

```yaml
capital: 1000000          # 初始资金
cash_buffer_pct: 0.05     # 现金缓冲 5%

screener:
  name: momentum_screener # 选股器
  top_n: 50               # 每日候选数

strategy:
  name: hot_money         # 持仓策略

market_regime:
  bullish_max_positions: 3  # 强势市场最多 3 只
  neutral_max_positions: 2  # 中性市场最多 2 只
  bearish_max_positions: 1  # 弱势市场最多 1 只

exit_rules:
  trailing_stop:
    active_pct: 0.10      # 盈利 10% 后激活
    drawdown_pct: 0.05    # 从高点回落 5% 卖出
  hard_stop:
    loss_pct: 0.08        # 亏损 8% 强制卖出
  time_stop:
    max_days: 7           # 持仓超过 7 天卖出
  signal_decay:
    rank_threshold: 15    # 排名跌出前 15 卖出
```

### 7.4 运行

**Web 界面**：进入「组合回测」页面，配置参数后提交

**CLI**：
```bash
python scripts/run_portfolio_backtest.py
```

### 7.5 结果解读

- **权益曲线**：账户总资产的日变化
- **回撤曲线**：账户的日内最大回撤
- **每日收益分布**：每日期望收益的波动情况
- **交易清单 CSV**：所有买卖记录的导出

---

## 8. 数据管理

### 8.1 数据源优先级

系统使用主备降级链获取数据：

```
1. 本地 Parquet 缓存（最快，零网络）
   ↓ 未命中
2. Tushare Pro（高质量，需 token）
   ↓ 失败/未配置
3. AKShare（免费公开，无需 token）
```

每次从网络源获取的数据会自动缓存到本地。

### 8.2 下载数据

```bash
# 下载全市场 3 年日线
python scripts/download_stocks.py

# 更多选项
python scripts/download_stocks.py --help
```

### 8.3 导出股票列表

```bash
# 导出全 A 股列表到 CSV
python scripts/export_stock_list.py
```

### 8.4 数据存储位置

| 目录 | 内容 |
|------|------|
| `data/daily/` | 日线 Parquet 文件（每只股票一个） |
| `data/cache/` | 元数据缓存（JSON） |
| `data/results/` | 回测结果（CSV + JSON） |
| `data/logs/` | 运行日志 |

### 8.5 配置 Tushare Token

1. 注册 [Tushare Pro](https://tushare.pro)
2. 获取 API Token
3. 配置：

```yaml
# config/settings.yaml
datasource:
  sources:
    tushare:
      enabled: true
      token: "你的token"
```

或环境变量：
```bash
export AUTOTRADE__DATASOURCE__SOURCES__TUSHARE__TOKEN="你的token"
```

---

## 9. 定时任务

### 9.1 配置定时任务

编辑 `config/scheduler.yaml`：

```yaml
jobs:
  - id: daily-scan
    cron: "30 15 * * 1-5"     # 周一至周五 15:30
    type: scan
    strategy: ma_cross
    top: 20

  - id: weekly-review
    cron: "0 18 * * 5"        # 每周五 18:00
    type: backtest
    strategy: macd_divergence
    symbols: ["000001", "600519"]
```

### 9.2 启动调度器

```bash
python -c "from autotrade.triggers.scheduler import main; main()"
```

---

## 10. 常见问题

### Q1: 启动报错 "拒绝访问" / "Access denied"

**原因**：端口 8080 被占用或防火墙拦截

**解决**：
```bash
# 查找占用 8080 端口的进程
# Windows:
netstat -ano | findstr :8080
# 然后 taskkill /PID <PID> /F
```

### Q2: 回测报错 "No bar data for ..."

**原因**：本地没有该股票的数据

**解决**：
1. 先运行 `python scripts/download_stocks.py` 下载数据
2. 或检查股票代码是否正确

### Q3: 策略参数修改后不生效

**原因**：参数优先级问题

**检查顺序**：
1. Web 前端策略参数面板是否展开了旧的值
2. YAML 配置文件是否格式错误
3. 环境变量是否覆盖了你的设置

### Q4: AI 策略生成失败

**可能原因**：
- DeepSeek API 密钥未配置（需在环境变量中设置）
- 网络连接问题
- 生成的代码有语法错误（会自动在界面上展示错误信息）

### Q5: 回测速度太慢

**优化方法**：
1. 缩小回测周期（用 `6m` 代替 `1y`）
2. 减少批量回测的股票数量
3. 确保本地缓存生效（`cache.enabled: true`）
4. 使用 `--top 10` 限制全市场扫描范围

### Q6: Web 界面显示异常

**尝试**：
1. 刷新页面（Ctrl+F5 强制刷新）
2. 清除浏览器缓存
3. 检查浏览器控制台是否有报错（F12）
4. 确认前端构建是最新的：`cd web && npm run build`

### Q7: 如何自定义策略

1. 在 `autotrade/strategies/` 新建 Python 文件
2. 继承 `Strategy` 基类，实现 `generate_signals()`
3. 在 `config/strategies/` 创建同名 YAML
4. 重启服务器

详见 [README 插件系统章节](./README.md#插件系统)

---

<p align="center">
  <sub>📧 有问题？欢迎提 Issue 或 PR</sub>
</p>
