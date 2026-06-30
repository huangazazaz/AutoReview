"""RSI 指标。

输出列:
- ind_rsi_{period}: 相对强弱指标
"""

from __future__ import annotations

import pandas as pd

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

        delta = df["close"].diff()
        gain = delta.clip(lower=0)
        loss = (-delta).clip(lower=0)
        avg_gain = gain.ewm(alpha=1 / self.period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / self.period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, 1e-10)
        df[col] = 100.0 - (100.0 / (1.0 + rs))
        return df
