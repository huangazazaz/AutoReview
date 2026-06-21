"""游资超短线择时策略 v2 — 激进止盈 + 趋势保护。

四道闸门（任一触发即 SELL）:
  闸门1 移动止盈: 最高涨幅 ≥ 5% 后，回撤 ≥ 2% 即锁利（激进锁利）
  闸门2 时间止损: 持仓 5 天且收益 < 3% 即离场
  闸门3 硬止损:   收益 ≤ -5% 即清仓
  闸门4 趋势破坏: 当日 MA20 < MA60 → 趋势转弱，立即离场

入场: 仅在 allowed_entry_dates（Screener 选出）发 BUY，满仓。
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from autotrade.core.interfaces import Strategy
from autotrade.core.models import Signal


def _sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=period).mean()


class HotMoneyStrategy(Strategy):
    """游资 v2: 激进锁利 + 趋势破坏离场。"""

    name = "hot_money"

    def __init__(
        self,
        allowed_entry_dates: list[date] | None = None,
        trailing_activate: float = 0.05,
        trailing_drawdown: float = 0.02,
        time_stop_days: int = 5,
        time_stop_min_gain: float = 0.03,
        stop_loss: float = 0.05,
        trend_ma_fast: int = 20,
        trend_ma_mid: int = 60,
    ):
        self.allowed_entry_dates = set(allowed_entry_dates or [])
        self.trailing_activate = trailing_activate
        self.trailing_drawdown = trailing_drawdown
        self.time_stop_days = time_stop_days
        self.time_stop_min_gain = time_stop_min_gain
        self.stop_loss = stop_loss
        self.trend_ma_fast = trend_ma_fast
        self.trend_ma_mid = trend_ma_mid
        self.name = "hot_money"
        self.required_indicators = []

    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        signals: list[Signal] = []
        if "close" not in df.columns:
            return signals

        # 预计算趋势均线
        close_series = df["close"]
        ma_fast = _sma(close_series, self.trend_ma_fast)
        ma_mid = _sma(close_series, self.trend_ma_mid)

        entry_price: float | None = None
        entry_idx: int = 0
        highest_price: float = 0.0
        trailing_active: bool = False

        for idx in range(len(df)):
            current_close = float(close_series.iloc[idx])
            if pd.isna(current_close):
                continue
            current_date = df.index[idx]
            today = current_date.date() if hasattr(current_date, "date") else current_date

            in_position = entry_price is not None
            mf = float(ma_fast.iloc[idx])
            mm = float(ma_mid.iloc[idx])

            # ---- 空仓: 检查是否在允许进场日 ----
            if not in_position:
                if today in self.allowed_entry_dates:
                    signals.append(Signal(
                        symbol="", date=current_date, action="BUY",
                        strength=1.0, reason="游资信号进场",
                    ))
                    entry_price = current_close
                    entry_idx = idx
                    highest_price = current_close
                    trailing_active = False
                    continue

            # ---- 持仓: 检查四道闸门 ----
            if in_position:
                if current_close > highest_price:
                    highest_price = current_close

                gain = (current_close - entry_price) / entry_price
                highest_gain = (highest_price - entry_price) / entry_price
                days_held = idx - entry_idx

                if highest_gain >= self.trailing_activate:
                    trailing_active = True

                # 闸门3: 硬止损（最高优先级）
                if gain <= -self.stop_loss:
                    signals.append(Signal(
                        symbol="", date=current_date, action="SELL",
                        strength=1.0, reason=f"硬止损({gain:.1%})",
                    ))
                    entry_price = None; highest_price = 0.0; trailing_active = False
                    continue

                # 闸门4: 趋势破坏（MA20 < MA60）
                if not pd.isna(mf) and not pd.isna(mm) and mf < mm:
                    signals.append(Signal(
                        symbol="", date=current_date, action="SELL",
                        strength=1.0, reason=f"趋势破坏(MA{self.trend_ma_fast}<MA{self.trend_ma_mid})",
                    ))
                    entry_price = None; highest_price = 0.0; trailing_active = False
                    continue

                # 闸门2: 时间止损
                if days_held >= self.time_stop_days and gain < self.time_stop_min_gain:
                    signals.append(Signal(
                        symbol="", date=current_date, action="SELL",
                        strength=1.0, reason=f"时间止损({days_held}天 +{gain:.1%})",
                    ))
                    entry_price = None; highest_price = 0.0; trailing_active = False
                    continue

                # 闸门1: 移动止盈
                if trailing_active:
                    dd = (current_close - highest_price) / highest_price
                    if dd <= -self.trailing_drawdown:
                        signals.append(Signal(
                            symbol="", date=current_date, action="SELL",
                            strength=1.0, reason=f"移动止盈(+{highest_gain:.1%}→{gain:.1%})",
                        ))
                        entry_price = None; highest_price = 0.0; trailing_active = False
                        continue

        return signals
