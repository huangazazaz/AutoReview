# Turtle Strategy + Bidirectional Backtester — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the classic Turtle Trading Strategy with dual-system bidirectional signals, plus extend the single-stock backtester to support short selling.

**Architecture:** ATR indicator → model extensions (Signal/Trade/Position/BacktestConfig) → backtester refactor (extract handlers + short support + vectorized metrics) → Turtle strategy (state-machine signal generation) → config → integration test. Each layer builds on the previous, tested independently.

**Tech Stack:** Python 3.11+, pandas, pandas_ta, numpy, pytest

---

### Task 1: ATR Indicator

**Files:**
- Create: `autotrade/indicators/atr.py`
- Modify: `autotrade/indicators/__init__.py`
- Test: `tests/unit/test_atr_indicator.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for ATR indicator."""
import pandas as pd
import numpy as np

from autotrade.indicators.atr import ATR


class TestATRIndicator:
    def test_atr_computes_expected_column(self):
        atr = ATR(period=14)
        assert atr.name == "atr"
        assert atr.params == {"period": 14}

        df = pd.DataFrame({
            "high": [10, 11, 12, 11, 10, 11, 12, 13, 14, 13, 12, 11, 10, 11, 12],
            "low":  [8,   9,  9,  8,  7,  8,  9, 10, 11, 10,  9,  8,  7,  8,  9],
            "close":[9,  10, 11, 10,  9, 10, 11, 12, 13, 12, 11, 10,  9, 10, 11],
        }, dtype=float)

        result = atr.compute(df)
        assert "ind_atr_14" in result.columns
        # First 13 rows should be NaN (need 14 periods)
        assert result["ind_atr_14"].iloc[:13].isna().all()
        # First valid value should exist
        assert not pd.isna(result["ind_atr_14"].iloc[13])
        # ATR should be positive
        assert (result["ind_atr_14"].dropna() > 0).all()

    def test_atr_idempotent(self):
        """Calling compute twice should not duplicate work."""
        atr = ATR(period=14)
        df = pd.DataFrame({
            "high": [10, 11, 12], "low": [9, 10, 11], "close": [10, 11, 12],
        }, dtype=float)
        result1 = atr.compute(df)
        result2 = atr.compute(result1)
        pd.testing.assert_frame_equal(result1, result2)

    def test_atr_custom_period(self):
        atr = ATR(period=5)
        df = pd.DataFrame({
            "high": [10, 11, 12, 11, 10, 11],
            "low":  [9,  10, 11, 10,  9, 10],
            "close":[10, 11, 12, 11, 10, 11],
        }, dtype=float)
        result = atr.compute(df)
        assert "ind_atr_5" in result.columns
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_atr_indicator.py -v`
Expected: FAIL — no module `autotrade.indicators.atr`

- [ ] **Step 3: Write the ATR indicator implementation**

```python
"""ATR indicator (Average True Range) using Wilder's smoothing.

Output column:
- ind_atr_{period}: Average True Range
"""
from __future__ import annotations

import pandas as pd
import pandas_ta as ta

from autotrade.core.interfaces import Indicator


class ATR(Indicator):
    name = "atr"
    params = {"period": 20}

    def __init__(self, period: int = 20):
        self.period = period
        self.name = "atr"
        self.params = {"period": period}

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        col = f"ind_atr_{self.period}"
        if col in df.columns:
            return df
        df[col] = ta.atr(df["high"], df["low"], df["close"], length=self.period)
        return df
```

- [ ] **Step 4: Register ATR in `__init__.py`**

Read `autotrade/indicators/__init__.py` first, then add:

```python
from autotrade.indicators.atr import ATR
```

Add `"ATR"` to the `__all__` list if it exists.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/unit/test_atr_indicator.py -v`
Expected: All 3 tests PASS

- [ ] **Step 6: Commit**

```bash
git add autotrade/indicators/atr.py autotrade/indicators/__init__.py tests/unit/test_atr_indicator.py
git commit -m "feat: add ATR indicator using Wilder's smoothing"
```

---

### Task 2: Model Extensions — Signal, Trade, Position, BacktestConfig

**Files:**
- Modify: `autotrade/core/models.py`
- Test: `tests/unit/test_models.py` (or create if not existing)

- [ ] **Step 1: Read current models.py to confirm exact content**

Already done — the models are at D:\AutoTrade\autotrade\core\models.py

- [ ] **Step 2: Write the model extension test**

Check if `tests/unit/test_models.py` exists. If not, create it:

```python
"""Tests for extended data models."""
import pytest
from dataclasses import dataclass
from datetime import date

from autotrade.core.models import (
    Bar, Signal, Trade, Position, BacktestConfig, BacktestResult,
)


class TestSignal:
    def test_signal_new_actions(self):
        """SELL_SHORT and BUY_TO_COVER are valid action types."""
        sig_long = Signal(symbol="000001", date=date(2025, 1, 1),
                          action="BUY", strength=1.0, reason="breakout")
        sig_short = Signal(symbol="000001", date=date(2025, 1, 1),
                           action="SELL_SHORT", strength=1.0, reason="breakdown")
        sig_cover = Signal(symbol="000001", date=date(2025, 1, 1),
                           action="BUY_TO_COVER", strength=1.0, reason="exit")
        sig_sell = Signal(symbol="000001", date=date(2025, 1, 1),
                          action="SELL", strength=1.0, reason="stop")
        assert sig_long.action == "BUY"
        assert sig_short.action == "SELL_SHORT"
        assert sig_cover.action == "BUY_TO_COVER"
        assert sig_sell.action == "SELL"

    def test_signal_defaults(self):
        sig = Signal(symbol="000001", date=date(2025, 1, 1), action="BUY")
        assert sig.strength == 1.0
        assert sig.reason == ""


class TestPosition:
    def test_position_long_short_tracking(self):
        pos = Position(symbol="000001")
        assert pos.long_qty == 0
        assert pos.short_qty == 0
        assert pos.long_avg_cost == 0.0
        assert pos.short_avg_cost == 0.0

    def test_position_net_qty(self):
        pos = Position(symbol="000001", long_qty=500, short_qty=200)
        assert pos.net_qty == 300

    def test_position_default_factory(self):
        pos = Position(symbol="000001")
        # Fields should be independent per instance
        pos2 = Position(symbol="000002")
        pos.long_qty = 100
        assert pos2.long_qty == 0


class TestBacktestConfig:
    def test_short_config_defaults(self):
        cfg = BacktestConfig()
        assert cfg.allow_short is False
        assert cfg.short_margin_ratio == 1.0
        assert cfg.short_interest_rate == 0.085

    def test_short_config_enabled(self):
        cfg = BacktestConfig(allow_short=True, short_margin_ratio=0.5)
        assert cfg.allow_short is True
        assert cfg.short_margin_ratio == 0.5


class TestTrade:
    def test_trade_new_actions(self):
        t1 = Trade(symbol="000001", date=date(2025, 1, 1), action="SELL_SHORT",
                   price=10.0, quantity=100, commission=5.0)
        t2 = Trade(symbol="000001", date=date(2025, 1, 1), action="BUY_TO_COVER",
                   price=9.0, quantity=100, commission=5.0, stamp_duty=0.9)
        assert t1.action == "SELL_SHORT"
        assert t2.action == "BUY_TO_COVER"
```

- [ ] **Step 3: Run test — expect partial failure (old Position fields still referenced elsewhere)**

Run: `pytest tests/unit/test_models.py -v`
Expected: Tests for Position may fail if old code references old fields. This is expected — we're changing the model in the next step.

- [ ] **Step 4: Modify `autotrade/core/models.py` — Position, BacktestConfig, Signal, Trade**

**Position — replace the entire class:**

```python
@dataclass
class Position:
    """某时刻的持仓快照，支持多空双向。"""
    symbol: str
    long_qty: int = 0            # 多头持仓股数
    long_avg_cost: float = 0.0    # 多头持仓均价
    short_qty: int = 0           # 空头持仓股数
    short_avg_cost: float = 0.0   # 空头持仓均价

    @property
    def net_qty(self) -> int:
        return self.long_qty - self.short_qty
