import time
import pytest
from autotrade.ai.session_store import SessionStore, Session, ChatMessage


class TestSessionStore:
    def test_create_session_returns_valid_session(self):
        store = SessionStore()
        session = store.create_session(title="Test")
        assert isinstance(session, Session)
        assert len(session.session_id) == 12
        assert session.title == "Test"
        assert session.messages == []
        assert session.current_strategy_code is None

    def test_get_session_returns_none_for_missing(self):
        store = SessionStore()
        assert store.get_session("nonexistent") is None

    def test_get_session_returns_created_session(self):
        store = SessionStore()
        session = store.create_session(title="Test")
        found = store.get_session(session.session_id)
        assert found is session
        assert found.session_id == session.session_id

    def test_add_message_appends_and_updates_last_active(self):
        store = SessionStore()
        session = store.create_session()
        old_active = session.last_active
        time.sleep(0.01)
        msg = ChatMessage(role="user", content="hello", timestamp="2026-01-01T00:00:00")
        store.add_message(session.session_id, msg)
        assert len(session.messages) == 1
        assert session.messages[0].content == "hello"
        assert session.last_active > old_active

    def test_add_message_raises_for_missing_session(self):
        store = SessionStore()
        msg = ChatMessage(role="user", content="hi", timestamp="2026-01-01T00:00:00")
        with pytest.raises(KeyError):
            store.add_message("nonexistent", msg)

    def test_delete_session_removes_and_returns_true(self):
        store = SessionStore()
        session = store.create_session()
        assert store.delete_session(session.session_id) is True
        assert store.get_session(session.session_id) is None

    def test_delete_session_returns_false_for_missing(self):
        store = SessionStore()
        assert store.delete_session("nonexistent") is False

    def test_cleanup_expired_removes_stale_sessions(self):
        store = SessionStore(ttl_seconds=0)  # Immediate expiry
        session = store.create_session(title="stale")
        removed = store.cleanup_expired()
        assert removed >= 1
        assert store.get_session(session.session_id) is None

    def test_cleanup_expired_preserves_active_sessions(self):
        store = SessionStore(ttl_seconds=3600)
        session = store.create_session(title="active")
        removed = store.cleanup_expired()
        assert store.get_session(session.session_id) is not None

    def test_thread_safety_concurrent_adds(self):
        import threading
        store = SessionStore()
        session = store.create_session()
        errors = []

        def add_messages(start: int):
            for i in range(start, start + 50):
                try:
                    msg = ChatMessage(role="user", content=f"msg{i}",
                                      timestamp="2026-01-01T00:00:00")
                    store.add_message(session.session_id, msg)
                except Exception as e:
                    errors.append(str(e))

        t1 = threading.Thread(target=add_messages, args=(0,))
        t2 = threading.Thread(target=add_messages, args=(50,))
        t1.start(); t2.start(); t1.join(); t2.join()

        assert len(errors) == 0
        assert len(session.messages) == 100
