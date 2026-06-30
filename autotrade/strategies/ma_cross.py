"""均线交叉策略 v2（分批买入 + 阶梯止盈）。

规则:
  买入:
    - 金叉当天，按 batches[0] 比例买入底仓（首批）
    - 持仓期间，价格相对首批买入价涨幅 ≥ batch_triggers[i] 时，按 batches[i] 加仓
    - 一旦触发过任何止盈卖出，不再加仓
  卖出:
    - 阶梯止盈（take_profit_levels）: 每个盈利阈值卖出对应比例
    - 止损: 亏损 ≥ stop_loss 全卖
    - 死叉: 清仓剩余持仓
    - 同一天内卖出优先于买入

参数（来自 config/strategies/ma_cross.yaml）:
  fast: 5                    # 快线周期
  slow: 20                   # 慢线周期
  stop_loss: 0.05            # 止损线
  batch_entry: true          # 是否启用分批买入
  batches: [0.4, 0.3, 0.3]   # 每批买入比例
  batch_triggers: [0.0, 0.01, 0.02]  # 每批触发涨幅阈值
  take_profit_levels:        # 阶梯止盈 [(涨幅阈值, 卖出比例), ...]
    - [0.10, 0.4]
    - [0.15, 0.3]
    - [0.20, 0.3]
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from autotrade.core.interfaces import Strategy
from autotrade.core.models import Signal
from autotrade.indicators.ma import MA




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

class MACrossStrategy(Strategy):
    name = "ma_cross"

    def __init__(self, fast: int = 5, slow: int = 20,
                 stop_loss: float = 0.05,
                 take_profit: float = 0.15,  # 向后兼容旧配置
                 trend_end: float = 0.10,     # 向后兼容（无 drawdown_rules 时用）
                 batch_entry: bool = False,
                 batches: list[float] | None = None,
                 batch_triggers: list[float] | None = None,
                 take_profit_levels: list[list[float]] | None = None,
                 drawdown_rules: list | None = None):
        self.fast = int(fast)
        self.slow = int(slow)
        self.stop_loss = float(stop_loss)
        self.take_profit = float(take_profit)
        self.name = "ma_cross"
        self.required_indicators = [MA(period=fast), MA(period=slow)]

        # 分批买入参数
        self.batch_entry = str(batch_entry).lower() in ("true", "1", "yes") if not isinstance(batch_entry, bool) else batch_entry
        self.batches = batches or [1.0]
        self.batch_triggers = batch_triggers or [0.0]

        # 阶梯止盈参数（严格按配置比例，不强制清仓）
        if take_profit_levels:
            self.take_profit_levels = [(float(tp[0]), float(tp[1])) for tp in (_parse_list(take_profit_levels))]
        elif take_profit > 0:
            self.take_profit_levels = [(take_profit, 1.0)]
        else:
            self.take_profit_levels = []

        # 回撤规则: [(回撤%, 力度), ...]  正数=加仓 负数=减仓 -1=清仓
        if drawdown_rules:
            self.drawdown_rules = [(float(r[0]), float(r[1])) for r in (_parse_list(drawdown_rules))]
        else:
            self.drawdown_rules = [(trend_end, -1.0)]  # 旧 trend_end → 单级清仓

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

        # ---- 分批 + 阶梯止盈状态 ----
        entry_price: float | None = None       # 首批买入价
        highest_price: float = 0.0             # 持仓期间最高价
        batch_count: int = 0                   # 已执行的买入批次数-1
        triggered_levels: set[int] = set()     # 已触发的止盈级别索引
        triggered_drawdowns: set[int] = set()  # 已触发的回撤规则索引
        total_batches = len(self.batches)

        for idx in range(len(df)):
            current_fast = fast_series.iloc[idx]
            current_slow = slow_series.iloc[idx]

            if pd.isna(current_fast) or pd.isna(current_slow):
                prev_fast = current_fast
                prev_slow = current_slow
                continue

            current_date = df.index[idx] if isinstance(df.index[idx], date) else df.index[idx]
            current_close = float(df.iloc[idx].get("close", current_fast))

            # ====================================================
            # 1. 金叉检测（进场 / 加仓）
            # ====================================================
            golden_cross = (
                prev_fast is not None and prev_slow is not None
                and not pd.isna(prev_fast) and not pd.isna(prev_slow)
                and prev_fast <= prev_slow and current_fast > current_slow
            )

            in_position = entry_price is not None

            if golden_cross:
                if not in_position:
                    # 首批买入
                    strength = self.batches[0] if self.batch_entry else 1.0
                    signals.append(Signal(
                        symbol="",
                        date=current_date,
                        action="BUY",
                        strength=strength,
                        reason=f"金叉 MA{self.fast}↑MA{self.slow}",
                    ))
                    entry_price = current_close
                    highest_price = current_close
                    batch_count = 0
                    triggered_levels.clear()
                    triggered_drawdowns.clear()
                elif self.batch_entry and batch_count + 1 < total_batches:
                    # 金叉再次出现且还有未执行的批次 → 也可以触发下一批
                    # 但前提是满足 batch_triggers 条件
                    trigger_pct = self.batch_triggers[batch_count + 1]
                    gain = (current_close - entry_price) / entry_price
                    if gain >= trigger_pct:
                        strength = self.batches[batch_count + 1]
                        signals.append(Signal(
                            symbol="",
                            date=current_date,
                            action="BUY",
                            strength=strength,
                            reason=f"加仓第{batch_count+2}批 +{gain:.1%}",
                        ))
                        batch_count += 1

            # ====================================================
            # 2. 持仓期间的批次加仓（非金叉日的价格触发）
            # ====================================================
            if (
                in_position
                and not golden_cross  # 避免同一天重复触发
                and self.batch_entry
                and batch_count + 1 < total_batches
                and not triggered_levels  # 未触发过止盈才加仓
            ):
                trigger_pct = self.batch_triggers[batch_count + 1]
                gain = (current_close - entry_price) / entry_price
                if gain >= trigger_pct:
                    strength = self.batches[batch_count + 1]
                    signals.append(Signal(
                        symbol="",
                        date=current_date,
                        action="BUY",
                        strength=strength,
                        reason=f"加仓第{batch_count+2}批 +{gain:.1%}",
                    ))
                    batch_count += 1

            # ====================================================
            # 3. 更新持仓期间最高价 + 止损检查
            # ====================================================
            if in_position:
                if current_close > highest_price:
                    highest_price = current_close

                gain = (current_close - entry_price) / entry_price
                if gain <= -self.stop_loss:
                    signals.append(Signal(
                        symbol="",
                        date=current_date,
                        action="SELL",
                        strength=1.0,
                        reason=f"止损({gain:.1%})",
                    ))
                    entry_price = None
                    highest_price = 0.0
                    batch_count = 0
                    triggered_levels.clear()
                    prev_fast = current_fast
                    prev_slow = current_slow
                    continue

            # ====================================================
            # 4. 阶梯止盈（严格按配置比例，不再强制清仓）
            # ====================================================
            if in_position:
                gain = (current_close - entry_price) / entry_price
                for level_idx, (threshold, sell_pct) in enumerate(self.take_profit_levels):
                    if level_idx in triggered_levels:
                        continue
                    if gain >= threshold:
                        signals.append(Signal(
                            symbol="",
                            date=current_date,
                            action="SELL",
                            strength=sell_pct,
                            reason=f"止盈L{level_idx+1} +{gain:.1%}",
                        ))
                        triggered_levels.add(level_idx)

            # ====================================================
            # 5. 回撤规则：从最高点回撤达到各级阈值时执行
            # ====================================================
            if in_position and highest_price > 0:
                drawdown = (current_close - highest_price) / highest_price
                for rule_idx, (dd_pct, strength) in enumerate(self.drawdown_rules):
                    if rule_idx in triggered_drawdowns:
                        continue
                    if drawdown <= -dd_pct:
                        if strength <= -1.0:
                            # 清仓
                            signals.append(Signal(
                                symbol="",
                                date=current_date,
                                action="SELL",
                                strength=1.0,
                                reason=f"回撤清仓 {drawdown:.1%}",
                            ))
                            entry_price = None
                            highest_price = 0.0
                            batch_count = 0
                            triggered_levels.clear()
                            triggered_drawdowns.clear()
                            break
                        elif strength < 0:
                            # 减仓
                            signals.append(Signal(
                                symbol="",
                                date=current_date,
                                action="SELL",
                                strength=-strength,
                                reason=f"回撤减仓 {drawdown:.1%}",
                            ))
                            triggered_drawdowns.add(rule_idx)
                        else:
                            # 加仓
                            signals.append(Signal(
                                symbol="",
                                date=current_date,
                                action="BUY",
                                strength=strength,
                                reason=f"回撤加仓 {drawdown:.1%}",
                            ))
                            triggered_drawdowns.add(rule_idx)

            # ====================================================
            # 5. 死叉检查
            # ====================================================
            death_cross = (
                prev_fast is not None and prev_slow is not None
                and not pd.isna(prev_fast) and not pd.isna(prev_slow)
                and prev_fast >= prev_slow and current_fast < current_slow
            )

            if in_position and death_cross:
                signals.append(Signal(
                    symbol="",
                    date=current_date,
                    action="SELL",
                    strength=1.0,
                    reason=f"死叉 MA{self.fast}↓MA{self.slow}",
                ))
                entry_price = None
                highest_price = 0.0
                batch_count = 0
                triggered_levels.clear()

            # 更新前一日的均线值
            prev_fast = current_fast
            prev_slow = current_slow

        return signals