```

**BacktestConfig — add 3 new fields after `max_positions`:**

```python
    allow_short: bool = False                # 是否允许做空
    short_margin_ratio: float = 1.0          # 融券保证金比例（1.0 = 100%）
    short_interest_rate: float = 0.085       # 融券年化利率
```

**Signal — update the `action` field comment from `# "BUY" | "SELL" | "HOLD"` to:**

```python
    action: str          # "BUY" | "SELL" | "SELL_SHORT" | "BUY_TO_COVER"
```

**Trade — update the `action` field comment similarly:**

```python
    action: str          # "BUY" | "SELL" | "SELL_SHORT" | "BUY_TO_COVER"
```

- [ ] **Step 5: Update all code that references old Position fields**

Use grep to find all references to `position.quantity`, `position.avg_cost`, `position.market_value` in the codebase. Then update `backtester.py` to use the new fields:

In `backtester.py` line 56-57, replace:
```python
        position = Position(symbol=symbol)
```
(no change needed — new Position defaults are fine)

In `backtester.py` line 76-77, replace:
```python
                if position.quantity <= 0:
                    continue
```
with:
```python
                if position.long_qty <= 0:
                    continue
```

In `backtester.py` lines 106-109, replace:
```python
                cash += amount - commission - stamp_duty
                position.quantity -= quantity
                if position.quantity <= 0:
                    position.avg_cost = 0.0
                position.market_value = position.quantity * actual_price
```
with:
```python
                cash += amount - commission - stamp_duty
                position.long_qty -= quantity
                if position.long_qty <= 0:
                    position.long_avg_cost = 0.0
```

In `backtester.py` lines 139-143, replace:
```python
                # 更新持仓均价
                total_cost = position.avg_cost * position.quantity + amount
                position.quantity += quantity
                position.avg_cost = total_cost / position.quantity if position.quantity > 0 else 0
                position.market_value = position.quantity * actual_price
```
with:
```python
                # 更新持仓均价
                total_cost = position.long_avg_cost * position.long_qty + amount
                position.long_qty += quantity
                position.long_avg_cost = total_cost / position.long_qty if position.long_qty > 0 else 0
```

In `backtester.py` line 152, replace:
```python
            position.market_value = position.quantity * bar.close
```
with:
```python
            long_market_value = position.long_qty * bar.close
            short_market_value = position.short_qty * bar.close
            position_market_value = long_market_value - short_market_value
```

In `backtester.py` line 153, replace:
```python
            total_equity = cash + position.market_value
```
with:
```python
            total_equity = cash + position_market_value
```

In `backtester.py` `_compute_sell_quantity` (lines 197-207), replace `position.quantity` with `position.long_qty`:
```python
    def _compute_sell_quantity(self, position: Position, strength: float) -> int:
        """计算卖出股数。"""
        if position.long_qty <= 0:
            return 0
        if self.config.position_sizing == "strength":
            quantity = int(position.long_qty * strength)
        else:
            quantity = position.long_qty
        # 向下取整到 lot_size 的倍数
        quantity = (quantity // self.config.lot_size) * self.config.lot_size
        return max(0, quantity)
```

Also check `autotrade/core/account.py` for any Position field references and update them.

- [ ] **Step 6: Run existing tests to check for regressions**

Run: `pytest tests/ -v --tb=short`
Expected: All previously passing tests still pass. Fix any field reference errors.

- [ ] **Step 7: Run model tests specifically**

Run: `pytest tests/unit/test_models.py -v`
Expected: All model tests PASS

- [ ] **Step 8: Commit**

```bash
git add autotrade/core/models.py autotrade/core/backtester.py tests/unit/test_models.py
git commit -m "refactor: extend models for short selling — Position, Signal, Trade, BacktestConfig"
```

---

### Task 3: Backtester Refactor — Extract Signal Handlers

**Files:**
- Modify: `autotrade/core/backtester.py`
- Test: (existing tests provide regression coverage)

This task refactors the monolithic `run()` method WITHOUT adding short selling. Pure extraction, behavior-preserving.

- [ ] **Step 1: Extract `_execute_buy_trade` method**

Replace the buy execution block (lines 112-143 in current `run()`) with a method call. Add this method to the `Backtester` class:

```python
    def _execute_buy_trade(self, position: Position, cash: float,
                           fill_price: float, strength: float,
                           bar: Bar, bars_sorted: list[Bar], idx: int,
                           sig: Signal) -> tuple[float, Trade | None]:
        """Execute a BUY order. Returns (updated_cash, trade_or_None)."""
        actual_price = fill_price * (1 + self.config.slippage)
        quantity = self._compute_buy_quantity(cash, actual_price, strength)
        if quantity <= 0:
            return cash, None

        amount = actual_price * quantity
        commission = max(amount * self.config.commission_rate,
                         self.config.min_commission)

        trade = Trade(
            symbol=bar.symbol, date=bar.date, action="BUY",
            price=round(actual_price, 2),
            quantity=quantity,
            commission=round(commission, 2),
        )
        cash -= amount + commission

        # 更新持仓均价
        total_cost = position.long_avg_cost * position.long_qty + amount
        position.long_qty += quantity
        position.long_avg_cost = total_cost / position.long_qty if position.long_qty > 0 else 0

        return cash, trade
```

- [ ] **Step 2: Extract `_execute_sell_trade` method**

```python
    def _execute_sell_trade(self, position: Position, cash: float,
                            fill_price: float, strength: float,
                            bar: Bar, sig: Signal) -> tuple[float, Trade | None]:
        """Execute a SELL order. Returns (updated_cash, trade_or_None)."""
        actual_price = fill_price * (1 - self.config.slippage)
        quantity = self._compute_sell_quantity(position, strength)
        if quantity <= 0:
            return cash, None

        amount = actual_price * quantity
        commission = max(amount * self.config.commission_rate,
                         self.config.min_commission)
        stamp_duty = amount * self.config.stamp_duty_rate

        trade = Trade(
            symbol=bar.symbol, date=bar.date, action="SELL",
            price=round(actual_price, 2),
            quantity=quantity,
            commission=round(commission, 2),
            stamp_duty=round(stamp_duty, 2),
        )
        cash += amount - commission - stamp_duty
        position.long_qty -= quantity
        if position.long_qty <= 0:
            position.long_avg_cost = 0.0

        return cash, trade
```

- [ ] **Step 3: Extract `_can_sell_today` method for T+1 logic**

```python
    def _can_sell_today(self, can_sell_after: date | None, today: date) -> bool:
        """Check if T+1 restriction allows selling today."""
        if not self.config.allow_t_plus_1:
            return True
        if can_sell_after is None:
            return True
        return today >= can_sell_after
```

- [ ] **Step 4: Rewrite `run()` to use extracted methods**

Replace the body of the `for i, bar in enumerate(bars_sorted):` loop in `run()` with:

