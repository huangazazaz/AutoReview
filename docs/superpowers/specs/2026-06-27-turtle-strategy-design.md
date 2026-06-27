# Turtle Trading Strategy + Bidirectional Backtester — Design Spec

**Date**: 2026-06-27  
**Status**: Draft  
**Branch**: dev/autotrade-mvp

---

## 1. Motivation

The current backtesting system (`Backtester`) only supports long-only trading. While this covers most A-share retail scenarios, it limits the strategy space — trend-following strategies like Turtle can also profit from downtrends through short selling. Additionally, the classic Turtle Trading Strategy is a landmark in systematic trading history and serves as an excellent benchmark for evaluating other strategies.

This spec defines:
1. **Bidirectional backtester extension** — adds short selling support to the existing single-stock `Backtester`
2. **Turtle Trading Strategy** — a faithful implementation of the original Turtle rules
3. **ATR indicator** — prerequisite for volatility-normalized position sizing

---

## 2. Goals

1. **Short selling in backtester**: `SELL_SHORT` opens short position, `BUY_TO_COVER` closes it; margin tracking and borrowing costs
2. **Turtle System 1 & 2**: both breakout systems run simultaneously, configurable on/off
3. **Bidirectional signals**: the strategy generates long and short entries independently
4. **ATR-based pyramiding**: add units every 0.5N (not fixed percentage)
5. **2N hard stop**: dynamic stop-loss based on last entry price, adjusted per pyramid add
6. **Code quality**: refactor `backtester.py` — extract signal handlers, unify position management, vectorize metrics

---

## 3. Non-Goals

- Portfolio-level short selling (only single-stock backtester extended, portfolio backtester stays long-only for now)
- Real-time margin call simulation (margin checked daily at close only)
- Securities lending availability filter (assume all stocks are shortable in backtest)
- Intraday data support
- Live trading integration

---

## 4. Architecture

### 4.1 Component Diagram

```
config/strategies/turtle.yaml
       │
       ▼
TurtleTraderStrategy.generate_signals(df)
       │
       ├──► ATR(20).compute(df)        → ind_atr_20 column (N value)
       ├──► Rolling 20/55-day high/low  → breakout levels
       ├──► State machine (daily loop)  → entry / pyramid / stop / exit
       └──► list[Signal]                → BUY | SELL | SELL_SHORT | BUY_TO_COVER
                    │
                    ▼
Backtester.run(signals, bars)
       │
       ├──► _handle_buy()          → increase long_qty
       ├──► _handle_sell()         → decrease long_qty
       ├──► _handle_short()        → increase short_qty (margin check)
       ├──► _handle_cover()        → decrease short_qty
       ├──► _update_equity()       → long_value - short_value + cash
       └──► _compute_metrics()     → vectorized return/drawdown/sharpe
```

### 4.2 Files Changed / Added

| File | Action | Purpose |
|------|--------|---------|
| `autotrade/indicators/atr.py` | **New** | ATR indicator (N-value) |
| `autotrade/strategies/turtle.py` | **New** | TurtleTraderStrategy with dual-system, bidirectional signals |
| `config/strategies/turtle.yaml` | **New** | Turtle strategy parameters |
| `autotrade/core/models.py` | **Modify** | Extend Signal.action, Trade.action; new Position fields; BacktestConfig short fields |
| `autotrade/core/backtester.py` | **Refactor** | Extract 4 signal handlers; add short support; vectorize metrics |
| `config/settings.yaml` | **Modify** | Add default short-related config keys |
| `tests/unit/test_atr_indicator.py` | **New** | ATR calculation tests |
| `tests/unit/test_turtle_strategy.py` | **New** | Turtle signal generation tests |
| `tests/unit/test_backtester_short.py` | **New** | Short selling backtester tests |

---

## 5. Detailed Design

### 5.1 ATR Indicator (`autotrade/indicators/atr.py`)

Uses `pandas_ta.atr()` under the hood. Output column: `ind_atr_{period}`.

