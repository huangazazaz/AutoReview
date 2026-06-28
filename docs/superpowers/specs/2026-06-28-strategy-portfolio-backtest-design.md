# Strategy-Driven Portfolio Backtest — Design Spec

**Date**: 2026-06-28
**Status**: Approved
**Branch**: dev/autotrade-mvp

---

## 1. Problem Statement

The existing `PortfolioBacktester` uses a **Screener** for stock selection and a fixed **ExitManager** (trailing stop, hard stop, time stop, signal decay) for exits. Trading strategies (Turtle, MA Cross, etc.) — which generate nuanced BUY/SELL signals — are not utilized in the account/portfolio context. Strategies are only usable in single-stock backtests.

**Goal**: Fuse stock filtering (Screener + AI) with trading strategies, enabling account-level backtesting where:
- **Entry**: Screener selects candidates; Strategy BUY signals confirm timing
- **Exit**: Strategy SELL signals drive exits; ExitManager provides a safety net

---

## 2. Architecture Overview

```
Screener scan → AI filter (optional) → StrategySignalCache (NEW)
                                            │
                                            ▼
                                   PortfolioBacktester (ENHANCED)
                                   ┌──────────────────────────┐
                                   │ Morning:                  │
                                   │  1. Execute pending buys   │
                                   │  2. Check strategy SELL    │ ← NEW
                                   │  3. ExitManager fallback   │
                                   │  4. Record equity          │
                                   │ Evening:                   │
                                   │  5. Detect market regime   │
                                   │  6. Screener ∩ strategy BUY│ ← ENHANCED
                                   │  7. Plan next-day buys     │
                                   └──────────────────────────┘
```

**Key principle**: Strategy is the primary decision-maker for both entry and exit. ExitManager acts only as a safety net (hard stop, trailing stop).

**Backward compatibility**: When no strategy is configured, behavior is identical to current.

---

## 3. Component Changes

### 3.1 NEW: `StrategySignalCache` (`autotrade/core/strategy_signal_cache.py`)

Pre-computes strategy signals for all candidate stocks, providing O(1) date-keyed lookup.

```python
class StrategySignalCache:
    def __init__(self, strategy: Strategy, market_data: dict[str, pd.DataFrame]):
        # For each symbol in market_data:
        #   1. Compute strategy.required_indicators on the DataFrame
        #   2. Call strategy.generate_signals(df)
        #   3. Index signals by (symbol, date):
        #      _buy_dates:  dict[str, set[date]]
        #      _sell_dates: dict[str, set[date]]
        #      _signals:    dict[str, dict[date, list[Signal]]]

    def has_buy(self, symbol: str, d: date, window: int = 1) -> bool:
        """True if a BUY signal exists within ±window days of d."""

    def has_sell(self, symbol: str, d: date, window: int = 0) -> bool:
        """True if a SELL signal exists on exact date d."""

    def get_signals_on(self, symbol: str, d: date) -> list[Signal]:
        """Get all signals for symbol on exact date d."""
```

**Performance**: Only computes for screener-selected symbols (typically 50–200), not the full universe.

**Edge cases**:
- Strategy signals missing `symbol` field → filled from the lookup key
- Empty market data → returns empty cache
- Strategy with no signals → all lookups return False

### 3.2 ENHANCED: `PortfolioBacktestConfig` (`portfolio_backtester.py`)

Add optional fields:

```python
@dataclass
class PortfolioBacktestConfig:
    # ... existing fields unchanged ...
    strategy_name: str | None = None       # NEW: strategy name (None = screener-only)
    strategy_params: dict | None = None    # NEW: strategy parameter overrides
    strategy_buy_window: int = 1           # NEW: ±days for BUY signal matching
```

### 3.3 ENHANCED: `PortfolioBacktester.run()` (`portfolio_backtester.py`)

New optional parameter:

```python
def run(
    self,
    market_data: dict[str, pd.DataFrame],
    screener_results: dict[date, list[tuple[str, float, str]]],
    signal_cache: StrategySignalCache | None = None,  # NEW
) -> PortfolioBacktestResult:
```

**Morning — exit logic change** (inserted before ExitManager check):

```python
# NEW: Check strategy SELL signals first
if signal_cache is not None:
    if signal_cache.has_sell(symbol, today):
        self._execute_sell(account, pos, price, today, ["strategy_sell"])
        continue  # skip ExitManager for this position

# EXISTING: ExitManager fallback check
triggers = self.exit_manager.check(pos, price, today, ...)
if triggers:
    self._execute_sell(account, pos, price, today, triggers)
```

**Evening — entry logic change** (in candidate filtering):

```python
# EXISTING: filter out already-held
available = [(s, sc, t) for s, sc, t in today_candidates if s not in held]

# NEW: filter to strategy-confirmed (when signal_cache provided)
if signal_cache is not None:
    window = self.config.strategy_buy_window
    available = [
        (s, sc, t) for s, sc, t in available
        if signal_cache.has_buy(s, today, window=window)
    ]

# EXISTING: take top picks
picks = available[:slots]
```

