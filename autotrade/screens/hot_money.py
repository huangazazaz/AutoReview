"""游资选股筛网 v2 — 趋势预过滤 + 三大信号源。

两步筛选:
  1. 预过滤（砍掉 ~80% 票）:
     - 趋势: MA20 > MA60 > MA120（多头排列）
     - 流动性: 日均成交额 > 5000 万
  2. 信号扫描:
     - 趋势回踩: 多头票回踩 MA20 后放量反弹
     - 动量突破: 多头票放量突破 10 日高点
     - 强度确认: 强势涨幅 + 放量 + 趋势完好

设计目标: 最大化收益率，不做随机，全市场精选。
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from autotrade.core.interfaces import Screener


def _sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=period).mean()


class HotMoneyScreener(Screener):
    """游资选股 v2: 趋势预过滤 + 三信号。"""

    name = "hot_money_screener"

    def __init__(
        self,
        max_picks: int = 3,
        min_score: float = 0.15,                # 最低评分门槛
        # 预过滤
        min_daily_amount: float = 50_000_000,   # 最低日均成交额
        trend_ma_fast: int = 20,
        trend_ma_mid: int = 60,
        trend_ma_slow: int = 120,
        # 动量排名
        momentum_lookback: int = 60,             # 动量回看天数
        momentum_min: float = 0.05,              # 最低 60 日涨幅（排除弱势票）
        momentum_max: float = 0.60,              # 最高 60 日涨幅（排除过度拉伸票）
        # 信号 A: 趋势回踩
        pullback_near_ma_pct: float = 0.03,      # 收盘价距 MA20 的百分比内
        pullback_gain_min: float = 0.015,         # 回踩日最小涨幅
        pullback_vol_ratio: float = 1.5,          # 量比
        # 信号 B: 动量突破
        breakout_period: int = 10,                # 突破 N 日高点
        breakout_gain_min: float = 0.03,          # 当日最小涨幅
        breakout_vol_ratio: float = 1.5,          # 量比
        # 信号 C: 强度确认
        strength_gain_min: float = 0.03,          # 最小涨幅
        strength_vol_ratio: float = 2.0,          # 量比
        # 排除
        exclude_min_history_days: int = 120,
    ):
        self.max_picks = max_picks
        self.min_score = min_score
        self.min_daily_amount = min_daily_amount
        self.trend_ma_fast = trend_ma_fast
        self.trend_ma_mid = trend_ma_mid
        self.trend_ma_slow = trend_ma_slow
        self.momentum_lookback = momentum_lookback
        self.momentum_min = momentum_min
        self.momentum_max = momentum_max
        self.pullback_near_ma_pct = pullback_near_ma_pct
        self.pullback_gain_min = pullback_gain_min
        self.pullback_vol_ratio = pullback_vol_ratio
        self.breakout_period = breakout_period
        self.breakout_gain_min = breakout_gain_min
        self.breakout_vol_ratio = breakout_vol_ratio
        self.strength_gain_min = strength_gain_min
        self.strength_vol_ratio = strength_vol_ratio
        self.exclude_min_history_days = exclude_min_history_days
        self.ma_slope_days = 5                     # MA 斜率检查天数
        self.market_breadth_min = 0.0              # 暂关闭，市场震荡期不宜用
        self.name = "hot_money_screener"

    # ------------------------------------------------------------------
    def scan(
        self,
        market_data: dict[str, pd.DataFrame],
        dates: list[date],
    ) -> dict[date, list[tuple[str, float, str]]]:
        """逐日扫描：预过滤 → 动量排名 → 信号评估。"""
        # ---- 预计算均线 ----
        for sym, df in market_data.items():
            if len(df) < self.exclude_min_history_days:
                continue
            df["_ma_fast"] = _sma(df["close"], self.trend_ma_fast)
            df["_ma_mid"] = _sma(df["close"], self.trend_ma_mid)
            df["_ma_slow"] = _sma(df["close"], self.trend_ma_slow)
            df["_amount_ma"] = _sma(df["amount"], self.trend_ma_fast)
            # 动量列
            df["_mom_ret"] = df["close"].pct_change(periods=self.momentum_lookback)

        result: dict[date, list[tuple[str, float, str]]] = {}
        for scan_date in dates:
            # ---- 第一遍：预过滤 + 动量区间 ----
            passing: list[tuple[str, int, float]] = []  # (sym, idx, mom_ret)
            for sym, df in market_data.items():
                idx = self._index_of(df, scan_date)
                if idx is None:
                    continue
                if not self._passes_prefilter(df, idx):
                    continue
                mr = float(df["_mom_ret"].iloc[idx])
                if pd.isna(mr):
                    continue
                # 动量区间过滤：太弱或太强都不要
                if mr < self.momentum_min or mr > self.momentum_max:
                    continue
                passing.append((sym, idx, mr))

            if not passing:
                result[scan_date] = []
                continue

            # ---- 市场广度: 多头比例不足则空仓 ----
            if self.market_breadth_min > 0:
                # 统计全市场 MA20 > MA60 的比例
                bull_count = 0
                total_checked = 0
                for sym, df in market_data.items():
                    if "_ma_fast" not in df.columns:
                        continue
                    i = self._index_of(df, scan_date)
                    if i is None:
                        continue
                    mf = float(df["_ma_fast"].iloc[i])
                    mm = float(df["_ma_mid"].iloc[i])
                    if not pd.isna(mf) and not pd.isna(mm) and mf > mm:
                        bull_count += 1
                    total_checked += 1
                if total_checked > 0 and bull_count / total_checked < self.market_breadth_min:
                    result[scan_date] = []
                    continue

            # ---- 第二遍：信号评估 ----
            candidates: list[tuple[str, float, str]] = []
            for sym, idx, _mr in passing:
                scored = self._evaluate(sym, market_data[sym], idx)
                if scored is not None:
                    candidates.append(scored)
            candidates.sort(key=lambda x: x[1], reverse=True)
            qualified = [c for c in candidates if c[1] >= self.min_score]
            result[scan_date] = qualified[: self.max_picks]

        return result

    def explain(
        self, market_data: dict[str, pd.DataFrame],
        symbol: str, date: date,
    ) -> dict[str, float]:
        """返回热钱选股的因子明细得分。"""
        import numpy as np
        df = market_data.get(symbol)
        if df is None:
            return {}
        idx = self._index_of(df, date)
        if idx is None or idx < self.exclude_min_history_days:
            return {}
        if not self._passes_prefilter(df, idx):
            return {}

        factors: dict[str, float] = {}

        # 趋势强度: MA20 / MA60 的比值映射到 0-1
        ma_f = float(df["_ma_fast"].iloc[idx])
        ma_m = float(df["_ma_mid"].iloc[idx])
        if not np.isnan(ma_f) and not np.isnan(ma_m) and ma_m > 0:
            trend = min((ma_f / ma_m - 1) * 5, 1.0)
            factors["趋势强度"] = round(max(trend, 0.0), 4)
        else:
            factors["趋势强度"] = 0.0

        # 动量得分: 60日涨幅映射
        if "_mom_ret" in df.columns:
            mr = float(df["_mom_ret"].iloc[idx])
            if not np.isnan(mr):
                momentum = min(max(mr, 0.05), 0.40) / 0.35
                factors["动量得分"] = round(momentum, 4)
            else:
                factors["动量得分"] = 0.0
        else:
            factors["动量得分"] = 0.0

        # 当日量比
        v = float(df["volume"].iloc[idx])
        vol_ma = float(df["volume"].iloc[max(0, idx - 20):idx].mean()) if idx > 0 else 0
        if vol_ma > 0:
            vol_ratio = v / vol_ma
            factors["量能得分"] = round(min(vol_ratio / 3.0, 1.0), 4)
        else:
            factors["量能得分"] = 0.0

        # 当日涨幅
        c = float(df["close"].iloc[idx])
        c_prev = float(df["close"].iloc[idx - 1])
        if c_prev > 0:
            gain = (c - c_prev) / c_prev
            factors["涨幅得分"] = round(min(max(gain, 0.0) / 0.05, 1.0), 4)
        else:
            factors["涨幅得分"] = 0.0

        # 突破力度（收盘价 vs 10日最高价）
        if idx >= 10:
            recent_high = float(df["high"].iloc[idx - 10:idx].max())
            if recent_high > 0 and c > recent_high:
                break_str = (c - recent_high) / recent_high
                factors["突破力度"] = round(min(break_str * 10, 1.0), 4)
            else:
                factors["突破力度"] = 0.0
        else:
            factors["突破力度"] = 0.0

        return factors

    # ------------------------------------------------------------------
    def _evaluate(
        self, sym: str, df: pd.DataFrame, idx: int,
    ) -> tuple[str, float, str] | None:
        """在 idx 日评估单只票。先预过滤，再扫信号。"""
        if idx < self.exclude_min_history_days:
            return None
        if not self._passes_prefilter(df, idx):
            return None

        # 信号 A: 趋势回踩（优先级最高，最可靠）
        score = self._check_pullback(df, idx)
        if score is not None:
            return (sym, score, "pullback")

        # 信号 B: 动量突破
        score = self._check_breakout(df, idx)
        if score is not None:
            return (sym, score, "breakout")

        # 信号 C: 强度确认
        score = self._check_strength(df, idx)
        if score is not None:
            return (sym, score, "strength")

        return None

    # ------------------------------------------------------------------
    # 预过滤
    # ------------------------------------------------------------------
    def _passes_prefilter(self, df: pd.DataFrame, idx: int) -> bool:
        """趋势 + 流动性预过滤。"""
        if "_ma_fast" not in df.columns:
            return False
        close = df["close"]
        vol = df["volume"]
        open_ = df["open"]
        high = df["high"]
        low = df["low"]

        c = float(close.iloc[idx])
        if pd.isna(c) or c <= 0:
            return False

        # 流动性: 当日成交额 > 0（排除停牌）
        amt_today = float(df["amount"].iloc[idx]) if "amount" in df.columns else (
            float(vol.iloc[idx]) * c
        )
        if amt_today <= 0:
            return False

        # 一字板排除
        h = float(high.iloc[idx])
        l = float(low.iloc[idx])
        if abs(h - l) < 1e-6:
            return False

        # 趋势: MA20 > MA60 > MA120，且 MA20 斜率向上
        ma_f = float(df["_ma_fast"].iloc[idx])
        ma_m = float(df["_ma_mid"].iloc[idx])
        ma_s = float(df["_ma_slow"].iloc[idx])
        if pd.isna(ma_f) or pd.isna(ma_m) or pd.isna(ma_s):
            return False
        if not (ma_f > ma_m > ma_s):
            return False
        # MA20 斜率: 今天 > N 天前
        # （暂放宽：只要求 MA20 > MA60 > MA120 即可，斜率检查过于严格）
        # slope_idx = max(0, idx - self.ma_slope_days)
        # ma_f_past = float(df["_ma_fast"].iloc[slope_idx])
        # if pd.isna(ma_f_past) or ma_f <= ma_f_past:
        #     return False

        # 流动性: 日均成交额
        amt_ma = float(df["_amount_ma"].iloc[idx])
        if pd.isna(amt_ma) or amt_ma < self.min_daily_amount:
            return False

        return True

    # ------------------------------------------------------------------
    # 信号 A: 趋势回踩
    # ------------------------------------------------------------------
    def _check_pullback(self, df: pd.DataFrame, idx: int) -> float | None:
        """趋势多头排列中，回踩 MA20 后放量反弹。"""
        if idx < 2:
            return None
        close = df["close"]
        vol = df["volume"]
        ma_f = float(df["_ma_fast"].iloc[idx])
        c = float(close.iloc[idx])
        c_prev = float(close.iloc[idx - 1])
        v = float(vol.iloc[idx])

        # 收盘价在 MA20 附近（±pullback_near_ma_pct）
        if ma_f <= 0:
            return None
        dist = abs(c - ma_f) / ma_f
        if dist > self.pullback_near_ma_pct:
            return None

        # 当日收阳且涨幅达标
        if c <= c_prev:
            return None
        gain = (c - c_prev) / c_prev
        if gain < self.pullback_gain_min:
            return None

        # 放量
        if idx < 5:
            return None
        vol_ma = float(vol.iloc[max(0, idx - 20):idx].mean())
        if vol_ma <= 0:
            return None
        vol_ratio = v / vol_ma
        if vol_ratio < self.pullback_vol_ratio:
            return None

        # 距离 MA20 越近、涨幅越大，得分越高
        score = (1 - dist / self.pullback_near_ma_pct) * 0.5 + min(gain, 0.1) * 0.3 + min(vol_ratio, 3) * 0.2
        return score

    # ------------------------------------------------------------------
    # 信号 B: 动量突破
    # ------------------------------------------------------------------
    def _check_breakout(self, df: pd.DataFrame, idx: int) -> float | None:
        """放量突破 N 日高点。"""
        if idx < self.breakout_period:
            return None
        close = df["close"]
        high = df["high"]
        vol = df["volume"]

        c = float(close.iloc[idx])
        c_prev = float(close.iloc[idx - 1])
        v = float(vol.iloc[idx])

        # 突破 N 日最高价（不含当日）
        recent_high = float(high.iloc[idx - self.breakout_period:idx].max())
        if c <= recent_high:
            return None

        # 涨幅
        gain = (c - c_prev) / c_prev if c_prev > 0 else 0
        if gain < self.breakout_gain_min:
            return None

        # 放量
        vol_ma = float(vol.iloc[max(0, idx - 20):idx].mean()) if idx > 0 else 0
        if vol_ma <= 0:
            return None
        vol_ratio = v / vol_ma
        if vol_ratio < self.breakout_vol_ratio:
            return None

        # 突破力度越大越好
        break_strength = (c - recent_high) / recent_high if recent_high > 0 else 0
        score = break_strength * 0.4 + min(gain, 0.1) * 0.3 + min(vol_ratio, 3) * 0.3
        return score

    # ------------------------------------------------------------------
    # 信号 C: 强度确认
    # ------------------------------------------------------------------
    def _check_strength(self, df: pd.DataFrame, idx: int) -> float | None:
        """趋势完好 + 当日强势涨幅 + 放量。"""
        close = df["close"]
        vol = df["volume"]

        c = float(close.iloc[idx])
        c_prev = float(close.iloc[idx - 1])
        v = float(vol.iloc[idx])

        gain = (c - c_prev) / c_prev if c_prev > 0 else 0
        if gain < self.strength_gain_min:
            return None

        # 收阳
        o = float(df["open"].iloc[idx])
        if c <= o:
            return None

        # 放量
        vol_ma = float(vol.iloc[max(0, idx - 20):idx].mean()) if idx > 0 else 0
        if vol_ma <= 0:
            return None
        vol_ratio = v / vol_ma
        if vol_ratio < self.strength_vol_ratio:
            return None

        score = min(gain, 0.1) * 0.5 + min(vol_ratio, 3) * 0.5
        return score

    # ------------------------------------------------------------------
    @staticmethod
    def _index_of(df: pd.DataFrame, target: date) -> int | None:
        for i, val in enumerate(df.index):
            d = val.date() if hasattr(val, "date") else val
            if d == target:
                return i
        return None
