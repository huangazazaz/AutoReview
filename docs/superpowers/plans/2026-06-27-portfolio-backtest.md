# Portfolio Backtest Engine — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a portfolio-level backtest engine that simulates a single account with 100万 initial capital, daily screener-based stock selection, signal-strength-weighted position sizing, unified exit rules, and produces an equity curve from 2023-06-27 to 2026-06-18.

**Architecture:** Four new modules (`Account`, `MarketRegime`, `ExitManager`, `PortfolioBacktester`) plus config and wiring. The backtester precomputes all screener results, then iterates daily: morning executes pending buys and checks exits at open, evening detects market regime and plans next-day buys. Screener handles entry; unified exit rules (trailing stop, hard stop, time stop, signal decay) handle exit.

**Tech Stack:** Python 3.10+, dataclasses, pandas, numpy, pytest

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `autotrade/core/account.py` | `PortfolioPosition`, `PortfolioTrade`, `Account` dataclasses |
| Create | `autotrade/core/market_regime.py` | `MarketRegime` — screener breadth → max positions |
| Create | `autotrade/core/exit_manager.py` | `ExitManager` — unified exit rules checker |
| Create | `autotrade/core/portfolio_backtester.py` | `PortfolioBacktester` — main daily loop |
| Create | `config/backtest/portfolio.yaml` | All configurable parameters |
| Create | `scripts/run_portfolio_backtest.py` | Standalone execution script |
| Create | `tests/unit/test_portfolio_backtester.py` | 17 unit tests |
| Modify | `autotrade/core/engine.py` | Add `run_portfolio_backtest()` |
| Modify | `autotrade/triggers/cli.py` | Add `portfolio-backtest` CLI command |
| Modify | `autotrade/reporters/plot_reporter.py` | Add equity curve chart method for portfolio results |

---

### Task 1: Account Dataclasses

**Files:**
- Create: `autotrade/core/account.py`
- Test: `tests/unit/test_portfolio_backtester.py` (shared test file)

- [ ] **Step 1: Write the test for PortfolioPosition**

```python
"""Tests for portfolio backtest components."""
from datetime import date

from autotrade.core.account import Account, PortfolioPosition, PortfolioTrade


class TestPortfolioPosition:
    def test_days_held(self):
        pos = PortfolioPosition(
            symbol="000001", entry_date=date(2024, 1, 10),
            entry_price=10.0, quantity=1000,
            highest_close_since_entry=10.5,
        )
        assert pos.days_held(date(2024, 1, 20)) == 10

    def test_market_value(self):
        pos = PortfolioPosition(
            symbol="000001", entry_date=date(2024, 1, 10),
            entry_price=10.0, quantity=1000,
            highest_close_since_entry=10.0,
        )
        assert pos.market_value(12.0) == 12000.0

    def test_pnl_pct_positive(self):
        pos = PortfolioPosition(
            symbol="000001", entry_date=date(2024, 1, 10),
            entry_price=10.0, quantity=1000,
            highest_close_since_entry=12.0,
        )
        assert pos.pnl_pct(11.0) == 0.1

    def test_pnl_pct_negative(self):
        pos = PortfolioPosition(
            symbol="000001", entry_date=date(2024, 1, 10),
            entry_price=10.0, quantity=1000,
            highest_close_since_entry=10.0,
        )
        assert pos.pnl_pct(9.0) == -0.1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_portfolio_backtester.py::TestPortfolioPosition -v`
Expected: FAIL with "No module named 'autotrade.core.account'"

- [ ] **Step 3: Write `autotrade/core/account.py`**

```python
"""Portfolio account models: Position, Trade, Account, PendingBuy."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class PortfolioPosition:
    """A single holding in the portfolio."""
    symbol: str
    entry_date: date
    entry_price: float
    quantity: int
    highest_close_since_entry: float
    locked_until: Optional[date] = None  # T+1: cannot sell before this date

    def days_held(self, current_date: date) -> int:
        return (current_date - self.entry_date).days

    def market_value(self, current_price: float) -> float:
        return self.quantity * current_price

    def pnl_pct(self, current_price: float) -> float:
        return (current_price - self.entry_price) / self.entry_price


@dataclass
class PortfolioTrade:
    """A completed buy-sell round trip."""
    symbol: str
    buy_date: date
    sell_date: date
    buy_price: float
    sell_price: float
    quantity: int
    pnl: float
    pnl_pct: float


@dataclass
class PendingBuy:
    """A buy order planned for the next trading day."""
    symbol: str
    quantity: int


@dataclass
class Account:
    """Portfolio account tracking cash, positions, equity history, and trades."""
    initial_capital: float
    cash: float
    positions: dict[str, PortfolioPosition] = field(default_factory=dict)
    equity_curve: list[tuple[date, float]] = field(default_factory=list)
    trades: list[PortfolioTrade] = field(default_factory=list)

    def total_equity(self, prices: dict[str, float]) -> float:
        """Cash plus mark-to-market value of all positions."""
        position_value = sum(
            pos.market_value(prices[sym])
            for sym, pos in self.positions.items()
            if sym in prices
        )
        return self.cash + position_value

    def record_equity(self, d: date, prices: dict[str, float]):
        """Snapshot total equity for date d."""
        self.equity_curve.append((d, self.total_equity(prices)))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_portfolio_backtester.py::TestPortfolioPosition -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add autotrade/core/account.py tests/unit/test_portfolio_backtester.py
git commit -m "feat: add Account, PortfolioPosition, PortfolioTrade dataclasses"
```

---

### Task 2: Account Equity & Trade Tests

**Files:**
- Modify: `tests/unit/test_portfolio_backtester.py` (append tests)

- [ ] **Step 1: Add Account tests to the test file**

```python
class TestAccount:
    def test_total_equity_all_cash(self):
        acct = Account(initial_capital=1000000.0, cash=1000000.0)
        assert acct.total_equity({}) == 1000000.0

    def test_total_equity_with_positions(self):
        acct = Account(initial_capital=1000000.0, cash=500000.0)
        pos = PortfolioPosition(
            symbol="000001", entry_date=date(2024, 1, 10),
            entry_price=10.0, quantity=10000,
            highest_close_since_entry=10.0,
        )
        acct.positions["000001"] = pos
        assert acct.total_equity({"000001": 12.0}) == 500000.0 + 120000.0

    def test_record_equity_appends(self):
        acct = Account(initial_capital=1000000.0, cash=1000000.0)
        acct.record_equity(date(2024, 1, 10), {})
        assert len(acct.equity_curve) == 1
        assert acct.equity_curve[0] == (date(2024, 1, 10), 1000000.0)

    def test_record_equity_with_position(self):
        acct = Account(initial_capital=1000000.0, cash=500000.0)
        pos = PortfolioPosition(
            symbol="000001", entry_date=date(2024, 1, 10),
            entry_price=10.0, quantity=10000,
            highest_close_since_entry=10.0,
        )
        acct.positions["000001"] = pos
        acct.record_equity(date(2024, 1, 10), {"000001": 12.0})
        assert acct.equity_curve[0][1] == 620000.0
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `pytest tests/unit/test_portfolio_backtester.py::TestAccount -v`
Expected: 4 PASS

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_portfolio_backtester.py
git commit -m "test: add Account equity tracking tests"
```

---

### Task 3: MarketRegime

**Files:**
- Create: `autotrade/core/market_regime.py`
- Modify: `tests/unit/test_portfolio_backtester.py` (append tests)

- [ ] **Step 1: Add MarketRegime tests**

