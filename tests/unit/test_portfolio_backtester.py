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


from autotrade.core.exit_manager import ExitManager


def _make_position(symbol="000001", entry_price=10.0, quantity=1000,
                   highest=10.5, entry_date=date(2024, 1, 10)):
    return PortfolioPosition(
        symbol=symbol, entry_date=entry_date,
        entry_price=entry_price, quantity=quantity,
        highest_close_since_entry=highest,
    )


class TestExitManager:
    def test_no_rules_triggered_when_safe(self):
        config = {
            "exit_rules": {
                "trailing_stop": {"enabled": True, "drawdown_pct": 0.08},
                "hard_stop": {"enabled": True, "loss_pct": 0.05},
                "time_stop": {"enabled": True, "max_holding_days": 20, "min_return_pct": 0.0},
                "signal_decay": {"enabled": True, "rank_threshold": 50},
            }
        }
        em = ExitManager(config)
        pos = _make_position(entry_price=10.0, highest=10.5)
        triggers = em.check(pos, 10.2, date(2024, 1, 13),
                            [("000001", 0.8, "strong")],
                            date(2024, 1, 12))
        assert triggers == []

    def test_hard_stop_triggers(self):
        config = {
            "exit_rules": {
                "trailing_stop": {"enabled": False, "drawdown_pct": 0.08},
                "hard_stop": {"enabled": True, "loss_pct": 0.05},
                "time_stop": {"enabled": False, "max_holding_days": 20, "min_return_pct": 0.0},
                "signal_decay": {"enabled": False, "rank_threshold": 50},
            }
        }
        em = ExitManager(config)
        pos = _make_position(entry_price=10.0, highest=10.0)
        triggers = em.check(pos, 9.4, date(2024, 1, 13),
                            [], date(2024, 1, 12))
        assert "hard_stop" in triggers

    def test_trailing_stop_triggers(self):
        config = {
            "exit_rules": {
                "trailing_stop": {"enabled": True, "drawdown_pct": 0.08},
                "hard_stop": {"enabled": False, "loss_pct": 0.05},
                "time_stop": {"enabled": False, "max_holding_days": 20, "min_return_pct": 0.0},
                "signal_decay": {"enabled": False, "rank_threshold": 50},
            }
        }
        em = ExitManager(config)
        pos = _make_position(entry_price=10.0, highest=12.0)
        triggers = em.check(pos, 10.5, date(2024, 1, 20),
                            [], date(2024, 1, 12))
        assert "trailing_stop" in triggers

    def test_trailing_stop_not_triggered_near_high(self):
        config = {
            "exit_rules": {
                "trailing_stop": {"enabled": True, "drawdown_pct": 0.08},
                "hard_stop": {"enabled": False, "loss_pct": 0.05},
                "time_stop": {"enabled": False, "max_holding_days": 20, "min_return_pct": 0.0},
                "signal_decay": {"enabled": False, "rank_threshold": 50},
            }
        }
        em = ExitManager(config)
        pos = _make_position(entry_price=10.0, highest=12.0)
        triggers = em.check(pos, 11.5, date(2024, 1, 20),
                            [], date(2024, 1, 12))
        assert "trailing_stop" not in triggers

    def test_time_stop_triggers(self):
        config = {
            "exit_rules": {
                "trailing_stop": {"enabled": False, "drawdown_pct": 0.08},
                "hard_stop": {"enabled": False, "loss_pct": 0.05},
                "time_stop": {"enabled": True, "max_holding_days": 20, "min_return_pct": 0.0},
                "signal_decay": {"enabled": False, "rank_threshold": 50},
            }
        }
        em = ExitManager(config)
        pos = _make_position(entry_price=10.0, highest=10.0,
                             entry_date=date(2024, 1, 2))
        triggers = em.check(pos, 10.0, date(2024, 1, 25),
                            [], date(2024, 1, 2))
        assert "time_stop" in triggers

    def test_time_stop_not_triggered_when_profitable(self):
        config = {
            "exit_rules": {
                "trailing_stop": {"enabled": False, "drawdown_pct": 0.08},
                "hard_stop": {"enabled": False, "loss_pct": 0.05},
                "time_stop": {"enabled": True, "max_holding_days": 20, "min_return_pct": 0.05},
                "signal_decay": {"enabled": False, "rank_threshold": 50},
            }
        }
        em = ExitManager(config)
        pos = _make_position(entry_price=10.0, highest=12.0,
                             entry_date=date(2024, 1, 2))
        triggers = em.check(pos, 12.0, date(2024, 1, 25),
                            [], date(2024, 1, 2))
        assert "time_stop" not in triggers

    def test_signal_decay_triggers(self):
        config = {
            "exit_rules": {
                "trailing_stop": {"enabled": False, "drawdown_pct": 0.08},
                "hard_stop": {"enabled": False, "loss_pct": 0.05},
                "time_stop": {"enabled": False, "max_holding_days": 20, "min_return_pct": 0.0},
                "signal_decay": {"enabled": True, "rank_threshold": 2},
            }
        }
        em = ExitManager(config)
        pos = _make_position(symbol="000001")
        candidates = [("A", 0.9, "strong"), ("B", 0.8, "strong"), ("000001", 0.5, "steady")]
        triggers = em.check(pos, 10.0, date(2024, 1, 15),
                            candidates, date(2024, 1, 12))
        assert "signal_decay" in triggers

    def test_signal_decay_not_triggered_when_in_top(self):
        config = {
            "exit_rules": {
                "trailing_stop": {"enabled": False, "drawdown_pct": 0.08},
                "hard_stop": {"enabled": False, "loss_pct": 0.05},
                "time_stop": {"enabled": False, "max_holding_days": 20, "min_return_pct": 0.0},
                "signal_decay": {"enabled": True, "rank_threshold": 6},
            }
        }
        em = ExitManager(config)
        pos = _make_position(symbol="000001")
        candidates = [("A", 0.9, "strong"), ("B", 0.8, "strong"), ("000001", 0.5, "steady")]
        triggers = em.check(pos, 10.0, date(2024, 1, 15),
                            candidates, date(2024, 1, 12))
        assert "signal_decay" not in triggers

    def test_multiple_rules_can_trigger(self):
        config = {
            "exit_rules": {
                "trailing_stop": {"enabled": True, "drawdown_pct": 0.08},
                "hard_stop": {"enabled": True, "loss_pct": 0.05},
                "time_stop": {"enabled": False, "max_holding_days": 20, "min_return_pct": 0.0},
                "signal_decay": {"enabled": False, "rank_threshold": 50},
            }
        }
        em = ExitManager(config)
        pos = _make_position(entry_price=10.0, highest=12.0)
        triggers = em.check(pos, 9.0, date(2024, 1, 20),
                            [], date(2024, 1, 12))
        assert "hard_stop" in triggers
        assert "trailing_stop" in triggers

    def test_disabled_rule_not_checked(self):
        config = {
            "exit_rules": {
                "trailing_stop": {"enabled": False, "drawdown_pct": 0.08},
                "hard_stop": {"enabled": False, "loss_pct": 0.05},
                "time_stop": {"enabled": False, "max_holding_days": 20, "min_return_pct": 0.0},
                "signal_decay": {"enabled": False, "rank_threshold": 50},
            }
        }
        em = ExitManager(config)
        pos = _make_position(entry_price=10.0, highest=12.0)
        triggers = em.check(pos, 5.0, date(2024, 2, 1),
                            [], date(2024, 1, 12))
        assert triggers == []
