"""Turtle Trading Strategy — dual-system trend following with bidirectional signals.

Core rules:
- System 1: 20-day breakout entry, 10-day breakout exit
- System 2: 55-day breakout entry, 20-day breakout exit
- Position sizing: 1 Unit = 1% of account / (N × point_value)
- Pyramiding: add 1 unit every 0.5N favorable move, max 4 units
- Stop loss: 2N against entry price, adjusted per pyramid add
- Trend filter (optional): only long when MA(fast) > MA(slow), only short when MA(fast) < MA(slow)
"""
from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from autotrade.core.interfaces import Strategy
from autotrade.core.models import Signal
from autotrade.indicators.atr import ATR
from autotrade.indicators.ma import MA


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
        # Trend filter
        use_trend_filter: bool = False,
        trend_ma_fast: int = 30,
        trend_ma_slow: int = 50,
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
        self.use_trend_filter = use_trend_filter
        self.trend_ma_fast = trend_ma_fast
        self.trend_ma_slow = trend_ma_slow

        self.required_indicators = [ATR(period=atr_period)]
        if use_trend_filter:
            self.required_indicators.extend([
                MA(period=trend_ma_fast),
                MA(period=trend_ma_slow),
            ])

    # ------------------------------------------------------------------
    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        signals: list[Signal] = []

        atr_col = f"ind_atr_{self.atr_period}"
        if atr_col not in df.columns or "high" not in df.columns or "low" not in df.columns:
            return signals

        # Trend filter columns (only if enabled)
        ma_fast_col = f"ind_ma_{self.trend_ma_fast}" if self.use_trend_filter else None
        ma_slow_col = f"ind_ma_{self.trend_ma_slow}" if self.use_trend_filter else None
        if self.use_trend_filter:
            if ma_fast_col not in df.columns or ma_slow_col not in df.columns:
                return signals

        n_days = len(df)
        min_days = max(self.system1_entry, self.system2_entry,
                       self.system1_exit, self.system2_exit, 10)
        if n_days < min_days:
            return signals

        # Pre-compute Donchian channels (shifted to avoid look-ahead)
        roll_high = df["high"].shift(1)
        roll_low = df["low"].shift(1)

        # Exit channels (always needed for both systems)
        donchian_high_10 = roll_high.rolling(self.system1_exit).max()
        donchian_low_10 = roll_low.rolling(self.system1_exit).min()
        donchian_high_20_exit = roll_high.rolling(self.system2_exit).max()
        donchian_low_20_exit = roll_low.rolling(self.system2_exit).min()

        # ---- Per-system, per-direction state ----
        def _init_state() -> dict:
            return {"entry_price": None, "units": 0, "last_add_price": None,
                    "last_trade_win": False}

        long_state: dict[str, dict] = {}
        short_state: dict[str, dict] = {}

        systems = []
        if self.use_system1:
            systems.append(("sys1", self.system1_entry, self.system1_exit))
            long_state["sys1"] = _init_state()
            short_state["sys1"] = _init_state()
        if self.use_system2:
            systems.append(("sys2", self.system2_entry, self.system2_exit))
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

            # Trend direction for this day
            trend_up: bool | None = None
            if self.use_trend_filter:
                ma_fast_val = df[ma_fast_col].iloc[idx]
                ma_slow_val = df[ma_slow_col].iloc[idx]
                if pd.isna(ma_fast_val) or pd.isna(ma_slow_val):
                    continue
                trend_up = ma_fast_val > ma_slow_val

            for sys_key, entry_period, exit_period in systems:
                # Entry/exit channel values for this day
                entry_high = roll_high.rolling(entry_period).max().iloc[idx]
                entry_low = roll_low.rolling(entry_period).min().iloc[idx]

                if exit_period == 10:
                    exit_high = donchian_high_10.iloc[idx]
                    exit_low = donchian_low_10.iloc[idx]
                else:
                    exit_high = donchian_high_20_exit.iloc[idx]
                    exit_low = donchian_low_20_exit.iloc[idx]

                # ---- LONG ----
                self._process_long(
                    signals, long_state[sys_key], current_date,
                    close_price, high_price, low_price, N,
                    sys_key, entry_high, entry_low, exit_low,
                    trend_up,
                )
                # ---- SHORT ----
                self._process_short(
                    signals, short_state[sys_key], current_date,
                    close_price, high_price, low_price, N,
                    sys_key, entry_low, exit_high,
                    trend_up,
                )

        return signals

    # ------------------------------------------------------------------
    def _process_long(self, signals, state, current_date,
                      close, high, low, N, sys_key,
                      entry_high, entry_low, exit_low,
                      trend_up: bool | None = None):
        """Process long signals for one system."""
        if not self.allow_long:
            return

        in_position = state["entry_price"] is not None

        if pd.isna(entry_high) or pd.isna(exit_low):
            return

        # --- Trend filter: only long when MA_fast > MA_slow ---
        if self.use_trend_filter and not in_position and trend_up is False:
            return

        # --- Entry ---
        if not in_position and close > entry_high:
            if sys_key == "sys1" and self.skip_if_last_win_sys1 and state["last_trade_win"]:
                return

            strength = self._compute_unit_strength(close, N)
            signals.append(Signal(
                symbol="", date=current_date, action="BUY",
                strength=strength,
                reason=f"Turtle {sys_key} breakout {self.system1_entry if sys_key == 'sys1' else self.system2_entry}d high",
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
                    reason=f"Turtle {sys_key} pyramid +{state['units'] + 1}/{self.max_units}u",
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
                reason=f"Turtle {sys_key} exit {self.system1_exit if sys_key == 'sys1' else self.system2_exit}d low",
            ))
            self._reset_long_state(state, close, state["entry_price"])

    # ------------------------------------------------------------------
    def _process_short(self, signals, state, current_date,
                       close, high, low, N, sys_key,
                       entry_low, exit_high,
                       trend_up: bool | None = None):
        """Process short signals for one system."""
        if not self.allow_short:
            return

        in_position = state["entry_price"] is not None

        if pd.isna(entry_low) or pd.isna(exit_high):
            return

        # --- Trend filter: only short when MA_fast < MA_slow ---
        if self.use_trend_filter and not in_position and trend_up is not False:
            return

        # --- Short entry ---
        if not in_position and close < entry_low:
            if sys_key == "sys1" and self.skip_if_last_win_sys1 and state["last_trade_win"]:
                return

            strength = self._compute_unit_strength(close, N)
            signals.append(Signal(
                symbol="", date=current_date, action="SELL_SHORT",
                strength=strength,
                reason=f"Turtle {sys_key} breakdown {self.system1_entry if sys_key == 'sys1' else self.system2_entry}d low",
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
                    reason=f"Turtle {sys_key} pyramid short +{state['units'] + 1}/{self.max_units}u",
                ))
                state["units"] += 1
                state["last_add_price"] = close
                return

        # --- Stop loss (2N above last add price for shorts) ---
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
                reason=f"Turtle {sys_key} exit short {self.system1_exit if sys_key == 'sys1' else self.system2_exit}d high",
            ))
            self._reset_short_state(state, close, state["entry_price"])

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
