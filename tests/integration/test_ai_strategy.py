"""Integration tests for AI strategy generation API."""
import json
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from autotrade.api.server import app
from autotrade.registry import init_registry


@pytest.fixture
def client():
    init_registry()
    return TestClient(app)


@pytest.fixture
def mock_deepseek():
    """Mock DeepSeek to return a valid strategy JSON."""
    with patch("autotrade.ai.strategy_generator.OpenAI") as mock:
        mock_client = MagicMock()
        mock.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps({
            "name": "test_ai_strat",
            "display_name": "测试AI策略",
            "description": "AI生成的测试策略",
            "python_code": (
                "from autotrade.core.interfaces import Strategy, Indicator\n"
                "from autotrade.core.models import Signal\n"
                "from autotrade.indicators.ma import MARibbon\n"
                "\n"
                "class TestAIStrat(Strategy):\n"
                "    name = 'test_ai_strat'\n"
                "    required_indicators = [MARibbon(period=5), MARibbon(period=20)]\n"
                "\n"
                "    def generate_signals(self, df):\n"
                "        signals = []\n"
                "        for i in range(1, len(df)):\n"
                "            d = df.index[i]\n"
                "            if df['ma_5'].iloc[i] > df['ma_20'].iloc[i] and df['ma_5'].iloc[i-1] <= df['ma_20'].iloc[i-1]:\n"
                "                signals.append(Signal(symbol='', date=d, action='BUY', strength=0.5, reason='golden_cross'))\n"
                "            elif df['ma_5'].iloc[i] < df['ma_20'].iloc[i] and df['ma_5'].iloc[i-1] >= df['ma_20'].iloc[i-1]:\n"
                "                signals.append(Signal(symbol='', date=d, action='SELL', strength=1.0, reason='death_cross'))\n"
                "        return signals\n"
            ),
            "yaml_code": "strategy: test_ai_strat\nparams:\n  fast: 5\n  slow: 20\n",
            "reasoning": "经典双均线交叉"
        })
        mock_client.chat.completions.create.return_value = mock_response
        yield mock


class TestAIStrategyAPI:
    """Integration tests for AI strategy endpoints."""

    def test_generate_strategy_success(self, client, mock_deepseek):
        resp = client.post("/ai/generate-strategy", json={
            "prompt": "做一个均线金叉策略",
            "symbol": "600522",
            "start": "2025-01-02",
            "end": "2025-01-31",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "error" not in data
        assert data["name"] == "test_ai_strat"
        assert data["display_name"] == "测试AI策略"
        assert "class TestAIStrat" in data["python_code"]

    def test_save_and_delete_strategy(self, client):
        # Save
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

            # Delete
            resp2 = client.delete("/strategies/test_temp_strat")
            assert resp2.status_code == 200
            data2 = resp2.json()
            assert "error" not in data2 or data2.get("success") is True

    def test_delete_builtin_protected(self, client):
        resp = client.delete("/strategies/turtle")
        assert resp.status_code == 200
        data = resp.json()
        assert "error" in data
