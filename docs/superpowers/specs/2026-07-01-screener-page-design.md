# Stock Screener Page — Design Spec

**Date**: 2026-07-01
**Branch**: dev/autotrade-mvp
**Status**: approved

---

## 1. Overview

新增「智能选股」页面，用户选择一个历史日期、一个选股器（Screener）和一个交易策略（Strategy），系统扫描全市场股票，先由选股器打分筛选候选，再由策略确认是否存在买点，最终返回当天最适合入手的股票及其详细理由。

### 核心流程

```
用户输入 → Screener 全市场扫描 → 候选排序 → Strategy 买点确认 → 返回有买点股票 + 因子明细
```

---

## 2. Backend Design

### 2.1 New API Endpoint: `GET /api/screeners`

List all available screeners with their parameter schemas (mirrors `GET /api/strategies` pattern).

**Response**:
```json
{
  "screeners": [
    {
      "name": "momentum_screener",
      "params": { "min_amount": 50000000, "score_threshold": 0.65, ... },
      "param_schema": {
        "min_amount": { "type": "float", "default": 50000000 },
        "score_threshold": { "type": "float", "default": 0.65 },
        ...
      }
    },
    {
      "name": "hot_money_screener",
      "params": { ... },
      "param_schema": { ... }
    }
  ]
}
```

Implementation: uses `list_screens()` from registry + `inspect.signature` for param schema (same as strategies endpoint).

### 2.2 New API Endpoint: `POST /api/screen`

**Request** (`ScreenRequest`):

```json
{
  "screener": "momentum",
  "strategy": "ma_cross",
  "date": "2026-06-30",
  "top_n": 20,
  "screener_params": { "momentum_weight": 0.25 },
  "strategy_params": { "fast_period": 5, "slow_period": 20 }
}
```

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `screener` | string | yes | — | Screener plugin name |
| `strategy` | string | yes | — | Strategy plugin name |
| `date` | string | yes | — | Target date (YYYY-MM-DD) |
| `top_n` | int | no | 20 | Max results returned |
| `screener_params` | dict | no | {} | Override screener YAML params |
| `strategy_params` | dict | no | {} | Override strategy YAML params |

**Response** (`ScreenResult`):

```json
{
  "date": "2026-06-30",
  "screener": "momentum",
  "strategy": "ma_cross",
  "universe_size": 4823,
  "candidates": 87,
  "with_buy_signal": 12,
  "results": [
    {
      "symbol": "600522",
      "name": "中天科技",
      "score": 0.87,
      "signal_tag": "momentum_pullback",
      "factor_breakdown": {
        "动量强度": 0.92,
        "短期回调": 0.85,
        "量能确认": 0.78,
        "均线排列": 0.90,
        "回调距离": 0.82,
        "波动率": 0.75,
        "一致性": 0.88
      },
      "buy_signal": {
        "date": "2026-06-30",
        "action": "BUY",
        "strength": 0.8,
        "reason": "快线5上穿慢线20，放量突破"
      },
      "key_metrics": {
        "close": 15.68,
        "volume": 52300000,
        "amount": 820000000,
        "ma_5": 15.20,
        "ma_20": 14.85,
        "ma_60": 13.92
      }
    }
  ]
}
```

**Sort order**: Stocks with `buy_signal != null` first, then by `score` descending within each group.

### 2.3 New Engine Function: `run_screen()`

Location: `autotrade/core/engine.py`

```python
def run_screen(
    screener_name: str,
    strategy_name: str,
    target_date: date,
    top_n: int = 20,
    screener_params: dict | None = None,
    strategy_params: dict | None = None,
) -> ScreenResult:
```

**Execution steps**:

1. Determine lookback window: `max(screener required days, strategy required indicator days)` — default 120 days
2. Load market data: fetch bars for all cached symbols in `[target_date - window, target_date]`, skip symbols with insufficient data
3. Instantiate Screener with merged params (YAML defaults + user overrides)
4. Call `Screener.scan(market_data, [target_date])` → candidates with scores and tags
5. Instantiate Strategy with merged params
6. For each candidate, compute indicators + `generate_signals(df)`, check for BUY signal on target_date
7. For each candidate, call `Screener.explain(symbol, date)` for factor breakdown
8. Extract key metrics from the last bar row (close, volume, amount, indicator values)
9. Sort: with buy_signal first, then by score descending
10. Truncate to top_n, return `ScreenResult`

### 2.4 Screener Interface Extension

Location: `autotrade/core/interfaces.py`

Add optional method to `Screener` base class:

```python
def explain(self, market_data: dict[str, pd.DataFrame],
            symbol: str, date: datetime.date) -> dict[str, float]:
    """Return factor-level scores for the given symbol on the given date.
    
    Returns:
        dict mapping factor name (Chinese) to score (0.0-1.0).
        Default returns empty dict; subclasses may override.
    """
    return {}
```

### 2.5 Screener `explain()` Implementations