```python
class ATR(Indicator):
    name = "atr"
    params = {"period": 20}

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        col = f"ind_atr_{self.period}"
        df[col] = ta.atr(df["high"], df["low"], df["close"], length=self.period)
        return df
```

Note: `pandas_ta.atr()` uses Wilder's smoothing (EMA with alpha=1/period), matching the original Turtle N-value specification exactly.

### 5.2 Model Extensions (`autotrade/core/models.py`)

#### Signal

```python
action: str  # "BUY" | "SELL" | "SELL_SHORT" | "BUY_TO_COVER"
```

#### Trade

```python
action: str  # "BUY" | "SELL" | "SELL_SHORT" | "BUY_TO_COVER"
```

#### Position (rewritten)

```python
@dataclass
class Position:
    symbol: str
    long_qty: int = 0
    long_avg_cost: float = 0.0
    short_qty: int = 0
    short_avg_cost: float = 0.0

    @property
    def net_qty(self) -> int:
        return self.long_qty - self.short_qty
```

Remove old `quantity`, `avg_cost`, `market_value` fields (computed on the fly).

#### BacktestConfig (new fields)

```python
allow_short: bool = False
short_margin_ratio: float = 1.0      # 融券保证金比例
short_interest_rate: float = 0.085   # 融券年化利率 8.5%
```

### 5.3 Backtester Refactoring (`autotrade/core/backtester.py`)

#### 5.3.1 Method Extraction

Current `run()` is ~160 lines of monolithic loop. Refactored into:

| Method | Responsibility |
|--------|---------------|
| `run()` | Orchestration: build signal_map, daily loop, return result |
| `_get_fill_price()` | (existing, unchanged) |
| `_handle_buy(sig, bar, ...)` | Open/add long: compute quantity, execute, update long_avg_cost |
| `_handle_sell(sig, bar, ...)` | Close/reduce long: compute quantity, execute, update long_avg_cost |
| `_handle_short(sig, bar, ...)` | Open/add short: margin check, execute, update short_avg_cost |
| `_handle_cover(sig, bar, ...)` | Close/reduce short: execute, update short_avg_cost |
| `_execute_trade(action, price, qty, ...)` | Unified trade execution: commission, stamp duty, lot rounding |
| `_compute_buy_quantity()` | (existing, unchanged) |
| `_compute_sell_quantity()` | Extended for short covering |
| `_update_equity(bar)` | Compute long_value - short_value + cash, append to equity_series |
| `_compute_metrics()` | Vectorized using numpy, handles both long and short trades |

#### 5.3.2 Daily Loop Logic

```python
for bar in bars_sorted:
    daily_signals = signal_map.get(today, [])

    # Phase 1: EXITS first (free up cash/margin)
    for sig in daily_signals:
        if sig.action == "SELL":
            self._handle_sell(sig, bar, ...)
        elif sig.action == "BUY_TO_COVER":
            self._handle_cover(sig, bar, ...)

    # Phase 2: ENTRIES after exits
    for sig in daily_signals:
        if sig.action == "BUY":
            self._handle_buy(sig, bar, ...)
        elif sig.action == "SELL_SHORT" and self.config.allow_short:
            self._handle_short(sig, bar, ...)

    # Phase 3: Mark to market
    self._update_equity(bar)
```

#### 5.3.3 Short Selling Mechanics

```python
def _handle_short(self, sig, bar, ...):
    # 1. Available margin = cash - existing_short_value * (1 + margin_ratio)
    # 2. New short position value = quantity * price
    # 3. Required margin = new_short_value * (1 + margin_ratio)
    # 4. Check: available >= required
    # 5. Execute: cash += new_short_value (proceeds), but margin is locked
    # 6. Track short_qty, short_avg_cost
```

For margin tracking, track `locked_margin` separately:
```python
locked_margin = short_qty * short_avg_cost * (1 + short_margin_ratio)
available_cash = cash - locked_margin
```

#### 5.3.4 Short Covering P&L

```python
# Covering profit = (short_avg_cost - cover_price) * cover_qty
# (profit when price drops below short entry)
cover_profit = (position.short_avg_cost - fill_price) * quantity
```

