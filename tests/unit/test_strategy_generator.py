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
        assert "ind_ma_" in prompt
        assert "ind_rsi_" in prompt
        assert "ind_macd_macd" in prompt
        assert "ind_bb_lower" in prompt

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


class TestStrategyGeneratorChat:
    """Tests for multi-turn chat functionality."""

    @patch("autotrade.ai.strategy_generator.OpenAI")
    def test_chat_sends_conversation_history(self, mock_openai):
        """chat() should include previous messages in API call."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content=json.dumps({
                "action": "chat",
                "message": "这是一个好问题。",
                "strategy": None,
            })))
        ]
        mock_client.chat.completions.create.return_value = mock_response

        gen = StrategyGenerator(api_key="test-key")
        history = [
            {"role": "user", "content": "做一个均线策略"},
            {"role": "assistant", "content": "已生成策略...",
             "strategy": {"name": "ma_test", "python_code": "class Test(Strategy): ..."}},
        ]
        result = gen.chat(history, "把止损改成3%")

        # Verify the API was called with conversation history embedded in user prompt
        call_args = mock_client.chat.completions.create.call_args
        messages = call_args[1]["messages"]
        assert len(messages) == 2  # system + user (history embedded in user content)
        assert messages[1]["role"] == "user"
        assert "均线策略" in messages[1]["content"]

        assert result["action"] == "chat"

    @patch("autotrade.ai.strategy_generator.OpenAI")
    def test_chat_handles_generate_action(self, mock_openai):
        """chat() should parse generate action with strategy code."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        strategy_code = "class MACross(Strategy):\n    name = 'ma_test'\n    def generate_signals(self, df): return []"
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content=json.dumps({
                "action": "generate",
                "message": "已生成策略。",
                "strategy": {
                    "name": "ma_test",
                    "display_name": "均线测试",
                    "description": "test",
                    "python_code": strategy_code,
                    "yaml_code": "strategy: ma_test\nparams: {}",
                    "reasoning": "simple test",
                },
            })))
        ]
        mock_client.chat.completions.create.return_value = mock_response

        gen = StrategyGenerator(api_key="test-key")
        result = gen.chat([], "做一个测试策略")

        assert result["action"] == "generate"
        assert result["strategy"]["name"] == "ma_test"
        assert result["strategy"]["python_code"] == strategy_code

    @patch("autotrade.ai.strategy_generator.OpenAI")
    def test_chat_handles_modify_action(self, mock_openai):
        """chat() should parse modify action with modified code."""
        mock_client = MagicMock()
        mock_openai.return_value = mock_client

        modified_code = "class MACross(Strategy):\n    name = 'ma_test'\n    stop_loss = 0.03\n    def generate_signals(self, df): return []"
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(message=MagicMock(content=json.dumps({
                "action": "modify",
                "message": "已将止损改为3%。",
                "strategy": {
                    "name": "ma_test",
                    "display_name": "均线测试",
                    "description": "modified",
                    "python_code": modified_code,
                    "yaml_code": "strategy: ma_test\nparams:\n  stop_loss: 0.03",
                    "reasoning": "modified stop loss",
                },
            })))
        ]
        mock_client.chat.completions.create.return_value = mock_response

        gen = StrategyGenerator(api_key="test-key")
        history = [
            {"role": "user", "content": "做一个均线策略"},
            {"role": "assistant", "content": "...", "strategy": {"name": "ma_test", "python_code": "..."}},
        ]
        result = gen.chat(history, "把止损改成3%")

        assert result["action"] == "modify"
        assert "0.03" in result["strategy"]["python_code"]

    def test_chat_build_prompt_includes_history_context(self):
        """_build_chat_prompt should reference previous strategy in history."""
        gen = StrategyGenerator(api_key="test-key")
        history = [
            {"role": "user", "content": "做一个均线金叉策略"},
            {"role": "assistant", "content": "已生成",
             "strategy": {"python_code": "class Test(Strategy): pass"}},
        ]
        prompt = gen._build_chat_prompt(history, "把止损改成3%")
        assert "均线金叉" in prompt
        assert "Test(Strategy)" in prompt or "strategy" in prompt.lower()
        assert "止损" in prompt
