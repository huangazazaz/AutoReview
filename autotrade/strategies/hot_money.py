"""游资超短线择时策略 — 三闸门出场状态机。

本策略是"选股后择时"架构的第二层, 只负责被选中后的进出场:
- 进场: 仅在 allowed_entry_dates（由 Screener 选出的日期）发 BUY, 满仓。
- 出场: 三道闸门任一触发即清仓（快速止盈 + 严格止损）。

三闸门（任一触发即 SELL）:
  闸门1 移动止盈: 最高涨幅 ≥ trailing_activate 后,
                  从最高点回撤 ≥ trailing_drawdown 即锁利。
  闸门2 时间止损: 持仓满 time_stop_days 且收益 < time_stop_min_gain 即离场。
  闸门3 硬止损:   收益 ≤ -stop_loss 即清仓。

注意: 进场形态判断（放量起涨/首阴反包）在 Screener 层完成,
      本策略不重算, required_indicators 为空（只需 close + 状态）。

设计详见 docs/superpowers/specs/2026-06-21-hot-money-strategy-design.md §4。
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from autotrade.core.interfaces import Strategy
from autotrade.core.models import Signal


class HotMoneyStrategy(Strategy):
    """游资超短线: 三闸门出场状态机。"""

    name = "hot_money"

    def __init__(
        self,
        allowed_entry_dates: list[date] | None = None,
        trailing_activate: float = 0.08,
        trailing_drawdown: float = 0.03,
        time_stop_days: int = 3,
        time_stop_min_gain: float = 0.03,
        stop_loss: float = 0.05,
    ):
        self.allowed_entry_dates = set(allowed_entry_dates or [])
        self.trailing_activate = trailing_activate
        self.trailing_drawdown = trailing_drawdown
        self.time_stop_days = time_stop_days
        self.time_stop_min_gain = time_stop_min_gain
        self.stop_loss = stop_loss
        self.name = "hot_money"
        # 三闸门只需 close + 状态, 无需指标
        self.required_indicators = []

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        signals: list[Signal] = []
        if "close" not in df.columns:
            return signals

        # 持仓状态
        entry_price: float | None = None
        entry_idx: int = 0
        highest_price: float = 0.0
        trailing_active: bool = False

        for idx in range(len(df)):
            current_close = float(df.iloc[idx]["close"])
            if pd.isna(current_close):
                continue
            current_date = df.index[idx]
            # df.index 可能是 DatetimeIndex（Timestamp）或 date
            today = current_date.date() if hasattr(current_date, "date") else current_date

            in_position = entry_price is not None

            # ---- 空仓: 检查是否在允许进场日 ----
            if not in_position:
                if today in self.allowed_entry_dates:
                    signals.append(Signal(
                        symbol="",
                        date=current_date,
                        action="BUY",
                        strength=1.0,
                        reason="游资信号进场",
                    ))
                    entry_price = current_close
                    entry_idx = idx
                    highest_price = current_close
                    trailing_active = False
                    # 进场当天不立即检查出场, 继续下一日
                    continue

            # ---- 持仓: 检查三闸门 ----
            if in_position:
                # 更新最高价
                if current_close > highest_price:
                    highest_price = current_close

                gain = (current_close - entry_price) / entry_price
                highest_gain = (highest_price - entry_price) / entry_price
                days_held = idx - entry_idx

                # 闸门1 启动条件: 最高涨幅达标
                if highest_gain >= self.trailing_activate:
                    trailing_active = True

                # 闸门3: 硬止损（最高优先级, 先判断）
                if gain <= -self.stop_loss:
                    signals.append(Signal(
                        symbol="",
                        date=current_date,
                        action="SELL",
                        strength=1.0,
                        reason=f"硬止损({gain:.1%})",
                    ))
                    entry_price = None
                    highest_price = 0.0
                    trailing_active = False
                    continue

                # 闸门1: 移动止盈（已启动且回撤达标）
                if trailing_active:
                    drawdown_from_high = (current_close - highest_price) / highest_price
                    if drawdown_from_high <= -self.trailing_drawdown:
                        signals.append(Signal(
                            symbol="",
                            date=current_date,
                            action="SELL",
                            strength=1.0,
                            reason=f"移动止盈(+{highest_gain:.1%}→{gain:.1%})",
                        ))
                        entry_price = None
                        highest_price = 0.0
                        trailing_active = False
                        continue

                # 闸门2: 时间止损
                if days_held >= self.time_stop_days and gain < self.time_stop_min_gain:
                    signals.append(Signal(
                        symbol="",
                        date=current_date,
                        action="SELL",
                        strength=1.0,
                        reason=f"时间止损({days_held}天 +{gain:.1%})",
                    ))
                    entry_price = None
                    highest_price = 0.0
                    trailing_active = False
                    continue

        return signals
