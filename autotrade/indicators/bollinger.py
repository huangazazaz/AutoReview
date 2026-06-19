"""布林带（Bollinger Bands）指标。

输出列:
- ind_bb_upper_{period}: 上轨
- ind_bb_middle_{period}: 中轨（SMA）
- ind_bb_lower_{period}: 下轨
- ind_bb_width_{period}: 带宽
"""

from __future__ import annotations

import pandas as pd
import pandas_ta as ta

from autotrade.core.interfaces import Indicator


class BollingerBands(Indicator):
    name = "bb"
    params = {"period": 20, "std": 2}

    def __init__(self, period: int = 20, std: float = 2.0):
        self.period = period
        self.std = std
        self.name = "bb"
        self.params = {"period": period, "std": std}

    def compute(self, df: pd.DataFrame) -> pd.DataFrame:
        if f"ind_bb_upper_{self.period}" in df.columns:
            return df
        # pandas_ta bbands 返回列: BBL(下轨), BBM(中轨), BBU(上轨), BBB(带宽), BBP(%b)
        result = ta.bbands(df["close"], length=self.period, std=self.std)
        if result is not None and len(result.columns) >= 3:
            df[f"ind_bb_lower_{self.period}"] = result.iloc[:, 0]
            df[f"ind_bb_middle_{self.period}"] = result.iloc[:, 1]
            df[f"ind_bb_upper_{self.period}"] = result.iloc[:, 2]
            # 带宽
            mid = df[f"ind_bb_middle_{self.period}"]
            upper = df[f"ind_bb_upper_{self.period}"]
            lower = df[f"ind_bb_lower_{self.period}"]
            df[f"ind_bb_width_{self.period}"] = (upper - lower) / mid
        return df
