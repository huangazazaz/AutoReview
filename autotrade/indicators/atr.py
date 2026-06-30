"""ATR indicator (Average True Range) using Wilder's smoothing.

Output column:
- ind_atr_{period}: Average True Range
"""
from __future__ import annotations

import pandas as pd

from autotrade.core.interfaces import Indicator


class ATR(Indicator):
    name = "atr"
    params = {"period": 20}

    def __init__(self, period: int = 20):
        self.period = int(period)
        self.name = "atr"
        self.params = {"period": self.period}

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        col = f"ind_atr_{self.period}"
        if col in df.columns:
            return df

        high, low, close = df["high"], df["low"], df["close"]
        prev_close = close.shift(1)
        tr = pd.concat([
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ], axis=1).max(axis=1)
        # Use Wilder's smoothing: first value is SMA, then EMA
        atr = tr.ewm(alpha=1 / self.period, adjust=False).mean()
        atr.iloc[:self.period] = float('nan')
        df[col] = atr
        return df
