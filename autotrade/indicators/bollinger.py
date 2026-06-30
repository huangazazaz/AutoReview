"""布林带（Bollinger Bands）指标。

输出列:
- ind_bb_upper_{period}: 上轨
- ind_bb_middle_{period}: 中轨（SMA）
- ind_bb_lower_{period}: 下轨
- ind_bb_width_{period}: 带宽
"""

from __future__ import annotations

import pandas as pd

from autotrade.core.interfaces import Indicator


class BollingerBands(Indicator):
    name = "bb"
    params = {"period": 20, "std": 2}

    def __init__(self, period: int = 20, std: float = 2.0):
        self.period = int(period)
        self.std = float(std)
        self.name = "bb"
        self.params = {"period": self.period, "std": self.std}

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        if f"ind_bb_upper_{self.period}" in df.columns:
            return df

        close = df["close"]
        middle = close.rolling(window=self.period).mean()
        std_dev = close.rolling(window=self.period).std()
        upper = middle + self.std * std_dev
        lower = middle - self.std * std_dev

        df[f"ind_bb_upper_{self.period}"] = upper
        df[f"ind_bb_middle_{self.period}"] = middle
        df[f"ind_bb_lower_{self.period}"] = lower
        df[f"ind_bb_width_{self.period}"] = (upper - lower) / middle
        return df
