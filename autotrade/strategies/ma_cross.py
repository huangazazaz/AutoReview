"""均线交叉策略。

规则:
- 快线上穿慢线 → BUY 信号（strength=1.0）
- 快线下穿慢线 → SELL 信号（strength=1.0）
- 否则 → HOLD

参数（来自 config/strategies/ma_cross.yaml）:
  fast: 5
  slow: 20
  stop_loss: 0.05
  take_profit: 0.15
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from autotrade.core.interfaces import Strategy
from autotrade.core.models import Signal
from autotrade.indicators.ma import MA


class MACrossStrategy(Strategy):
    name = "ma_cross"

    def __init__(self, fast: int = 5, slow: int = 20,
                 stop_loss: float = 0.05, take_profit: float = 0.15):
        self.fast = fast
        self.slow = slow
        self.stop_loss = stop_loss
        self.take_profit = take_profit
        self.name = "ma_cross"
        self.required_indicators = [MA(period=fast), MA(period=slow)]

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        signals: list[Signal] = []
        fast_col = f"ind_ma_{self.fast}"
        slow_col = f"ind_ma_{self.slow}"

        if fast_col not in df.columns or slow_col not in df.columns:
            return signals

        fast_series = df[fast_col]
        slow_series = df[slow_col]

        prev_fast = None
        prev_slow = None
        entry_price: float | None = None

        for idx in range(len(df)):
            current_fast = fast_series.iloc[idx]
            current_slow = slow_series.iloc[idx]

            if pd.isna(current_fast) or pd.isna(current_slow):
                prev_fast = current_fast
                prev_slow = current_slow
                continue

            current_date = df.index[idx] if isinstance(df.index[idx], date) else df.index[idx]

            if prev_fast is not None and prev_slow is not None:
                if not pd.isna(prev_fast) and not pd.isna(prev_slow):
                    # 金叉：快线上穿慢线
                    if prev_fast <= prev_slow and current_fast > current_slow:
                        signals.append(Signal(
                            symbol="",
                            date=current_date,
                            action="BUY",
                            strength=1.0,
                            reason=f"MA{self.fast}上穿MA{self.slow}",
                        ))
                        entry_price = float(df.iloc[idx].get("close", current_fast))

                    # 死叉：快线下穿慢线
                    elif prev_fast >= prev_slow and current_fast < current_slow:
                        signals.append(Signal(
                            symbol="",
                            date=current_date,
                            action="SELL",
                            strength=1.0,
                            reason=f"MA{self.fast}下穿MA{self.slow}",
                        ))
                        entry_price = None

                    # 止损/止盈检查（基于当前持仓）
                    if entry_price is not None:
                        current_price = float(df.iloc[idx].get("close", current_fast))
                        pnl_pct = (current_price - entry_price) / entry_price
                        if pnl_pct <= -self.stop_loss:
                            signals.append(Signal(
                                symbol="",
                                date=current_date,
                                action="SELL",
                                strength=1.0,
                                reason=f"止损({pnl_pct:.1%})",
                            ))
                            entry_price = None
                        elif self.take_profit > 0 and pnl_pct >= self.take_profit:
                            signals.append(Signal(
                                symbol="",
                                date=current_date,
                                action="SELL",
                                strength=1.0,
                                reason=f"止盈({pnl_pct:.1%})",
                            ))
                            entry_price = None

            prev_fast = current_fast
            prev_slow = current_slow

        return signals
