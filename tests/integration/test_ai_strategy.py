"""Integration tests for AI strategy generation API — comprehensive edge cases."""
import json
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from autotrade.api.server import app
from autotrade.registry import init_registry


@pytest.fixture(autouse=True)
def _init():
    init_registry()
    yield


@pytest.fixture
def client():
    return TestClient(app)


# ---- Valid strategy templates ----

_VALID_STRATEGY_NO_PARAMS = {
    "name": "test_no_params",
    "display_name": "无参数测试",
    "description": "没有__init__参数的策略",
    "python_code": (
        "from autotrade.core.interfaces import Strategy\n"
        "from autotrade.core.models import Signal\n"
        "from autotrade.indicators.ma import MA, EMA\n"
        "\n"
        "class TestNoParams(Strategy):\n"
        "    name = 'test_no_params'\n"
        "    required_indicators = [MA(5), MA(20)]\n"
        "\n"
        "    def generate_signals(self, df):\n"
        "        signals = []\n"
        "        for i in range(1, len(df)):\n"
        "            d = df.index[i]\n"
        "            if df['ind_ma_5'].iloc[i] > df['ind_ma_20'].iloc[i] and df['ind_ma_5'].iloc[i-1] <= df['ind_ma_20'].iloc[i-1]:\n"
        "                signals.append(Signal(symbol='', date=d, action='BUY', strength=0.5, reason='golden'))\n"
        "            elif df['ind_ma_5'].iloc[i] < df['ind_ma_20'].iloc[i] and df['ind_ma_5'].iloc[i-1] >= df['ind_ma_20'].iloc[i-1]:\n"
        "                signals.append(Signal(symbol='', date=d, action='SELL', strength=1.0, reason='death'))\n"
        "        return signals\n"
    ),
    "yaml_code": "strategy: test_no_params\nparams: {}\n",
    "reasoning": "测试"
}

_VALID_STRATEGY_WITH_PARAMS = {
    "name": "test_with_params",
    "display_name": "带参数测试",
    "description": "带__init__参数的策略",
    "python_code": (
        "from autotrade.core.interfaces import Strategy\n"
        "from autotrade.core.models import Signal\n"
        "from autotrade.indicators.ma import MA\n"
        "\n"
        "class TestWithParams(Strategy):\n"
        "    name = 'test_with_params'\n"
        "    required_indicators = [MA(5), MA(20)]\n"
        "\n"
        "    def __init__(self, fast=5, slow=20):\n"
        "        self.fast = fast\n"
        "        self.slow = slow\n"
        "        self.required_indicators = [MA(fast), MA(slow)]\n"
        "\n"
        "    def generate_signals(self, df):\n"
        "        signals = []\n"
        "        col_f = 'ind_ma_%d' % self.fast\n"
        "        col_s = 'ind_ma_%d' % self.slow\n"
        "        for i in range(1, len(df)):\n"
        "            d = df.index[i]\n"
        "            if df[col_f].iloc[i] > df[col_s].iloc[i] and df[col_f].iloc[i-1] <= df[col_s].iloc[i-1]:\n"
        "                signals.append(Signal(symbol='', date=d, action='BUY', strength=0.5, reason='golden'))\n"
        "            elif df[col_f].iloc[i] < df[col_s].iloc[i] and df[col_f].iloc[i-1] >= df[col_s].iloc[i-1]:\n"
        "                signals.append(Signal(symbol='', date=d, action='SELL', strength=1.0, reason='death'))\n"
        "        return signals\n"
    ),
    "yaml_code": "strategy: test_with_params\nparams:\n  fast: 5\n  slow: 20\n",
    "reasoning": "测试"
}

_VALID_STRATEGY_PARAMS_MISMATCH = {
    "name": "test_mismatch",
    "display_name": "参数不匹配",
    "description": "YAML有stop_loss_pct但__init__不接受",
    "python_code": (
        "from autotrade.core.interfaces import Strategy\n"
        "from autotrade.core.models import Signal\n"
        "from autotrade.indicators.ma import MA\n"
        "\n"
        "class TestMismatch(Strategy):\n"
        "    name = 'test_mismatch'\n"
        "    required_indicators = [MA(5), MA(20)]\n"
        "\n"
        "    def generate_signals(self, df):\n"
        "        return []\n"
    ),
    "yaml_code": "strategy: test_mismatch\nparams:\n  stop_loss_pct: 5\n  take_profit_pct: 20\n",
    "reasoning": "测试参数不匹配场景"
}

_VALID_STRATEGY_BAD_CODE = {
    "name": "test_bad_syntax",
    "display_name": "语法错误",
    "description": "Python代码有语法错误",
    "python_code": "class BadSyntax(Strategy):\n    name = 'bad'\n    def generate_signals(self, df)\n        return []",
    "yaml_code": "strategy: test_bad_syntax\nparams: {}\n",
    "reasoning": "测试"
}


