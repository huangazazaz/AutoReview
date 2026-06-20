# AutoTrade API 文档

```
Base URL: http://localhost:8080
Content-Type: application/json
```

---

## 1. 健康检查

```http
GET /health
```

**响应**:
```json
{"status": "ok"}
```

---

## 2. 单股回测

```http
POST /analyze
```

**请求体**:

| 字段 | 类型 | 必填 | 说明 |
|------|------|:---:|------|
| `symbol` | string | ✅ | 股票代码，如 `"600522"` |
| `strategy` | string | ❌ | 策略名，默认 `"ma_cross"` |
| `start` | string | ❌ | 开始日期 `"YYYY-MM-DD"`，优先于 period |
| `end` | string | ❌ | 结束日期 `"YYYY-MM-DD"` |
| `period` | string | ❌ | 快捷周期，默认 `"1y"`（见下方 Period 说明） |
| `datasource` | string | ❌ | 数据源，默认走主备降级 |

**请求示例**:
```json
{
  "symbol": "600522",
  "strategy": "ma_cross",
  "period": "6m"
}
```

**响应**:
```json
{
  "symbol": "600522",
  "stock_name": "",
  "metrics": {
    "initial_capital": 1000000.00,
    "final_equity": 1489800.00,
    "total_trades": 25,
    "buy_trades": 15,
    "sell_trades": 10,
    "total_return_pct": 74.68,
    "win_rate": 66.67,
    "max_drawdown_pct": -10.70,
    "sharpe_ratio": 3.22
  },
  "signal_count": 25,
  "trades": [
    {
      "date": "2026-01-20",
      "action": "BUY",
      "price": 18.92,
      "quantity": 31700,
      "commission": 179.92,
      "stamp_duty": 0.0,
      "position": 31700,
      "cash": 400056.08,
      "total_equity": 999820.08,
      "reason": "金叉 MA5↑MA20"
    },
    {
      "date": "2026-02-09",
      "action": "SELL",
      "price": 23.30,
      "quantity": 6300,
      "commission": 44.03,
      "stamp_duty": 146.79,
      "position": 25400,
      "cash": 546715.05,
      "total_equity": 1138535.05,
      "reason": "止盈L1 +22.2%"
    }
  ],
  "equity_curve": [
    {"date": "2025-12-19", "equity": 1000000.00},
    {"date": "2025-12-22", "equity": 1001520.50}
  ]
}
```

**metrics 字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `initial_capital` | float | 初始资金 |
| `final_equity` | float | 最终权益（含未平仓市值） |
| `total_trades` | int | 总交易笔数 |
| `buy_trades` | int | 买入笔数 |
| `sell_trades` | int | 卖出笔数 |
| `total_return_pct` | float | 总收益率(%) |
| `win_rate` | float | 胜率(%)，按持仓周期计算 |
| `max_drawdown_pct` | float | 最大回撤(%)，负数 |
| `sharpe_ratio` | float | 夏普比率 |

**trades 字段说明**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `date` | string | 交易日 |
| `action` | string | BUY 买入 / SELL 卖出 |
| `price` | float | 成交价 |
| `quantity` | int | 本次成交股数 |
| `commission` | float | 佣金 |
| `stamp_duty` | float | 印花税（仅卖出） |
| `position` | int | 交易后持仓股数，0=空仓 |
| `cash` | float | 交易后剩余现金 |
| `total_equity` | float | 交易后总资产（现金+持仓市值） |
| `reason` | string | 触发原因（金叉/死叉/止盈/止损/回撤加仓等） |

**equity_curve** (每日净值曲线):

| 字段 | 类型 | 说明 |
|------|------|------|
| `date` | string | 日期 |
| `equity` | float | 当日总资产 |

---

## 3. 批量回测

```http
POST /backtest
```

**请求体**:

| 字段 | 类型 | 必填 | 说明 |
|------|------|:---:|------|
| `strategy` | string | ❌ | 策略名，默认 `"ma_cross"` |
| `symbols` | string | 二选一 | 股票代码，逗号分隔 `"600522,000001"` |
| `group` | string | 二选一 | 分组名 `"自选"`，对应 `config/groups/<name>.yaml` |
| `start` | string | ❌ | 开始日期 |
| `end` | string | ❌ | 结束日期 |
| `period` | string | ❌ | 快捷周期，默认 `"1y"` |
| `datasource` | string | ❌ | 数据源 |