**MomentumScreener** (`autotrade/screens/momentum.py`):
- Re-computes the 7 factors for the target symbol/date
- Returns: `{"动量强度": ..., "短期回调": ..., "量能确认": ..., "均线排列": ..., "回调距离": ..., "波动率": ..., "一致性": ...}`

**HotMoneyScreener** (`autotrade/screens/hot_money.py`):
- Re-computes its factor breakdown
- Returns factors specific to the detected signal type (pullback/breakout/strength)

### 2.6 Files Changed (Backend)

| File | Change |
|------|--------|
| `autotrade/core/interfaces.py` | Add `Screener.explain()` optional method |
| `autotrade/core/engine.py` | Add `run_screen()` function |
| `autotrade/core/models.py` | Add `ScreenResult` dataclass |
| `autotrade/api/server.py` | Add `GET /api/screeners` and `POST /api/screen` endpoints |
| `autotrade/screens/momentum.py` | Implement `explain()` |
| `autotrade/screens/hot_money.py` | Implement `explain()` |

---

## 3. Frontend Design

### 3.1 Route

`/screener` — protected route (requires auth), lazy-loaded `Screener.tsx`.

### 3.2 Sidebar

New nav item "选股" between "Dashboard" and "Analyze". Icon: `Search` or `Target`.

### 3.3 Page Layout

```
┌──────────────────────────────────────────────────────────┐
│  📊 智能选股                                              │
│  基于选股器扫描 + 策略买点确认，发现当天最佳入场机会         │
├──────────────────────────────────────────────────────────┤
│  [选股器 ▼] [交易策略 ▼] [日期 📅] [返回数量] [参数 ⚙]    │
│  ┌─ 参数面板（可折叠）───────────────────────────────────┐│
│  │ 选股器参数:  [momentum_weight] [volume_threshold] ... ││
│  │ 策略参数:    [fast_period] [slow_period] ...          ││
│  └──────────────────────────────────────────────────────┘│
│                                    [ 🔍 开始选股 ]        │
├──────────────────────────────────────────────────────────┤
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────┐ │
│  │ 扫描股票  │ │ 候选股票  │ │ 有买点    │ │ 命中率       │ │
│  │  4,823   │ │    87    │ │   12     │ │  0.25%      │ │
│  └──────────┘ └──────────┘ └──────────┘ └─────────────┘ │
├──────────────────────────────────────────────────────────┤
│  筛选: [全部 ○] [仅看有买点 ○]  评分 ≥ [0.6 ──slider──] │
├──────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐ │
│  │ # │ 代码    │ 名称  │ 评分 │ 信号标签 │ 因子 │ 买点 │ │
│  │───│─────────│───────│──────│──────────│──────│──────│ │
│  │🥇 │ 600522  │中天.. │ 0.87 │ momentum │██░░░│ BUY  │ │
│  │🥈 │ 000001  │平安.. │ 0.82 │ breakout │██░░░│ BUY  │ │
│  │🥉 │ 300750  │宁德.. │ 0.79 │ strength │██░░░│  —   │ │
│  └─────────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────┤
│  📈 评分分布（横向柱状图，Top 10-20）                      │
│  ★ 600522 ████████████████████ 0.87                      │
│  ★ 000001 ██████████████████   0.82                      │
│    300750 █████████████████    0.79                      │
└──────────────────────────────────────────────────────────┘
```

### 3.4 Table Columns

| Column | Description |
|--------|-------------|
| Rank | Medal icons for top 3 (🥇🥈🥉) |
| Symbol + Name | Clickable → navigates to `/analyze?symbol=X&strategy=Y` |
| Score | Colored bar: green (>0.8), yellow (>0.6), gray (<0.6) |
| Signal Tag | Badge component (e.g., `momentum_pullback`) |
| Factor Breakdown | Hover tooltip with mini bar chart of all factor scores |
| Buy Signal | Green BUY badge + truncated reason (expandable on click) |
| Key Metrics | close / MA5 / MA20 / volume |
| Action | Link button to Analyze page |

### 3.5 Parameter Editors

**Screener params** use a new `ScreenerParamsEditor` component following the same pattern as the existing `StrategyParamsEditor`. It reads the screener's `param_schema` from `GET /api/screeners` and renders dynamic form fields:

- `float` / `int` → number input
- `bool` → checkbox
- `str` → text input
- Render in a collapsible card below the screener selector

**Strategy params** reuse the existing `StrategyParamsEditor` component.

### 3.6 State Handling

| State | Behavior |
|-------|----------|
| **Initial** | Form ready, date defaults to latest available trading date |
| **Loading** | Skeleton rows for table + skeleton cards for stats; show spinner on submit button |
| **Empty** | "当天没有符合条件的股票" — suggest changing screener/strategy or relaxing params |
| **Error** | Display error message with details (e.g., "日期无数据", "选股器不存在") |
| **Results** | Full table + chart + summary cards |

