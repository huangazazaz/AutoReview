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

            # --- Phase 1: Process exits (SELL + BUY_TO_COVER) ---
            for sig in daily_signals:
                if sig.action == "SELL":
                    if not self._can_sell_today(can_sell_after, today):
                        continue
                    fill_price = self._get_fill_price(sig, bar, bars_sorted, i, is_buy=False)
                    if fill_price is None:
                        continue
                    cash, trade = self._execute_sell_trade(position, cash, fill_price,
                                                           sig.strength, bar, sig)
                    if trade:
                        trades.append(trade)
                elif sig.action == "BUY_TO_COVER":
                    fill_price = self._get_fill_price(sig, bar, bars_sorted, i, is_buy=False)
                    if fill_price is None:
                        continue
                    cash, trade = self._execute_cover_trade(position, cash, fill_price,
                                                            sig.strength, bar)
                    if trade:
                        trades.append(trade)

            # --- Phase 2: Process entries (BUY + SELL_SHORT) ---
            for sig in daily_signals:
                if sig.action == "BUY":
                    fill_price = self._get_fill_price(sig, bar, bars_sorted, i, is_buy=True)
                    if fill_price is None:
                        continue
                    cash, trade = self._execute_buy_trade(position, cash, fill_price,
                                                          sig.strength, bar, bars_sorted, i, sig)
                    if trade:
                        trades.append(trade)
                        if self.config.allow_t_plus_1 and i + 1 < len(bars_sorted):
                            can_sell_after = bars_sorted[i + 1].date
                elif sig.action == "SELL_SHORT" and self.config.allow_short:
                    fill_price = self._get_fill_price(sig, bar, bars_sorted, i, is_buy=False)
                    if fill_price is None:
                        continue
                    cash, trade = self._execute_short_trade(position, cash, fill_price,
                                                            sig.strength, bar)
                    if trade:
                        trades.append(trade)

            # 更新市值的每日估值
            long_market_value = position.long_qty * bar.close
            short_market_value = position.short_qty * bar.close
            total_equity = cash + long_market_value - short_market_value
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

    def _can_sell_today(self, can_sell_after: Optional[date], today: date) -> bool:
        """Check if T+1 restriction allows selling today."""
        if not self.config.allow_t_plus_1:
            return True
        if can_sell_after is None:
            return True
        return today >= can_sell_after

    def _execute_sell_trade(self, position: Position, cash: float,
                            fill_price: float, strength: float,
                            bar: Bar, sig: Signal) -> tuple[float, Trade | None]:
        """Execute a SELL order. Returns (updated_cash, trade_or_None)."""
        actual_price = fill_price * (1 - self.config.slippage)
        quantity = self._compute_sell_quantity(position, strength)
        if quantity <= 0:
            return cash, None

        amount = actual_price * quantity
        commission = max(amount * self.config.commission_rate,
                         self.config.min_commission)
        stamp_duty = amount * self.config.stamp_duty_rate

        trade = Trade(
            symbol=bar.symbol, date=bar.date, action="SELL",
            price=round(actual_price, 2),
            quantity=quantity,
            commission=round(commission, 2),
            stamp_duty=round(stamp_duty, 2),
        )
        cash += amount - commission - stamp_duty
        position.long_qty -= quantity
        if position.long_qty <= 0:
            position.long_avg_cost = 0.0

        return cash, trade

    def _execute_buy_trade(self, position: Position, cash: float,
                           fill_price: float, strength: float,
                           bar: Bar, bars_sorted: list[Bar], idx: int,
                           sig: Signal) -> tuple[float, Trade | None]:
        """Execute a BUY order. Returns (updated_cash, trade_or_None)."""
        actual_price = fill_price * (1 + self.config.slippage)
        quantity = self._compute_buy_quantity(cash, actual_price, strength)
        if quantity <= 0:
            return cash, None

        amount = actual_price * quantity
        commission = max(amount * self.config.commission_rate,
                         self.config.min_commission)

        trade = Trade(
            symbol=bar.symbol, date=bar.date, action="BUY",
            price=round(actual_price, 2),
            quantity=quantity,
            commission=round(commission, 2),
        )
        cash -= amount + commission

        # 更新持仓均价
        total_cost = position.long_avg_cost * position.long_qty + amount
        position.long_qty += quantity
        position.long_avg_cost = total_cost / position.long_qty if position.long_qty > 0 else 0

        return cash, trade

    def _execute_short_trade(self, position: Position, cash: float,
                             fill_price: float, strength: float,
                             bar: Bar) -> tuple[float, Trade | None]:
        """Execute a SELL_SHORT order. Returns (updated_cash, trade_or_None)."""
        actual_price = fill_price * (1 - self.config.slippage)
        quantity = self._compute_buy_quantity(cash, actual_price, strength)
        if quantity <= 0:
            return cash, None

        # Margin check: required = new_short_value * margin_ratio
        new_short_value = actual_price * quantity
        required_margin = new_short_value * self.config.short_margin_ratio
        existing_margin = (position.short_qty * position.short_avg_cost *
                          self.config.short_margin_ratio) if position.short_qty > 0 else 0
        available_margin = cash - existing_margin
        if available_margin < required_margin:
            return cash, None  # Insufficient margin

        amount = new_short_value
        commission = max(amount * self.config.commission_rate,
                         self.config.min_commission)

        trade = Trade(
            symbol=bar.symbol, date=bar.date, action="SELL_SHORT",
            price=round(actual_price, 2),
            quantity=quantity,
            commission=round(commission, 2),
        )
        # Short sale proceeds increase cash (margin is locked conceptually)
        cash += amount - commission

        # Update short position
        total_cost = position.short_avg_cost * position.short_qty + amount
        position.short_qty += quantity
        position.short_avg_cost = total_cost / position.short_qty if position.short_qty > 0 else 0

        return cash, trade

    def _execute_cover_trade(self, position: Position, cash: float,
                             fill_price: float, strength: float,
                             bar: Bar) -> tuple[float, Trade | None]:
        """Execute a BUY_TO_COVER order. Returns (updated_cash, trade_or_None)."""
        if position.short_qty <= 0:
            return cash, None

        actual_price = fill_price * (1 + self.config.slippage)

        # Compute cover quantity
        if self.config.position_sizing == "strength":
            quantity = int(position.short_qty * strength)
        else:
            quantity = position.short_qty
        quantity = (quantity // self.config.lot_size) * self.config.lot_size
        if quantity <= 0:
            return cash, None

        amount = actual_price * quantity
        commission = max(amount * self.config.commission_rate,
                         self.config.min_commission)

        trade = Trade(
            symbol=bar.symbol, date=bar.date, action="BUY_TO_COVER",
            price=round(actual_price, 2),
            quantity=quantity,
            commission=round(commission, 2),
        )
        cash -= amount + commission

        position.short_qty -= quantity
        if position.short_qty <= 0:
            position.short_avg_cost = 0.0

        return cash, trade

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
        if position.long_qty <= 0:
            return 0
        if self.config.position_sizing == "strength":
            quantity = int(position.long_qty * strength)
        else:
            quantity = position.long_qty
        # 向下取整到 lot_size 的倍数
        quantity = (quantity // self.config.lot_size) * self.config.lot_size
        return max(0, quantity)

    @staticmethod
    def _split_cycles(trades: list) -> list[tuple[list, list]]:
        """将交易列表按持仓周期拆分。每轮从空仓到再次空仓为一个周期。

        处理多空双向：分别跟踪多头净持仓和空头净持仓。

        Returns:
            [(entries, exits), ...]
            最后一个周期可能只有开仓交易（未平仓）。
        """
        cycles: list[tuple[list, list]] = []
        current_entries: list = []
        current_exits: list = []
        long_position = 0
        short_position = 0

        for t in trades:
            if t.action == "BUY":
                current_entries.append(t)
                long_position += t.quantity
            elif t.action == "SELL":
                current_exits.append(t)
                long_position -= t.quantity
            elif t.action == "SELL_SHORT":
                current_entries.append(t)
                short_position += t.quantity
            elif t.action == "BUY_TO_COVER":
                current_exits.append(t)
                short_position -= t.quantity

            # Cycle ends when both long and short are fully closed
            if long_position == 0 and short_position == 0 and current_entries:
                cycles.append((current_entries, current_exits))
                current_entries = []
                current_exits = []

        # Unclosed cycle
        if current_entries:
            cycles.append((current_entries, current_exits))

        return cycles


    def _compute_metrics(self, trades: list[Trade],
                         equity_series: list[float],
                         dates: list[date]) -> dict:
        """计算回测汇总指标（向量化）。"""
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

        # 胜率：按持仓周期计算
        wins = 0
        cycles = self._split_cycles(trades)
        for buys, sells in cycles:
            if not sells:
                continue  # 未平仓周期不参与胜率
            total_buy_amount = sum(b.price * b.quantity for b in buys)
            total_buy_qty = sum(b.quantity for b in buys)
            total_sell_amount = sum(s.price * s.quantity for s in sells)
            total_sell_qty = sum(s.quantity for s in sells)
            if total_buy_qty > 0 and total_sell_qty > 0:
                avg_buy = total_buy_amount / total_buy_qty
                avg_sell = total_sell_amount / total_sell_qty
                if avg_sell > avg_buy:
                    wins += 1
        total_cycles = len(cycles) - (1 if cycles and not cycles[-1][1] else 0)
        win_rate = (wins / total_cycles * 100) if total_cycles > 0 else 0.0

        # 最大回撤（向量化）
        equity_arr = np.array(equity_series)
        peak = np.maximum.accumulate(equity_arr)
        drawdown_pct = (equity_arr - peak) / peak
        max_drawdown_pct = float(np.min(drawdown_pct) * 100)

        # 夏普比率（向量化）
        returns = np.diff(equity_arr) / equity_arr[:-1]
        if len(returns) > 1:
            mean_ret = np.mean(returns)
            std_ret = np.std(returns, ddof=1)
            sharpe = float(mean_ret / std_ret * np.sqrt(252)) if std_ret > 0 else 0.0
        else:
            sharpe = 0.0

        buy_trades = sum(1 for t in trades if t.action == "BUY")
        sell_trades = sum(1 for t in trades if t.action in ("SELL", "BUY_TO_COVER"))

        return {
            "initial_capital": initial_capital,
            "final_equity": round(final_equity, 2),
            "total_trades": len(trades),
            "buy_trades": buy_trades,
            "sell_trades": sell_trades,
            "total_return_pct": round(total_return_pct, 2),
            "win_rate": round(win_rate, 2),
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "sharpe_ratio": round(sharpe, 4),
        }
