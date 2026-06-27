# Portfolio Backtest Engine — Design Spec

**Date**: 2026-06-27  
**Status**: Draft  
**Branch**: dev/autotrade-mvp

---

## 1. Motivation

The current backtesting system (`Backtester`) operates on single stocks independently — each stock runs through a strategy and is evaluated in isolation. The screener-based workflow (`run_screener_backtest()`) also backtests each screened stock independently, then aggregates results. Neither simulates a real portfolio where multiple positions coexist, share a common capital pool, and compete for allocation.

This spec defines a **Portfolio Backtest Engine** that:
- Manages a single account with shared capital across multiple simultaneous positions
- Uses screened candidates daily, allocates capital by signal strength
- Manages exits via unified risk rules independent of individual strategies
- Produces a realistic equity curve from 3 years of daily A-share data

---

## 2. Goals

1. **Portfolio-level simulation**: single account, multiple concurrent positions, shared cash pool
2. **Signal-strength allocation**: stronger screener scores → larger position size
3. **Dynamic position sizing**: market regime (derived from screener output breadth) controls max positions (1–3)
4. **Unified exit framework**: mobile stop-loss, time stop, hard stop, signal decay — configurable, decoupled from entry
5. **A-share rules compliance**: T+1, lot size 100, stamp duty on sells, commission
6. **Start-to-end equity curve**: daily NAV from 2023-06-27 to 2026-06-18

---

## 3. Non-Goals

- Live trading integration (paper or real)
- Intraday data / minute bars
- Short selling / margin
- Multi-strategy or multi-screener blending (v1 uses one screener)
- Risk-parity, Kelly criterion, or volatility-targeted sizing (v1 uses simple strength-weighting)

---

## 4. Architecture

### 4.1 Component Diagram

```
config/backtest/portfolio.yaml
       │
       ▼
engine.run_portfolio_backtest()
       │
       ├──► DataSource (failover chain)
       │       └──► {symbol: pd.DataFrame}  (market data cache)
       │
       ├──► Screener.scan(market_data, dates)
       │       └──► {date: [(symbol, score, tag), ...]}
       │
       ├──► MarketRegime.detect(daily_candidates)
       │       └──► int  (max_positions: 1|2|3)
       │
       ├──► ExitManager.check(portfolio, market_data, screener_snapshot)
       │       └──► list[sell_orders]
       │
       └──► PortfolioBacktester.run(candidates, market_data)
               │
               ├──► Account (cash, positions, equity history)
               ├──► OrderExecutor (T+1, lot rounding, commission)
               └──► Result (trades, equity_curve, metrics)
```

### 4.2 New Files

| File | Purpose |
|------|---------|
| `autotrade/core/portfolio_backtester.py` | Core loop: daily iteration, order matching, equity tracking |
| `autotrade/core/account.py` | Account state: cash, positions dict, equity curve |
| `autotrade/core/market_regime.py` | Market breadth → max positions mapping |
| `autotrade/core/exit_manager.py` | Unified exit rules (trailing stop, time stop, hard stop, signal decay) |
| `config/backtest/portfolio.yaml` | All configurable parameters |
| `scripts/run_portfolio_backtest.py` | Standalone execution script |
| `tests/unit/test_portfolio_backtester.py` | Unit tests |

### 4.3 Modified Files

| File | Change |
|------|--------|
| `autotrade/core/engine.py` | Add `run_portfolio_backtest()` method |
| `autotrade/triggers/cli.py` | Add `portfolio-backtest` CLI command |

---

## 5. Data Flow (Per Trading Day)

