"""Integration tests for AI chat API endpoints."""
import os
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from autotrade.api.server import app
    return TestClient(app)


@pytest.fixture
def api_key_is_set():
    """Check if DEEPSEEK_API_KEY is configured."""
    return bool(os.environ.get("DEEPSEEK_API_KEY"))


class TestChatAPI:
    def test_post_chat_creates_session_and_returns_response(self, client, api_key_is_set):
        """POST /ai/chat without session_id should create a new session."""
        res = client.post("/ai/chat", json={
            "prompt": "hello",
            "symbol": "600522",
        })
        assert res.status_code == 200
        data = res.json()

        if not api_key_is_set:
            # Without API key, endpoint returns error message
            assert "error" in data
            return

        assert "session_id" in data
        assert len(data["session_id"]) == 12
        assert "message" in data
        assert data["message"]["role"] == "assistant"

    def test_post_chat_continues_session(self, client, api_key_is_set):
        """POST /ai/chat with session_id should continue existing session."""
        if not api_key_is_set:
            pytest.skip("DEEPSEEK_API_KEY not set")

        # First message
        res1 = client.post("/ai/chat", json={"prompt": "hello", "symbol": "600522"})
        assert res1.status_code == 200
        sid = res1.json()["session_id"]

        # Second message continues same session
        res2 = client.post("/ai/chat", json={
            "session_id": sid,
            "prompt": "how are you",
            "symbol": "600522",
        })
        assert res2.status_code == 200
        assert res2.json()["session_id"] == sid

    def test_get_chat_history_returns_session(self, client, api_key_is_set):
        """GET /ai/chat/{id} should return session with messages."""
        if not api_key_is_set:
            pytest.skip("DEEPSEEK_API_KEY not set")

        # Create session with a message
        res = client.post("/ai/chat", json={"prompt": "test", "symbol": "600522"})
        sid = res.json()["session_id"]

        # Get history
        res2 = client.get(f"/ai/chat/{sid}")
        assert res2.status_code == 200
        data = res2.json()
        assert data["session"]["session_id"] == sid
        assert len(data["messages"]) >= 2  # user + assistant

    def test_get_chat_history_404_for_missing(self, client):
        """GET /ai/chat/{id} should return 404 for nonexistent session."""
        res = client.get("/ai/chat/nonexistent123")
        assert res.status_code == 404

    def test_delete_chat_removes_session(self, client, api_key_is_set):
        """DELETE /ai/chat/{id} should remove session."""
        if not api_key_is_set:
            pytest.skip("DEEPSEEK_API_KEY not set")

        res = client.post("/ai/chat", json={"prompt": "test", "symbol": "600522"})
        sid = res.json()["session_id"]

        res2 = client.delete(f"/ai/chat/{sid}")
        assert res2.status_code == 200
        assert res2.json()["ok"] is True

        # Verify gone
        res3 = client.get(f"/ai/chat/{sid}")
        assert res3.status_code == 404

    def test_delete_chat_404_for_missing(self, client):
        """DELETE /ai/chat/{id} should return 404 for nonexistent session."""
        res = client.delete("/ai/chat/nonexistent123")
        assert res.status_code == 404