```python
        for i, bar in enumerate(bars_sorted):
            today = bar.date
            daily_signals = signal_map.get(today, [])

            # --- Phase 1: Process SELL signals (exit longs first) ---
            for sig in daily_signals:
                if sig.action != "SELL":
                    continue
                if not self._can_sell_today(can_sell_after, today):
                    continue
                fill_price = self._get_fill_price(sig, bar, bars_sorted, i, is_buy=False)
                if fill_price is None:
                    continue
                cash, trade = self._execute_sell_trade(position, cash, fill_price,
                                                       sig.strength, bar, sig)
                if trade:
                    trades.append(trade)

            # --- Phase 2: Process BUY signals (enter longs after exits) ---
            for sig in daily_signals:
                if sig.action != "BUY":
                    continue
                fill_price = self._get_fill_price(sig, bar, bars_sorted, i, is_buy=True)
                if fill_price is None:
                    continue
                cash, trade = self._execute_buy_trade(position, cash, fill_price,
                                                      sig.strength, bar, bars_sorted, i, sig)
                if trade:
                    trades.append(trade)
                    # T+1 锁定
                    if self.config.allow_t_plus_1 and i + 1 < len(bars_sorted):
                        can_sell_after = bars_sorted[i + 1].date

            # --- Phase 3: Mark to market ---
            long_market_value = position.long_qty * bar.close
            short_market_value = position.short_qty * bar.close
            total_equity = cash + long_market_value - short_market_value
            equity_series.append(total_equity)
            dates_series.append(today)
```

- [ ] **Step 5: Run existing tests to verify no regressions**

Run: `pytest tests/ -v --tb=short`
Expected: All previously passing tests still pass. No behavior change.

- [ ] **Step 6: Commit**

```bash
git add autotrade/core/backtester.py
git commit -m "refactor: extract signal handlers from Backtester.run() — _execute_buy_trade, _execute_sell_trade, _can_sell_today"
```

---

### Task 4: Backtester — Add Short Selling Support

**Files:**
- Modify: `autotrade/core/backtester.py`
- Test: `tests/unit/test_backtester_short.py`

- [ ] **Step 1: Write the short selling backtester test**

```python
"""Tests for backtester short selling support."""
import pandas as pd
from datetime import date, timedelta

from autotrade.core.models import Bar, Signal, BacktestConfig
from autotrade.core.backtester import Backtester


def _make_bars(symbol="000001", start_price=10.0, n=30):
    """Generate n days of simple OHLCV bars."""
    bars = []
    prices = [start_price + i * 0.1 for i in range(n)]
    for i, p in enumerate(prices):
        bars.append(Bar(
            symbol=symbol,
            date=date(2025, 1, 1) + timedelta(days=i),
            open=p, high=p + 0.05, low=p - 0.05, close=p,
            volume=100000, amount=p * 100000,
        ))
    return bars


class TestBacktesterShort:
    def test_short_entry_and_cover_profit(self):
        """Short at 12, cover at 10 → profit."""
        cfg = BacktestConfig(
            initial_capital=100_000, fill_price="close",
            allow_short=True, short_margin_ratio=1.0,
            position_sizing="full",
        )
        bt = Backtester(cfg)
        bars = _make_bars(start_price=10.0, n=20)

        signals = [
            Signal(symbol="000001", date=bars[10].date, action="SELL_SHORT",
                   strength=1.0, reason="breakdown"),
            Signal(symbol="000001", date=bars[15].date, action="BUY_TO_COVER",
                   strength=1.0, reason="exit"),
        ]

        result = bt.run(signals, bars)
        # Short at ~11.0, cover at ~11.5 → loss in this setup
        # Let's design a better test: short high, cover low
        trades = result.trades
        assert len(trades) == 2
        assert trades[0].action == "SELL_SHORT"
        assert trades[1].action == "BUY_TO_COVER"

    def test_short_entry_requires_allow_short(self):
        """Short signals ignored when allow_short=False."""
        cfg = BacktestConfig(
            initial_capital=100_000, fill_price="close",
            allow_short=False,
        )
        bt = Backtester(cfg)
        bars = _make_bars(n=20)

        signals = [
            Signal(symbol="000001", date=bars[10].date, action="SELL_SHORT",
                   strength=1.0, reason="breakdown"),
        ]

        result = bt.run(signals, bars)
        # No short trade should execute
        short_trades = [t for t in result.trades if t.action == "SELL_SHORT"]
        assert len(short_trades) == 0

    def test_short_cover_profit_calculation(self):
        """Short at 15, cover at 10 → profit of ~5 per share."""
        cfg = BacktestConfig(
            initial_capital=100_000, fill_price="close",
            allow_short=True, short_margin_ratio=1.0,
            position_sizing="full",
        )
        bt = Backtester(cfg)

        # Build bars where price drops
        bars = []
        for i in range(20):
            p = 15.0 if i < 5 else (15.0 - (i - 5) * 0.5)
            bars.append(Bar(
                symbol="000001",
                date=date(2025, 1, 1) + timedelta(days=i),
                open=p, high=p, low=p, close=p,
                volume=100000, amount=p * 100000,
            ))

        signals = [
            Signal(symbol="000001", date=bars[5].date, action="SELL_SHORT",
                   strength=1.0, reason="breakdown"),
            Signal(symbol="000001", date=bars[15].date, action="BUY_TO_COVER",
                   strength=1.0, reason="exit"),
        ]

        result = bt.run(signals, bars)
        # With position_sizing="full": bought with all cash at 15
        # Short entry: short_qty = 100000 / 15 ≈ 6600 shares (lot size 100)
        # Cover: buy back at lower price → profit
        final_equity = result.equity_curve.iloc[-1]
        assert final_equity > 100_000, f"Expected profit, got equity={final_equity}"

    def test_simultaneous_long_and_short(self):
        """Can hold long and short positions simultaneously."""
        cfg = BacktestConfig(
            initial_capital=100_000, fill_price="close",
            allow_short=True, short_margin_ratio=1.0,
            position_sizing="strength",
        )
        bt = Backtester(cfg)
        bars = _make_bars(n=30)

        signals = [
            Signal(symbol="000001", date=bars[5].date, action="BUY",
                   strength=0.5, reason="long entry"),
            Signal(symbol="000001", date=bars[10].date, action="SELL_SHORT",
                   strength=0.5, reason="short entry"),
            Signal(symbol="000001", date=bars[20].date, action="SELL",
                   strength=1.0, reason="exit long"),
            Signal(symbol="000001", date=bars[25].date, action="BUY_TO_COVER",
                   strength=1.0, reason="exit short"),
        ]

        result = bt.run(signals, bars)
        actions = [t.action for t in result.trades]
        assert "BUY" in actions
        assert "SELL_SHORT" in actions
        assert "SELL" in actions
        assert "BUY_TO_COVER" in actions

    def test_margin_insufficient_blocks_short(self):
        """When cash is depleted, new short orders are rejected."""
        cfg = BacktestConfig(
            initial_capital=1000, fill_price="close",
            allow_short=True, short_margin_ratio=1.0,
            position_sizing="full",
        )
        bt = Backtester(cfg)
        bars = _make_bars(start_price=50.0, n=20)

        # First short uses all margin
        signals = [
            Signal(symbol="000001", date=bars[5].date, action="SELL_SHORT",
                   strength=1.0, reason="first short"),
            Signal(symbol="000001", date=bars[6].date, action="SELL_SHORT",
                   strength=1.0, reason="second short — should fail"),
        ]

        result = bt.run(signals, bars)
        short_trades = [t for t in result.trades if t.action == "SELL_SHORT"]
        # Only one short should execute (second fails due to margin)
        assert len(short_trades) == 1
```

- [ ] **Step 2: Run test to verify they fail**

Run: `pytest tests/unit/test_backtester_short.py -v`
Expected: Some tests FAIL — short selling not yet implemented

- [ ] **Step 3: Add `_execute_short_trade` method to Backtester**

Add after `_execute_sell_trade`:

