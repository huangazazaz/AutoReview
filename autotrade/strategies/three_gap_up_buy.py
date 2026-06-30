import pandas as pd
from autotrade.core.interfaces import Strategy, Signal
from autotrade.indicators.ma import MA

class ThreeGapUpBuy(Strategy):
    name = 'three_gap_up_buy'
    required_indicators = []

    def __init__(self, stop_loss_pct=5.0, take_profit_pct=10.0):
        self.stop_loss_pct = stop_loss_pct
        self.take_profit_pct = take_profit_pct
        self.entry_price = None
        self.position = 0  # 0: no position, 1: long

    def generate_signals(self, df: pd.DataFrame) -> list:
        signals = []
        if len(df) < 4:
            return signals

        # 计算连续三日高开阳线条件
        for i in range(3, len(df)):
            # 检查连续三日高开且收阳
            cond1 = df['open'].iloc[i-2] > df['close'].iloc[i-3]  # 第1日高开
            cond2 = df['close'].iloc[i-2] > df['open'].iloc[i-2]  # 第1日收阳
            cond3 = df['open'].iloc[i-1] > df['close'].iloc[i-2]  # 第2日高开
            cond4 = df['close'].iloc[i-1] > df['open'].iloc[i-1]  # 第2日收阳
            cond5 = df['open'].iloc[i] > df['close'].iloc[i-1]    # 第3日高开
            cond6 = df['close'].iloc[i] > df['open'].iloc[i]      # 第3日收阳

            if cond1 and cond2 and cond3 and cond4 and cond5 and cond6:
                # 买入信号
                entry_price = df['close'].iloc[i]
                stop_loss = entry_price * (1 - self.stop_loss_pct / 100)
                take_profit = entry_price * (1 + self.take_profit_pct / 100)
                signals.append(Signal(
                    symbol='600522',
                    date=df.index[i],
                    action='BUY',
                    strength=1.0,
                    reason=f'连续三日高开阳线，入场价{entry_price:.2f}，止损{stop_loss:.2f}，止盈{take_profit:.2f}'
                ))

        # 止损止盈检查（简化：假设已有持仓，根据当前价格判断）
        if self.position == 1 and self.entry_price is not None:
            current_price = df['close'].iloc[-1]
            if current_price <= self.entry_price * (1 - self.stop_loss_pct / 100):
                signals.append(Signal(
                    symbol='600522',
                    date=df.index[-1],
                    action='SELL',
                    strength=1.0,
                    reason=f'止损触发，入场价{self.entry_price:.2f}，当前价{current_price:.2f}'
                ))
                self.position = 0
                self.entry_price = None
            elif current_price >= self.entry_price * (1 + self.take_profit_pct / 100):
                signals.append(Signal(
                    symbol='600522',
                    date=df.index[-1],
                    action='SELL',
                    strength=1.0,
                    reason=f'止盈触发，入场价{self.entry_price:.2f}，当前价{current_price:.2f}'
                ))
                self.position = 0
                self.entry_price = None

        return signals