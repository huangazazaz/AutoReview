"""动量多因子选股 — 聚焦近1个月走势，7因子加权打分。

两步筛选:
  1. 预过滤: 趋势（MA20>MA60）+ 流动性 + 动量区间
  2. 多因子打分:
     - 动量强度 (mom_1m): 近1月涨跌幅
     - 短期回调 (mom_5d): 近5日涨跌幅（反向）
     - 量能确认 (vol_ratio): 当日量/20日均量
     - 均线多头 (ma_score): MA5>MA10>MA20>MA60 排列
     - 回调到位 (pullback): 距MA20偏离度
     - 波动适中 (atr_ratio): ATR/收盘价
     - 稳步上涨 (consistency): 近20日阳线占比

信号标签:
  - momentum_strong: 强势追入型
  - momentum_pullback: 回调买入型
  - momentum_steady: 稳步上涨型
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from autotrade.core.interfaces import Screener


def _sma(series: pd.Series, length: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=length).mean()


def _atr(df: pd.DataFrame, length: int) -> pd.Series:
    """Average True Range using Wilder's smoothing."""
    high, low, close = df["high"], df["low"], df["close"]
    prev_close = close.shift(1)
    tr = pd.concat([
        (high - low).abs(),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / length, adjust=False).mean()


class MomentumScreener(Screener):
    """动量多因子选股: 趋势预过滤 + 7因子加权打分。"""

    name = "momentum_screener"

    def __init__(
        self,
        # 预筛选
        min_amount: float = 50_000_000,
        mom_1m_min: float = 0.03,
        mom_1m_max: float = 0.40,
        exclude_min_history_days: int = 60,
        # 因子权重
        weight_mom_1m: float = 0.20,
        weight_mom_5d: float = 0.15,
        weight_vol_ratio: float = 0.15,
        weight_ma_score: float = 0.15,
        weight_pullback: float = 0.15,
        weight_atr_ratio: float = 0.10,
        weight_consistency: float = 0.10,
        # 入选控制
        score_threshold: float = 0.65,
        top_n_per_day: int = 10,
    ):
        self.min_amount = min_amount
        self.mom_1m_min = mom_1m_min
        self.mom_1m_max = mom_1m_max
        self.exclude_min_history_days = exclude_min_history_days

        self.weight_mom_1m = weight_mom_1m
        self.weight_mom_5d = weight_mom_5d
        self.weight_vol_ratio = weight_vol_ratio
        self.weight_ma_score = weight_ma_score
        self.weight_pullback = weight_pullback
        self.weight_atr_ratio = weight_atr_ratio
        self.weight_consistency = weight_consistency

        self.score_threshold = score_threshold
        self.top_n_per_day = top_n_per_day

    # ------------------------------------------------------------------
    def scan(
        self,
        market_data: dict[str, pd.DataFrame],
        dates: list[date],
    ) -> dict[date, list[tuple[str, float, str]]]:
        """逐日扫描：预过滤 → 多因子打分 → 排序截取。"""
        result: dict[date, list[tuple[str, float, str]]] = {}

        for scan_date in dates:
            candidates: list[tuple[str, float, str]] = []

            for sym, df in market_data.items():
                idx = self._index_of(df, scan_date)
                if idx is None:
                    continue
                if idx < self.exclude_min_history_days:
                    continue
                if not self._passes_prefilter(df, idx):
                    continue
                total_score, tag = self._score(df, idx)
                if total_score >= self.score_threshold:
                    candidates.append((sym, total_score, tag))

            candidates.sort(key=lambda x: x[1], reverse=True)
            result[scan_date] = candidates[: self.top_n_per_day]

        return result

    # ------------------------------------------------------------------
    # 预过滤
    # ------------------------------------------------------------------
    def _passes_prefilter(self, df: pd.DataFrame, idx: int) -> bool:
        """趋势 + 流动性 + 动量区间预过滤。"""
        close = df["close"]
        vol = df["volume"]

        c = float(close.iloc[idx])
        if pd.isna(c) or c <= 0:
            return False

        # 排除一字板
        h = float(df["high"].iloc[idx])
        l = float(df["low"].iloc[idx])
        if abs(h - l) < 1e-6:
            return False

        # 排除停牌
        amt_today = float(df["amount"].iloc[idx]) if "amount" in df.columns else (
            float(vol.iloc[idx]) * c
        )
        if amt_today <= 0:
            return False

        # 趋势: MA20 > MA60
        ma20 = _sma(close, length=20)
        ma60 = _sma(close, length=60)
        ma20_val = float(ma20.iloc[idx])
        ma60_val = float(ma60.iloc[idx])
        if pd.isna(ma20_val) or pd.isna(ma60_val):
            return False
        if ma20_val <= ma60_val:
            return False

        # 流动性: 20日均成交额
        amt = df["amount"] if "amount" in df.columns else (vol * close)
        amt_ma20 = float(amt.iloc[max(0, idx - 20):idx + 1].mean())
        if pd.isna(amt_ma20) or amt_ma20 < self.min_amount:
            return False

        # 动量区间: 近1月涨跌幅
        mom_1m = self._calc_momentum_1m(df, idx)
        if mom_1m is None:
            return False
        if mom_1m < self.mom_1m_min or mom_1m > self.mom_1m_max:
            return False

        return True

    # ------------------------------------------------------------------
    # 多因子打分
    # ------------------------------------------------------------------
    def _score(self, df: pd.DataFrame, idx: int) -> tuple[float, str]:
        """计算7因子加权总分，返回 (total_score, tag)。"""
        factors: dict[str, float] = {}

        # 1. 动量强度
        v = self._calc_momentum_1m(df, idx)
        factors["mom_1m"] = self._score_s_curve(v, center=0.15, k=15, floor=0.0, ceil=1.0) if v is not None else 0.0

        # 2. 短期回调（反向）
        v = self._calc_momentum_5d(df, idx)
        factors["mom_5d"] = self._score_s_curve(v, center=-0.02, k=20, floor=0.0, ceil=1.0, reverse=True) if v is not None else 0.0

        # 3. 量能确认
        v = self._calc_vol_ratio(df, idx)
        factors["vol_ratio"] = self._score_peak(v, peak=1.5, width=1.0, floor=0.0) if v is not None else 0.0

        # 4. 均线多头
        factors["ma_score"] = self._calc_ma_score(df, idx)

        # 5. 回调到位
        v = self._calc_pullback(df, idx)
        factors["pullback"] = self._score_peak(v, peak=0.02, width=0.04, floor=0.0) if v is not None else 0.0

        # 6. 波动适中
        v = self._calc_atr_ratio(df, idx)
        factors["atr_ratio"] = self._score_peak(v, peak=0.035, width=0.02, floor=0.0) if v is not None else 0.0

        # 7. 稳步上涨
        v = self._calc_consistency(df, idx)
        factors["consistency"] = self._score_peak(v, peak=0.65, width=0.15, floor=0.0) if v is not None else 0.0

        # 加权总分
        total = (
            factors["mom_1m"] * self.weight_mom_1m
            + factors["mom_5d"] * self.weight_mom_5d
            + factors["vol_ratio"] * self.weight_vol_ratio
            + factors["ma_score"] * self.weight_ma_score
            + factors["pullback"] * self.weight_pullback
            + factors["atr_ratio"] * self.weight_atr_ratio
            + factors["consistency"] * self.weight_consistency
        )

        raw_mom_1m = self._calc_momentum_1m(df, idx) or 0.0
        raw_mom_5d = self._calc_momentum_5d(df, idx) or 0.0
        raw_consistency = self._calc_consistency(df, idx) or 0.0
        tag = self._classify_signal(raw_mom_1m, raw_mom_5d, raw_consistency)

        return total, tag

    # ------------------------------------------------------------------
    # 因子计算方法
    # ------------------------------------------------------------------
    def _calc_momentum_1m(self, df: pd.DataFrame, idx: int) -> float | None:
        """近1月(20交易日)涨跌幅。"""
        if idx < 20:
            return None
        c = float(df["close"].iloc[idx])
        c_20d = float(df["close"].iloc[idx - 20])
        if pd.isna(c) or pd.isna(c_20d) or c_20d <= 0:
            return None
        return (c - c_20d) / c_20d

    def _calc_momentum_5d(self, df: pd.DataFrame, idx: int) -> float | None:
        """近5交易日涨跌幅。"""
        if idx < 5:
            return None
        c = float(df["close"].iloc[idx])
        c_5d = float(df["close"].iloc[idx - 5])
        if pd.isna(c) or pd.isna(c_5d) or c_5d <= 0:
            return None
        return (c - c_5d) / c_5d

    def _calc_vol_ratio(self, df: pd.DataFrame, idx: int) -> float | None:
        """当日成交量 / 20日均量。"""
        if idx < 20:
            return None
        v_today = float(df["volume"].iloc[idx])
        v_ma20 = float(df["volume"].iloc[max(0, idx - 20):idx].mean())
        if pd.isna(v_today) or pd.isna(v_ma20) or v_ma20 <= 0:
            return None
        return v_today / v_ma20

    def _calc_ma_score(self, df: pd.DataFrame, idx: int) -> float:
        """均线多头排列程度：MA5>MA10>MA20>MA60 满足几条。"""
        close = df["close"]
        ma5 = _sma(close, length=5)
        ma10 = _sma(close, length=10)
        ma20 = _sma(close, length=20)
        ma60 = _sma(close, length=60)

        m5 = float(ma5.iloc[idx])
        m10 = float(ma10.iloc[idx])
        m20 = float(ma20.iloc[idx])
        m60_ = float(ma60.iloc[idx])

        count = 0
        if not pd.isna(m5) and not pd.isna(m10) and m5 > m10:
            count += 1
        if not pd.isna(m10) and not pd.isna(m20) and m10 > m20:
            count += 1
        if not pd.isna(m20) and not pd.isna(m60_) and m20 > m60_:
            count += 1
        # 总共3个比较，映射到0~1
        score_map = {0: 0.1, 1: 0.3, 2: 0.6, 3: 1.0}
        return score_map.get(count, 0.1)

    def _calc_pullback(self, df: pd.DataFrame, idx: int) -> float | None:
        """收盘价距MA20的偏离度 (close - ma20) / ma20。"""
        close = df["close"]
        ma20 = _sma(close, length=20)
        c = float(close.iloc[idx])
        m20 = float(ma20.iloc[idx])
        if pd.isna(c) or pd.isna(m20) or m20 <= 0:
            return None
        return (c - m20) / m20

    def _calc_atr_ratio(self, df: pd.DataFrame, idx: int) -> float | None:
        """ATR(20) / 收盘价。"""
        if idx < 20:
            return None
        c = float(df["close"].iloc[idx])
        if pd.isna(c) or c <= 0:
            return None
        atr_series = _atr(df, length=20)
        atr_val = float(atr_series.iloc[idx])
        if pd.isna(atr_val):
            return None
        return atr_val / c

    def _calc_consistency(self, df: pd.DataFrame, idx: int) -> float | None:
        """近20日阳线占比 (close > open 的天数 / 20)。"""
        if idx < 20:
            return None
        closes = df["close"].iloc[idx - 19:idx + 1]
        opens = df["open"].iloc[idx - 19:idx + 1]
        up_days = (closes > opens).sum()
        return up_days / 20

    # ------------------------------------------------------------------
    # 打分映射函数
    # ------------------------------------------------------------------
    @staticmethod
    def _score_s_curve(x: float, center: float, k: float,
                       floor: float = 0.0, ceil: float = 1.0,
                       reverse: bool = False) -> float:
        """S曲线映射: 1/(1+exp(-k*(x-center)))，可选反向。"""
        raw = 1.0 / (1.0 + np.exp(-k * (x - center)))
        if reverse:
            raw = 1.0 - raw
        return floor + (ceil - floor) * raw

    @staticmethod
    def _score_peak(x: float, peak: float, width: float,
                    floor: float = 0.0) -> float:
        """峰值型映射: 在 peak 附近得高分，偏离后高斯衰减。"""
        z = (x - peak) / (width + 1e-9)
        raw = np.exp(-0.5 * z * z)
        return floor + (1.0 - floor) * raw

    # ------------------------------------------------------------------
    # 信号分类
    # ------------------------------------------------------------------
    def _classify_signal(self, raw_mom_1m: float, raw_mom_5d: float,
                         raw_consistency: float) -> str:
        """根据原始因子值给信号打标签。

        Args:
            raw_mom_1m: 近1月涨跌幅（原始值，如 0.15 = 15%）
            raw_mom_5d: 近5日涨跌幅（原始值）
            raw_consistency: 近20日阳线占比（原始值，如 0.65 = 65%）
        """
        # mom_1m 高 + mom_5d 为正 → strong
        if raw_mom_1m > 0.10 and raw_mom_5d > 0.005:
            return "momentum_strong"

        # mom_1m 中等 + mom_5d 为负 → pullback
        if raw_mom_1m > 0.05 and raw_mom_5d < -0.005:
            return "momentum_pullback"

        # consistency 突出 → steady
        if raw_consistency > 0.75:
            return "momentum_steady"

        # 默认
        return "momentum_steady"

    # ------------------------------------------------------------------
    @staticmethod
    def _index_of(df: pd.DataFrame, target: date) -> int | None:
        """查找 target date 在 DataFrame 中的整数索引。"""
        for i, val in enumerate(df.index):
            d = val.date() if hasattr(val, "date") else val
            if d == target:
                return i
        return None