```
Precompute: run Screener.scan() once for all dates → screener_results: dict[date, candidates]
             (all screener results known upfront for signal_decay lookups)

For each trading day D in [2023-06-27, 2026-06-18]:

  ── MORNING (at D's open price) ──
  
  1. EXECUTE PENDING BUYS (planned on D-1):
     For each buy planned yesterday:
       Fill at D's open price (with slippage: open * 1.001)
       Deduct cash, create position, record trade
       Mark position as T+1 locked (can't sell until D+1)

  2. CHECK EXITS (unlocked positions only):
     For each position P not locked by T+1:
       Check ExitManager rules using D's open price and screener_results[D-1]:
         - trailing_stop:   (high_since_entry - open) / high_since_entry > drawdown_pct
         - time_stop:       days_held >= max_days AND pnl_pct < min_return
         - hard_stop:       (open - entry_price) / entry_price < -loss_pct
         - signal_decay:    symbol not in screener_results[D-1] top-K
       If any rule triggers → SELL at D's open (with slippage: open * 0.999)
       Deduct stamp duty, update cash, remove position, record trade

  3. RECORD EQUITY:
     equity = cash + sum(position.quantity * D_open for each position)
     Append (D, equity) to equity_curve

  ── EVENING (after D's close) ──

  4. DETECT REGIME:
     MarketRegime.detect(screener_results[D]) → max_positions (1|2|3)

  5. PLAN BUYS (execute tomorrow at D+1 open):
     slots = max_positions - len(positions)
     If slots > 0:
       Filter screener_results[D]: exclude already-held symbols
       Pick top 'slots' candidates by score
       Allocate cash by signal-strength weight (see §6.6)
       Store pending buys for execution on D+1
```

### 5.1 Look-Ahead Prevention

| Action | Data Used | Execution Price | Why Safe |
|--------|-----------|-----------------|----------|
| Exit checks on D | Screener from D-1, price data through D-1 | D's open | All inputs known before D's open |
| Screener on D | D's close (OHLCV for day D) | — (info only) | Uses same-day close after it forms |
| Buys planned on D | Screener from D | D+1's open | Screener uses D's close, not D+1's |
| Buys executed on D+1 | Plan from D | D+1's open | Plan was frozen before D+1 open known |

The key invariant: **no decision on day D uses any data from day D's future**. The screener runs on D's close to plan D+1's buys — the screener never sees D+1's open before committing.

### 5.2 Cash Buffer

A configurable fraction (default 5%) of available cash is reserved:
- Prevents zero-cash edge cases from lot rounding
- Simulates real-world caution
- `available_for_buy = cash * (1 - cash_buffer)`

---

## 6. Component Details

### 6.1 Account (`account.py`)

```python
@dataclass
class Account:
    initial_capital: float
    cash: float
    positions: dict[str, Position]       # symbol → Position
    equity_curve: list[tuple[date, float]]  # (date, total_equity)
    trades: list[Trade]

    def equity(self, prices: dict[str, float]) -> float:
        """cash + mark-to-market position value"""
```

- `Position` tracks: symbol, entry_date, entry_price, quantity, highest_close_since_entry, days_held
- `Trade` records: symbol, buy_date, sell_date, buy_price, sell_price, quantity, pnl, pnl_pct

### 6.2 ExitManager (`exit_manager.py`)

Configurable rules, all keyed off `config/backtest/portfolio.yaml`:

```yaml
exit_rules:
  trailing_stop:
    enabled: true
    drawdown_pct: 0.08       # sell when drop 8% from position high
  time_stop:
    enabled: true
    max_holding_days: 20     # sell after 20 days
    min_return_pct: 0.0      # …if return is below this
  hard_stop:
    enabled: true
    loss_pct: 0.05           # sell when loss exceeds 5%
  signal_decay:
    enabled: true
    rank_threshold: 50       # sell when stock falls out of screener top-50
```

Each rule returns `(should_sell: bool, reason: str)`. Any rule can trigger a sell.

### 6.3 MarketRegime (`market_regime.py`)

Computes market breadth from screener output:

