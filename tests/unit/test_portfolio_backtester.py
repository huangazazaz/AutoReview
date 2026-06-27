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


from autotrade.core.market_regime import MarketRegime


class TestMarketRegime:
    def test_empty_candidates_returns_zero(self):
        mr = MarketRegime()
        assert mr.detect([]) == 0

    def test_bullish_returns_3(self):
        mr = MarketRegime(bullish_threshold=0.6)
        candidates = [("A", 0.9, "strong"), ("B", 0.8, "strong"), ("C", 0.7, "strong")]
        assert mr.detect(candidates) == 3

    def test_neutral_returns_2(self):
        mr = MarketRegime(neutral_threshold=0.4, bullish_threshold=0.6)
        candidates = [("A", 0.5, "steady"), ("B", 0.45, "steady")]
        assert mr.detect(candidates) == 2

    def test_bearish_returns_1(self):
        mr = MarketRegime(neutral_threshold=0.4)
        candidates = [("A", 0.35, "weak"), ("B", 0.3, "weak")]
        assert mr.detect(candidates) == 1

    def test_scores_below_threshold_excluded(self):
        mr = MarketRegime(score_threshold=0.3, neutral_threshold=0.4, bullish_threshold=0.6)
        # Only one candidate above score_threshold (0.3), avg=0.5 → neutral → 2
        candidates = [("A", 0.5, "steady"), ("B", 0.2, "weak"), ("C", 0.1, "weak")]
        assert mr.detect(candidates) == 2

    def test_all_below_threshold_returns_1(self):
        mr = MarketRegime(score_threshold=0.3)
        candidates = [("A", 0.2, "weak"), ("B", 0.1, "weak")]
        assert mr.detect(candidates) == 1