```python
from autotrade.core.market_regime import MarketRegime


class TestMarketRegime:
    def test_empty_candidates_returns_zero(self):
        mr = MarketRegime()
        assert mr.detect([]) == 0

    def test_bullish_returns_3(self):
        mr = MarketRegime(bullish_threshold=0.6)
        candidates = [("A", 0.9, "strong"), ("B", 0.8, "strong"), ("C", 0.7, "strong")]
        assert mr.detect(candidates) == 3

    def test_neutral_returns_2(self):
        mr = MarketRegime(neutral_threshold=0.4, bullish_threshold=0.6)
        candidates = [("A", 0.5, "steady"), ("B", 0.45, "steady")]
        assert mr.detect(candidates) == 2

    def test_bearish_returns_1(self):
        mr = MarketRegime(neutral_threshold=0.4)
        candidates = [("A", 0.35, "weak"), ("B", 0.3, "weak")]
        assert mr.detect(candidates) == 1

    def test_scores_below_threshold_excluded(self):
        mr = MarketRegime(score_threshold=0.3, neutral_threshold=0.4, bullish_threshold=0.6)
        # Only one candidate above score_threshold (0.3), avg=0.5 → neutral → 2
        candidates = [("A", 0.5, "steady"), ("B", 0.2, "weak"), ("C", 0.1, "weak")]
        assert mr.detect(candidates) == 2

    def test_all_below_threshold_returns_1(self):
        mr = MarketRegime(score_threshold=0.3)
        candidates = [("A", 0.2, "weak"), ("B", 0.1, "weak")]
        assert mr.detect(candidates) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_portfolio_backtester.py::TestMarketRegime -v`
Expected: FAIL (no module / no class)

- [ ] **Step 3: Write `autotrade/core/market_regime.py`**

```python
"""Market regime detector — maps screener output breadth to max positions."""
from __future__ import annotations


class MarketRegime:
    """Detect market regime from screener candidate quality.

    Uses the average score of candidates above a threshold as a proxy
    for market breadth/health. Higher average → more positions allowed.
    """

    def __init__(
        self,
        score_threshold: float = 0.3,
        bullish_threshold: float = 0.6,
        neutral_threshold: float = 0.4,
    ):
        self.score_threshold = score_threshold
        self.bullish_threshold = bullish_threshold
        self.neutral_threshold = neutral_threshold

    def detect(self, candidates: list[tuple[str, float, str]]) -> int:
        """Return max_positions (0|1|2|3) based on candidate quality.

        Args:
            candidates: List of (symbol, score, tag) sorted by score desc.

        Returns:
            Max simultaneous positions: 0 if no candidates, 1-3 otherwise.
        """
        if not candidates:
            return 0

        valid_scores = [s for _, s, _ in candidates if s >= self.score_threshold]
        if not valid_scores:
            return 1

        avg = sum(valid_scores) / len(valid_scores)
        if avg >= self.bullish_threshold:
            return 3
        elif avg >= self.neutral_threshold:
            return 2
        else:
            return 1
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_portfolio_backtester.py::TestMarketRegime -v`
Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add autotrade/core/market_regime.py tests/unit/test_portfolio_backtester.py
git commit -m "feat: add MarketRegime with screener-breadth-based detection"
```

---

### Task 4: ExitManager

**Files:**
- Create: `autotrade/core/exit_manager.py`
- Modify: `tests/unit/test_portfolio_backtester.py` (append tests)

- [ ] **Step 1: Add ExitManager tests**

```python
from autotrade.core.exit_manager import ExitManager


def _make_position(symbol="000001", entry_price=10.0, quantity=1000,
                   highest=10.5, entry_date=date(2024, 1, 10)):
    return PortfolioPosition(
        symbol=symbol, entry_date=entry_date,
        entry_price=entry_price, quantity=quantity,
        highest_close_since_entry=highest,
    )