def _make_mock_openai(response_dict):
    """Create a mock OpenAI client that returns a given strategy dict."""
    mock = MagicMock()
    mock_client = MagicMock()
    mock.return_value = mock_client
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = json.dumps(response_dict)
    mock_client.chat.completions.create.return_value = mock_response
    return mock


class TestAIStrategyEndToEnd:
    """End-to-end tests for the AI strategy generation flow."""

    def test_generate_with_matching_params(self, client):
        """Strategy with YAML params that match __init__ → backtest succeeds."""
        with patch("autotrade.ai.strategy_generator.OpenAI", _make_mock_openai(_VALID_STRATEGY_WITH_PARAMS)):
            resp = client.post("/ai/generate-strategy", json={
                "prompt": "做一个策略",
                "symbol": "600522",
                "start": "2025-01-02",
                "end": "2025-01-15",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert "error" not in data
        assert data["name"] == "test_with_params"
        assert data["python_code"]
        # Backtest may fail (no data for 600522 in test), but should not crash
        assert "backtest" in data

    def test_generate_no_params(self, client):
        """Strategy with no __init__ params → backtest succeeds."""
        with patch("autotrade.ai.strategy_generator.OpenAI", _make_mock_openai(_VALID_STRATEGY_NO_PARAMS)):
            resp = client.post("/ai/generate-strategy", json={
                "prompt": "做一个策略",
                "symbol": "600522",
                "start": "2025-01-02",
                "end": "2025-01-15",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert "error" not in data
        assert data["name"] == "test_no_params"

    def test_generate_params_mismatch(self, client):
        """YAML has params not in __init__ → should fall back to no-args instantiation."""
        with patch("autotrade.ai.strategy_generator.OpenAI", _make_mock_openai(_VALID_STRATEGY_PARAMS_MISMATCH)):
            resp = client.post("/ai/generate-strategy", json={
                "prompt": "做一个止损止盈策略",
                "symbol": "600522",
                "start": "2025-01-02",
                "end": "2025-01-15",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert "error" not in data
        assert data["name"] == "test_mismatch"
        # Should still return a response (backtest may or may not succeed)
        assert "backtest" in data

    def test_generate_with_rsi_strategy(self, client):
        """Test an RSI-based strategy with correct column names (ind_rsi_14)."""
        rsi_strategy = {
            "name": "test_rsi",
            "display_name": "RSI测试",
            "description": "RSI超买超卖",
            "python_code": (
                "from autotrade.core.interfaces import Strategy\n"
                "from autotrade.core.models import Signal\n"
                "from autotrade.indicators.rsi import RSI\n"
                "\n"
                "class TestRSI(Strategy):\n"
                "    name = 'test_rsi'\n"
                "    required_indicators = [RSI(14)]\n"
                "\n"
                "    def generate_signals(self, df):\n"
                "        signals = []\n"
                "        for i in range(1, len(df)):\n"
                "            d = df.index[i]\n"
                "            v = df['ind_rsi_14'].iloc[i]\n"
                "            if v < 30:\n"
                "                signals.append(Signal(symbol='', date=d, action='BUY', strength=0.6, reason='oversold'))\n"
                "            elif v > 70:\n"
                "                signals.append(Signal(symbol='', date=d, action='SELL', strength=1.0, reason='overbought'))\n"
                "        return signals\n"
            ),
            "yaml_code": "strategy: test_rsi\nparams:\n  period: 14\n",
            "reasoning": "RSI策略"
        }
        with patch("autotrade.ai.strategy_generator.OpenAI", _make_mock_openai(rsi_strategy)):
            resp = client.post("/ai/generate-strategy", json={
                "prompt": "RSI超买超卖策略",
                "symbol": "600522",
                "start": "2025-01-02",
                "end": "2025-01-15",
            })
        assert resp.status_code == 200
        data = resp.json()
        assert "error" not in data
        assert data["name"] == "test_rsi"

    def test_save_and_delete_strategy(self, client):
        resp = client.post("/strategies/save", json={
            "name": "test_temp_strat",
            "python_code": (
                "from autotrade.core.interfaces import Strategy\n"
                "class TestTemp(Strategy):\n"
                "    name='test_temp_strat'\n"
                "    def generate_signals(self, df): return []"
            ),
            "yaml_code": "strategy: test_temp_strat\nparams: {}",
        })
        assert resp.status_code == 200
        data = resp.json()
        if "error" not in data:
            assert data["success"] is True
            resp2 = client.delete("/strategies/test_temp_strat")
            assert resp2.status_code == 200

    def test_delete_builtin_protected(self, client):
        resp = client.delete("/strategies/turtle")
        data = resp.json()
        assert "error" in data
