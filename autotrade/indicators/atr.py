"""ATR indicator (Average True Range) using Wilder's smoothing.

Output column:
- ind_atr_{period}: Average True Range
"""
from __future__ import annotations

import pandas as pd
import pandas_ta as ta

from autotrade.core.interfaces import Indicator


class ATR(Indicator):
    name = "atr"
    params = {"period": 20}

    def __init__(self, period: int = 20):
        self.period = period
        self.name = "atr"
        self.params = {"period": period}

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        col = f"ind_atr_{self.period}"
        if col in df.columns:
            return df
        df[col] = ta.atr(df["high"], df["low"], df["close"], length=self.period)
        return df