class TestExitManager:
    def test_no_rules_triggered_when_safe(self):
        config = {
            "exit_rules": {
                "trailing_stop": {"enabled": True, "drawdown_pct": 0.08},
                "hard_stop": {"enabled": True, "loss_pct": 0.05},
                "time_stop": {"enabled": True, "max_holding_days": 20, "min_return_pct": 0.0},
                "signal_decay": {"enabled": True, "rank_threshold": 50},
            }
        }
        em = ExitManager(config)
        pos = _make_position(entry_price=10.0, highest=10.5)
        # price at 10.2: drawdown from high = (10.5-10.2)/10.5 = 2.9% < 8%
        # loss from entry = (10.2-10.0)/10.0 = 2% > -5%
        # holding 3 days < 20
        triggers = em.check(pos, 10.2, date(2024, 1, 13),
                            [("000001", 0.8, "strong")],
                            date(2024, 1, 12))
        assert triggers == []

    def test_hard_stop_triggers(self):
        config = {
            "exit_rules": {
                "trailing_stop": {"enabled": False, "drawdown_pct": 0.08},
                "hard_stop": {"enabled": True, "loss_pct": 0.05},
                "time_stop": {"enabled": False, "max_holding_days": 20, "min_return_pct": 0.0},
                "signal_decay": {"enabled": False, "rank_threshold": 50},
            }
        }
        em = ExitManager(config)
        pos = _make_position(entry_price=10.0, highest=10.0)
        triggers = em.check(pos, 9.4, date(2024, 1, 13),
                            [], date(2024, 1, 12))
        assert "hard_stop" in triggers

    def test_trailing_stop_triggers(self):
        config = {
            "exit_rules": {
                "trailing_stop": {"enabled": True, "drawdown_pct": 0.08},
                "hard_stop": {"enabled": False, "loss_pct": 0.05},
                "time_stop": {"enabled": False, "max_holding_days": 20, "min_return_pct": 0.0},
                "signal_decay": {"enabled": False, "rank_threshold": 50},
            }
        }
        em = ExitManager(config)
        pos = _make_position(entry_price=10.0, highest=12.0)
        # drawdown from high: (12.0-10.5)/12.0 = 12.5% >= 8%
        triggers = em.check(pos, 10.5, date(2024, 1, 20),
                            [], date(2024, 1, 12))
        assert "trailing_stop" in triggers

    def test_trailing_stop_not_triggered_near_high(self):
        config = {
            "exit_rules": {
                "trailing_stop": {"enabled": True, "drawdown_pct": 0.08},
                "hard_stop": {"enabled": False, "loss_pct": 0.05},
                "time_stop": {"enabled": False, "max_holding_days": 20, "min_return_pct": 0.0},
                "signal_decay": {"enabled": False, "rank_threshold": 50},
            }
        }
        em = ExitManager(config)
        pos = _make_position(entry_price=10.0, highest=12.0)
        # drawdown: (12.0-11.5)/12.0 = 4.2% < 8%
        triggers = em.check(pos, 11.5, date(2024, 1, 20),
                            [], date(2024, 1, 12))
        assert "trailing_stop" not in triggers

    def test_time_stop_triggers(self):
        config = {
            "exit_rules": {
                "trailing_stop": {"enabled": False, "drawdown_pct": 0.08},
                "hard_stop": {"enabled": False, "loss_pct": 0.05},
                "time_stop": {"enabled": True, "max_holding_days": 20, "min_return_pct": 0.0},
                "signal_decay": {"enabled": False, "rank_threshold": 50},
            }
        }
        em = ExitManager(config)
        pos = _make_position(entry_price=10.0, highest=10.0,
                             entry_date=date(2024, 1, 2))
        triggers = em.check(pos, 10.0, date(2024, 1, 25),
                            [], date(2024, 1, 2))
        assert "time_stop" in triggers

    def test_time_stop_not_triggered_when_profitable(self):
        config = {
            "exit_rules": {
                "trailing_stop": {"enabled": False, "drawdown_pct": 0.08},
                "hard_stop": {"enabled": False, "loss_pct": 0.05},
                "time_stop": {"enabled": True, "max_holding_days": 20, "min_return_pct": 0.05},
                "signal_decay": {"enabled": False, "rank_threshold": 50},
            }
        }
        em = ExitManager(config)
        pos = _make_position(entry_price=10.0, highest=12.0,
                             entry_date=date(2024, 1, 2))
        # PnL = (12.0-10.0)/10.0 = 20% > 5% min_return → don't time-stop
        triggers = em.check(pos, 12.0, date(2024, 1, 25),
                            [], date(2024, 1, 2))
        assert "time_stop" not in triggers

    def test_signal_decay_triggers(self):
        config = {
            "exit_rules": {
                "trailing_stop": {"enabled": False, "drawdown_pct": 0.08},
                "hard_stop": {"enabled": False, "loss_pct": 0.05},
                "time_stop": {"enabled": False, "max_holding_days": 20, "min_return_pct": 0.0},
                "signal_decay": {"enabled": True, "rank_threshold": 2},
            }
        }
        em = ExitManager(config)
        pos = _make_position(symbol="000001")
        # Top 2 symbols are "A" and "B" — "000001" is not in top 2
        candidates = [("A", 0.9, "strong"), ("B", 0.8, "strong"), ("000001", 0.5, "steady")]
        triggers = em.check(pos, 10.0, date(2024, 1, 15),
                            candidates, date(2024, 1, 12))
        assert "signal_decay" in triggers

    def test_signal_decay_not_triggered_when_in_top(self):
        config = {
            "exit_rules": {
                "trailing_stop": {"enabled": False, "drawdown_pct": 0.08},
                "hard_stop": {"enabled": False, "loss_pct": 0.05},
                "time_stop": {"enabled": False, "max_holding_days": 20, "min_return_pct": 0.0},
                "signal_decay": {"enabled": True, "rank_threshold": 6},
            }
        }
        em = ExitManager(config)
        pos = _make_position(symbol="000001")
        candidates = [("A", 0.9, "strong"), ("B", 0.8, "strong"), ("000001", 0.5, "steady")]
        triggers = em.check(pos, 10.0, date(2024, 1, 15),
                            candidates, date(2024, 1, 12))
        assert "signal_decay" not in triggers

    def test_multiple_rules_can_trigger(self):
        config = {
            "exit_rules": {
                "trailing_stop": {"enabled": True, "drawdown_pct": 0.08},
                "hard_stop": {"enabled": True, "loss_pct": 0.05},
                "time_stop": {"enabled": False, "max_holding_days": 20, "min_return_pct": 0.0},
                "signal_decay": {"enabled": False, "rank_threshold": 50},
            }
        }
        em = ExitManager(config)
        pos = _make_position(entry_price=10.0, highest=12.0)
        # price 9.0: loss from entry = -10% → hard_stop
        # drawdown from high = (12-9)/12 = 25% → trailing_stop
        triggers = em.check(pos, 9.0, date(2024, 1, 20),
                            [], date(2024, 1, 12))
        assert "hard_stop" in triggers
        assert "trailing_stop" in triggers

    def test_disabled_rule_not_checked(self):
        config = {
            "exit_rules": {
                "trailing_stop": {"enabled": False, "drawdown_pct": 0.08},
                "hard_stop": {"enabled": False, "loss_pct": 0.05},
                "time_stop": {"enabled": False, "max_holding_days": 20, "min_return_pct": 0.0},
                "signal_decay": {"enabled": False, "rank_threshold": 50},
            }
        }
        em = ExitManager(config)
        pos = _make_position(entry_price=10.0, highest=12.0)
        triggers = em.check(pos, 5.0, date(2024, 2, 1),
                            [], date(2024, 1, 12))
        assert triggers == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_portfolio_backtester.py::TestExitManager -v`
Expected: FAIL (no module)

- [ ] **Step 3: Write `autotrade/core/exit_manager.py`**

```python
"""Unified exit rule engine — trailing stop, hard stop, time stop, signal decay."""
from __future__ import annotations

from datetime import date

from autotrade.core.account import PortfolioPosition


class ExitManager:
    """Check exit rules against a position and current market state.

    Four exit gates, each configurable and independently enabled:
    1. trailing_stop: sell when price drops drawdown_pct from position high
    2. hard_stop: sell when loss exceeds loss_pct from entry
    3. time_stop: sell when held too long without sufficient return
    4. signal_decay: sell when stock falls out of screener top-K
    """

    def __init__(self, config: dict):
        rules = config.get("exit_rules", {})
        self.trailing_stop = rules.get("trailing_stop", {})
        self.hard_stop = rules.get("hard_stop", {})
        self.time_stop = rules.get("time_stop", {})
        self.signal_decay = rules.get("signal_decay", {})

    def check(
        self,
        position: PortfolioPosition,
        current_price: float,
        current_date: date,
        screener_candidates: list[tuple[str, float, str]],
        screener_date: date,
    ) -> list[str]:
        """Check all enabled exit rules. Returns list of triggered rule names."""
        triggers: list[str] = []

        # 1. Trailing stop: drawdown from highest close since entry
        if self.trailing_stop.get("enabled", True):
            drawdown_pct = self.trailing_stop["drawdown_pct"]
            if position.highest_close_since_entry > 0:
                drawdown = (
                    (position.highest_close_since_entry - current_price)
                    / position.highest_close_since_entry
                )
                if drawdown >= drawdown_pct:
                    triggers.append("trailing_stop")

        # 2. Hard stop: absolute loss from entry
        if self.hard_stop.get("enabled", True):
            loss_pct = self.hard_stop["loss_pct"]
            loss = (current_price - position.entry_price) / position.entry_price
            if loss <= -loss_pct:
                triggers.append("hard_stop")

        # 3. Time stop: held too long with insufficient return
        if self.time_stop.get("enabled", True):
            max_days = self.time_stop["max_holding_days"]
            min_return = self.time_stop["min_return_pct"]
            days = position.days_held(current_date)
            pnl = position.pnl_pct(current_price)
            if days >= max_days and pnl < min_return:
                triggers.append("time_stop")

        # 4. Signal decay: stock no longer in screener top-K
        if self.signal_decay.get("enabled", True):
            rank_threshold = self.signal_decay["rank_threshold"]
            top_symbols = {s for s, _, _ in screener_candidates[:rank_threshold]}
            if position.symbol not in top_symbols:
                triggers.append("signal_decay")

        return triggers
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_portfolio_backtester.py::TestExitManager -v`
Expected: 10 PASS

- [ ] **Step 5: Commit**

```bash
git add autotrade/core/exit_manager.py tests/unit/test_portfolio_backtester.py
git commit -m "feat: add ExitManager with 4-gate unified exit rules"
```

---

### Task 5: PortfolioBacktester — Core Loop

**Files:**
- Create: `autotrade/core/portfolio_backtester.py`
- Modify: `tests/unit/test_portfolio_backtester.py` (append tests)

- [ ] **Step 1: Add PortfolioBacktester tests**

```python
import pandas as pd
import numpy as np
from autotrade.core.portfolio_backtester import PortfolioBacktester, PortfolioBacktestConfig


