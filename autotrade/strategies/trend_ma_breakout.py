"""金叉 + RSI 择时过滤策略（最精简有效版）。

核心理念：
  在标准 MA 金叉策略基础上，只增加一个 RSI 择时过滤器：
  只在 RSI 30~60 区间内响应金叉信号 → 捕捉"回调结束、趋势恢复"的最佳买点。
  
  为什么只要 RSI？
  - RSI < 30: 下跌趋势中，金叉可能是假信号
  - RSI 30~60: 回调企稳、趋势健康恢复的"甜区"
  - RSI > 60: 已经涨了一段，追高风险大
  - 量能过滤会遗漏太多好机会（之前实验已证实）
  - BB 过滤与 MA(20) 高度相关，冗余

买入:
  - 金叉当天，且 RSI 在 [rsi_low, rsi_high] 内 → 按 batches[0] 买入底仓
  - 持仓期间，价格涨幅 ≥ batch_triggers[i] → 按 batches[i] 加仓
  - 触发止盈后不再加仓

卖出（继承 ma_cross 全部退出机制）:
  - 阶梯止盈
  - 止损
  - 回撤规则（加仓/减仓/清仓）
  - 死叉

预期 vs ma_cross:
  - 更少的入场（过滤掉弱势/追高金叉）→ 更高胜率
  - RSI 甜区入场 → 更好的入场价格 → 更高收益率
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from autotrade.core.interfaces import Strategy
from autotrade.core.models import Signal
from autotrade.indicators.ma import MA
from autotrade.indicators.rsi import RSI




def _parse_list(val):
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        import json
        try:
            p = json.loads(val)
            if isinstance(p, list):
                return p
        except:
            pass
    return val or []

class TrendMABreakoutStrategy(Strategy):
    """金叉 + RSI 择时 + 分批 + 回撤规则。"""

    name = "trend_ma_breakout"

    def __init__(
        self,
        fast: int = 5,
        slow: int = 20,
        rsi_period: int = 14,
        rsi_low: float = 30,
        rsi_high: float = 60,
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
        self.rsi_period = int(rsi_period)
        self.rsi_low = int(rsi_low)
        self.rsi_high = int(rsi_high)
        self.stop_loss = float(stop_loss)
        self.name = "trend_ma_breakout"

        self.required_indicators = [
            MA(period=fast),
            MA(period=slow),
            RSI(period=rsi_period),
        ]

        # 分批买入
        self.batch_entry = str(batch_entry).lower() in ("true", "1", "yes") if not isinstance(batch_entry, bool) else batch_entry
        self.batches = batches or [1.0]
        self.batch_triggers = batch_triggers or [0.0]

        # 阶梯止盈
        if take_profit_levels:
            self.take_profit_levels = [(float(tp[0]), float(tp[1])) for tp in (_parse_list(take_profit_levels))]
        elif take_profit > 0:
            self.take_profit_levels = [(take_profit, 1.0)]
        else:
            self.take_profit_levels = []

        # 回撤规则
        if drawdown_rules:
            self.drawdown_rules = [(float(r[0]), float(r[1])) for r in (_parse_list(drawdown_rules))]
        else:
            self.drawdown_rules = [(trend_end, -1.0)]

    # ------------------------------------------------------------------
    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        signals: list[Signal] = []

        fast_col = f"ind_ma_{self.fast}"
        slow_col = f"ind_ma_{self.slow}"
        rsi_col = f"ind_rsi_{self.rsi_period}"

        for col in [fast_col, slow_col, rsi_col, "close"]:
            if col not in df.columns:
                return signals

        fast_series = df[fast_col]
        slow_series = df[slow_col]
        rsi_series = df[rsi_col]

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
            current_rsi = rsi_series.iloc[idx]

            if pd.isna(current_fast) or pd.isna(current_slow) or pd.isna(current_rsi):
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

            in_position = entry_price is not None

            # ====================================================
            # 1. 金叉入场（RSI 择时过滤）
            # ====================================================
            if golden_cross:
                if not in_position:
                    # RSI 在甜区才入场
                    rsi_sweet_spot = self.rsi_low <= current_rsi <= self.rsi_high
                    if rsi_sweet_spot:
                        strength = self.batches[0] if self.batch_entry else 1.0
                        signals.append(
                            Signal(
                                symbol="",
                                date=current_date,
                                action="BUY",
                                strength=strength,
                                reason=f"金叉 MA{self.fast}↑MA{self.slow} RSI{current_rsi:.0f}",
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
