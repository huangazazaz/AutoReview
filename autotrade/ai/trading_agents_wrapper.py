"""Thin wrapper around TradingAgentsGraph for batch A-share analysis."""
from __future__ import annotations

import logging
from typing import Any

from autotrade.ai.symbol_utils import normalize_a_share_symbol

logger = logging.getLogger(__name__)


class TradingAgentsWrapper:
    """Wraps TradingAgentsGraph for single-stock LLM analysis.

    Handles symbol normalization, lazy initialization, error recovery,
    and timeout protection. All failures default to "Hold" (safe).
    """

    def __init__(self, config: dict[str, Any]):
        self.llm_provider = config.get("llm_provider", "deepseek")
        self.deep_think_llm = config.get("deep_think_llm", "deepseek-chat")
        self.quick_think_llm = config.get("quick_think_llm", "deepseek-chat")
        self.max_debate_rounds = config.get("max_debate_rounds", 1)
        self.timeout = config.get("timeout_seconds", 120)
        self._graph = None  # lazy init

    def _init_graph(self):
        """Lazy-initialize the TradingAgentsGraph."""
        from tradingagents.graph.trading_graph import TradingAgentsGraph
        from tradingagents.default_config import DEFAULT_CONFIG

        cfg = DEFAULT_CONFIG.copy()
        cfg["llm_provider"] = self.llm_provider
        cfg["deep_think_llm"] = self.deep_think_llm
        cfg["quick_think_llm"] = self.quick_think_llm
        cfg["max_debate_rounds"] = self.max_debate_rounds

        self._graph = TradingAgentsGraph(debug=False, config=cfg)

    def analyze(self, symbol: str, date_str: str) -> str:
        """Run multi-agent LLM analysis for one stock on one date.

        Args:
            symbol: 6-digit A-share code (e.g. "000001").
            date_str: Analysis date in "YYYY-MM-DD" format.

        Returns:
            One of: "Buy", "Overweight", "Hold", "Underweight", "Sell".
            Returns "Hold" on any error or timeout.
        """
        if self._graph is None:
            try:
                self._init_graph()
            except Exception as e:
                logger.error("Failed to initialize TradingAgents: %s", e)
                return "Hold"

        normalized = normalize_a_share_symbol(symbol)

        try:
            _, decision = self._graph.propagate(normalized, date_str)
            logger.info("AI analysis: %s on %s → %s", symbol, date_str, decision)
            return decision
        except Exception as e:
            logger.warning(
                "AI analysis failed for %s on %s: %s", symbol, date_str, e
            )
            return "Hold"