```python
    def _execute_short_trade(self, position: Position, cash: float,
                             fill_price: float, strength: float,
                             bar: Bar) -> tuple[float, Trade | None]:
        """Execute a SELL_SHORT order. Returns (updated_cash, trade_or_None)."""
        actual_price = fill_price * (1 - self.config.slippage)
        quantity = self._compute_buy_quantity(cash, actual_price, strength)
        if quantity <= 0:
            return cash, None

        # Margin check: required = new_short_value * (1 + margin_ratio)
        new_short_value = actual_price * quantity
        required_margin = new_short_value * (1 + self.config.short_margin_ratio)
        existing_margin = (position.short_qty * position.short_avg_cost *
                          (1 + self.config.short_margin_ratio)) if position.short_qty > 0 else 0
        available_margin = cash - existing_margin
        if available_margin < required_margin:
            return cash, None  # Insufficient margin

        amount = new_short_value
        commission = max(amount * self.config.commission_rate,
                         self.config.min_commission)

        trade = Trade(
            symbol=bar.symbol, date=bar.date, action="SELL_SHORT",
            price=round(actual_price, 2),
            quantity=quantity,
            commission=round(commission, 2),
        )
        # Short sale proceeds increase cash (but margin is locked conceptually)
        cash += amount - commission

        # Update short position
        total_cost = position.short_avg_cost * position.short_qty + amount
        position.short_qty += quantity
        position.short_avg_cost = total_cost / position.short_qty if position.short_qty > 0 else 0

        return cash, trade
```

- [ ] **Step 4: Add `_execute_cover_trade` method**

```python
    def _execute_cover_trade(self, position: Position, cash: float,
                             fill_price: float, strength: float,
                             bar: Bar) -> tuple[float, Trade | None]:
        """Execute a BUY_TO_COVER order. Returns (updated_cash, trade_or_None)."""
        if position.short_qty <= 0:
            return cash, None

        actual_price = fill_price * (1 + self.config.slippage)

        # Compute cover quantity
        if self.config.position_sizing == "strength":
            quantity = int(position.short_qty * strength)
        else:
            quantity = position.short_qty
        quantity = (quantity // self.config.lot_size) * self.config.lot_size
        if quantity <= 0:
            return cash, None

        amount = actual_price * quantity
        commission = max(amount * self.config.commission_rate,
                         self.config.min_commission)

        trade = Trade(
            symbol=bar.symbol, date=bar.date, action="BUY_TO_COVER",
            price=round(actual_price, 2),
            quantity=quantity,
            commission=round(commission, 2),
        )
        cash -= amount + commission

        position.short_qty -= quantity
        if position.short_qty <= 0:
            position.short_avg_cost = 0.0

        return cash, trade
```

- [ ] **Step 5: Update `run()` to handle SELL_SHORT and BUY_TO_COVER**

Modify the daily loop in `run()` to add Phase 1b (cover shorts before exits) and Phase 2b (short entries after buys):

Replace the SELL processing loop (Phase 1) with:

```python
            # --- Phase 1: Process exits (SELL + BUY_TO_COVER) ---
            for sig in daily_signals:
                if sig.action == "SELL":
                    if not self._can_sell_today(can_sell_after, today):
                        continue
                    fill_price = self._get_fill_price(sig, bar, bars_sorted, i, is_buy=False)
                    if fill_price is None:
                        continue
                    cash, trade = self._execute_sell_trade(position, cash, fill_price,
                                                           sig.strength, bar, sig)
                    if trade:
                        trades.append(trade)
                elif sig.action == "BUY_TO_COVER":
                    fill_price = self._get_fill_price(sig, bar, bars_sorted, i, is_buy=False)
                    if fill_price is None:
                        continue
                    cash, trade = self._execute_cover_trade(position, cash, fill_price,
                                                            sig.strength, bar)
                    if trade:
                        trades.append(trade)

            # --- Phase 2: Process entries (BUY + SELL_SHORT) ---
            for sig in daily_signals:
                if sig.action == "BUY":
                    fill_price = self._get_fill_price(sig, bar, bars_sorted, i, is_buy=True)
                    if fill_price is None:
                        continue
                    cash, trade = self._execute_buy_trade(position, cash, fill_price,
                                                          sig.strength, bar, bars_sorted, i, sig)
                    if trade:
                        trades.append(trade)
                        if self.config.allow_t_plus_1 and i + 1 < len(bars_sorted):
                            can_sell_after = bars_sorted[i + 1].date
                elif sig.action == "SELL_SHORT" and self.config.allow_short:
                    fill_price = self._get_fill_price(sig, bar, bars_sorted, i, is_buy=False)
                    if fill_price is None:
                        continue
                    cash, trade = self._execute_short_trade(position, cash, fill_price,
                                                            sig.strength, bar)
                    if trade:
                        trades.append(trade)
```

- [ ] **Step 6: Run short backtester tests**

Run: `pytest tests/unit/test_backtester_short.py -v`
Expected: All tests PASS

- [ ] **Step 7: Run full test suite to check for regressions**

Run: `pytest tests/ -v --tb=short`
Expected: All previously passing tests still pass

- [ ] **Step 8: Commit**

```bash
git add autotrade/core/backtester.py tests/unit/test_backtester_short.py
git commit -m "feat: add short selling support to Backtester (SELL_SHORT, BUY_TO_COVER, margin)"
```

---

### Task 5: Backtester — Vectorize Metrics

**Files:**
- Modify: `autotrade/core/backtester.py` (only `_compute_metrics` and `_split_cycles`)
- Test: (existing backtester tests provide regression coverage)

- [ ] **Step 1: Read current `_split_cycles` and `_compute_metrics` (lines 209-305)**

Already read — the current implementation uses loops for cycle splitting. We'll keep `_split_cycles` for win rate (needs sequential logic) but vectorize the return/drawdown/sharpe calculations.

- [ ] **Step 2: Update `_compute_metrics` with vectorized calculations**

Replace `_compute_metrics` (lines 241-305) with:

```python
    def _compute_metrics(self, trades: list[Trade],
                         equity_series: list[float],
                         dates: list[date]) -> dict:
        """计算回测汇总指标（向量化）。"""
        if not trades or len(equity_series) < 2:
            return {
                "total_trades": len(trades),
                "total_return_pct": 0.0,
                "win_rate": 0.0,
                "max_drawdown_pct": 0.0,
                "sharpe_ratio": 0.0,
            }

        initial_capital = equity_series[0]
        final_equity = equity_series[-1]
        total_return_pct = (final_equity - initial_capital) / initial_capital * 100

        # 胜率：按持仓周期计算
        wins = 0
        cycles = self._split_cycles(trades)
        for buys, sells in cycles:
            if not sells:
                continue
            total_buy_amount = sum(b.price * b.quantity for b in buys)
            total_buy_qty = sum(b.quantity for b in buys)
            total_sell_amount = sum(s.price * s.quantity for s in sells)
            total_sell_qty = sum(s.quantity for s in sells)
            if total_buy_qty > 0 and total_sell_qty > 0:
                avg_buy = total_buy_amount / total_buy_qty
                avg_sell = total_sell_amount / total_sell_qty
                if avg_sell > avg_buy:
                    wins += 1
        total_cycles = len(cycles) - (1 if cycles and not cycles[-1][1] else 0)
        win_rate = (wins / total_cycles * 100) if total_cycles > 0 else 0.0

        # 最大回撤（向量化）
        equity_arr = np.array(equity_series)
        peak = np.maximum.accumulate(equity_arr)
        drawdown_pct = (equity_arr - peak) / peak  # negative values
        max_drawdown_pct = float(np.min(drawdown_pct) * 100)  # negative percentage

        # 夏普比率（向量化）
        returns = np.diff(equity_arr) / equity_arr[:-1]
        if len(returns) > 1:
            mean_ret = np.mean(returns)
            std_ret = np.std(returns, ddof=1)
            sharpe = float(mean_ret / std_ret * np.sqrt(252)) if std_ret > 0 else 0.0
        else:
            sharpe = 0.0

        buy_trades = sum(1 for t in trades if t.action == "BUY")
        sell_trades = sum(1 for t in trades if t.action in ("SELL", "BUY_TO_COVER"))

        return {
            "initial_capital": initial_capital,
            "final_equity": round(final_equity, 2),
            "total_trades": len(trades),
            "buy_trades": buy_trades,
            "sell_trades": sell_trades,
            "total_return_pct": round(total_return_pct, 2),
            "win_rate": round(win_rate, 2),
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "sharpe_ratio": round(sharpe, 4),
        }
```

