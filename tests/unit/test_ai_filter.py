"""Tests for AI filter components."""
from autotrade.ai.symbol_utils import normalize_a_share_symbol


class TestSymbolNormalization:
    def test_shanghai_600(self):
        assert normalize_a_share_symbol("600519") == "600519.SS"

    def test_shanghai_601(self):
        assert normalize_a_share_symbol("601318") == "601318.SS"

    def test_shanghai_603(self):
        assert normalize_a_share_symbol("603259") == "603259.SS"

    def test_shanghai_688(self):
        assert normalize_a_share_symbol("688981") == "688981.SS"

    def test_shenzhen_000(self):
        assert normalize_a_share_symbol("000001") == "000001.SZ"

    def test_shenzhen_002(self):
        assert normalize_a_share_symbol("002415") == "002415.SZ"

    def test_shenzhen_300(self):
        assert normalize_a_share_symbol("300750") == "300750.SZ"

    def test_unknown_prefix_defaults_sz(self):
        assert normalize_a_share_symbol("123456") == "123456.SZ"


import tempfile
from pathlib import Path
from autotrade.ai.llm_cache import LLMCache


class TestLLMCache:
    def test_cache_hit(self):
        cache = LLMCache()
        cache.set("000001", "2024-01-15", "Buy")
        assert cache.get("000001", "2024-01-15") == "Buy"

    def test_cache_miss_returns_none(self):
        cache = LLMCache()
        assert cache.get("000001", "2024-01-15") is None

    def test_cache_different_date_different_entry(self):
        cache = LLMCache()
        cache.set("000001", "2024-01-15", "Buy")
        cache.set("000001", "2024-01-16", "Sell")
        assert cache.get("000001", "2024-01-15") == "Buy"
        assert cache.get("000001", "2024-01-16") == "Sell"

    def test_cache_different_symbol_independent(self):
        cache = LLMCache()
        cache.set("000001", "2024-01-15", "Buy")
        cache.set("600519", "2024-01-15", "Sell")
        assert cache.get("000001", "2024-01-15") == "Buy"
        assert cache.get("600519", "2024-01-15") == "Sell"

    def test_cache_persist_and_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "cache.json"
            cache = LLMCache(cache_dir=str(tmp))
            cache.set("000001", "2024-01-15", "Buy")
            cache.set("600519", "2024-01-16", "Sell")
            cache.save_to_disk()

            # Load into new cache
            cache2 = LLMCache(cache_dir=str(tmp))
            cache2.load_from_disk()
            assert cache2.get("000001", "2024-01-15") == "Buy"
            assert cache2.get("600519", "2024-01-16") == "Sell"
            assert cache2.get("000001", "2024-01-17") is None

    def test_cache_overwrite(self):
        cache = LLMCache()
        cache.set("000001", "2024-01-15", "Buy")
        cache.set("000001", "2024-01-15", "Sell")  # overwrite
        assert cache.get("000001", "2024-01-15") == "Sell"


from unittest.mock import patch, MagicMock
from autotrade.ai.trading_agents_wrapper import TradingAgentsWrapper


class TestTradingAgentsWrapper:
    def test_init_creates_config(self):
        config = {
            "llm_provider": "deepseek",
            "deep_think_llm": "deepseek-chat",
            "quick_think_llm": "deepseek-chat",
            "max_debate_rounds": 1,
            "timeout_seconds": 120,
        }
        wrapper = TradingAgentsWrapper(config)
        assert wrapper.llm_provider == "deepseek"
        assert wrapper.timeout == 120

    def test_lazy_init_graph(self):
        """Graph should not be created until first analyze call."""
        wrapper = TradingAgentsWrapper({})
        assert wrapper._graph is None

    @patch("tradingagents.graph.trading_graph.TradingAgentsGraph")
    def test_analyze_returns_buy(self, mock_graph_class):
        """Mocked TradingAgents returns 'Buy'."""
        mock_graph = MagicMock()
        mock_graph.propagate.return_value = ({}, "Buy")
        mock_graph_class.return_value = mock_graph

        wrapper = TradingAgentsWrapper({})
        result = wrapper.analyze("000001", "2024-01-15")
        assert result == "Buy"
        mock_graph.propagate.assert_called_once_with("000001.SZ", "2024-01-15")

    @patch("tradingagents.graph.trading_graph.TradingAgentsGraph")
    def test_analyze_handles_sell(self, mock_graph_class):
        mock_graph = MagicMock()
        mock_graph.propagate.return_value = ({}, "Sell")
        mock_graph_class.return_value = mock_graph

        wrapper = TradingAgentsWrapper({})
        result = wrapper.analyze("600519", "2024-06-15")
        assert result == "Sell"
        mock_graph.propagate.assert_called_once_with("600519.SS", "2024-06-15")

    @patch("tradingagents.graph.trading_graph.TradingAgentsGraph")
    def test_analyze_error_returns_hold(self, mock_graph_class):
        mock_graph = MagicMock()
        mock_graph.propagate.side_effect = RuntimeError("API error")
        mock_graph_class.return_value = mock_graph

        wrapper = TradingAgentsWrapper({})
        result = wrapper.analyze("000001", "2024-01-15")
        assert result == "Hold"

    @patch("tradingagents.graph.trading_graph.TradingAgentsGraph")
    def test_analyze_timeout_returns_hold(self, mock_graph_class):
        mock_graph = MagicMock()
        mock_graph.propagate.side_effect = TimeoutError("timeout")
        mock_graph_class.return_value = mock_graph

        wrapper = TradingAgentsWrapper({"timeout_seconds": 1})
        result = wrapper.analyze("000001", "2024-01-15")
        assert result == "Hold"


