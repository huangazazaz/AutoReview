"""Unified exit rule engine — trailing stop, hard stop, time stop, signal decay."""
from __future__ import annotations

from datetime import date

from autotrade.core.account import PortfolioPosition


class ExitManager:
    """Check exit rules against a position and current market state.

    Four exit gates, each configurable and independently enabled:
    1. trailing_stop: sell when price drops drawdown_pct from position high
    2. hard_stop: sell when loss exceeds loss_pct from entry
    3. time_stop: sell when held too long without sufficient return
    4. signal_decay: sell when stock falls out of screener top-K
    """

    def __init__(self, config: dict):
        rules = config.get("exit_rules", {})
        self.trailing_stop = rules.get("trailing_stop", {})
        self.hard_stop = rules.get("hard_stop", {})
        self.time_stop = rules.get("time_stop", {})
        self.signal_decay = rules.get("signal_decay", {})

    def check(
        self,
        position: PortfolioPosition,
        current_price: float,
        current_date: date,
        screener_candidates: list[tuple[str, float, str]],
        screener_date: date,
    ) -> list[str]:
        """Check all enabled exit rules. Returns list of triggered rule names."""
        triggers: list[str] = []

        # 1. Trailing stop: drawdown from highest close since entry
        if self.trailing_stop.get("enabled", True):
            drawdown_pct = self.trailing_stop["drawdown_pct"]
            if position.highest_close_since_entry > 0:
                drawdown = (
                    (position.highest_close_since_entry - current_price)
                    / position.highest_close_since_entry
                )
                if drawdown >= drawdown_pct:
                    triggers.append("trailing_stop")

        # 2. Hard stop: absolute loss from entry
        if self.hard_stop.get("enabled", True):
            loss_pct = self.hard_stop["loss_pct"]
            loss = (current_price - position.entry_price) / position.entry_price
            if loss <= -loss_pct:
                triggers.append("hard_stop")

        # 3. Time stop: held too long with insufficient return
        if self.time_stop.get("enabled", True):
            max_days = self.time_stop["max_holding_days"]
            min_return = self.time_stop["min_return_pct"]
            days = position.days_held(current_date)
            pnl = position.pnl_pct(current_price)
            if days >= max_days and pnl <= min_return:
                triggers.append("time_stop")

        # 4. Signal decay: stock no longer in screener top-K
        if self.signal_decay.get("enabled", True):
            rank_threshold = self.signal_decay["rank_threshold"]
            top_symbols = {s for s, _, _ in screener_candidates[:rank_threshold]}
            if position.symbol not in top_symbols:
                triggers.append("signal_decay")

        return triggers