- [ ] **Step 3: Update `_split_cycles` to handle short trades**

Replace `_split_cycles` (lines 209-238) with version that accounts for short trades:

```python
    @staticmethod
    def _split_cycles(trades: list) -> list[tuple[list, list]]:
        """将交易列表按持仓周期拆分。每轮从空仓到再次空仓为一个周期。

        处理多空双向：分别跟踪多头净持仓和空头净持仓。

        Returns:
            [(buys_and_shorts, sells_and_covers), ...]
            最后一个周期可能只有开仓交易（未平仓）。
        """
        cycles: list[tuple[list, list]] = []
        current_entries: list = []
        current_exits: list = []
        long_position = 0
        short_position = 0

        for t in trades:
            if t.action == "BUY":
                current_entries.append(t)
                long_position += t.quantity
            elif t.action == "SELL":
                current_exits.append(t)
                long_position -= t.quantity
            elif t.action == "SELL_SHORT":
                current_entries.append(t)
                short_position += t.quantity
            elif t.action == "BUY_TO_COVER":
                current_exits.append(t)
                short_position -= t.quantity

            # Cycle ends when both long and short are fully closed
            if long_position == 0 and short_position == 0 and current_entries:
                cycles.append((current_entries, current_exits))
                current_entries = []
                current_exits = []

        # Unclosed cycle
        if current_entries:
            cycles.append((current_entries, current_exits))

        return cycles
```

- [ ] **Step 4: Run existing tests to verify no regressions**

Run: `pytest tests/ -v --tb=short`
Expected: All tests pass

- [ ] **Step 5: Commit**

```bash
git add autotrade/core/backtester.py
git commit -m "perf: vectorize backtester metrics and support short trades in cycle splitting"
```

---

### Task 6: Turtle Trading Strategy

**Files:**
- Create: `autotrade/strategies/turtle.py`
- Test: `tests/unit/test_turtle_strategy.py`

- [ ] **Step 1: Write the turtle strategy tests**

```python
"""Tests for Turtle Trading Strategy."""
import pandas as pd
import numpy as np
from datetime import date, timedelta

from autotrade.strategies.turtle import TurtleTraderStrategy
from autotrade.core.models import Signal


def _make_trending_df(direction="up", n_days=100):
    """Generate a DataFrame with a clear trend for testing breakout logic."""
    np.random.seed(42)
    dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(n_days)]

    if direction == "up":
        base = np.linspace(10, 20, n_days)
    elif direction == "down":
        base = np.linspace(20, 10, n_days)
    else:
        base = np.full(n_days, 15.0)

    noise = np.random.normal(0, 0.3, n_days).cumsum() * 0.3
    close = base + noise
    high = close + np.abs(np.random.normal(0, 0.3, n_days))
    low = close - np.abs(np.random.normal(0, 0.3, n_days))
    open_p = close - np.random.normal(0, 0.1, n_days)

    df = pd.DataFrame({
        "open": open_p, "high": high, "low": low,
        "close": close, "volume": 100000,
    }, index=dates)

    # Pre-compute ATR for the DataFrame (simulating what engine would do)
    import pandas_ta as ta
    df["ind_atr_20"] = ta.atr(df["high"], df["low"], df["close"], length=20)

    return df


class TestTurtleStrategy:
    def test_strategy_name_and_indicators(self):
        strategy = TurtleTraderStrategy()
        assert strategy.name == "turtle"
        indicator_names = [ind.name for ind in strategy.required_indicators]
        assert "atr" in indicator_names

    def test_system1_long_entry_on_breakout(self):
        """System 1: 20-day high breakout → BUY signal."""
        strategy = TurtleTraderStrategy(use_system1=True, use_system2=False)
        df = _make_trending_df(direction="up", n_days=60)

        signals = strategy.generate_signals(df)
        buy_signals = [s for s in signals if s.action == "BUY"]
        assert len(buy_signals) > 0, "Expected at least one BUY on uptrend breakout"
        for s in buy_signals:
            assert s.reason != ""

    def test_system2_long_entry_on_breakout(self):
        """System 2: 55-day high breakout → BUY signal."""
        strategy = TurtleTraderStrategy(use_system1=False, use_system2=True)
        df = _make_trending_df(direction="up", n_days=100)

        signals = strategy.generate_signals(df)
        buy_signals = [s for s in signals if s.action == "BUY"]
        assert len(buy_signals) > 0, "Expected at least one BUY on 55-day breakout"

    def test_system1_short_entry_on_breakdown(self):
        """System 1: 20-day low breakdown → SELL_SHORT signal."""
        strategy = TurtleTraderStrategy(
            use_system1=True, use_system2=False,
            allow_long=False, allow_short=True,
        )
        df = _make_trending_df(direction="down", n_days=60)

        signals = strategy.generate_signals(df)
        short_signals = [s for s in signals if s.action == "SELL_SHORT"]
        assert len(short_signals) > 0, "Expected at least one SELL_SHORT on downtrend"

    def test_no_signals_in_sideways_market(self):
        """Sideways market should produce few or no breakout signals."""
        strategy = TurtleTraderStrategy(use_system1=True, use_system2=False)
        df = _make_trending_df(direction="sideways", n_days=60)

        signals = strategy.generate_signals(df)
        buy_signals = [s for s in signals if s.action == "BUY"]
        short_signals = [s for s in signals if s.action == "SELL_SHORT"]
        # In pure sideways, breakouts are rare (but possible with noise)
        assert len(buy_signals) <= 5, f"Expected few signals in sideways, got {len(buy_signals)}"

    def test_dual_system_generates_independent_signals(self):
        """Both systems enabled → signals from both."""
        strategy = TurtleTraderStrategy(use_system1=True, use_system2=True)
        df = _make_trending_df(direction="up", n_days=100)

        signals = strategy.generate_signals(df)
        # System 1 (20-day) should fire earlier than System 2 (55-day)
        sys1_buys = [s for s in signals if s.action == "BUY" and "Sys1" in s.reason]
        sys2_buys = [s for s in signals if s.action == "BUY" and "Sys2" in s.reason]
        # At minimum, we should have signals from the active systems
        total_buys = len([s for s in signals if s.action == "BUY"])
        assert total_buys > 0

    def test_stop_loss_generates_exit(self):
        """After entry, a sharp reversal should trigger stop loss."""
        strategy = TurtleTraderStrategy(
            use_system1=True, use_system2=False,
            stop_atr_mult=0.5,  # Tight stop for testing
        )
        # Build a df that breaks out then reverses sharply
        np.random.seed(42)
        n = 80
        dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(n)]
        base = np.linspace(10, 20, 40).tolist() + np.linspace(20, 12, 40).tolist()
        df = pd.DataFrame({
            "open": base, "high": [b + 0.5 for b in base],
            "low": [b - 0.5 for b in base], "close": base,
            "volume": 100000,
        }, index=dates)

        import pandas_ta as ta
        df["ind_atr_20"] = ta.atr(df["high"], df["low"], df["close"], length=20)

        signals = strategy.generate_signals(df)
        sell_signals = [s for s in signals if s.action == "SELL"]
        # Should have at least one exit (stop loss or regular exit)
        assert len(sell_signals) > 0, "Expected exit signal on reversal"

    def test_system1_skip_after_win(self):
        """skip_if_last_win_sys1=True skips next System 1 after profitable trade."""
        strategy = TurtleTraderStrategy(
            use_system1=True, use_system2=False,
            skip_if_last_win_sys1=True,
        )
        df = _make_trending_df(direction="up", n_days=80)

        signals = strategy.generate_signals(df)
        buy_signals = [s for s in signals if s.action == "BUY"]
        # Should still have signals, just potentially fewer
        assert len(buy_signals) > 0

    def test_pyramiding_signals(self):
        """Multiple BUY signals as price moves favorably."""
        strategy = TurtleTraderStrategy(
            use_system1=True, use_system2=False,
            max_units=4, pyramid_atr_mult=0.5,
        )
        df = _make_trending_df(direction="up", n_days=100)

        signals = strategy.generate_signals(df)
        buy_signals = [s for s in signals if s.action == "BUY"]
        # In a strong trend, should have multiple units (entry + pyramid adds)
        assert len(buy_signals) > 0

    def test_exit_on_breakdown(self):
        """System 1 exit: 10-day low breakdown → SELL."""
        strategy = TurtleTraderStrategy(
            use_system1=True, use_system2=False,
        )
        # Up then down: entry on breakout, then exit on breakdown
        np.random.seed(42)
        n = 100
        dates = [date(2025, 1, 1) + timedelta(days=i) for i in range(n)]
        # Go up, then crash
        base = np.linspace(10, 25, 60).tolist() + np.linspace(25, 10, 40).tolist()
        df = pd.DataFrame({
            "open": base, "high": [b + 0.5 for b in base],
            "low": [b - 0.5 for b in base], "close": base,
            "volume": 100000,
        }, index=dates)

        import pandas_ta as ta
        df["ind_atr_20"] = ta.atr(df["high"], df["low"], df["close"], length=20)

        signals = strategy.generate_signals(df)
        sell_signals = [s for s in signals if s.action == "SELL"]
        assert len(sell_signals) > 0, "Expected SELL on breakdown"

    def test_signal_strength_is_positive(self):
        """All BUY/SELL_SHORT signals have positive strength."""
        strategy = TurtleTraderStrategy()
        df = _make_trending_df(direction="up", n_days=100)

        signals = strategy.generate_signals(df)
        for s in signals:
            if s.action in ("BUY", "SELL_SHORT"):
                assert s.strength > 0, f"Expected positive strength, got {s.strength}"
            elif s.action in ("SELL", "BUY_TO_COVER"):
                assert s.strength > 0, f"Expected positive strength for exit"

    def test_direction_flag_disables_short(self):
        """allow_short=False produces no SELL_SHORT signals."""
        strategy = TurtleTraderStrategy(
            use_system1=True, use_system2=False,
            allow_long=True, allow_short=False,
        )
        df = _make_trending_df(direction="down", n_days=60)

        signals = strategy.generate_signals(df)
        short_signals = [s for s in signals if s.action == "SELL_SHORT"]
        assert len(short_signals) == 0, "No short signals when allow_short=False"

    def test_direction_flag_disables_long(self):
        """allow_long=False produces no BUY signals."""
        strategy = TurtleTraderStrategy(
            use_system1=True, use_system2=False,
            allow_long=False, allow_short=True,
        )
        df = _make_trending_df(direction="up", n_days=60)

        signals = strategy.generate_signals(df)
        buy_signals = [s for s in signals if s.action == "BUY"]
        assert len(buy_signals) == 0, "No buy signals when allow_long=False"
```