#### 5.3.5 Vectorized Metrics

Replace the loop-based `_split_cycles()` with numpy operations:

```python
def _compute_metrics(self, trades, equity_series, dates):
    equity_arr = np.array(equity_series)
    
    # Returns
    returns = np.diff(equity_arr) / equity_arr[:-1]
    
    # Max drawdown (vectorized)
    peak = np.maximum.accumulate(equity_arr)
    drawdown = (equity_arr - peak) / peak
    max_dd = np.min(drawdown)
    
    # Sharpe (annualized)
    sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
    
    # Win rate by trade cycle
    # ... (keeps cycle-splitting but uses faster numpy for computation)
```

### 5.4 Turtle Strategy (`autotrade/strategies/turtle.py`)

#### 5.4.1 Class Definition

```python
class TurtleTraderStrategy(Strategy):
    name = "turtle"
    required_indicators = [ATR(period=20)]

    def __init__(
        self,
        # System config
        system1_entry: int = 20,
        system1_exit: int = 10,
        system2_entry: int = 55,
        system2_exit: int = 20,
        use_system1: bool = True,
        use_system2: bool = True,
        # Volatility
        atr_period: int = 20,
        # Position
        account_risk_pct: float = 0.01,
        max_units: int = 4,
        # Pyramiding
        pyramid_atr_mult: float = 0.5,
        # Stop loss
        stop_atr_mult: float = 2.0,
        # Direction
        allow_long: bool = True,
        allow_short: bool = True,
        # System 1 filter
        skip_if_last_win_sys1: bool = True,
    ):
        ...
```

#### 5.4.2 State Machine (per system, per direction)

The strategy maintains 4 independent state trackers:

```python
# long_state["sys1"] = {"entry_price": float|None, "units": int, "last_add_price": float|None, "last_trade_win": bool}
# long_state["sys2"] = {...}
# short_state["sys1"] = {...}
# short_state["sys2"] = {...}
```

#### 5.4.3 Signal Generation Flow (daily)

```
For each day:
  N = df["ind_atr_20"].iloc[idx]
  
  For each enabled system (sys1, sys2):
    entry_period, exit_period = (20, 10) for sys1 or (55, 20) for sys2
    
    # --- LONG ---
    if allow_long and not in_long_position:
      if price > DONCHIAN_HIGH(entry_period):
        if not (system == sys1 and skip_if_last_win_sys1 and last_trade_win):
          → BUY signal, strength = account_risk_pct
    
    if in_long_position:
      if price > last_add_price + pyramid_atr_mult * N and units < max_units:
        → BUY signal (pyramid add)
      if price < last_entry_price - stop_atr_mult * N:
        → SELL signal (stop loss, all units)
      if price < DONCHIAN_LOW(exit_period):
        → SELL signal (exit, all units)
    
    # --- SHORT (mirror logic) ---
    if allow_short and not in_short_position:
      if price < DONCHIAN_LOW(entry_period):
        → SELL_SHORT signal
    
    if in_short_position:
      if price < last_add_price - pyramid_atr_mult * N and units < max_units:
        → SELL_SHORT signal (pyramid add)
      if price > last_entry_price + stop_atr_mult * N:
        → BUY_TO_COVER signal (stop loss)
      if price > DONCHIAN_HIGH(exit_period):
        → BUY_TO_COVER signal (exit)
```

#### 5.4.4 Donchian Channel Computation

```python
# Rolling N-period high (excluding current day, using shift(1))
df["donchian_high_20"] = df["high"].shift(1).rolling(20).max()
df["donchian_low_20"] = df["low"].shift(1).rolling(20).min()
df["donchian_high_55"] = df["high"].shift(1).rolling(55).max()
df["donchian_low_55"] = df["low"].shift(1).rolling(55).min()
df["donchian_high_10"] = df["high"].shift(1).rolling(10).max()
df["donchian_low_10"] = df["low"].shift(1).rolling(10).min()
```

Uses `shift(1)` to avoid look-ahead bias (today's breakout must be based on yesterday's channel).

#### 5.4.5 Strength Calculation

