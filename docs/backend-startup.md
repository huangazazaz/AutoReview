# AutoTrade 后端启动指南

## 快速启动

| 平台 | 脚本 | 说明 |
|------|------|------|
| Windows | `start.bat` | 双击或命令行运行，启动 API 服务器 |
| macOS / Linux | `./start.sh` | 终端运行，启动 API 服务器 |
| Windows CLI | `cli.bat <命令>` | 快捷命令行入口，如 `cli.bat analyze --symbol 000001` |

```bash
# Windows
start.bat                      # 启动 Web 服务
cli.bat list strategies        # 查看可用策略

# macOS / Linux
./start.sh                     # 启动 Web 服务
python -m autotrade.triggers.cli list strategies
```

---

## 目录

- [环境要求](#环境要求)
- [安装依赖](#安装依赖)
- [启动方式](#启动方式)
  - [1. API 服务器（Web 前端 + REST API）](#1-api-服务器web-前端--rest-api)
  - [2. CLI 命令行](#2-cli-命令行)
  - [3. 定时调度器](#3-定时调度器)
- [配置说明](#配置说明)
- [目录结构](#目录结构)
- [常见问题](#常见问题)

---

## 环境要求

| 组件 | 版本 |
|------|------|
| Python | ≥ 3.10 |
| pip | ≥ 22.0（推荐 24+） |
| 网络 | 需要访问 A 股数据源（AKShare / Tushare） |

---

## 安装依赖

### 方式一：从 pyproject.toml 安装（推荐）

```bash
# 如果在 git 仓库中，pyproject.toml 可能已被删除，先恢复：
git restore pyproject.toml

# 安装核心依赖
pip install -e .

# 安装 API 服务依赖（FastAPI + Uvicorn）
pip install -e ".[api]"

# 可选：安装 Tushare 数据源支持
pip install -e ".[tushare]"

# 可选：安装图表报告依赖
pip install -e ".[plot]"

# 可选：安装开发/测试依赖
pip install -e ".[dev]"

# 一键安装所有依赖：
pip install -e ".[api,tushare,plot,dev]"
```

### 方式二：手动安装

```bash
pip install pandas>=2.0 numpy>=1.24 pyyaml>=6.0 click>=8.1 \
            apscheduler>=3.10 akshare>=1.10 pandas-ta>=0.3.14b \
            pyarrow>=14.0 rich>=13.0 fastapi>=0.104 uvicorn
```

### 方式三：使用虚拟环境（推荐生产环境）

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[api]"

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[api]"
```

---

## 启动方式

### 1. API 服务器（Web 前端 + REST API）

启动 Web 服务，提供前端界面和 REST API：

```bash
python -m autotrade.api
```

启动后访问：
- **前端界面**: http://localhost:8080
- **API 文档 (Swagger)**: http://localhost:8080/docs
- **健康检查**: http://localhost:8080/health

**服务器参数**（在 `autotrade/api/__main__.py` 中配置）：
| 参数 | 默认值 | 说明 |
|------|--------|------|
| host | `0.0.0.0` | 监听地址（`0.0.0.0` 允许外部访问） |
| port | `8080` | 监听端口 |
| reload | `true` | 代码变更自动重载（开发模式） |

生产环境建议关闭 `reload` 并使用 `uvicorn` 直接启动：

```bash
uvicorn autotrade.api.server:app --host 0.0.0.0 --port 8080 --workers 4
```

> **提示**：Windows 用户可直接双击 `start.bat` 启动。

---

### 2. CLI 命令行

用于命令行快速回测、扫描和分析。安装包后可使用 `autotrade` 命令：

```bash
# 单股分析
autotrade analyze --symbol 000001 --strategy ma_cross

# 批量回测（指定多只股票）
autotrade backtest --strategy ma_cross --symbols "000001,600519,600522"

# 按分组批量回测
autotrade backtest --strategy macd_divergence --group 自选

# 全市场扫描
autotrade scan --strategy ma_cross --top 10

# 查看可用策略
autotrade list strategies

# 查看可用数据源
autotrade list datasources

# 查看股票分组
autotrade list-groups
```

如果未通过 pip 安装包，可直接运行模块：

```bash
python -m autotrade.triggers.cli analyze --symbol 000001 --strategy ma_cross
```

> **可用策略**: `ma_cross`（均线交叉）、`macd_divergence`（MACD 背离）  
> **可用周期**: `1y`（1年）、`6m`（6月）、`3m`（3月）、`20d`（20天）、`60t`（60交易日）

---

### 3. 定时调度器

按 `config/scheduler.yaml` 中配置的 cron 表达式定时执行任务：

```bash
# 安装包后
autotrade-scheduler

# 或直接运行
python -c "from autotrade.triggers.scheduler import main; main()"
```

当前调度配置（`config/scheduler.yaml`）：

| 任务名 | 时间 | 策略 | 说明 |
|--------|------|------|------|
| `daily-scan` | 周一~周五 15:30 | `ma_cross` | 全市场扫描 Top 20 |
| `weekly-review` | 每周五 18:00 | `macd_divergence` | 回测 000001 + 600519 |

---

## 配置说明

### 配置文件优先级（低 → 高）

1. 代码硬编码默认值
2. `config/settings.yaml`（提交到 git）
3. 环境变量 `AUTOTRADE__<SECTION>__<KEY>`
4. `config/settings.local.yaml`（本地覆盖，不提交 git）

### 关键配置项（`config/settings.yaml`）

```yaml
datasource:
  default: failover          # 数据源模式（failover=主备降级）
  sources:
    tushare:
      enabled: true          # 主力数据源（需配 token）
      priority: 1
      token: ""              # Tushare API token
    akshare:
      enabled: true          # 备用数据源（免费，无需 token）
      priority: 2

backtest:
  initial_capital: 100000    # 初始资金
  fill_price: next_open      # 成交价（next_open=次日开盘价）
  commission_rate: 0.0003    # 佣金费率
  stamp_duty_rate: 0.001     # 印花税（仅卖出）
  slippage: 0.001            # 滑点
  allow_t_plus_1: true       # T+1 制度

logging:
  level: INFO                # 日志级别
  file: data/logs/autotrade.log
```

### 环境变量覆盖示例

```bash
# Windows PowerShell
$env:AUTOTRADE__BACKTEST__INITIAL_CAPITAL = 200000
$env:AUTOTRADE__DATASOURCE__SOURCES__TUSHARE__TOKEN = "your_token"

# macOS / Linux
export AUTOTRADE__BACKTEST__INITIAL_CAPITAL=200000
export AUTOTRADE__DATASOURCE__SOURCES__TUSHARE__TOKEN="your_token"
```

### 策略参数配置

策略参数存放在 `config/strategies/<策略名>.yaml`：

- `config/strategies/ma_cross.yaml` — 均线交叉策略参数
- `config/strategies/macd_divergence.yaml` — MACD 背离策略参数

可以直接编辑这些文件修改策略参数，也可通过 Web 前端在策略参数面板中覆盖。

---

## 目录结构

```
D:\AutoTrade\
├── autotrade/                 # 主包
│   ├── api/                   # FastAPI 服务器
│   │   ├── __main__.py        # API 入口（python -m autotrade.api）
│   │   └── server.py          # 路由定义 + 请求模型
│   ├── core/                  # 核心引擎
│   │   ├── engine.py          # 编排层（analyze_stock / run_backtest）
│   │   ├── backtester.py      # 回测撮合引擎
│   │   ├── config.py          # 配置加载（YAML + 环境变量）
│   │   ├── models.py          # 数据模型（Bar / Signal / Trade）
│   │   └── interfaces.py      # 插件抽象基类
│   ├── dataSources/           # 数据源插件
│   ├── indicators/            # 技术指标插件
│   ├── strategies/            # 策略插件
│   ├── reporters/             # 报告输出插件
│   └── triggers/              # 入口触发器
│       ├── cli.py             # Click CLI
│       └── scheduler.py       # APScheduler 定时任务
├── config/                    # 配置文件
│   ├── settings.yaml          # 全局配置
│   ├── scheduler.yaml         # 定时任务配置
│   ├── strategies/            # 策略参数
│   └── groups/                # 股票分组
├── frontend/                  # Web 前端（SPA）
├── tests/                     # 测试
├── data/                      # 运行时数据（缓存/结果/日志）
├── docs/                      # 文档
├── start.bat                  # Windows 一键启动
└── pyproject.toml             # 项目配置 + 依赖声明
```

---

## 常见问题

### Q: 启动后无法访问 localhost:8080？

检查防火墙是否拦截了 8080 端口。Windows 可以在"Windows 防火墙 → 高级设置 → 入站规则"中添加端口放行。

### Q: 回测报错 "No bar data for ..."？

数据源无法获取该股票的行情数据。检查：
1. 网络是否正常（AKShare 需要访问公开数据源）
2. Tushare token 是否有效（如果使用 Tushare 作为主力数据源）
3. 尝试切换数据源：`--datasource akshare`

### Q: Tushare token 在哪里获取？

访问 https://tushare.pro 注册账号，在"个人主页 → 接口 TOKEN"中获取。将 token 填入 `config/settings.yaml` 的 `datasource.sources.tushare.token` 字段。

### Q: 如何切换数据源？

1. **Web 前端**：在回测参数表单的"数据源"下拉框中选择
2. **CLI**：`autotrade analyze --symbol 000001 --datasource akshare`
3. **配置文件**：修改 `settings.yaml` 中 `datasource.default` 的值

### Q: 回测速度慢怎么办？

1. 使用 `--period 6m` 缩小回测时间范围
2. 确保本地缓存生效（`cache.enabled: true`）
3. 减少全市场扫描的股票数量（`--top 10`）

### Q: 如何添加自定义策略？

1. 在 `autotrade/strategies/` 下新建 `.py` 文件
2. 继承 `autotrade.core.interfaces.Strategy` 类
3. 实现 `generate_signals(self, df) -> list[Signal]` 方法
4. 设置类属性 `name` 和 `required_indicators`
5. 在 `config/strategies/` 下创建对应的 `.yaml` 参数文件
6. 重启服务器即可自动发现