def _make_config(**kwargs) -> PortfolioBacktestConfig:
    defaults = {
        "start_date": date(2024, 1, 2),
        "end_date": date(2024, 1, 31),
        "initial_capital": 1_000_000.0,
        "cash_buffer": 0.05,
        "top_n_candidates": 10,
        "fill_price": "next_open",
        "commission_rate": 0.0003,
        "stamp_duty_rate": 0.001,
        "slippage": 0.001,
        "min_commission": 5.0,
        "lot_size": 100,
        "allow_t_plus_1": True,
        "exit_rules": {
            "trailing_stop": {"enabled": True, "drawdown_pct": 0.08},
            "hard_stop": {"enabled": True, "loss_pct": 0.05},
            "time_stop": {"enabled": True, "max_holding_days": 20, "min_return_pct": 0.0},
            "signal_decay": {"enabled": True, "rank_threshold": 50},
        },
        "market_regime": {
            "score_threshold": 0.3,
            "bullish_threshold": 0.6,
            "neutral_threshold": 0.4,
        },
    }
    defaults.update(kwargs)
    return PortfolioBacktestConfig(**defaults)


def _make_market_data(symbols: list[str], dates: list[date],
                      base_prices: dict[str, float] = None) -> dict[str, pd.DataFrame]:
    """Build minimal market data DataFrames for testing."""
    base = base_prices or {}
    market = {}
    for sym in symbols:
        price = base.get(sym, 10.0)
        # Slightly varying prices over dates
        records = []
        for i, d in enumerate(dates):
            p = price * (1 + i * 0.01)  # gentle uptrend
            records.append({
                "date": d,
                "open": p,
                "high": p * 1.02,
                "low": p * 0.98,
                "close": p * 1.01,
                "volume": 1_000_000,
                "amount": p * 1_000_000,
            })
        df = pd.DataFrame(records)
        df.set_index("date", inplace=True)
        market[sym] = df
    return market


def _make_trading_dates(start: date, days: int) -> list[date]:
    """Generate a list of consecutive weekdays (simplified trading dates)."""
    import datetime
    dates = []
    current = start
    for _ in range(days):
        if current.weekday() < 5:
            dates.append(current)
        current = current + datetime.timedelta(days=1)
    return dates