from datetime import date
from autotrade.ai.ai_filter import AIFilter


def _make_mock_wrapper(decisions: dict):
    """Create a mock TradingAgentsWrapper that returns predefined decisions."""
    mock = MagicMock()
    def analyze(symbol, date_str):
        key = f"{symbol}|{date_str}"
        return decisions.get(key, "Hold")
    mock.analyze = analyze
    return mock


class TestAIFilter:
    def test_keep_buy_drop_hold_and_sell(self):
        wrapper = _make_mock_wrapper({
            "000001|2024-01-15": "Buy",
            "000002|2024-01-15": "Hold",
            "000003|2024-01-15": "Sell",
            "000004|2024-01-15": "Overweight",
        })
        cache = LLMCache()
        ai_filter = AIFilter(wrapper, cache, config={
            "max_candidates_per_day": 10,
            "enabled": True,
        })

        candidates = {
            date(2024, 1, 15): [
                ("000001", 0.9, "strong"),
                ("000002", 0.8, "strong"),
                ("000003", 0.7, "strong"),
                ("000004", 0.6, "strong"),
            ]
        }

        result = ai_filter.filter(candidates, {})
        kept = result.get(date(2024, 1, 15), [])
        kept_symbols = [s for s, _, _ in kept]
        assert "000001" in kept_symbols      # Buy
        assert "000004" in kept_symbols      # Overweight
        assert "000002" not in kept_symbols  # Hold
        assert "000003" not in kept_symbols  # Sell

    def test_disabled_passthrough(self):
        wrapper = _make_mock_wrapper({})
        cache = LLMCache()
        ai_filter = AIFilter(wrapper, cache, config={
            "max_candidates_per_day": 10,
            "enabled": False,
        })

        candidates = {
            date(2024, 1, 15): [
                ("000001", 0.9, "strong"),
                ("000002", 0.8, "strong"),
            ]
        }

        result = ai_filter.filter(candidates, {})
        assert result == candidates

    def test_respects_max_candidates(self):
        """Only top N candidates should be analyzed."""
        analyzed = []
        mock = MagicMock()
        def analyze(symbol, date_str):
            analyzed.append(symbol)
            return "Buy"
        mock.analyze = analyze

        cache = LLMCache()
        ai_filter = AIFilter(mock, cache, config={
            "max_candidates_per_day": 3,
            "enabled": True,
        })

        candidates = {
            date(2024, 1, 15): [
                ("A", 0.9, "s"), ("B", 0.8, "s"), ("C", 0.7, "s"),
                ("D", 0.6, "s"), ("E", 0.5, "s"),
            ]
        }

        ai_filter.filter(candidates, {})
        assert len(analyzed) == 3
        assert analyzed == ["A", "B", "C"]

    def test_empty_candidates_no_error(self):
        wrapper = _make_mock_wrapper({})
        cache = LLMCache()
        ai_filter = AIFilter(wrapper, cache, config={
            "max_candidates_per_day": 10,
            "enabled": True,
        })

        result = ai_filter.filter({}, {})
        assert result == {}

    def test_cache_prevents_reanalysis(self):
        """Cached decisions should not trigger new LLM calls."""
        analyzed = []
        mock = MagicMock()
        def analyze(symbol, date_str):
            analyzed.append(symbol)
            return "Buy"
        mock.analyze = analyze

        cache = LLMCache()
        cache.set("000001", "2024-01-15", "Buy")  # pre-cached

        ai_filter = AIFilter(mock, cache, config={
            "max_candidates_per_day": 10,
            "enabled": True,
        })

        candidates = {
            date(2024, 1, 15): [("000001", 0.9, "s")]
        }

        result = ai_filter.filter(candidates, {})
        assert len(analyzed) == 0
        assert len(result[date(2024, 1, 15)]) == 1
