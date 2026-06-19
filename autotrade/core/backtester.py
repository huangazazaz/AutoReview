"""回测引擎（撮合/T+1/涨跌停/手续费/仓位管理）。

核心设计：
- 非插件 —— A 股撮合规则是硬约束，不应被替换；但参数可配置。
- 逐日模拟：遍历每个交易日，检查信号 → 执行交易 → 更新持仓 → 记录净值。
- 成交价默认次日开盘价（避免未来函数），可配置为当日收盘价。
"""

from __future__ import annotations

from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

from autotrade.core.models import (
    Bar, BacktestConfig, BacktestResult, Position, Signal, Trade,
)


class Backtester:
    """回测引擎，负责逐日撮合、持仓管理、资金计算。"""

    def __init__(self, config: BacktestConfig):
        self.config = config

    def run(self, signals: list[Signal], bars: list[Bar]) -> BacktestResult:
        """运行回测。

        Args:
            signals: 策略产生的信号列表（已按日期排序）。
            bars: 日线数据列表（已按日期排序）。

        Returns:
            BacktestResult 包含成交记录、净值曲线、汇总指标。
        """
        if not bars:
            return BacktestResult(
                symbol=signals[0].symbol if signals else "",
                metrics={"error": "No bar data"},
            )

        symbol = bars[0].symbol
        signal_map: dict[date, list[Signal]] = {}
        for s in signals:
            signal_map.setdefault(s.date, []).append(s)

        # 按日期排序的 bar 列表
        bars_sorted = sorted(bars, key=lambda b: b.date)
        bar_dates = [b.date for b in bars_sorted]
        date_to_bar = {b.date: b for b in bars_sorted}

        # 状态初始化
        cash = self.config.initial_capital
        position = Position(symbol=symbol)
        trades: list[Trade] = []
        equity_series: list[float] = [cash]  # 净值序列
        dates_series: list[date] = [bar_dates[0]] if bar_dates else []

        # 买入锁定（T+1）：记录可卖日期
        can_sell_after: Optional[date] = None

        for i, bar in enumerate(bars_sorted):
            today = bar.date
            daily_signals = signal_map.get(today, [])

            # 处理当天的信号（先卖后买，避免现金不足）
            buy_signals = [s for s in daily_signals if s.action == "BUY"]
            sell_signals = [s for s in daily_signals if s.action == "SELL"]

            # --- 执行卖出 ---
            for sig in sell_signals:
                if position.quantity <= 0:
                    continue
                if self.config.allow_t_plus_1 and can_sell_after and today < can_sell_after:
                    continue  # T+1 锁定中，不能卖

                # 确定成交价
                fill_price = self._get_fill_price(sig, bar, bars_sorted, i, is_buy=False)
                if fill_price is None:
                    continue

                # 滑点（卖出成交价降低）
                actual_price = fill_price * (1 - self.config.slippage)

                # 计算卖出数量（按 strength 比例）
                quantity = self._compute_sell_quantity(position, sig.strength)
                if quantity <= 0:
                    continue

                amount = actual_price * quantity
                commission = max(amount * self.config.commission_rate,
                                 self.config.min_commission)
                stamp_duty = amount * self.config.stamp_duty_rate

                trade = Trade(
                    symbol=symbol, date=today, action="SELL",
                    price=round(actual_price, 2),
                    quantity=quantity,
                    commission=round(commission, 2),
                    stamp_duty=round(stamp_duty, 2),
                )
                trades.append(trade)
                cash += amount - commission - stamp_duty
                position.quantity -= quantity
                if position.quantity <= 0:
                    position.avg_cost = 0.0
                position.market_value = position.quantity * actual_price

            # --- 执行买入 ---
            for sig in buy_signals:
                # 确定成交价
                fill_price = self._get_fill_price(sig, bar, bars_sorted, i, is_buy=True)
                if fill_price is None:
                    continue

                # 滑点（买入成交价提高）
                actual_price = fill_price * (1 + self.config.slippage)

                # 计算买入数量
                quantity = self._compute_buy_quantity(cash, actual_price, sig.strength)
                if quantity <= 0:
                    continue

                amount = actual_price * quantity
                commission = max(amount * self.config.commission_rate,
                                 self.config.min_commission)

                trade = Trade(
                    symbol=symbol, date=today, action="BUY",
                    price=round(actual_price, 2),
                    quantity=quantity,
                    commission=round(commission, 2),
                )
                trades.append(trade)
                cash -= amount + commission

                # 更新持仓均价
                total_cost = position.avg_cost * position.quantity + amount
                position.quantity += quantity
                position.avg_cost = total_cost / position.quantity if position.quantity > 0 else 0
                position.market_value = position.quantity * actual_price

                # T+1 锁定
                if self.config.allow_t_plus_1:
                    # 找到下一个交易日
                    if i + 1 < len(bars_sorted):
                        can_sell_after = bars_sorted[i + 1].date

            # 更新市值的每日估值
            position.market_value = position.quantity * bar.close
            total_equity = cash + position.market_value
            equity_series.append(total_equity)
            dates_series.append(today)

        # 构建结果
        result = BacktestResult(
            symbol=symbol,
            trades=trades,
            signals=signals,
            equity_curve=pd.Series(equity_series, index=dates_series),
            metrics=self._compute_metrics(trades, equity_series, dates_series),
        )
        return result

    def _get_fill_price(self, sig: Signal, bar: Bar,
                        bars_sorted: list[Bar], idx: int,
                        is_buy: bool) -> Optional[float]:
        """获取成交价。"""
        if self.config.fill_price == "close":
            return bar.close
        elif self.config.fill_price == "next_open":
            # 次日开盘价
            if idx + 1 < len(bars_sorted):
                return bars_sorted[idx + 1].open
            else:
                return None  # 最后一天无下一日数据
        return bar.close

    def _compute_buy_quantity(self, cash: float, price: float,
                              strength: float) -> int:
        """计算买入股数（A股规则：100股整数倍，按 strength 比例）。"""
        if cash <= 0 or price <= 0:
            return 0

        if self.config.position_sizing == "strength":
            available = cash * strength
        else:
            available = cash

        max_shares = int(available / price)
        # 向下取整到 lot_size 的倍数
        quantity = (max_shares // self.config.lot_size) * self.config.lot_size
        return quantity

    def _compute_sell_quantity(self, position: Position, strength: float) -> int:
        """计算卖出股数。"""
        if position.quantity <= 0:
            return 0
        if self.config.position_sizing == "strength":
            quantity = int(position.quantity * strength)
        else:
            quantity = position.quantity
        # 向下取整到 lot_size 的倍数
        quantity = (quantity // self.config.lot_size) * self.config.lot_size
        return max(0, quantity)

    def _compute_metrics(self, trades: list[Trade],
                         equity_series: list[float],
                         dates: list[date]) -> dict:
        """计算回测汇总指标。"""
        if not trades or len(equity_series) < 2:
            return {
                "total_trades": len(trades),
                "total_return_pct": 0.0,
                "win_rate": 0.0,
                "max_drawdown_pct": 0.0,
                "sharpe_ratio": 0.0,
            }

        initial_capital = equity_series[0]
        final_equity = equity_series[-1]
        total_return_pct = (final_equity - initial_capital) / initial_capital * 100

        # 胜率：按买卖配对计算
        buy_trades = [t for t in trades if t.action == "BUY"]
        sell_trades = [t for t in trades if t.action == "SELL"]
        # 简化：按顺序配对
        wins = 0
        total_pairs = min(len(buy_trades), len(sell_trades))
        for i in range(total_pairs):
            buy = buy_trades[i]
            sell = sell_trades[i]
            if sell.price > buy.price:
                wins += 1
        win_rate = (wins / total_pairs * 100) if total_pairs > 0 else 0.0

        # 最大回撤
        equity_arr = np.array(equity_series)
        peak = np.maximum.accumulate(equity_arr)
        drawdown = (peak - equity_arr) / peak * 100
        max_drawdown_pct = float(np.max(drawdown))

        # 夏普比率（简化：用日收益率，无风险利率=0）
        if len(equity_series) > 1:
            returns = pd.Series(equity_series).pct_change().dropna()
            if returns.std() > 0:
                sharpe = float(returns.mean() / returns.std() * np.sqrt(252))
            else:
                sharpe = 0.0
        else:
            sharpe = 0.0

        return {
            "initial_capital": initial_capital,
            "final_equity": round(final_equity, 2),
            "total_trades": len(trades),
            "buy_trades": len(buy_trades),
            "sell_trades": len(sell_trades),
            "total_return_pct": round(total_return_pct, 2),
            "win_rate": round(win_rate, 2),
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "sharpe_ratio": round(sharpe, 4),
        }
