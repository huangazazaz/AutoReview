"""Tests for portfolio backtest components."""
from datetime import date

from autotrade.core.account import Account, PortfolioPosition, PortfolioTrade


class TestPortfolioPosition:
    def test_days_held(self):
        pos = PortfolioPosition(
            symbol="000001", entry_date=date(2024, 1, 10),
            entry_price=10.0, quantity=1000,
            highest_close_since_entry=10.5,
        )
        assert pos.days_held(date(2024, 1, 20)) == 10

    def test_market_value(self):
        pos = PortfolioPosition(
            symbol="000001", entry_date=date(2024, 1, 10),
            entry_price=10.0, quantity=1000,
            highest_close_since_entry=10.0,
        )
        assert pos.market_value(12.0) == 12000.0

    def test_pnl_pct_positive(self):
        pos = PortfolioPosition(
            symbol="000001", entry_date=date(2024, 1, 10),
            entry_price=10.0, quantity=1000,
            highest_close_since_entry=12.0,
        )
        assert pos.pnl_pct(11.0) == 0.1

    def test_pnl_pct_negative(self):
        pos = PortfolioPosition(
            symbol="000001", entry_date=date(2024, 1, 10),
            entry_price=10.0, quantity=1000,
            highest_close_since_entry=10.0,
        )
        assert pos.pnl_pct(9.0) == -0.1


class TestAccount:
    def test_total_equity_all_cash(self):
        acct = Account(initial_capital=1000000.0, cash=1000000.0)
        assert acct.total_equity({}) == 1000000.0

    def test_total_equity_with_positions(self):
        acct = Account(initial_capital=1000000.0, cash=500000.0)
        pos = PortfolioPosition(
            symbol="000001", entry_date=date(2024, 1, 10),
            entry_price=10.0, quantity=10000,
            highest_close_since_entry=10.0,
        )
        acct.positions["000001"] = pos
        assert acct.total_equity({"000001": 12.0}) == 500000.0 + 120000.0

    def test_record_equity_appends(self):
        acct = Account(initial_capital=1000000.0, cash=1000000.0)
        acct.record_equity(date(2024, 1, 10), {})
        assert len(acct.equity_curve) == 1
        assert acct.equity_curve[0] == (date(2024, 1, 10), 1000000.0)

    def test_record_equity_with_position(self):
        acct = Account(initial_capital=1000000.0, cash=500000.0)
        pos = PortfolioPosition(
            symbol="000001", entry_date=date(2024, 1, 10),
            entry_price=10.0, quantity=10000,
            highest_close_since_entry=10.0,
        )
        acct.positions["000001"] = pos
        acct.record_equity(date(2024, 1, 10), {"000001": 12.0})
        assert acct.equity_curve[0][1] == 620000.0