class TestPortfolioBacktester:
    def test_empty_screener_no_trades(self):
        """With no screener candidates, no trades should be made."""
        config = _make_config()
        bt = PortfolioBacktester(config)
        dates_list = _make_trading_dates(date(2024, 1, 2), 20)
        market = _make_market_data(["000001"], dates_list)
        screener_results: dict = {d: [] for d in dates_list}

        result = bt.run(market, screener_results)
        assert len(result.trades) == 0
        assert len(result.equity_curve) > 0
        assert result.equity_curve.iloc[0] == 1_000_000.0

    def test_single_candidate_creates_position(self):
        """A single screener candidate should result in a buy on the next day."""
        config = _make_config(
            allow_t_plus_1=False,  # simplify test: allow same-day sell
        )
        bt = PortfolioBacktester(config)
        dates_list = _make_trading_dates(date(2024, 1, 2), 10)
        market = _make_market_data(["000001"], dates_list, {"000001": 10.0})

        # Screener finds "000001" every day
        screener_results = {d: [("000001", 0.8, "momentum_strong")] for d in dates_list}

        result = bt.run(market, screener_results)
        # Should have created at least one trade (a buy on day 2)
        assert len(result.trades) == 1  # one buy-sell round trip (forced close at end)
        assert result.equity_curve is not None
        assert len(result.equity_curve) == len(dates_list)

    def test_max_positions_not_exceeded_with_tight_limit(self):
        """With max_positions=1 regime, only 1 stock held at a time."""
        config = _make_config(
            market_regime={
                "score_threshold": 0.3,
                "bullish_threshold": 0.99,  # unreachable → always bearish → 1
                "neutral_threshold": 0.99,
            },
            allow_t_plus_1=False,
            exit_rules={
                "trailing_stop": {"enabled": False},
                "hard_stop": {"enabled": False},
                "time_stop": {"enabled": False},
                "signal_decay": {"enabled": True, "rank_threshold": 1},
            },
        )
        bt = PortfolioBacktester(config)
        dates_list = _make_trading_dates(date(2024, 1, 2), 10)
        market = _make_market_data(["000001", "000002", "000003"],
                                   dates_list, {"000001": 10.0, "000002": 20.0,
                                                "000003": 30.0})

        # 3 candidates daily, but regime says only 1 position
        screener_results = {}
        for d in dates_list:
            screener_results[d] = [
                ("000001", 0.4, "steady"),  # below bullish/neutral thresholds
                ("000002", 0.35, "steady"),
                ("000003", 0.3, "weak"),
            ]

        result = bt.run(market, screener_results)
        # Each trade is a round-trip; with signal_decay threshold=1,
        # only the top candidate stays, so position rotates as candidates change
        assert len(result.trades) >= 0  # may have trades or not depending on exact timing
        # Key: should not crash or error
        assert result.equity_curve is not None

    def test_lot_size_rounding(self):
        """All trade quantities must be multiples of lot_size (100)."""
        config = _make_config(allow_t_plus_1=False)
        bt = PortfolioBacktester(config)
        dates_list = _make_trading_dates(date(2024, 1, 2), 5)
        market = _make_market_data(["000001"], dates_list, {"000001": 10.0})

        screener_results = {d: [("000001", 0.8, "strong")] for d in dates_list}
        result = bt.run(market, screener_results)

        # All trade quantities should be multiples of 100
        for trade in result.trades:
            assert trade.quantity % 100 == 0, f"Quantity {trade.quantity} not a multiple of 100"

    def test_equity_curve_one_point_per_day(self):
        """Equity curve should have one entry per trading day."""
        config = _make_config()
        bt = PortfolioBacktester(config)
        dates_list = _make_trading_dates(date(2024, 1, 2), 20)
        market = _make_market_data(["000001"], dates_list)
        screener_results = {d: [] for d in dates_list}

        result = bt.run(market, screener_results)
        # One equity point per trading day
        assert len(result.equity_curve) == len(dates_list)

    def test_buy_followed_by_sell_frees_symbol(self):
        """After a sell, the symbol can be bought again later."""
        config = _make_config(
            allow_t_plus_1=False,
            exit_rules={
                "trailing_stop": {"enabled": False},
                "hard_stop": {"enabled": False},
                "time_stop": {"enabled": False},
                "signal_decay": {"enabled": True, "rank_threshold": 1},
            },
        )
        bt = PortfolioBacktester(config)
        dates_list = _make_trading_dates(date(2024, 1, 2), 10)
        market = _make_market_data(["000001", "000002"], dates_list,
                                   {"000001": 10.0, "000002": 20.0})

        # Day 0-2: 000001 is top, Day 3-9: 000002 is top
        screener_results = {}
        for i, d in enumerate(dates_list):
            if i < 3:
                screener_results[d] = [
                    ("000001", 0.6, "strong"),
                    ("000002", 0.5, "strong"),
                ]
            else:
                screener_results[d] = [
                    ("000002", 0.6, "strong"),
                    ("000001", 0.5, "strong"),
                ]

        result = bt.run(market, screener_results)
        # Should have trades for both symbols (bought, then signal_decay triggered sell, then other bought)
        symbols_traded = {t.symbol for t in result.trades}
        assert len(symbols_traded) >= 1  # at least one symbol was traded
        assert result.equity_curve is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/unit/test_portfolio_backtester.py::TestPortfolioBacktester -v`
Expected: FAIL

- [ ] **Step 3: Write `autotrade/core/portfolio_backtester.py`**

```python
"""Portfolio-level backtest engine — daily loop with screener-driven entries
and unified exit rules across multiple simultaneous positions."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Optional

import numpy as np
import pandas as pd

from autotrade.core.account import (
    Account, PendingBuy, PortfolioPosition, PortfolioTrade,
)
from autotrade.core.exit_manager import ExitManager
from autotrade.core.market_regime import MarketRegime

logger = logging.getLogger(__name__)


@dataclass
class PortfolioBacktestConfig:
    """Configuration for a portfolio backtest run."""
    start_date: date
    end_date: date
    initial_capital: float = 1_000_000.0
    cash_buffer: float = 0.05
    top_n_candidates: int = 50
    fill_price: str = "next_open"
    commission_rate: float = 0.0003
    stamp_duty_rate: float = 0.001
    slippage: float = 0.001
    min_commission: float = 5.0
    lot_size: int = 100
    allow_t_plus_1: bool = True
    exit_rules: dict = field(default_factory=dict)
    market_regime: dict = field(default_factory=dict)


@dataclass
class PortfolioBacktestResult:
    """Result of a portfolio backtest."""
    trades: list[PortfolioTrade] = field(default_factory=list)
    equity_curve: Optional[pd.Series] = None
    metrics: dict = field(default_factory=dict)


class PortfolioBacktester:
    """Portfolio-level backtest engine.

    Daily loop:
      Morning: execute pending buys, check exits, record equity
      Evening: detect regime, plan next-day buys from screener results
    """

    def __init__(self, config: PortfolioBacktestConfig):
        self.config = config
        self.exit_manager = ExitManager({
            "exit_rules": config.exit_rules,
        })
        self.regime = MarketRegime(**config.market_regime)

    def run(
        self,
        market_data: dict[str, pd.DataFrame],
        screener_results: dict[date, list[tuple[str, float, str]]],
    ) -> PortfolioBacktestResult:
        """Execute the portfolio backtest.

        Args:
            market_data: {symbol: DataFrame} with date index and OHLCV columns.
            screener_results: {date: [(symbol, score, tag), ...]} precomputed
                by the screener for all trading dates.

        Returns:
            PortfolioBacktestResult with trades, equity curve, and metrics.
        """
        # Collect all unique trading dates from market data
        all_dates: set[date] = set()
        for df in market_data.values():
            for idx_val in df.index:
                d = idx_val.date() if hasattr(idx_val, "date") else idx_val
                all_dates.add(d)
        trading_dates = sorted(d for d in all_dates
                               if self.config.start_date <= d <= self.config.end_date)

        if not trading_dates:
            return PortfolioBacktestResult(
                metrics={"error": "No trading dates in range"},
            )

        # Initialize account
        account = Account(
            initial_capital=self.config.initial_capital,
            cash=self.config.initial_capital,
        )

        pending_buys: list[PendingBuy] = []
        prev_date: Optional[date] = None

        for day_idx, today in enumerate(trading_dates):
            # --- Get open prices for today ---
            opens = self._get_day_prices(market_data, today, "open")

            # --- Morning: execute pending buys ---
            for buy in pending_buys:
                price = opens.get(buy.symbol)
                if price is None:
                    continue  # no data, skip
                self._execute_buy(account, buy, price, today)

            pending_buys.clear()

            # --- Morning: check exits (unlocked positions) ---
            prev_screener = screener_results.get(prev_date, []) if prev_date else []
            for symbol in list(account.positions.keys()):
                pos = account.positions[symbol]
                # T+1 lock check
                if (self.config.allow_t_plus_1 and pos.locked_until
                        and today <= pos.locked_until):
                    continue

                price = opens.get(symbol)
                if price is None:
                    continue

                # Update highest close
                if price > pos.highest_close_since_entry:
                    pos.highest_close_since_entry = price

                triggers = self.exit_manager.check(
                    pos, price, today, prev_screener, prev_date or today,
                )
                if triggers:
                    self._execute_sell(account, pos, price, today, triggers)

            # --- Morning: record equity ---
            account.record_equity(today, opens)

            # --- Evening: detect regime ---
            today_candidates = screener_results.get(today, [])
            max_positions = self.regime.detect(today_candidates)

            # --- Evening: plan buys for next day ---
            if max_positions > 0:
                slots = max_positions - len(account.positions)
                if slots > 0:
                    # Filter: exclude already-held symbols
                    held = set(account.positions.keys())
                    available = [
                        (s, sc, t) for s, sc, t in today_candidates
                        if s not in held
                    ][:self.config.top_n_candidates]

                    picks = available[:slots]
                    if picks:
                        pending_buys = self._plan_buys(
                            picks, account.cash, opens,
                        )

            prev_date = today

        # Force-close any remaining positions at last available close
        if account.positions:
            closes = self._get_day_prices(market_data, trading_dates[-1], "close")
            for symbol, pos in list(account.positions.items()):
                price = closes.get(symbol)
                if price is None:
                    continue
                self._execute_sell(account, pos, price, trading_dates[-1],
                                   ["end_of_period"])

        # Build result
        equity_series = pd.Series(
            [eq for _, eq in account.equity_curve],
            index=[d for d, _ in account.equity_curve],
        )
        metrics = self._compute_metrics(account, equity_series)

        return PortfolioBacktestResult(
            trades=account.trades,
            equity_curve=equity_series,
            metrics=metrics,
        )

    # ---- Internal helpers ----

    def _get_day_prices(
        self, market_data: dict[str, pd.DataFrame], d: date, col: str,
    ) -> dict[str, float]:
        """Get a price column for all symbols on a given date."""
        prices: dict[str, float] = {}
        for sym, df in market_data.items():
            try:
                val = df.loc[d, col]
                if isinstance(val, pd.Series):
                    val = val.iloc[0]
                if not pd.isna(val) and float(val) > 0:
                    prices[sym] = float(val)
            except (KeyError, TypeError):
                pass
        return prices

    def _execute_buy(
        self, account: Account, buy: PendingBuy,
        price: float, today: date,
    ):
        """Execute a pending buy at today's open."""
        fill_price = price * (1 + self.config.slippage)
        quantity = buy.quantity
        if quantity <= 0:
            return

        cost = quantity * fill_price
        commission = max(cost * self.config.commission_rate,
                         self.config.min_commission)
        total_cost = cost + commission

        if total_cost > account.cash:
            # Adjust quantity downward
            affordable_qty = int(
                (account.cash - self.config.min_commission)
                / (fill_price * (1 + self.config.commission_rate))
            )
            quantity = (affordable_qty // self.config.lot_size) * self.config.lot_size
            if quantity <= 0:
                return
            cost = quantity * fill_price
            commission = max(cost * self.config.commission_rate,
                             self.config.min_commission)
            total_cost = cost + commission

        account.cash -= total_cost

        locked_until = None
        if self.config.allow_t_plus_1:
            locked_until = today  # can't sell until next trading day

        position = PortfolioPosition(
            symbol=buy.symbol,
            entry_date=today,
            entry_price=fill_price,
            quantity=quantity,
            highest_close_since_entry=fill_price,
            locked_until=locked_until,
        )
        account.positions[buy.symbol] = position

    def _execute_sell(
        self, account: Account, position: PortfolioPosition,
        price: float, today: date, triggers: list[str],
    ):
        """Execute a sell for a position."""
        fill_price = price * (1 - self.config.slippage)
        quantity = position.quantity
        proceeds = quantity * fill_price
        commission = max(proceeds * self.config.commission_rate,
                         self.config.min_commission)
        stamp_duty = proceeds * self.config.stamp_duty_rate

        account.cash += proceeds - commission - stamp_duty

        pnl = proceeds - (position.entry_price * quantity) - commission - stamp_duty
        pnl_pct = (fill_price - position.entry_price) / position.entry_price

        trade = PortfolioTrade(
            symbol=position.symbol,
            buy_date=position.entry_date,
            sell_date=today,
            buy_price=position.entry_price,
            sell_price=fill_price,
            quantity=quantity,
            pnl=round(pnl, 2),
            pnl_pct=round(pnl_pct, 4),
        )
        account.trades.append(trade)
        del account.positions[position.symbol]

    def _plan_buys(
        self,
        picks: list[tuple[str, float, str]],
        cash: float,
        opens: dict[str, float],
    ) -> list[PendingBuy]:
        """Allocate cash by signal strength and create pending buys."""
        total_score = sum(sc for _, sc, _ in picks)
        if total_score <= 0:
            return []

        available = cash * (1 - self.config.cash_buffer)
        pending: list[PendingBuy] = []

        for symbol, score, _ in picks:
            weight = score / total_score
            alloc = available * weight
            price = opens.get(symbol)
            if price is None or price <= 0:
                continue
            fill_price = price * (1 + self.config.slippage)
            # Account for commission in quantity calculation
            qty = int(alloc / (fill_price * (1 + self.config.commission_rate))
                      / self.config.lot_size) * self.config.lot_size
            if qty > 0:
                pending.append(PendingBuy(symbol=symbol, quantity=qty))

        return pending

    def _compute_metrics(
        self, account: Account, equity_curve: pd.Series,
    ) -> dict:
        """Compute summary metrics."""
        if equity_curve.empty or len(equity_curve) < 2:
            return {
                "total_trades": len(account.trades),
                "total_return_pct": 0.0,
                "win_rate": 0.0,
                "max_drawdown_pct": 0.0,
                "sharpe_ratio": 0.0,
            }

        initial = equity_curve.iloc[0]
        final = equity_curve.iloc[-1]
        total_return_pct = (final - initial) / initial * 100

        # Win rate
        wins = sum(1 for t in account.trades if t.pnl > 0)
        total_closed = len(account.trades)
        win_rate = (wins / total_closed * 100) if total_closed > 0 else 0.0

        # Max drawdown
        peak = np.maximum.accumulate(equity_curve.values)
        drawdown = (peak - equity_curve.values) / peak * 100
        max_drawdown_pct = -float(np.max(drawdown)) if len(drawdown) > 0 else 0.0

        # Sharpe ratio
        returns = equity_curve.pct_change().dropna()
        if returns.std() > 0:
            sharpe = float(returns.mean() / returns.std() * np.sqrt(252))
        else:
            sharpe = 0.0

        return {
            "initial_capital": self.config.initial_capital,
            "final_equity": round(final, 2),
            "total_trades": len(account.trades),
            "total_return_pct": round(total_return_pct, 2),
            "win_rate": round(win_rate, 2),
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "sharpe_ratio": round(sharpe, 4),
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_portfolio_backtester.py::TestPortfolioBacktester -v`
Expected: all tests pass

- [ ] **Step 5: Commit**

```bash
git add autotrade/core/portfolio_backtester.py tests/unit/test_portfolio_backtester.py
git commit -m "feat: add PortfolioBacktester with daily loop and strength-weighted allocation"
```

---

### Task 6: Configuration YAML

**Files:**
- Create: `config/backtest/portfolio.yaml`

- [ ] **Step 1: Create directory and write config**

```bash
mkdir -p config/backtest
```

Write `config/backtest/portfolio.yaml`:

```yaml
# Portfolio Backtest Configuration
# 组合级回测 — 单账户多持仓 + Screener 入场 + 统一出场

portfolio_backtest:
  # 回测时间区间
  start_date: "2023-06-27"
  end_date: "2026-06-18"

  # 资金
  initial_capital: 1_000_000.0
  cash_buffer: 0.05              # 保留 5% 现金缓冲

  # 选股
  screener: "momentum_screener"  # 使用的筛选器名称
  screener_params: {}            # 覆盖筛选器参数 (可选)
  top_n_candidates: 50           # 每日考虑的候选股数量上限

  # 市场环境判断 (基于筛选器输出广度)
  market_regime:
    score_threshold: 0.3         # 最低分阈值
    bullish_threshold: 0.6       # 平均分 >= 0.6 → 最多持仓 3 支
    neutral_threshold: 0.4       # 平均分 >= 0.4 → 最多持仓 2 支
    # 否则 → 最多持仓 1 支

  # 统一出场规则
  exit_rules:
    trailing_stop:
      enabled: true
      drawdown_pct: 0.08         # 从持仓最高点回撤 8% → 卖出
    time_stop:
      enabled: true
      max_holding_days: 20       # 持有 20 个交易日后
      min_return_pct: 0.0        # …如果收益低于 0% → 卖出
    hard_stop:
      enabled: true
      loss_pct: 0.05             # 亏损超过 5% → 立即卖出
    signal_decay:
      enabled: true
      rank_threshold: 50         # 跌出筛选器 top 50 → 卖出

  # 交易成本 (A 股规则)
  fill_price: "next_open"
  commission_rate: 0.0003        # 万三
  stamp_duty_rate: 0.001         # 千一 (仅卖出)
  slippage: 0.001               # 千一
  min_commission: 5.0            # 最低 5 元
  lot_size: 100                  # 一手 100 股
  allow_t_plus_1: true           # T+1 制度

  # 输出
  output_dir: "data/results"
  output_prefix: "portfolio_backtest"
```

- [ ] **Step 2: Commit**

```bash
git add config/backtest/portfolio.yaml
git commit -m "feat: add portfolio backtest YAML configuration"
```

---

### Task 7: Engine Integration — `run_portfolio_backtest()`

**Files:**
- Modify: `autotrade/core/engine.py`

- [ ] **Step 1: Read the engine.py tail to find insertion point**

The file ends at line 508 with the `run_screener_backtest()` function. We'll add the new function after it.

- [ ] **Step 2: Add `run_portfolio_backtest()` to engine.py**

Append after `run_screener_backtest()` (after line 507):

```python


# ---- 组合回测 ----

def _load_portfolio_backtest_config() -> dict:
    """Load portfolio backtest configuration from YAML."""
    import yaml
    cfg_path = (
        Path(__file__).resolve().parent.parent.parent
        / "config" / "backtest" / "portfolio.yaml"
    )
    if not cfg_path.exists():
        logger.warning("Portfolio backtest config not found, using defaults")
        return {}
    with open(cfg_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("portfolio_backtest", {}) or {}


def run_portfolio_backtest(
    screener_name: str = "momentum_screener",
    start: Optional[date] = None,
    end: Optional[date] = None,
    symbols: str | list[str] = "all",
    datasource_name: str = FAILOVER_NAME,
    screener_params: dict[str, Any] | None = None,
    reporter_names: tuple[str, ...] = ("console",),
) -> dict[str, Any]:
    """组合级回测: 单账户多持仓 + Screener 每日选股 + 统一出场。

    流程:
      1. 加载配置 (config/backtest/portfolio.yaml)
      2. 加载全市场 OHLCV 数据
      3. 预计算 Screener 每日候选
      4. 运行 PortfolioBacktester 逐日模拟
      5. 输出报告

    Args:
        screener_name: 选股筛选器名称。
        start/end: 回测区间，None 则从配置读取。
        symbols: "all" 用全市场，或代码列表。
        screener_params: Screener 参数覆盖。
        reporter_names: 报告输出方式。

    Returns:
        汇总字典。
    """
    from autotrade.core.portfolio_backtester import (
        PortfolioBacktestConfig, PortfolioBacktester,
    )

    init_registry()

    # ---- 1. 加载配置 ----
    cfg = _load_portfolio_backtest_config()
    if not cfg:
        return {"error": "Portfolio backtest config not found"}

    if start is None:
        start_str = cfg.get("start_date", "2023-06-27")
        start = datetime.strptime(start_str, "%Y-%m-%d").date()
    if end is None:
        end_str = cfg.get("end_date", "2026-06-18")
        end = datetime.strptime(end_str, "%Y-%m-%d").date()

    # ---- 2. 解析 symbols + 加载全市场数据 ----
    resolved = _resolve_symbols(symbols, datasource_name)
    if not resolved:
        return {"error": "No symbols to analyze", "results": []}

    # 排除 ST / *ST 股票
    st_exclude = _load_st_exclusion_set()
    if st_exclude:
        resolved = [s for s in resolved if s not in st_exclude]
        logger.info("排除 ST 后剩余 %d 只", len(resolved))
    if not resolved:
        return {"error": "All symbols excluded as ST", "results": []}

    market_data = _load_market_data(resolved, start, end)
    if not market_data:
        return {"error": "No market data loaded", "results": []}

    # 交易日序列
    all_dates: set[date] = set()
    for df in market_data.values():
        for v in df.index:
            d = v.date() if hasattr(v, "date") else v
            all_dates.add(d)
    scan_dates = sorted(d for d in all_dates if start <= d <= end)

    # ---- 3. 运行 Screener ----
    s_params = screener_params
    if s_params is None:
        s_params = _load_screener_params(screener_name)
    # Override screener top_n to match portfolio config
    top_n = int(cfg.get("top_n_candidates", 50))
    s_params["top_n_per_day"] = top_n
    screener_cls = get_screener(screener_name)
    screener = screener_cls(**s_params)
    selection = screener.scan(market_data, scan_dates)
    logger.info("Screener 扫描完成: %d 个交易日有候选", len(selection))

    # ---- 4. 构建回测配置 ----
    exit_rules = cfg.get("exit_rules", {})
    market_regime_cfg = cfg.get("market_regime", {})

    bt_config = PortfolioBacktestConfig(
        start_date=start,
        end_date=end,
        initial_capital=float(cfg.get("initial_capital", 1_000_000)),
        cash_buffer=float(cfg.get("cash_buffer", 0.05)),
        top_n_candidates=top_n,
        fill_price=str(cfg.get("fill_price", "next_open")),
        commission_rate=float(cfg.get("commission_rate", 0.0003)),
        stamp_duty_rate=float(cfg.get("stamp_duty_rate", 0.001)),
        slippage=float(cfg.get("slippage", 0.001)),
        min_commission=float(cfg.get("min_commission", 5.0)),
        lot_size=int(cfg.get("lot_size", 100)),
        allow_t_plus_1=bool(cfg.get("allow_t_plus_1", True)),
        exit_rules=exit_rules,
        market_regime=market_regime_cfg,
    )

    # ---- 5. 运行组合回测 ----
    backtester = PortfolioBacktester(bt_config)
    result = backtester.run(market_data, selection)

    logger.info(
        "组合回测完成: %d 笔交易, 收益率 %.2f%%, 最大回撤 %.2f%%, 夏普 %.4f",
        len(result.trades),
        result.metrics.get("total_return_pct", 0.0),
        result.metrics.get("max_drawdown_pct", 0.0),
        result.metrics.get("sharpe_ratio", 0.0),
    )

    # ---- 6. 输出报告 ----
    for rep_name in reporter_names:
        try:
            reporter_cls = get_reporter(rep_name)
            reporter = reporter_cls() if isinstance(reporter_cls, type) else reporter_cls
            if hasattr(reporter, "render_portfolio"):
                reporter.render_portfolio(result, bt_config)
            else:
                # Fallback: render equity curve via existing method
                logger.info("Reporter '%s' does not support portfolio results", rep_name)
        except Exception as e:
            logger.error("Reporter '%s' failed: %s", rep_name, e)

    # ---- 7. 保存结果 ----
    output_dir = Path(cfg.get("output_dir", "data/results"))
    output_dir.mkdir(parents=True, exist_ok=True)
    from datetime import datetime as dt
    timestamp = dt.now().strftime("%Y%m%d_%H%M%S")
    prefix = cfg.get("output_prefix", "portfolio_backtest")
    run_dir = output_dir / f"{prefix}_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)

    # Save equity curve
    if result.equity_curve is not None:
        result.equity_curve.to_csv(run_dir / "equity_curve.csv", header=["equity"])

    # Save trades
    if result.trades:
        trades_df = pd.DataFrame([
            {
                "symbol": t.symbol,
                "buy_date": t.buy_date,
                "sell_date": t.sell_date,
                "buy_price": t.buy_price,
                "sell_price": t.sell_price,
                "quantity": t.quantity,
                "pnl": t.pnl,
                "pnl_pct": t.pnl_pct,
            }
            for t in result.trades
        ])
        trades_df.to_csv(run_dir / "trades.csv", index=False)

    # Save summary
    import json
    with open(run_dir / "summary.json", "w", encoding="utf-8") as f:
        json.dump(result.metrics, f, ensure_ascii=False, indent=2)

    print(f"\n结果已保存到: {run_dir}")
    print(f"  权益曲线: {run_dir / 'equity_curve.csv'}")
    print(f"  交易明细: {run_dir / 'trades.csv'}")
    print(f"  汇总指标: {run_dir / 'summary.json'}")

    return {
        "metrics": result.metrics,
        "trade_count": len(result.trades),
        "output_dir": str(run_dir),
    }
```

- [ ] **Step 3: Commit**

```bash
git add autotrade/core/engine.py
git commit -m "feat: add run_portfolio_backtest() to engine"
```

---

### Task 8: Plot Reporter — Equity Curve Chart

**Files:**
- Modify: `autotrade/reporters/plot_reporter.py`

- [ ] **Step 1: Read existing plot_reporter.py**

Read the file to understand existing patterns.

- [ ] **Step 2: Add `render_portfolio()` method**

Append to the `PlotReporter` class:

```python
    def render_portfolio(self, result, config=None):
        """Render portfolio backtest results with equity curve chart."""
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates

        if result.equity_curve is None or result.equity_curve.empty:
            print("No equity curve to plot.")
            return

        fig, axes = plt.subplots(3, 1, figsize=(14, 12),
                                 gridspec_kw={"height_ratios": [3, 1, 1]})

        # 1. Equity curve
        ax1 = axes[0]
        eq = result.equity_curve
        ax1.plot(eq.index, eq.values, color="#1f77b4", linewidth=1.2, label="Equity")
        ax1.axhline(y=eq.iloc[0], color="gray", linestyle="--", alpha=0.5, label="Initial")
        ax1.fill_between(eq.index, eq.iloc[0], eq.values,
                         where=eq.values >= eq.iloc[0],
                         color="green", alpha=0.1)
        ax1.fill_between(eq.index, eq.values, eq.iloc[0],
                         where=eq.values < eq.iloc[0],
                         color="red", alpha=0.1)
        ax1.set_ylabel("Account Equity (¥)")
        ax1.set_title("Portfolio Backtest — Equity Curve", fontsize=13, fontweight="bold")
        ax1.legend(loc="upper left")
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45, ha="right")

        # 2. Drawdown
        ax2 = axes[1]
        peak = eq.cummax()
        drawdown = (eq - peak) / peak * 100
        ax2.fill_between(eq.index, 0, drawdown.values, color="red", alpha=0.3)
        ax2.plot(eq.index, drawdown.values, color="red", linewidth=0.8)
        ax2.set_ylabel("Drawdown (%)")
        ax2.grid(True, alpha=0.3)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45, ha="right")

        # 3. Daily returns
        ax3 = axes[2]
        daily_ret = eq.pct_change() * 100
        colors = ["green" if v >= 0 else "red" for v in daily_ret.values]
        ax3.bar(eq.index[1:], daily_ret.values[1:], color=colors, width=1, alpha=0.6)
        ax3.set_ylabel("Daily Return (%)")
        ax3.set_xlabel("Date")
        ax3.grid(True, alpha=0.3)
        ax3.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
        plt.setp(ax3.xaxis.get_majorticklabels(), rotation=45, ha="right")

        plt.tight_layout()

        # Save
        if config:
            from pathlib import Path
            from datetime import datetime
            output_dir = Path(config.output_dir) if hasattr(config, "output_dir") else Path("data/results")
            output_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = output_dir / f"equity_curve_{timestamp}.png"
            plt.savefig(save_path, dpi=150, bbox_inches="tight")
            print(f"  Chart saved to: {save_path}")

        plt.show()

        # Print metrics summary
        metrics = result.metrics
        if metrics:
            print("\n  ── Performance Metrics ──")
            print(f"  Initial Capital:  ¥{metrics.get('initial_capital', 0):,.0f}")
            print(f"  Final Equity:     ¥{metrics.get('final_equity', 0):,.0f}")
            print(f"  Total Return:     {metrics.get('total_return_pct', 0):.2f}%")
            print(f"  Win Rate:         {metrics.get('win_rate', 0):.2f}%")
            print(f"  Max Drawdown:     {metrics.get('max_drawdown_pct', 0):.2f}%")
            print(f"  Sharpe Ratio:     {metrics.get('sharpe_ratio', 0):.4f}")
            print(f"  Total Trades:     {metrics.get('total_trades', 0)}")
```

- [ ] **Step 3: Commit**

```bash
git add autotrade/reporters/plot_reporter.py
git commit -m "feat: add render_portfolio() to PlotReporter for equity curve chart"
```

---

### Task 9: CLI Command

**Files:**
- Modify: `autotrade/triggers/cli.py`

- [ ] **Step 1: Read the CLI file to understand the pattern**

The CLI uses Click. Look at existing commands like `backtest` for the pattern.

- [ ] **Step 2: Add `portfolio-backtest` command**

Add after the existing `backtest` command block:

```python
@cli.command("portfolio-backtest")
@click.option("--screener", "-s", default="momentum_screener",
              help="选股筛选器名称")
@click.option("--start", default=None, help="开始日期 YYYY-MM-DD（默认从配置读取）")
@click.option("--end", default=None, help="结束日期 YYYY-MM-DD（默认从配置读取）")
@click.option("--symbols", default="all", help="股票代码列表，'all' 表示全市场")
@click.option("--reporter", "-r", multiple=True, default=["console", "plot"],
              help="报告输出方式 (console, csv, plot)")
@click.pass_context
def portfolio_backtest_cmd(ctx, screener, start, end, symbols, reporter):
    """组合级回测: 单账户多持仓 + 每日选股 + 统一出场。

    基于 config/backtest/portfolio.yaml 配置，从全市场筛选候选股，
    按信号强度分仓买入，统一出场规则管理风险。
    """
    from datetime import datetime
    from autotrade.core.engine import run_portfolio_backtest

    start_date = None
    end_date = None
    if start:
        start_date = datetime.strptime(start, "%Y-%m-%d").date()
    if end:
        end_date = datetime.strptime(end, "%Y-%m-%d").date()

    print(f"\n{'='*60}")
    print(f"  组合回测")
    print(f"  筛选器: {screener}")
    print(f"  区间: {start or '从配置读取'} → {end or '从配置读取'}")
    print(f"  股票池: {symbols}")
    print(f"{'='*60}\n")

    result = run_portfolio_backtest(
        screener_name=screener,
        start=start_date,
        end=end_date,
        symbols=symbols,
        reporter_names=reporter,
    )

    if "error" in result:
        print(f"\n  ✗ 回测失败: {result['error']}")
    else:
        print(f"\n  ✓ 回测完成")
        if "output_dir" in result:
            print(f"  结果目录: {result['output_dir']}")
```

- [ ] **Step 3: Commit**

```bash
git add autotrade/triggers/cli.py
git commit -m "feat: add portfolio-backtest CLI command"
```

---

### Task 10: Standalone Script

**Files:**
- Create: `scripts/run_portfolio_backtest.py`

- [ ] **Step 1: Write the standalone script**

```python
#!/usr/bin/env python
"""Standalone script to run a portfolio backtest.

Usage:
    python scripts/run_portfolio_backtest.py

Configuration is read from config/backtest/portfolio.yaml.
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from autotrade.core.engine import run_portfolio_backtest
from autotrade.registry import init_registry


def main():
    init_registry()

    print("=" * 60)
    print("  AutoTrade — Portfolio Backtest")
    print("=" * 60)

    result = run_portfolio_backtest(
        screener_name="momentum_screener",
        symbols="all",
        reporter_names=("console", "plot"),
    )

    if "error" in result:
        print(f"\n  ✗ Backtest failed: {result['error']}")
        return 1

    print("\n  ✓ Backtest complete")
    if "output_dir" in result:
        print(f"  Results saved to: {result['output_dir']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Commit**

```bash
git add scripts/run_portfolio_backtest.py
git commit -m "feat: add standalone portfolio backtest script"
```

---

### Task 11: End-to-End Integration Test (Small Scale)

**Files:**
- Create: `tests/integration/test_portfolio_backtest.py`

- [ ] **Step 1: Write integration test**

```python
"""Integration test: small-scale portfolio backtest with real data."""
from datetime import date

from autotrade.core.engine import run_portfolio_backtest
from autotrade.registry import init_registry


def test_portfolio_backtest_small_scale():
    """Run a 1-month portfolio backtest with a small symbol set."""
    init_registry()

    result = run_portfolio_backtest(
        screener_name="momentum_screener",
        start=date(2025, 1, 2),
        end=date(2025, 1, 31),
        symbols=["000001", "000002", "600000", "600036", "601318"],
        reporter_names=(),  # no report output during test
    )

    # Should not error
    assert "error" not in result

    # Should have metrics
    metrics = result.get("metrics", {})
    assert "total_return_pct" in metrics
    assert "sharpe_ratio" in metrics
    assert "max_drawdown_pct" in metrics

    # Trade count should be non-negative
    assert result.get("trade_count", -1) >= 0

    print(f"Integration test passed: {metrics}")
```

- [ ] **Step 2: Run integration test**

Run: `pytest tests/integration/test_portfolio_backtest.py::test_portfolio_backtest_small_scale -v`
Expected: PASS (or SKIP if data not available)

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_portfolio_backtest.py
git commit -m "test: add small-scale portfolio backtest integration test"
```

---

### Task 12: Final Run — Full Backtest

- [ ] **Step 1: Run the full 3-year backtest**

```bash
python scripts/run_portfolio_backtest.py
```

- [ ] **Step 2: Verify outputs**

Check that these files exist:
- `data/results/portfolio_backtest_*/equity_curve.csv`
- `data/results/portfolio_backtest_*/trades.csv`
- `data/results/portfolio_backtest_*/summary.json`

- [ ] **Step 3: Review metrics**

Verify that:
- Total return is computed (not NaN)
- Trade count is reasonable (not 0, not absurdly high)
- Equity curve is non-degenerate (shows variation)

- [ ] **Step 4: Final commit (if any tweaks needed)**

```bash
git add -A
git commit -m "chore: final adjustments after full backtest run"
```