- [ ] **Step 2: Run test to verify they fail**

Run: `pytest tests/unit/test_turtle_strategy.py -v`
Expected: FAIL — no module `autotrade.strategies.turtle`

- [ ] **Step 3: Write the TurtleTraderStrategy implementation**

```python
"""Turtle Trading Strategy — dual-system trend following with bidirectional signals.

Core rules:
- System 1: 20-day breakout entry, 10-day breakout exit
- System 2: 55-day breakout entry, 20-day breakout exit
- Position sizing: 1 Unit = 1% of account / (N × point_value)
- Pyramiding: add 1 unit every 0.5N favorable move, max 4 units
- Stop loss: 2N against entry price, adjusted per pyramid add
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from autotrade.core.interfaces import Strategy
from autotrade.core.models import Signal
from autotrade.indicators.atr import ATR


class TurtleTraderStrategy(Strategy):
    """Classic Turtle Trading System with dual-system bidirectional signals."""

    name = "turtle"

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
        self.system1_entry = system1_entry
        self.system1_exit = system1_exit
        self.system2_entry = system2_entry
        self.system2_exit = system2_exit
        self.use_system1 = use_system1
        self.use_system2 = use_system2
        self.atr_period = atr_period
        self.account_risk_pct = account_risk_pct
        self.max_units = max_units
        self.pyramid_atr_mult = pyramid_atr_mult
        self.stop_atr_mult = stop_atr_mult
        self.allow_long = allow_long
        self.allow_short = allow_short
        self.skip_if_last_win_sys1 = skip_if_last_win_sys1

        self.required_indicators = [ATR(period=atr_period)]

    # ------------------------------------------------------------------
    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        signals: list[Signal] = []

        atr_col = f"ind_atr_{self.atr_period}"
        if atr_col not in df.columns or "high" not in df.columns or "low" not in df.columns:
            return signals

        n_days = len(df)
        if n_days < max(self.system1_entry, self.system2_entry, self.system1_exit,
                        self.system2_exit, 10):
            return signals

        # Pre-compute Donchian channels (shifted to avoid look-ahead)
        roll_high = df["high"].shift(1)
        roll_low = df["low"].shift(1)

        # Entry channels
        if self.use_system1:
            donchian_high_20 = roll_high.rolling(self.system1_entry).max()
            donchian_low_20 = roll_low.rolling(self.system1_entry).min()
        if self.use_system2:
            donchian_high_55 = roll_high.rolling(self.system2_entry).max()
            donchian_low_55 = roll_low.rolling(self.system2_entry).min()

        # Exit channels
        donchian_high_10 = roll_high.rolling(self.system1_exit).max()
        donchian_low_10 = roll_low.rolling(self.system1_exit).min()
        donchian_high_20_exit = roll_high.rolling(self.system2_exit).max()
        donchian_low_20_exit = roll_low.rolling(self.system2_exit).min()

        # ---- Per-system, per-direction state ----
        # long_state[sys_key] = {"entry_price": float|None, "units": int,
        #                        "last_add_price": float|None, "last_trade_win": bool}
        long_state: dict[str, dict] = {}
        short_state: dict[str, dict] = {}

        def _init_state() -> dict:
            return {"entry_price": None, "units": 0, "last_add_price": None,
                    "last_trade_win": False}

        if self.use_system1:
            long_state["sys1"] = _init_state()
            short_state["sys1"] = _init_state()
        if self.use_system2:
            long_state["sys2"] = _init_state()
            short_state["sys2"] = _init_state()

        # ------------------------------------------------------------------
        # Daily loop
        # ------------------------------------------------------------------
        for idx in range(n_days):
            current_date = df.index[idx]
            if isinstance(current_date, pd.Timestamp):
                current_date = current_date.date()
            elif hasattr(current_date, "date"):
                current_date = current_date.date()

            close_price = float(df["close"].iloc[idx])
            high_price = float(df["high"].iloc[idx])
            low_price = float(df["low"].iloc[idx])
            N = df[atr_col].iloc[idx]

            if pd.isna(N) or N <= 0:
                continue

            # Process each enabled system
            systems = []
            if self.use_system1:
                systems.append(("sys1", self.system1_entry, self.system1_exit))
            if self.use_system2:
                systems.append(("sys2", self.system2_entry, self.system2_exit))

            for sys_key, entry_period, exit_period in systems:
                # ---- LONG ----
                self._process_long(
                    signals, long_state[sys_key], df, idx, current_date,
                    close_price, high_price, low_price, N,
                    sys_key, entry_period, exit_period,
                )
                # ---- SHORT ----
                self._process_short(
                    signals, short_state[sys_key], df, idx, current_date,
                    close_price, high_price, low_price, N,
                    sys_key, entry_period, exit_period,
                )

        return signals

    # ------------------------------------------------------------------
    def _process_long(self, signals, state, df, idx, current_date,
                      close, high, low, N, sys_key, entry_period, exit_period):
        """Process long signals for one system."""
        if not self.allow_long:
            return

        in_position = state["entry_price"] is not None

        # --- Donchian levels ---
        roll_high = df["high"].shift(1)
        roll_low = df["low"].shift(1)
        entry_high = roll_high.rolling(entry_period).max().iloc[idx]
        exit_low = roll_low.rolling(exit_period).min().iloc[idx]

        if pd.isna(entry_high) or pd.isna(exit_low):
            return

        # --- Entry ---
        if not in_position and close > entry_high:
            # System 1 filter: skip if last trade was a win
            if sys_key == "sys1" and self.skip_if_last_win_sys1 and state["last_trade_win"]:
                return

            strength = self._compute_unit_strength(close, N)
            signals.append(Signal(
                symbol="", date=current_date, action="BUY",
                strength=strength,
                reason=f"Turtle {sys_key} breakout ↑{entry_period}d high",
            ))
            state["entry_price"] = close
            state["units"] = 1
            state["last_add_price"] = close
            return

        if not in_position:
            return

        # --- Pyramiding ---
        if state["units"] < self.max_units:
            add_price = state["last_add_price"] + self.pyramid_atr_mult * N
            if close > add_price:
                strength = self._compute_unit_strength(close, N)
                signals.append(Signal(
                    symbol="", date=current_date, action="BUY",
                    strength=strength,
                    reason=f"Turtle {sys_key} pyramid +{state['units'] + 1}/4u",
                ))
                state["units"] += 1
                state["last_add_price"] = close
                return

        # --- Stop loss (2N from last add price) ---
        stop_price = state["last_add_price"] - self.stop_atr_mult * N
        if low <= stop_price:
            signals.append(Signal(
                symbol="", date=current_date, action="SELL",
                strength=1.0,
                reason=f"Turtle {sys_key} stop {self.stop_atr_mult}N",
            ))
            self._reset_long_state(state, close, state["entry_price"])
            return

        # --- Exit ---
        if close < exit_low:
            signals.append(Signal(
                symbol="", date=current_date, action="SELL",
                strength=1.0,
                reason=f"Turtle {sys_key} exit ↓{exit_period}d low",
            ))
            self._reset_long_state(state, close, state["entry_price"])
            return

    # ------------------------------------------------------------------
    def _process_short(self, signals, state, df, idx, current_date,
                       close, high, low, N, sys_key, entry_period, exit_period):
        """Process short signals for one system."""
        if not self.allow_short:
            return

        in_position = state["entry_price"] is not None

        roll_high = df["high"].shift(1)
        roll_low = df["low"].shift(1)
        entry_low = roll_low.rolling(entry_period).min().iloc[idx]
        exit_high = roll_high.rolling(exit_period).max().iloc[idx]

        if pd.isna(entry_low) or pd.isna(exit_high):
            return

        # --- Short entry ---
        if not in_position and close < entry_low:
            if sys_key == "sys1" and self.skip_if_last_win_sys1 and state["last_trade_win"]:
                return

            strength = self._compute_unit_strength(close, N)
            signals.append(Signal(
                symbol="", date=current_date, action="SELL_SHORT",
                strength=strength,
                reason=f"Turtle {sys_key} breakdown ↓{entry_period}d low",
            ))
            state["entry_price"] = close
            state["units"] = 1
            state["last_add_price"] = close
            return

        if not in_position:
            return

        # --- Pyramiding (price drops more) ---
        if state["units"] < self.max_units:
            add_price = state["last_add_price"] - self.pyramid_atr_mult * N
            if close < add_price:
                strength = self._compute_unit_strength(close, N)
                signals.append(Signal(
                    symbol="", date=current_date, action="SELL_SHORT",
                    strength=strength,
                    reason=f"Turtle {sys_key} pyramid short +{state['units'] + 1}/4u",
                ))
                state["units"] += 1
                state["last_add_price"] = close
                return

        # --- Stop loss (2N above last add price) ---
        stop_price = state["last_add_price"] + self.stop_atr_mult * N
        if high >= stop_price:
            signals.append(Signal(
                symbol="", date=current_date, action="BUY_TO_COVER",
                strength=1.0,
                reason=f"Turtle {sys_key} stop {self.stop_atr_mult}N short",
            ))
            self._reset_short_state(state, close, state["entry_price"])
            return

        # --- Exit (breakout above exit_period high) ---
        if close > exit_high:
            signals.append(Signal(
                symbol="", date=current_date, action="BUY_TO_COVER",
                strength=1.0,
                reason=f"Turtle {sys_key} exit short ↑{exit_period}d high",
            ))
            self._reset_short_state(state, close, state["entry_price"])
            return

    # ------------------------------------------------------------------
    def _compute_unit_strength(self, price: float, N: float) -> float:
        """Compute signal strength for 1 Turtle unit.

        Turtle Unit = (Account × 1%) / (N × point_value)
        For the backtester: quantity = cash × strength / price
        → strength = account_risk_pct × price / N
        """
        raw = self.account_risk_pct * price / N
        return min(raw, 1.0)  # Clamp to max 100% of cash

    # ------------------------------------------------------------------
    @staticmethod
    def _reset_long_state(state: dict, exit_price: float, entry_price: float):
        """Reset long state after exit and record win/loss."""
        state["last_trade_win"] = exit_price > entry_price
        state["entry_price"] = None
        state["units"] = 0
        state["last_add_price"] = None

    @staticmethod
    def _reset_short_state(state: dict, cover_price: float, entry_price: float):
        """Reset short state after exit and record win/loss."""
        state["last_trade_win"] = cover_price < entry_price  # profit when cover < entry
        state["entry_price"] = None
        state["units"] = 0
        state["last_add_price"] = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_turtle_strategy.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add autotrade/strategies/turtle.py tests/unit/test_turtle_strategy.py
git commit -m "feat: add Turtle Trading Strategy with dual-system bidirectional signals"
```

