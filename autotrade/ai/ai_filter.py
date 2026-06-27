"""AI Filter — pipes screener results through LLM analysis, keeps only Buy-rated."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

import pandas as pd

from autotrade.ai.llm_cache import LLMCache
from autotrade.ai.trading_agents_wrapper import TradingAgentsWrapper

logger = logging.getLogger(__name__)


class AIFilter:
    """Secondary filter: run AI analysis on screener candidates, keep Buys.

    The filter receives the screener's output ({date: [(symbol, score, tag)]})
    and for each day, analyzes the top N candidates via TradingAgents.
    Only stocks rated "Buy" or "Overweight" are passed through to the backtester.
    """

    def __init__(
        self,
        wrapper: TradingAgentsWrapper,
        cache: LLMCache,
        config: dict[str, Any],
    ):
        self.wrapper = wrapper
        self.cache = cache
        self.max_candidates_per_day = config.get("max_candidates_per_day", 10)
        self.enabled = config.get("enabled", True)

    def filter(
        self,
        screener_results: dict[date, list[tuple[str, float, str]]],
        market_data: dict[str, pd.DataFrame],
    ) -> dict[date, list[tuple[str, float, str]]]:
        """Filter screener results through AI analysis.

        Args:
            screener_results: {date: [(symbol, score, tag), ...]}
            market_data: {symbol: DataFrame} (unused by filter, passed for future use)

        Returns:
            Filtered results in same format, containing only AI-approved stocks.
        """
        if not self.enabled:
            return screener_results

        filtered: dict[date, list[tuple[str, float, str]]] = {}

        for d, candidates in screener_results.items():
            to_analyze = candidates[:self.max_candidates_per_day]
            kept: list[tuple[str, float, str]] = []

            for symbol, score, tag in to_analyze:
                decision = self._get_decision(symbol, d)
                if decision in ("Buy", "Overweight"):
                    kept.append((symbol, score, tag))

            if kept:
                filtered[d] = kept

        total_in = sum(len(v) for v in screener_results.values())
        total_out = sum(len(v) for v in filtered.values())
        logger.info(
            "AI filter: %d candidates → %d approved (%.1f%%)",
            total_in, total_out,
            (total_out / total_in * 100) if total_in > 0 else 0,
        )

        return filtered

    def _get_decision(self, symbol: str, d: date) -> str:
        """Get AI decision for a stock on a date, using cache if available."""
        date_str = d.isoformat()

        cached = self.cache.get(symbol, date_str)
        if cached is not None:
            return cached

        try:
            decision = self.wrapper.analyze(symbol, date_str)
        except Exception:
            decision = "Hold"

        self.cache.set(symbol, date_str, decision)
        return decision