```python
def detect(self, candidates: list[tuple[str, float, str]]) -> int:
    """
    candidates: [(symbol, score, tag), ...] sorted by score desc
    Returns: max_positions (1|2|3)
    """
    if not candidates:
        return 0  # no positions

    # Use average score of candidates above threshold
    valid = [s for _, s, _ in candidates if s >= self.score_threshold]
    avg_score = sum(valid) / len(valid) if valid else 0.0

    if avg_score >= self.bullish_threshold:
        return 3
    elif avg_score >= self.neutral_threshold:
        return 2
    else:
        return 1
```

Configurable thresholds in `portfolio.yaml`:

```yaml
market_regime:
  score_threshold: 0.3       # minimum score to count as "valid"
  bullish_threshold: 0.6     # avg_score >= 0.6 → 3 positions
  neutral_threshold: 0.4     # avg_score >= 0.4 → 2 positions
  # else → 1 position
```

### 6.4 PortfolioBacktester (`portfolio_backtester.py`)

The main loop orchestrator. Key design decisions:

- **Preload all market data** into memory (dict of DataFrames) for fast daily access — same as current `_load_market_data()`
- **Precompute all screener results** for the full date range before the simulation loop — enables signal_decay checks without rerunning
- **Daily iteration** over sorted unique trading dates from the market data
- **Output**: `PortfolioBacktestResult` with `equity_curve` (pd.Series), `trades` (list[Trade]), `metrics` (dict)

### 6.5 Commission & Costs

Reuse existing logic from `Backtester._get_fill_price()` and commission calculations:
- Commission: `max(amount * 0.0003, 5.0)` per trade
- Stamp duty: `amount * 0.001` on sells only
- Slippage: buy at `price * 1.001`, sell at `price * 0.999`
- Lot size: 100 shares, quantity always rounded down to nearest lot

### 6.6 Allocation Algorithm

```
Given: cash C, picks [(s1, score1), (s2, score2), ...], cash_buffer B

1. available = C * (1 - B)
2. total_score = sum(score_i for all picks)
3. For each pick i:
     weight_i = score_i / total_score
     allocated_i = available * weight_i
     quantity_i = floor(allocated_i / (price_i * 1.001) / 100) * 100
     cost_i = quantity_i * price_i * 1.001 + commission
     cash -= cost_i
```

If allocated amount cannot buy even 1 lot → skip that pick, redistribute.

---

## 7. Configuration

### `config/backtest/portfolio.yaml`

```yaml
portfolio_backtest:
  # Time range
  start_date: "2023-06-27"
  end_date: "2026-06-18"

  # Capital
  initial_capital: 1_000_000.0
  cash_buffer: 0.05              # reserve 5% cash

  # Screener
  screener: "momentum_screener"  # which screener to use
  screener_params: {}            # override screener config (optional)
  top_n_candidates: 50           # how many candidates to consider daily (must be >= signal_decay.rank_threshold)

  # Market regime
  market_regime:
    score_threshold: 0.3
    bullish_threshold: 0.6
    neutral_threshold: 0.4

  # Exit rules
  exit_rules:
    trailing_stop:
      enabled: true
      drawdown_pct: 0.08
    time_stop:
      enabled: true
      max_holding_days: 20
      min_return_pct: 0.0
    hard_stop:
      enabled: true
      loss_pct: 0.05
    signal_decay:
      enabled: true
      rank_threshold: 50

  # Execution
  fill_price: "next_open"
  commission_rate: 0.0003
  stamp_duty_rate: 0.001
  slippage: 0.001
  min_commission: 5.0
  lot_size: 100
  allow_t_plus_1: true

  # Output
  output_dir: "data/results"
  output_prefix: "portfolio_backtest"
```

---

## 8. Output Format

### 8.1 Console Output (via ConsoleReporter)

- Summary table: total return, annualized return, max drawdown, Sharpe ratio, win rate, total trades
- Equity curve chart (matplotlib)

### 8.2 File Output

