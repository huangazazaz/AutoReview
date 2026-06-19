"""RSI 指标。

输出列:
- ind_rsi_{period}: 相对强弱指标
"""

from __future__ import annotations

import pandas as pd
import pandas_ta as ta

from autotrade.core.interfaces import Indicator


class RSI(Indicator):
    name = "rsi"
    params = {"period": 14}

    def __init__(self, period: int = 14):
        self.period = period
        self.name = "rsi"
        self.params = {"period": period}

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        col = f"ind_rsi_{self.period}"
        if col in df.columns:
            return df
        df[col] = ta.rsi(df["close"], length=self.period)
        return df