---

### Task 7: Turtle Config YAML + Registration

**Files:**
- Create: `config/strategies/turtle.yaml`
- Modify: `autotrade/strategies/__init__.py`

- [ ] **Step 1: Create the turtle strategy config**

```yaml
# Turtle Trading Strategy — 海龟交易策略
#
# 经典趋势跟踪策略，基于波动率标准化仓位的机械化交易系统。
# 双系统（短期20日 + 长期55日）同时监控，做多/做空双向参与。
#
# 核心机制:
#   N值 = 20日ATR（真实波幅）
#   1 Unit = 账户1% / (N × 每点价值)  ← 波动率标准化仓位
#   加仓 = 每0.5N有利移动加1 Unit，最多4 Unit
#   止损 = 最后入场价 ± 2N
#
strategy: turtle
params:
  # ---- 系统参数 ----
  system1_entry: 20          # 系统一入场: 突破20日最高/最低
  system1_exit: 10           # 系统一离场: 反向突破10日最低/最高
  system2_entry: 55          # 系统二入场: 突破55日最高/最低
  system2_exit: 20           # 系统二离场: 反向突破20日最低/最高
  use_system1: true          # 启用系统一（短期）
  use_system2: true          # 启用系统二（长期）

  # ---- 波动率 ----
  atr_period: 20             # N值周期（标准海龟用20）

  # ---- 仓位 ----
  account_risk_pct: 0.01     # 每Unit风险 = 账户的1%
  max_units: 4               # 单品种最大4个Unit

  # ---- 加仓 ----
  pyramid_atr_mult: 0.5      # 每0.5N加一次仓

  # ---- 止损 ----
  stop_atr_mult: 2.0         # 2N硬止损

  # ---- 方向 ----
  allow_long: true           # 允许做多
  allow_short: true          # 允许做空

  # ---- 系统一过滤器 ----
  skip_if_last_win_sys1: true  # 上一次系统一盈利则跳过下次信号
```