**请求示例**:
```json
{
  "strategy": "ma_cross",
  "group": "自选",
  "period": "6m"
}
```

```json
{
  "strategy": "ma_cross",
  "symbols": "600522,000001,600036",
  "period": "1y"
}
```

**响应**:
```json
{
  "total": 2,
  "success": 2,
  "failed": 0,
  "avg_return_pct": 18.17,
  "positive_count": 1,
  "negative_count": 1,
  "best_symbol": "600522",
  "best_return": 48.98,
  "worst_symbol": "000001",
  "worst_return": -12.63,
  "results": [
    {
      "symbol": "600522",
      "stock_name": "中天科技",
      "trades": 8,
      "return_pct": 48.98,
      "sharpe": 2.6334,
      "max_drawdown_pct": -5.21,
      "win_rate": 66.67
    },
    {
      "symbol": "000001",
      "stock_name": "平安银行",
      "trades": 9,
      "return_pct": -12.63,
      "sharpe": -2.8794,
      "max_drawdown_pct": -15.30,
      "win_rate": 33.33
    }
  ]
}
```

**响应字段**:

| 字段 | 类型 | 说明 |
|------|------|------|
| `total` | int | 总股票数 |
| `success` | int | 成功数 |
| `failed` | int | 失败数 |
| `avg_return_pct` | float | 平均收益率(%) |
| `positive_count` | int | 正收益股票数 |
| `negative_count` | int | 负收益股票数 |
| `best_symbol` | string | 最佳股票代码 |
| `best_return` | float | 最佳收益率(%) |
| `worst_symbol` | string | 最差股票代码 |
| `worst_return` | float | 最差收益率(%) |
| `results` | array | 每只股票的汇总 |
| `results[].symbol` | string | 股票代码 |
| `results[].stock_name` | string | 股票名称 |
| `results[].trades` | int | 交易笔数 |
| `results[].return_pct` | float | 收益率(%) |
| `results[].sharpe` | float | 夏普比率 |
| `results[].max_drawdown_pct` | float | 最大回撤(%)，负数 |
| `results[].win_rate` | float | 胜率(%) |

> 注意：`/backtest` 只返回汇总，不返回每只股票的详细交易记录。如需单股详情，用 `/analyze` 逐只请求。

---

## 4. 策略列表

```http
GET /strategies
```

**响应**:
```json
{
  "strategies": ["ma_cross", "macd_divergence"]
}
```

---

## 5. 分组列表

```http
GET /groups
```

**响应**:
```json
{
  "groups": [
    {
      "id": "自选",
      "name": "自选",
      "symbols": [
        {"code": "600522", "name": "中天科技"},
        {"code": "000001", "name": "平安银行"}
      ]
    },
    {
      "id": "通信",
      "name": "通信",
      "symbols": [
        {"code": "600522", "name": "中天科技"},
        {"code": "000063", "name": "中兴通讯"},
        {"code": "600487", "name": "亨通光电"}
      ]
    }
  ]
}
```

---

## 6. 数据源列表

```http
GET /datasources
```

**响应**:
```json
{
  "datasources": ["akshare", "tushare", "local"]
}
```

---

## Period 快捷周期说明

| 写法 | 含义 | 示例 |
|------|------|------|
| `"1y"` | 最近 1 年 | 默认值 |
| `"6m"` | 最近 6 个月 | |
| `"3m"` | 最近 3 个月 | |
| `"20d"` | 最近 20 个日历日 | |
| `"60t"` | 最近约 60 个交易日 | |

如果同时传了 `start`/`end` 和 `period`，**显式日期优先**。

---

## 7. 分组 CRUD

### 获取单个分组

```http
GET /groups/{id}
```

**响应**: 同 `GET /groups` 中的单个元素格式。

### 创建分组

```http
POST /groups
```

