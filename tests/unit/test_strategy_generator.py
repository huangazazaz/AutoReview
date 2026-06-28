"""Tests for StrategyGenerator."""
import json
import pytest
from unittest.mock import patch, MagicMock

from autotrade.ai.strategy_generator import StrategyGenerator, STRATEGY_GEN_PROMPT


class TestStrategyGenerator:
    """Unit tests for StrategyGenerator."""

    def test_build_prompt_includes_user_input(self):
        gen = StrategyGenerator(api_key="test-key")
        prompt = gen._build_prompt("做一个均线金叉策略")
        assert "均线金叉" in prompt
        assert "Strategy" in prompt
        assert "json" in prompt.lower()

    def test_parse_valid_json_response(self):
        gen = StrategyGenerator(api_key="test-key")
        raw = json.dumps({
            "name": "ma_test",
            "display_name": "测试策略",
            "description": "测试用",
            "python_code": "class MaTest:\n    pass",
            "yaml_code": "strategy: ma_test\nparams: {}",
            "reasoning": "test"
        })
        result = gen._parse_response(raw)
        assert result["name"] == "ma_test"
        assert result["display_name"] == "测试策略"
        assert "class MaTest" in result["python_code"]

    def test_parse_invalid_json_returns_error(self):
        gen = StrategyGenerator(api_key="test-key")
        result = gen._parse_response("not json at all {broken")
        assert "error" in result
        assert "raw" in result

    def test_parse_missing_fields_returns_error(self):
        gen = StrategyGenerator(api_key="test-key")
        result = gen._parse_response('{"name": "only_name"}')
        assert "error" in result

    def test_validate_python_syntax_ok(self):
        gen = StrategyGenerator(api_key="test-key")
        code = "class Foo:\n    def bar(self):\n        return 1"
        ok, err = gen._validate_python(code)
        assert ok is True
        assert err is None

    def test_validate_python_syntax_error(self):
        gen = StrategyGenerator(api_key="test-key")
        code = "class Foo:\n    def bar(self)\n        return 1"  # missing colon
        ok, err = gen._validate_python(code)
        assert ok is False
        assert err is not None

    def test_name_conflict_resolution(self):
        gen = StrategyGenerator(api_key="test-key")
        # "turtle" already exists
        name = gen._resolve_name("turtle")
        assert name.startswith("turtle_")
        # Non-conflicting name stays the same
        name2 = gen._resolve_name("totally_new_strategy")
        assert name2 == "totally_new_strategy"

    @patch("autotrade.ai.strategy_generator.OpenAI")
    def test_generate_success(self, mock_openai):
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "name": "test_strat",
            "display_name": "测试",
            "description": "desc",
            "python_code": "from autotrade.core.interfaces import Strategy\n\nclass TestStrat(Strategy):\n    name = 'test_strat'\n    def generate_signals(self, df):\n        return []",
            "yaml_code": "strategy: test_strat\nparams: {}",
            "reasoning": "test"
        })
        mock_client.chat.completions.create.return_value = mock_response

        gen = StrategyGenerator(api_key="test-key")
        result = gen.generate("做一个测试策略")

        assert "error" not in result
        assert result["name"] == "test_strat"
        assert result["python_code"]

    @patch("autotrade.ai.strategy_generator.OpenAI")
    def test_generate_api_error(self, mock_openai):
        mock_client = MagicMock()
        mock_openai.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API down")

        gen = StrategyGenerator(api_key="test-key")
        result = gen.generate("做一个策略")

        assert "error" in result
        assert "AI 服务暂时不可用" in result["error"]
