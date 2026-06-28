# AI Strategy Generator — Design Spec

**Date**: 2026-06-28
**Status**: Approved
**Branch**: dev/autotrade-mvp

---

## 1. Problem Statement

Users currently must write Python strategy classes + YAML configs manually. This requires programming knowledge and understanding of the plugin interface. We want to allow users to describe trading ideas in natural language and have AI generate working strategies with instant backtest feedback.

## 2. Core Workflow

```
User describes strategy in natural language
  → AI generates Python class + YAML config
    → Single-stock quick backtest
      → User reviews results
        → Save to disk (permanent) or delete (discard)
```

## 3. Architecture

### 3.1 New Files

| File | Purpose |
|---|---|
| `autotrade/ai/strategy_generator.py` | DeepSeek-powered strategy code generator |
| `web/src/pages/AIStrategy.tsx` | Chat-based AI strategy builder UI |

### 3.2 Modified Files

| File | Change |
|---|---|
| `autotrade/api/server.py` | 3 new endpoints: generate-strategy, save-strategy, delete-strategy |
| `web/src/App.tsx` | Route `/ai-strategy` |
| `web/src/components/Sidebar.tsx` | Nav item "AI 策略" |

## 4. API Endpoints

### 4.1 `POST /ai/generate-strategy`

**Request:**
```json
{
  "prompt": "做一个5日和10日均线金叉买入、死叉卖出的策略，止损5%",
  "symbol": "600522",
  "start": "2025-01-01",
  "end": "2025-12-31"
}
```

**Response (success):**
```json
{
  "name": "ma_cross_5_10",
  "display_name": "5日10日均线交叉策略",
  "description": "MA5上穿MA10买入，下穿卖出，5%止损",
  "python_code": "from autotrade.core.interfaces import Strategy...",
  "yaml_code": "strategy: ma_cross_5_10\nparams:\n  fast: 5\n  slow: 10...",
  "backtest": {
    "symbol": "600522",
    "return_pct": 32.5,
    "win_rate": 45.2,
    "sharpe_ratio": 1.82,
    "max_drawdown_pct": -12.3,
    "total_trades": 24
  },
  "reasoning": "经典的短期均线交叉策略..."
}
```

**Response (error):**
```json
{
  "error": "AI 返回格式异常，请重试"
}
```

**Flow:**
1. Fill prompt template with user's description
2. Call DeepSeek API (`deepseek-chat`)
3. Parse JSON response
4. Validate Python syntax via `compile()`
5. Dynamically register strategy
6. Run single-stock backtest (600522 default, 1 year)
7. Return everything

### 4.2 `POST /strategies/save`

**Request:**
```json
{
  "name": "ma_cross_5_10",
  "python_code": "...",
  "yaml_code": "..."
}
```

**Response:**
```json
{
  "success": true,
  "name": "ma_cross_5_10",
  "python_path": "autotrade/strategies/ma_cross_5_10.py",
  "yaml_path": "config/strategies/ma_cross_5_10.yaml"
}
```

**Error cases:**
- Name conflict → `{ error: "策略名已存在: ma_cross_5_10" }`
- File write error → `{ error: "保存失败: ..." }`

**Post-save:** Automatically calls `registry.init_registry(force_reload=True)` to make the new strategy available immediately.

### 4.3 `DELETE /strategies/{name}`

**Response (success):**
```json
{
  "success": true,
  "name": "ma_cross_5_10"
}
```

**Response (protected):**
```json
{
  "error": "不能删除内置策略: turtle"
}
```

Built-in strategies (turtle, ma_cross, ma_cross_macd, hot_money, golden_filter, trend_ma_breakout, trend_bb_rsi, macd_divergence) are protected from deletion.

## 5. AI Strategy Generator

### 5.1 Prompt Template