### 3.4 ENHANCED: `PortfolioTrade` (`account.py`)

Add trigger field:

```python
@dataclass
class PortfolioTrade:
    # ... existing fields ...
    trigger: str = ""  # NEW: "strategy_buy" | "strategy_sell" | "trailing_stop" | ...
```

All `_execute_sell` calls pass trigger info. `_execute_buy` records trigger.

### 3.5 ENHANCED: `run_portfolio_backtest()` (`engine.py`)

New parameters:

```python
def run_portfolio_backtest(
    screener_name: str = "momentum_screener",
    strategy_name: str | None = None,       # NEW
    strategy_params: dict | None = None,    # NEW
    strategy_buy_window: int = 1,           # NEW
    ...
):
```

Logic addition after AI filter step:

```python
# NEW: Build strategy and signal cache if strategy_name is set
signal_cache = None
if strategy_name:
    strategy_cls = get_strategy(strategy_name)
    strategy = _instantiate_strategy(strategy_cls, strategy_params)
    signal_cache = StrategySignalCache(strategy, market_data)
    logger.info("Strategy signal cache built for %s: %d stocks",
                strategy_name, len(signal_cache))

# Pass signal_cache to backtester
result = backtester.run(market_data, selection, signal_cache=signal_cache)
```

### 3.6 ENHANCED: CLI (`triggers/cli.py`)

New `portfolio-backtest` command options:

```
--strategy TEXT         Strategy name (e.g., turtle, ma_cross)
--strategy-params JSON  Strategy parameter overrides as JSON string
```

### 3.7 ENHANCED: Reporters

- **Console reporter**: Display `trigger` column in trade table
- **Plot reporter**: Color-code trades by trigger type in equity curve annotations
- **Trade CSV export**: Include `trigger` column

### 3.8 ENHANCED: Config (`config/backtest/portfolio.yaml`)

New optional fields:

```yaml
portfolio_backtest:
  # ... existing fields ...

  strategy: "turtle"              # NEW (optional)
  strategy_params:                # NEW (optional)
    use_system1: true
    use_system2: true
    allow_long: true
    allow_short: false
  strategy_buy_window: 1          # NEW (optional, default 1)
```

---

## 4. Trigger Values

| Trigger | Meaning |
|---|---|
| `strategy_buy` | Strategy BUY signal confirmed entry |
| `screener` | Screener-only mode entry (no strategy configured) |
| `strategy_sell` | Strategy SELL signal triggered exit |
| `trailing_stop` | ExitManager trailing stop |
| `hard_stop` | ExitManager hard stop |
| `time_stop` | ExitManager time stop |
| `signal_decay` | ExitManager signal decay |
| `end_of_period` | Force-close at backtest end |

---

## 5. Error Handling

| Scenario | Behavior |
|---|---|
| Strategy not found in registry | Return error, log warning |
| Strategy has no required_indicators | Work fine (no indicator columns needed) |
| Strategy generates no signals | SignalCache returns False for all lookups; backtest runs screener-only |
| SignalCache construction fails | Log error, fall back to screener-only mode |
| Market data missing for a symbol | Skip that symbol in cache construction |

---

## 6. Testing Plan

### Unit Tests (`test_strategy_signal_cache.py`)
- BUY/SELL signals correctly indexed by date
- `has_buy()` with window: matches exact, ±1, outside window
- `has_sell()` exact-date matching
- Empty market data → no errors
- Strategy with no indicators → works

### Unit Tests (`test_portfolio_backtester_strategy.py`)
- Strategy BUY signal confirms screener candidate → position opened
- No strategy BUY signal → candidate skipped
- Strategy SELL → position closed with trigger="strategy_sell"
- ExitManager fallback: works when strategy has no SELL signal
- Both signals on same day: SELL processed before BUY (existing order)

### Integration Tests
- End-to-end: momentum_screener + turtle strategy backtest
- Verify trades are produced with correct trigger values
- Verify equity curve is non-empty
- Regression: screener-only mode produces identical results as before

---

## 7. Files Changed Summary

| File | Change |
|---|---|
| `autotrade/core/strategy_signal_cache.py` | **NEW** — signal pre-computation and lookup |
| `autotrade/core/portfolio_backtester.py` | ENHANCE — config + run() with strategy signals |
| `autotrade/core/account.py` | ENHANCE — PortfolioTrade.trigger field |
| `autotrade/core/engine.py` | ENHANCE — run_portfolio_backtest() params |
| `autotrade/triggers/cli.py` | ENHANCE — new CLI options |
| `autotrade/reporters/console.py` | ENHANCE — trigger column in output |
| `autotrade/reporters/plot_reporter.py` | ENHANCE — trigger-aware charting |
| `config/backtest/portfolio.yaml` | ENHANCE — strategy fields |
| `tests/unit/test_strategy_signal_cache.py` | **NEW** |
| `tests/unit/test_portfolio_backtester_strategy.py` | **NEW** |
| `tests/integration/test_portfolio_backtest.py` | ENHANCE — strategy-driven cases |
