"""金叉 + MACD动量过滤 策略（精简版）。

在 ma_cross 基础上只加一个核心过滤：
  - MACD 柱状图 > 0（金叉时短期动量必须为正）

保留 ma_cross 全部优秀设计:
  - 分批加仓
  - 阶梯止盈
  - 回撤规则（加仓/减仓/清仓）
  - 止损 + 死叉离场

相比 original ma_cross 的改进:
  - MACD 动量过滤掉弱势金叉 → 预期更高胜率
  - 更少的假突破入场 → 更低的回撤

参数:
  fast: 5 / slow: 20
  macd_fast: 12 / macd_slow: 26 / macd_signal: 9
  stop_loss: 0.05
  batch_entry: true
  batches: [0.6, 0.2, 0.2]
  batch_triggers: [0.0, 0.05, 0.1]
  take_profit_levels: [[0.20, 0.2], [0.30, 0.2], [0.45, 0.2]]
  drawdown_rules: [[0.05, 0.2], [0.10, 0.2], [0.15, -1.0]]
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from autotrade.core.interfaces import Strategy
from autotrade.core.models import Signal
from autotrade.indicators.ma import MA
from autotrade.indicators.macd import MACD


class MACrossMACDStrategy(Strategy):
    """MA Cross + MACD momentum filter strategy."""

    name = "ma_cross_macd"

    def __init__(
        self,
        fast: int = 5,
        slow: int = 20,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        stop_loss: float = 0.05,
        take_profit: float = 0.15,
        trend_end: float = 0.10,
        batch_entry: bool = True,
        batches: list[float] | None = None,
        batch_triggers: list[float] | None = None,
        take_profit_levels: list[list[float]] | None = None,
        drawdown_rules: list | None = None,
    ):
        self.fast = int(fast)
        self.slow = int(slow)
        self.macd_fast = int(macd_fast)
        self.macd_slow = int(macd_slow)
        self.macd_signal = int(macd_signal)
        self.stop_loss = float(stop_loss)
        self.take_profit = float(take_profit)
        self.name = "ma_cross_macd"
        self.required_indicators = [
            MA(period=fast),
            MA(period=slow),
            MACD(fast=macd_fast, slow=macd_slow, signal=macd_signal),
        ]

        # 分批买入
        self.batch_entry = int(batch_entry)
        self.batches = batches or [1.0]
        self.batch_triggers = batch_triggers or [0.0]

        # 阶梯止盈
        if take_profit_levels:
            self.take_profit_levels = [(float(tp[0]), float(tp[1])) for tp in take_profit_levels]
        elif take_profit > 0:
            self.take_profit_levels = [(take_profit, 1.0)]
        else:
            self.take_profit_levels = []

        # 回撤规则
        if drawdown_rules:
            self.drawdown_rules = [(float(r[0]), float(r[1])) for r in drawdown_rules]
        else:
            self.drawdown_rules = [(trend_end, -1.0)]

    # ------------------------------------------------------------------
    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        signals: list[Signal] = []

        fast_col = f"ind_ma_{self.fast}"
        slow_col = f"ind_ma_{self.slow}"
        macd_hist_col = "ind_macd_histogram"

        required = [fast_col, slow_col, macd_hist_col, "close"]
        for col in required:
            if col not in df.columns:
                return signals

        fast_series = df[fast_col]
        slow_series = df[slow_col]
        macd_hist = df[macd_hist_col]

        prev_fast = None
        prev_slow = None

        # ---- 持仓状态 ----
        entry_price: float | None = None
        highest_price: float = 0.0
        batch_count: int = 0
        triggered_levels: set[int] = set()
        triggered_drawdowns: set[int] = set()
        total_batches = len(self.batches)

        for idx in range(len(df)):
            current_fast = fast_series.iloc[idx]
            current_slow = slow_series.iloc[idx]
            current_hist = macd_hist.iloc[idx]

            if pd.isna(current_fast) or pd.isna(current_slow) or pd.isna(current_hist):
                prev_fast = current_fast
                prev_slow = current_slow
                continue

            current_date = df.index[idx] if isinstance(df.index[idx], date) else df.index[idx]
            current_close = float(df.iloc[idx].get("close", current_fast))

            # 金叉
            golden_cross = (
                prev_fast is not None and prev_slow is not None
                and not pd.isna(prev_fast) and not pd.isna(prev_slow)
                and prev_fast <= prev_slow and current_fast > current_slow
            )

            # MACD 动量过滤：柱状图必须为正
            macd_momentum_ok = current_hist > 0

            in_position = entry_price is not None

            # ====================================================
            # 1. 金叉入场（需 MACD 动量确认）
            # ====================================================
            if golden_cross and macd_momentum_ok:
                if not in_position:
                    strength = self.batches[0] if self.batch_entry else 1.0
                    signals.append(
                        Signal(
                            symbol="",
                            date=current_date,
                            action="BUY",
                            strength=strength,
                            reason=f"金叉 MA{self.fast}↑MA{self.slow}",
                        )
                    )
                    entry_price = current_close
                    highest_price = current_close
                    batch_count = 0
                    triggered_levels.clear()
                    triggered_drawdowns.clear()
                elif self.batch_entry and batch_count + 1 < total_batches:
                    trigger_pct = self.batch_triggers[batch_count + 1]
                    gain = (current_close - entry_price) / entry_price
                    if gain >= trigger_pct:
                        strength = self.batches[batch_count + 1]
                        signals.append(
                            Signal(
                                symbol="",
                                date=current_date,
                                action="BUY",
                                strength=strength,
                                reason=f"加仓第{batch_count + 2}批 +{gain:.1%}",
                            )
                        )
                        batch_count += 1

            # ====================================================
            # 2. 非金叉日批次加仓
            # ====================================================
            if (
                in_position
                and not golden_cross
                and self.batch_entry
                and batch_count + 1 < total_batches
                and not triggered_levels
            ):
                trigger_pct = self.batch_triggers[batch_count + 1]
                gain = (current_close - entry_price) / entry_price
                if gain >= trigger_pct:
                    strength = self.batches[batch_count + 1]
                    signals.append(
                        Signal(
                            symbol="",
                            date=current_date,
                            action="BUY",
                            strength=strength,
                            reason=f"加仓第{batch_count + 2}批 +{gain:.1%}",
                        )
                    )
                    batch_count += 1

            # ====================================================
            # 3. 更新最高价 + 止损
            # ====================================================
            if in_position:
                if current_close > highest_price:
                    highest_price = current_close

                gain = (current_close - entry_price) / entry_price
                if gain <= -self.stop_loss:
                    signals.append(
                        Signal(
                            symbol="",
                            date=current_date,
                            action="SELL",
                            strength=1.0,
                            reason=f"止损({gain:.1%})",
                        )
                    )
                    entry_price = None
                    highest_price = 0.0
                    batch_count = 0
                    triggered_levels.clear()
                    prev_fast = current_fast
                    prev_slow = current_slow
                    continue

            # ====================================================
            # 4. 阶梯止盈
            # ====================================================
            if in_position:
                gain = (current_close - entry_price) / entry_price
                for level_idx, (threshold, sell_pct) in enumerate(self.take_profit_levels):
                    if level_idx in triggered_levels:
                        continue
                    if gain >= threshold:
                        signals.append(
                            Signal(
                                symbol="",
                                date=current_date,
                                action="SELL",
                                strength=sell_pct,
                                reason=f"止盈L{level_idx + 1} +{gain:.1%}",
                            )
                        )
                        triggered_levels.add(level_idx)

            # ====================================================
            # 5. 回撤规则
            # ====================================================
            if in_position and highest_price > 0:
                drawdown = (current_close - highest_price) / highest_price
                for rule_idx, (dd_pct, strength) in enumerate(self.drawdown_rules):
                    if rule_idx in triggered_drawdowns:
                        continue
                    if drawdown <= -dd_pct:
                        if strength <= -1.0:
                            signals.append(
                                Signal(
                                    symbol="",
                                    date=current_date,
                                    action="SELL",
                                    strength=1.0,
                                    reason=f"回撤清仓 {drawdown:.1%}",
                                )
                            )
                            entry_price = None
                            highest_price = 0.0
                            batch_count = 0
                            triggered_levels.clear()
                            triggered_drawdowns.clear()
                            break
                        elif strength < 0:
                            signals.append(
                                Signal(
                                    symbol="",
                                    date=current_date,
                                    action="SELL",
                                    strength=-strength,
                                    reason=f"回撤减仓 {drawdown:.1%}",
                                )
                            )
                            triggered_drawdowns.add(rule_idx)
                        else:
                            signals.append(
                                Signal(
                                    symbol="",
                                    date=current_date,
                                    action="BUY",
                                    strength=strength,
                                    reason=f"回撤加仓 {drawdown:.1%}",
                                )
                            )
                            triggered_drawdowns.add(rule_idx)

            # ====================================================
            # 6. 死叉检查
            # ====================================================
            death_cross = (
                prev_fast is not None and prev_slow is not None
                and not pd.isna(prev_fast) and not pd.isna(prev_slow)
                and prev_fast >= prev_slow and current_fast < current_slow
            )

            if in_position and death_cross:
                signals.append(
                    Signal(
                        symbol="",
                        date=current_date,
                        action="SELL",
                        strength=1.0,
                        reason=f"死叉 MA{self.fast}↓MA{self.slow}",
                    )
                )
                entry_price = None
                highest_price = 0.0
                batch_count = 0
                triggered_levels.clear()

            prev_fast = current_fast
            prev_slow = current_slow

        return signals