```
data/results/portfolio_backtest_YYYYMMDD_HHMMSS/
  ├── equity_curve.csv        # date, equity
  ├── trades.csv              # all trades with P&L
  ├── daily_positions.csv     # end-of-day holdings
  ├── equity_curve.png        # chart
  └── summary.json            # metrics dict
```

---

## 9. Testing Strategy

### Unit Tests (`tests/unit/test_portfolio_backtester.py`)

| # | Test | What it validates |
|---|------|-------------------|
| 1 | `test_empty_candidates_no_trades` | No screener candidates → no positions opened |
| 2 | `test_single_buy_creates_position` | One candidate → one position with correct quantity |
| 3 | `test_strength_weighted_allocation` | Higher score → more capital allocated |
| 4 | `test_lot_rounding` | Quantities always multiples of 100 |
| 5 | `test_t_plus_1_prevents_same_day_sell` | Position opened today can't be sold today |
| 6 | `test_commission_and_stamp_duty` | Costs correctly deducted |
| 7 | `test_trailing_stop_triggers` | 8% drawdown from high triggers sell |
| 8 | `test_hard_stop_triggers` | 5% loss triggers sell |
| 9 | `test_time_stop_triggers` | 20 days holding + flat return triggers sell |
| 10 | `test_signal_decay_triggers` | Stock falling out of top-50 triggers sell |
| 11 | `test_max_positions_enforced` | Never exceeds market_regime limit |
| 12 | `test_cash_buffer_respected` | Cash buffer always maintained |
| 13 | `test_equity_curve_tracks_daily` | Equity recorded every trading day |
| 14 | `test_bullish_regime_3_positions` | High avg_score → 3 positions |
| 15 | `test_bearish_regime_1_position` | Low avg_score → 1 position |
| 16 | `test_regime_zero_when_no_candidates` | No candidates → 0 positions |
| 17 | `test_sell_frees_cash_for_rebuy` | After sell, cash available for new buys |

### Integration Test

- Run a 1-month backtest with real parquet data and MomentumScreener, verify:
  - Equity curve is non-degenerate
  - Trades exist and have valid P&L
  - No look-ahead (entry dates strictly after screener dates)

---

## 10. Edge Cases

| Edge Case | Handling |
|-----------|----------|
| No screener candidates on a day | Skip buys, just check exits |
| Candidate already held | Skip (don't double-buy), try next candidate |
| Cash too low for any lot | Skip all buys for that day |
| Stock suspended / no data | Skip that stock in screener, mark position for forced exit at last close |
| Position at end date | Force-close at last available close price, include in final equity |
| Insufficient history for screener | Exclude stock from universe |
| All exits trigger same day | Sell all, become all-cash, wait for next buy day |

---

## 11. Implementation Order

1. **`account.py`** — Account dataclass with equity tracking
2. **`market_regime.py`** — Market breadth → position count
3. **`exit_manager.py`** — Unified exit rules
4. **`portfolio_backtester.py`** — Main loop integrating all components
5. **`config/backtest/portfolio.yaml`** — Configuration
6. **`engine.py` modification** — `run_portfolio_backtest()` entry point
7. **`scripts/run_portfolio_backtest.py`** — Standalone runner
8. **`cli.py` modification** — CLI command
9. **Unit tests** — All 17 tests
10. **Integration test** — 1-month real data run

---

## 12. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Memory pressure loading 5000+ stock DataFrames | Already handled — existing `_load_market_data()` uses this pattern; 5K stocks × 750 days × OHLCV ≈ 500 MB, manageable |
| Screener runtime for 5000 stocks daily | MomentumScreener is vectorized (pandas ops); pre-filters reduce effective set to ~200–500 stocks. 750 days × 500 stocks × 7 factors ≈ minutes, not hours |
| Position sizing edge cases with very small cash | Cash buffer (5%) + lot rounding guard (skip if < 1 lot) |
| T+1 lock and signal_decay conflict | Signal decay only checked for unlocked positions (held ≥ 1 day) |
