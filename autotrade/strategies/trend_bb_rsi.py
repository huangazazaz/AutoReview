"""布林带 + RSI + MACD + 量能 多因子策略。

四维共振，追求高胜率/高收益：
  趋势 —— 布林带中轨定方向（价格 > 中轨 = 多头）
  动量 —— RSI 识别超买超卖，避免追高
  反转 —— MACD 柱状图捕捉动能转折
  量能 —— 放量确认突破有效性

买入（全部条件同时满足）:
  1. 收盘价 > BB 中轨                     — 多头趋势
  2. RSI 在 [buy_low, buy_high] 之间    — 非超买，有上行空间
  3. 成交量 > vol_factor × 20日均量      — 放量确认
  4. MACD 柱状图 > 0 且 > 前一日           — 动能转正 / 加速

卖出（任一触发）:
  1. 收盘价 < BB 下轨                     — 趋势破位
  2. RSI > rsi_sell                      — 超买
  3. 亏损 ≥ stop_loss                     — 硬止损
  4. 从最高价回撤 ≥ trailing_stop         — 移动止盈
  5. MACD 柱状图 < 0 且连续 2 日缩小      — 动能衰竭
  6. 阶梯止盈（take_profit_levels）       — 分批锁定利润

参数（来自 config/strategies/trend_bb_rsi.yaml）:
  bb_period: 20               # 布林带周期
  bb_std: 2.0                 # 布林带标准差
  rsi_period: 14              # RSI 周期
  rsi_buy_low: 30             # RSI 买入下限
  rsi_buy_high: 55            # RSI 买入上限
  rsi_sell: 75                # RSI 超买卖出阈值
  macd_fast: 12               # MACD 快线
  macd_slow: 26               # MACD 慢线
  macd_signal: 9              # MACD 信号线
  vol_period: 20              # 量能均线周期
  vol_factor: 1.2             # 放量倍数
  stop_loss: 0.07             # 止损线
  trailing_stop: 0.10         # 移动止盈回撤线
  take_profit_levels:         # 阶梯止盈 [(涨幅阈值, 卖出比例), ...]
    - [0.15, 0.4]
    - [0.30, 0.4]
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from autotrade.core.interfaces import Strategy
from autotrade.core.models import Signal
from autotrade.indicators.bollinger import BollingerBands
from autotrade.indicators.macd import MACD
from autotrade.indicators.rsi import RSI


class TrendBBRSIStrategy(Strategy):
    name = "trend_bb_rsi"

    def __init__(
        self,
        bb_period: int = 20,
        bb_std: float = 2.0,
        rsi_period: int = 14,
        rsi_buy_low: float = 30,
        rsi_buy_high: float = 55,
        rsi_sell: float = 75,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        vol_period: int = 20,
        vol_factor: float = 1.2,
        stop_loss: float = 0.07,
        trailing_stop: float = 0.10,
        take_profit_levels: list[list[float]] | None = None,
    ):
        self.bb_period = int(bb_period)
        self.bb_std = float(bb_std)
        self.rsi_period = int(rsi_period)
        self.rsi_buy_low = int(rsi_buy_low)
        self.rsi_buy_high = int(rsi_buy_high)
        self.rsi_sell = int(rsi_sell)
        self.macd_fast = int(macd_fast)
        self.macd_slow = int(macd_slow)
        self.macd_signal = int(macd_signal)
        self.vol_period = int(vol_period)
        self.vol_factor = int(vol_factor)
        self.stop_loss = float(stop_loss)
        self.trailing_stop = float(trailing_stop)

        self.name = "trend_bb_rsi"
        self.required_indicators = [
            BollingerBands(period=bb_period, std=bb_std),
            RSI(period=rsi_period),
            MACD(fast=macd_fast, slow=macd_slow, signal=macd_signal),
        ]

        # 阶梯止盈
        if take_profit_levels:
            self.take_profit_levels = [(float(tp[0]), float(tp[1])) for tp in take_profit_levels]
        else:
            self.take_profit_levels = [(0.15, 0.4), (0.30, 0.4)]

    # ------------------------------------------------------------------
    # generate_signals
    # ------------------------------------------------------------------
    def generate_signals(self, df: pd.DataFrame) -> list[Signal]:
        signals: list[Signal] = []

        # ---- 指标列名 ----
        bb_upper = f"ind_bb_upper_{self.bb_period}"
        bb_middle = f"ind_bb_middle_{self.bb_period}"
        bb_lower = f"ind_bb_lower_{self.bb_period}"
        rsi_col = f"ind_rsi_{self.rsi_period}"
        macd_hist_col = "ind_macd_histogram"

        required_cols = [bb_middle, bb_lower, rsi_col, macd_hist_col, "close", "volume"]
        for col in required_cols:
            if col not in df.columns:
                return signals

        # ---- 成交量均线（策略内部计算） ----
        vol_ma = df["volume"].rolling(window=self.vol_period).mean()

        # ---- 持仓状态变量 ----
        entry_price: float | None = None       # 入场价
        highest_price: float = 0.0              # 持仓期间最高收盘价
        triggered_levels: set[int] = set()      # 已触发的阶梯止盈索引
        consecutive_hist_down: int = 0          # MACD 柱连续缩小计数

        for idx in range(len(df)):
            current_date = (
                df.index[idx] if isinstance(df.index[idx], date) else df.index[idx]
            )
            close = float(df.iloc[idx]["close"])
            volume = float(df.iloc[idx]["volume"])

            bb_mid = float(df.iloc[idx][bb_middle])
            bb_low = float(df.iloc[idx][bb_lower])
            rsi = float(df.iloc[idx][rsi_col])
            macd_hist = float(df.iloc[idx][macd_hist_col])

            # 跳过指标未就绪的行
            if pd.isna(bb_mid) or pd.isna(rsi) or pd.isna(macd_hist):
                continue

            vol_ma_val = vol_ma.iloc[idx]
            vol_confirm = (
                not pd.isna(vol_ma_val) and volume > vol_ma_val * self.vol_factor
            )

            in_position = entry_price is not None

            # ============================================================
            #  卖 出 逻 辑（先卖后买，释放现金）
            # ============================================================
            if in_position:
                # 更新持仓期最高价
                if close > highest_price:
                    highest_price = close

                should_sell_full = False
                sell_reason = ""

                gain = (close - entry_price) / entry_price

                # --- 1. 硬止损 ---
                if gain <= -self.stop_loss:
                    should_sell_full = True
                    sell_reason = f"止损({gain:.1%})"

                # --- 2. 移动止盈（从最高价回撤） ---
                elif (
                    highest_price > 0
                    and (close - highest_price) / highest_price <= -self.trailing_stop
                    and gain > 0
                ):
                    dd = (close - highest_price) / highest_price
                    should_sell_full = True
                    sell_reason = f"移动止盈回撤{dd:.1%}"

                # --- 3. 趋势破位（跌破 BB 下轨） ---
                elif close < bb_low:
                    should_sell_full = True
                    sell_reason = "跌破布林下轨"

                # --- 4. RSI 超买 ---
                elif rsi > self.rsi_sell:
                    should_sell_full = True
                    sell_reason = f"RSI超买({rsi:.0f})"

                # --- 5. MACD 动能衰竭（柱 < 0 且连续 2 日缩小） ---
                if not should_sell_full and macd_hist < 0:
                    if idx > 0:
                        prev_hist = float(df.iloc[idx - 1][macd_hist_col])
                        if not pd.isna(prev_hist) and macd_hist < prev_hist:
                            consecutive_hist_down += 1
                        else:
                            consecutive_hist_down = 1
                    else:
                        consecutive_hist_down = 1

                    if consecutive_hist_down >= 2:
                        should_sell_full = True
                        sell_reason = "MACD动能衰竭"
                else:
                    consecutive_hist_down = 0

                # --- 6. 阶梯止盈（部分卖出，不清仓） ---
                if not should_sell_full:
                    for level_idx, (threshold, sell_pct) in enumerate(
                        self.take_profit_levels
                    ):
                        if level_idx in triggered_levels:
                            continue
                        if gain >= threshold:
                            signals.append(
                                Signal(
                                    symbol="",
                                    date=current_date,
                                    action="SELL",
                                    strength=sell_pct,
                                    reason=f"阶梯止盈L{level_idx + 1} +{gain:.1%}",
                                )
                            )
                            triggered_levels.add(level_idx)

                # --- 执行全仓卖出 ---
                if should_sell_full:
                    signals.append(
                        Signal(
                            symbol="",
                            date=current_date,
                            action="SELL",
                            strength=1.0,
                            reason=sell_reason,
                        )
                    )
                    entry_price = None
                    highest_price = 0.0
                    triggered_levels.clear()
                    consecutive_hist_down = 0
                    continue  # 当天已清仓，跳过买入判断

            # ============================================================
            #  买 入 逻 辑（四维共振）
            # ============================================================
            if not in_position:
                # 条件 1: 多头趋势 — 收盘价在 BB 中轨之上
                trend_up = close > bb_mid

                # 条件 2: RSI 在买入区间（非超买，有上行空间）
                rsi_ok = self.rsi_buy_low <= rsi <= self.rsi_buy_high

                # 条件 3: 放量确认
                volume_ok = vol_confirm

                # 条件 4: MACD 柱状图转正且加速（柱 > 0 且 > 前一日）
                macd_ok = False
                if macd_hist > 0:
                    if idx >= 1:
                        prev_hist = float(df.iloc[idx - 1][macd_hist_col])
                        if not pd.isna(prev_hist) and (
                            prev_hist <= 0 or macd_hist > prev_hist
                        ):
                            # 由负转正 或 正在加速
                            macd_ok = True
                    else:
                        macd_ok = True

                if trend_up and rsi_ok and volume_ok and macd_ok:
                    signals.append(
                        Signal(
                            symbol="",
                            date=current_date,
                            action="BUY",
                            strength=1.0,
                            reason=f"BB回调买入 RSI{rsi:.0f}",
                        )
                    )
                    entry_price = close
                    highest_price = close
                    triggered_levels.clear()
                    consecutive_hist_down = 0

        return signals
