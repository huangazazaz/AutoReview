"""MACD 背离策略。

规则:
- 底背离（价格新低 + MACD 未新低）→ BUY
- 顶背离（价格新高 + MACD 未新高）→ SELL
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from autotrade.core.interfaces import Strategy
from autotrade.core.models import Signal
from autotrade.indicators.macd import MACD


class MACDDivergenceStrategy(Strategy):
    name = "macd_divergence"

    def __init__(self, lookback: int = 30):
        self.lookback = lookback
        self.name = "macd_divergence"
        self.required_indicators = [MACD()]

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        signals: list[Signal] = []

        if "ind_macd_macd" not in df.columns:
            return signals

        macd = df["ind_macd_macd"]
        close = df["close"] if "close" in df.columns else None

        if close is None:
            return signals

        for idx in range(self.lookback, len(df)):
            lookback_close = close.iloc[idx - self.lookback: idx + 1]
            lookback_macd = macd.iloc[idx - self.lookback: idx + 1]

            if lookback_macd.isna().any():
                continue

            current_close = lookback_close.iloc[-1]
            current_macd = lookback_macd.iloc[-1]
            min_close_idx = lookback_close.idxmin()
            min_macd_at_price_low = lookback_macd.loc[min_close_idx]

            max_close_idx = lookback_close.idxmax()
            max_macd_at_price_high = lookback_macd.loc[max_close_idx]

            current_date = df.index[idx]

            # 底背离：价格新低但 MACD 未新低
            if (current_close == lookback_close.min() and
                    current_macd > min_macd_at_price_low):
                signals.append(Signal(
                    symbol="",
                    date=current_date,
                    action="BUY",
                    strength=0.8,
                    reason="MACD底背离",
                ))

            # 顶背离：价格新高但 MACD 未新高
            if (current_close == lookback_close.max() and
                    current_macd < max_macd_at_price_high):
                signals.append(Signal(
                    symbol="",
                    date=current_date,
                    action="SELL",
                    strength=0.8,
                    reason="MACD顶背离",
                ))

        return signals