### 3.7 Component Tree

```
Screener.tsx
├─ PageHero
├─ Form Card
│   ├─ Screener selector (react-select, from available screeners)
│   ├─ Strategy selector (react-select, useCachedStrategies)
│   ├─ DatePicker (input[type=date])
│   ├─ TopN input (number)
│   ├─ Params toggle button
│   ├─ StrategyParamsEditor (collapsible, existing component)
│   └─ Submit button
├─ Summary Cards (4 MetricCards)
├─ Filter bar (buy signal toggle + score threshold slider)
├─ Results Table (sortable)
│   ├─ Score bar component
│   ├─ Factor tooltip component
│   └─ Buy signal badge + reason expand
├─ ECharts horizontal bar chart (score distribution)
└─ Empty / Error / Loading states
```

### 3.8 TypeScript Types

```typescript
// types/index.ts additions

interface ParamSchemaEntry {
  type?: string;
  default?: any;
}

interface ScreenerInfo {
  name: string;
  params: Record<string, any>;
  param_schema: Record<string, ParamSchemaEntry>;
}

interface ScreenRequest {
  screener: string;
  strategy: string;
  date: string;
  top_n?: number;
  screener_params?: Record<string, any>;
  strategy_params?: Record<string, any>;
}

interface FactorBreakdown {
  [factorName: string]: number;
}

interface BuySignalInfo {
  date: string;
  action: "BUY";
  strength: number;
  reason: string;
}

interface KeyMetrics {
  close: number;
  volume: number;
  amount: number;
  [indicator: string]: number;
}

interface ScreenItem {
  symbol: string;
  name: string;
  score: number;
  signal_tag: string;
  factor_breakdown: FactorBreakdown;
  buy_signal: BuySignalInfo | null;
  key_metrics: KeyMetrics;
}

interface ScreenResult {
  date: string;
  screener: string;
  strategy: string;
  universe_size: number;
  candidates: number;
  with_buy_signal: number;
  results: ScreenItem[];
}
```

### 3.9 API Client Addition

```typescript
// api/client.ts
getScreeners: (): Promise<{ screeners: ScreenerInfo[] }> =>
  request('/api/screeners'),

screen: (data: ScreenRequest): Promise<ScreenResult> =>
  request('/api/screen', { method: 'POST', body: JSON.stringify(data) }),
```

### 3.10 Files Changed (Frontend)

| File | Change |
|------|--------|
| `web/src/pages/Screener.tsx` | **New** — main page component |
| `web/src/components/ScreenerParamsEditor.tsx` | **New** — dynamic params form for screeners |
| `web/src/api/client.ts` | Add `getScreeners()` and `screen()` methods |
| `web/src/types/index.ts` | Add `Screen*` types + `ScreenerInfo` |
| `web/src/App.tsx` | Add `/screener` route |
| `web/src/components/Sidebar.tsx` | Add "选股" nav item |

---

## 4. Data Flow

```
┌──────────────┐     POST /api/screen     ┌──────────────┐
│   Frontend   │ ─────────────────────────→│   FastAPI    │
│  Screener.tsx│                           │  server.py   │
│              │←─────────────────────────│              │
│   ScreenResult (JSON)                    │              │
└──────────────┘                           └──────┬───────┘
                                                  │
                                          ┌───────▼───────┐
                                          │  engine.py    │
                                          │  run_screen() │
                                          └───────┬───────┘
                                                  │
                          ┌───────────────────────┼───────────────────────┐
                          │                       │                       │
                  ┌───────▼───────┐     ┌─────────▼────────┐    ┌────────▼────────┐
                  │  DataSource   │     │    Screener      │    │    Strategy     │
                  │  get_bars()   │     │  scan() +        │    │ generate_signals│
                  │               │     │  explain()       │    │                 │
                  └───────────────┘     └──────────────────┘    └─────────────────┘
```

---

## 5. Edge Cases & Error Handling

| Scenario | Handling |
|----------|----------|
| No screener available | API returns 400 with message "选股器不存在: xxx" |
| No strategy available | API returns 400 with message "策略不存在: xxx" |
| Date has no market data | API returns 400 "目标日期无交易数据" |
| Date is in the future | Frontend disables future dates in date picker |
| Zero candidates found | Return empty results with `candidates: 0`; frontend shows empty state |
| Candidates found but zero buy signals | Return all candidates with `buy_signal: null`; `with_buy_signal: 0` |
| Invalid params | API validates types and returns 422 with details |
| Request timeout | Frontend sets reasonable timeout (e.g., 60s); shows timeout error |
| Partial data (some stocks missing bars) | Skip those stocks silently, continue with available data |

---

## 6. Non-Goals (Out of Scope)

- Real-time / streaming results
- Batch running multiple screeners or strategies in one request
- Saving screener results for later review
- Email / notification alerts based on screener results
- Backtesting the screener's historical accuracy (this is portfolio backtest territory)
