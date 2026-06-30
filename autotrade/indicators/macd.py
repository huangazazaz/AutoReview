"""MACD 指标。

输出列:
- ind_macd_macd: MACD 快线
- ind_macd_signal: 信号线
- ind_macd_histogram: 柱状图（macd - signal）
"""

from __future__ import annotations

import pandas as pd

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

        close = df["close"]
        ema_fast = close.ewm(span=self.fast, adjust=False).mean()
        ema_slow = close.ewm(span=self.slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=self.signal, adjust=False).mean()
        histogram = macd_line - signal_line

        df["ind_macd_macd"] = macd_line
        df["ind_macd_signal"] = signal_line
        df["ind_macd_histogram"] = histogram
        return df
