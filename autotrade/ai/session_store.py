"""Thread-safe in-memory session store for AI chat conversations."""
from __future__ import annotations

import uuid
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class ChatMessage:
    """A single message in a conversation."""
    role: str                    # "user" | "assistant"
    content: str                 # Natural language text
    timestamp: str               # ISO format timestamp
    strategy: Optional[dict] = None    # Strategy result (code, yaml, etc.)
    backtest: Optional[dict] = None    # Backtest metrics


@dataclass
class Session:
    """A conversation session."""
    session_id: str
    title: str = ""
    created_at: str = ""
    last_active: str = ""
    messages: list[ChatMessage] = field(default_factory=list)
    current_strategy_code: Optional[str] = None
    current_yaml_code: Optional[str] = None


class SessionStore:
    """Thread-safe in-memory store for chat sessions.

    Sessions expire after `ttl_seconds` of inactivity. Call `cleanup_expired()`
    periodically (e.g. every 30 min) to remove stale sessions.
    """

    def __init__(self, ttl_seconds: int = 7200):
        self._sessions: dict[str, Session] = {}
        self._lock = threading.Lock()
        self._ttl_seconds = ttl_seconds

    def create_session(self, title: str = "") -> Session:
        """Create a new session and return it."""
        session_id = uuid.uuid4().hex[:12]
        now = datetime.now(timezone.utc).isoformat()
        session = Session(
            session_id=session_id,
            title=title,
            created_at=now,
            last_active=now,
        )
        with self._lock:
            self._sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID, or None if not found."""
        with self._lock:
            return self._sessions.get(session_id)

    def add_message(self, session_id: str, msg: ChatMessage) -> None:
        """Append a message to the session and update last_active. Raises KeyError if session missing."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(f"Session not found: {session_id}")
            session.messages.append(msg)
            session.last_active = datetime.now(timezone.utc).isoformat()

    def update_strategy(self, session_id: str, python_code: str, yaml_code: str) -> None:
        """Update the current strategy code for a session."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                raise KeyError(f"Session not found: {session_id}")
            session.current_strategy_code = python_code
            session.current_yaml_code = yaml_code

    def delete_session(self, session_id: str) -> bool:
        """Delete a session. Returns True if it existed."""
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    def cleanup_expired(self) -> int:
        """Remove sessions that have been inactive beyond TTL. Returns count removed."""
        now = datetime.now(timezone.utc)
        expired_ids: list[str] = []
        with self._lock:
            for sid, session in self._sessions.items():
                try:
                    last = datetime.fromisoformat(session.last_active)
                    if (now - last).total_seconds() > self._ttl_seconds:
                        expired_ids.append(sid)
                except (ValueError, TypeError):
                    expired_ids.append(sid)
            for sid in expired_ids:
                del self._sessions[sid]
        return len(expired_ids)
