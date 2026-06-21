"""游资选股筛网 — 放量起涨 + 首阴反包。

两个信号源, 任一触发即入选:
  信号1 放量起涨（Volume Breakout）: 大涨 + 放量 + 突破近期高点 + 多头位置。
  信号2 首阴反包（First-Yin Reversal）: 强势股首次回调收阴后, 次日大阳反包。

逐日扫描全市场, 按强度评分降序取前 max_picks 只。

设计详见 docs/superpowers/specs/2026-06-21-hot-money-strategy-design.md §3。
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from autotrade.core.interfaces import Screener


def _sma(series: pd.Series, period: int) -> pd.Series:
    """简单移动平均（不依赖外部库）。"""
    return series.rolling(window=period, min_periods=period).mean()


class HotMoneyScreener(Screener):
    """游资选股: 放量起涨 + 首阴反包。"""

    name = "hot_money_screener"

    def __init__(
        self,
        max_picks: int = 8,
        ma_period: int = 20,
        trend_ma_period: int = 60,
        breakout_lookback: int = 20,
        breakout_min_gain: float = 0.05,
        breakout_volume_ratio: float = 2.0,
        breakout_min_body: float = 0.03,
        reversal_lookback_strong_days: int = 10,
        reversal_strong_count: int = 2,
        reversal_strong_gain: float = 0.05,
        reversal_first_yin_drop: float = 0.02,
        reversal_gain: float = 0.03,
        exclude_min_history_days: int = 60,
    ):
        self.max_picks = max_picks
        self.ma_period = ma_period
        self.trend_ma_period = trend_ma_period
        self.breakout_lookback = breakout_lookback
        self.breakout_min_gain = breakout_min_gain
        self.breakout_volume_ratio = breakout_volume_ratio
        self.breakout_min_body = breakout_min_body
        self.reversal_lookback_strong_days = reversal_lookback_strong_days
        self.reversal_strong_count = reversal_strong_count
        self.reversal_strong_gain = reversal_strong_gain
        self.reversal_first_yin_drop = reversal_first_yin_drop
        self.reversal_gain = reversal_gain
        self.exclude_min_history_days = exclude_min_history_days
        self.name = "hot_money_screener"
        self.required_indicators = []

    def scan(
        self,
        market_data: dict[str, pd.DataFrame],
        dates: list[date],
    ) -> dict[date, list[tuple[str, float, str]]]:
        """逐日扫描, 返回每日候选（按 score 降序）。"""
        result: dict[date, list[tuple[str, float, str]]] = {}
        for scan_date in dates:
            candidates: list[tuple[str, float, str]] = []
            for symbol, df in market_data.items():
                scored = self._evaluate(symbol, df, scan_date)
                if scored is not None:
                    candidates.append(scored)
            candidates.sort(key=lambda x: x[1], reverse=True)
            result[scan_date] = candidates[: self.max_picks]
        return result

    def _evaluate(
        self, symbol: str, df: pd.DataFrame, scan_date: date,
    ) -> tuple[str, float, str] | None:
        """评估单只票在 scan_date 的信号。返回 (symbol, score, type) 或 None。"""
        if len(df) < self.exclude_min_history_days:
            return None

        idx = self._index_of_date(df, scan_date)
        if idx is None or idx < 1:
            return None

        close = df["close"]
        open_ = df["open"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        c_today = float(close.iloc[idx])
        c_prev = float(close.iloc[idx - 1])
        o_today = float(open_.iloc[idx])
        h_today = float(high.iloc[idx])
        l_today = float(low.iloc[idx])
        v_today = float(volume.iloc[idx])

        # 排除项: 停牌（volume==0）、一字板
        if v_today <= 0:
            return None
        is_one_word = abs(h_today - l_today) < 1e-6
        if is_one_word:
            return None

        # 信号1: 放量起涨
        breakout = self._check_breakout(
            c_today, c_prev, o_today, h_today, l_today, v_today,
            high, volume, close, idx,
        )
        if breakout is not None:
            return (symbol, breakout, "breakout")

        # 信号2: 首阴反包
        reversal = self._check_reversal(
            close, open_, volume, idx,
        )
        if reversal is not None:
            return (symbol, reversal, "reversal")

        return None

    def _check_breakout(
        self, c_today, c_prev, o_today, h_today, l_today, v_today,
        high_series, volume_series, close_series, idx,
    ) -> float | None:
        """信号1: 放量起涨。返回 score 或 None。"""
        if c_prev <= 0:
            return None
        gain = (c_today - c_prev) / c_prev
        # C1 涨幅
        if gain < self.breakout_min_gain:
            return None
        # C2 量比（当日量 / 过去 ma_period 均量）
        vol_start = max(0, idx - self.ma_period)
        vol_ma = float(volume_series.iloc[vol_start:idx].mean()) if idx > 0 else 0
        if vol_ma <= 0:
            return None
        vol_ratio = v_today / vol_ma
        if vol_ratio < self.breakout_volume_ratio:
            return None
        # C3 突破近 breakout_lookback 日最高价（不含当日）
        lb_start = max(0, idx - self.breakout_lookback)
        recent_high = float(high_series.iloc[lb_start:idx].max())
        if c_today <= recent_high:
            return None
        # C4 位置: close ≥ MA(trend_ma_period) × 0.95
        if idx < self.trend_ma_period:
            return None
        trend_ma = float(close_series.iloc[idx - self.trend_ma_period:idx].mean())
        if trend_ma <= 0:
            return None
        if c_today < trend_ma * 0.95:
            return None
        # C5 非一字（实体幅度）
        body = (h_today - l_today) / c_prev
        if body < self.breakout_min_body:
            return None

        # 强度评分: 涨幅×0.5 + 量比×0.3 + 突破力度×0.2
        breakout_strength = (c_today - recent_high) / recent_high if recent_high > 0 else 0
        score = gain * 0.5 + min(vol_ratio, 5.0) * 0.3 + breakout_strength * 0.2
        return score

    def _check_reversal(
        self, close_series, open_series, volume_series, idx,
    ) -> float | None:
        """信号2: 首阴反包。scan_date=idx 当天是反包日, idx-1 是首阴日。"""
        if idx < self.reversal_lookback_strong_days + 1:
            return None

        c_today = float(close_series.iloc[idx])
        c_prev = float(close_series.iloc[idx - 1])
        o_today = float(open_series.iloc[idx])
        o_prev = float(open_series.iloc[idx - 1])
        v_today = float(volume_series.iloc[idx])
        v_prev = float(volume_series.iloc[idx - 1])

        # C3 反包: 今日收阳且涨幅 ≥ reversal_gain, 且收盘 ≥ 昨日实体顶部
        if c_prev <= 0:
            return None
        reversal_gain_val = (c_today - c_prev) / c_prev
        yesterday_body_top = max(o_prev, c_prev)
        if reversal_gain_val < self.reversal_gain:
            return None
        if c_today < yesterday_body_top:
            return None
        if c_today <= o_today:
            return None  # 必须收阳

        # C2 首阴: 昨日收阴且跌幅 ≥ first_yin_drop
        if o_prev <= 0:
            return None
        if o_prev <= c_prev:
            return None  # 昨日不是阴线
        yin_drop = (o_prev - c_prev) / o_prev  # 跌幅(正数)
        if yin_drop < self.reversal_first_yin_drop:
            return None

        # C4 量能: 今日量 ≥ 昨日量
        if v_today < v_prev:
            return None

        # C1 前置强势: 过去 lookback_strong_days 天内至少 strong_count 天涨幅 ≥ strong_gain
        win_start = max(0, idx - self.reversal_lookback_strong_days - 1)
        win_end = idx - 1  # 首阴日本身不算强势日
        strong_days = 0
        for j in range(win_start, win_end):
            if j < 1:
                continue
            prev = float(close_series.iloc[j - 1])
            if prev <= 0:
                continue
            d_gain = (float(close_series.iloc[j]) - prev) / prev
            if d_gain >= self.reversal_strong_gain:
                strong_days += 1
        if strong_days < self.reversal_strong_count:
            return None

        # C5 位置: 今日 close ≥ MA(ma_period)
        if idx < self.ma_period:
            return None
        ma_val = float(close_series.iloc[idx - self.ma_period:idx].mean())
        if c_today < ma_val:
            return None

        # 强度评分
        strength_ratio = v_today / v_prev if v_prev > 0 else 1
        score = reversal_gain_val * 0.5 + min(strong_days / 3, 1) * 0.3 + min(strength_ratio, 2) * 0.2
        return score

    @staticmethod
    def _index_of_date(df: pd.DataFrame, target: date) -> int | None:
        """在 df.index 中定位 target date。兼容 Timestamp/date 索引。"""
        idx_arr = df.index
        for i, val in enumerate(idx_arr):
            d = val.date() if hasattr(val, "date") else val
            if d == target:
                return i
        return None
