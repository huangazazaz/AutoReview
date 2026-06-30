"""均线指标（MA/EMA）。

输出列:
- ind_ma_{period}: 简单移动平均线
- ind_ema_{period}: 指数移动平均线
"""

from __future__ import annotations

import pandas as pd

from autotrade.core.interfaces import Indicator


class MA(Indicator):
    name = "ma"
    params = {"period": 20}

    def __init__(self, period: int = 20, mode: str = "sma"):
        self.period = period
        self.mode = mode
        self.name = "ma"
        self.params = {"period": period, "mode": mode}

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        col = f"ind_ma_{self.period}"
        if col in df.columns:
            return df

        if self.mode == "ema":
            df[col] = df["close"].ewm(span=self.period, adjust=False).mean()
        else:
            df[col] = df["close"].rolling(window=self.period).mean()
        return df


class EMA(Indicator):
    name = "ema"
    params = {"period": 20}

    def __init__(self, period: int = 20):
        self.period = period
        self.name = "ema"
        self.params = {"period": period}

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        col = f"ind_ema_{self.period}"
        if col in df.columns:
            return df
        df[col] = df["close"].ewm(span=self.period, adjust=False).mean()
        return df
