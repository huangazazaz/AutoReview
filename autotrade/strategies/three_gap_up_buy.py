"""连续三日高开阳线策略：检测连续3天高开并收阳的K线形态，配合止盈止损。

逻辑：
  1. 买入: 连续3个交易日每天都高开（开盘价 > 前日收盘价）且收阳（收盘价 > 开盘价）
  2. 卖出: 达到止盈价或触发止损
"""
import pandas as pd
from autotrade.core.interfaces import Strategy, Signal


class ThreeGapUpBuy(Strategy):
    name = "three_gap_up_buy"
    required_indicators = []

    def __init__(self, stop_loss_pct: float = 5.0, take_profit_pct: float = 10.0):
        self.stop_loss_pct = float(stop_loss_pct)
        self.take_profit_pct = float(take_profit_pct)

    def generate_signals(self, df: pd.DataFrame) -> list:
        signals = []
        if len(df) < 4:
            return signals

        in_position = False
        entry_price = 0.0

        for i in range(3, len(df)):
            current_close = float(df["close"].iloc[i])
            current_open = float(df["open"].iloc[i])

            # ---- 持仓中：检查止盈止损 ----
            if in_position:
                stop_loss = entry_price * (1 - self.stop_loss_pct / 100)
                take_profit = entry_price * (1 + self.take_profit_pct / 100)

                if current_close <= stop_loss:
                    signals.append(Signal(
                        symbol="",
                        date=df.index[i],
                        action="SELL",
                        strength=1.0,
                        reason=f"止损触发 入场{entry_price:.2f} 当前{current_close:.2f}",
                    ))
                    in_position = False
                    entry_price = 0.0
                    continue

                if current_close >= take_profit:
                    signals.append(Signal(
                        symbol="",
                        date=df.index[i],
                        action="SELL",
                        strength=1.0,
                        reason=f"止盈触发 入场{entry_price:.2f} 当前{current_close:.2f}",
                    ))
                    in_position = False
                    entry_price = 0.0
                    continue

            # ---- 非持仓：检查三日高开阳线买入条件 ----
            if not in_position:
                cond1 = float(df["open"].iloc[i - 2]) > float(df["close"].iloc[i - 3])
                cond2 = float(df["close"].iloc[i - 2]) > float(df["open"].iloc[i - 2])
                cond3 = float(df["open"].iloc[i - 1]) > float(df["close"].iloc[i - 2])
                cond4 = float(df["close"].iloc[i - 1]) > float(df["open"].iloc[i - 1])
                cond5 = current_open > float(df["close"].iloc[i - 1])
                cond6 = current_close > current_open

                if cond1 and cond2 and cond3 and cond4 and cond5 and cond6:
                    entry_price = current_close
                    in_position = True
                    stop_loss = entry_price * (1 - self.stop_loss_pct / 100)
                    take_profit = entry_price * (1 + self.take_profit_pct / 100)
                    signals.append(Signal(
                        symbol="",
                        date=df.index[i],
                        action="BUY",
                        strength=1.0,
                        reason=f"三日高开阳线 入场{entry_price:.2f} 止损{stop_loss:.2f} 止盈{take_profit:.2f}",
                    ))

        return signals