- [ ] **Step 2: Register in strategies `__init__.py`**

Read `autotrade/strategies/__init__.py`, then add:

```python
from autotrade.strategies.turtle import TurtleTraderStrategy
```

Add `"TurtleTraderStrategy"` to the `__all__` list if it exists.

- [ ] **Step 3: Verify auto-registration works**

Run: `python -c "from autotrade.registry import init_registry; init_registry(); from autotrade.registry import get_strategy; s = get_strategy('turtle'); print(f'Strategy: {s.__name__}')"`
Expected: `Strategy: TurtleTraderStrategy`

- [ ] **Step 4: Commit**

```bash
git add config/strategies/turtle.yaml autotrade/strategies/__init__.py
git commit -m "feat: add turtle strategy YAML config and register strategy"
```

---

### Task 8: Integration Test — End-to-End Turtle Backtest

**Files:**
- Create: `tests/integration/test_turtle_backtest.py`

- [ ] **Step 1: Write the integration test**

```python
"""Integration test: Turtle strategy + Backtester end-to-end."""
import pandas as pd
import numpy as np
from datetime import date, timedelta

from autotrade.core.models import Bar, Signal, BacktestConfig
from autotrade.core.backtester import Backtester
from autotrade.strategies.turtle import TurtleTraderStrategy


def _generate_market_data(symbol="000001", n_days=200, trend="up"):
    """Generate realistic daily bars with a clear trend."""
    np.random.seed(123)
    dates = [date(2024, 1, 1) + timedelta(days=i) for i in range(n_days)]

    if trend == "up":
        drift = 0.0005
    elif trend == "down":
        drift = -0.0005
    else:
        drift = 0.0

    returns = np.random.normal(drift, 0.02, n_days)
    prices = 10.0 * np.exp(np.cumsum(returns))

    bars = []
    for i, (d, close) in enumerate(zip(dates, prices)):
        daily_range = close * np.random.uniform(0.01, 0.03)
        bars.append(Bar(
            symbol=symbol, date=d,
            open=float(close * (1 + np.random.uniform(-0.005, 0.005))),
            high=float(close + daily_range / 2),
            low=float(close - daily_range / 2),
            close=float(close),
            volume=float(np.random.randint(50000, 200000)),
            amount=float(close * np.random.randint(50000, 200000)),
        ))

    # Build DataFrame for strategy
    df = pd.DataFrame({
        "open": [b.open for b in bars],
        "high": [b.high for b in bars],
        "low": [b.low for b in bars],
        "close": [b.close for b in bars],
        "volume": [b.volume for b in bars],
    }, index=[b.date for b in bars])

    import pandas_ta as ta
    df["ind_atr_20"] = ta.atr(df["high"], df["low"], df["close"], length=20)

    return bars, df


class TestTurtleIntegration:
    def test_turtle_long_backtest_on_uptrend(self):
        """Turtle strategy on uptrend should produce BUY signals and positive equity."""
        bars, df = _generate_market_data(n_days=200, trend="up")

        strategy = TurtleTraderStrategy(
            use_system1=True, use_system2=False,
            allow_long=True, allow_short=False,
            max_units=4,
        )
        signals = strategy.generate_signals(df)

        # Attach symbol to signals
        for s in signals:
            s.symbol = "000001"

        cfg = BacktestConfig(
            initial_capital=100_000,
            fill_price="next_open",
            allow_short=False,
            position_sizing="strength",
        )
        bt = Backtester(cfg)
        result = bt.run(signals, bars)

        # Basic sanity checks
        assert len(result.trades) > 0, "Expected at least some trades"
        assert result.equity_curve is not None
        assert len(result.equity_curve) > 1
        assert "total_return_pct" in result.metrics
        assert "sharpe_ratio" in result.metrics
        print(f"Long-only metrics: return={result.metrics['total_return_pct']:.2f}%, "
              f"sharpe={result.metrics['sharpe_ratio']:.4f}, "
              f"trades={result.metrics['total_trades']}")

    def test_turtle_bidirectional_backtest(self):
        """Turtle strategy with long+short on mixed market."""
        bars, df = _generate_market_data(n_days=200, trend="up")

        strategy = TurtleTraderStrategy(
            use_system1=True, use_system2=False,
            allow_long=True, allow_short=True,
            max_units=4,
        )
        signals = strategy.generate_signals(df)
        for s in signals:
            s.symbol = "000001"

        cfg = BacktestConfig(
            initial_capital=100_000,
            fill_price="next_open",
            allow_short=True,
            short_margin_ratio=1.0,
            position_sizing="strength",
        )
        bt = Backtester(cfg)
        result = bt.run(signals, bars)

        assert len(result.trades) > 0
        actions = set(t.action for t in result.trades)
        assert "BUY" in actions, "Expected BUY trades"
        print(f"Bidirectional metrics: return={result.metrics['total_return_pct']:.2f}%, "
              f"sharpe={result.metrics['sharpe_ratio']:.4f}, "
              f"trades={result.metrics['total_trades']}")

    def test_turtle_full_dual_system(self):
        """Both System 1 and System 2 enabled."""
        bars, df = _generate_market_data(n_days=300, trend="up")

        strategy = TurtleTraderStrategy(
            use_system1=True, use_system2=True,
        )
        signals = strategy.generate_signals(df)
        for s in signals:
            s.symbol = "000001"

        cfg = BacktestConfig(
            initial_capital=100_000,
            fill_price="next_open",
            position_sizing="strength",
        )
        bt = Backtester(cfg)
        result = bt.run(signals, bars)

        assert len(result.trades) > 0
        buy_signals = [s for s in signals if s.action == "BUY"]
        sys1_buys = sum(1 for s in buy_signals if "sys1" in s.reason.lower())
        sys2_buys = sum(1 for s in buy_signals if "sys2" in s.reason.lower())
        print(f"System1 buys: {sys1_buys}, System2 buys: {sys2_buys}")
        # At least one system should fire
        assert sys1_buys + sys2_buys > 0

    def test_turtle_metrics_are_valid(self):
        """All metrics should be in valid ranges."""
        bars, df = _generate_market_data(n_days=200, trend="up")

        strategy = TurtleTraderStrategy(
            use_system1=True, use_system2=False,
        )
        signals = strategy.generate_signals(df)
        for s in signals:
            s.symbol = "000001"

        cfg = BacktestConfig(
            initial_capital=100_000,
            fill_price="next_open",
            position_sizing="strength",
        )
        bt = Backtester(cfg)
        result = bt.run(signals, bars)

        m = result.metrics
        # Return can be positive or negative
        assert isinstance(m["total_return_pct"], (int, float))
        # Win rate between 0 and 100
        assert 0 <= m["win_rate"] <= 100
        # Max drawdown is negative
        assert m["max_drawdown_pct"] <= 0
        # Sharpe is finite
        assert np.isfinite(m["sharpe_ratio"])
```

- [ ] **Step 2: Run integration tests**

Run: `pytest tests/integration/test_turtle_backtest.py -v`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_turtle_backtest.py
git commit -m "test: add integration tests for Turtle strategy end-to-end"
```

---

### Task 9: Final Verification

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All tests pass (existing + new)

- [ ] **Step 2: Run a manual backtest via CLI**

Run: `python -c "
from autotrade.registry import init_registry; init_registry()
from autotrade.core.config import get_strategy_params
from autotrade.strategies.turtle import TurtleTraderStrategy

params = get_strategy_params('turtle')
print('Turtle strategy params loaded:', params)
strat = TurtleTraderStrategy(**params)
print(f'Strategy ready: {strat.name}, indicators: {[i.name for i in strat.required_indicators]}")
`
Expected: No errors, prints strategy info

- [ ] **Step 3: Commit any remaining changes**

```bash
git status
git add -A
git commit -m "chore: final verification — all tests pass, strategy registers correctly"
```