```python
# Turtle Unit = (Account * 1%) / (N * point_value)
# For A-shares, point_value = 1
# Since backtester uses strength as fraction of cash:
#   quantity = cash * strength / price
#   Turtle quantity = Account * 0.01 / N
#   → strength = 0.01 * price / N  (when cash ≈ account)

def _compute_unit_strength(self, price, N):
    """Return strength value for 1 Turtle unit."""
    return self.account_risk_pct * price / N
```

### 5.5 Config (`config/strategies/turtle.yaml`)

```yaml
strategy: turtle
params:
  # ---- 系统参数 ----
  system1_entry: 20
  system1_exit: 10
  system2_entry: 55
  system2_exit: 20
  use_system1: true
  use_system2: true

  # ---- 波动率 ----
  atr_period: 20

  # ---- 仓位 ----
  account_risk_pct: 0.01
  max_units: 4

  # ---- 加仓 ----
  pyramid_atr_mult: 0.5

  # ---- 止损 ----
  stop_atr_mult: 2.0

  # ---- 方向 ----
  allow_long: true
  allow_short: true

  # ---- 系统一过滤器 ----
  skip_if_last_win_sys1: true
```

---

## 6. Backward Compatibility

| Change | Impact |
|--------|--------|
| `Signal.action` new values | Existing strategies only use `BUY`/`SELL` → no impact |
| `Trade.action` new values | Reporters iterate over trades → may need update if they switch on action |
| `Position` fields changed | `Backtester` internal — no external API impact |
| `BacktestConfig` new fields | All have defaults (`allow_short=False`) → no impact |
| `Backtester` refactor | Same public API (`run(signals, bars) → BacktestResult`) → no impact |

---

## 7. Testing Strategy

### Unit Tests

| Test | Validates |
|------|-----------|
| `test_atr_computation` | ATR matches pandas_ta reference output |
| `test_turtle_entry_sys1_long` | 20-day high breakout generates BUY |
| `test_turtle_entry_sys2_long` | 55-day high breakout generates BUY |
| `test_turtle_entry_sys1_short` | 20-day low breakdown generates SELL_SHORT |
| `test_turtle_pyramiding_long` | 0.5N move triggers additional BUY, up to 4 units |
| `test_turtle_stop_loss_long` | 2N move against position triggers SELL all |
| `test_turtle_stop_loss_pyramid_adjust` | Stop moves 0.5N after each pyramid add |
| `test_turtle_exit_sys1` | 10-day low breakdown triggers SELL |
| `test_turtle_exit_sys2` | 20-day low breakdown triggers SELL |
| `test_turtle_skip_last_win_sys1` | System 1 entry skipped after profitable trade |
| `test_turtle_dual_system` | Both systems generate signals independently |
| `test_backtester_buy` | Long entry: quantity, commission, T+1 |
| `test_backtester_sell` | Long exit: P&L, stamp duty |
| `test_backtester_short` | Short entry: margin check, proceeds |
| `test_backtester_cover` | Short exit: P&L calculation (profit on drop) |
| `test_backtester_margin_insufficient` | Short order rejected when margin insufficient |
| `test_backtester_long_and_short` | Simultaneous long + short positions |

### Integration Tests

| Test | Validates |
|------|-----------|
| `test_turtle_backtest_long_only` | Full run: Turtle strategy → Backtester → metrics |
| `test_turtle_backtest_long_short` | Full run with bidirectional trading |
| `test_turtle_vs_buy_and_hold` | Turtle strategy on known trending stock outperforms in drawdown |

---

## 8. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| ATR indicator name collision | Use `ind_atr_{period}` naming convention (same as all other indicators) |
| Turtle unit strength > 1.0 for low-N stocks | Clamp strength to `min(max_units * account_risk_pct, 1.0)` |
| Short margin model too simplistic | Document as simplified model; real margin rules are exchange-specific and complex |
| Existing reporters break on new Trade.action | Add defensive defaults in reporters (treat unknown action as SELL for reporting) |
| Performance regression from refactor | Profile before/after; vectorized metrics should be faster than loop-based |
