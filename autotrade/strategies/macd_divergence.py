"""MACD 背离策略。

规则:
- 底背离（价格新低 + MACD 未新低）→ BUY
- 顶背离（价格新高 + MACD 未新高）→ SELL

参数（来自 config/strategies/macd_divergence.yaml）:
  fast: 12            # MACD 快线周期
  slow: 26            # MACD 慢线周期
  signal: 9           # 信号线周期
  lookback: 30        # 背离检测窗口
  buy_strength: 0.8   # 底背离买入信号强度
  sell_strength: 0.8  # 顶背离卖出信号强度
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from autotrade.core.interfaces import Strategy
from autotrade.core.models import Signal
from autotrade.indicators.macd import MACD




def _parse_list(val):
    if isinstance(val, list):
        return val
    if isinstance(val, str):
        import json
        try:
            p = json.loads(val)
            if isinstance(p, list):
                return p
        except:
            pass
    return val or []
class MACDDivergenceStrategy(Strategy):
    name = "macd_divergence"

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9,
                 lookback: int = 30,
                 buy_strength: float = 0.8,
                 sell_strength: float = 0.8):
        self.fast = int(fast)
        self.slow = int(slow)
        self.signal = int(signal)
        self.lookback = int(lookback)
        self.buy_strength = int(buy_strength)
        self.sell_strength = int(sell_strength)
        self.name = "macd_divergence"
        self.required_indicators = [MACD(fast=fast, slow=slow, signal=signal)]

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
            current_date = df.index[idx]

            # 排除当天，取前 lookback 根 bar 作为参照窗口
            prev_close = lookback_close.iloc[:-1]
            prev_macd = lookback_macd.iloc[:-1]

            if len(prev_close) == 0:
                continue

            # ====================================================
            # 底背离：价格创严格新低，但 MACD 高于前低时的 MACD
            # ====================================================
            prev_low_idx = prev_close.idxmin()
            prev_low_macd = prev_macd.loc[prev_low_idx]
            prev_low_price = prev_close.min()

            if current_close < prev_low_price and current_macd > prev_low_macd:
                signals.append(Signal(
                    symbol="",
                    date=current_date,
                    action="BUY",
                    strength=self.buy_strength,
                    reason="MACD底背离",
                ))

            # ====================================================
            # 顶背离：价格创严格新高，但 MACD 低于前高时的 MACD
            # ====================================================
            prev_high_idx = prev_close.idxmax()
            prev_high_macd = prev_macd.loc[prev_high_idx]
            prev_high_price = prev_close.max()

            if current_close > prev_high_price and current_macd < prev_high_macd:
                signals.append(Signal(
                    symbol="",
                    date=current_date,
                    action="SELL",
                    strength=self.sell_strength,
                    reason="MACD顶背离",
                ))

        return signals