```
你是一个量化策略工程师。根据用户的自然语言描述，生成一个完整的交易策略。

你必须返回严格的 JSON 格式，包含以下字段：
{
  "name": "策略英文名（snake_case，如 ma_cross_v2）",
  "display_name": "策略中文名（简短）",
  "description": "一句话描述策略逻辑",
  "python_code": "完整的 Python 策略类代码",
  "yaml_code": "完整的 YAML 配置",
  "reasoning": "简要设计思路（1-2句）"
}

策略 Python 类必须遵循以下接口：
- 继承自 autotrade.core.interfaces.Strategy
- 必须设置 name 属性（与策略名一致）
- required_indicators 声明所需指标（使用 autotrade.indicators 下的类）
- 实现 generate_signals(self, df: pd.DataFrame) -> list[Signal] 方法
  - df 的 index 是 date，包含 open/high/low/close/volume 列 + 指标列
  - 返回 Signal(symbol="", date=date, action="BUY"/"SELL", strength=0.0~1.0, reason="")

可用的指标类 (在 autotrade.indicators 包中):
- MARibbon(params: period=5) → 列: ma_{period}
- RSIIndicator(params: period=14) → 列: rsi
- ATRIndicator(params: period=14) → 列: atr
- MACDIndicator(params: fast=12, slow=26, signal=9) → 列: macd, macd_signal, macd_hist
- BollingerIndicator(params: period=20, std=2) → 列: bb_upper, bb_middle, bb_lower

YAML 格式:
strategy: <name>
params:
  param1: value1
  param2: value2

用户需求: {user_prompt}
```

### 5.2 Error Handling

| Scenario | Response |
|---|---|
| DeepSeek API error | `{ error: "AI 服务暂时不可用，请稍后重试" }` |
| JSON parse failure | `{ error: "AI 返回格式异常，请重试", raw: "..." }` |
| Python syntax error | `{ error: "生成的策略代码有语法错误", details: "..." }` |
| Name conflict | Auto-append `_v{N}` suffix, retry |
| Backtest fails | Still return code + yaml with `backtest: null` |

## 6. Frontend UI

### 6.1 Page Layout

Three sections:

**Left sidebar (240px):**
- Stock symbol input (default: 600522)
- Date range picker
- Example prompts (click to fill)

**Main chat area:**
- Scrollable message history
- User messages: right-aligned bubble with prompt text
- AI response card: strategy name, backtest metrics (4 stat cards), collapsible code blocks, action buttons

**Bottom input bar:**
- Text input + Send button
- "换一批示例" to refresh example prompts

### 6.2 AI Response Card

```
┌──────────────────────────────────────────┐
│ 🤖 已生成: 5日10日均线交叉策略            │
│ 经典短期均线交叉，5%止损保护               │
├──────────────────────────────────────────┤
│  收益率: +32.5%  胜率: 45.2%             │
│  夏普: 1.82      最大回撤: -12.3%        │
│  交易次数: 24                             │
├──────────────────────────────────────────┤
│  📝 策略代码 (点击展开)            [▼]    │
├──────────────────────────────────────────┤
│  [🔄 换个股票回测] [💾 保存] [🗑 删除]    │
│  [🔄 重新生成]                            │
└──────────────────────────────────────────┘
```

### 6.3 States

- **Loading**: Spinner with "AI 正在生成策略..."
- **Error**: Red banner with error message + retry button
- **Empty**: Example prompts + "输入策略想法开始"
- **Saved**: Button changes to "✅ 已保存" (disabled)

## 7. Strategy Save/Delete

### Save

Writes two files:
- `autotrade/strategies/{name}.py`
- `config/strategies/{name}.yaml`

Then reloads the plugin registry so the strategy is immediately available in the strategy dropdowns on Analyze/Backtest/Portfolio pages.

### Delete

Removes both files, reloads registry. Built-in strategies are protected (hardcoded list).

## 8. Testing Plan

### Unit Tests
- `test_strategy_generator.py`: Prompt template formatting, JSON response parsing, syntax validation
- `test_ai_strategy_api.py`: Generate endpoint (mock DeepSeek), save endpoint, delete endpoint, protected strategies

### Integration Test
- End-to-end: mock DeepSeek response → generate → parse → backtest → verify result shape
