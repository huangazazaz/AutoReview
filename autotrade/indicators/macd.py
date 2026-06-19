"""MACD 指标。

输出列:
- ind_macd_macd: MACD 快线
- ind_macd_signal: 信号线
- ind_macd_histogram: 柱状图（macd - signal）
"""

from __future__ import annotations

import pandas as pd
import pandas_ta as ta

from autotrade.core.interfaces import Indicator


class MACD(Indicator):
    name = "macd"
    params = {"fast": 12, "slow": 26, "signal": 9}

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        self.fast = fast
        self.slow = slow
        self.signal = signal
        self.name = "macd"
        self.params = {"fast": fast, "slow": slow, "signal": signal}

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        if "ind_macd_macd" in df.columns:
            return df
        result = ta.macd(df["close"], fast=self.fast, slow=self.slow, signal=self.signal)
        if result is not None:
            df["ind_macd_macd"] = result.iloc[:, 0]
            df["ind_macd_signal"] = result.iloc[:, 1]
            df["ind_macd_histogram"] = result.iloc[:, 2]
        return df
