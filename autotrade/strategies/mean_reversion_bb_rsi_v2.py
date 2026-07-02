import pandas as pd
from autotrade.core.interfaces import Strategy, Signal
from autotrade.indicators.bollinger import BollingerBands
from autotrade.indicators.rsi import RSI

class MeanReversionBBRSI(Strategy):
    name = "mean_reversion_bb_rsi_v2"
    required_indicators = [
        BollingerBands(period=20, std=2.0),
        RSI(period=14)
    ]

    def __init__(self, bb_period=20, bb_std=2.0, rsi_period=14, oversold=30, overbought=70, min_hold_days=2):
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.rsi_period = rsi_period
        self.oversold = oversold
        self.overbought = overbought
        self.min_hold_days = min_hold_days
        self.last_buy_date = None

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        signals = []
        for date, row in df.iterrows():
            close = row['close']
            lower = row[f'ind_bb_lower_{self.bb_period}']
            upper = row[f'ind_bb_upper_{self.bb_period}']
            rsi = row[f'ind_rsi_{self.rsi_period}']

            if pd.isna(lower) or pd.isna(upper) or pd.isna(rsi):
                continue

            # 买入信号：价格触及下轨且RSI超卖
            if close <= lower and rsi <= self.oversold:
                signals.append(Signal(
                    symbol="",
                    date=date,
                    action="BUY",
                    strength=0.8,
                    reason=f"价格{close:.2f}触及下轨{lower:.2f}，RSI{rsi:.1f}超卖"
                ))
                self.last_buy_date = date

            # 卖出信号：价格触及上轨且RSI超买，且持股天数不少于min_hold_days
            elif close >= upper and rsi >= self.overbought:
                if self.last_buy_date is not None:
                    days_held = (date - self.last_buy_date).days
                    if days_held >= self.min_hold_days:
                        signals.append(Signal(
                            symbol="",
                            date=date,
                            action="SELL",
                            strength=0.8,
                            reason=f"价格{close:.2f}触及上轨{upper:.2f}，RSI{rsi:.1f}超买，持股{days_held}天"
                        ))
        return signals
