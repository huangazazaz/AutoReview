"""Portfolio-level backtest engine — daily loop with screener-driven entries
and unified exit rules across multiple simultaneous positions."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

from autotrade.core.account import (
    Account, PendingBuy, PortfolioPosition, PortfolioTrade,
)
from autotrade.core.exit_manager import ExitManager
from autotrade.core.market_regime import MarketRegime

logger = logging.getLogger(__name__)


@dataclass
class PortfolioBacktestConfig:
    """Configuration for a portfolio backtest run."""
    start_date: date
    end_date: date
    initial_capital: float = 1_000_000.0
    cash_buffer: float = 0.05
    top_n_candidates: int = 50
    fill_price: str = "next_open"
    commission_rate: float = 0.0003
    stamp_duty_rate: float = 0.001
    slippage: float = 0.001
    min_commission: float = 5.0
    lot_size: int = 100
    allow_t_plus_1: bool = True
    exit_rules: dict = field(default_factory=dict)
    market_regime: dict = field(default_factory=dict)


@dataclass
class PortfolioBacktestResult:
    """Result of a portfolio backtest."""
    trades: list[PortfolioTrade] = field(default_factory=list)
    equity_curve: Optional[pd.Series] = None
    metrics: dict = field(default_factory=dict)


class PortfolioBacktester:
    """Portfolio-level backtest engine.

    Daily loop:
      Morning: execute pending buys, check exits, record equity
      Evening: detect regime, plan next-day buys from screener results
    """

    def __init__(self, config: PortfolioBacktestConfig):
        self.config = config
        self.exit_manager = ExitManager({
            "exit_rules": config.exit_rules,
        })
        self.regime = MarketRegime(**config.market_regime)

    def run(
        self,
        market_data: dict[str, pd.DataFrame],
        screener_results: dict[date, list[tuple[str, float, str]]],
    ) -> PortfolioBacktestResult:
        """Execute the portfolio backtest.

        Args:
            market_data: {symbol: DataFrame} with date index and OHLCV columns.
            screener_results: {date: [(symbol, score, tag), ...]} precomputed
                by the screener for all trading dates.

        Returns:
            PortfolioBacktestResult with trades, equity curve, and metrics.
        """
        # Collect all unique trading dates from market data
        all_dates: set[date] = set()
        for df in market_data.values():
            for idx_val in df.index:
                d = idx_val.date() if hasattr(idx_val, "date") else idx_val
                all_dates.add(d)
        trading_dates = sorted(d for d in all_dates
                               if self.config.start_date <= d <= self.config.end_date)

        if not trading_dates:
            return PortfolioBacktestResult(
                metrics={"error": "No trading dates in range"},
            )

        # Initialize account
        account = Account(
            initial_capital=self.config.initial_capital,
            cash=self.config.initial_capital,
        )

        pending_buys: list[PendingBuy] = []
        prev_date: Optional[date] = None

        for day_idx, today in enumerate(trading_dates):
            # --- Get open prices for today ---
            opens = self._get_day_prices(market_data, today, "open")

            # --- Morning: execute pending buys ---
            for buy in pending_buys:
                price = opens.get(buy.symbol)
                if price is None:
                    continue
                self._execute_buy(account, buy, price, today)

            pending_buys.clear()

            # --- Morning: check exits (unlocked positions) ---
            prev_screener = screener_results.get(prev_date, []) if prev_date else []
            for symbol in list(account.positions.keys()):
                pos = account.positions[symbol]
                # T+1 lock check
                if (self.config.allow_t_plus_1 and pos.locked_until
                        and today <= pos.locked_until):
                    continue

                price = opens.get(symbol)
                if price is None:
                    continue

                # Update highest close
                if price > pos.highest_close_since_entry:
                    pos.highest_close_since_entry = price

                triggers = self.exit_manager.check(
                    pos, price, today, prev_screener, prev_date or today,
                )
                if triggers:
                    self._execute_sell(account, pos, price, today, triggers)

            # --- Morning: record equity ---
            account.record_equity(today, opens)

            # --- Evening: detect regime ---
            today_candidates = screener_results.get(today, [])
            max_positions = self.regime.detect(today_candidates)

            # --- Evening: plan buys for next day ---
            if max_positions > 0:
                slots = max_positions - len(account.positions)
                if slots > 0:
                    held = set(account.positions.keys())
                    available = [
                        (s, sc, t) for s, sc, t in today_candidates
                        if s not in held
                    ][:self.config.top_n_candidates]

                    picks = available[:slots]
                    if picks:
                        pending_buys = self._plan_buys(
                            picks, account.cash, opens,
                        )

            prev_date = today

        # Force-close any remaining positions at last available close
        if account.positions:
            closes = self._get_day_prices(market_data, trading_dates[-1], "close")
            for symbol, pos in list(account.positions.items()):
                price = closes.get(symbol)
                if price is None:
                    continue
                self._execute_sell(account, pos, price, trading_dates[-1],
                                   ["end_of_period"])

        # Build result
        equity_series = pd.Series(
            [eq for _, eq in account.equity_curve],
            index=[d for d, _ in account.equity_curve],
        )
        metrics = self._compute_metrics(account, equity_series)

        return PortfolioBacktestResult(
            trades=account.trades,
            equity_curve=equity_series,
            metrics=metrics,
        )

    # ---- Internal helpers ----

    def _get_day_prices(
        self, market_data: dict[str, pd.DataFrame], d: date, col: str,
    ) -> dict[str, float]:
        """Get a price column for all symbols on a given date."""
        prices: dict[str, float] = {}
        for sym, df in market_data.items():
            try:
                val = df.loc[d, col]
                if isinstance(val, pd.Series):
                    val = val.iloc[0]
                if not pd.isna(val) and float(val) > 0:
                    prices[sym] = float(val)
            except (KeyError, TypeError):
                pass
        return prices

    def _execute_buy(
        self, account: Account, buy: PendingBuy,
        price: float, today: date,
    ):
        """Execute a pending buy at today's open."""
        fill_price = price * (1 + self.config.slippage)
        quantity = buy.quantity
        if quantity <= 0:
            return

        cost = quantity * fill_price
        commission = max(cost * self.config.commission_rate,
                         self.config.min_commission)
        total_cost = cost + commission

        if total_cost > account.cash:
            # Adjust quantity downward to fit available cash
            affordable_qty = int(
                (account.cash - self.config.min_commission)
                / (fill_price * (1 + self.config.commission_rate))
            )
            quantity = (affordable_qty // self.config.lot_size) * self.config.lot_size
            if quantity <= 0:
                return
            cost = quantity * fill_price
            commission = max(cost * self.config.commission_rate,
                             self.config.min_commission)
            total_cost = cost + commission

        account.cash -= total_cost

        locked_until = None
        if self.config.allow_t_plus_1:
            locked_until = today  # can't sell until next trading day

        position = PortfolioPosition(
            symbol=buy.symbol,
            entry_date=today,
            entry_price=fill_price,
            quantity=quantity,
            highest_close_since_entry=fill_price,
            locked_until=locked_until,
        )
        account.positions[buy.symbol] = position

    def _execute_sell(
        self, account: Account, position: PortfolioPosition,
        price: float, today: date, triggers: list[str],
    ):
        """Execute a sell for a position."""
        fill_price = price * (1 - self.config.slippage)
        quantity = position.quantity
        proceeds = quantity * fill_price
        commission = max(proceeds * self.config.commission_rate,
                         self.config.min_commission)
        stamp_duty = proceeds * self.config.stamp_duty_rate

        account.cash += proceeds - commission - stamp_duty

        pnl = proceeds - (position.entry_price * quantity) - commission - stamp_duty
        pnl_pct = (fill_price - position.entry_price) / position.entry_price

        trade = PortfolioTrade(
            symbol=position.symbol,
            buy_date=position.entry_date,
            sell_date=today,
            buy_price=position.entry_price,
            sell_price=fill_price,
            quantity=quantity,
            pnl=round(pnl, 2),
            pnl_pct=round(pnl_pct, 4),
        )
        account.trades.append(trade)
        del account.positions[position.symbol]

    def _plan_buys(
        self,
        picks: list[tuple[str, float, str]],
        cash: float,
        opens: dict[str, float],
    ) -> list[PendingBuy]:
        """Allocate cash by signal strength and create pending buys."""
        total_score = sum(sc for _, sc, _ in picks)
        if total_score <= 0:
            return []

        available = cash * (1 - self.config.cash_buffer)
        pending: list[PendingBuy] = []

        for symbol, score, _ in picks:
            weight = score / total_score
            alloc = available * weight
            price = opens.get(symbol)
            if price is None or price <= 0:
                continue
            fill_price = price * (1 + self.config.slippage)
            qty = int(alloc / (fill_price * (1 + self.config.commission_rate))
                      / self.config.lot_size) * self.config.lot_size
            if qty > 0:
                pending.append(PendingBuy(symbol=symbol, quantity=qty))

        return pending

    def _compute_metrics(
        self, account: Account, equity_curve: pd.Series,
    ) -> dict:
        """Compute summary metrics."""
        if equity_curve.empty or len(equity_curve) < 2:
            return {
                "total_trades": len(account.trades),
                "total_return_pct": 0.0,
                "win_rate": 0.0,
                "max_drawdown_pct": 0.0,
                "sharpe_ratio": 0.0,
            }

        initial = equity_curve.iloc[0]
        final = equity_curve.iloc[-1]
        total_return_pct = (final - initial) / initial * 100

        # Win rate
        wins = sum(1 for t in account.trades if t.pnl > 0)
        total_closed = len(account.trades)
        win_rate = (wins / total_closed * 100) if total_closed > 0 else 0.0

        # Max drawdown
        peak = np.maximum.accumulate(equity_curve.values)
        drawdown = (peak - equity_curve.values) / peak * 100
        max_drawdown_pct = -float(np.max(drawdown)) if len(drawdown) > 0 else 0.0

        # Sharpe ratio (annualized, risk-free=0)
        returns = equity_curve.pct_change().dropna()
        if len(returns) > 1 and returns.std() > 0:
            sharpe = float(returns.mean() / returns.std() * np.sqrt(252))
        else:
            sharpe = 0.0

        return {
            "initial_capital": self.config.initial_capital,
            "final_equity": round(final, 2),
            "total_trades": len(account.trades),
            "total_return_pct": round(total_return_pct, 2),
            "win_rate": round(win_rate, 2),
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "sharpe_ratio": round(sharpe, 4),
        }
