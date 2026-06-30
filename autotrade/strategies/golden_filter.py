"""金叉 + 质量过滤 + 分批 + 止盈止损 策略（v4 最终版）。

相比 ma_cross 的增强：
  买入过滤（金叉之外额外要求）:
    - 成交量 > 20日均量（放量确认）
    - RSI < 70（非超买）
    - 收盘价 > BB 中轨（布林带多头确认）
  
  保留 ma_cross 的优秀设计:
    - 金叉入场 + 分批加仓
    - 阶梯止盈
    - 回撤规则（加仓/减仓/清仓）
    - 止损 + 死叉离场

规则:
  买入:
    - 金叉当天，满足质量过滤条件 → 按 batches[0] 买入底仓
    - 持仓期间，价格涨幅 ≥ batch_triggers[i] 时 → 按 batches[i] 加仓
    - 触发过止盈卖出后不再加仓
  卖出:
    - 阶梯止盈（take_profit_levels）
    - 止损: 亏损 ≥ stop_loss 全卖
    - 回撤规则: drawdown_rules
    - 死叉: 清仓剩余持仓

参数:
  fast: 5                    # 快线周期
  slow: 20                   # 慢线周期
  rsi_period: 14             # RSI 周期
  rsi_max_entry: 70          # 买入时 RSI 上限
  bb_period: 20              # BB 周期
  bb_std: 2.0                # BB 标准差
  vol_period: 20             # 量能均线周期
  stop_loss: 0.05            # 止损线
  batch_entry: true          # 启用分批买入
  batches: [0.6, 0.2, 0.2]   # 每批买入比例
  batch_triggers: [0.0, 0.05, 0.1]  # 触发涨幅阈值
  take_profit_levels:        # 阶梯止盈
    - [0.20, 0.2]
    - [0.30, 0.2]
    - [0.45, 0.2]
  drawdown_rules:            # 回撤规则 [(回撤%, 力度)]
    - [0.05, 0.2]            # -5%: 加仓 20%
    - [0.10, 0.2]            # -10%: 加仓 20%
    - [0.15, -1.0]           # -15%: 清仓
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from autotrade.core.interfaces import Strategy
from autotrade.core.models import Signal
from autotrade.indicators.bollinger import BollingerBands
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

class GoldenFilterStrategy(Strategy):
    name = "golden_filter"

    def __init__(
        self,
        fast: int = 5,
        slow: int = 20,
        rsi_period: int = 14,
        rsi_max_entry: float = 70,
        bb_period: int = 20,
        bb_std: float = 2.0,
        vol_period: int = 20,
        stop_loss: float = 0.05,
        take_profit: float = 0.15,              # 向后兼容
        trend_end: float = 0.10,                 # 向后兼容
        batch_entry: bool = True,
        batches: list[float] | None = None,
        batch_triggers: list[float] | None = None,
        take_profit_levels: list[list[float]] | None = None,
        drawdown_rules: list | None = None,
    ):
        self.fast = int(fast)
        self.slow = int(slow)
        self.rsi_period = int(rsi_period)
        self.rsi_max_entry = float(rsi_max_entry)
        self.bb_period = int(bb_period)
        self.bb_std = float(bb_std)
        self.vol_period = int(vol_period)
        self.stop_loss = float(stop_loss)
        self.name = "golden_filter"

        self.required_indicators = [
            MA(period=fast),
            MA(period=slow),
            RSI(period=rsi_period),
            BollingerBands(period=bb_period, std=bb_std),
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
    # generate_signals
    # ------------------------------------------------------------------
    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        signals: list[Signal] = []

        fast_col = f"ind_ma_{self.fast}"
        slow_col = f"ind_ma_{self.slow}"
        rsi_col = f"ind_rsi_{self.rsi_period}"
        bb_middle_col = f"ind_bb_middle_{self.bb_period}"

        required = [fast_col, slow_col, rsi_col, bb_middle_col, "close", "volume"]
        for col in required:
            if col not in df.columns:
                return signals

        # 成交量均线
        vol_ma = df["volume"].rolling(window=self.vol_period).mean()

        # ---- 持仓状态 ----
        entry_price: float | None = None
        highest_price: float = 0.0
        batch_count: int = 0
        triggered_levels: set[int] = set()
        triggered_drawdowns: set[int] = set()
        total_batches = len(self.batches)

        prev_fast: float | None = None
        prev_slow: float | None = None

        for idx in range(len(df)):
            current_fast = float(df.iloc[idx][fast_col])
            current_slow = float(df.iloc[idx][slow_col])
            current_rsi = float(df.iloc[idx][rsi_col])
            current_bb_mid = float(df.iloc[idx][bb_middle_col])

            if pd.isna(current_fast) or pd.isna(current_slow) or pd.isna(current_rsi) or pd.isna(current_bb_mid):
                prev_fast = current_fast
                prev_slow = current_slow
                continue

            current_date = df.index[idx] if isinstance(df.index[idx], date) else df.index[idx]
            current_close = float(df.iloc[idx].get("close", current_fast))
            current_volume = float(df.iloc[idx].get("volume", 0))

            # 量能确认
            vol_ma_val = vol_ma.iloc[idx]
            volume_ok = not pd.isna(vol_ma_val) and current_volume > vol_ma_val

            # 金叉
            golden_cross = (
                prev_fast is not None and prev_slow is not None
                and not pd.isna(prev_fast) and not pd.isna(prev_slow)
                and prev_fast <= prev_slow and current_fast > current_slow
            )

            in_position = entry_price is not None

            # ====================================================
            # 1. 金叉入场（带质量过滤）
            # ====================================================
            if golden_cross:
                if not in_position:
                    # 质量过滤: 放量 + RSI非超买 + BB多头
                    quality_pass = (
                        volume_ok
                        and current_rsi < self.rsi_max_entry
                        and current_close > current_bb_mid
                    )
                    if quality_pass:
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
                    # 持仓中，金叉再次出现，加仓
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
            # 2. 非金叉日的批次加仓（价格触发）
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