**请求体**:
```json
{
  "id": "新能源",
  "name": "新能源",
  "symbols": [
    {"code": "300750", "name": "宁德时代"},
    {"code": "002594", "name": "比亚迪"}
  ]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|:---:|------|
| `id` | string | ✅ | 分组唯一标识（文件名） |
| `name` | string | ❌ | 显示名称，默认同 id |
| `symbols` | array | ❌ | 股票列表 |
| `symbols[].code` | string | ✅ | 股票代码 |
| `symbols[].name` | string | ❌ | 股票名称 |

**响应**: 创建后的分组完整信息。

### 更新分组

```http
PUT /groups/{id}
```

**请求体**: 同创建，所有字段可选，传了就更新。

```json
{
  "name": "新能源改名",
  "symbols": [
    {"code": "300750", "name": "宁德"},
    {"code": "002594", "name": "比亚迪"},
    {"code": "601012", "name": "隆基绿能"}
  ]
}
```

### 删除分组

```http
DELETE /groups/{id}
```

**响应**:
```json
{"ok": true, "deleted": "新能源"}
```

---

## 8. 日线数据查询

```http
POST /bars
```

**请求体**:

| 字段 | 类型 | 必填 | 说明 |
|------|------|:---:|------|
| `symbol` | string | ✅ | 股票代码 |
| `start` | string | ❌ | 开始日期 |
| `end` | string | ❌ | 结束日期 |
| `period` | string | ❌ | 快捷周期，默认 `"1y"` |

**请求示例**:
```json
{
  "symbol": "600522",
  "period": "20d"
}
```

**响应**:
```json
{
  "symbol": "600522",
  "count": 14,
  "start": "2026-06-01",
  "end": "2026-06-19",
  "bars": [
    {
      "date": "2026-06-01",
      "open": 44.50,
      "high": 45.80,
      "low": 43.90,
      "close": 45.13,
      "volume": 12500000,
      "amount": 560000000
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `symbol` | string | 股票代码 |
| `count` | int | K 线条数 |
| `start` | string | 实际开始日期 |
| `end` | string | 实际结束日期 |
| `bars` | array | 日线数据列表 |
| `bars[].date` | string | 交易日期 |
| `bars[].open` | float | 开盘价 |
| `bars[].high` | float | 最高价 |
| `bars[].low` | float | 最低价 |
| `bars[].close` | float | 收盘价 |
| `bars[].volume` | float | 成交量（股） |
| `bars[].amount` | float | 成交额（元） |

---

## 9. 本地缓存股票

```http
GET /cache/stocks
```

列出所有已在本地缓存日线数据的股票，供前端下拉框快速选择。

**响应**:
```json
{
  "symbols": [
    {
      "symbol": "600522",
      "bars": 295,
      "start": "2025-04-01",
      "end": "2026-06-18",
      "last_close": 56.55
    },
    {
      "symbol": "000001",
      "bars": 295,
      "start": "2025-04-01",
      "end": "2026-06-18",
      "last_close": 10.52
    }
  ]
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `symbol` | string | 股票代码 |
| `bars` | int | 缓存 K 线条数 |
| `start` | string | 最早日期 |
| `end` | string | 最晚日期 |
| `last_close` | float | 最新收盘价 |

---

## 前端调用示例

```javascript
// 1. 获取分组列表
const groups = await fetch('/groups').then(r => r.json());

// 2. 跑分组回测
const result = await fetch('/backtest', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    strategy: 'ma_cross',
    group: '自选',
    period: '6m'
  })
}).then(r => r.json());

// result.avg_return_pct → 18.17
// result.results → [{symbol, trades, return_pct, sharpe}, ...]

// 3. 查看单股详情
const detail = await fetch('/analyze', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    symbol: '600522',
    strategy: 'ma_cross',
    period: '6m'
  })
}).then(r => r.json());

// detail.metrics → 完整指标
// detail.trades → 逐笔交易记录
// detail.signal_count → 信号数
```

---

## 错误响应

```json
{
  "error": "No data"
}
```

或 HTTP 422（请求参数校验失败）:
```json
{
  "detail": [
    {
      "loc": ["body", "symbol"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```
