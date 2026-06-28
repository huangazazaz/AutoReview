"""Portfolio account models: Position, Trade, Account, PendingBuy."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class PortfolioPosition:
    """A single holding in the portfolio."""
    symbol: str
    entry_date: date
    entry_price: float
    quantity: int
    highest_close_since_entry: float
    locked_until: Optional[date] = None  # T+1: cannot sell before this date
    entry_trigger: str = ""  # "strategy_buy" | "screener" — how this position was entered

    def days_held(self, current_date: date) -> int:
        return (current_date - self.entry_date).days

    def market_value(self, current_price: float) -> float:
        return self.quantity * current_price

    def pnl_pct(self, current_price: float) -> float:
        return (current_price - self.entry_price) / self.entry_price


@dataclass
class PortfolioTrade:
    """A completed buy-sell round trip."""
    symbol: str
    buy_date: date
    sell_date: date
    buy_price: float
    sell_price: float
    quantity: int
    pnl: float
    pnl_pct: float
    trigger: str = ""  # "strategy_buy" | "strategy_sell" | "trailing_stop" | ...


@dataclass
class PendingBuy:
    """A buy order planned for the next trading day."""
    symbol: str
    quantity: int
    trigger: str = ""  # "strategy_buy" | "screener"


@dataclass
class Account:
    """Portfolio account tracking cash, positions, equity history, and trades."""
    initial_capital: float
    cash: float
    positions: dict[str, PortfolioPosition] = field(default_factory=dict)
    equity_curve: list[tuple[date, float]] = field(default_factory=list)
    trades: list[PortfolioTrade] = field(default_factory=list)

    def total_equity(self, prices: dict[str, float]) -> float:
        """Cash plus mark-to-market value of all positions."""
        position_value = sum(
            pos.market_value(prices[sym])
            for sym, pos in self.positions.items()
            if sym in prices
        )
        return self.cash + position_value

    def record_equity(self, d: date, prices: dict[str, float]):
        """Snapshot total equity for date d."""
        self.equity_curve.append((d, self.total_equity(prices)))
